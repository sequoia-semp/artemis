from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ...exceptions import WorkbenchException
from ..contracts import DATA_CONNECTOR_NOT_IMPLEMENTED, DataRequest, DataResult


@dataclass(frozen=True)
class DataConnector:
    id: str
    kind: str

    def available(self) -> bool:
        return False

    def describe(self) -> dict[str, Any]:
        return {"id": self.id, "kind": self.kind, "available": self.available()}

    def fetch(self, request: DataRequest) -> DataResult:
        raise WorkbenchException(DATA_CONNECTOR_NOT_IMPLEMENTED, f"{self.id} does not implement live fetch for {request.contract}")
