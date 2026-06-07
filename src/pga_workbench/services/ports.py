from __future__ import annotations

from dataclasses import dataclass, field
from importlib.util import find_spec
from typing import Any, Protocol

from ..exceptions import WorkbenchException
from ..models import GreeksReport, HistoricalVaRReport, NormalizedPosition
from .greeks import run_black76_greeks
from .risk import run_historical_var

OSS_ADAPTER_UNAVAILABLE = "OSS_ADAPTER_UNAVAILABLE"
OSS_ADAPTER_NOT_VALIDATED = "OSS_ADAPTER_NOT_VALIDATED"


class PricingPort(Protocol):
    port_id: str
    implementation: str

    def option_greeks(self, rows: list[dict[str, Any]], run_id: str = "pricing-port-greeks") -> GreeksReport:
        """Return canonical option price/Greek rows from canonical model inputs."""


class RiskPort(Protocol):
    port_id: str
    implementation: str

    def historical_var(
        self,
        positions: list[NormalizedPosition],
        historical_returns: list[dict[str, Any]],
        as_of: str,
        run_id: str = "risk-port-var",
        confidence_levels: list[float] | None = None,
    ) -> HistoricalVaRReport:
        """Return canonical historical VaR output from canonical exposures and returns."""


@dataclass(frozen=True)
class BuiltinBlack76PricingPort:
    port_id: str = "pricing.black76_builtin"
    implementation: str = "pga_workbench.services.greeks.run_black76_greeks"

    def option_greeks(self, rows: list[dict[str, Any]], run_id: str = "pricing-port-greeks") -> GreeksReport:
        return run_black76_greeks(rows, run_id=run_id)


@dataclass(frozen=True)
class BuiltinHistoricalRiskPort:
    port_id: str = "risk.historical_var_builtin"
    implementation: str = "pga_workbench.services.risk.run_historical_var"

    def historical_var(
        self,
        positions: list[NormalizedPosition],
        historical_returns: list[dict[str, Any]],
        as_of: str,
        run_id: str = "risk-port-var",
        confidence_levels: list[float] | None = None,
    ) -> HistoricalVaRReport:
        return run_historical_var(
            positions,
            historical_returns,
            as_of=as_of,
            run_id=run_id,
            confidence_levels=confidence_levels,
        )


@dataclass(frozen=True)
class OptionalOssAdapterCandidate:
    port_id: str
    capability: str
    package: str
    implementation: str
    status: str = "candidate_not_oracle_validated"

    def availability(self) -> dict[str, Any]:
        return {
            "port_id": self.port_id,
            "capability": self.capability,
            "package": self.package,
            "implementation": self.implementation,
            "status": self.status,
            "available": find_spec(self.package) is not None,
            "authoritative": False,
        }

    def require_available_and_validated(self) -> None:
        if find_spec(self.package) is None:
            raise WorkbenchException(
                OSS_ADAPTER_UNAVAILABLE,
                f"Optional OSS adapter {self.port_id} requires package {self.package}, which is not installed",
            )
        raise WorkbenchException(
            OSS_ADAPTER_NOT_VALIDATED,
            f"Optional OSS adapter {self.port_id} is not oracle-validated for authoritative use",
        )


@dataclass(frozen=True)
class QuantLibBlack76PricingPort:
    candidate: OptionalOssAdapterCandidate = field(
        default_factory=lambda: OptionalOssAdapterCandidate(
            port_id="pricing.quantlib_black76_candidate",
            capability="pricing",
            package="QuantLib",
            implementation="optional_quantlib_black76_adapter",
        )
    )

    @property
    def port_id(self) -> str:
        return self.candidate.port_id

    @property
    def implementation(self) -> str:
        return self.candidate.implementation

    def option_greeks(self, rows: list[dict[str, Any]], run_id: str = "quantlib-candidate-greeks") -> GreeksReport:
        self.candidate.require_available_and_validated()
        raise AssertionError("unreachable")


OPTIONAL_OSS_ADAPTER_CANDIDATES = [
    OptionalOssAdapterCandidate(
        port_id="pricing.quantlib_black76_candidate",
        capability="pricing",
        package="QuantLib",
        implementation="optional_quantlib_black76_adapter",
    ),
    OptionalOssAdapterCandidate(
        port_id="risk.riskfolio_candidate",
        capability="risk",
        package="riskfolio",
        implementation="optional_riskfolio_adapter",
    ),
    OptionalOssAdapterCandidate(
        port_id="risk.cvxportfolio_candidate",
        capability="risk",
        package="cvxportfolio",
        implementation="optional_cvxportfolio_adapter",
    ),
    OptionalOssAdapterCandidate(
        port_id="risk.skfolio_candidate",
        capability="risk",
        package="skfolio",
        implementation="optional_skfolio_adapter",
    ),
]


def valuation_port_catalog() -> dict[str, Any]:
    builtin = [
        {
            "port_id": BuiltinBlack76PricingPort().port_id,
            "capability": "pricing",
            "package": "pga_workbench",
            "implementation": BuiltinBlack76PricingPort().implementation,
            "status": "validated_builtin",
            "available": True,
            "authoritative": True,
        },
        {
            "port_id": BuiltinHistoricalRiskPort().port_id,
            "capability": "risk",
            "package": "pga_workbench",
            "implementation": BuiltinHistoricalRiskPort().implementation,
            "status": "validated_builtin",
            "available": True,
            "authoritative": True,
        },
    ]
    optional = [candidate.availability() for candidate in OPTIONAL_OSS_ADAPTER_CANDIDATES]
    return {
        "builtins": builtin,
        "optional_oss_candidates": optional,
        "policy": {
            "default_authority": "validated_builtin",
            "optional_adapter_rule": "candidate adapters must be installed, wrapped behind ports, and oracle-validated before authoritative use",
            "llm_rule": "LLMs may narrate deterministic tool outputs only",
        },
    }
