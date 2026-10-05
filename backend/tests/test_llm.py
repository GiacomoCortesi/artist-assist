"""LLM provider selection tests (mocked SDKs)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest


@pytest.fixture(autouse=True)
def clear_settings(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ENVIRONMENT", "test")
    from app.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_llm_live_alias_openai_live(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_LIVE", "1")
    monkeypatch.delenv("LLM_LIVE", raising=False)
    from app.config import get_settings

    get_settings.cache_clear()
    assert get_settings().llm_live == 1


def test_complete_chat_openai(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_LIVE", "1")
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    class FakeCompletions:
        def create(self, **kwargs):
            assert kwargs["model"] == "gpt-4o-mini"
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content="openai caption"))]
            )

    class FakeClient:
        def __init__(self, **kwargs):
            assert kwargs["api_key"] == "sk-test"
            self.chat = SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setattr("app.agent.llm.OpenAI", FakeClient)

    from app.agent.llm import complete_chat
    from app.config import get_settings

    get_settings.cache_clear()
    text = complete_chat(user_content="hello", settings=get_settings())
    assert text == "openai caption"


def test_complete_chat_anthropic(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_LIVE", "1")
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "ant-test")
    monkeypatch.setenv("ANTHROPIC_CHAT_MODEL", "claude-sonnet-4-6")

    class FakeMessages:
        def create(self, **kwargs):
            assert kwargs["model"] == "claude-sonnet-4-6"
            assert kwargs["system"]
            return SimpleNamespace(
                content=[SimpleNamespace(type="text", text="claude caption")]
            )

    class FakeClient:
        def __init__(self, **kwargs):
            assert kwargs["api_key"] == "ant-test"
            self.messages = FakeMessages()

    monkeypatch.setattr("app.agent.llm.Anthropic", FakeClient)

    from app.agent.llm import complete_chat
    from app.config import get_settings

    get_settings.cache_clear()
    text = complete_chat(user_content="hello", settings=get_settings())
    assert text == "claude caption"


def test_llm_not_configured_without_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_LIVE", "1")
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    from app.agent.llm import llm_configured
    from app.config import get_settings

    get_settings.cache_clear()
    assert llm_configured(get_settings()) is False
