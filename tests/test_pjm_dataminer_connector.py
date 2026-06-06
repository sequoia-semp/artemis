from __future__ import annotations

import os

import pytest

from pga_workbench.data.connectors.pjm_dataminer import (
    PJM_DATAMINER_AUTH_MISSING,
    PJM_DATAMINER_ERROR,
    PJM_DATAMINER_POLICY_ERROR,
    PjmDataMinerConnector,
    PjmDataMinerRetryAfter,
    PjmDataMinerTokenBucket,
    shared_pjm_dataminer_rate_limiter,
)
from pga_workbench.data.contracts import DataRequest
from pga_workbench.exceptions import WorkbenchException


def test_pjm_dataminer_connector_builds_header_url_and_paginates(monkeypatch):
    monkeypatch.delenv("ARTEMIS_PJM_API_KEY", raising=False)
    calls = []

    def fake_get(url, headers, timeout):
        calls.append((url, headers, timeout))
        if "startRow=1" in url:
            return {"items": [{"row": 1}], "totalRows": 2}
        return {"items": [{"row": 2}], "totalRows": 2}

    connector = PjmDataMinerConnector(api_key="test-key", base_url="https://example.test/api/v1", http_get=fake_get)
    result = connector.fetch(
        DataRequest(
            contract="load_frcstd_7_day",
            parameters={"feed": "load_frcstd_7_day", "query": {"rowCount": 1, "startRow": 1, "format": "json"}, "max_pages": 2},
        )
    )

    assert [item["row"] for item in result.records] == [1, 2]
    assert calls[0][0].startswith("https://example.test/api/v1/load_frcstd_7_day?")
    assert "subscription-key" not in calls[0][0].lower()
    assert calls[0][1] == {"Ocp-Apim-Subscription-Key": "test-key"}
    assert result.lineage["row_count"] == 2
    assert result.lineage["page_count"] == 2


def test_pjm_dataminer_connector_can_fetch_single_page(monkeypatch):
    monkeypatch.delenv("ARTEMIS_PJM_API_KEY", raising=False)
    calls = []

    def fake_get(url, headers, timeout):
        calls.append(url)
        return {"items": [{"row": 1}], "totalRows": 100}

    result = PjmDataMinerConnector(api_key="test-key", http_get=fake_get).fetch(
        DataRequest(
            contract="load_frcstd_7_day",
            parameters={"feed": "load_frcstd_7_day", "query": {"rowCount": 1, "startRow": 1}, "paginate": False},
        )
    )

    assert result.records == [{"row": 1}]
    assert len(calls) == 1
    assert result.lineage["page_count"] == 1


def test_pjm_dataminer_connector_requires_key(monkeypatch):
    monkeypatch.delenv("ARTEMIS_PJM_API_KEY", raising=False)
    connector = PjmDataMinerConnector(api_key=None, http_get=lambda *_: {"items": []})

    with pytest.raises(WorkbenchException) as exc:
        connector.fetch(DataRequest(contract="load_frcstd_7_day", parameters={"feed": "load_frcstd_7_day"}))

    assert exc.value.code == PJM_DATAMINER_AUTH_MISSING


def test_pjm_dataminer_connector_rejects_error_payload(monkeypatch):
    monkeypatch.delenv("ARTEMIS_PJM_API_KEY", raising=False)
    connector = PjmDataMinerConnector(
        api_key="test-key",
        http_get=lambda *_: {"code": "BadRequest", "message": "Invalid filter", "errors": [{"field": "datetime_beginning_utc"}]},
    )

    with pytest.raises(WorkbenchException) as exc:
        connector.fetch(DataRequest(contract="da_hrl_lmps", parameters={"feed": "da_hrl_lmps"}))

    assert exc.value.code == PJM_DATAMINER_ERROR
    assert "Invalid filter" in exc.value.message


def test_pjm_dataminer_connector_rejects_unexpected_non_list_envelope(monkeypatch):
    monkeypatch.delenv("ARTEMIS_PJM_API_KEY", raising=False)
    connector = PjmDataMinerConnector(
        api_key="test-key",
        http_get=lambda *_: {"row": 1, "totalRows": 1},
    )

    with pytest.raises(WorkbenchException) as exc:
        connector.fetch(DataRequest(contract="load_frcstd_7_day", parameters={"feed": "load_frcstd_7_day"}))

    assert exc.value.code == PJM_DATAMINER_ERROR
    assert "recognized records array" in exc.value.message


