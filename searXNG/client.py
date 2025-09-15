import requests
from typing import List, Dict, Any, Optional
import logging

class SearXNGClient:
    """
    SearXNG Search client
    Used to perform searches and format the results into the specified JSON format
    """
    def __init__(self, instance_url: str = "https://searx.party"):
        """
        Initialize SearXNG client

        参数:
        - instance_url: SearXNG instance URL
        """
        self.instance_url = instance_url
        self.logger = logging.getLogger(__name__)

    def search(self, query: str,
               categories: Optional[List[str]] = None,
               engines: Optional[List[str]] = None,
               language: str = "en",
               max_results: int = 20,
               timeout: int = 30,
               pageno: int = 1,
               time_range: Optional[str] = None,
               safesearch: int = 0,
               format: str = "json",
               results_on_new_tab: Optional[int] = None,
               image_proxy: Optional[bool] = None,
               autocomplete: Optional[str] = None,
               theme: Optional[str] = None,
               enabled_plugins: Optional[List[str]] = None,
               disabled_plugins: Optional[List[str]] = None,
               enabled_engines: Optional[List[str]] = None,
               disabled_engines: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Performs a search and returns formatted results

        Parameters:
        - query: search query
        - categories: search category list (e.g. ['general', 'images', 'news'])
        - engines: search engine list (e.g. ['google', 'bing', 'duckduckgo'])
        - language: search language code
        - include_images: whether to include image results
        - max_results: maximum number of results to return
        - timeout: API request timeout (seconds)
        - pageno: search result page number
        - time_range: time range filter ('day', 'week', 'month', 'year')
        - safesearch: safe search level (0=off, 1=medium, 2=strict)
        - format: response format ('json', 'csv', 'rss')
        - results_on_new_tab: open results in new tab (0=no, 1=yes)
        - image_proxy: whether to use SearXNG to proxy images
        - autocomplete: autocomplete service
        - theme: interface theme
        - enabled_plugins: list of plugins to enable
        - disabled_plugins: list of plugins to disable
        - enabled_engines: list of engines to enable
        - disabled_engines: list of engines to disable
        Returns:
        - Structured search result JSON
        """
        self.logger.info(f"Start search: {query}")

        # Build query parameters
        params = {
            'q': query,
            'format': format,
            'language': language,
            'safesearch': safesearch,
            'pageno': pageno
        }

        # Add optional parameters
        if categories:
            params['categories'] = ','.join(categories)
        if engines:
            params['engines'] = ','.join(engines)
        if time_range:
            params['time_range'] = time_range
        if results_on_new_tab is not None:
            params['results_on_new_tab'] = results_on_new_tab
        if image_proxy is not None:
            params['image_proxy'] = 'True' if image_proxy else 'False'
        if autocomplete:
            params['autocomplete'] = autocomplete
        if theme:
            params['theme'] = theme
        if enabled_plugins:
            params['enabled_plugins'] = ','.join(enabled_plugins)
        if disabled_plugins:
            params['disabled_plugins'] = ','.join(disabled_plugins)
        if enabled_engines:
            params['enabled_engines'] = ','.join(enabled_engines)
        if disabled_engines:
            params['disabled_engines'] = ','.join(disabled_engines)

        # Build request URL
        url = f"{self.instance_url}/search"

        try:
            # Send search request
            self.logger.info(f"Request URL: {url} Parameters: {params}")
            response = requests.get(url, params=params, timeout=timeout)
            response.raise_for_status()  # Check for HTTP errors

            # Parse response
            search_results = response.json()
            self.logger.info(f"Got {len(search_results.get('results', []))} results")

            # Format results
            return self._format_results(query, search_results, max_results)

        except requests.RequestException as e:
            self.logger.error(f"Request error: {e}")
            # Return empty results on error
            return self._format_results(query, {"results": []}, 0)

    def _format_results(self, query: str, search_data: Dict[str, Any],
                        max_results: int) -> Dict[str, Any]:
        """
        Format search results into the specified JSON format

        Parameters:
        - query: original query
        - search_data: search result data
        - image_results: image search result data
        - max_results: maximum result count

        Returns:
        - Formatted JSON result
        """
        # Initialize result list
        formatted_results = []

        # Process normal search results
        results = search_data.get('results', [])
        for index, result in enumerate(results[:max_results]):
            # Get content and process trailing ellipsis
            content = result.get('content', '')

            # Add to indexed results list
            content_item = {
                "index": index,
                "result": content
            }

            formatted_results.append(content_item)

        # Build final result
        final_result = {
            "query": query,
            "content": formatted_results,
        }

        return final_result
