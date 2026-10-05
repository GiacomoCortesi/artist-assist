"""LLM chat completions — OpenAI or Anthropic (Claude), with optional tools."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from anthropic import Anthropic
from openai import OpenAI
from sqlalchemy.orm import Session

from app.agent.tools import ToolContext, anthropic_tool_defs, execute_tool, openai_tool_defs
from app.config import Settings, get_settings

SYSTEM_PROMPT = (
    "You are ArtistAssist, an interactive content co-designer for one musician. "
    "Chat turn-by-turn. Use tools for facts (posts, comments, context docs, releases) and "
    "to save drafts with upsert_draft when the user wants an exportable caption. "
    "Synced comments include full text plus sentiment/theme tags — call query_comments "
    "to review praise, complaints, questions, or negativity; do not claim you only have "
    "aggregate metrics. query_posts returns counts/captions only. "
    "TikTok has no comment text. Do not dump full databases into replies — call tools. "
    "Never invent dates, links, metrics, or comment wording. Never claim content was published. "
    "Ask clarifying questions when the brief is vague."
)

_MAX_TOOL_ROUNDS = 6

EventCallback = Callable[[str, dict[str, Any]], None]


class LlmError(RuntimeError):
    """Live LLM call failed or is misconfigured."""


def llm_configured(settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    if not settings.llm_live:
        return False
    if settings.llm_provider == "anthropic":
        return bool(settings.anthropic_api_key)
    if settings.llm_provider == "openai":
        return bool(settings.openai_api_key)
    raise LlmError(f"Unknown LLM provider: {settings.llm_provider}")


def complete_chat(
    *,
    user_content: str,
    system_content: str = SYSTEM_PROMPT,
    settings: Settings | None = None,
) -> str:
    """Return assistant text from the configured live provider (no tools)."""
    settings = settings or get_settings()
    if not llm_configured(settings):
        raise LlmError("LLM not configured for live calls")

    if settings.llm_provider == "openai":
        return _openai_chat(settings, system_content=system_content, user_content=user_content)
    if settings.llm_provider == "anthropic":
        return _anthropic_chat(settings, system_content=system_content, user_content=user_content)
    raise LlmError(f"Unknown LLM provider: {settings.llm_provider}")


def run_tool_loop(
    *,
    session: Session,
    messages: list[dict[str, Any]],
    system_content: str = SYSTEM_PROMPT,
    settings: Settings | None = None,
    tool_executor: Callable[..., str] | None = None,
    tool_ctx: ToolContext | None = None,
    on_event: EventCallback | None = None,
) -> str:
    """Multi-turn tool loop. `messages` are OpenAI-style (no system message)."""
    settings = settings or get_settings()
    if not llm_configured(settings):
        raise LlmError("LLM not configured for live calls")
    ctx = tool_ctx or ToolContext(session)
    executor = tool_executor or (
        lambda s, name, args: execute_tool(s, name, args, ctx=ctx)
    )

    if settings.llm_provider == "openai":
        return _openai_chat_with_tools(
            settings,
            session=session,
            system_content=system_content,
            messages=list(messages),
            tool_executor=executor,
            on_event=on_event,
        )
    if settings.llm_provider == "anthropic":
        return _anthropic_chat_with_tools(
            settings,
            session=session,
            system_content=system_content,
            messages=list(messages),
            tool_executor=executor,
            on_event=on_event,
        )
    raise LlmError(f"Unknown LLM provider: {settings.llm_provider}")


def _emit(on_event: EventCallback | None, event_type: str, data: dict[str, Any]) -> None:
    if on_event is not None:
        on_event(event_type, data)


def _openai_chat(settings: Settings, *, system_content: str, user_content: str) -> str:
    client = OpenAI(api_key=settings.openai_api_key)
    completion = client.chat.completions.create(
        model=settings.openai_chat_model,
        messages=[
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_content},
        ],
    )
    return completion.choices[0].message.content or ""


def _anthropic_chat(settings: Settings, *, system_content: str, user_content: str) -> str:
    client = Anthropic(api_key=settings.anthropic_api_key)
    message = client.messages.create(
        model=settings.anthropic_chat_model,
        max_tokens=2048,
        system=system_content,
        messages=[{"role": "user", "content": user_content}],
    )
    parts: list[str] = []
    for block in message.content:
        if getattr(block, "type", None) == "text":
            parts.append(getattr(block, "text", "") or "")
    return "".join(parts)


def _parse_tool_args(raw: str | dict[str, Any] | None) -> dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        parsed = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _openai_chat_with_tools(
    settings: Settings,
    *,
    session: Session,
    system_content: str,
    messages: list[dict[str, Any]],
    tool_executor: Callable[..., str],
    on_event: EventCallback | None = None,
) -> str:
    client = OpenAI(api_key=settings.openai_api_key)
    working: list[dict[str, Any]] = [
        {"role": "system", "content": system_content},
        *messages,
    ]
    tools = openai_tool_defs()

    for _ in range(_MAX_TOOL_ROUNDS):
        completion = client.chat.completions.create(
            model=settings.openai_chat_model,
            messages=working,
            tools=tools,
            tool_choice="auto",
        )
        message = completion.choices[0].message
        tool_calls = getattr(message, "tool_calls", None) or []
        if not tool_calls:
            text = message.content or ""
            _emit(on_event, "message", {"content": text})
            return text

        working.append(
            {
                "role": "assistant",
                "content": message.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments or "{}",
                        },
                    }
                    for tc in tool_calls
                ],
            }
        )
        for tc in tool_calls:
            args = _parse_tool_args(tc.function.arguments)
            _emit(on_event, "tool_start", {"name": tc.function.name, "arguments": args})
            result = tool_executor(session, tc.function.name, args)
            _emit(
                on_event,
                "tool_result",
                {"name": tc.function.name, "content": result[:2000]},
            )
            working.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                }
            )

    completion = client.chat.completions.create(
        model=settings.openai_chat_model,
        messages=working,
    )
    text = completion.choices[0].message.content or ""
    _emit(on_event, "message", {"content": text})
    return text


def _to_anthropic_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert OpenAI-style history (including tool roles) to Anthropic messages."""
    out: list[dict[str, Any]] = []
    i = 0
    while i < len(messages):
        msg = messages[i]
        role = msg.get("role")
        if role == "user":
            out.append({"role": "user", "content": msg.get("content") or ""})
            i += 1
            continue
        if role == "assistant":
            content_blocks: list[dict[str, Any]] = []
            text = msg.get("content")
            if text:
                content_blocks.append({"type": "text", "text": text})
            for tc in msg.get("tool_calls") or []:
                fn = tc.get("function") or {}
                content_blocks.append(
                    {
                        "type": "tool_use",
                        "id": tc.get("id"),
                        "name": fn.get("name"),
                        "input": _parse_tool_args(fn.get("arguments")),
                    }
                )
            if content_blocks:
                out.append({"role": "assistant", "content": content_blocks})
            i += 1
            # Collect following tool results into one user message
            tool_results: list[dict[str, Any]] = []
            while i < len(messages) and messages[i].get("role") == "tool":
                t = messages[i]
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": t.get("tool_call_id"),
                        "content": t.get("content") or "",
                    }
                )
                i += 1
            if tool_results:
                out.append({"role": "user", "content": tool_results})
            continue
        if role == "tool":
            # Orphan tool message — wrap alone
            out.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": msg.get("tool_call_id"),
                            "content": msg.get("content") or "",
                        }
                    ],
                }
            )
            i += 1
            continue
        i += 1
    return out


