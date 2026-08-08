## 0.1.0 (2026-08-08)

### Notes

- Requires `mcp>=2.0.0`. The old decorator-based `Server` API
  (`@server.list_tools()` etc.) is no longer supported.

### Feat

- **cli**: add --timeout and --log-level options
- **client**: validate max_results range and time_range values
- **server**: migrate to mcp 2.0 constructor-based handler API
- **server**: implement resource info for web search

### Fix

- **server**: validate and coerce raw tool arguments before use
- **adapters**: surface search failures instead of returning empty results

### Refactor

- Update VHS demo example for clarity
- Clean up code structure and remove redundancies
