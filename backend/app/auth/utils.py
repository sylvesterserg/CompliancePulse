from __future__ import annotations

import json
import secrets
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Dict, Optional

from .password_hasher import PasswordHasher, VerifyMismatchError
from .signing import BadSignature, Signer


_hasher = PasswordHasher()


@dataclass
class SessionData:
    """Represents state tracked for a browser session."""

    user_id: Optional[int]
    organization_id: Optional[int]
    csrf_token: str
    created_at: datetime
    expires_at: datetime

    def touch(self, ttl_seconds: int) -> None:
        self.expires_at = datetime.utcnow() + timedelta(seconds=ttl_seconds)

    @property
    def is_authenticated(self) -> bool:
        return self.user_id is not None

    def to_json(self) -> str:
        payload = asdict(self)
        payload["created_at"] = self.created_at.isoformat()
        payload["expires_at"] = self.expires_at.isoformat()
        return json.dumps(payload)

    @classmethod
    def from_json(cls, payload: str) -> "SessionData":
        data: Dict[str, str] = json.loads(payload)
        return cls(
            user_id=data.get("user_id"),
            organization_id=data.get("organization_id"),
            csrf_token=data["csrf_token"],
            created_at=datetime.fromisoformat(data["created_at"]),
            expires_at=datetime.fromisoformat(data["expires_at"]),
        )


class _MemoryBackend:
    def __init__(self) -> None:
        self._store: Dict[str, str] = {}

    def read(self, key: str) -> Optional[str]:
        return self._store.get(key)

    def write(self, key: str, value: str, ttl_seconds: int) -> None:
        self._store[key] = value

    def delete(self, key: str) -> None:
        self._store.pop(key, None)


class _RedisBackend:
    def __init__(self, url: str) -> None:
        import redis

        self.client = redis.Redis.from_url(url, decode_responses=True)

    def read(self, key: str) -> Optional[str]:
        return self.client.get(key)

    def write(self, key: str, value: str, ttl_seconds: int) -> None:
        self.client.set(name=key, value=value, ex=ttl_seconds)

    def delete(self, key: str) -> None:
        self.client.delete(key)


class SessionStore:
    """Manages secure cookie-backed sessions with pluggable storage."""

    def __init__(self, secret: str, default_ttl: int = 86400, backend: str = "memory", redis_url: str | None = None):
        self.default_ttl = default_ttl
        self.signer = Signer(secret)
        if backend == "redis" and redis_url:
            self.backend = _RedisBackend(redis_url)
        else:
            self.backend = _MemoryBackend()

    def _serialize(self, data: SessionData) -> str:
        return data.to_json()

    def _deserialize(self, payload: str) -> SessionData:
        return SessionData.from_json(payload)

    def _generate_session_id(self) -> str:
        return secrets.token_urlsafe(32)

    def _generate_csrf(self) -> str:
        return secrets.token_urlsafe(32)

    def create(self, user_id: int | None = None, organization_id: int | None = None) -> tuple[str, SessionData]:
        session_id = self._generate_session_id()
        data = SessionData(
            user_id=user_id,
            organization_id=organization_id,
            csrf_token=self._generate_csrf(),
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(seconds=self.default_ttl),
        )
        self.backend.write(session_id, self._serialize(data), self.default_ttl)
        return session_id, data

    def save(self, session_id: str, data: SessionData) -> None:
        self.backend.write(session_id, self._serialize(data), self.default_ttl)

    def get(self, session_id: str, *, touch: bool = True) -> Optional[SessionData]:
        payload = self.backend.read(session_id)
        if not payload:
            return None
        data = self._deserialize(payload)
        if data.expires_at < datetime.utcnow():
            self.destroy(session_id)
            return None
        if touch:
            data.touch(self.default_ttl)
            self.save(session_id, data)
        return data

    def destroy(self, session_id: str) -> None:
        self.backend.delete(session_id)

    def rotate_csrf(self, session_id: str, data: SessionData) -> str:
        data.csrf_token = self._generate_csrf()
        self.save(session_id, data)
        return data.csrf_token

    def sign(self, session_id: str) -> str:
        return self.signer.sign(session_id.encode()).decode()

    def unsign(self, signed_value: str) -> Optional[str]:
        try:
            return self.signer.unsign(signed_value.encode()).decode()
        except BadSignature:
            return None


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    try:
        return _hasher.verify(hashed, password)
    except VerifyMismatchError:
        return False


def slugify(value: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in value)
    collapsed = "-".join(filter(None, cleaned.split("-")))
    return collapsed or secrets.token_hex(4)
