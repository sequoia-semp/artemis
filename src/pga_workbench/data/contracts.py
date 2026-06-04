from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..exceptions import WorkbenchException

FIXTURE_DATA_NOT_ALLOWED = "FIXTURE_DATA_NOT_ALLOWED"
DATA_CONNECTOR_NOT_IMPLEMENTED = "DATA_CONNECTOR_NOT_IMPLEMENTED"


@dataclass(frozen=True)
class DataRequest:
    contract: str
    as_of: str | None = None
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DataResult:
    source: str
    contract: str
    data_environment: str
    records: list[dict[str, Any]]
    lineage: dict[str, Any] = field(default_factory=dict)


def assert_data_environment_allowed(mode: str, data_environment: str, allow_fixture: bool = False) -> None:
    if mode == "analyst" and data_environment in {"fixture", "test"} and not allow_fixture:
        raise WorkbenchException(
            FIXTURE_DATA_NOT_ALLOWED,
            f"{data_environment} data cannot be used in normal Analyst Mode; pass explicit fixture/test mode for validation.",
        )
