"""Configuration for GridWise application.

Reads environment variables for LLM provider settings and other options.

Environment variables:
- LLM_API_KEY: required for LLM provider
- LLM_MODEL: required for LLM provider (e.g., "gpt-4o-mini")
- LLM_BASE_URL: optional, OpenAI-compatible base URL
- LLM_TIMEOUT_SECONDS: optional, default 30
- LLM_MAX_RETRIES: optional, default 2
"""

import os
from typing import Optional


def get_settings():
    """Get configuration settings from environment variables."""

    return _Settings(
        llm_api_key=os.getenv("LLM_API_KEY", ""),
        llm_model=os.getenv("LLM_MODEL", ""),
        llm_base_url=os.getenv("LLM_BASE_URL", None),
        llm_timeout_seconds=int(os.getenv("LLM_TIMEOUT_SECONDS", "30")),
        llm_max_retries=int(os.getenv("LLM_MAX_RETRIES", "2")),
    )


class _Settings:
    """Private settings class."""

    def __init__(
        self,
        llm_api_key: str,
        llm_model: str,
        llm_base_url: Optional[str],
        llm_timeout_seconds: int,
        llm_max_retries: int,
    ):
        self.llm_api_key = llm_api_key
        self.llm_model = llm_model
        self.llm_base_url = llm_base_url
        self.llm_timeout_seconds = llm_timeout_seconds
        self.llm_max_retries = llm_max_retries