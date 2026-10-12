# TOP TIER brand badges

## What it is, and what it is not

There is no US government rating or grading of gas stations. Federally, the EPA only sets a minimum detergent concentration that every gasoline must meet (in force since 1995). State weights-and-measures programs check pump accuracy and fuel specifications, but they do not publish quality tiers.

TOP TIER Detergent Gasoline is a voluntary standard created in 2004 by automakers (BMW, General Motors, Honda, Toyota, Volkswagen, Mercedes-Benz, Audi, and others). Licensed brands must exceed the EPA detergent minimum, avoid metallic additives, and pass audits by ISO 17025 laboratories. Licensing is brand-level: every outlet and octane grade of a licensed brand qualifies, with or without a pump decal. GasWise labels it as a brand license, never as a government rating.

## Source and refresh

- Source: the program's public table at <https://www.toptiergas.com/gasoline-brands/> (Brand / Country). Plain HTTP, no browser. On 2026-10-11 it listed 98 brands, 78 in the USA, last modified 2026-08-27. Changes happen a few times a year, not on a fixed annual date.
- `TopTierProvider` (`backend/gaswise/providers/quality/top_tier.py`) refreshes on a schedule, never during a search. On startup it checks staleness, then re-checks every 6 hours and fetches when the list is older than `GASWISE_TOP_TIER_REFRESH_HOURS` (default 168).
- A successful refresh is written atomically to `GASWISE_TOP_TIER_CACHE_FILE` (default `~/.cache/gaswise/top-tier-brands.json`; empty disables the cache). A cold start loads the cache, then the bundled snapshot `top_tier_brands.json` shipped with the package.
- Safety: a page without a Brand / Country table, or with fewer than 30 US brands, is treated as a page change. The previous list is kept and the failure is logged.
- `GASWISE_TOP_TIER_REFRESH_ENABLED=false` disables network refresh (tests do this); matching still works from the cache or bundled snapshot.

## Matching

`domain/pricing/top_tier.py` matches a station name, or a Waze brand field, against US brands. A match must be the whole name or a whole-word prefix ("Chevron ExtraMile" matches Chevron; "Shellbrook Fuel" does not match Shell). Multi-name brands are split ("Costco / Kirkland Signature"). Brands made of everyday words (Express Mart, Fuel Depot, Fast Fuel, Beacon, WOW and similar) only match exactly. Stations are tagged once at acquisition (`Station.top_tier_brand`), so tags are signed with the smart snapshot and reranks reuse them without a lookup.

Limits: name matching can miss rebadged or oddly named outlets and cannot see a brand dropping a single station. Show it as a brand badge, and keep the "look for the decal" note.

## Ranking: a preference, not a filter

Stations without a TOP TIER brand stay in every result. `prefer_top_tier` (default true) only affects Best Value: when the cost-first winner is not TOP TIER, the first TOP TIER station whose conservative total cost is within `top_tier_margin_per_gallon` × purchased gallons (default 0.05 USD/gal, so $0.50 for 10 gal) moves to the top. Lowest Cost and Quickest stay purely cost- and time-ordered. When the preference changes the winner, `recommendations.best_value.top_tier_preferred_over` names the station it replaced, the extra cost and the margin, and the frontend says so on the card. `top_tier_only` remains an API option for strict filtering.

## API

- `Station.top_tier_brand`: matched brand or null.
- `RankOptions.prefer_top_tier`, `top_tier_margin_per_gallon`: Best Value preference described above.
- `RankOptions.top_tier_only`: strict filter (`not_top_tier`); not exposed in the UI. Both work in `/v1/smart/rerank` with zero upstream calls.
- `GET /v1/quality/top-tier`: the current list, its origin (`bundled`, `cache`, `live`), page modification time and fetch time. Served from memory.
- `/v1/capabilities` reports `top_tier_list_origin` and `top_tier_list_modified_at`.

Sources checked: [TOP TIER approved brands](https://www.toptiergas.com/gasoline-brands/), [TOP TIER program announcement (2024)](https://www.toptiergas.com/2024/04/12/top-tier-program-exceeds-100000-licensed-stations/), [Top Tier Detergent Gasoline overview](https://en.wikipedia.org/wiki/Top_Tier_Detergent_Gasoline).
