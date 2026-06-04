from __future__ import annotations

from .base import DataConnector


class IsoApiConnector(DataConnector):
    def __init__(self) -> None:
        super().__init__(id="iso_api", kind="iso_api")