def _anthropic_chat_with_tools(
    settings: Settings,
    *,
    session: Session,
    system_content: str,
    messages: list[dict[str, Any]],
    tool_executor: Callable[..., str],
    on_event: EventCallback | None = None,
) -> str:
    client = Anthropic(api_key=settings.anthropic_api_key)
    # Keep an OpenAI-shaped working copy so conversion stays consistent
    working = list(messages)
    tools = anthropic_tool_defs()

    for _ in range(_MAX_TOOL_ROUNDS):
        message = client.messages.create(
            model=settings.anthropic_chat_model,
            max_tokens=2048,
            system=system_content,
            messages=_to_anthropic_messages(working),
            tools=tools,
        )
        content_blocks = list(message.content)
        tool_uses = [b for b in content_blocks if getattr(b, "type", None) == "tool_use"]
        if not tool_uses or message.stop_reason == "end_turn":
            parts: list[str] = []
            for block in content_blocks:
                if getattr(block, "type", None) == "text":
                    parts.append(getattr(block, "text", "") or "")
            text = "".join(parts)
            if parts or not tool_uses:
                _emit(on_event, "message", {"content": text})
                return text

        assistant_openai: dict[str, Any] = {
            "role": "assistant",
            "content": "".join(
                getattr(b, "text", "") or ""
                for b in content_blocks
                if getattr(b, "type", None) == "text"
            )
            or None,
            "tool_calls": [
                {
                    "id": block.id,
                    "type": "function",
                    "function": {
                        "name": block.name,
                        "arguments": json.dumps(getattr(block, "input", {}) or {}),
                    },
                }
                for block in tool_uses
            ],
        }
        working.append(assistant_openai)

        for block in tool_uses:
            args = _parse_tool_args(getattr(block, "input", None))
            _emit(on_event, "tool_start", {"name": block.name, "arguments": args})
            result = tool_executor(session, block.name, args)
            _emit(on_event, "tool_result", {"name": block.name, "content": result[:2000]})
            working.append(
                {
                    "role": "tool",
                    "tool_call_id": block.id,
                    "content": result,
                }
            )

    message = client.messages.create(
        model=settings.anthropic_chat_model,
        max_tokens=2048,
        system=system_content,
        messages=_to_anthropic_messages(working),
    )
    parts = []
    for block in message.content:
        if getattr(block, "type", None) == "text":
            parts.append(getattr(block, "text", "") or "")
    text = "".join(parts)
    _emit(on_event, "message", {"content": text})
    return text
