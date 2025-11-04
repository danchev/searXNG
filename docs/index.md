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
    - `max_results` (integer): Maximum number of results, default is 10
    - `time_range` (string): Time range filter ('day', 'week', 'month', 'year')

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
