"""Tests for CLI argument parsing."""

import pytest

from ohmycode.cli import parse_args


def test_parse_args_rejects_llm_cli_overrides():
    with pytest.raises(SystemExit):
        parse_args(["--provider", "openai"])
