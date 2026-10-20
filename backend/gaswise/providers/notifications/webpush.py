"""Encrypted-at-rest browser push subscriptions and Web Push delivery."""

import asyncio
import base64
import ipaddress
import json
import socket
from urllib.parse import urlsplit

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from pywebpush import WebPushException, webpush


class PushSubscriptionCipher:
    def __init__(self, encoded_key: str):
        try:
            key = base64.urlsafe_b64decode(encoded_key + "=" * (-len(encoded_key) % 4))
        except Exception:
            key = b""
        if len(key) != 32:
            raise ValueError("Push subscription key must be URL-safe base64 for exactly 32 bytes")
        self._cipher = AESGCM(key)

    def encrypt(self, subscription: dict) -> bytes:
        nonce = __import__("secrets").token_bytes(12)
        ciphertext = self._cipher.encrypt(nonce, json.dumps(subscription, separators=(",", ":")).encode(), b"gaswise-push-v1")
        return nonce + ciphertext

    def decrypt(self, payload: bytes) -> dict:
        return json.loads(self._cipher.decrypt(payload[:12], payload[12:], b"gaswise-push-v1"))


async def _public_endpoint(endpoint: str) -> None:
    parsed = urlsplit(endpoint)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("push_endpoint_invalid")
    try:
        addresses = await asyncio.to_thread(socket.getaddrinfo, parsed.hostname, 443, type=socket.SOCK_STREAM)
    except OSError:
        raise ValueError("push_endpoint_unresolvable") from None
    if not addresses or any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):
        raise ValueError("push_endpoint_not_public")


class WebPushSender:
    def __init__(self, private_key: str, subject: str):
        self.private_key, self.subject = private_key, subject

    async def send(self, subscription: dict, payload: dict) -> None:
        await _public_endpoint(subscription["endpoint"])
        try:
            await asyncio.to_thread(
                webpush,
                subscription_info=subscription,
                data=json.dumps(payload, separators=(",", ":")),
                vapid_private_key=self.private_key,
                vapid_claims={"sub": self.subject},
                ttl=300,
            )
        except WebPushException as error:
            status = getattr(getattr(error, "response", None), "status_code", None)
            if status in {404, 410}:
                raise PushEndpointGone from None
            raise PushDeliveryError from None


class PushDeliveryError(Exception):
    pass


class PushEndpointGone(PushDeliveryError):
    pass
