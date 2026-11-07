#!/usr/bin/env bash
# Deploy GasWise to remote production server directly, bypassing GitHub Actions completely.
# 100% free, zero CI minutes or package storage used.
set -euo pipefail

SSH_KEY="${GASWISE_DEPLOY_KEY:-$HOME/.ssh/LightsailDefaultKey-ap-northeast-1.pem}"
SERVER_HOST="${GASWISE_HOST:-100.108.62.74}"

echo "================================================="
echo "   GasWise Host Deployment (Bypassing GH Actions)"
echo "================================================="
echo "Host:    $SERVER_HOST"
echo "Key:     $SSH_KEY"
echo "Target:  https://gaswise.wayneclub.com/"
echo "-------------------------------------------------"

ssh -i "$SSH_KEY" "ubuntu@$SERVER_HOST" "/home/ubuntu/apps/gaswise/deploy-local.sh"

echo "-------------------------------------------------"
echo "Verifying public HTTPS endpoint..."
curl --fail --silent --show-error --retry 3 --retry-delay 2 https://gaswise.wayneclub.com/ -o /dev/null
echo "GasWise is live and healthy at https://gaswise.wayneclub.com/"
