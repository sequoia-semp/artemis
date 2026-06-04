from __future__ import annotations

from .base import DataConnector


class FileDropConnector(DataConnector):
    def __init__(self) -> None:
        super().__init__(id="file_drop", kind="file")

    def available(self) -> bool:
        return True
