"""Domain layer for search functionality."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class SearchQuery:
    """Value object representing a search query."""

    text: str

    def __post_init__(self) -> None:
        if not self.text or not self.text.strip():
            raise ValueError("Search query cannot be empty")


@dataclass(frozen=True)
class SearchResultUrl:
    """Value object representing a URL."""

    value: str


@dataclass(frozen=True)
class SearchResultTitle:
    """Value object representing a result title."""

    value: str


@dataclass(frozen=True)
class SearchResultContent:
    """Value object representing result content."""

    value: str


@dataclass(frozen=True)
class ResultIndex:
    """Value object representing a result index."""

    value: int

    def __post_init__(self) -> None:
        if self.value < 0:
            raise ValueError("Index cannot be negative")


@dataclass(frozen=True)
class SearchResult:
    """Entity representing a single search result."""

    index: ResultIndex
    title: SearchResultTitle
    url: SearchResultUrl
    content: SearchResultContent


@dataclass(frozen=True)
class SearchResultCollection:
    """First-class collection of search results."""

    query: SearchQuery
    results: tuple[SearchResult, ...]

    def format_as_text(self) -> list[str]:
        """Format results for display."""
        output = []
        for result in self.results:
            formatted = self._format_single_result(result)
            output.append(formatted)
        return output

    def _format_single_result(self, result: SearchResult) -> str:
        """Format a single result item."""
        return (
            f"[{result.index.value}] {result.title.value}\n"
            f"URL: {result.url.value}\n"
            f"{result.content.value}\n"
        )


MAX_RESULTS_LIMIT = 100
VALID_TIME_RANGES = frozenset({"day", "week", "month", "year"})


@dataclass(frozen=True)
class SearchParameters:
    """Value object encapsulating search parameters."""

    categories: tuple[str, ...]
    engines: tuple[str, ...]
    language: str
    max_results: int
    time_range: str | None

    def __post_init__(self) -> None:
        # bool is a subclass of int, but is never a valid result count. Raised
        # as ValueError, not TypeError, so it stays on the same exception type
        # as every other SearchParameters validation failure.
        if isinstance(self.max_results, bool) or not isinstance(self.max_results, int):
            raise ValueError("Max results must be an integer")  # noqa: TRY004
        if self.max_results <= 0:
            raise ValueError("Max results must be positive")
        if self.max_results > MAX_RESULTS_LIMIT:
            raise ValueError(f"Max results cannot exceed {MAX_RESULTS_LIMIT}")
        if self.time_range is not None and self.time_range not in VALID_TIME_RANGES:
            valid = ", ".join(sorted(VALID_TIME_RANGES))
            raise ValueError(f"Time range must be one of: {valid}")


class SearchError(Exception):
    """Raised when a search cannot be completed."""


class SearchPort(Protocol):
    """Port for search functionality (outbound)."""

    async def search(
        self, query: SearchQuery, parameters: SearchParameters
    ) -> SearchResultCollection:
        """Execute search and return results."""
        ...
