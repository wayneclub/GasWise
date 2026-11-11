"""Shared HTTP execution policy for expensive upstream operations."""

import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

from fastapi import HTTPException

from gaswise.domain.ports import (
    ProviderCapacityExceededError,
    ProviderError,
    ProviderRateLimitedError,
    ProviderUnavailableError,
)

T = TypeVar("T")


class OperationRunner:
    def __init__(self, capacity: int, *, acquire_timeout: float = 0.5, timeout: float = 55):
        self.slots = asyncio.Semaphore(capacity)
        self.acquire_timeout = acquire_timeout
        self.timeout = timeout

    async def run(self, operation: Callable[[], Awaitable[T]]) -> T:
        try:
            await asyncio.wait_for(self.slots.acquire(), timeout=self.acquire_timeout)
        except TimeoutError:
            raise HTTPException(429, "search_capacity_exceeded", headers={"Retry-After": "5"}) from None
        try:
            async with asyncio.timeout(self.timeout):
                return await operation()
        except ProviderRateLimitedError as error:
            raise HTTPException(429, str(error), headers={"Retry-After": "10"}) from None
        except ProviderCapacityExceededError as error:
            raise HTTPException(429, str(error), headers={"Retry-After": "5"}) from None
        except ProviderUnavailableError as error:
            raise HTTPException(503, str(error)) from None
        except ProviderError as error:
            raise HTTPException(502, str(error)) from None
        except TimeoutError:
            raise HTTPException(504, "search_timeout") from None
        finally:
            self.slots.release()
