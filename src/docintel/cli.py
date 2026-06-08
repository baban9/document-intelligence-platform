"""CLI entry point."""

import argparse

from docintel.app import create_app
from docintel.config import Config


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the document intelligence API.")
    parser.add_argument("--host", default=Config.HOST)
    parser.add_argument("--port", type=int, default=Config.PORT)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    app = create_app()
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
