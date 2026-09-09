"""Infrastructure adapters - HTTP client and external integrations."""

import asyncio
import json
import logging
import math
from dataclasses import dataclass
from itertools import islice
from typing import Any
from urllib.parse import urlparse

import httpx2

from searxng.client import (
    ResultIndex,
    SearchError,
    SearchParameters,
    SearchQuery,
    SearchResult,
    SearchResultCollection,
    SearchResultContent,
    SearchResultTitle,
    SearchResultUrl,
)

# Upper bounds on individual result fields, chosen well above what real
# instances return so ordinary results are never altered. They exist only
# to bound the worst case, where an oversized response from a misbehaving
# instance would otherwise be forwarded verbatim into the model's context.
MAX_TITLE_CHARS = 500
MAX_URL_CHARS = 2000
MAX_CONTENT_CHARS = 2000
TRUNCATION_MARKER = "…[truncated]"
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_CONCURRENT_SEARCHES = 8


@dataclass(frozen=True)
class InstanceUrl:
    """Value object representing a SearXNG instance URL."""

    value: str

    def __post_init__(self) -> None:
        if not self.value or not self.value.strip():
            raise ValueError("Instance URL cannot be empty")

        stripped = self.value.strip()
        if stripped != self.value:
            raise ValueError(
                f"Instance URL must not have leading or trailing whitespace, "
                f"got: {self.value!r}"
            )

        parsed = urlparse(self.value)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValueError(
                f"Instance URL must be an absolute http(s) URL, got: {self.value}"
            )

        # Normalise so joining "/search" never produces a double slash.
        object.__setattr__(self, "value", self.value.rstrip("/"))


@dataclass(frozen=True)
class SearchTimeout:
    """Value object representing search timeout."""

    seconds: float

    def __post_init__(self) -> None:
        # bool is a subclass of int, but is never a meaningful timeout.
        if isinstance(self.seconds, bool):
            raise ValueError("Timeout must be a number, not a bool")  # noqa: TRY004
        if not math.isfinite(self.seconds) or self.seconds <= 0:
            raise ValueError("Timeout must be positive")


class HttpSearchAdapter:
    """Adapter for HTTP-based search using SearXNG."""

    def __init__(
        self,
        instance_url: str = "https://searx.party",
        timeout: float = 30,
        session: httpx2.AsyncClient | None = None,
    ) -> None:
        self._instance_url = InstanceUrl(value=instance_url)
        self._timeout = SearchTimeout(seconds=timeout)
        self._session = session or httpx2.AsyncClient(
            limits=httpx2.Limits(max_connections=MAX_CONCURRENT_SEARCHES),
        )
        self._slots = asyncio.Semaphore(MAX_CONCURRENT_SEARCHES)
        self._logger = logging.getLogger(__name__)

    async def search(
        self, query: SearchQuery, parameters: SearchParameters
    ) -> SearchResultCollection:
        """Search with bounded admission and a cancellable network deadline."""
        # No waiting queue: overload must not accumulate unbounded tasks.
        # This check and acquire have no intervening suspension when available.
        if self._slots.locked():
            raise SearchError("Search capacity reached; retry later")
        async with self._slots:
            try:
                async with asyncio.timeout(self._timeout.seconds):
                    raw_results = await self._execute_request(
                        f"{self._instance_url.value}/search",
                        self._build_request_params(query, parameters),
                    )
                    return self._map_to_domain(
                        query, raw_results, parameters.max_results
                    )
            except (TimeoutError, httpx2.TimeoutException) as e:
                raise SearchError(
                    f"Search timed out after {self._timeout.seconds}s"
                ) from e
            except httpx2.HTTPStatusError as e:
                raise SearchError(
                    f"Search request failed: HTTP {e.response.status_code}"
                ) from e
            except httpx2.RequestError as e:
                # Exception messages can include URLs, credentials and queries.
                raise SearchError("Search request failed: network error") from e
            except (ValueError, RecursionError) as e:
                raise SearchError("Invalid response from search instance") from e

    def _build_request_params(
        self, query: SearchQuery, parameters: SearchParameters
    ) -> dict[str, Any]:
        """Build HTTP request parameters."""
        params: dict[str, Any] = {
            "q": query.text,
            "format": "json",
            "language": parameters.language,
            "safesearch": 1,
            "pageno": 1,
        }

        if parameters.categories:
            params["categories"] = ",".join(parameters.categories)

        if parameters.engines:
            params["engines"] = ",".join(parameters.engines)

        if parameters.time_range:
            params["time_range"] = parameters.time_range

        return params

    async def _execute_request(
        self, url: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Bound raw response bytes before decoding or parsing untrusted data."""
        async with self._session.stream(
            "GET",
            url,
            params=params,
            timeout=self._timeout.seconds,
            headers={"Accept-Encoding": "identity"},
            follow_redirects=False,
        ) as response:
            response.raise_for_status()
            # Reject compression instead of allowing decompression to allocate
            # an arbitrarily large buffer before we can enforce the byte limit.
            if (
                response.headers.get("content-encoding", "identity").lower()
                != "identity"
            ):
                raise SearchError(
                    "Search instance returned unsupported content encoding"
                )
            length = response.headers.get("content-length")
            if length is not None and int(length) > MAX_RESPONSE_BYTES:
                raise SearchError("Search response exceeds 2 MiB limit")
            body = bytearray()
            async for chunk in response.aiter_raw():
                if len(body) + len(chunk) > MAX_RESPONSE_BYTES:
                    raise SearchError("Search response exceeds 2 MiB limit")
                body.extend(chunk)

        results = json.loads(body)
        if (
            not isinstance(results, dict)
            or not isinstance(results.get("results"), list)
            or results.get("error")
            or results.get("errors")
        ):
            raise ValueError("Invalid search response structure")
        self._logger.info("Search completed: %d results", len(results["results"]))
        return results

    async def close(self) -> None:
        """Release the underlying HTTP connection pool."""
        await self._session.aclose()

    def _map_to_domain(
        self, query: SearchQuery, raw_data: dict[str, Any], max_results: int
    ) -> SearchResultCollection:
        """Map raw API response to domain model."""
        results = raw_data["results"]

        domain_results = [
            self._create_domain_result(index, result)
            for index, result in enumerate(
                islice((r for r in results if isinstance(r, dict)), max_results)
            )
        ]

        return SearchResultCollection(query=query, results=tuple(domain_results))

    def _create_domain_result(
        self, index: int, raw_result: dict[str, Any]
    ) -> SearchResult:
        """Create domain result from raw data."""
        return SearchResult(
            index=ResultIndex(value=index),
            title=SearchResultTitle(
                value=_as_text(raw_result.get("title"), MAX_TITLE_CHARS)
            ),
            url=SearchResultUrl(value=_as_text(raw_result.get("url"), MAX_URL_CHARS)),
            content=SearchResultContent(
                value=_as_text(raw_result.get("content"), MAX_CONTENT_CHARS)
            ),
        )


def _as_text(value: Any, limit: int) -> str:
    """Coerce a raw JSON field to a string, treating null as empty.

    Truncates at ``limit`` characters. Result fields come from whichever
    instance the operator points at, and are forwarded verbatim into the
    model's context, so an oversized response would otherwise be able to
    exhaust the context window. The limits are far above what real
    instances return, so legitimate results pass through untouched.
    """
    if value is None:
        return ""
    text = value if isinstance(value, str) else str(value)
    if len(text) <= limit:
        return text
    return text[:limit] + TRUNCATION_MARKER
