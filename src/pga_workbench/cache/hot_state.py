from __future__ import annotations

from pathlib import Path
from typing import Any

from ..exceptions import WorkbenchException
from ..models import GenerationMixObservation, PriceSurfacePoint
from ..serialization import read_json
from ..state.packs import validate_state_pack

HOT_STATE_INVALID = "HOT_STATE_INVALID"


class HotState:
    """Read-only view over the accepted state referenced by current.json."""

    def __init__(self, state_root: Path):
        self.state_root = Path(state_root)

    def current_pointer(self) -> dict[str, Any]:
        return read_json(self.state_root / "current.json")

    def load_current(self) -> dict[str, Any]:
        pointer = self.current_pointer()
        accepted_dir = Path(pointer["path"])
        if not accepted_dir.is_absolute():
            accepted_dir = self.state_root / accepted_dir
        if accepted_dir.parent.name != "accepted":
            raise WorkbenchException(HOT_STATE_INVALID, f"current.json must point to an accepted state: {accepted_dir}")
        validate_state_pack(accepted_dir)
        payload = read_json(accepted_dir / "state_pack.json")
        if payload["state_id"] != pointer.get("state_id"):
            raise WorkbenchException(HOT_STATE_INVALID, "current.json state_id does not match accepted state pack")
        return payload

    def artifacts(self) -> dict[str, Any]:
        return dict(self.load_current().get("artifacts", {}))

    def price_surface_points(
        self,
        *,
        commodity: str | None = None,
        location_id: str | None = None,
        source_role: str | None = None,
        source_artifact: str | None = None,
    ) -> list[PriceSurfacePoint]:
        """Return accepted price-surface points from HotState with optional filters."""

        rows = self.artifacts().get("price_surface_points")
        if rows is None:
            return []
        if not isinstance(rows, list):
            raise WorkbenchException(HOT_STATE_INVALID, "HotState price_surface_points must be a list")
        points: list[PriceSurfacePoint] = []
        for row in rows:
            if not isinstance(row, dict):
                raise WorkbenchException(HOT_STATE_INVALID, "HotState price_surface_points entries must be mappings")
            point = PriceSurfacePoint(**dict(row))
            if commodity is not None and point.commodity != commodity:
                continue
            if location_id is not None and point.location_id != location_id:
                continue
            if source_role is not None and point.source_role != source_role:
                continue
            if source_artifact is not None and point.lineage.get("source_artifact") != source_artifact:
                continue
            points.append(point)
        return points

    def source_price_points(self, *, commodity: str | None = "power", location_id: str | None = None) -> list[PriceSurfacePoint]:
        """Return accepted source-published price points, excluding derived shapes."""

        return self.price_surface_points(
            commodity=commodity,
            location_id=location_id,
            source_role="authoritative_iso_publication",
        )

    def derived_price_shape_points(self, *, commodity: str | None = "power", location_id: str | None = None) -> list[PriceSurfacePoint]:
        """Return accepted derived price-shape points built from source prices."""

        return self.price_surface_points(
            commodity=commodity,
            location_id=location_id,
            source_artifact="power_price_shape_rollups",
        )

    def fundamental_source_records(
        self,
        *,
        state_key: str = "pjm_load_fundamentals",
        product_id: str | None = None,
        location_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return source-specific fundamental records from an accepted state product."""

        state = self.artifacts().get(state_key)
        if state is None:
            return []
        if not isinstance(state, dict):
            raise WorkbenchException(HOT_STATE_INVALID, f"HotState {state_key} must be a mapping")
        source_products = state.get("source_products")
        if not isinstance(source_products, dict):
            raise WorkbenchException(HOT_STATE_INVALID, f"HotState {state_key}.source_products must be a mapping")
        records: list[dict[str, Any]] = []
        for current_product_id, rows in source_products.items():
            if product_id is not None and str(current_product_id) != product_id:
                continue
            if not isinstance(rows, list):
                raise WorkbenchException(HOT_STATE_INVALID, f"HotState {state_key}.source_products entries must be lists")
            for row in rows:
                if not isinstance(row, dict):
                    raise WorkbenchException(HOT_STATE_INVALID, f"HotState {state_key}.source_products records must be mappings")
                if location_id is not None and row.get("location_id") != location_id:
                    continue
                payload = dict(row)
                payload.setdefault("source_product_id", str(current_product_id))
                records.append(payload)
        return records

    def fundamental_best_series_records(
        self,
        *,
        state_key: str = "pjm_load_fundamentals",
        metric_id: str | None = None,
        location_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return best-series fundamental records without mixing them with source products."""

        state = self.artifacts().get(state_key)
        if state is None:
            return []
        if not isinstance(state, dict):
            raise WorkbenchException(HOT_STATE_INVALID, f"HotState {state_key} must be a mapping")
        best_series = state.get("best_series")
        if not isinstance(best_series, dict):
            raise WorkbenchException(HOT_STATE_INVALID, f"HotState {state_key}.best_series must be a mapping")
        records: list[dict[str, Any]] = []
        for current_metric_id, rows in best_series.items():
            if metric_id is not None and str(current_metric_id) != metric_id:
                continue
            if not isinstance(rows, list):
                raise WorkbenchException(HOT_STATE_INVALID, f"HotState {state_key}.best_series entries must be lists")
            for row in rows:
                if not isinstance(row, dict):
                    raise WorkbenchException(HOT_STATE_INVALID, f"HotState {state_key}.best_series records must be mappings")
                if location_id is not None and row.get("location_id") != location_id:
                    continue
                payload = dict(row)
                payload.setdefault("best_series_id", str(current_metric_id))
                records.append(payload)
        return records

    def generation_mix_observations(self, *, location_id: str | None = None, fuel_id: str | None = None) -> list[GenerationMixObservation]:
        """Return accepted source-backed generation mix observations."""

        rows = self.artifacts().get("generation_mix_observations")
        if rows is None:
            return []
        if not isinstance(rows, list):
            raise WorkbenchException(HOT_STATE_INVALID, "HotState generation_mix_observations must be a list")
        observations: list[GenerationMixObservation] = []
        for row in rows:
            if not isinstance(row, dict):
                raise WorkbenchException(HOT_STATE_INVALID, "HotState generation_mix_observations entries must be mappings")
            observation = GenerationMixObservation(**dict(row))
            if location_id is not None and observation.location_id != location_id:
                continue
            if fuel_id is not None and observation.fuel_id != fuel_id:
                continue
            observations.append(observation)
        return observations

    def artifact_gaps(
        self,
        state_key: str,
        *,
        location_id: str | None = None,
        reason: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return explicit accepted-state gaps for a source or derived artifact."""

        state = self.artifacts().get(state_key)
        if state is None:
            return []
        if not isinstance(state, dict):
            raise WorkbenchException(HOT_STATE_INVALID, f"HotState {state_key} must be a mapping")
        gaps = state.get("gaps")
        if gaps is None:
            return []
        if not isinstance(gaps, list):
            raise WorkbenchException(HOT_STATE_INVALID, f"HotState {state_key}.gaps must be a list")
        records: list[dict[str, Any]] = []
        for gap in gaps:
            if not isinstance(gap, dict):
                raise WorkbenchException(HOT_STATE_INVALID, f"HotState {state_key}.gaps entries must be mappings")
            if location_id is not None and gap.get("location_id") != location_id:
                continue
            if reason is not None and gap.get("reason") != reason:
                continue
            payload = dict(gap)
            payload.setdefault("source_artifact", state_key)
            records.append(payload)
        return records

    def fundamental_gaps(self, *, state_key: str = "pjm_load_fundamentals", location_id: str | None = None, reason: str | None = None) -> list[dict[str, Any]]:
        """Return accepted fundamental coverage gaps."""

        return self.artifact_gaps(state_key, location_id=location_id, reason=reason)

    def generation_mix_gaps(self, *, location_id: str | None = None, reason: str | None = None) -> list[dict[str, Any]]:
        """Return accepted generation mix coverage gaps."""

        return self.artifact_gaps("pjm_generation_mix", location_id=location_id, reason=reason)

    def price_shape_gaps(self, *, location_id: str | None = None, reason: str | None = None) -> list[dict[str, Any]]:
        """Return accepted derived price-shape coverage gaps."""

        return self.artifact_gaps("power_price_shape_rollups", location_id=location_id, reason=reason)
