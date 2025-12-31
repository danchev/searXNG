"""Infrastructure adapters - HTTP client and external integrations."""

import logging
from dataclasses import dataclass
from typing import Any

import requests

from searxng.client import (
    ResultIndex,
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
        if not self.value:
            raise ValueError("Instance URL cannot be empty")


@dataclass(frozen=True)
class SearchTimeout:
    """Value object representing search timeout."""

    seconds: int

    def __post_init__(self) -> None:
        if self.seconds <= 0:
            raise ValueError("Timeout must be positive")


class HttpSearchAdapter:
    """Adapter for HTTP-based search using SearXNG."""

    def __init__(
        self,
        instance_url: str = "https://searx.party",
        timeout: int = 30,
    ) -> None:
        self._instance_url = InstanceUrl(value=instance_url)
        self._timeout = SearchTimeout(seconds=timeout)
        self._logger = logging.getLogger(__name__)

    def search(
        self, query: SearchQuery, parameters: SearchParameters
    ) -> SearchResultCollection:
        """Execute search and return results."""
        self._logger.info(f"Start search: {query.text}")

        request_params = self._build_request_params(query, parameters)
        search_url = f"{self._instance_url.value}/search"

        try:
            raw_results = self._execute_request(search_url, request_params)
            return self._map_to_domain(query, raw_results, parameters.max_results)
        except requests.RequestException as e:
            self._logger.error(f"Request error: {e}")
            return SearchResultCollection(query=query, results=())

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
        """Execute HTTP request."""
        self._logger.info(f"Request URL: {url} Parameters: {params}")
        response = requests.get(url, params=params, timeout=self._timeout.seconds)
        response.raise_for_status()

        results = response.json()
        self._logger.info(f"Got {len(results.get('results', []))} results")
        return results

    def _map_to_domain(
        self, query: SearchQuery, raw_data: dict[str, Any], max_results: int
    ) -> SearchResultCollection:
        """Map raw API response to domain model."""
        results = raw_data.get("results", [])
        domain_results = []

        for index, result in enumerate(results[:max_results]):
            domain_result = self._create_domain_result(index, result)
            domain_results.append(domain_result)

        return SearchResultCollection(query=query, results=tuple(domain_results))

    def _create_domain_result(
        self, index: int, raw_result: dict[str, Any]
    ) -> SearchResult:
        """Create domain result from raw data."""
        return SearchResult(
            index=ResultIndex(value=index),
            title=SearchResultTitle(value=raw_result.get("title", "")),
            url=SearchResultUrl(value=raw_result.get("url", "")),
            content=SearchResultContent(value=raw_result.get("content", "")),
        )
