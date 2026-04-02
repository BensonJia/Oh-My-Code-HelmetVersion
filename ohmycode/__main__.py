"""Entry point for the `ohmycode` CLI."""

import sys


def main() -> None:
    """CLI entry point. Delegates to cli.run()."""
    from ohmycode.cli import run

    sys.exit(run())


if __name__ == "__main__":
    main()
