# AWS / Lightsail

GasWise uses the existing PassBar deployment infrastructure on the Lightsail
host: Docker images from GHCR, the external `npm_network`, Nginx Proxy Manager,
Cloudflare DNS, and a renewable Let's Encrypt DNS certificate.

Production URL: https://gaswise.wayneclub.com

## Server files

The deployment directory is `/home/ubuntu/apps/gaswise`:

- `docker-compose.yml` and `deploy.sh` are copied from this directory.
- `.env` contains the private service token and provider configuration (mode
  `prices_only`; paid Google Places and Routes APIs are disabled).
- `credentials/` contains runtime Maps/Waze sessions, outside Git and images.
  Keep the directory mode `0700` and files `0600`, owned by container UID 1000.
  Waze may update its session after login, so this directory is writable.
- `.deployed-image-tag` records the last healthy immutable release.

Only the frontend joins the existing proxy network. Neither container publishes
a public port, and the backend belongs only to the app network. Container health
checks, automatic restart, memory limits, and bounded log rotation are enabled.

The shared public pricing cache uses the existing `postgres` container through
`postgres:5432` on `docker_default`. Set the dedicated `GASWISE_DATABASE_URL` in
private `.env`; no new database container or public port is created. The backend's
existing `vpn_egress` network also reaches this DB endpoint, but only the GasBuddy
HTTP client uses the US proxy. See [shared pricing cache](../docs/shared-pricing-cache.md).

## Deploy an image already published by GitHub Actions

```sh
ssh -i ~/.ssh/LightsailDefaultKey-ap-northeast-1.pem ubuntu@13.159.93.30 \
  'cd ~/apps/gaswise && ./deploy.sh sha-<full-commit-hash>'
```

Copy the current `docker-compose.yml` before deployment and run `deploy.sh` as
`ubuntu`, without `sudo`, so `.env` retains its service-user ownership.

The script pulls both images, waits for health, checks and reloads NPM, and records
the release. A failed upgrade rolls back to the previous healthy image tag.
GitHub Actions automatically builds and publishes images; this server script
performs deployment explicitly.

## Proxy and DNS

Cloudflare's proxied A record points `gaswise.wayneclub.com` at `13.159.93.30`.
NPM forwards the hostname to `gaswise-frontend:8080` using the shared network,
forces HTTPS, enables HSTS/HTTP2, and allows 130 seconds for upstream responses.
The certificate uses NPM's Cloudflare DNS challenge and renewal management.
Keep DNS credentials and NPM signing keys on the server, outside this repository.

Verify the public HTTPS page, ZIP/address resolution, a bounded live smart search,
and zero-call reranking after deployment. Native GPS still requires a real browser
and device verification; a valid HTTPS certificate alone does not prove GPS works.
