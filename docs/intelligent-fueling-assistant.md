# Intelligent fueling assistant

## Implementation status (2026-10-20)

The first vertical slice is implemented behind `GASWISE_SMART_ALERTS_ENABLED`:

- encrypted Web Push subscriptions with per-installation secrets;
- explicit exact-condition station watches, capped at 20 per installation;
- local refuelling cadence and expiring coarse need-state synchronization;
- one alert-policy seam for freshness, evidence, need and savings decisions;
- source-conflict suppression, user thresholds, 24-hour watch cooldown, quiet hours,
  durable outbox retries and a 30-day in-app inbox;
- service-worker display/click handling and complete disable/delete semantics;
- encrypted private backup of refuelling settings/events, excluding Push authority.

Watches currently evaluate observations produced by normal searches and configured
public collection. They do not promise a dedicated provider request for each user
or station. The UI says "when GasWise observes" for this reason. A future watched-
station scheduler must coalesce nearby watches and consume the existing shared
background budgets; it must not create one upstream request per watch.

## Product promise

GasWise should not notify a user merely because a pump-price observation changed.
It should answer a decision:

> Should I refuel now, where should I stop, and what is the likely value of acting?

An alert is useful only when the user may need fuel, the opportunity is materially
better than waiting, and the observation is reliable enough to justify an
interruption. Choosing not to notify is part of the product.

## Goals and boundaries

The first release should:

- estimate a broad refuelling-need window without claiming precise tank telemetry;
- learn relevant stations and recurring contexts locally on the user's device;
- combine need, observed price history, detour, time, payment, rewards, membership,
  opening status and evidence quality;
- explain every recommendation in dollars, time and data freshness;
- adapt notification frequency from explicit feedback and observable interaction;
- preserve the current separation between private browser data and public price
  observations.

The first release should not:

- continuously collect location or silently build a server-side travel history;
- claim that an observed quote is the exact time a pump changed its price;
- claim a precise remaining fuel level without vehicle telemetry;
- predict future prices from sparse station history;
- infer visits merely because a phone passed near a station;
- send an alert based on a station name match, estimated payment basis or a single
  anomalous observation.

## User experience

### Activation

The feature is opt-in and introduced after GasWise has produced at least one useful
recommendation. Activation asks for four small choices:

1. Typical driving: miles per week or one of light, normal and heavy.
2. Refuelling habit: near one-half, one-quarter or the warning light.
3. Notification style: only strong opportunities, balanced, or more frequent.
4. Quiet hours.

Vehicle MPG and tank capacity use the selected vehicle when known. Missing capacity
does not block the feature; GasWise can reason about time since refuelling and
typical weekly usage with lower confidence.

The browser notification permission prompt appears only after the user turns on an
actual alert. A denied permission still permits an in-app notification inbox.

### Refuelling event

Search results and the assistant home card expose **I just refuelled**. The minimal
event records:

- local timestamp;
- optional odometer;
- optional approximate tank state before refuelling;
- optional station selected from the current result;
- whether the user filled the tank or bought a specified number of gallons.

All fields except the timestamp are optional. The confirmation immediately shows
the next broad need estimate, for example: **Likely to need fuel in 6–10 days**.
The user can edit or delete every event.

### Relevant stations

The browser maintains context-specific station affinity rather than one global
"favourite":

- near a user-labelled area such as Home or Work;
- on a recurring route the user explicitly saves;
- explicitly watched;
- membership stations;
- stations repeatedly chosen for navigation or confirmed refuelling.

Private labels and route endpoints remain local. Navigation is a stronger signal
than viewing details, and a confirmed refuelling event is strongest. Affinity
decays over time. GasWise never describes a station as frequently visited until the
user confirms that wording.

When evidence is strong, ask instead of assuming:

> You often choose this station after searching. Use it as one of your regular
> stations?

### Notification examples

Act now:

