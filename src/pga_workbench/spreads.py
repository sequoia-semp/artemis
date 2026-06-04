from dataclasses import dataclass
from .exceptions import WorkbenchException, NON_CANONICAL_BASIS_ORIENTATION

APPROVED_POWER_SPREADS = {
    "WH/AD": ("WH", "AD"),
    "AD/NI": ("AD", "NI"),
    "WH/NI": ("WH", "NI"),
}
FORBIDDEN_POWER_SPREADS = {"AD/WH", "NI/AD", "NI/WH"}


@dataclass(frozen=True)
class SpreadExposure:
    quote_label: str
    first: str
    second: str
    signed_quantity: float
    first_leg_exposure: float
    second_leg_exposure: float


def normalize_spread_label(label: str) -> str:
    return label.strip().upper().replace(" ", "")


def decompose_power_spread(label: str, signed_quantity: float) -> SpreadExposure:
    norm = normalize_spread_label(label)
    if norm in FORBIDDEN_POWER_SPREADS:
        raise WorkbenchException(
            NON_CANONICAL_BASIS_ORIENTATION,
            f"{norm} is forbidden by default. Use approved orientation with signed quantity."
        )
    if norm not in APPROVED_POWER_SPREADS:
        raise WorkbenchException(
            NON_CANONICAL_BASIS_ORIENTATION,
            f"{norm} is not an approved power basis edge."
        )
    first, second = APPROVED_POWER_SPREADS[norm]
    return SpreadExposure(norm, first, second, signed_quantity, signed_quantity, -signed_quantity)
