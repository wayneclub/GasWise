# Browser-only vehicle identity

VIN / plate identifiers remain on the user's browser. GasWise temporarily
processes a lookup and forwards it to the selected vehicle-data provider, but
has no identifier database, persistent identifier cache, or identifier logging.
Vehicle identity lookups use JSON POST through the app gateway. The configured
AutoZone and NHTSA flows use upstream POST. Optional Vehicle Databases uses its
provider-required URL format; do not enable HTTP request logging for that client.
Third-party services have their own retention policies; GasWise cannot control
their retention after an explicitly requested lookup.

## Local encryption

- Native Web Crypto AES-GCM, 256-bit non-extractable CryptoKey.
- One origin-local IndexedDB record contains the CryptoKey, random 96-bit IV,
  ciphertext, and expiration metadata. No raw key export or plaintext fallback.
- Purpose/version and expiration are authenticated as additional data.
- Confirmed identity is restored locally without an upstream request or password.
- Thirty days after the last save, expired data is deleted on next access.
- Clear removes ciphertext and its key together, clears shared frontend identity,
  and resets the vehicle input. Writes/clear are serialized in each document.
- Unsupported/blocked storage keeps the identity in current-session memory;
  failures are visible, including a failed clear. User can clear site data in
  browser settings. Ordinary localStorage preferences have an explicit allowlist
  and never include VIN, plate, or destination coordinates.

Encryption protects stored payload integrity and keeps identifiers out of
plaintext browser storage. Because automatic unlock uses a key in the same
browser profile, it is not password-based or hardware-backed protection against
malicious same-origin code or a fully compromised browser profile. The app's
CSP, trusted dependency boundaries, and no-referrer policy remain necessary.

## Server handling

The API returns `Cache-Control: no-store`. Request validation replies omit raw
input and exception context, and Pydantic error strings hide input values.
No visitor identifiers are added to pricing caches, signed pricing snapshots,
metrics, or SQL. Existing public station/price/AAA caches remain anonymous.
Route cache values contain totals and duration, not the user's origin; their
keys are digests. Identifier lookup results are not persisted server-side.

This feature needs no PostgreSQL. If a shared pricing database is later needed,
`db.wayneclub.com` can hold public station/price observations only; visitor VIN,
plate, browser key and ciphertext must not be sent to that database.

## Validation

Real Web Crypto unit tests cover round-trip encryption, failed key export,
tampering, authenticated expiration, expiry, queued clear, and unavailable
storage. Native Codex-browser QA uses synthetic data on separate localhost port
5174, verifies restoration after reload and non-exportable key/ciphertext flags,
then clears the test record. No identity lookup is sent upstream during this QA.
The dev-only page is `frontend/src/test/identity-vault-check.html`; it is not a
production build entry or a file in the public static directory.

References: [Web Crypto / IndexedDB keys](https://developer.mozilla.org/en-US/docs/Web/API/SubtleCrypto),
[CryptoKey extractability](https://developer.mozilla.org/en-US/docs/Web/API/CryptoKey).
