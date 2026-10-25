"""Bounded NordVPN US exit supervision on the Docker host; never rotates the live source.

Uses existing private service credentials without printing them. A failed VPN
login advances to a distinct city, up to three attempts persisted across restarts.
This handles VPN connection failures, never HTTP/provider rate-limit responses.
"""
import argparse
import json
import os
import subprocess
import tempfile
import time
from pathlib import Path

LABEL = 'gaswise.purpose=managed-pricing-egress'
LOCATION_ENDPOINTS = ('https://ipinfo.io/json', 'https://ipapi.co/json/')


def docker(*args):
    return subprocess.check_output(['docker', *args], stderr=subprocess.STDOUT if args and args[0] == 'logs' else subprocess.DEVNULL).decode()


def failure_reason(logs, status):
    if 'AUTH_FAILED' in logs:
        return 'vpn_auth_failed'
    if status in ('exited', 'dead'):
        return 'vpn_startup_failed'
    return None


def next_candidate(state, cities, maximum=3):
    if len(state.get('attempts', [])) >= maximum:
        return None
    used = {attempt['city'] for attempt in state.get('attempts', [])}
    return next((city for city in cities if city not in used), None)


def prepare_generation(state, now, maximum=3, cooldown=7200):
    """Bound replacement attempts, then reopen a fresh generation after cooldown."""
    state.setdefault('generation', 1)
    if len(state.get('attempts', [])) < maximum:
        return True
    if 'cooldown_until' not in state:
        state['cooldown_until'] = now + cooldown
        return False
    if now < state['cooldown_until']:
        return False
    state['generation'] += 1
    state['attempts'] = []
    state.pop('cooldown_until', None)
    return True


def save_state(path, state):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(state, indent=2) + '\n')
    temporary.chmod(0o600)
    temporary.replace(path)


def load_state(path, now, maximum=3, cooldown=7200):
    """Migrate exhausted legacy state without restarting its elapsed cooldown."""
    if not path.exists():
        return {'attempts': []}
    state = json.loads(path.read_text())
    if ('generation' not in state and 'cooldown_until' not in state
            and len(state.get('attempts', [])) >= maximum):
        state['cooldown_until'] = min(now, path.stat().st_mtime) + cooldown
    return state


def remove_owned(name):
    try:
        row = json.loads(docker('inspect', name))[0]
    except subprocess.CalledProcessError:
        return
    if row['Config'].get('Labels', {}).get('gaswise.purpose') != 'managed-pricing-egress':
        raise RuntimeError('Target is not owned by this supervisor')
    docker('rm', '-f', name)


def create_exit(source, target, city, network):
    original = json.loads(docker('inspect', source))[0]
    values = dict(item.split('=', 1) for item in original['Config']['Env'] if '=' in item)
    keys = ('VPN_SERVICE_PROVIDER', 'VPN_TYPE', 'OPENVPN_USER', 'OPENVPN_PASSWORD')
    env = {key: values[key] for key in keys}
    if env['VPN_SERVICE_PROVIDER'] != 'nordvpn' or env['VPN_TYPE'] != 'openvpn':
        raise RuntimeError('This supervisor requires an existing NordVPN OpenVPN source')
    env.update(SERVER_COUNTRIES='United States', SERVER_CITIES=city, OPENVPN_PROTOCOL='udp',
               HTTPPROXY='on', HTTPPROXY_LISTENING_ADDRESS=':8888')
    if any('\n' in value or '\r' in value for value in env.values()):
        raise RuntimeError('Multiline environment inputs are not supported')
    descriptor, filename = tempfile.mkstemp(prefix='gaswise-egress-', dir='/tmp')
    try:
        with os.fdopen(descriptor, 'w') as stream:
            stream.write(''.join(key + '=' + value + '\n' for key, value in env.items()))
        os.chmod(filename, 0o600)
        docker('create', '--name', target, '--label', LABEL, '--cap-add=NET_ADMIN',
               '--device', '/dev/net/tun:/dev/net/tun', '--network', network, '--memory', '192m',
               '--env-file', filename, original['Image'])
        docker('start', target)
    finally:
        os.unlink(filename)


def verify_us_https(target):
    """Require the lane's local HTTP proxy to complete HTTPS with a US location."""
    for endpoint in LOCATION_ENDPOINTS:
        try:
            payload = docker(
                'exec', '-e', 'HTTPS_PROXY=http://127.0.0.1:8888',
                '-e', 'https_proxy=http://127.0.0.1:8888', target,
                'wget', '-qO-', '-T', '15', '--tries=1', endpoint,
            )
            if len(payload) > 16_384:
                continue
            data = json.loads(payload)
            country = data.get('country') or data.get('country_code')
            if isinstance(country, str):
                return {'https_status': 200, 'country': country.upper()}
        except (subprocess.CalledProcessError, ValueError, TypeError, AttributeError):
            continue
    return None


def write_health(path, available, verification=None, primary_available=True, primary_verification=None):
    if path is not None:
        unavailable = ([] if primary_available else [0]) + ([] if available else [1])
        state = {'unavailable_lanes': unavailable}
        evidence = {}
        if primary_available and primary_verification is not None:
            evidence['0'] = primary_verification
        if available and verification is not None:
            evidence['1'] = verification
        if evidence:
            state['verification'] = evidence
        save_state(path, state)


def publish_primary_health(path, source):
    verification = verify_us_https(source)
    available = bool(
        verification and verification.get('https_status') == 200 and verification.get('country') == 'US'
    )
    write_health(path, False, primary_available=available, primary_verification=verification)
    return available


