"""Tests for the provider protocol and registry."""

from ohmycode.providers.base import (
    PROVIDER_REGISTRY,
    Provider,
    get_provider,
    register_provider,
)


class FakeProvider:
    name = "fake"

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    async def stream(self, messages, tools, system, model, **kwargs):
        yield {"type": "text", "text": "hello"}


def test_register_and_get_provider():
    register_provider("fake", FakeProvider)
    assert "fake" in PROVIDER_REGISTRY
    provider = get_provider("fake", api_key="test")
    assert isinstance(provider, FakeProvider)
    assert provider.kwargs["api_key"] == "test"


def test_get_unknown_provider_raises():
    import pytest

    with pytest.raises(ValueError, match="Unknown provider"):
        get_provider("nonexistent_xyz")
