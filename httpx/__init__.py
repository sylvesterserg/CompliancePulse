"""Minimal subset of the httpx API for offline testing."""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, List, Optional


@dataclass
class Response:
    status_code: int
    _body: bytes

    def json(self) -> Any:
        return json.loads(self._body.decode())

    def raise_for_status(self) -> None:
        if not (200 <= self.status_code < 400):
            raise RuntimeError(f"Request failed with status code {self.status_code}")


class AsyncClient:
    def __init__(self, *, app: Callable[..., Awaitable[Any]], base_url: str):
        self.app = app
        self.base_url = base_url
        self._started = False

    async def __aenter__(self) -> "AsyncClient":
        await self._startup()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self._shutdown()

    async def _startup(self) -> None:
        if self._started:
            return
        if hasattr(self.app, "router"):
            await self.app.router.startup()  # type: ignore[attr-defined]
        self._started = True

    async def _shutdown(self) -> None:
        if not self._started:
            return
        if hasattr(self.app, "router"):
            await self.app.router.shutdown()  # type: ignore[attr-defined]
        self._started = False

    async def post(self, path: str, *, json: Optional[Dict[str, Any]] = None) -> Response:
        return await self._request("POST", path, json=json)

    async def get(self, path: str) -> Response:
        return await self._request("GET", path)

    async def _request(self, method: str, path: str, *, json: Optional[Dict[str, Any]] = None) -> Response:
        body_bytes: Optional[bytes] = None
        headers: List[tuple[bytes, bytes]] = []
        if json is not None:
            body_bytes = json_lib_dumps(json).encode()
            headers.append((b"content-type", b"application/json"))

        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "method": method,
            "scheme": "http",
            "path": path,
            "query_string": b"",
            "headers": headers,
        }

        response_start: Dict[str, Any] | None = None
        response_body = bytearray()

        async def receive() -> Dict[str, Any]:
            nonlocal body_bytes
            if body_bytes is not None:
                chunk = body_bytes
                body_bytes = None
                return {"type": "http.request", "body": chunk, "more_body": False}
            await asyncio.sleep(0)
            return {"type": "http.disconnect"}

        async def send(message: Dict[str, Any]) -> None:
            nonlocal response_start, response_body
            if message["type"] == "http.response.start":
                response_start = message
            elif message["type"] == "http.response.body":
                response_body.extend(message.get("body", b""))

        await self.app(scope, receive, send)

        if response_start is None:
            raise RuntimeError("Application did not send a response start event")

        status_code = response_start.get("status", 500)
        return Response(status_code=status_code, _body=bytes(response_body))


def json_lib_dumps(data: Any) -> str:
    return json.dumps(data)


__all__ = ["AsyncClient", "Response"]
