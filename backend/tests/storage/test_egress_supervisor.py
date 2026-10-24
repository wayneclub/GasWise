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
    monkeypatch.setattr(supervisor, 'publish_primary_health', lambda *args: True)
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


def test_https_us_verification_is_required_before_lane_becomes_available(monkeypatch, tmp_path):
    import json

    calls = []
    health = tmp_path / 'health.json'
    rows = [{
        'Config': {'Labels': {'gaswise.purpose': 'managed-pricing-egress'}},
        'State': {'Status': 'running', 'Health': {'Status': 'healthy'}},
    }]

    def docker(*args):
        calls.append(args)
        if args[0] == 'inspect':
            return json.dumps(rows)
        if args[0] == 'logs':
            return ''
        if args[0] == 'exec':
            return json.dumps({'country': 'CA'})
        raise AssertionError(args)

    monkeypatch.setattr(supervisor, 'docker', docker)
    assert supervisor.monitor('gaswise-egress-2', False, health) == 'egress_verification_failed'
    assert json.loads(health.read_text())['unavailable_lanes'] == [1]
    assert any(call[0] == 'exec' for call in calls)


def test_verified_us_https_lane_publishes_evidence_without_secrets(monkeypatch, tmp_path):
    import json

    health = tmp_path / 'health.json'
    rows = [{
        'Config': {'Labels': {'gaswise.purpose': 'managed-pricing-egress'}},
        'State': {'Status': 'running', 'Health': {'Status': 'healthy'}},
    }]
    monkeypatch.setattr(supervisor, 'docker', lambda *args: (
        json.dumps(rows) if args[0] == 'inspect' else '' if args[0] == 'logs'
        else json.dumps({'country': 'US'})
    ))
    assert supervisor.monitor('gaswise-egress-2', False, health) == 'healthy'
    saved = json.loads(health.read_text())
    assert saved['unavailable_lanes'] == []
    assert saved['verification']['1'] == {'https_status': 200, 'country': 'US'}


def test_exhausted_generation_waits_then_reopens_candidates():
    state = {'attempts': [
        {'city': 'Dallas', 'result': 'egress_verification_failed'},
        {'city': 'Miami', 'result': 'vpn_auth_failed'},
        {'city': 'Seattle', 'result': 'vpn_health_timeout'},
    ]}
    assert not supervisor.prepare_generation(state, now=1000, maximum=3, cooldown=7200)
    assert state['cooldown_until'] == 8200
    assert not supervisor.prepare_generation(state, now=8199, maximum=3, cooldown=7200)
    assert supervisor.prepare_generation(state, now=8200, maximum=3, cooldown=7200)
    assert state['attempts'] == []
    assert state['generation'] == 2


def test_unverified_primary_is_excluded_while_verified_replacement_stays_available(monkeypatch, tmp_path):
    import json

    health = tmp_path / 'health.json'
    rows = [{
        'Config': {'Labels': {'gaswise.purpose': 'managed-pricing-egress'}},
        'State': {'Status': 'running', 'Health': {'Status': 'healthy'}},
    }]

    def docker(*args):
        if args[0] == 'inspect':
            return json.dumps(rows)
        if args[0] == 'logs':
            return ''
        if args[0] == 'exec':
            target = args[5]
            return json.dumps({'country': 'CA' if target == 'gluetun' else 'US'})
        raise AssertionError(args)

    monkeypatch.setattr(supervisor, 'docker', docker)
    assert supervisor.monitor('gaswise-egress-2', False, health, 300, 'gluetun') == 'healthy'
    saved = json.loads(health.read_text())
    assert saved['unavailable_lanes'] == [0]
    assert saved['verification']['1'] == {'https_status': 200, 'country': 'US'}


def test_no_replacement_snapshot_still_verifies_primary(monkeypatch, tmp_path):
    import json

    health = tmp_path / 'health.json'
    monkeypatch.setattr(supervisor, 'verify_us_https', lambda target: None)
    assert not supervisor.publish_primary_health(health, 'gluetun')
    assert json.loads(health.read_text())['unavailable_lanes'] == [0, 1]


def test_target_startup_failure_does_not_assume_primary_is_available(monkeypatch, tmp_path):
    import json

    health = tmp_path / 'health.json'
    row = {'State': {'Status': 'exited', 'Health': {'Status': 'unhealthy'}}}
    monkeypatch.setattr(supervisor, 'docker', lambda *args: json.dumps([row]) if args[0] == 'inspect' else '')
    monkeypatch.setattr(supervisor, 'verify_us_https', lambda target: None)
    assert supervisor.monitor('gaswise-egress-2', False, health, 300, 'gluetun') == 'vpn_startup_failed'
    assert json.loads(health.read_text())['unavailable_lanes'] == [0, 1]
