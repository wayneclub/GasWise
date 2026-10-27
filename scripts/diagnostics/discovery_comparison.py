"""Bounded public-region comparison; no tokens, signatures or visitor locations in output."""
import json
import os
import time
import urllib.request
from collections import Counter

REGIONS = [('dtla', 34.0407, -118.266, 5000), ('bakersfield', 35.3733, -119.0187, 8000)]


def main():
    report = {'label': os.environ.get('GASWISE_COMPARISON_LABEL', 'sample'), 'regions': []}
    for name, lat, lng, radius in REGIONS:
        body = dict(origin={'lat': lat, 'lng': lng}, radius_meters=radius, fuel_type='regular',
                    discovery_tiles=8, maps_detail_limit=0, gasbuddy_page_limit=1,
                    station_lookup_limit=0, calculate_routes=False, allow_unknown_payment=True)
        request = urllib.request.Request('http://127.0.0.1:8000/v1/smart/search', data=json.dumps(body).encode(),
                                         headers={'Authorization': 'Bearer '+os.environ['GASWISE_API_TOKEN'],
                                                  'Content-Type': 'application/json'})
        start = time.monotonic()
        with urllib.request.urlopen(request, timeout=90) as response:
            result = json.load(response)
        snapshot = result['snapshot']
        ids = {}
        for row in snapshot['stations']:
            ids.setdefault(row['source'], set()).add(row['id'])
        report['regions'].append(dict(
            region=name, query=body, seconds=round(time.monotonic()-start, 3),
            inventory_ids=sorted({row['place_id'] for row in snapshot['inventory']}),
            observed_inventory_ids=sorted({row['place_id'] for row in snapshot['inventory'] if row.get('discovery_state','observed')=='observed'}),
            retained_inventory_ids=sorted({row['place_id'] for row in snapshot['inventory'] if row.get('discovery_state')=='known'}),
            discovery_metrics=snapshot.get('discovery_metrics',{}),
            station_ids={source: sorted(values) for source, values in ids.items()},
            price_rows=dict(Counter(row['source'] for row in snapshot['stations'])),
            statuses=snapshot['source_statuses'], upstream=result['upstream_calls'], cache_hits=result['cache_hits'],
            area_estimate=snapshot['discovery_area_covered'], timings=result['timings_ms']))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
