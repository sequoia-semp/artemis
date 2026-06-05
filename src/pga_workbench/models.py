from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class RawMark:
    as_of: str
    raw_product: str
    raw_period: str
    price: float
    source: str
    source_role: str = "authoritative_input"
    raw_row_id: str | None = None


@dataclass(frozen=True)
class PriceSurfacePoint:
    as_of: str
    index_id: str
    location_id: str
    commodity: str
    period_id: str
    price: float
    quote_unit: str
    source: str
    source_role: str
    lineage: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RawPosition:
    as_of: str
    raw_product: str
    raw_period: str
    raw_quantity: float
    quantity_unit: str
    position_id: str
    raw_mark: float | None = None
    book: str | None = None
    strategy: str | None = None
    portfolio: str | None = None
    sleeve: str | None = None
    structure_id: str | None = None
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    source: str = "local_table"
    source_role: str = "authoritative_input"
    reference_hours: float | None = None
    delivery_days: int | None = None


@dataclass(frozen=True)
class PositionLot:
    as_of: str
    position_id: str
    instrument_id: str
    instrument_type: str
    raw_product: str
    period_id: str
    signed_quantity: float
    quantity_unit: str
    mark: float | None
    source: str
    source_role: str
    book: str | None = None
    strategy: str | None = None
    portfolio: str | None = None
    sleeve: str | None = None
    structure_id: str | None = None
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExposureRecord:
    as_of: str
    position_id: str
    index_id: str
    period_id: str
    signed_quantity: float
    quantity_unit: str
    exposure_type: str = "flat_price"
    component: str | None = None
    component_weight: float = 1.0
    derived_MWh: float | None = None
    derived_MMBtu: float | None = None
    market_value: float | None = None
    book: str | None = None
    strategy: str | None = None
    portfolio: str | None = None
    sleeve: str | None = None
    structure_id: str | None = None
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class NormalizedPosition:
    as_of: str
    position_id: str
    raw: dict[str, Any]
    identity: dict[str, Any]
    normalized: dict[str, Any]
    derived: dict[str, Any]
    decomposition: dict[str, Any] = field(default_factory=dict)
    exceptions: list[dict[str, Any]] = field(default_factory=list)
    position_lot: dict[str, Any] = field(default_factory=dict)
    exposures: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class OptionContract:
    option_contract_id: str
    contract_symbol: str
    commodity: str
    location_id: str
    underlying_index_id: str
    settlement_method: str
    contract_size: dict[str, Any]
    contract_period: str
    premium_quote_unit: str
    strike_unit: str
    option_style: str
    exercise_method: str
    valuation_model: str
    model_scope: str
    source_documents: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class VolSurfacePoint:
    as_of: str
    underlying_index_id: str
    delivery_period_id: str
    option_expiry: str
    model_convention: str
    atm: dict[str, Any]
    skew: dict[str, Any]
    status: str
    lineage: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ForecastSnapshot:
    as_of: str
    source: str
    forecast_type: str
    location_id: str
    delivery_start: str
    delivery_end: str
    value: float
    unit: str
    vintage: str
    lineage: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FundamentalObservation:
    as_of: str
    source: str
    metric: str
    location_id: str
    delivery_start: str
    delivery_end: str
    value: float
    unit: str
    lineage: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PnlAttributionReport:
    run_id: str
    prior_as_of: str
    current_as_of: str
    position_change_effect: float
    price_move_effect: float
    basis_move_effect: float
    strip_weight_effect: float
    atc_component_effect: float
    mark_adjustment_effect: float
    unexplained_residual: float
    bridge_sums: bool
    drivers: list[dict[str, Any]]
    option_delta_effect: float = 0.0
    option_gamma_effect: float = 0.0
    option_vega_effect: float = 0.0
    option_theta_effect: float = 0.0
    group_breakdowns: list[dict[str, Any]] = field(default_factory=list)
    exceptions: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class HistoricalVaRReport:
    run_id: str
    as_of: str
    method: str
    horizon_days: int
    confidence_levels: list[float]
    lookback_observations: int
    var_by_confidence: dict[str, float]
    scenario_pnl: list[dict[str, Any]]
    lineage: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GreeksReport:
    run_id: str
    as_of: str
    model_convention: str
    greeks: list[dict[str, Any]]
    lineage: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ForwardPriceHeatmapReport:
    run_id: str
    as_of: str
    history_days: list[int]
    cells: list[dict[str, Any]]
    lineage: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExceptionReport:
    run_id: str
    as_of: str
    exceptions: list[dict[str, Any]]


@dataclass(frozen=True)
class RunManifest:
    run_id: str
    created_at: str
    agent_pack_version: str
    inputs: list[dict[str, Any]] = field(default_factory=list)
    outputs: list[dict[str, Any]] = field(default_factory=list)
    tests: dict[str, Any] = field(default_factory=dict)
    exceptions: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MorningStatePack:
    state_id: str
    as_of: str
    created_at: str
    synthetic: bool
    artifacts: dict[str, Any]
    manifest: RunManifest


@dataclass(frozen=True)
class IntradayOverlay:
    overlay_id: str
    base_state_id: str
    created_at: str
    artifacts: dict[str, Any]
    manifest: RunManifest


@dataclass(frozen=True)
class AgentMemoryEntry:
    entry_id: str
    created_at: str
    category: str
    summary: str
    provenance: str
    canonical: bool = False
    related_change_request: str | None = None
