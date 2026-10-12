"""Bounded process-memory cache. Never changes source timestamps or persists locations."""

import copy
import time
from collections import OrderedDict


class TTLCache:
    def __init__(self, capacity=256, clock=time.monotonic):
        self.capacity, self.clock = capacity, clock
        self.entries = OrderedDict()

    def get(self, key):
        now = self.clock()
        for expired in [k for k, (expiry, _) in self.entries.items() if expiry <= now]:
            self.entries.pop(expired)
        entry = self.entries.get(key)
        if entry is None:
            return None
        self.entries.move_to_end(key)
        return copy.deepcopy(entry[1])

    def put(self, key, value, seconds):
        self.entries[key] = (self.clock() + seconds, copy.deepcopy(value))
        self.entries.move_to_end(key)
        while len(self.entries) > self.capacity:
            self.entries.popitem(last=False)

    def clear(self):
        self.entries.clear()
