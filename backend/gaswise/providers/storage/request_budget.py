"""Count actual outgoing provider requests against the shared database budget."""

from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

from gaswise.domain.ports import ProviderError
from gaswise.domain.pricing.shared_cache import background_acquisition


def retry_seconds(headers):
    value = headers.get("Retry-After")
    if not value:
        return None
    try:
        return max(0, float(value))
    except ValueError:
        try:
            return max(0, (parsedate_to_datetime(value) - datetime.now(UTC)).total_seconds())
        except (TypeError, ValueError, OverflowError):
            return None


class RequestBudget:
    def __init__(self, store, limits, background_daily_limit=100):
        self.store, self.limits = store, limits
        self.background_daily_limit = background_daily_limit

    async def before(self, source):
        try:
            if background_acquisition.get():
                await self.store.consume(source, self.limits[source], background=True,
                                         background_daily_limit=self.background_daily_limit)
            else:
                await self.store.consume(source, self.limits[source])
        except ProviderError:
            raise
        except Exception:
            raise ProviderError("shared_pricing_budget_unavailable") from None

    async def after(self, source, response):
        if response.status_code not in (401, 403, 429) and response.headers.get("cf-mitigated") != "challenge":
            return
        try:
            await self.store.cooldown(source, retry_seconds(response.headers))
        except Exception:
            raise ProviderError("shared_pricing_budget_unavailable") from None
        raise ProviderError(f"{source}_rate_limited" if response.status_code == 429 else f"{source}_access_rejected_cooldown")
