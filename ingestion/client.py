"""HTTP transport for NHL's public JSON APIs.

The client deliberately uses the standard library.  A cache can be supplied by
the application via ``cache_get``/``cache_put`` without coupling ingestion to a
particular database or object-store implementation.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class RawResponseMetadata:
    url: str
    status: int
    headers: Mapping[str, str]
    retrieved_at: str
    attempts: int
    sha256: str
    from_cache: bool = False


class NHLAPIError(RuntimeError):
    """An HTTP, transport, or malformed-response error from an NHL API."""

    def __init__(self, message: str, *, url: str, status: int | None = None, body: str = ""):
        super().__init__(message)
        self.url = url
        self.status = status
        self.body = body[:1000]


CacheGet = Callable[[str], tuple[bytes, RawResponseMetadata] | bytes | None]
CachePut = Callable[[str, bytes, RawResponseMetadata], None]


def _query_value(value: Any) -> str:
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, separators=(",", ":"), sort_keys=True)
    return str(value)


class NHLHTTPClient:
    """Resilient JSON GET client for ``api.nhle.com`` and ``api-web.nhle.com``."""

    def __init__(
        self,
        base_url: str = "https://api.nhle.com/stats/rest/en/",
        *,
        timeout: float = 30.0,
        retries: int = 3,
        backoff_seconds: float = 0.5,
        user_agent: str = "nhl-ai-take-home/1.0 (+https://www.nhl.com/)",
        opener: Callable[..., Any] = urlopen,
        sleep: Callable[[float], None] = time.sleep,
        cache_get: CacheGet | None = None,
        cache_put: CachePut | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/") + "/"
        self.timeout = timeout
        self.retries = max(0, retries)
        self.backoff_seconds = max(0.0, backoff_seconds)
        self.user_agent = user_agent
        self.opener = opener
        self.sleep = sleep
        self.cache_get = cache_get
        self.cache_put = cache_put

    def build_url(self, path: str, params: Mapping[str, Any] | None = None) -> str:
        clean_path = path.lstrip("/")
        # Endpoint modules may pass an absolute Stats REST path while this
        # client is already rooted at `/stats/rest/en/`.
        if clean_path.startswith("stats/rest/en/") and self.base_url.endswith("/stats/rest/en/"):
            url = urljoin(self.base_url, "/" + clean_path)
        else:
            url = urljoin(self.base_url, clean_path)
        if params:
            query = urlencode([(key, _query_value(value)) for key, value in params.items()])
            url = f"{url}?{query}"
        return url

    def get_json(
        self,
        path: str,
        params: Mapping[str, Any] | None = None,
        *,
        cache_key: str | None = None,
    ) -> tuple[dict[str, Any], RawResponseMetadata]:
        url = self.build_url(path, params)
        key = cache_key or url
        if self.cache_get:
            cached = self.cache_get(key)
            if cached is not None:
                if isinstance(cached, tuple):
                    payload, metadata = cached
                else:
                    payload, metadata = cached, RawResponseMetadata(
                        url=url, status=200, headers={}, retrieved_at="", attempts=0,
                        sha256=hashlib.sha256(cached).hexdigest(), from_cache=True,
                    )
                return self._decode(payload, url), RawResponseMetadata(
                    url=metadata.url, status=metadata.status, headers=metadata.headers,
                    retrieved_at=metadata.retrieved_at, attempts=metadata.attempts,
                    sha256=metadata.sha256, from_cache=True,
                )

        last_error: Exception | None = None
        for attempt in range(1, self.retries + 2):
            request = Request(url, headers={"Accept": "application/json", "User-Agent": self.user_agent})
            try:
                with self.opener(request, timeout=self.timeout) as response:
                    body = response.read()
                    status = int(getattr(response, "status", 200))
                    headers = {str(k): str(v) for k, v in response.headers.items()}
                metadata = RawResponseMetadata(
                    url=url,
                    status=status,
                    headers=headers,
                    retrieved_at=datetime.now(timezone.utc).isoformat(),
                    attempts=attempt,
                    sha256=hashlib.sha256(body).hexdigest(),
                )
                decoded = self._decode(body, url)
                if self.cache_put:
                    self.cache_put(key, body, metadata)
                return decoded, metadata
            except HTTPError as exc:
                last_error = exc
                retryable = exc.code == 429 or 500 <= exc.code < 600
                if not retryable or attempt > self.retries:
                    body = exc.read().decode("utf-8", "replace")
                    raise NHLAPIError(f"NHL API returned HTTP {exc.code}", url=url, status=exc.code, body=body) from exc
                retry_after = exc.headers.get("Retry-After") if exc.headers else None
                self._wait(attempt, retry_after)
            except (URLError, TimeoutError, OSError) as exc:
                last_error = exc
                if attempt > self.retries:
                    raise NHLAPIError(f"NHL API request failed: {exc}", url=url) from exc
                self._wait(attempt, None)
        raise NHLAPIError(f"NHL API request failed: {last_error}", url=url) from last_error

    @staticmethod
    def _decode(body: bytes, url: str) -> dict[str, Any]:
        try:
            value = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise NHLAPIError("NHL API returned invalid JSON", url=url, body=body.decode("utf-8", "replace")) from exc
        if not isinstance(value, dict):
            raise NHLAPIError("NHL API returned a non-object JSON document", url=url)
        return value

    def _wait(self, attempt: int, retry_after: str | None) -> None:
        delay = None
        if retry_after:
            try:
                delay = max(0.0, float(retry_after))
            except ValueError:
                try:
                    target = parsedate_to_datetime(retry_after)
                    delay = max(0.0, (target - datetime.now(target.tzinfo)).total_seconds())
                except (TypeError, ValueError, OverflowError):
                    delay = None
        self.sleep(min(delay if delay is not None else self.backoff_seconds * (2 ** (attempt - 1)), 30.0))
