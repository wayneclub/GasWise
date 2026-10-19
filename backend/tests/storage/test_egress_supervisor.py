import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('egress_supervisor', Path(__file__).resolve().parents[3] / 'scripts/infra/manage_pricing_egress.py')
supervisor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(supervisor)


def test_auth_failure_uses_distinct_candidates_and_persistent_three_attempt_limit(tmp_path):
    state = {'attempts': []}
    cities = ['Dallas', 'Miami', 'Seattle', 'Los Angeles']
    path = tmp_path / 'state.json'
    for expected in cities[:3]:
        assert supervisor.next_candidate(state, cities) == expected
        state['attempts'].append({'city': expected, 'result': 'vpn_auth_failed'})
        supervisor.save_state(path, state)
    import json
    assert supervisor.next_candidate(json.loads(path.read_text()), cities) is None
    assert path.stat().st_mode & 0o777 == 0o600


def test_only_vpn_errors_trigger_node_rotation():
    assert supervisor.failure_reason('AUTH_FAILED', 'running') == 'vpn_auth_failed'
    assert supervisor.failure_reason('HTTP 429 or 403', 'running') is None
    assert supervisor.failure_reason('normal startup', 'exited') == 'vpn_startup_failed'


def test_existing_unowned_container_cannot_be_deleted(monkeypatch):
    import json
    calls = []
    def docker(*args):
        calls.append(args)
        return json.dumps([{'Config': {'Labels': {}}}])
    monkeypatch.setattr(supervisor, 'docker', docker)
    with pytest.raises(RuntimeError, match='not owned'):
        supervisor.remove_owned('gluetun')
    assert len(calls) == 1


def test_main_rotates_after_auth_failure_then_stops_on_healthy_exit(monkeypatch, tmp_path):
    import json
    import sys
    created = []
    outcomes = iter(['vpn_auth_failed', 'healthy'])
    monkeypatch.setattr(sys, 'argv', ['manage', '--state', str(tmp_path / 'state.json')])
    monkeypatch.setattr(supervisor, 'remove_owned', lambda name: None)
    monkeypatch.setattr(supervisor, 'create_exit', lambda source, target, city, network: created.append(city))
    monkeypatch.setattr(supervisor, 'monitor', lambda *args: next(outcomes))
    supervisor.main()
    assert created == ['Dallas', 'Miami']
    assert json.loads((tmp_path / 'state.json').read_text())['attempts'][-1]['result'] == 'healthy'


def test_restart_resumes_healthy_owned_exit_without_replacing_it(monkeypatch, tmp_path):
    import json
    import sys
    path = tmp_path / 'state.json'
    supervisor.save_state(path, {'attempts': [{'city': 'Dallas', 'result': 'healthy'}]})
    monkeypatch.setattr(sys, 'argv', ['manage', '--state', str(path)])
    monkeypatch.setattr(supervisor, 'docker', lambda *args: json.dumps([{'Config': {'Labels': {'gaswise.purpose': 'managed-pricing-egress'}}, 'State': {'Status': 'running'}}]))
    monkeypatch.setattr(supervisor, 'monitor', lambda *args: 'healthy')
    monkeypatch.setattr(supervisor, 'create_exit', lambda *args: pytest.fail('Healthy exit was replaced'))
    supervisor.main()
