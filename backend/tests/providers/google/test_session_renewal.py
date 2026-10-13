import json
import time

import httpx
import pytest

from gaswise.providers.google.maps_web import MapsWebProvider
from gaswise.providers.google.session_renewal import renew_session


def session(tmp_path):
    path = tmp_path / "session.json"
    path.write_text(json.dumps({"cookies": [{"name": "SID", "value": "synthetic-old", "domain": ".google.com", "path": "/", "expires": -1}]}))
    path.chmod(0o600)
    return path


def test_cookie_rotation_is_private_and_used_by_next_request(tmp_path):
    path = session(tmp_path)
    now = time.time()
    renew_session(path, httpx.Headers({"set-cookie": "SID=synthetic-new; Domain=.google.com; Path=/; Secure; HttpOnly; Max-Age=3600"}), now=now)
    assert "SID=synthetic-new" in MapsWebProvider(None, path).headers()["Cookie"]
    assert path.stat().st_mode & 0o777 == 0o600
    cookie = json.loads(path.read_text())["cookies"][0]
    assert cookie["expires"] == now + 3600
    assert cookie["secure"] and cookie["httpOnly"]


def test_unrelated_cookie_domains_paths_and_deleted_values_are_not_saved(tmp_path):
    path = session(tmp_path)
    headers = httpx.Headers([
        ("set-cookie", "SID=untrusted; Domain=evil.test; Path=/"),
        ("set-cookie", "SID=wrong-path; Domain=.google.com; Path=/other"),
        ("set-cookie", "NID=deleted; Domain=.google.com; Path=/; Max-Age=0"),
        ("set-cookie", "SIDCC=synthetic-rotation; Domain=.google.com; Path=/; Max-Age=3600"),
    ])
    renew_session(path, headers, now=1000)
    values = {c["name"]: c["value"] for c in json.loads(path.read_text())["cookies"]}
    assert values == {"SID": "synthetic-old", "SIDCC": "synthetic-rotation"}


def test_response_rotation_preserves_newer_browser_session(tmp_path):
    path = session(tmp_path)
    browser = json.loads(path.read_text())
    browser["cookies"][0]["value"] = "browser-renewed"
    path.write_text(json.dumps(browser))
    renew_session(path, httpx.Headers({"set-cookie": "SIDCC=rotated; Domain=.google.com; Path=/"}))
    assert "SID=browser-renewed" in MapsWebProvider(None, path).headers()["Cookie"]


def test_public_or_symlinked_session_is_not_written(tmp_path):
    path = session(tmp_path)
    path.chmod(0o644)
    headers = httpx.Headers({"set-cookie": "SIDCC=rotated; Domain=.google.com; Path=/"})
    with pytest.raises(ValueError):
        renew_session(path, headers)
    path.chmod(0o600)
    link = tmp_path / "link.json"
    link.symlink_to(path)
    with pytest.raises(ValueError):
        renew_session(link, headers)


def test_in_flight_old_session_cannot_overwrite_browser_renewal(tmp_path):
    path = session(tmp_path)
    renew_session(path, httpx.Headers({"set-cookie": "SID=stale-response; Domain=.google.com; Path=/"}),
                  request_cookie="SID=older-browser-session")
    assert json.loads(path.read_text())["cookies"][0]["value"] == "synthetic-old"