def test_pjm_dataminer_connector_reads_env_key(monkeypatch):
    monkeypatch.setenv("ARTEMIS_PJM_API_KEY", "env-key")
    seen_headers = []

    def fake_get(url, headers, timeout):
        seen_headers.append(headers)
        return {"items": []}

    PjmDataMinerConnector(http_get=fake_get).fetch(DataRequest(contract="load_frcstd_7_day", parameters={"feed": "load_frcstd_7_day"}))

    assert seen_headers == [{"Ocp-Apim-Subscription-Key": "env-key"}]
    assert os.environ["ARTEMIS_PJM_API_KEY"] == "env-key"


def test_pjm_dataminer_connector_defaults_to_one_bounded_page(monkeypatch):
    monkeypatch.delenv("ARTEMIS_PJM_API_KEY", raising=False)
    calls = []

    def fake_get(url, headers, timeout):
        calls.append(url)
        return {"items": [{"row": 1}], "totalRows": 100}

    result = PjmDataMinerConnector(api_key="test-key", http_get=fake_get).fetch(
        DataRequest(contract="load_frcstd_7_day", parameters={"feed": "load_frcstd_7_day", "query": {"rowCount": 1}})
    )

    assert result.records == [{"row": 1}]
    assert len(calls) == 1
    assert result.lineage["max_pages"] == 1
    assert result.lineage["truncated_by_max_pages"] is True
    assert result.lineage["account_class"] == "non_member"
    assert result.lineage["max_connections_per_minute"] == 6


def test_pjm_dataminer_connector_rejects_unbounded_pagination(monkeypatch):
    monkeypatch.delenv("ARTEMIS_PJM_API_KEY", raising=False)
    connector = PjmDataMinerConnector(api_key="test-key", http_get=lambda *_: {"items": []})

    with pytest.raises(WorkbenchException) as exc:
        connector.fetch(DataRequest(contract="load_frcstd_7_day", parameters={"feed": "load_frcstd_7_day", "max_pages": 0}))

    assert exc.value.code == PJM_DATAMINER_POLICY_ERROR


def test_pjm_dataminer_connector_rejects_row_count_and_start_row_policy_violations(monkeypatch):
    monkeypatch.delenv("ARTEMIS_PJM_API_KEY", raising=False)
    connector = PjmDataMinerConnector(api_key="test-key", http_get=lambda *_: {"items": []})

    with pytest.raises(WorkbenchException) as row_exc:
        connector.fetch(
            DataRequest(contract="load_frcstd_7_day", parameters={"feed": "load_frcstd_7_day", "query": {"rowCount": 50001}})
        )
    with pytest.raises(WorkbenchException) as start_exc:
        connector.fetch(
            DataRequest(contract="load_frcstd_7_day", parameters={"feed": "load_frcstd_7_day", "query": {"rowCount": 1, "startRow": 0}})
        )

    assert row_exc.value.code == PJM_DATAMINER_POLICY_ERROR
    assert start_exc.value.code == PJM_DATAMINER_POLICY_ERROR


def test_pjm_dataminer_connector_rejects_planned_pages_over_connection_budget(monkeypatch):
    monkeypatch.delenv("ARTEMIS_PJM_API_KEY", raising=False)
    connector = PjmDataMinerConnector(api_key="test-key", http_get=lambda *_: {"items": []})

    with pytest.raises(WorkbenchException) as exc:
        connector.fetch(
            DataRequest(
                contract="load_frcstd_7_day",
                parameters={"feed": "load_frcstd_7_day", "query": {"rowCount": 1}, "max_pages": 7},
            )
        )

    assert exc.value.code == PJM_DATAMINER_POLICY_ERROR
    assert "connection budget" in exc.value.message


def test_pjm_dataminer_connector_rejects_over_budget_rate_override(monkeypatch):
    monkeypatch.delenv("ARTEMIS_PJM_API_KEY", raising=False)
    connector = PjmDataMinerConnector(
        api_key="test-key",
        account_class="non_member",
        max_connections_per_minute=7,
        http_get=lambda *_: {"items": []},
    )

    with pytest.raises(WorkbenchException) as exc:
        connector.fetch(DataRequest(contract="load_frcstd_7_day", parameters={"feed": "load_frcstd_7_day"}))

    assert exc.value.code == PJM_DATAMINER_POLICY_ERROR
    assert "override exceeds account-class budget" in exc.value.message


