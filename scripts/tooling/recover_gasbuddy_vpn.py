"""Host-side recovery of the existing US gluetun; no credentials in state/logs."""
import argparse
import fcntl
import json
import os
import re
import subprocess
import tempfile
import time
import urllib.request
from datetime import datetime
from pathlib import Path


def get_boot_time():
    try:
        with open("/proc/stat", "r") as stream:
            for line in stream:
                if line.startswith("btime "):
                    return int(line.split()[1])
    except (OSError, ValueError, IndexError):
        pass
    return None


def probe_proxy(proxy="http://127.0.0.1:8888", timeout=5):
    for endpoint in ("https://ipinfo.io/country", "https://ipapi.co/country/"):
        try:
            handler = urllib.request.ProxyHandler({"http": proxy, "https": proxy})
            opener = urllib.request.build_opener(handler)
            req = urllib.request.Request(endpoint, headers={"User-Agent": "GasWise-VPN-Probe/1"})
            with opener.open(req, timeout=timeout) as resp:
                if resp.status == 200:
                    country = resp.read().decode().strip().upper()
                    if country == "US":
                        return "healthy"
        except Exception:
            continue
    return "unhealthy"


def decide(state, health, started, now, boot_time=None):
    state = dict(state)
    if boot_time is not None:
        last_boot = state.get("boot_time")
        if last_boot is not None and last_boot != boot_time:
            state.update(failures=0, attempts=0, status="reboot_cleared")
        state["boot_time"] = boot_time
    if health == "healthy":
        state.update(failures=0, attempts=0, status="healthy")
        return state, False
    if now - started < 120:
        state.update(failures=0, status="starting")
        return state, False
    state["failures"] = state.get("failures", 0) + 1
    cooldown = 600 if state.get("attempts", 0) >= 3 else 180
    recover = state["failures"] >= 3 and now - state.get("last_attempt", 0) >= cooldown
    state["status"] = "recovery_due" if recover else "waiting"
    return state, recover


def update_env_hostname(env_path, hostname):
    try:
        if not env_path.exists():
            return
        text = env_path.read_text()
        lines = [line for line in text.splitlines() if not line.startswith("NORDVPN_SERVER_HOSTNAME=")]
        lines.append(f"NORDVPN_SERVER_HOSTNAME={hostname}")
        temporary = env_path.with_suffix(".tmp")
        temporary.write_text("\n".join(lines) + "\n")
        temporary.chmod(0o600)
        temporary.replace(env_path)
    except OSError:
        pass


def save(path, value):
    fd, temporary = tempfile.mkstemp(prefix=".vpn-recovery-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def command(args, timeout=15):
    return subprocess.check_output(args, timeout=timeout, stderr=subprocess.DEVNULL, text=True)


def known_gluetun_nodes(source="gluetun"):
    try:
        raw = command(["docker", "exec", source, "grep", "-o", '"us[0-9]*\\.nordvpn\\.com"', "/gluetun/servers/nordvpn.json"])
        return set(h.strip('"') for h in raw.splitlines())
    except Exception:
        return set()


def recommended(excluded, known=None):
    url = "https://api.nordvpn.com/v1/servers/recommendations?filters[country_id]=228&limit=50"
    request = urllib.request.Request(url, headers={"User-Agent": "GasWise-VPN-Recovery/1"})
    with urllib.request.urlopen(request, timeout=10) as response:
        rows = json.load(response)
    for row in sorted(rows, key=lambda r: r.get("load", 100)):
        hostname = row.get("hostname", "")
        if re.fullmatch(r"us\d+\.nordvpn\.com", hostname) and hostname not in excluded:
            if known and hostname not in known:
                continue
            return hostname
    raise RuntimeError("no_eligible_us_node")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--compose-dir", type=Path, default=Path("/home/ubuntu/docker"))
    parser.add_argument("--state-dir", type=Path, default=Path("/home/ubuntu/apps/gaswise/recovery"))
    args = parser.parse_args()
    args.state_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    with (args.state_dir / "lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        path = args.state_dir / "state.json"
        state = json.loads(path.read_text()) if path.exists() else {}
        container = json.loads(command(["docker", "inspect", "gluetun"]))[0]
        env = dict(item.split("=", 1) for item in container["Config"]["Env"] if "=" in item)
        # Refuse to recreate a different egress/service or use a non-US selection.
        if env.get("VPN_SERVICE_PROVIDER", "").lower() != "nordvpn" or env.get("SERVER_COUNTRIES", "").lower() != "united states":
            raise RuntimeError("unexpected_vpn_configuration")
        if Path(container["Config"]["Labels"]["com.docker.compose.project.working_dir"]) != args.compose_dir:
            raise RuntimeError("unexpected_compose_directory")
        started = datetime.fromisoformat(container["State"]["StartedAt"].replace("Z", "+00:00")).timestamp()
        running = container["State"].get("Running", False)
        active_health = probe_proxy("http://127.0.0.1:8888", timeout=5) if running else "stopped"
        docker_health = (container["State"].get("Health", {}).get("Status", "unknown")
                         if running else "stopped")
        health = "healthy" if active_health == "healthy" else docker_health
        now = time.time()
        boot_time = get_boot_time()
        state, recover = decide(state, health, started, now, boot_time=boot_time)
        if recover:
            logs = command(["docker", "logs", "--tail", "100", "gluetun"])
            nodes = re.findall(r"\[(us\d+\.nordvpn\.com)\] Peer Connection Initiated", logs)
            excluded = state.get("failed_nodes", [])
            if nodes:
                excluded = list(dict.fromkeys([*excluded, nodes[-1]]))[-5:]
            # Persist the cooldown BEFORE any network request/recreation, including errors.
            state.update(last_attempt=now, attempts=state.get("attempts", 0)+1,
                         failed_nodes=excluded, status="recovering")
            save(path, state)
            known = known_gluetun_nodes()
            hostname = recommended(excluded, known=known)
            override = args.state_dir / "compose.override.json"
            save(override, {"services": {"gluetun": {"environment": {"SERVER_HOSTNAMES": hostname}}}})
            update_env_hostname(args.compose_dir / ".env", hostname)
            command(["docker", "compose", "--project-directory", str(args.compose_dir),
                     "-f", str(args.compose_dir / "docker-compose.yml"), "-f", str(override),
                     "up", "-d", "--no-deps", "--force-recreate", "gluetun"], timeout=90)
            state.update(status="switched_waiting_for_health", selected_node=hostname, failures=0)
        save(path, state)
        print(json.dumps({"status": state["status"], "failures": state.get("failures", 0),
                          "attempts": state.get("attempts", 0)}))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print('{"status":"recovery_check_failed"}')
        raise SystemExit(1) from None
