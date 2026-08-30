import pytest

from core import llm
from core.llm import LLMClient, LLMError, client_from_env


def test_unsupported_provider_rejected():
    with pytest.raises(ValueError, match="unsupported LLM provider"):
        LLMClient(provider="chatgpt", api_key="x")


def test_default_model_assigned_per_provider():
    assert LLMClient(provider="groq", api_key="x").model == "llama-3.3-70b-versatile"
    assert LLMClient(provider="gemini", api_key="x").model == "gemini-2.0-flash"


def test_explicit_model_overrides_default():
    client = LLMClient(provider="groq", api_key="x", model="custom-model")
    assert client.model == "custom-model"


def test_complete_returns_result_on_first_success(monkeypatch):
    monkeypatch.setitem(llm._CALLERS, "groq", lambda client, prompt, system, temp: "hello")
    client = LLMClient(provider="groq", api_key="x")
    assert client.complete("hi") == "hello"


def test_complete_retries_then_succeeds(monkeypatch):
    monkeypatch.setattr(llm.time, "sleep", lambda seconds: None)
    calls = {"count": 0}

    def flaky(client, prompt, system, temp):
        calls["count"] += 1
        if calls["count"] < 3:
            raise RuntimeError("rate limited")
        return "ok"

    monkeypatch.setitem(llm._CALLERS, "groq", flaky)
    client = LLMClient(provider="groq", api_key="x", max_retries=3)

    assert client.complete("hi") == "ok"
    assert calls["count"] == 3


def test_complete_raises_llm_error_after_exhausting_retries(monkeypatch):
    monkeypatch.setattr(llm.time, "sleep", lambda seconds: None)

    def always_fails(client, prompt, system, temp):
        raise RuntimeError("still down")

    monkeypatch.setitem(llm._CALLERS, "groq", always_fails)
    client = LLMClient(provider="groq", api_key="x", max_retries=2)

    with pytest.raises(LLMError) as exc_info:
        client.complete("hi")
    assert isinstance(exc_info.value.__cause__, RuntimeError)


def test_client_from_env_reads_provider_and_key(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("LLM_API_KEY", "secret")
    client = client_from_env()
    assert client.provider == "gemini"
    assert client.api_key == "secret"


def test_client_from_env_defaults_provider_to_groq(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.setenv("LLM_API_KEY", "secret")
    assert client_from_env().provider == "groq"


def test_client_from_env_requires_api_key(monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    with pytest.raises(LLMError, match="LLM_API_KEY"):
        client_from_env()
