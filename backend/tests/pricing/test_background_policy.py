from gaswise.domain.pricing.background_policy import optional_allowance, warming_interval


def test_optional_share_and_feasible_warming_interval():
    assert optional_allowance(640) == 128
    assert warming_interval(900, 4, 38 * 4, 640) == 102600
    assert warming_interval(900, 3, 8 * 3, 160) == 64800
    assert warming_interval(900, 1, 1, 800) == 900
    assert optional_allowance(4) == 0
