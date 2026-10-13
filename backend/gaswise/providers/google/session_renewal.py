"""Persist Google response cookie rotations to the existing private session file."""
import fcntl
import json
import os
import re
import tempfile
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from http.cookies import SimpleCookie
from pathlib import Path

DOMAINS = {".google.com", "www.google.com", "google.com"}


def renew_session(path: Path | None, headers, now=None, request_cookie=None):
    if path is None or not headers.get_list("set-cookie"):
        return
    now = now or datetime.now(UTC).timestamp()
    updates = {}
    for raw in headers.get_list("set-cookie"):
        cookie = SimpleCookie()
        cookie.load(raw)
        for name, item in cookie.items():
            domain = item["domain"] or "www.google.com"
            cookie_path = item["path"] or "/"
            if domain not in DOMAINS or cookie_path != "/" or not re.fullmatch(r"[A-Za-z0-9_-]+", name):
                continue
            value = item.value
            if not value.isascii() or any(c in value for c in "\r\n;"):
                continue
            expires = -1
            if item["max-age"]:
                try:
                    expires = now + int(item["max-age"])
                except ValueError:
                    continue
            elif item["expires"]:
                try:
                    expires = parsedate_to_datetime(item["expires"]).timestamp()
                except (ValueError, TypeError, OverflowError):
                    continue
            updates[name] = {"name": name, "value": value, "domain": ".google.com" if domain == "google.com" else domain,
                             "path": "/", "expires": expires, "secure": bool(item["secure"]),
                             "httpOnly": bool(item["httponly"])}
    if not updates:
        return
    path = Path(path)
    # Cooperating workers reread inside a lock; replacing the cookie file itself is atomic.
    lock_path = path.with_name(path.name + ".lock")
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if path.is_symlink() or not path.is_file() or path.stat().st_mode & 0o077:
            raise ValueError("unsafe_private_session")
        payload = json.loads(path.read_text())
        if request_cookie is not None:
            requested = SimpleCookie()
            requested.load(request_cookie)
            stored = {c["name"]: c["value"] for c in payload["cookies"]}
            # A browser sync may have replaced authentication while this HTTP request ran.
            # Never overwrite its new session with rotations from an older account session.
            for name in ("SID", "__Secure-1PSID", "__Secure-3PSID"):
                old = requested.get(name)
                if old is not None and stored.get(name) != old.value:
                    return
        cookies = [c for c in payload["cookies"] if c["name"] not in updates]
        cookies.extend(c for c in updates.values() if c["expires"] < 0 or c["expires"] > now)
        payload.update(cookies=cookies, renewed_at=datetime.fromtimestamp(now, UTC).isoformat())
        fd, temporary = tempfile.mkstemp(prefix=".google-session-", dir=path.parent)
        try:
            with os.fdopen(fd, "w") as stream:
                json.dump(payload, stream)
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
