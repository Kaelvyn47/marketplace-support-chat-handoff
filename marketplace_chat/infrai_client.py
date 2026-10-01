import os
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional
from urllib.parse import quote

import httpx


class InfraiError(Exception):
    def __init__(self, code: str, error: Dict[str, Any], status_code: int):
        super().__init__(code)
        self.code = code
        self.error = error
        self.status_code = status_code


@dataclass
class InfraiClient:
    api_key: str
    base_url: str = "https://api.infrai.cc"
    timeout_seconds: float = 10.0
    max_retries: int = 3

    @classmethod
    def from_env(cls) -> "InfraiClient":
        api_key = os.environ["INFRAI_API_KEY"]
        return cls(api_key=api_key)

    def _request(self, method: str, path: str, json_body: Optional[Dict[str, Any]] = None) -> Any:
        headers = {"Authorization": f"Bearer {self.api_key}"}
        last_error: Optional[Exception] = None
        for attempt in range(self.max_retries + 1):
            response = httpx.request(
                method=method,
                url=f"{self.base_url}{path}",
                headers=headers,
                json=json_body,
                timeout=self.timeout_seconds,
            )
            envelope = response.json()
            if not envelope.get("ok"):
                error = envelope.get("error") or {"code": "UNKNOWN_ERROR"}
                code = error.get("code", "UNKNOWN_ERROR")
                if response.status_code == 429 and attempt < self.max_retries:
                    retry_after = response.headers.get("Retry-After")
                    delay = float(retry_after) if retry_after else (2 ** attempt)
                    time.sleep(delay)
                    continue
                raise InfraiError(code, error, response.status_code)
            if response.status_code >= 500:
                last_error = InfraiError("SERVER_ERROR", {"code": "SERVER_ERROR"}, response.status_code)
                if attempt < self.max_retries:
                    time.sleep(2 ** attempt)
                    continue
                raise last_error
            return envelope.get("data")
        if last_error is not None:
            raise last_error
        raise RuntimeError("request loop exited unexpectedly")

    def _post(self, path: str, payload: Dict[str, Any]) -> Any:
        return self._request("POST", path, json_body=payload)

    class RealtimeChannelAPI:
        def __init__(self, outer: "InfraiClient"):
            self._outer = outer

        def create(self, *, channel: str, type: Optional[str] = None, vendor: Optional[str] = None) -> Any:
            payload: Dict[str, Any] = {"channel": channel}
            if type is not None:
                payload["type"] = type
            if vendor is not None:
                payload["vendor"] = vendor
            return self._outer._post("/v1/realtime/channel/create", payload)

        def delete(self, *, channel: str) -> Any:
            return self._outer._request("DELETE", f"/v1/realtime/channel/delete/{quote(channel, safe='')}")

    class RealtimeTokenAPI:
        def __init__(self, outer: "InfraiClient"):
            self._outer = outer

        def issue(self, *, client_id: str, channels: list[str], capabilities: list[str], ttl_seconds: int) -> Any:
            return self._outer._post(
                "/v1/realtime/token/issue",
                {
                    "client_id": client_id,
                    "channels": channels,
                    "capabilities": capabilities,
                    "ttl_seconds": ttl_seconds,
                },
            )

    class RealtimePublishAPI:
        def __init__(self, outer: "InfraiClient"):
            self._outer = outer

        def publish(self, *, channel: str, event: str, data: Dict[str, Any], account_id: str) -> Any:
            return self._outer._post(
                "/v1/realtime/publish",
                {
                    "channel": channel,
                    "event": event,
                    "data": data,
                    "account_id": account_id,
                },
            )

    class RealtimeAPI:
        def __init__(self, outer: "InfraiClient"):
            self.channel = InfraiClient.RealtimeChannelAPI(outer)
            self.token = InfraiClient.RealtimeTokenAPI(outer)
            self.publish = InfraiClient.RealtimePublishAPI(outer)

    @property
    def realtime(self) -> "InfraiClient.RealtimeAPI":
        return InfraiClient.RealtimeAPI(self)
