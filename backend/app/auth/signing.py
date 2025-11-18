"""Lightweight signer compatible with the subset of itsdangerous we rely on."""

from __future__ import annotations

import base64
import hashlib
import hmac


class BadSignature(Exception):
    """Raised when a signed value fails verification."""


class Signer:
    """Minimal stand-in for :class:`itsdangerous.Signer`."""

    def __init__(self, secret_key: str, sep: str = ".") -> None:
        self.secret_key = secret_key.encode("utf-8")
        self.sep = sep

    def get_signature(self, value: bytes) -> str:
        digest = hmac.new(self.secret_key, msg=value, digestmod=hashlib.sha256).digest()
        return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")

    def sign(self, value: bytes) -> bytes:
        signature = self.get_signature(value)
        return self.sep.join([value.decode("utf-8"), signature]).encode("utf-8")

    def unsign(self, signed_value: bytes) -> bytes:
        try:
            value_str, signature = signed_value.decode("utf-8").rsplit(self.sep, 1)
        except ValueError as exc:  # pragma: no cover - defensive
            raise BadSignature("Malformed signed value") from exc

        expected = self.get_signature(value_str.encode("utf-8"))
        if not hmac.compare_digest(signature, expected):
            raise BadSignature("Invalid signature")
        return value_str.encode("utf-8")


__all__ = ["Signer", "BadSignature"]
