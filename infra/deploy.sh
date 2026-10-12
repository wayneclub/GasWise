#!/usr/bin/env bash
# Run from /home/ubuntu/apps/gaswise after GHCR publication.
set -euo pipefail
cd "$(dirname "$0")"
tag="${1:?Usage: deploy.sh sha-<full commit hash>}"
[[ "$tag" =~ ^sha-[a-f0-9]{40}$ ]] || { echo 'An immutable SHA image tag is required.' >&2; exit 1; }
[[ -f .env ]] || { echo 'Missing private .env' >&2; exit 1; }
previous="$(cat .deployed-image-tag 2>/dev/null || true)"
export GASWISE_IMAGE_TAG="$tag"
rollback() {
  if [[ -n "$previous" && "$previous" != "$tag" ]]; then
    echo "Rolling back to $previous" >&2
    GASWISE_IMAGE_TAG="$previous" docker compose up -d --no-build --wait --wait-timeout 180
    docker exec nginx-proxy-manager nginx -t && docker exec nginx-proxy-manager nginx -s reload
  fi
}
trap rollback ERR
docker compose pull
docker compose up -d --no-build --wait --wait-timeout 180
docker exec nginx-proxy-manager nginx -t
docker exec nginx-proxy-manager nginx -s reload
python3 - <<'PY'
import os
from pathlib import Path
path = Path('.env')
rows = [r for r in path.read_text().splitlines() if not r.startswith('GASWISE_IMAGE_TAG=')]
rows.append('GASWISE_IMAGE_TAG=' + os.environ['GASWISE_IMAGE_TAG'])
temporary = Path('.env.deploy')
temporary.touch(mode=0o600)
temporary.chmod(0o600)
temporary.write_text('\n'.join(rows) + '\n')
temporary.replace(path)
PY
printf '%s\n' "$tag" > .deployed-image-tag
trap - ERR
docker compose ps
