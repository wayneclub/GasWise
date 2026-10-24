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
GitHub Actions now deploys automatically after tests and both image publications
succeed on `main` (push or manual workflow dispatch). PRs and tags do not deploy.
The production environment records each deployment. Main runs and production
deployments are serialized without cancelling an in-progress deployment.

Repository secrets: `GASWISE_DEPLOY_HOST`, `GASWISE_DEPLOY_KNOWN_HOSTS` (pinned
server host key), and `GASWISE_DEPLOY_SSH_KEY` (dedicated private key). The server's
authorized key uses `restrict,command="/home/ubuntu/apps/gaswise/actions-deploy.sh"`.
This wrapper accepts only immutable image tags and holds a server deployment lock.
It cannot run arbitrary SSH commands or open a shell. Private provider credentials
stay on the server. Copy wrapper/script updates separately using the admin identity.

## Proxy and DNS

Cloudflare's proxied A record points `gaswise.wayneclub.com` at `13.159.93.30`.
NPM forwards the hostname to `gaswise-frontend:8080` using the shared network,
forces HTTPS, enables HSTS/HTTP2, and allows 130 seconds for upstream responses.
The certificate uses NPM's Cloudflare DNS challenge and renewal management.
Keep DNS credentials and NPM signing keys on the server, outside this repository.

Verify the public HTTPS page, ZIP/address resolution, a bounded live smart search,
and zero-call reranking after deployment. Native GPS still requires a real browser
and device verification; a valid HTTPS certificate alone does not prove GPS works.

## Bounded secondary NordVPN exit supervision

`scripts/infra/manage_pricing_egress.py` runs on the Docker host. It copies existing
private NordVPN service credentials into a mode-0600 temporary env file, creates
an isolated managed exit on `docker_default`, and deletes that file immediately.
The original `gluetun` container is never stopped or reconfigured. AUTH_FAILED,
startup failure or a sustained unhealthy tunnel selects the next distinct US city
(Dallas, Miami, Seattle). At most three attempts are persisted in a private state
file, so process restarts cannot create an infinite authentication loop. This
supervisor does not observe provider HTTP responses and does not rotate on 403/429.

Install the script in `/home/ubuntu/apps/gaswise/recovery/` and the supplied
`gaswise-egress-supervisor.service` in systemd. `--watch` supervises a successful
secondary exit and resumes the same owned container after a process restart.
The lane is published only after its own HTTP proxy completes an HTTPS location
request with status 200 and country US. A failed verification removes that owned
secondary and advances to the next city. If all three attempts fail, the service
leaves the production exit alone and waits two hours before opening a new
replacement generation; systemd checks the persisted cooldown every five minutes.
This bounds authentication/rebuild attempts without requiring an operator to
delete `egress-2-state.json`.
Do not enable an unhealthy exit in `GASWISE_PRICING_EGRESS_PROXIES`.
