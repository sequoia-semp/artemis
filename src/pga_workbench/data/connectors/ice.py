from __future__ import annotations

from .base import DataConnector


class IceExchangeConnector(DataConnector):
    def __init__(self) -> None:
        super().__init__(id="ice_exchange", kind="ice_exchange")
