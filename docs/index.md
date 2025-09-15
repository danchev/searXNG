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

## Installation

### Install via pip

```bash
# Install
pip install searXNG

# Get the latest version
pip install -U searXNG
```

## Usage Example

### Configure as an MCP Service

Add the following to your MCP configuration:

```json
"mcpServers": {
  "searxng": {
    "command": "uvx",
    "args": ["searxng", "--instance-url=https://searx.party"]
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
npx @modelcontextprotocol/inspector uv run searxng
```

## License

AGPLv3+ License - see [LICENSE](LICENSE) for details.
