# Docker and automatic GitHub builds

The app runs as two non-root containers: the FastAPI backend and the frontend's same-origin Node gateway. Only the frontend is exposed, on localhost port 8080 by default. Service tokens remain server-side. Both runtime filesystems are read-only; temporary caches use `/tmp`.

## Run locally

```sh
cp docker.env.example .env
# Replace GASWISE_API_TOKEN with a private random token.
docker compose up -d --build --wait
```

Open http://localhost:8080. Without provider credentials this starts the synthetic demo. Your existing host app on ports 5173/8000 is separate.

## Pull published images

```sh
docker compose pull
docker compose up -d --no-build --wait
```

Images are `ghcr.io/wayneclub/gaswise-backend:latest` and `ghcr.io/wayneclub/gaswise-frontend:latest`. If the packages are private, sign in with `docker login ghcr.io` using a token with `read:packages`. GitHub package visibility is managed separately from repository visibility.

Every push to `main` runs backend/frontend/gateway regression tests, builds both containers, and smoke-tests the frontend → authenticated gateway → backend demo flow. Only after these pass does it publish Linux AMD64 and ARM64 images to GHCR. Images receive `latest` and `sha-<commit>` tags; `v*` Git tags also produce a version tag. Pull requests validate but do not publish. Manual runs are available under GitHub Actions. Actions use immutable commit references. Publishing uses the workflow's short-lived GitHub token, not a saved registry password.

## Live providers

Images include the live adapters but never include `.env`, user sessions, cookies, keys, or local research output. Configure live providers at runtime using the backend settings in `backend/.env.example` and the provider setup documents. For an existing local setup, add a private Compose override (ignored by Git), for example:

```yaml
services:
  backend:
    env_file:
      - ./backend/.env
    environment:
      GASWISE_MODE: google
      GASWISE_MAPS_WEB_SESSION_FILE: /run/gaswise/google-maps-http-session.json
      GASWISE_WAZE_SESSION_FILE: /run/gaswise/waze-http-session.json
      GASWISE_WAZE_LOGIN_FILE: /run/gaswise/waze-http-login.bin
    volumes:
      - /absolute/path/to/private/gaswise-credentials:/run/gaswise:ro
```

Set the same `GASWISE_API_TOKEN` in the root `.env` and the backend configuration so the frontend gateway can authenticate. Enable the providers you use (`GASWISE_MAPS_WEB_ROUTES_ENABLED`, `GASWISE_WAZE_ENABLED`, etc.) in the runtime settings. Paths inside the backend `.env` must refer to container paths. The backend runs as UID 1000; mounted credential files must be readable by that UID while retaining the strict permissions required by the provider (such as 0600). Provision a private container-specific copy; never make credentials world-readable or commit them. Session expiry and provider restrictions still apply.

Private override files can be named `compose.private.yaml` and passed explicitly:

```sh
docker compose -f compose.yaml -f compose.private.yaml up -d --wait
```

Stop with `docker compose down`. Docker starts no live upstream searches during the included demo smoke test.

Implementation references: [Docker's GHCR workflow](https://docs.docker.com/build/ci/github-actions/push-multi-registries/) and [uv's Docker integration](https://docs.astral.sh/uv/guides/integration/docker/).
