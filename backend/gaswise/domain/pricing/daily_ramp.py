"""Conservative daily background allowance review; no provider safety guarantees."""

from datetime import timedelta


def reviewed_limit(row):
    current = row["adaptive_daily_limit"]
    if current is None or row["clock"] - row["daily_review_at"] < timedelta(days=1):
        return None
    issue = max((value for value in (row["last_rejection_at"], row["last_collection_failure_at"])
                 if value is not None), default=None)
    clean = issue is None or issue <= row["daily_review_at"]
    recent = row["background_last_request_at"] is not None and row["clock"] - row["background_last_request_at"] < timedelta(days=1)
    if clean and recent and row["daily_review_requests"] >= current * .75:
        return min(row["adaptive_daily_max"], current * 2)
    return current
