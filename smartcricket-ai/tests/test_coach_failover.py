"""A busy provider model must not leave the coach waiting through repeated retries."""
import httpx
import pytest

from backend.app import coach
from backend.app.config import settings


MESSAGES = [{"role": "system", "content": "Coach"}, {"role": "user", "content": "How is my knee?"}]


def provider_error(status):
    request = httpx.Request("POST", "https://generativelanguage.googleapis.com/v1beta/models/test:generateContent")
    return httpx.HTTPStatusError("provider error", request=request, response=httpx.Response(status, request=request))


def test_busy_gemini_model_uses_next_fallback(monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "gemini")
    monkeypatch.setattr(settings, "llm_model", "busy-model")
    monkeypatch.setattr(settings, "llm_fallback_models", "working-model,other-model")
    tried = []

    def call(model, body, timeout):
        tried.append(model)
        assert 0 < timeout <= 12
        if model == "busy-model":
            raise provider_error(503)
        return "General tip: watch the ball onto the bat."

    monkeypatch.setattr(coach, "_gemini", call)
    assert coach._call(MESSAGES).startswith("General tip:")
    assert tried == ["busy-model", "working-model"]


def test_rejected_gemini_key_is_reported_separately(monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "gemini")
    monkeypatch.setattr(settings, "llm_model", "test-model")
    monkeypatch.setattr(settings, "llm_fallback_models", "fallback-model")
    tried = []

    def call(model, body, timeout):
        tried.append(model)
        raise provider_error(401)

    monkeypatch.setattr(coach, "_gemini", call)
    with pytest.raises(coach.CoachAuthError):
        coach._call(MESSAGES)
    assert tried == ["test-model"]
