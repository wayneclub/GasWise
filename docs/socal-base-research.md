# SoCal fixed-base selection

This is a sampling plan for unattended fuel-price history, not a ranking of fuel
transactions or proof of the most frequently visited individual stations.

## Selection and provenance

- Include every city with at least 100,000 residents in the January 2026 California
  Department of Finance population ranking within Los Angeles, Orange, San Diego,
  Riverside, San Bernardino, Ventura, Santa Barbara and Imperial counties: 49 cities.
- Add 36 regional sampling bases for SGV employment/retail access, intercity commutes,
  and desert highway travel. These are curated coverage choices, not measured
  transaction leaders. Baker and Rowland Heights are Census-designated places.
- Use Census 2025 Gazetteer interior points for new bases. Select the incorporated
  city record over a same-named CDP (notably Burbank). Retain the original public LA,
  Irvine and San Diego points so existing schedules/cache/history remain stable.
- A 10-km circle is a sampling area, not municipal boundaries or whole-city coverage.
  Nearby bases overlap; source and physical-station identities need separate deduplication.

Sources:

- [California Department of Finance E-1, released May 2026](https://dof.ca.gov/forecasting/demographics/estimates-e1/)
- [January 2026 city population ranking workbook](https://dof.ca.gov/media/docs/forecasting/Demographics/estimates-e1/RankCities_2026.xlsx)
- [Census 2025 California place Gazetteer](https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2025_Gazetteer/2025_gaz_place_06.txt)
- [SCAG regional scope](https://www.scag.ca.gov/about-us)
- [Caltrans I-15 corridor facility profile](https://dot.ca.gov/-/media/dot-media/programs/transportation-planning/documents/f0009438-final-2015-itsp-a11y.pdf)
- [Caltrans District 8 corridor projects](https://dot.ca.gov/caltrans-near-me/district%208)
- [SANDAG regional transportation plan](https://sandag.org/planning/regional-plan-landing/current-plan)
- [SBCAG regional travel patterns](https://www.sbcag.org/new-report-reveals-changes-and-trends-in-regional-travel-patterns/)
- [City of Industry employment base](https://www.cityofindustry.org/231/Economic-Development)

## Sampling cadence and capacity

Each base has five jobs: GasBuddy Regular/Premium, Maps Regular/Premium, and one
Waze all-reported-fuels acquisition. Waze retains native fuel/payment/octane
labels; unknown payment and unverified octane remain unknown. Its all-fuels cache
has a separate versioned namespace from single-fuel serving queries. The 85 bases
produce 425 persisted jobs. They run without visitor searches.

The target interval is 24 hours after success, but the actual interval is bounded
by shared source allowance, cooldown and queue size. Exhausted sources are skipped
before claiming jobs, preserving their old due dates. The oldest due jobs run
first; population breaks ties within the same initial batch. Restarts do not reset
completed jobs' schedules. Fixed work takes precedence over extra hot-query warming.

At the existing 40 background HTTP/source/24-hour allowance, a full 170-query
GasBuddy pass at a cold four HTTP/query would require about 17 allowance days.
A Waze pass is 85 queries, at least three allowance days at one HTTP/query,
before authentication/failure overhead. Bootstrap reuse or early pagination stops
can reduce cost; rejections and foreground demand can delay progress. This is not
a promise that every city is updated daily. Daily caps are not provider-published
safe limits and are not automatically increased by adding cities.

## Bases

| County | Count | Bases |
| --- | ---: | --- |
| Imperial | 2 | Calexico, El Centro |
| Los Angeles | 23 | Alhambra, Arcadia, Burbank, Diamond Bar, Downey, El Monte, Glendale, Industry, Inglewood, Lancaster, Long Beach, Los Angeles, Monterey Park, Norwalk, Palmdale, Pasadena, Pomona, Rowland Heights, San Gabriel, Santa Clarita, Torrance, Walnut, West Covina |
| Orange | 14 | Anaheim, Costa Mesa, Fullerton, Garden Grove, Huntington Beach, Irvine, Lake Forest, Mission Viejo, Orange, San Clemente, San Juan Capistrano, Santa Ana, Tustin, Westminster |
| Riverside | 15 | Banning, Beaumont, Blythe, Corona, Eastvale, Indio, Jurupa Valley, Lake Elsinore, Menifee, Moreno Valley, Murrieta, Palm Desert, Palm Springs, Riverside, Temecula |
| San Bernardino | 13 | Baker, Barstow, Chino, Chino Hills, Fontana, Hesperia, Needles, Ontario, Rancho Cucamonga, Redlands, Rialto, San Bernardino, Victorville |
| San Diego | 9 | Carlsbad, Chula Vista, El Cajon, Encinitas, Escondido, Oceanside, San Diego, San Marcos, Vista |
| Santa Barbara | 4 | Buellton, Goleta, Santa Barbara, Santa Maria |
| Ventura | 5 | Camarillo, Oxnard, San Buenaventura (Ventura), Simi Valley, Thousand Oaks |
