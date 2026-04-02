# tests/conftest.py
"""Shared test fixtures for OhMyCode."""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncIterator

import pytest

from ohmycode.core.messages import TextChunk, TokenUsage, TurnComplete


class MockProvider:
    name = "mock"

    def __init__(self, responses=None, **kwargs):
        self.responses = responses or ["Hello from mock!"]
        self._call_count = 0

    async def stream(self, messages, tools, system, model, **kwargs):
        idx = min(self._call_count, len(self.responses) - 1)
        self._call_count += 1
        yield TextChunk(text=self.responses[idx])
        yield TurnComplete(finish_reason="stop", usage=TokenUsage(10, 5, 15))

    async def complete(self, messages, model, system_prompt="", tools=None, **kwargs):
        idx = min(self._call_count, len(self.responses) - 1)
        self._call_count += 1
        return self.responses[idx]


@pytest.fixture
def mock_provider():
    return MockProvider()


@pytest.fixture
def tmp_dir(tmp_path: Path) -> Path:
    """Provide a clean temporary directory for file-based tests."""
    return tmp_path


@pytest.fixture
def mock_config(tmp_path: Path) -> dict:
    """Return a minimal config dict for testing."""
    return {
        "provider": "openai",
        "model": "gpt-4o-mini",
        "mode": "auto",
        "max_turns": 10,
        "token_budget": 4096,
        "output_tokens_reserved": 1024,
        "rules": [],
        "base_url": "http://35.164.11.19:3887/v1",
        "api_key": "test-key",
    }
