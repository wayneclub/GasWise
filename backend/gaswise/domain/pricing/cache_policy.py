"""Retention policy for public provider responses, independent of storage."""

from datetime import UTC, datetime, timedelta

PRICE_LISTS = ("prices", "stations", "all_prices")


def quote_expiry(quote):
    reported = quote.get("price_updated_at")
    fetched = quote.get("fetched_at")
    timestamp = reported or fetched
    if not timestamp:
        return None
    date = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    return date + (timedelta(hours=72) if reported else timedelta(hours=6))


def prune_quotes(payload, now=None):
    """Never renew source timestamps by re-fetching an unchanged old quote."""
    now = now or datetime.now(UTC)
    def eligible(quote):
        expiry = quote_expiry(quote)
        reported = quote.get("price_updated_at")
        future = reported and datetime.fromisoformat(reported.replace("Z", "+00:00")) > now + timedelta(minutes=5)
        return expiry is not None and expiry > now and not future
    if isinstance(payload, list):
        return [quote for quote in payload if eligible(quote)]
    return {
        key: [quote for quote in value if eligible(quote)] if key in PRICE_LISTS else value
        for key, value in payload.items()
    }


def public_quotes(payload):
    if isinstance(payload, list):
        return payload
    # all_prices may repeat stations; the database's quote key deduplicates them.
    return [quote for key in PRICE_LISTS for quote in payload.get(key, [])]
