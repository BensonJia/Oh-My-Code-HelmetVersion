"""Tests for the OpenAI-compatible provider."""

import pytest

from ohmycode.providers.base import PROVIDER_REGISTRY


def test_openai_provider_is_registered():
    import ohmycode.providers.openai  # noqa: F401
    assert "openai" in PROVIDER_REGISTRY


def test_openai_provider_instantiation():
    from ohmycode.providers.openai import OpenAIProvider

    provider = OpenAIProvider(
        api_key="test-key",
        base_url="http://localhost:8080/v1",
    )
    assert provider.name == "openai"
