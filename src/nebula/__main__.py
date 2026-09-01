"""Entry point: `uv run nebula` or `python -m nebula`."""

import argparse

from nebula.app import run


def main() -> None:
    parser = argparse.ArgumentParser(prog="nebula")
    parser.add_argument(
        "--dev",
        action="store_true",
        help="load the Vite dev server instead of the built frontend",
    )
    args = parser.parse_args()
    run(dev=args.dev)


if __name__ == "__main__":
    main()
