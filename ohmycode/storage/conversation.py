"""Conversation persistence (Task 18) — save and restore conversation history."""

from __future__ import annotations

import json
import random
import string
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

from ohmycode.core.messages import (
    AssistantMessage,
    Message,
    SystemMessage,
    ToolResultMessage,
    ToolUseBlock,
    UserMessage,
)

# ---- Paths ----

CONVERSATIONS_DIR = Path.home() / ".ohmycode" / "conversations"


def _ensure_dir() -> None:
    CONVERSATIONS_DIR.mkdir(parents=True, exist_ok=True)


def generate_conversation_id() -> str:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    rand_suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return f"{timestamp}-{rand_suffix}"


# ---- Serialization helpers ----


def _tool_use_block_to_dict(tub: ToolUseBlock) -> dict:
    return {
        "tool_use_id": tub.tool_use_id,
        "tool_name": tub.tool_name,
        "params": tub.params,
    }


def _tool_use_block_from_dict(d: dict) -> ToolUseBlock:
    return ToolUseBlock(
        tool_use_id=d["tool_use_id"],
        tool_name=d["tool_name"],
        params=d.get("params", {}),
    )


def _msg_to_dict(msg: Message) -> dict:
    """Serialize a Message to a JSON-serializable dict."""
    if isinstance(msg, UserMessage):
        return {"role": "user", "content": msg.content}
    if isinstance(msg, AssistantMessage):
        d: dict = {"role": "assistant", "content": msg.content}
        if msg.tool_calls:
            d["tool_calls"] = [_tool_use_block_to_dict(tc) for tc in msg.tool_calls]
        return d
    if isinstance(msg, ToolResultMessage):
        return {
            "role": "tool",
            "tool_use_id": msg.tool_use_id,
            "content": msg.content,
            "is_error": msg.is_error,
        }
    if isinstance(msg, SystemMessage):
        return {"role": "system", "content": msg.content}
    # Fallback
    return {"role": getattr(msg, "role", "unknown"), "content": getattr(msg, "content", "")}


def _dict_to_msg(d: dict) -> Message:
    """Deserialize a dict back into a Message object."""
    role = d.get("role", "user")
    if role == "user":
        return UserMessage(content=d.get("content", ""))
    if role == "assistant":
        tool_calls = [_tool_use_block_from_dict(tc) for tc in d.get("tool_calls", [])]
        return AssistantMessage(content=d.get("content", ""), tool_calls=tool_calls)
    if role == "tool":
        return ToolResultMessage(
            tool_use_id=d.get("tool_use_id", ""),
            content=d.get("content", ""),
            is_error=d.get("is_error", False),
        )
    if role == "system":
        return SystemMessage(content=d.get("content", ""))
    # Fallback to UserMessage
    return UserMessage(content=d.get("content", ""))


# ---- Public API ----


def save_conversation(
    messages: List[Message],
    provider: str = "",
    model: str = "",
    mode: str = "",
    conversation_id: str = "",
) -> str:
    """Serialize messages to JSON and save to CONVERSATIONS_DIR.

    Returns the filename (not full path).
    Filename format: YYYYMMDD-HHMMSS-<random8>.json
    """
    _ensure_dir()
    filename = f"{conversation_id or generate_conversation_id()}.json"
    filepath = CONVERSATIONS_DIR / filename
    data = {
        "metadata": {
            "provider": provider,
            "model": model,
            "mode": mode,
            "saved_at": datetime.now().isoformat(),
            "message_count": len(messages),
        },
        "messages": [_msg_to_dict(m) for m in messages],
    }
    filepath.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return filename


def load_conversation(
    resume_arg: str = "",
) -> Optional[Tuple[List[Message], dict]]:
    """Load a conversation from disk.

    Args:
        resume_arg: Empty string = most recent conversation.
                    Otherwise, match against filename (prefix or full name).

    Returns:
        (messages, metadata) tuple, or None if not found.
    """
    _ensure_dir()
    all_files = sorted(CONVERSATIONS_DIR.glob("*.json"))
    if not all_files:
        return None

    if resume_arg == "":
        # Most recent
        target = all_files[-1]
    else:
        # Match by filename prefix or exact name
        matched = [f for f in all_files if f.name.startswith(resume_arg) or f.name == resume_arg]
        if not matched:
            return None
        target = matched[-1]

    try:
        raw = target.read_text(encoding="utf-8")
        data = json.loads(raw)
    except Exception:
        return None

    metadata = data.get("metadata", {})
    metadata["filename"] = target.name
    messages_raw = data.get("messages", [])
    messages = [_dict_to_msg(d) for d in messages_raw]
    return messages, metadata
