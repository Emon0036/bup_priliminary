"""LLM Interpreter for GridWise operator notes.

Interpret 1-3 operator notes using a single LLM call.

Responsibilities:
- Build the system prompt and user message
- Call the LLM provider once
- Post-process and normalize the response
- Return list of interpretation dicts ready for guardrails validation

The LLM must produce structured output matching the exact schema.
Never allow raw LLM text to modify the optimizer directly.
"""

import json
from typing import List, Dict, Any, Optional

from .base import LLMBase, LLMProvider, LLMInterpreter


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def create_interpreter(
    provider=None,
    api_key: str = "",
    model: str = "",
    base_url: Optional[str] = None,
    timeout_seconds: int = 30,
    max_retries: int = 2,
) -> LLMInterpreter:
    """Factory function to create an LLMInterpreter with the given provider.

    Accepts either a pre-built provider object, or individual params to build one.
    """
    if provider is None:
        provider = LLMProvider(
            api_key=api_key,
            model=model,
            base_url=base_url,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
        )
    return LLMInterpreter(provider=provider)


# ---------------------------------------------------------------------------
# Pre-built interpreter (for convenient import)
# ---------------------------------------------------------------------------

# The actual interpreter will be configured at runtime via environment variables.
# This module-level instance is a placeholder; main.py should create one via
# create_interpreter(os.getenv("LLM_API_KEY"), os.getenv("LLM_MODEL")).
interpreter: LLMInterpreter | None = None