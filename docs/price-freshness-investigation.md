# Quote age investigation — 2026-10-12

76, 1800 E Olympic Blvd, Los Angeles CA 90021, Google place ChIJc1HhbZ3IwoARxU5LFiaukrM. Native Maps page displayed a blanket “prices over 24 hours old” warning, with prices $5.90 regular / $6.10 midgrade / $6.20 premium / $8.50 diesel.

A bounded production request at 16:33 UTC returned Premium $6.20 with price_updated_at 2026-10-11T21:41:35Z (18h52m old), independently of fetched_at 2026-10-12T16:33:32Z. A separate public-station detail request confirmed field 86 timestamps: regular 1791714113, midgrade 1791604072, premium 1791754895, diesel 1791628608. Other grades were over 24 hours old. The native blanket warning and Premium-specific timestamp differ; this is not evidence of cross-source confirmation or a verified current pump price.

GasBuddy returned gasbuddy_http_bootstrap_challenge with zero quotes. No GasBuddy price contributed to this selection. Existing ranking excludes a selected quote older than max_price_age_minutes (default 1440), rather than using collection time as price age.

Screenshot selection: credit estimate $6.20 + assumed $0.20 = $6.40/gal, 10 gal $64.00 + detour fuel $1.51 = $65.51. Against quickest $70.95, savings $5.44; balanced prices 9 extra minutes at $15/hour ($2.25), so its score remains lower by $3.19. No cashback was shown in the screenshot. Route timings may differ on a new search.

UI now shows actual quote-relative age instead of calling every quote under 24 hours “updated today”. TOP TIER is a compact badge next to station names; the rating row contains only rating/review count.
