from pathlib import Path


def test_setup_cli_ps1_exists_and_has_windows_install_steps():
    script = Path("scripts/setup-cli.ps1")
    assert script.is_file()
    content = script.read_text(encoding="utf-8")
    assert 'pip install -e ".[dev]"' in content
    assert "ohmycode.cmd" in content
    assert "ohmycode.ps1" in content
    assert "SetEnvironmentVariable" in content
