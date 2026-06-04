from dataclasses import dataclass
import re
from .exceptions import WorkbenchException, UNKNOWN_PRODUCT, UNKNOWN_GAS_LOCATION

POWER_LOCATIONS = {"WH", "AD", "NI"}
GAS_ALIASES = {
    "HH": "HH", "HENRY": "HH", "HENRYHUB": "HH", "HENRY_HUB": "HH",
    "TETCO-M3": "TETCO_M3", "TETCOM3": "TETCO_M3", "TETCO M3": "TETCO_M3", "M3": "TETCO_M3",
    "TETCO-M2": "TETCO_M2", "TETCOM2": "TETCO_M2", "TETCO M2": "TETCO_M2", "M2": "TETCO_M2",
    "TRANSCOZ6NNY": "TRANSCO_Z6_NNY", "TRANSCO Z6 NNY": "TRANSCO_Z6_NNY", "Z6NNY": "TRANSCO_Z6_NNY", "Z6 NNY": "TRANSCO_Z6_NNY",
    "TRANSCOZ6NY": "TRANSCO_Z6_NY", "TRANSCO Z6 NY": "TRANSCO_Z6_NY", "Z6NY": "TRANSCO_Z6_NY", "Z6 NY": "TRANSCO_Z6_NY",
    "TRANSCOZ5": "TRANSCO_Z5", "TRANSCO Z5": "TRANSCO_Z5", "Z5": "TRANSCO_Z5",
    "TRANSCOZ5SOUTH": "TRANSCO_Z5_SOUTH", "TRANSCO Z5 SOUTH": "TRANSCO_Z5_SOUTH", "Z5SOUTH": "TRANSCO_Z5_SOUTH", "Z5 SOUTH": "TRANSCO_Z5_SOUTH",
    "EASTERNGASSOUTH": "EASTERN_GAS_SOUTH", "EASTERN GAS SOUTH": "EASTERN_GAS_SOUTH", "EGS": "EASTERN_GAS_SOUTH", "APPALACHIA": "EASTERN_GAS_SOUTH",
}
GAS_INDEX_KEYWORDS = {
    "GDD": "GDD",
    "LD1": "LD1",
    "IFERC": "IFERC",
    "BASIS": "BASIS_TO_LD1",
    "INDEX": "GDD_INDEX_TO_IFERC",
    "SWING": "GDD_SWING",
}


@dataclass(frozen=True)
class MarketIndex:
    index_id: str
    commodity: str
    location_id: str
    index_family: str
    market_run: str | None = None
    price_component: str | None = None
    shape: str | None = None
    quote_unit: str = ""
    is_defaulted: bool = False
    default_reason: str | None = None


def normalize_power_index(raw: str) -> MarketIndex:
    s = raw.strip().upper().replace("-", " ")
    tokens = re.split(r"\s+", s)
    loc = next((t for t in tokens if t in POWER_LOCATIONS), None)
    if not loc:
        raise WorkbenchException(UNKNOWN_PRODUCT, f"Unknown power location in {raw}")
    market_run = "DA" if "DA" in tokens else "RT" if "RT" in tokens else "RT"
    defaulted = "DA" not in tokens and "RT" not in tokens
    if "PEAK" in tokens or "PK" in tokens:
        shape = "PEAK"
    elif "OFFPEAK" in tokens or "OFF" in tokens or "OP" in tokens:
        shape = "OFFPEAK"
    elif "ATC" in tokens:
        shape = "ATC"
    else:
        shape = "ATC"
        defaulted = True
    idx = f"PJM.{loc}.{market_run}.FULL_LMP.{shape}"
    return MarketIndex(idx, "power", loc, "ISO_LMP", market_run, "FULL_LMP", shape, "USD_per_MWh", defaulted, "bare_power_defaults_applied" if defaulted else None)


def _compact(s: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", s.upper())


def normalize_gas_index(raw: str) -> MarketIndex:
    raw_up = raw.strip().upper()
    compact = _compact(raw_up)
    location = None
    for alias, loc in GAS_ALIASES.items():
        if _compact(alias) in compact:
            location = loc
            break
    if not location:
        raise WorkbenchException(UNKNOWN_GAS_LOCATION, f"Unknown gas location in {raw}")

    index_family = None
    for keyword, family in GAS_INDEX_KEYWORDS.items():
        if keyword in raw_up.split() or keyword in compact:
            index_family = family
            break
    defaulted = False
    if index_family is None:
        index_family = "GDD"
        defaulted = True
    idx = f"GAS.{location}.{index_family}"
    return MarketIndex(idx, "gas", location, index_family, None, None, "DAILY" if index_family == "GDD" else "MONTHLY", "USD_per_MMBtu", defaulted, "recognized_gas_location_defaults_to_GDD" if defaulted else None)
