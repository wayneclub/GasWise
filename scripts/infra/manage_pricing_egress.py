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


def save_state(path, state):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(state, indent=2) + '\n')
    temporary.chmod(0o600)
    temporary.replace(path)


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


def write_health(path, available):
    if path is not None:
        save_state(path, {'unavailable_lanes': [] if available else [1]})


def monitor(target, watch, health_path=None):
    deadline = time.monotonic() + 60
    published = 0
    reported = False
    write_health(health_path, False)
    while True:
        row = json.loads(docker('inspect', target))[0]
        reason = failure_reason(docker('logs', '--tail', '80', target), row['State']['Status'])
        if reason:
            write_health(health_path, False)
            return reason
        healthy = row['State'].get('Health', {}).get('Status') == 'healthy'
        if healthy:
            if not reported or time.monotonic() - published >= 10:
                write_health(health_path, True)
                published = time.monotonic()
            if not reported:
                print(json.dumps({'event': 'vpn_healthy', 'target': target}), flush=True)
                reported = True
            if not watch:
                return 'healthy'
            deadline = time.monotonic() + 60
        elif reported:
            write_health(health_path, False)
            reported = False
        if time.monotonic() >= deadline:
            write_health(health_path, False)
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
    args = parser.parse_args()
    if args.source == args.target:
        raise SystemExit('Source and target must be different')
    cities = list(dict.fromkeys(city.strip() for city in args.cities.split(',') if city.strip()))
    state = json.loads(args.state.read_text()) if args.state.exists() else {'attempts': []}
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
            outcome = monitor(args.target, args.watch, args.health_state)
            state['attempts'][-1]['result'] = outcome
            save_state(args.state, state)
            if outcome == 'healthy':
                return
            remove_owned(args.target)
    while (city := next_candidate(state, cities, args.max_attempts)) is not None:
        write_health(args.health_state, False)
        remove_owned(args.target)
        state['attempts'].append({'city': city, 'result': 'starting'})
        save_state(args.state, state)
        print(json.dumps({'event': 'vpn_attempt', 'city': city, 'attempt': len(state['attempts'])}), flush=True)
        try:
            create_exit(args.source, args.target, city, args.network)
            outcome = monitor(args.target, args.watch, args.health_state)
        except (subprocess.CalledProcessError, OSError, ValueError, KeyError, RuntimeError) as error:
            outcome = 'supervisor_' + type(error).__name__
        state['attempts'][-1]['result'] = outcome
        save_state(args.state, state)
        print(json.dumps({'event': outcome, 'city': city}), flush=True)
        if outcome == 'healthy':
            return
        remove_owned(args.target)
    write_health(args.health_state, False)
    print(json.dumps({'event': 'vpn_attempts_exhausted', 'production_source_unchanged': True}), flush=True)
    raise SystemExit(2)


if __name__ == '__main__':
    main()
