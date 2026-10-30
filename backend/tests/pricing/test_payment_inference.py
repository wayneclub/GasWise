from datetime import timedelta
from decimal import Decimal

from gaswise.domain.pricing.comparison import comparable_prices, comparison_price
from gaswise.domain.pricing.payment import infer_payment
from tests.support.comparison import NOW, quote, select


def unknown():
    return quote(canonical_id='site').model_copy(update={'payment_type': 'unknown'})


def test_new_unknown_does_not_remove_valid_card_quote():
    card = quote(source='gasbuddy_web', age=180, canonical_id='site')
    selected, _, _ = select([unknown(), card], fuel_type='premium')
    assert selected[0].station.source == 'gasbuddy_web'


def test_maps_waze_are_one_evidence_family():
    selected, _, _ = select([quote(canonical_id='site'), quote(source='waze', canonical_id='site')], fuel_type='premium')
    assert comparable_prices(selected[0], NOW)[-1] == 1
    assert comparable_prices(selected[0], NOW)[4] == 'limited'


def test_same_price_does_not_change_original_payment():
    raw = unknown()
    cash = quote(canonical_id='site').model_copy(update={'payment_type': 'cash'})
    card = quote(canonical_id='site')
    inferred = infer_payment(raw, [raw, cash, card], [], NOW)
    assert inferred['classification'] == 'same_price'
    assert inferred['confidence'] == 'medium'
    assert raw.payment_type == 'unknown'


def test_history_requires_independent_days_and_preserves_raw_price():
    raw = unknown()
    cash = quote(source='gasbuddy_web', canonical_id='site').model_copy(update={'payment_type': 'cash'})
    history = []
    for day in (1, 2, 3):
        timestamp = NOW - timedelta(days=day)
        history.extend([cash.model_copy(update={'price_updated_at': timestamp}),
                        cash.model_copy(update={'payment_type': 'credit', 'price_per_gallon': Decimal('6.10'), 'price_updated_at': timestamp})])
    assert infer_payment(raw, [raw, cash], history, NOW)['spread'] == '0.10'
    assert infer_payment(raw, [raw, cash], history[:2]*5, NOW)['spread'] is None
    raw.payment_history = [r.model_dump(mode='json') for r in history]
    selected, _, _ = select([raw, cash], fuel_type='premium', payment_type='credit', allow_unknown_payment=True)
    station = selected[0].station
    assert station.price_per_gallon == Decimal('6.00')
    assert station.comparison_price_per_gallon == Decimal('6.10')
    assert station.payment_type == 'unknown'


def test_old_card_quote_does_not_suppress_fresh_unknown():
    card = quote(source='gasbuddy_web', age=1500, canonical_id='site')
    selected, _, _ = select([unknown(), card], fuel_type='premium', allow_unknown_payment=True)
    assert selected[0].station.payment_type == 'unknown'


def test_mapped_location_mismatch_is_not_payment_evidence():
    raw = unknown()
    cash = quote(canonical_id='site').model_copy(update={'payment_type':'cash', 'location': raw.location.model_copy(update={'lat':35})})
    assert infer_payment(raw, [cash], [], NOW)['classification'] == 'unknown'


def test_correlated_feeds_can_conflict_without_independent_corroboration():
    selected, _, _ = select([quote(canonical_id='site'), quote(source='waze', price='6.30', canonical_id='site')], fuel_type='premium')
    comparison = comparable_prices(selected[0], NOW)
    assert comparison[-1] == 1
    assert comparison[3:5] == ('conflicting', 'disputed')


def test_invalid_history_does_not_break_ranking():
    raw = unknown()
    raw.payment_history = [{'bad': 'record'}]
    selected, _, _ = select([raw], fuel_type='premium', allow_unknown_payment=True)
    assert selected[0].station.payment_inference['spread'] is None


def test_wrong_membership_cannot_classify_payment():
    raw = unknown()
    cash = quote(canonical_id='site', membership_required='club').model_copy(update={'payment_type':'cash'})
    selected, _, _ = select([raw, cash], fuel_type='premium', allow_unknown_payment=True)
    assert selected[0].station.payment_inference['classification'] == 'unknown'


def test_different_price_period_cannot_classify_payment():
    raw = unknown()
    cash = quote(canonical_id='site', age=200).model_copy(update={'payment_type':'cash'})
    assert infer_payment(raw, [cash], [], NOW)['classification'] == 'unknown'


