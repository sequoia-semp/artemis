from __future__ import annotations

from .base import DataConnector


class VendorApiConnector(DataConnector):
    def __init__(self) -> None:
        super().__init__(id="vendor_api", kind="vendor_api")