> **Tonight is a good time to refuel**
> You will likely need fuel within 2–4 days. The on-route Chevron is $4.39/gal,
> near its observed 30-day low. Compared with your usual option, 10 gal is about
> $3.20 less with no extra drive. Reported today at 8:20 AM.

Wait:

> **No special trip needed**
> Costco dropped 14 cents, but you will likely pass it Thursday. Waiting avoids
> about 6.2 extra miles. Tell GasWise if your tank is below one-quarter.

Urgent:

> **A nearby open station is the safer choice**
> Your estimated fuel window is nearly exhausted. This Shell costs about 40 cents
> more than the cheapest result but saves 18 minutes and 9 miles.

"Wait" advice normally stays in the in-app inbox. It becomes a push notification
only when it corrects a previously sent recommendation or the user requests daily
guidance.

## Decision model

### Inputs

The engine operates on four independently qualified inputs:

1. **Need window**: elapsed time, typical miles, MPG, tank capacity and explicit
   refuelling events.
2. **Opportunity**: current comparable price, 7/30/90-day observed distribution,
   nearby alternatives and expected purchase quantity.
3. **Convenience**: precise or clearly labelled estimated detour, added time,
   opening status and saved route context.
4. **Evidence**: source report age, station identity, fuel grade, octane, payment
   basis, membership condition and cross-source conflict.

The current smart-ranking calculation remains the authority for monetary and time
cost. The assistant must not implement a second, inconsistent cost formula.

### Need estimate

Represent remaining range as an interval, not a point estimate. A simple first
model is:

```text
estimated miles used = elapsed weeks * typical weekly miles
uncertainty = input uncertainty + elapsed-time growth + missing-event penalty
remaining range interval = tank range - estimated miles-used interval
need window = time until the user's chosen refuelling reserve is crossed
```

Confidence is high only with recent odometer/refuelling inputs, medium with repeated
refuelling cadence, and low with generic weekly mileage. Low confidence may support
a question or inbox card, but never an urgent low-fuel push.

### Opportunity features

Do not make percentage price movement the main signal. Calculate:

- cents-per-gallon change against the last comparable confirmed level;
- expected purchase savings in dollars;
- percentile within the station's comparable 30-day observations;
- savings against the user's usual station and the current nearby winner;
- detour fuel and time cost;
- cashback and membership effects;
- probability-free evidence penalties for stale, unknown or conflicting data.

History comparisons require the same physical station, grade/octane, payment type
and purchase condition. Estimated comparison prices may influence a sensitivity
range but cannot trigger an alert by themselves.

### Action score

Use an inspectable scoring model before any learned ranking:

```text
action_score =
    need_urgency
  + net_savings_value
  + historical_price_value
  + route_convenience
  + station_affinity
  + evidence_quality
  - interruption_cost
  - recent_notification_penalty
```

Each component is normalized and returned with a reason code. Hard gates run before
scoring:

- valid stable station identity;
- fresh enough current quote;
- comparable fuel and purchase conditions;
- station not known closed;
- no unresolved material source conflict;
- sufficient price coverage to support the statement being made.

Suggested initial outcomes are `notify_now`, `inbox_opportunity`, `wait`,
`ask_for_input` and `no_action`. Thresholds vary with the selected notification
style, not with hidden demographic assumptions.

### Notification fatigue and hysteresis

- At most one push per day by default and three per week.
- A station/fuel/condition alert has a 24-hour cooldown.
- Do not repeat an alert within the same price band.
- After a drop alert, require a meaningful recovery before another drop alert.
- Batch weaker opportunities into an optional digest.
- Quiet hours defer rather than discard an opportunity, unless it expires.
- A user can choose **useful**, **not useful**, **too frequent**, or **wrong fuel
  estimate** directly from the detail view.

Opening a notification is weak positive evidence. Starting navigation is stronger.
Explicit feedback is strongest. Ignoring notifications must reduce frequency slowly;
it does not prove the recommendation was wrong.

## Privacy and data ownership

### Browser-only private state

Keep these fields in a new versioned IndexedDB store:

- refuelling events and odometer entries;
- typical mileage and refuelling reserve;
- private place labels and saved route endpoints;
- station-affinity events and learned weights;
- local notification feedback;
- the current need estimate.

This data is included only in an explicitly exported encrypted private backup.
It must not enter analytics, shared caches, logs or `quote_history`.

### Notification subscription and coarse need sync

Push delivery is part of the MVP and requires limited server state. Enabling it
creates a random, revocable notification installation ID that is separate from the
existing local profile ID. The server receives only:

- push endpoint material;
- explicitly watched canonical/source station identities;
- fuel, octane, payment and membership conditions;
- alert threshold/style, quiet-hours timezone and expiry;
- an optional coarse need state: `not_due`, `approaching`, `due`, or `unknown`;
- the need state's confidence (`high`, `medium`, or `low`) and expiry, never its raw
  mileage calculation;
- the minimum state needed for deduplication and delivery.

It does not receive VIN, plate, MPG, tank size, refuelling events, odometer, private
place labels, routes or continuous location. The browser derives the coarse state
locally and refreshes it when GasWise is opened or a refuelling event is recorded.
It automatically expires; an expired state becomes `unknown` rather than silently
remaining urgent.

This permits useful background decisions without exposing the underlying private
model. For example, a strong observed low-price opportunity can push immediately
for a high-confidence `due` user, wait for a stronger saving when `approaching`, and
stay in the inbox when `not_due`. Low-confidence or unknown need can never produce
low-fuel urgency language. When the notification is opened, the browser performs a
fresh full evaluation using its local context and may explain that the opportunity
has changed.

Disabling notifications deletes the server subscription and rotates the installation
ID before any future opt-in.

## System design

```text
Public collection -> quote_history -> comparable change detector
                                     -> station opportunity records

Local refuelling model + local contexts + current/ranked opportunity
                                     -> action scorer -> inbox / notification

Explicit server watch subscription -> bounded watched-station scheduler
                                   -> push outbox -> delivery adapter
```

### New server entities

`station_opportunities`

- station identity and exact fuel/condition partition;
- current and prior observation keys;
- change, observed percentile and evidence flags;
- evaluation and expiry timestamps;
- unique key preventing duplicate evaluation.

`alert_installations`

- random installation ID hash;
- encrypted push subscription material;
- created, last-confirmed and expiry timestamps;
- disabled/deleted state.

`alert_watches`

- installation reference;
- stable station identity and fuel/condition partition;
- user-selected sensitivity and quiet-hours timezone;
- last delivered price band and time;
- no location, route or vehicle identity.

`alert_need_state`

- installation reference;
- coarse state and confidence enum;
- calculated-at and mandatory expiry timestamps;
- no raw inputs or reconstructable driving history.

`alert_outbox`

- installation and opportunity references;
- dedupe key, expiry, attempts, next attempt and delivery result;
- generic notification text; no private route or fuel estimate.

These tables are separate from the existing operator-facing collection Telegram
notifications.

### Collection policy

An alert promise is credible only if watched stations receive adequate observations.
Add a bounded watched-station scheduler that:

- coalesces all users watching the same public station/fuel partition;
- never creates one provider request per user;
- reuses fresh public cache/history before making a request;
- has strict per-source daily budgets and foreground reserve;
- increases cadence near a possible trigger and backs off when unchanged;
- expires watches that are not periodically confirmed;
- reports insufficient coverage instead of promising active monitoring.

A watch must display its actual monitoring quality: active, limited observations,
temporarily unavailable, or unsupported source.

## API outline

The exact authentication mechanism requires a separate threat review. A proposed
surface is:

- `POST /v1/alerts/installations` — opt in and register push material;
- `DELETE /v1/alerts/installations/{token}` — revoke and delete;
- `PUT /v1/alerts/watches/{station_key}` — create or replace an explicit watch;
- `DELETE /v1/alerts/watches/{station_key}` — stop watching;
- `GET /v1/alerts/watches` — show status and monitoring quality;
- `PUT /v1/alerts/need-state` — replace the optional coarse state with a short TTL;
- `POST /v1/assistant/evaluate` — evaluate a current signed snapshot plus ephemeral
  local context without persisting that context.