def test_pjm_dataminer_connector_allows_lower_rate_override(monkeypatch):
    monkeypatch.delenv("ARTEMIS_PJM_API_KEY", raising=False)
    result = PjmDataMinerConnector(
        api_key="test-key",
        account_class="non_member",
        max_connections_per_minute=3,
        http_get=lambda *_: {"items": []},
    ).fetch(DataRequest(contract="load_frcstd_7_day", parameters={"feed": "load_frcstd_7_day"}))

    assert result.lineage["max_connections_per_minute"] == 3


def test_pjm_dataminer_token_bucket_sleeps_on_burst(monkeypatch):
    monkeypatch.delenv("ARTEMIS_PJM_API_KEY", raising=False)
    now = [0.0]
    sleeps = []
    calls = []

    def fake_sleep(seconds):
        sleeps.append(seconds)
        now[0] += seconds

    def fake_get(url, headers, timeout):
        calls.append(url)
        if "startRow=1" in url:
            return {"items": [{"row": 1}], "totalRows": 3}
        if "startRow=2" in url:
            return {"items": [{"row": 2}], "totalRows": 3}
        return {"items": [{"row": 3}], "totalRows": 3}

    limiter = PjmDataMinerTokenBucket(2, clock=lambda: now[0], sleep=fake_sleep)
    result = PjmDataMinerConnector(api_key="test-key", http_get=fake_get, rate_limiter=limiter).fetch(
        DataRequest(
            contract="load_frcstd_7_day",
            parameters={"feed": "load_frcstd_7_day", "query": {"rowCount": 1}, "max_pages": 3},
        )
    )

    assert [record["row"] for record in result.records] == [1, 2, 3]
    assert len(calls) == 3
    assert sleeps == [pytest.approx(30.0)]
    assert result.lineage["runtime_rate_limiter_enabled"] is True


def test_pjm_dataminer_connector_honors_retry_after_then_succeeds(monkeypatch):
    monkeypatch.delenv("ARTEMIS_PJM_API_KEY", raising=False)
    calls = []
    sleeps = []

    def fake_get(url, headers, timeout):
        calls.append(url)
        if len(calls) == 1:
            raise PjmDataMinerRetryAfter(2.0)
        return {"items": [{"row": 1}], "totalRows": 1}

    result = PjmDataMinerConnector(api_key="test-key", http_get=fake_get, retry_sleep=sleeps.append).fetch(
        DataRequest(
            contract="load_frcstd_7_day",
            parameters={"feed": "load_frcstd_7_day", "query": {"rowCount": 1}, "paginate": False},
        )
    )

    assert result.records == [{"row": 1}]
    assert len(calls) == 2
    assert sleeps == [2.0]
    assert result.lineage["max_retry_attempts"] == 3


def test_pjm_dataminer_connector_rejects_retry_after_when_budget_exhausted(monkeypatch):
    monkeypatch.delenv("ARTEMIS_PJM_API_KEY", raising=False)
    sleeps = []

    def fake_get(url, headers, timeout):
        raise PjmDataMinerRetryAfter(1.0)

    connector = PjmDataMinerConnector(api_key="test-key", http_get=fake_get, retry_sleep=sleeps.append, max_retry_attempts=1)

    with pytest.raises(WorkbenchException) as exc:
        connector.fetch(
            DataRequest(
                contract="load_frcstd_7_day",
                parameters={"feed": "load_frcstd_7_day", "query": {"rowCount": 1}, "paginate": False},
            )
        )

    assert exc.value.code == PJM_DATAMINER_ERROR
    assert "retry budget" in exc.value.message
    assert sleeps == [1.0]


def test_pjm_dataminer_shared_limiter_is_process_shared():
    first = shared_pjm_dataminer_rate_limiter("non_member", 6)
    second = shared_pjm_dataminer_rate_limiter("non_member", 6)
    different_budget = shared_pjm_dataminer_rate_limiter("non_member", 600)

    assert first is second
    assert first is not different_budget


def test_pjm_dataminer_member_policy_allows_larger_bounded_page_plan(monkeypatch):
    monkeypatch.delenv("ARTEMIS_PJM_API_KEY", raising=False)
    calls = []

    def fake_get(url, headers, timeout):
        calls.append(url)
        if "startRow=1" in url:
            return {"items": [{"row": 1}], "totalRows": 2}
        return {"items": [{"row": 2}], "totalRows": 2}

    result = PjmDataMinerConnector(api_key="test-key", account_class="member", http_get=fake_get).fetch(
        DataRequest(
            contract="load_frcstd_7_day",
            parameters={"feed": "load_frcstd_7_day", "query": {"rowCount": 1}, "max_pages": 7},
        )
    )

    assert [record["row"] for record in result.records] == [1, 2]
    assert len(calls) == 2
    assert result.lineage["account_class"] == "member"
    assert result.lineage["max_connections_per_minute"] == 600


