# Provider recovery

GasWise uses the existing PostgreSQL and US `gluetun` containers. Credentials
remain in private files. No credential values belong in Git, logs, task output,
health state or PostgreSQL public pricing tables.

## US VPN recovery on the production host

`scripts/tooling/recover_gasbuddy_vpn.py` runs from a systemd timer every minute,
independently of the local Codex app. It checks Docker health without a GasBuddy
request. A healthy VPN is never replaced for speed or a price-source 429/403.

Allow two minutes after container startup and require three failed checks.
Recovery excludes the recently failed US nodes, obtains a US recommendation and
recreates only `gluetun`, using the existing compose configuration plus a small
override. Record the attempt before doing network I/O. Wait at least 30 minutes
between attempts; after three unsuccessful attempts wait two hours. Keep the
independent `nord-optimizer` in monitor-only mode to avoid competing switches.

State and lock files live in `/home/ubuntu/apps/gaswise/recovery`. The timer uses
the `ubuntu` account. Install the script under `/home/ubuntu/apps/gaswise` and the
two `infra/gaswise-vpn-recovery.*` units under `/etc/systemd/system`, then enable
the timer. The host requires Python 3, Docker Compose and network access to the
NordVPN recommendation endpoint. A real account/credential failure cannot be
fixed by changing nodes; cooldown prevents an uncontrolled authentication loop.

## Google session renewal

`MapsWebProvider` now persists accepted Google response `Set-Cookie` rotations
to its existing private session file. It only accepts Google domains at `/`,
preserves other cookies, respects deletion/expiry, writes mode 0600 atomically,
and uses a separate file lock for cooperating workers. It rechecks the session
identity so an in-flight old request cannot overwrite a new browser login.
Subsequent source requests read the renewed file. Source budgets and cooldowns
apply to these requests as usual; this does not trigger polling of idle areas.

The thread automation checks the production session hourly with
`check_google_session.py`, one budgeted Google search request in a known public
canary region, with zero detail requests. HTTP 200 or a Regular summary alone does not prove session
health. A missing table could also reflect a changed canary; treat it as a
signal to investigate, not proof of account logout.

When the canary fails or the browser snapshot is over one day old, use the
user-authorized, already signed-in Google Maps browser session to refresh the
local private file. Use the computer-use API; never read/decrypt browser profile
databases or print cookies. If Google asks for sign-in, CAPTCHA or 2FA, stop the
dependent action and ask the user to handle it. Do not create an account or alter
security settings.

Copy the new snapshot using SSH to the existing credentials directory as
`google-maps-http-session.candidate.json` (0600), then run
`install_google_session.py` on the host. It validates the candidate against the
budgeted canary before atomically replacing the active file under its lock. A
failed candidate never replaces the previous working session. Installation
invalidates Maps query responses, preserving station identities and quote
report timestamps, and does not restart the app or touch other providers.

Production SSH uses `ubuntu@13.159.93.30` and the existing local key
`/Users/wayneclub/.ssh/LightsailDefaultKey-ap-northeast-1.pem`; the `lightsail-aws`
alias points at a different host. Local Google session file:
`/Users/wayneclub/.config/gaswise/google-maps-http-session.json`.

Browser synchronization depends on the user's Mac, Codex and authorized browser
being available. Server-side cookie rotation and VPN recovery continue without
them. Notify only for a meaningful recovery, failure or required user action;
stay quiet while healthy. Never promise to automatically recreate a revoked
Google login or invalid NordVPN service credentials.
