"""Provider-agnostic LLM completion with retries.

Every AI-touching component (profiler, goal_translator, explainer) calls
through LLMClient instead of talking to Groq/Gemini directly, so swapping
providers or changing retry behaviour happens in exactly one place.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Callable

DEFAULT_MODEL_BY_PROVIDER = {
    "groq": "llama-3.3-70b-versatile",
    "gemini": "gemini-2.0-flash",
}


class LLMError(Exception):
    """Raised when a provider call fails after all retries are exhausted."""


@dataclass
class LLMClient:
    provider: str
    api_key: str
    model: str | None = None
    max_retries: int = 3
    retry_backoff_seconds: float = 1.0

    def __post_init__(self) -> None:
        if self.provider not in DEFAULT_MODEL_BY_PROVIDER:
            raise ValueError(f"unsupported LLM provider: {self.provider!r}")
        self.model = self.model or DEFAULT_MODEL_BY_PROVIDER[self.provider]

    def complete(self, prompt: str, system: str | None = None, temperature: float = 0.2) -> str:
        call = _CALLERS[self.provider]
        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                return call(self, prompt, system, temperature)
            except Exception as exc:  # provider SDKs each raise their own types
                last_error = exc
                if attempt < self.max_retries:
                    time.sleep(self.retry_backoff_seconds * attempt)
        raise LLMError(
            f"{self.provider} completion failed after {self.max_retries} attempts"
        ) from last_error


def client_from_env() -> LLMClient:
    """Reads LLM_PROVIDER / LLM_API_KEY from the process environment.

    Loading .env into the environment is api/config.py's job at startup -
    core/ stays framework-agnostic and just assumes the env is populated.
    """
    api_key = os.environ.get("LLM_API_KEY")
    if not api_key:
        raise LLMError("LLM_API_KEY is not set")
    return LLMClient(provider=os.environ.get("LLM_PROVIDER", "groq"), api_key=api_key)


def _call_groq(client: LLMClient, prompt: str, system: str | None, temperature: float) -> str:
    from groq import Groq

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    response = Groq(api_key=client.api_key).chat.completions.create(
        model=client.model, messages=messages, temperature=temperature
    )
    return response.choices[0].message.content


def _call_gemini(client: LLMClient, prompt: str, system: str | None, temperature: float) -> str:
    from google import genai
    from google.genai import types

    response = genai.Client(api_key=client.api_key).models.generate_content(
        model=client.model,
        contents=prompt,
        config=types.GenerateContentConfig(system_instruction=system, temperature=temperature),
    )
    return response.text


_CALLERS: dict[str, Callable[[LLMClient, str, str | None, float], str]] = {
    "groq": _call_groq,
    "gemini": _call_gemini,
}
