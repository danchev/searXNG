from .server import serve


def main():
    """SearXNG MCP Server - Web search functionality for MCP"""
    import argparse
    import asyncio

    parser = argparse.ArgumentParser(
        description="MCP server that provides network search capabilities for models"
    )
    parser.add_argument("--instance-url", default="https://searx.party",
                        help="SearXNG instance URL (default: https://searx.party)")
    args = parser.parse_args()

    asyncio.run(serve(instance_url=args.instance_url))


if __name__ == "__main__":
    main()