def test_new_unknown_conflict_widens_card_comparison_range():
    card = quote(source='gasbuddy_web', price='6.00', age=180, canonical_id='site')
    raw = unknown().model_copy(update={'price_per_gallon':Decimal('6.50')})
    selected, _, warnings = select([raw, card], fuel_type='premium', allow_unknown_payment=True)
    assert selected[0].station.payment_type == 'credit'
    assert comparable_prices(selected[0], NOW)[:2] == (Decimal('6.00'), Decimal('6.50'))
    assert any('Possible price change' in w for w in warnings)


def test_fastrip_rounded_maps_evidence_is_per_grade_and_keeps_raw_terms():
    # Photo-based synthetic rule replay, not a historical provider API replay.
    rows = []
    for grade, maps, cash, card in [
        ('regular', '5.86', '5.739', '5.859'),
        ('midgrade', '6.06', '5.939', '6.059'),
        ('premium', '6.04', '6.039', '6.159'),
        ('diesel', '8.00', '7.879', '7.999'),
    ]:
        base = quote(canonical_id='fastrip').model_copy(update={'fuel_type': grade})
        rows.extend([
            base.model_copy(update={'source': 'google_maps_web', 'payment_type': 'unknown', 'price_per_gallon': Decimal(maps)}),
            base.model_copy(update={'source': 'gasbuddy_web', 'payment_type': 'cash', 'price_per_gallon': Decimal(cash)}),
            base.model_copy(update={'source': 'gasbuddy_web', 'payment_type': 'credit', 'price_per_gallon': Decimal(card)}),
        ])
    for row in rows[::3]:
        inferred = infer_payment(row, rows, [], NOW)
        assert inferred['classification'] == ('cash' if row.fuel_type == 'premium' else 'credit')
        assert inferred['basis'] == 'contemporaneous_price_match'
        assert row.payment_type == 'unknown'
        assert len(inferred['matched_quotes']) == 1
    assert rows[6].price_per_gallon == Decimal('6.04')


def test_maps_cent_match_rejects_nearby_but_differently_rounded_price():
    raw = unknown().model_copy(update={'source': 'google_maps_web', 'price_per_gallon': Decimal('6.04')})
    for price in ('6.031', '6.034', '6.045', '6.049'):
        peer = quote(canonical_id='site', price=price)
        assert infer_payment(raw, [peer], [], NOW)['classification'] == 'unknown'
    assert infer_payment(raw, [quote(canonical_id='site', price='6.035')], [], NOW)['classification'] == 'credit'


def test_rounded_maps_cash_and_card_collision_is_unresolved_not_same_price():
    raw = unknown().model_copy(update={'source': 'google_maps_web', 'price_per_gallon': Decimal('6.04')})
    cash = quote(canonical_id='site', price='6.039').model_copy(update={'payment_type': 'cash'})
    card = quote(canonical_id='site', price='6.041')
    inferred = infer_payment(raw, [cash, card], [], NOW)
    assert inferred['classification'] == 'unknown'
    assert inferred['basis'] == 'ambiguous_price_match'
    assert inferred['confidence'] == 'low'
    assert raw.payment_type == 'unknown'


def test_maps_three_digit_price_is_not_treated_as_a_cent_rounded_quote():
    raw = unknown().model_copy(update={'source': 'google_maps_web', 'price_per_gallon': Decimal('6.039')})
    assert infer_payment(raw, [quote(canonical_id='site', price='6.041')], [], NOW)['classification'] == 'unknown'


def test_uniform_brand_costco_infers_same_price_zero_spread():
    costco_raw = unknown().model_copy(update={'name': 'Costco Gasoline', 'membership_required': 'costco', 'price_per_gallon': Decimal('5.59')})
    inferred = infer_payment(costco_raw, [], [], NOW)
    assert inferred['classification'] == 'same_price'
    assert inferred['confidence'] == 'high'
    assert inferred['basis'] == 'uniform_brand_terms'
    assert inferred['spread'] == '0.00'

    selected, excluded, _ = select([costco_raw], payment_type='credit', memberships=['costco'], allow_unknown_payment=True)
    assert excluded == 0
    assert len(selected) == 1
    # No $0.20 markup applied to uniform brand
    assert comparison_price(selected[0].station) == Decimal('5.59')
    assert selected[0].station.payment_price_adjustment == Decimal(0)

