"""Validate a private staged Google session before replacing production credentials."""
import fcntl
import json
import os
import subprocess
from pathlib import Path

ROOT = Path("/home/ubuntu/apps/gaswise")
CREDENTIALS = ROOT / "credentials"
CANDIDATE = CREDENTIALS / "google-maps-http-session.candidate.json"
ACTIVE = CREDENTIALS / "google-maps-http-session.json"


def main():
    if CANDIDATE.is_symlink() or not CANDIDATE.is_file() or CANDIDATE.stat().st_mode & 0o077 or CANDIDATE.stat().st_size > 100000:
        raise ValueError("invalid_candidate")
    check = (ROOT / "check_google_session.py").read_text()
    result = subprocess.run([
        "docker", "exec", "-i", "-e", "GASWISE_MAPS_WEB_SESSION_FILE=/run/gaswise/google-maps-http-session.candidate.json",
        "gaswise-backend", "python", "-",
    ], input=check, text=True, capture_output=True, timeout=45)
    if result.returncode:
        print('{"status":"candidate_not_installed"}')
        return 2
    fd = os.open(ACTIVE.with_name(ACTIVE.name + ".lock"), os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        os.replace(CANDIDATE, ACTIVE)
    # Invalidate only Maps query responses. Station identities and quote report times
    # remain intact; next acquisition still obeys the shared request budget/leases.
    invalidation = '''
import asyncio
from gaswise.app.settings import Settings
from gaswise.providers.storage.postgres import PostgresPricingCache
async def run():
    store=await PostgresPricingCache.connect(Settings().database_url.get_secret_value())
    try:
        await store.pool.execute("UPDATE gaswise.query_cache SET fresh_until=now(),stale_until=now() WHERE source='maps' AND payload IS NOT NULL")
    finally: await store.close()
try: asyncio.run(run())
except Exception: raise SystemExit(1) from None
'''
    result = subprocess.run(["docker", "exec", "-i", "gaswise-backend", "python", "-"],
                            input=invalidation, text=True, capture_output=True, timeout=30)
    print(json.dumps({"status": "installed" if result.returncode == 0 else "installed_cache_invalidation_deferred"}))
    return result.returncode


if __name__ == "__main__":
    try:
        code = main()
    except Exception:
        print('{"status":"session_install_failed"}')
        code = 1
    raise SystemExit(code)
