"""Small Ollama HTTP client for local embeddings and generation."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from .config import DEFAULT_EMBED_MODEL, DEFAULT_LLM_MODEL, DEFAULT_OLLAMA_HOST


@dataclass
class OllamaClient:
    host: str = DEFAULT_OLLAMA_HOST
    embed_model: str = DEFAULT_EMBED_MODEL
    llm_model: str = DEFAULT_LLM_MODEL

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one local embedding per input text using Ollama."""
        if not texts:
            return []

        try:
            response = self._post(
                "/api/embed",
                {"model": self.embed_model, "input": texts},
            )
            embeddings = response.get("embeddings")
            if embeddings:
                return embeddings
        except RuntimeError:
            pass

        return [self._post("/api/embeddings", {"model": self.embed_model, "prompt": text})["embedding"] for text in texts]

    def generate(self, prompt: str, temperature: float = 0.1) -> str:
        response = self._post(
            "/api/generate",
            {
                "model": self.llm_model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": temperature},
            },
        )
        return str(response.get("response", "")).strip()

    def list_models(self) -> list[str]:
        """Return locally available Ollama model names."""
        response = self._get("/api/tags", timeout=15)
        models = response.get("models", [])
        return sorted(str(model.get("name", "")) for model in models if model.get("name"))

    def has_model(self, model_name: str) -> bool:
        """Check both exact names and Ollama tags such as `model:latest`."""
        available = set(self.list_models())
        if model_name in available:
            return True
        if ":" not in model_name:
            return f"{model_name}:latest" in available
        return False

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.host.rstrip('/')}{path}"
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace").strip()
            raise RuntimeError(
                f"Ollama request failed for model `{payload.get('model')}`. "
                "Make sure the model is pulled locally. "
                f"Server response: {detail or exc.reason}"
            ) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(
                "Could not reach Ollama. Start it with `ollama serve` and pull the required models."
            ) from exc

    def _get(self, path: str, timeout: int = 120) -> dict[str, Any]:
        url = f"{self.host.rstrip('/')}{path}"
        request = urllib.request.Request(url, method="GET")
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace").strip()
            raise RuntimeError(f"Ollama request failed: {detail or exc.reason}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(
                "Could not reach Ollama. Start it with `ollama serve` and pull the required models."
            ) from exc

