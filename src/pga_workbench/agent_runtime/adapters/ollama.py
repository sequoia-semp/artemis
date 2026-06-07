from __future__ import annotations

import json
import os
import urllib.request


class OllamaAdapter:
    def __init__(self, base_url: str = "http://localhost:11434", model: str | None = None, timeout: float = 60.0):
        self.base_url = base_url.rstrip("/")
        self.model = model or os.environ.get("ARTEMIS_OPENAI_COMPATIBLE_MODEL") or os.environ.get("OLLAMA_MODEL") or ""
        self.timeout = timeout

    def complete(self, prompt: str) -> str:
        if not self.model:
            raise ValueError("Ollama model is required; pass model or set ARTEMIS_OPENAI_COMPATIBLE_MODEL")
        payload = json.dumps({"model": self.model, "prompt": prompt, "stream": False}).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
        return str(data.get("response") or "")
