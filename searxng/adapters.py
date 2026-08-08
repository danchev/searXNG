"""Infrastructure adapters - HTTP client and external integrations."""

import asyncio
import logging
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import requests

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
        if self.seconds <= 0:
            raise ValueError("Timeout must be positive")


class HttpSearchAdapter:
    """Adapter for HTTP-based search using SearXNG."""

    def __init__(
        self,
        instance_url: str = "https://searx.party",
        timeout: float = 30,
        session: requests.Session | None = None,
    ) -> None:
        self._instance_url = InstanceUrl(value=instance_url)
        self._timeout = SearchTimeout(seconds=timeout)
        self._session = session or requests.Session()
        self._logger = logging.getLogger(__name__)

    async def search(
        self, query: SearchQuery, parameters: SearchParameters
    ) -> SearchResultCollection:
        """Execute search and return results.

        ``requests`` is blocking, so the call is offloaded to a worker thread to
        keep the server's event loop responsive to concurrent requests.
        """
        self._logger.info("Start search: %s", query.text)

        request_params = self._build_request_params(query, parameters)
        search_url = f"{self._instance_url.value}/search"

        try:
            raw_results = await asyncio.to_thread(
                self._execute_request, search_url, request_params
            )
        except requests.Timeout as e:
            raise SearchError(f"Search timed out after {self._timeout.seconds}s") from e
        except requests.RequestException as e:
            raise SearchError(f"Search request failed: {e}") from e
        except ValueError as e:
            raise SearchError(f"Invalid response from search instance: {e}") from e

        return self._map_to_domain(query, raw_results, parameters.max_results)

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

    def _execute_request(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        """Execute HTTP request. Blocking - call via a worker thread."""
        self._logger.debug("Request URL: %s Parameters: %s", url, params)
        response = self._session.get(url, params=params, timeout=self._timeout.seconds)
        response.raise_for_status()

        results = response.json()
        if not isinstance(results, dict):
            # ValueError, not TypeError: search() maps decode failures (which
            # json() also raises as ValueError) onto a single SearchError.
            raise ValueError(  # noqa: TRY004
                f"Expected a JSON object, got {type(results).__name__}"
            )

        self._logger.info("Got %d results", len(results.get("results", [])))
        return results

    def close(self) -> None:
        """Release the underlying HTTP connection pool."""
        self._session.close()

    def _map_to_domain(
        self, query: SearchQuery, raw_data: dict[str, Any], max_results: int
    ) -> SearchResultCollection:
        """Map raw API response to domain model."""
        results = raw_data.get("results") or []
        if not isinstance(results, list):
            self._logger.warning("Unexpected 'results' payload; treating as empty")
            results = []

        domain_results = [
            self._create_domain_result(index, result)
            for index, result in enumerate(
                [r for r in results if isinstance(r, dict)][:max_results]
            )
        ]

        return SearchResultCollection(query=query, results=tuple(domain_results))

    def _create_domain_result(
        self, index: int, raw_result: dict[str, Any]
    ) -> SearchResult:
        """Create domain result from raw data."""
        return SearchResult(
            index=ResultIndex(value=index),
            title=SearchResultTitle(value=_as_text(raw_result.get("title"))),
            url=SearchResultUrl(value=_as_text(raw_result.get("url"))),
            content=SearchResultContent(value=_as_text(raw_result.get("content"))),
        )


def _as_text(value: Any) -> str:
    """Coerce a raw JSON field to a string, treating null as empty."""
    if value is None:
        return ""
    return value if isinstance(value, str) else str(value)
