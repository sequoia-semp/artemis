from __future__ import annotations

from typing import Protocol


class LocalLLMAdapter(Protocol):
    def complete(self, prompt: str) -> str:
        ...
