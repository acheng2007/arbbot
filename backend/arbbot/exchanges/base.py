import asyncio
import json
import random
from collections.abc import Callable
from typing import Protocol

import httpx

from arbbot.domain import Book, Market


class Adapter(Protocol):
    venue: str

    async def discover(self, limit: int) -> list[Market]: ...

    async def fetch_book(self, market: Market) -> Book: ...


class ExchangeHTTP:
    """Bounded, paced read requests. Regenerate auth headers on every retry."""

    def __init__(self, client: httpx.AsyncClient, interval: float = 0.15):
        self.client = client
        self.interval = interval
        self.lock = asyncio.Lock()
        self.next_request = 0.0

    async def get(self, url: str, params=None, headers: Callable | None = None):
        for attempt in range(3):
            async with self.lock:
                loop = asyncio.get_running_loop()
                await asyncio.sleep(max(0, self.next_request - loop.time()))
                self.next_request = loop.time() + self.interval
            try:
                response = await self.client.get(
                    url,
                    params=params,
                    headers=headers() if headers else None,
                )
                response.raise_for_status()
                # Retain exact native numeric text in source payloads.
                return json.loads(response.text, parse_float=str)
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code not in {429, 500, 502, 503, 504} or attempt == 2:
                    raise
                try:
                    delay = min(30, max(0, float(exc.response.headers.get("Retry-After", "0"))))
                except ValueError:
                    delay = 0
            except httpx.TransportError:
                if attempt == 2:
                    raise
                delay = 0
            await asyncio.sleep(max(delay, 2**attempt + random.uniform(0, 0.25)))
        raise RuntimeError("Retry budget exhausted")
