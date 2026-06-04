from __future__ import annotations

from typing import Protocol


class ViewRenderer(Protocol):
    def render(self, view: dict) -> str | bytes:
        ...
