"""Canonical snapshot serialization, signing and expiration verification."""

import hashlib
import hmac
import json
import math
from datetime import UTC, datetime

from gaswise.contracts.smart import SmartSnapshot
from gaswise.domain.ports import InvalidSnapshotSignatureError, SnapshotExpiredError


def canonical(value):
    """JSON-number-agnostic form: browsers re-serialize 3.0 as 3 and reorder integer-like keys."""
    if isinstance(value, dict):
        return {key: canonical(item) for key, item in value.items()}
    if isinstance(value, list):
        return [canonical(item) for item in value]
    if isinstance(value, float) and math.isfinite(value) and value.is_integer():
        return int(value)
    return value


def snapshot_bytes(snapshot: SmartSnapshot) -> bytes:
    payload = canonical(snapshot.model_dump(mode="json"))
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


class SnapshotSigner:
    """Signs client-held price snapshots and validates signatures against tampering and expiration."""

    def __init__(self, secret: bytes):
        self.secret = secret

    def sign(self, snapshot: SmartSnapshot) -> str:
        """Compute a canonical HMAC-SHA256 signature for the given snapshot."""
        return hmac.new(self.secret, snapshot_bytes(snapshot), hashlib.sha256).hexdigest()

    def verify(self, snapshot: SmartSnapshot, signature: str) -> None:
        """Validate HMAC signature integrity and check that the snapshot has not expired."""
        if not hmac.compare_digest(signature, self.sign(snapshot)):
            raise InvalidSnapshotSignatureError()
        if datetime.now(UTC) >= snapshot.expires_at:
            raise SnapshotExpiredError()
