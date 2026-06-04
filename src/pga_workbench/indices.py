from dataclasses import dataclass
import re
from .registry_access import RegistryCatalog, find_gas_location, find_power_location, gas_index_keywords


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


def normalize_power_index(raw: str, catalog: RegistryCatalog | None = None) -> MarketIndex:
    s = raw.strip().upper().replace("-", " ")
    tokens = re.split(r"\s+", s)
    loc = find_power_location(raw, catalog)
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


def normalize_gas_index(raw: str, catalog: RegistryCatalog | None = None) -> MarketIndex:
    raw_up = raw.strip().upper()
    compact = _compact(raw_up)
    location = find_gas_location(raw, catalog)

    index_family = None
    for keyword, family in gas_index_keywords(catalog).items():
        if keyword in raw_up.split() or keyword in compact:
            index_family = family
            break
    defaulted = False
    if index_family is None:
        index_family = "GDD"
        defaulted = True
    idx = f"GAS.{location}.{index_family}"
    return MarketIndex(idx, "gas", location, index_family, None, None, "DAILY" if index_family == "GDD" else "MONTHLY", "USD_per_MMBtu", defaulted, "recognized_gas_location_defaults_to_GDD" if defaulted else None)
