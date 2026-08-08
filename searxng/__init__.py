import argparse
import asyncio
import logging
import sys

from searxng.server import DEFAULT_INSTANCE_URL, serve

DEFAULT_TIMEOUT = 30


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="searxng",
        description="MCP server that provides network search capabilities for models",
    )
    parser.add_argument(
        "--instance-url",
        default=DEFAULT_INSTANCE_URL,
        help=f"SearXNG instance URL (default: {DEFAULT_INSTANCE_URL})",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help=f"Search request timeout in seconds (default: {DEFAULT_TIMEOUT})",
    )
    parser.add_argument(
        "--log-level",
        default="WARNING",
        choices=("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"),
        help="Logging verbosity (default: WARNING)",
    )
    return parser


def main() -> None:
    """SearXNG MCP Server - Web search functionality for MCP"""
    parser = _build_parser()
    args = parser.parse_args()

    # stdout carries the MCP protocol, so logs must go to stderr.
    logging.basicConfig(
        level=args.log_level,
        stream=sys.stderr,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if args.timeout <= 0:
        parser.error("--timeout must be a positive number of seconds")

    try:
        asyncio.run(serve(instance_url=args.instance_url, timeout=args.timeout))
    except KeyboardInterrupt:
        pass
    except ValueError as e:
        # e.g. a malformed --instance-url, validated lazily inside serve().
        # Caught here so the user sees a one-line message, not a traceback.
        parser.error(str(e))


if __name__ == "__main__":
    main()
