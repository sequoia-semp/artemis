from dataclasses import dataclass


@dataclass(frozen=True)
class ATCComponent:
    shape: str
    signed_mw: float


@dataclass(frozen=True)
class ATCDecomposition:
    signed_mw: float
    components: list[ATCComponent]


def decompose_atc(signed_mw: float) -> ATCDecomposition:
    return ATCDecomposition(
        signed_mw=signed_mw,
        components=[ATCComponent("PEAK", signed_mw), ATCComponent("OFFPEAK", signed_mw)],
    )


def atc_blended_price(peak_price: float, offpeak_price: float, peak_hours: float, offpeak_hours: float) -> float:
    total_hours = peak_hours + offpeak_hours
    if total_hours == 0:
        raise ValueError("total ATC hours cannot be zero")
    return (peak_price * peak_hours + offpeak_price * offpeak_hours) / total_hours
