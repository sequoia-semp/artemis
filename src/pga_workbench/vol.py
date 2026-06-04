from dataclasses import dataclass
from .exceptions import WorkbenchException, UNSUPPORTED_VOL_SURFACE

MVP_VOL_LOCATIONS = {"WH", "HH"}


@dataclass(frozen=True)
class VolPoint:
    location_id: str
    atm_iv: float
    model_convention: str = "Black76"
    atm_definition: str = "true_at_the_money_underlying_settle"


def validate_vol_location(location_id: str) -> None:
    if location_id.upper() not in MVP_VOL_LOCATIONS:
        raise WorkbenchException(UNSUPPORTED_VOL_SURFACE, f"Vol surface for {location_id} is not in MVP scope")


def absolute_iv_from_atm_diff(atm_iv: float, iv_diff_to_atm: float) -> float:
    return atm_iv + iv_diff_to_atm


def risk_reversal(call_iv: float, put_iv: float) -> float:
    return call_iv - put_iv
