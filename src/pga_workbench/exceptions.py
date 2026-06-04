from dataclasses import dataclass


@dataclass(frozen=True)
class WorkbenchException(Exception):
    code: str
    message: str
    blocking: bool = True

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


UNKNOWN_PRODUCT = "UNKNOWN_PRODUCT"
UNKNOWN_PERIOD = "UNKNOWN_PERIOD"
NON_CANONICAL_BASIS_ORIENTATION = "NON_CANONICAL_BASIS_ORIENTATION"
UNSUPPORTED_VOL_SURFACE = "UNSUPPORTED_VOL_SURFACE"
UNKNOWN_GAS_LOCATION = "UNKNOWN_GAS_LOCATION"
