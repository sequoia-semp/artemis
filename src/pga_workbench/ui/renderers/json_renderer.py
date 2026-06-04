from __future__ import annotations

import json


class JsonViewRenderer:
    def render(self, view: dict) -> str:
        return json.dumps(view, indent=2, sort_keys=True)
