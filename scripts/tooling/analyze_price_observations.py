"""Analyze exported public quotes offline; never guess payment provenance."""
import argparse
import json
from collections import Counter
from decimal import Decimal
from pathlib import Path


def analyze(quotes):
    # Stratify so the larger Maps cache cannot overwhelm the other sources.
    limits = {'gasbuddy_web': 34, 'waze': 33, 'google_maps_web': 33}
    sample = []
    for source, limit in limits.items():
        rows = sorted((q for q in quotes if q['source'] == source),
                      key=lambda q: (q['id'], q['fuel_type'], q['payment_type']))
        sample.extend(rows[:limit])
    return {'sample_count': len(sample),
            'source_counts': dict(Counter(q['source'] for q in sample)),
            'price_precision': {source: dict(Counter(
                max(0, -Decimal(q['price_per_gallon']).as_tuple().exponent)
                for q in sample if q['source'] == source)) for source in limits},
            'observations': sample,
            'limitations': 'Observations are not matched station pairs. Cached report times vary; no payment inference.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    args.output.write_text(json.dumps(analyze(json.loads(args.input.read_text())['quotes']),
                                    ensure_ascii=False, indent=2))
