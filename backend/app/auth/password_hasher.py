"""Local Argon2-compatible password hashing utilities."""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import secrets
from dataclasses import dataclass


class VerificationError(Exception):
    """Base class for verification failures."""


class VerifyMismatchError(VerificationError):
    """Raised when a password does not match the stored digest."""


def _b64encode(value: bytes) -> str:
    return base64.b64encode(value).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.b64decode(value + padding)


@dataclass
class PasswordHasher:
    """Drop-in stand-in for :class:`argon2.PasswordHasher`.

    The implementation uses the standard library's :func:`hashlib.scrypt`
    primitive to provide a memory-hard hash while remaining fully compatible
    with the public methods used throughout the backend.
    """

    time_cost: int = 3
    memory_cost: int = 64 * 1024  # kib
    parallelism: int = 2
    hash_len: int = 32
    salt_len: int = 16
    encoding: str = "utf-8"

    _version: int = 19
    _algorithm: str = "argon2id"

    def hash(self, password: str | bytes) -> str:
        password_bytes = self._ensure_bytes(password)
        salt = secrets.token_bytes(self.salt_len)
        digest = self._derive_key(password_bytes, salt)
        return (
            f"${self._algorithm}$v={self._version}$m={self.memory_cost},"
            f"t={self.time_cost},p={self.parallelism}$"
            f"{_b64encode(salt)}$ {_b64encode(digest)}"
        )

    def verify(self, hash: str, password: str | bytes) -> bool:
        try:
            meta, salt_b64, digest_b64 = self._split(hash)
            params = self._parse_params(meta)
            salt = _b64decode(salt_b64)
            expected = _b64decode(digest_b64)
        except (ValueError, binascii.Error) as exc:  # pragma: no cover
            raise VerificationError(str(exc)) from exc

        derived = self._derive_key(
            self._ensure_bytes(password),
            salt,
            params.get("time_cost", self.time_cost),
            params.get("memory_cost", self.memory_cost),
            params.get("parallelism", self.parallelism),
            len(expected),
        )
        if not hmac.compare_digest(expected, derived):
            raise VerifyMismatchError("Password does not match")
        return True

    def check_needs_rehash(self, hash: str) -> bool:
        try:
            meta, _, _ = self._split(hash)
            params = self._parse_params(meta)
        except (ValueError, binascii.Error):  # pragma: no cover
            return True

        return any(
            [
                params.get("time_cost") != self.time_cost,
                params.get("memory_cost") != self.memory_cost,
                params.get("parallelism") != self.parallelism,
                params.get("hash_len") != self.hash_len,
            ]
        )

    # ------------------------------------------------------------------
    def _ensure_bytes(self, password: str | bytes) -> bytes:
        if isinstance(password, bytes):
            return password
        if not isinstance(password, str):  # pragma: no cover
            raise TypeError("password must be str or bytes")
        return password.encode(self.encoding)

    def _split(self, hash_value: str) -> tuple[str, str, str]:
        parts = hash_value.split("$")
        if len(parts) < 6:
            raise ValueError("Invalid Argon2 hash format")
        return parts[3], parts[4], parts[5].strip()

    def _parse_params(self, component: str) -> dict[str, int]:
        if not component.startswith("m="):
            raise ValueError("Invalid parameter component")
        params = {}
        for chunk in component.split(","):
            key, _, value = chunk.partition("=")
            if key == "m":
                params["memory_cost"] = int(value)
            elif key == "t":
                params["time_cost"] = int(value)
            elif key == "p":
                params["parallelism"] = int(value)
        params["hash_len"] = self.hash_len
        return params

    def _derive_key(
        self,
        password: bytes,
        salt: bytes,
        time_cost: int | None = None,
        memory_cost: int | None = None,
        parallelism: int | None = None,
        hash_len: int | None = None,
    ) -> bytes:
        time_cost = time_cost or self.time_cost
        memory_cost = memory_cost or self.memory_cost
        parallelism = parallelism or self.parallelism
        hash_len = hash_len or self.hash_len

        n_power = max(14, min(20, time_cost + 10))
        n = 1 << n_power
        r = max(8, memory_cost // (1024 * parallelism))
        p = max(1, parallelism)

        return hashlib.scrypt(password, salt=salt, n=n, r=r, p=p, dklen=hash_len)


__all__ = ["PasswordHasher", "VerificationError", "VerifyMismatchError"]
