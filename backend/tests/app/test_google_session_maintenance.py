import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from pydantic import SecretStr

from tests.support.paths import FIXTURES


def load(name):
    path = Path(__file__).resolve().parents[3] / "scripts/tooling" / (name + ".py")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.asyncio
async def test_google_check_uses_one_budgeted_search_with_no_details(tmp_path, monkeypatch, capsys):
    module = load("check_google_session")
    session = tmp_path / "session.json"
    session.write_text(json.dumps({"cookies": [{"name": "SID", "value": "synthetic", "domain": ".google.com", "path": "/", "expires": -1}]}))
    session.chmod(0o600)
    settings = SimpleNamespace(database_url=SecretStr("synthetic"), maps_web_session_file=session, maps_requests_per_minute=60)
    monkeypatch.setattr(module, "Settings", lambda: settings)
    budgets, closed, calls = [], [], []

    class Store:
        async def consume(self, source, limit):
            budgets.append((source, limit))

        async def close(self):
            closed.append(True)

    async def connect(dsn):
        return Store()

    monkeypatch.setattr(module.PostgresPricingCache, "connect", connect)
    row = json.loads((FIXTURES / "maps_web_fuel_observed.json").read_text())

    def handle(request):
        calls.append(request.url.path)
        assert request.url.path == "/search"
        return httpx.Response(200, text=")]}'\n" + json.dumps([row]))

    original = httpx.AsyncClient
    monkeypatch.setattr(module.httpx, "AsyncClient", lambda **kwargs: original(transport=httpx.MockTransport(handle), **kwargs))
    assert await module.check() == 0
    assert json.loads(capsys.readouterr().out)["status"] == "full_fuel_table_available"
    assert calls == ["/search"] and budgets == [("maps", 60)] and closed == [True]


def installer(tmp_path, monkeypatch):
    module = load("install_google_session")
    monkeypatch.setattr(module, "ROOT", tmp_path)
    active, candidate = tmp_path / "active.json", tmp_path / "candidate.json"
    monkeypatch.setattr(module, "ACTIVE", active)
    monkeypatch.setattr(module, "CANDIDATE", candidate)
    active.write_text("previous working session")
    candidate.write_text("new candidate")
    active.chmod(0o600)
    candidate.chmod(0o600)
    (tmp_path / "check_google_session.py").write_text("candidate check")
    return module, active, candidate


def test_rejected_candidate_preserves_active_credentials(tmp_path, monkeypatch, capsys):
    module, active, candidate = installer(tmp_path, monkeypatch)
    monkeypatch.setattr(module.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(returncode=2))
    assert module.main() == 2
    assert active.read_text() == "previous working session"
    assert candidate.exists()
    assert "new candidate" not in capsys.readouterr().out


def test_validated_candidate_replaces_atomically_and_invalidates_cache(tmp_path, monkeypatch, capsys):
    module, active, candidate = installer(tmp_path, monkeypatch)
    calls = []

    def run(args, **kwargs):
        calls.append((args, kwargs["input"]))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(module.subprocess, "run", run)
    assert module.main() == 0
    assert active.read_text() == "new candidate" and not candidate.exists()
    assert active.stat().st_mode & 0o777 == 0o600
    assert "GASWISE_MAPS_WEB_SESSION_FILE=/run/gaswise/google-maps-http-session.candidate.json" in calls[0][0]
    assert "UPDATE gaswise.query_cache" in calls[1][1]
    assert json.loads(capsys.readouterr().out)["status"] == "installed"
