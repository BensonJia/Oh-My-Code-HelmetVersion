"""Provider protocol definitions and registry."""

from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path
from typing import Any, AsyncIterator, Protocol, runtime_checkable

from ohmycode.core.messages import Message, StreamEvent


class ToolDef:
    """Tool definition sent to the LLM API."""

    def __init__(self, name: str, description: str, parameters: dict):
        self.name = name
        self.description = description
        self.parameters = parameters

    def to_api_dict(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


@runtime_checkable
class Provider(Protocol):
    name: str

    async def stream(
        self,
        messages: list[Message],
        tools: list[ToolDef],
        system: str,
        model: str,
        **kwargs: Any,
    ) -> AsyncIterator[StreamEvent]: ...

    async def complete(
        self,
        messages: list[Any],
        model: str,
        system_prompt: str = "",
        tools: list[Any] | None = None,
        **kwargs: Any,
    ) -> Any: ...


PROVIDER_REGISTRY: dict[str, type] = {}


def register_provider(name: str, cls: type) -> None:
    PROVIDER_REGISTRY[name] = cls


def get_provider(name: str, **kwargs: Any) -> Any:
    if name not in PROVIDER_REGISTRY:
        raise ValueError(
            f"Unknown provider: '{name}'. Available: {list(PROVIDER_REGISTRY.keys())}"
        )
    return PROVIDER_REGISTRY[name](**kwargs)


def auto_import_providers() -> None:
    package_dir = Path(__file__).parent
    for module_info in pkgutil.iter_modules([str(package_dir)]):
        if module_info.name != "base":
            importlib.import_module(f"ohmycode.providers.{module_info.name}")
