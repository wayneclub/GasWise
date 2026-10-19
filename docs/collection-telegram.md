# Collection attempt history and Telegram reporting

Fixed-base jobs append a durable PostgreSQL attempt when their owner completes them.
Success, source failure, internal-budget deferral, and interruption are separate outcomes.
Expired job leases record an interruption before takeover. Ownership and a unique
job/owner key prevent duplicate completion records. Historical failures before this
feature cannot be reconstructed from the previous last-error-only fields.

Each record stores start/finish/retry timestamps, sanitized reason code, final HTTP
status and phase, selected egress lane, HTTP request attempts, and returned quote
and station counts. HTTP attempts count budget-admitted requests, including transport
failures. Cache hits can have zero HTTP attempts and no lane. Quote/station return
counts overlap across jobs and are not unique-station coverage. Lane task success
rates use success/(success + source failure), excluding budget deferrals and interruption.
The global provider budgets and rejection cooldowns remain unchanged.

A failed or interrupted attempt and its Telegram outbox row commit together.
The background worker sends failure alerts and hourly summaries for hours containing
attempts. Hour boundaries are UTC; displayed timestamps use America/Los_Angeles
with daylight-saving timezone labels. The journal and outbox retain 90 days.
`GET /v1/sources/collection-report?hours=24` requires the existing API authorization
and supports 1–2160 hours. It reports tracking start, reasons, lanes and delivery status
without making any provider requests.

Set these private runtime variables (do not commit their values):

```
GASWISE_COLLECTION_TELEGRAM_ENABLED=true
GASWISE_COLLECTION_TELEGRAM_BOT_TOKEN=<existing bot token>
GASWISE_COLLECTION_TELEGRAM_CHAT_ID=<existing destination>
GASWISE_COLLECTION_TELEGRAM_THREAD_ID=<optional forum topic id>
```

Collection and PostgreSQL must be enabled. Sending uses the Bot API only; it does
not poll updates or interfere with the existing bot's command loop. A successful
Telegram message id acknowledges delivery. Retry errors and timestamps persist;
429 respects Telegram retry_after. Network uncertainty can cause a duplicate message
on retry, so alerts include a run id. Notices older than 24 hours expire and remain
visible in delivery statistics instead of sending stale alert floods. Global dispatch
spacing and leases coordinate multiple backend workers. Tokens, provider bodies,
raw errors, cookies, CSRF values and proxy credentials are excluded from reports/logs.

To verify delivery, create an explicitly labeled `canary` attempt, let the actual
outbox worker send it, verify sent_at and telegram_message_id, then remove synthetic
rows. Do not confuse a notification canary with a real source incident or throughput
measurement.