def monitor(target, watch, health_path=None, verify_interval=300, source=None):
    deadline = time.monotonic() + 60
    published = 0
    reported = False
    verification = None
    primary_verification = None
    next_verification = 0
    write_health(health_path, False, primary_available=False)

    def publish_failure():
        nonlocal primary_verification
        if primary_verification is None:
            primary_verification = verify_us_https(source) if source else {
                'https_status': 200, 'country': 'US'
            }
        primary_available = bool(
            primary_verification and primary_verification.get('https_status') == 200
            and primary_verification.get('country') == 'US'
        )
        write_health(health_path, False, primary_available=primary_available,
                     primary_verification=primary_verification)

    while True:
        row = json.loads(docker('inspect', target))[0]
        reason = failure_reason(docker('logs', '--tail', '80', target), row['State']['Status'])
        if reason:
            publish_failure()
            return reason
        healthy = row['State'].get('Health', {}).get('Status') == 'healthy'
        if healthy:
            if time.monotonic() >= next_verification:
                verification = verify_us_https(target)
                primary_verification = verify_us_https(source) if source else {
                    'https_status': 200, 'country': 'US'
                }
                if not verification or verification.get('https_status') != 200 or verification.get('country') != 'US':
                    write_health(
                        health_path, False,
                        primary_available=bool(primary_verification and primary_verification.get('https_status') == 200
                                               and primary_verification.get('country') == 'US'),
                        primary_verification=primary_verification,
                    )
                    return 'egress_verification_failed'
                next_verification = time.monotonic() + verify_interval
            primary_available = bool(
                primary_verification and primary_verification.get('https_status') == 200
                and primary_verification.get('country') == 'US'
            )
            if not reported or time.monotonic() - published >= 10:
                write_health(health_path, True, verification, primary_available, primary_verification)
                published = time.monotonic()
            if not reported:
                print(json.dumps({'event': 'egress_verified', 'target': target,
                                  'https_status': 200, 'country': 'US'}), flush=True)
                reported = True
            if not watch:
                return 'healthy'
            deadline = time.monotonic() + 60
        elif reported:
            publish_failure()
            reported = False
        if time.monotonic() >= deadline:
            publish_failure()
            return 'vpn_health_timeout'
        time.sleep(2)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', default='gluetun')
    parser.add_argument('--target', default='gaswise-egress-2')
    parser.add_argument('--network', default='docker_default')
    parser.add_argument('--cities', default='Dallas,Miami,Seattle')
    parser.add_argument('--max-attempts', type=int, choices=(1, 2, 3), default=3)
    parser.add_argument('--state', type=Path, required=True)
    parser.add_argument('--watch', action='store_true')
    parser.add_argument('--health-state', type=Path)
    parser.add_argument('--retry-cooldown-seconds', type=int, default=7200)
    args = parser.parse_args()
    if args.source == args.target:
        raise SystemExit('Source and target must be different')
    cities = list(dict.fromkeys(city.strip() for city in args.cities.split(',') if city.strip()))
    state = load_state(args.state, time.time(), args.max_attempts, args.retry_cooldown_seconds)
    if state['attempts'] and state['attempts'][-1]['result'] in ('starting', 'healthy'):
        try:
            row = json.loads(docker('inspect', args.target))[0]
            if row['Config'].get('Labels', {}).get('gaswise.purpose') != 'managed-pricing-egress':
                raise RuntimeError('Existing target is not owned by this supervisor')
        except subprocess.CalledProcessError:
            row = None
        if row is not None:
            if row['State']['Status'] in ('created', 'exited'):
                docker('start', args.target)
            outcome = monitor(args.target, args.watch, args.health_state, 300, args.source)
            state['attempts'][-1]['result'] = outcome
            save_state(args.state, state)
            if outcome == 'healthy':
                return
            remove_owned(args.target)
    if not prepare_generation(state, time.time(), args.max_attempts, args.retry_cooldown_seconds):
        save_state(args.state, state)
        publish_primary_health(args.health_state, args.source)
        print(json.dumps({'event': 'replacement_cooldown',
                          'retry_after_seconds': max(0, round(state['cooldown_until'] - time.time()))}), flush=True)
        raise SystemExit(2)
    save_state(args.state, state)
    while (city := next_candidate(state, cities, args.max_attempts)) is not None:
        publish_primary_health(args.health_state, args.source)
        remove_owned(args.target)
        state['attempts'].append({'city': city, 'result': 'starting'})
        save_state(args.state, state)
        print(json.dumps({'event': 'vpn_attempt', 'city': city, 'attempt': len(state['attempts'])}), flush=True)
        try:
            create_exit(args.source, args.target, city, args.network)
            outcome = monitor(args.target, args.watch, args.health_state, 300, args.source)
        except (subprocess.CalledProcessError, OSError, ValueError, KeyError, RuntimeError) as error:
            outcome = 'supervisor_' + type(error).__name__
        state['attempts'][-1]['result'] = outcome
        save_state(args.state, state)
        print(json.dumps({'event': outcome, 'city': city}), flush=True)
        if outcome == 'healthy':
            return
        remove_owned(args.target)
    publish_primary_health(args.health_state, args.source)
    prepare_generation(state, time.time(), args.max_attempts, args.retry_cooldown_seconds)
    save_state(args.state, state)
    print(json.dumps({'event': 'vpn_attempts_exhausted', 'production_source_unchanged': True,
                      'replacement_generation': state['generation']}), flush=True)
    raise SystemExit(2)


if __name__ == '__main__':
    main()