def test_pjm_dataminer_connector_builds_public_definition_url_without_key(monkeypatch):
    monkeypatch.setenv("ARTEMIS_PJM_API_KEY", "env-key")
    connector = PjmDataMinerConnector(base_url="https://api.example/api/v1", definition_base_url="https://definition.example")

    assert connector.definition_url("rt_hrl_lmps") == "https://definition.example/feed/rt_hrl_lmps/definition"
    assert connector.metadata_url("rt_hrl_lmps") == "https://api.example/api/v1/rt_hrl_lmps/metadata"
    assert "env-key" not in connector.definition_url("rt_hrl_lmps")
    assert "env-key" not in connector.metadata_url("rt_hrl_lmps")

    with pytest.raises(WorkbenchException) as exc:
        connector.definition_url("bad/feed")

    assert exc.value.code == PJM_DATAMINER_ERROR


def test_pjm_dataminer_connector_fetches_metadata_definition_with_key(monkeypatch):
    monkeypatch.delenv("ARTEMIS_PJM_API_KEY", raising=False)
    calls = []

    def fake_get(url, headers, timeout):
        calls.append((url, headers, timeout))
        return {"columns": [{"fieldName": "datetime_beginning_utc"}]}

    payload = PjmDataMinerConnector(api_key="test-key", base_url="https://api.example/api/v1", http_get=fake_get).fetch_definition("rt_hrl_lmps")

    assert payload == {"columns": [{"fieldName": "datetime_beginning_utc"}]}
    assert calls == [("https://api.example/api/v1/rt_hrl_lmps/metadata", {"Ocp-Apim-Subscription-Key": "test-key"}, 30.0)]


def test_pjm_dataminer_connector_requires_key_for_metadata_definition(monkeypatch):
    monkeypatch.delenv("ARTEMIS_PJM_API_KEY", raising=False)
    connector = PjmDataMinerConnector(api_key=None, http_get=lambda *_: {"columns": []})

    with pytest.raises(WorkbenchException) as exc:
        connector.fetch_definition("rt_hrl_lmps")

    assert exc.value.code == PJM_DATAMINER_AUTH_MISSING


def test_pjm_dataminer_connector_rejects_definition_error_payload(monkeypatch):
    monkeypatch.delenv("ARTEMIS_PJM_API_KEY", raising=False)
    connector = PjmDataMinerConnector(
        api_key="test-key",
        definition_base_url="https://definition.example",
        http_get=lambda *_: {"code": "BadRequest", "message": "Unknown feed"},
    )

    with pytest.raises(WorkbenchException) as exc:
        connector.fetch_definition("unknown_feed")

    assert exc.value.code == PJM_DATAMINER_ERROR
    assert "Unknown feed" in exc.value.message


@pytest.mark.skipif(os.environ.get("ARTEMIS_RUN_LIVE_PJM_TESTS") != "1", reason="live PJM smoke tests are opt-in")
def test_live_pjm_dataminer_one_page_smoke():
    connector = PjmDataMinerConnector(timeout_seconds=20)
    result = connector.fetch(
        DataRequest(
            contract="load_frcstd_7_day",
            parameters={
                "feed": "load_frcstd_7_day",
                "query": {"rowCount": 1, "startRow": 1},
                "paginate": False,
            },
        )
    )

    assert len(result.records) == 1
    assert result.lineage["page_count"] == 1
    assert {
        "evaluated_at_datetime_utc",
        "forecast_datetime_beginning_utc",
        "forecast_area",
        "forecast_load_mw",
    } <= set(result.records[0])


@pytest.mark.skipif(os.environ.get("ARTEMIS_RUN_LIVE_PJM_TESTS") != "1", reason="live PJM smoke tests are opt-in")
def test_live_pjm_dataminer_lmp_one_page_smoke():
    connector = PjmDataMinerConnector(timeout_seconds=20)
    result = connector.fetch(
        DataRequest(
            contract="rt_hrl_lmps",
            parameters={
                "feed": "rt_hrl_lmps",
                "query": {
                    "rowCount": 1,
                    "startRow": 1,
                    "pnode_id": 51288,
                    "datetime_beginning_utc": "06/01/2026 00:00:00 to 06/01/2026 23:59:59",
                    "row_is_current": True,
                },
                "paginate": False,
            },
        )
    )

    assert len(result.records) == 1
    assert {"datetime_beginning_utc", "pnode_id", "total_lmp_rt", "row_is_current"} <= set(result.records[0])