The evaluation endpoint returns component scores, reason codes, confidence,
recommended action and a user-facing explanation. Requests and responses remain
`no-store`; private context is not logged.

## Delivery phases

### Phase 1: intelligent assistant with push

- **I just refuelled** and editable local refuelling history.
- Broad need window with visible confidence.
- Local regular-station learning and explicit confirmation.
- Current smart-ranking reuse plus 30-day comparable price position.
- Explainable `notify_now`, `wait`, `ask_for_input` and `no_action` decisions.
- Watched-station scheduler and monitoring-quality status.
- Web Push with in-app fallback.
- Server-side strong-opportunity detection, dedupe, cooldown and quiet hours.
- Expiring coarse need-state sync for background timing.
- Personalized full evaluation on open.

The push title and body are produced from server-verifiable public price evidence
and the coarse need bucket. Deep links contain an opaque opportunity ID, never a
location, price-source credential or private profile data.

### Phase 2: adaptive timing and route context

- User-saved recurring route contexts.
- Feedback-adjusted thresholds and interruption cost.
- Optional privacy-reviewed synchronization of deliberately saved route windows,
  without background location tracking.
- Controlled evaluation against the transparent rules baseline before any learned
  model can influence delivery.

### Push delivery mechanics

- A service worker receives the push, displays the notification and opens the exact
  assistant opportunity on click.
- The application requests notification permission only in response to the user's
  explicit **Turn on smart alerts** action.
- Subscription creation is confirmed server-side before the UI promises monitoring.
- Push payloads contain only display-safe text, opportunity ID, expiry and a signed
  deep-link token. Full station and reasoning data are fetched after the app opens.
- Expired opportunities open a fresh evaluation rather than showing an actionable
  stale recommendation.
- Delivery retries use bounded exponential backoff. Permanent endpoint rejection
  deletes the push material and marks alerts as requiring reactivation.
- An in-app inbox receives the same opportunity record, so missed or unsupported
  push delivery does not erase the advice.
- Notification actions are limited to **View recommendation** and **Mute this
  station**. Recording a refuelling event requires opening the app and confirming it.

## Success measures

Measure utility rather than raw engagement:

- notification-to-navigation and notification-to-confirmed-refuelling rate;
- estimated dollars and detour time saved, labelled as estimates;
- useful versus not-useful feedback;
- alerts per active user and notification disable rate;
- price opportunity coverage and freshness by watched station;
- false urgency reports and wrong-condition alerts, which should be treated as
  safety-quality defects;
- percentage of decisions that abstain because evidence is insufficient.

Do not optimize click-through alone. A useful **wait** recommendation or a week with
no unnecessary alerts is a successful outcome.

## MVP acceptance criteria

1. A user can record, edit and delete a refuelling event without sending it to the
   backend.
2. Need is always presented as a range with a confidence explanation.
3. All price comparisons use exact compatible station/fuel/payment/condition
   partitions and retain source timestamps.
4. The assistant reuses the existing smart-ranking cost outputs rather than
   recalculating a divergent winner.
5. Every outcome includes machine-readable reason codes and a concise explanation.
6. Low-confidence need data cannot produce an urgent push.
7. No watch implies no background station-specific collection.
8. An unsupported or budget-limited watch is visibly degraded, not silently stale.
9. Notification cooldown, hysteresis, quiet hours and global frequency caps have
   deterministic tests.
10. Clearing private data removes the local assistant state; disabling push removes
    the server installation and its watches.
11. A push subscription, service-worker click flow and expired-opportunity fallback
    pass browser integration tests.
12. The server stores only the coarse need enum, confidence and expiry; tests reject
    raw mileage, odometer, route, VIN, plate and place-label fields.
