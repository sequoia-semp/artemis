from __future__ import annotations

import json
import os
import threading
import time
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from ...exceptions import WorkbenchException
from ..contracts import DataRequest, DataResult
from .base import DataConnector

PJM_DATAMINER_AUTH_MISSING = "PJM_DATAMINER_AUTH_MISSING"
PJM_DATAMINER_ERROR = "PJM_DATAMINER_ERROR"
PJM_DATAMINER_POLICY_ERROR = "PJM_DATAMINER_POLICY_ERROR"
PJM_DATAMINER_MAX_ROW_COUNT = 50000
PJM_DATAMINER_DEFAULT_MAX_PAGES = 1
PJM_DATAMINER_CONNECTION_LIMITS_PER_MINUTE = {
    "non_member": 6,
    "member": 600,
}
PJM_DATAMINER_DEFAULT_MAX_RETRY_ATTEMPTS = 3

HttpGet = Callable[[str, dict[str, str], float], dict[str, Any]]
Clock = Callable[[], float]
Sleep = Callable[[float], None]


class PjmDataMinerRetryAfter(Exception):
    def __init__(self, retry_after_seconds: float, message: str = "PJM Data Miner throttled request") -> None:
        super().__init__(message)
        self.retry_after_seconds = float(retry_after_seconds)


class PjmDataMinerTokenBucket:
    def __init__(
        self,
        max_connections_per_minute: int,
        *,
        clock: Clock | None = None,
        sleep: Sleep | None = None,
        capacity: int | None = None,
    ) -> None:
        if max_connections_per_minute < 1:
            raise WorkbenchException(PJM_DATAMINER_POLICY_ERROR, "PJM Data Miner token bucket limit must be positive")
        self.max_connections_per_minute = int(max_connections_per_minute)
        self.capacity = int(capacity or max_connections_per_minute)
        if self.capacity < 1:
            raise WorkbenchException(PJM_DATAMINER_POLICY_ERROR, "PJM Data Miner token bucket capacity must be positive")
        self._clock = clock or time.monotonic
        self._sleep = sleep or time.sleep
        self._lock = threading.Lock()
        self._tokens = float(self.capacity)
        self._last_refill = self._clock()

    @property
    def refill_rate_per_second(self) -> float:
        return self.max_connections_per_minute / 60.0

    def acquire(self) -> float:
        total_slept = 0.0
        while True:
            with self._lock:
                now = self._clock()
                elapsed = max(0.0, now - self._last_refill)
                self._tokens = min(float(self.capacity), self._tokens + elapsed * self.refill_rate_per_second)
                self._last_refill = now
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return total_slept
                wait_seconds = (1.0 - self._tokens) / self.refill_rate_per_second
            self._sleep(wait_seconds)
            total_slept += wait_seconds


_SHARED_RATE_LIMITERS: dict[tuple[str, int], PjmDataMinerTokenBucket] = {}
_SHARED_RATE_LIMITERS_LOCK = threading.Lock()


def shared_pjm_dataminer_rate_limiter(account_class: str, max_connections_per_minute: int) -> PjmDataMinerTokenBucket:
    key = (str(account_class), int(max_connections_per_minute))
    with _SHARED_RATE_LIMITERS_LOCK:
        limiter = _SHARED_RATE_LIMITERS.get(key)
        if limiter is None:
            limiter = PjmDataMinerTokenBucket(max_connections_per_minute)
            _SHARED_RATE_LIMITERS[key] = limiter
        return limiter


def _default_http_get(url: str, headers: dict[str, str], timeout: float) -> dict[str, Any]:
    request_headers = {
        "Accept": "application/json",
        "User-Agent": "artemis-pjm-workbench/0.2",
        **headers,
    }
    request = Request(url, headers=request_headers)
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except HTTPError as exc:
        if exc.code == 429:
            retry_after = _retry_after_seconds(exc.headers.get("Retry-After") if exc.headers else None)
            raise PjmDataMinerRetryAfter(retry_after, f"PJM Data Miner HTTP 429: retry after {retry_after:g} seconds") from exc
        raw_error = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw_error)
        except json.JSONDecodeError:
            payload = {}
        message = payload.get("message") if isinstance(payload, dict) else None
        raise WorkbenchException(PJM_DATAMINER_ERROR, f"PJM Data Miner HTTP {exc.code}: {message or exc.reason}") from exc
    except URLError as exc:
        raise WorkbenchException(PJM_DATAMINER_ERROR, f"PJM Data Miner request failed: {exc.reason}") from exc
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise WorkbenchException(PJM_DATAMINER_ERROR, "PJM Data Miner response must be a JSON object")
    return payload


