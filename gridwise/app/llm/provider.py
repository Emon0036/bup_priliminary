"""Provider for OpenAI-compatible language models.

Supports:
- OpenAI GPT-4o, GPT-4o-mini
- Anthropic Claude (via compatible endpoint)
- Any OpenAI-compatible API

Handles:
- API key management
- Request building
- Retries with backoff
- Timeout enforcement
- Rate limit detection
"""

import os
import json
import time
import typing
from typing import Any, Optional

import httpx


class LLMProvider:
    """Concrete provider for OpenAI-compatible APIs."""

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: Optional[str] = None,
        timeout_seconds: int = 30,
        max_retries: int = 2,
    ):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url or os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self._client: Optional[httpx.Client] = None

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(
                timeout=httpx.Timeout(self.timeout_seconds),
                limits=httpx.Limits(max_connections=5, keepalive_expiry=300),
            )
        return self._client

    def call(self, messages: list[dict[str, str]]) -> str:
        """Send messages to the LLM and return the raw text response.

        Retries up to max_retries times on transient failures.
        Raises LLMError on persistent failure.
        """
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.0,
            "max_tokens": 1000,
            "response_format": {"type": "json_object"},
        }

        last_error: Any = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = self.client.post(url, headers=headers, json=payload)
                if resp.status_code == 429:
                    # Rate limited - backoff
                    wait = min(2 ** attempt, 10)
                    time.sleep(wait)
                    continue
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"]
            except httpx.TimeoutException as e:
                last_error = e
                if attempt < self.max_retries:
                    time.sleep(min(2 ** attempt, 5))
                    continue
                raise
            except (httpx.HTTPError, json.JSONDecodeError, KeyError) as e:
                last_error = e
                if attempt < self.max_retries:
                    time.sleep(min(2 ** attempt, 5))
                    continue
                raise

        raise last_error or RuntimeError("LLM call failed")

    def close(self):
        if self._client:
            self._client.close()
            self._client = None