from dataclasses import dataclass
from .exceptions import WorkbenchException, NON_CANONICAL_BASIS_ORIENTATION
from .registry_access import RegistryCatalog, load_registry_catalog


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


def decompose_power_spread(label: str, signed_quantity: float, catalog: RegistryCatalog | None = None) -> SpreadExposure:
    catalog = catalog or load_registry_catalog()
    norm = normalize_spread_label(label)
    if norm in catalog.forbidden_spreads:
        raise WorkbenchException(
            NON_CANONICAL_BASIS_ORIENTATION,
            f"{norm} is forbidden by default. Use approved orientation with signed quantity."
        )
    record = catalog.approved_spreads.get(norm)
    if record is None:
        raise WorkbenchException(
            NON_CANONICAL_BASIS_ORIENTATION,
            f"{norm} is not an approved power basis edge."
        )
    first, second = str(record["first"]), str(record["second"])
    return SpreadExposure(norm, first, second, signed_quantity, signed_quantity, -signed_quantity)
