"""One conservative allowance policy for optional background acquisition."""
import math


def optional_allowance(daily_limit):
    # City sampling and hotspot repair retain at least 80% of the allowance.
    return max(0, int(daily_limit) // 5)


def warming_interval(minimum, request_cost, active_cost, daily_limit):
    allowance = optional_allowance(daily_limit)
    if allowance == 0:
        return 86400
    return max(minimum, math.ceil(86400 * max(request_cost, active_cost) / allowance))
