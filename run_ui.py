"""Deprecated entrypoint: use React UI (make ui-dev or make up)."""

from __future__ import annotations

import sys


def main() -> None:
    print(
        "Gradio UI was removed. Use the React UI instead:\n"
        "  make up      # Docker stack with web UI on :8080\n"
        "  make ui-dev  # local Vite dev server on :5173",
        file=sys.stderr,
    )
    raise SystemExit(1)


if __name__ == "__main__":
    main()