def _records_from_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if payload.get("errors") or (payload.get("code") and payload.get("message")):
        message = str(payload.get("message") or "PJM Data Miner returned an error payload")
        raise WorkbenchException(PJM_DATAMINER_ERROR, message)
    for key in ["items", "Items", "data", "Data", "value", "Value"]:
        records = payload.get(key)
        if isinstance(records, list):
            return [dict(item) for item in records if isinstance(item, dict)]
    if all(not isinstance(value, list) for value in payload.values()):
        return [dict(payload)]
    raise WorkbenchException(PJM_DATAMINER_ERROR, "PJM Data Miner response did not contain a recognized records array")


def _total_rows(payload: dict[str, Any]) -> int | None:
    for key in ["totalRows", "TotalRows", "total_rows", "totalRowCount"]:
        value = payload.get(key)
        if value is None:
            continue
        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            raise WorkbenchException(PJM_DATAMINER_ERROR, f"Invalid PJM Data Miner total rows value: {value!r}") from exc
    return None


class PjmDataMinerConnector(DataConnector):
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        definition_base_url: str | None = None,
        http_get: HttpGet | None = None,
        timeout_seconds: float = 30.0,
        account_class: str | None = None,
        max_connections_per_minute: int | None = None,
        max_row_count: int = PJM_DATAMINER_MAX_ROW_COUNT,
        default_max_pages: int = PJM_DATAMINER_DEFAULT_MAX_PAGES,
        rate_limiter: PjmDataMinerTokenBucket | None = None,
        retry_sleep: Sleep | None = None,
        max_retry_attempts: int = PJM_DATAMINER_DEFAULT_MAX_RETRY_ATTEMPTS,
    ) -> None:
        super().__init__(id="pjm_dataminer", kind="iso_api")
        uses_default_http_get = http_get is None
        self.api_key = api_key or os.environ.get("ARTEMIS_PJM_API_KEY")
        self.base_url = (base_url or os.environ.get("ARTEMIS_PJM_API_BASE_URL") or "https://api.pjm.com/api/v1").rstrip("/")
        self.definition_base_url = (
            definition_base_url or os.environ.get("ARTEMIS_PJM_DATAMINER_DEFINITION_BASE_URL") or "https://dataminer2.pjm.com"
        ).rstrip("/")
        self.http_get = http_get or _default_http_get
        self.timeout_seconds = timeout_seconds
        self.account_class = (account_class or os.environ.get("ARTEMIS_PJM_ACCOUNT_CLASS") or "non_member").lower()
        self.max_connections_per_minute = max_connections_per_minute or _env_positive_int("ARTEMIS_PJM_MAX_CONNECTIONS_PER_MINUTE")
        self.max_row_count = int(max_row_count)
        self.default_max_pages = int(default_max_pages)
        self.rate_limiter = rate_limiter
        if self.rate_limiter is None and uses_default_http_get:
            self.rate_limiter = shared_pjm_dataminer_rate_limiter(self.account_class, self._connection_limit())
        self.retry_sleep = retry_sleep or time.sleep
        self.max_retry_attempts = int(max_retry_attempts)
        if self.max_retry_attempts < 0:
            raise WorkbenchException(PJM_DATAMINER_POLICY_ERROR, "PJM Data Miner max retry attempts must not be negative")

    def available(self) -> bool:
        return bool(self.api_key)

    def _headers(self) -> dict[str, str]:
        if not self.api_key:
            raise WorkbenchException(PJM_DATAMINER_AUTH_MISSING, "ARTEMIS_PJM_API_KEY is required for live PJM Data Miner requests")
        return {"Ocp-Apim-Subscription-Key": self.api_key}

    def _url(self, feed: str, query: dict[str, Any]) -> str:
        cleaned = {key: value for key, value in query.items() if value is not None}
        suffix = f"?{urlencode(cleaned)}" if cleaned else ""
        return f"{self.base_url}/{feed}{suffix}"

    def definition_url(self, feed: str) -> str:
        if not feed or "/" in feed or "?" in feed:
            raise WorkbenchException(PJM_DATAMINER_ERROR, "PJM Data Miner feed name is required for definition URLs")
        return f"{self.definition_base_url}/feed/{feed}/definition"

    def metadata_url(self, feed: str) -> str:
        if not feed or "/" in feed or "?" in feed:
            raise WorkbenchException(PJM_DATAMINER_ERROR, "PJM Data Miner feed name is required for metadata URLs")
        return f"{self.base_url}/{feed}/metadata"

    def fetch_definition(self, feed: str) -> dict[str, Any]:
        payload = self._request_json(self.metadata_url(feed))
        if payload.get("errors") or (payload.get("code") and payload.get("message")):
            message = str(payload.get("message") or "PJM Data Miner returned a definition error payload")
            raise WorkbenchException(PJM_DATAMINER_ERROR, message)
        return payload

    def _connection_limit(self) -> int:
        if self.max_connections_per_minute is not None:
            if self.max_connections_per_minute < 1:
                raise WorkbenchException(PJM_DATAMINER_POLICY_ERROR, "PJM Data Miner max connections per minute must be positive")
            return self.max_connections_per_minute
        try:
            return PJM_DATAMINER_CONNECTION_LIMITS_PER_MINUTE[self.account_class]
        except KeyError as exc:
            allowed = ", ".join(sorted(PJM_DATAMINER_CONNECTION_LIMITS_PER_MINUTE))
            raise WorkbenchException(PJM_DATAMINER_POLICY_ERROR, f"Unknown PJM account class {self.account_class!r}; expected one of {allowed}") from exc

    def _acquire_rate_limit(self) -> float:
        if self.rate_limiter is None:
            return 0.0
        return self.rate_limiter.acquire()

    def _request_json(self, url: str) -> dict[str, Any]:
        attempt = 0
        while True:
            self._acquire_rate_limit()
            try:
                return self.http_get(url, self._headers(), self.timeout_seconds)
            except PjmDataMinerRetryAfter as exc:
                if attempt >= self.max_retry_attempts:
                    raise WorkbenchException(
                        PJM_DATAMINER_ERROR,
                        f"PJM Data Miner throttled request exceeded retry budget after {attempt} retries",
                    ) from exc
                delay = exc.retry_after_seconds * (2**attempt)
                self.retry_sleep(delay)
                attempt += 1

    def _planned_max_pages(self, parameters: dict[str, Any], paginate: bool) -> int:
        raw = parameters.get("max_pages")
        max_pages = self.default_max_pages if raw is None else int(raw)
        if max_pages < 1:
            raise WorkbenchException(PJM_DATAMINER_POLICY_ERROR, "Unbounded PJM Data Miner pagination is not allowed")
        if paginate and max_pages > self._connection_limit():
            raise WorkbenchException(
                PJM_DATAMINER_POLICY_ERROR,
                f"PJM Data Miner request plans {max_pages} pages but the {self.account_class} connection budget is {self._connection_limit()} per minute",
            )
        return max_pages

    def fetch(self, request: DataRequest) -> DataResult:
        feed = str(request.parameters.get("feed") or request.contract)
        if not feed:
            raise WorkbenchException(PJM_DATAMINER_ERROR, "PJM Data Miner feed is required")
        query = dict(request.parameters.get("query") or {})
        row_count = _query_int(query, "rowCount", "rowcount", default=50000)
        start_row = _query_int(query, "startRow", "startrow", default=1)
        if row_count < 1 or row_count > self.max_row_count:
            raise WorkbenchException(PJM_DATAMINER_POLICY_ERROR, f"PJM Data Miner rowCount must be between 1 and {self.max_row_count}")
        if start_row < 1:
            raise WorkbenchException(PJM_DATAMINER_POLICY_ERROR, "PJM Data Miner startRow is one-based and must be at least 1")
        query["rowCount"] = row_count
        query["startRow"] = start_row
        records: list[dict[str, Any]] = []
        total_rows: int | None = None
        paginate = bool(request.parameters.get("paginate", True))
        max_pages = self._planned_max_pages(dict(request.parameters), paginate)
        page_count = 0

        while True:
            page_count += 1
            query["startRow"] = start_row
            payload = self._request_json(self._url(feed, query))
            page = _records_from_payload(payload)
            records.extend(page)
            total_rows = _total_rows(payload) if total_rows is None else total_rows
            if not paginate or page_count >= max_pages or total_rows is None or len(records) >= total_rows or not page:
                break
            start_row += row_count

        truncated_by_max_pages = bool(paginate and total_rows is not None and len(records) < total_rows and page_count >= max_pages)

        return DataResult(
            source="PJM Data Miner",
            contract=request.contract,
            data_environment=str(request.parameters.get("data_environment") or "production"),
            records=records,
            lineage={
                "connector_id": self.id,
                "feed": feed,
                "base_url": self.base_url,
                "row_count": len(records),
                "total_rows": total_rows,
                "page_count": page_count,
                "max_pages": max_pages,
                "truncated_by_max_pages": truncated_by_max_pages,
                "account_class": self.account_class,
                "max_connections_per_minute": self._connection_limit(),
                "runtime_rate_limiter_enabled": self.rate_limiter is not None,
                "max_retry_attempts": self.max_retry_attempts,
                "max_row_count": self.max_row_count,
            },
        )


def _env_positive_int(name: str) -> int | None:
    value = os.environ.get(name)
    if value in (None, ""):
        return None
    parsed = int(value)
    if parsed < 1:
        raise WorkbenchException(PJM_DATAMINER_POLICY_ERROR, f"{name} must be positive")
    return parsed


def _query_int(query: dict[str, Any], primary: str, alternate: str, default: int) -> int:
    value = query.get(primary)
    if value is None:
        value = query.get(alternate)
    if value is None:
        value = default
    return int(value)


def _retry_after_seconds(value: Any) -> float:
    if value in (None, ""):
        return 1.0
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return 1.0
    return max(0.0, parsed)
