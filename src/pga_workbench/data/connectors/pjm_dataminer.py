from __future__ import annotations

import json
import os
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

HttpGet = Callable[[str, dict[str, str], float], dict[str, Any]]


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
    ) -> None:
        super().__init__(id="pjm_dataminer", kind="iso_api")
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
        payload = self.http_get(self.metadata_url(feed), self._headers(), self.timeout_seconds)
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
            payload = self.http_get(self._url(feed, query), self._headers(), self.timeout_seconds)
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
