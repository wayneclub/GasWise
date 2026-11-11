import pytest
from datetime import UTC, datetime, timedelta

from gaswise.contracts.common import Point
from gaswise.contracts.search import Search
from gaswise.contracts.smart import SmartSnapshot
from gaswise.domain.ports import InvalidSnapshotSignatureError, SnapshotExpiredError
from gaswise.services.pricing.signer import SnapshotSigner


def dummy_snapshot(expired: bool = False) -> SmartSnapshot:
    now = datetime.now(UTC)
    expires = now - timedelta(seconds=10) if expired else now + timedelta(seconds=300)
    return SmartSnapshot(
        query=Search(origin=Point(lat=34.0, lng=-118.0)),
        stations=[],
        source_statuses=[],
        collected_at=now,
        expires_at=expires,
    )


def test_snapshot_signer_sign_and_verify():
    secret = b"test-secret-key-12345"
    signer = SnapshotSigner(secret)
    snapshot = dummy_snapshot()
    sig = signer.sign(snapshot)

    assert isinstance(sig, str)
    assert len(sig) == 64
    # Valid signature does not raise
    signer.verify(snapshot, sig)


def test_snapshot_signer_rejects_tampered_signature():
    signer = SnapshotSigner(b"test-secret-key-12345")
    snapshot = dummy_snapshot()
    invalid_sig = "a" * 64

    with pytest.raises(InvalidSnapshotSignatureError):
        signer.verify(snapshot, invalid_sig)


def test_snapshot_signer_rejects_expired_snapshot():
    signer = SnapshotSigner(b"test-secret-key-12345")
    snapshot = dummy_snapshot(expired=True)
    sig = signer.sign(snapshot)

    with pytest.raises(SnapshotExpiredError):
        signer.verify(snapshot, sig)
