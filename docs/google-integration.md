# Google Places fuel prices

`POST /v1/sources/google/prices` uses Nearby Search (New) only. It works alongside
GasBuddy in `prices_only` mode; it does not call Routes, Text Search or Place Details.
Set `GASWISE_GOOGLE_API_KEY` in `backend/.env` and keep `GASWISE_API_TOKEN` configured.
Restart the backend after configuration changes. Never send the Google key to clients.

Enable **Places API (New)** and billing in Google Cloud. Restrict the server key to
Places API (New) and, when available, the backend's public egress IP addresses.
Enable Routes API and allow it on the key only when using Google recommendations.

Example JSON body (Bearer authentication required):

```json
{"origin":{"lat":34.0522,"lng":-118.2437},"radius_meters":5000,"max_results":20,"fuel_type":"premium"}
```

The endpoint returns normalized `stations`, attribution and coverage warnings.
`fuel_type` accepts regular, midgrade, premium and diesel. Up to 20 places are
searched, but only US stations with a positive USD price matching the selected fuel
are returned. An empty list means no matching prices were supplied, not free fuel.
Prices are USD per US gallon, serialized as decimal strings. Google's `updateTime`
is preserved separately from retrieval time. Premium does not verify numeric 91
AKI; cash/credit conditions are unknown. Third-party attribution is retained on each
station. Clients must display the required Google Maps attribution and provider
credits; on-map Places results require a Google map. No frontend is included here.

Normal successful requests issue one Nearby Search call regardless of result count.
Transient failures can retry up to three attempts. This endpoint does not poll;
calling it repeatedly creates additional upstream requests. It stores no price
history and returns `Cache-Control: no-store`. Existing recommendations/SSE have
separate route and polling costs and can also include GasBuddy address resolution.

## Pricing and operational limits

Checked against the official global list on 2026-10-09: requesting `fuelOptions`
triggers Nearby Search Enterprise + Atmosphere: 1,000 free monthly events, then
$40 per 1,000 events in the first paid tier. Place Details Enterprise + Atmosphere
has a separate 1,000-event cap and $25 per 1,000 first-tier price; Text Search
Enterprise + Atmosphere has 1,000 and $40. Usage is aggregated across projects
linked to a billing account, not granted per user. These caps are not enforced by
this service. Configure Google Cloud quotas and budget alerts before public use;
budget alerts do not stop billing. The service token/concurrency limit is not a
monthly spending cap. Do not archive Places content for longitudinal research
without checking the applicable license and storage exceptions.

Sources:
- [Global pricing](https://developers.google.com/maps/billing-and-pricing/pricing)
- [Nearby Search fields and limits](https://developers.google.com/maps/documentation/places/web-service/nearby-search)
- [FuelOptions schema](https://developers.google.com/maps/documentation/places/web-service/reference/rest/v1/places#FuelOptions)
- [Policies and attribution](https://developers.google.com/maps/documentation/places/web-service/policies)

Live price coverage and account billing remain unverified until a configured key
is used. Automated tests use synthetic responses and do not consume Google quota.
