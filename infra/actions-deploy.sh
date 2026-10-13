#!/usr/bin/env bash
# Forced command for the dedicated Actions SSH key; no interactive shell access.
set -euo pipefail
tag="${SSH_ORIGINAL_COMMAND:-}"
[[ "$tag" =~ ^sha-[a-f0-9]{40}$ ]] || { echo 'Expected immutable release tag.' >&2; exit 1; }
cd /home/ubuntu/apps/gaswise
exec 9>.deploy.lock
flock -w 600 9
exec ./deploy.sh "$tag"
