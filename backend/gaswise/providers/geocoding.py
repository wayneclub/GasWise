"""Location lookup via observed Google Maps website arrays; no Places API."""
import asyncio
import hashlib
import re
import time

from pydantic import ValidationError

from gaswise.contracts.common import Point
from gaswise.domain.ports import ProviderError
from gaswise.providers.google.maps_web import FEATURES, MapsWebProvider, records

US_SCOPE = ', United States'


def is_business(row):
    # Observed field 88[1]: businesses carry 'SearchResult.TYPE_*'; cities,
    # neighborhoods and other areas carry None.
    try:
        return isinstance(row[88][1], str)
    except (IndexError, TypeError):
        return False


def country(row):
    try:
        return row[183][1][6]
    except (IndexError, TypeError):
        return None


class LocationProvider:
    def __init__(self, maps_web: MapsWebProvider):
        self.maps_web = maps_web
        self.lock = asyncio.Lock()
        self.last_request = 0.0
        self.cache = {}

    @staticmethod
    def parse(data):
        candidates, seen = [], set()
        for row in records(data):
            try:
                # Country comes from the structured address, never viewport bias.
                if row[183][1][6] != 'US':
                    continue
                point = Point(lat=row[9][2], lng=row[9][3])
                identifier = row[78] if isinstance(row[78], str) and row[78] else row[10]
                name = row[11]
                if not isinstance(identifier, str) or not identifier or not isinstance(name, str) or not name.strip():
                    continue
                address = ', '.join(row[2]) if isinstance(row[2], list) and all(isinstance(s, str) for s in row[2]) else None
                label = f'{name}, {address}' if address and address != name else name
                if identifier in seen:
                    continue
                seen.add(identifier)
                candidates.append({'id': identifier, 'label': label, 'location': point})
            except (IndexError, TypeError, KeyError, ValidationError):
                continue
            if len(candidates) == 5:
                break
        return candidates

    async def search(self, text: str):
        text = ' '.join(text.split())
        if len(text) < 2 or len(text) > 200:
            raise ProviderError('location_invalid_query')
        headers = self.maps_web.headers()
        zip_code = re.fullmatch(r'\d{5}(?:-\d{4})?', text)
        query = text + US_SCOPE if zip_code else text
        key = hashlib.sha256(query.casefold().encode()).hexdigest()
        async with self.lock:
            now = time.monotonic()
            self.cache = {k: v for k, v in self.cache.items() if v[0] > now}
            if key in self.cache:
                return self.cache[key][1]
            data = await self.request(query, headers)
            rows = list(records(data))
            us_top = next((row for row in rows if country(row) == 'US'), None)
            result = {'candidates': self.parse(data), 'reason': None}
            if not result['candidates'] and any(country(row) not in (None, 'US') for row in rows):
                # Google found the place, but it is outside the US price sources.
                result['reason'] = 'unsupported_area'
            elif (result['candidates'] and is_business(us_top) and not zip_code
                  and not query.casefold().endswith(US_SCOPE.casefold())):
                # A business top hit for a place-like query ("new york, new york" is a
                # Las Vegas casino). Prefer a city or area when a US-scoped query has one.
                scoped = await self.request(query + US_SCOPE, headers)
                top = next((r for r in records(scoped) if country(r) == 'US'), None)
                if top is not None and not is_business(top):
                    result['candidates'] = self.parse(scoped)
            if result['candidates'] or result['reason']:
                if len(self.cache) >= 32:
                    self.cache.pop(next(iter(self.cache)))
                self.cache[key] = (time.monotonic() + 120, result)
            return result

    async def request(self, query, headers):
        # Caller holds self.lock; requests stay at most one per second.
        await asyncio.sleep(max(0, 1 - (time.monotonic() - self.last_request)))
        self.last_request = time.monotonic()
        # US-wide initial viewport. Each result still requires explicit US metadata.
        pb = '!4m12!1m3!1d10000000!2d-98!3d39!2m3!1f0!2f0!3f0!3m2!1i1280!2i720!4f13.1!7i20!10b1' + FEATURES
        return await self.maps_web.get_data('/search', {'tbm': 'map', 'hl': 'en', 'gl': 'us', 'pb': pb, 'q': query}, headers)
