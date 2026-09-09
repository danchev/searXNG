## 0.1.2 (2026-09-09)

### CI

- Keep real-socket integration tests on POSIX, where their asyncio connection
  teardown semantics are deterministic; the unit suite remains cross-platform.

## 0.1.1 (2026-09-09)

### Fix

- Bound upstream responses to 2 MiB and concurrent searches to eight per process;
  excess searches fail immediately instead of queuing.
- Use cancellable async HTTP with a total network deadline.
- Reject malformed search responses and invalid `time_range` types with tool errors.
- Remove queries and upstream exception details from application logs; suppress
  HTTP dependency INFO/DEBUG logs in the CLI.

### Compatibility

- `HttpSearchAdapter` now accepts an `httpx2.AsyncClient` instead of a
  `requests.Session`. Its `close()` method must be awaited.
- Instances must serve `/search` directly and honor `Accept-Encoding: identity`;
  redirects and compressed responses are rejected.

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
