[![PyPI Version](https://img.shields.io/pypi/v/searxng.svg)](https://pypi.org/project/searxng)
[![License](https://img.shields.io/pypi/l/searxng.svg)](https://pypi.org/project/searxng)
[![PyPI Downloads](https://static.pepy.tech/personalized-badge/searxng?period=total&units=INTERNATIONAL_SYSTEM&left_color=GRAY&right_color=BLUE&left_text=downloads)](https://pypi.org/project/searxng)

# searXNG

A network search server based on MCP technology, providing privacy-friendly web search functionality using the [SearXNG](https://github.com/searxng/searxng) search engine.

## Features

This server provides the following main features:

- Web search via multiple search engines
- Supports various search categories (general, images, news, etc.)
- Customizable search engine selection
- Language filtering
- Time range filtering
- Control over the number of search results

## Available Tools

- `web_search` - Perform web search using SearXNG
  - Required parameters:
    - `query` (string): The search query
  - Optional parameters:
    - `categories` (array): Search categories, e.g. ['general', 'images', 'news']
    - `engines` (array): Search engines, e.g. ['google', 'bing', 'duckduckgo']
    - `language` (string): Language code for search, default is "en"
    - `max_results` (integer): Maximum number of results, default is 10 (1-100)
    - `time_range` (string): Time range filter ('day', 'week', 'month', 'year')

If a search cannot be completed (the instance is unreachable, rate-limits the
request, or returns a malformed response), the tool returns an error result
describing the failure rather than an empty result list.

## Command Line Options

| Option | Default | Description |
| --- | --- | --- |
| `--instance-url` | `https://searx.party` | SearXNG instance to query. Must be an absolute `http(s)` URL. |
| `--timeout` | `30` | Per-search request timeout, in seconds. |
| `--log-level` | `WARNING` | Logging verbosity: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`. Logs are written to stderr. |
| `--transport` | `stdio` | Transport to serve on: `stdio` or `http`. |
| `--host` | `127.0.0.1` | Host to bind when `--transport=http`. |
| `--port` | `8000` | Port to bind when `--transport=http`. |

## Transports

By default the server speaks **stdio**, which is what local MCP clients
(Claude Desktop, IDE integrations, `uvx`) launch it with.

For remote access, `--transport http` serves the **Streamable HTTP**
transport at `/mcp`:

```bash
searxng --transport http --host 127.0.0.1 --port 8000
# endpoint: http://127.0.0.1:8000/mcp
```

> The legacy SSE transport is intentionally not implemented. It was
> superseded by Streamable HTTP in the 2025-03-26 MCP protocol revision
> and should not be used for new deployments.

**Security:** the server performs no authentication, so it binds to
`127.0.0.1` by default. Only pass `--host 0.0.0.0` on a trusted network,
or put an authenticating reverse proxy in front of it.

## Usage Example

### Configure as an MCP Service

To set up SearXNG as an MCP server, add one of the following to your MCP configuration file:

**UVX setup:**
```json
"mcpServers": {
  "searxng": {
    "command": "uvx",
    "args": ["searxng", "--instance-url=https://searx.party"]
  }
}
```

**Docker setup:**
```json
"mcpServers": {
  "searxng": {
    "command": "docker",
    "args": [
      "run",
      "-i",
      "--rm",
      "supercorp/supergateway:uvx",
      "--stdio",
      "uvx searxng --instance-url=https://searx.party"
    ]
  }
}
```

### Example Invocation

1.
```json
{
  "name": "web_search",
  "arguments": {
    "query": "climate change research",
    "categories": ["general"],
    "engines": ["google"],
    "language": "en",
    "max_results": 15,
    "time_range": "month"
  }
}
```

## Debugging

You can use the MCP inspector to debug the server:

```bash
npx @modelcontextprotocol/inspector uvx searxng
```

## License

AGPLv3+ License - see [LICENSE](LICENSE) for details.
