"""Real socket tests for network limits, cancellation and MCP error handling."""

import asyncio
import json
import logging
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
from mcp import Client

from searxng.adapters import (
    MAX_CONCURRENT_SEARCHES,
    MAX_RESPONSE_BYTES,
    HttpSearchAdapter,
)
from searxng.client import SearchError, SearchQuery
from searxng.server import SearchUseCase, build_server
from tests.test_adapters import make_parameters


pytestmark = pytest.mark.skipif(
    sys.platform == "win32",
    reason="asyncio real-socket teardown is not deterministic on Windows",
)


@asynccontextmanager
async def upstream(
    mode: str,
) -> AsyncIterator[tuple[str, asyncio.Event, asyncio.Event]]:
    disconnected = asyncio.Event()
    started = asyncio.Event()
    tasks: set[asyncio.Task] = set()

    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        task = asyncio.current_task()
        assert task is not None
        tasks.add(task)
        try:
            request = await reader.readuntil(b"\r\n\r\n")
            started.set()
            if mode == "slow" and b"q=retry" not in request:
                writer.write(b"HTTP/1.1 200 OK\r\nContent-Length: 10000\r\n\r\n")
                await writer.drain()
                # Keep supplying data faster than the read inactivity timeout.
                while not reader.at_eof():
                    writer.write(b" ")
                    await writer.drain()
                    await asyncio.sleep(0.02)
            elif mode == "length":
                writer.write(
                    f"HTTP/1.1 200 OK\r\nContent-Length: {MAX_RESPONSE_BYTES + 1}\r\n\r\n".encode()
                )
                await writer.drain()
                await reader.read()
            elif mode == "chunked":
                writer.write(b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n")
                chunk = b"x" * 65536
                for _ in range(MAX_RESPONSE_BYTES // len(chunk) + 1):
                    writer.write(f"{len(chunk):x}\r\n".encode() + chunk + b"\r\n")
                    await writer.drain()
                # Do not terminate the body: the client must stop at the limit.
                await reader.read()
            elif mode == "encoding":
                writer.write(
                    b"HTTP/1.1 200 OK\r\nContent-Encoding: gzip\r\nContent-Length: 999\r\n\r\n"
                )
                await writer.drain()
                await reader.read()
            else:
                payload = (
                    {"results": None}
                    if mode == "malformed"
                    else {
                        "results": [
                            {
                                "title": "Fixture",
                                "url": "https://example.com",
                                "content": "Found",
                            }
                        ]
                    }
                )
                body = json.dumps(payload).encode()
                status = b"503 Unavailable" if mode == "error" else b"200 OK"
                writer.write(
                    b"HTTP/1.1 "
                    + status
                    + b"\r\nContent-Length: "
                    + str(len(body)).encode()
                    + b"\r\nConnection: close\r\n\r\n"
                    + body
                )
                await writer.drain()
        except (ConnectionError, asyncio.IncompleteReadError):
            pass
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except ConnectionError:
                pass
            disconnected.set()
            tasks.discard(task)

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    try:
        yield (
            f"http://127.0.0.1:{server.sockets[0].getsockname()[1]}",
            disconnected,
            started,
        )
    finally:
        server.close()
        await server.wait_closed()
        pending = list(tasks)
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)


@pytest.mark.parametrize(
    "mode,message",
    [
        ("length", "exceeds"),
        ("chunked", "exceeds"),
        ("encoding", "encoding"),
        ("malformed", "Invalid response"),
    ],
)
async def test_rejects_unsafe_responses_and_closes_connection(mode, message):
    async with upstream(mode) as (url, disconnected, _):
        adapter = HttpSearchAdapter(url)
        try:
            with pytest.raises(SearchError, match=message):
                await asyncio.wait_for(
                    adapter.search(SearchQuery("test"), make_parameters()), 2
                )
            await asyncio.wait_for(disconnected.wait(), 2)
        finally:
            await adapter.close()


async def test_total_deadline_stops_slow_stream_and_releases_capacity():
    async with upstream("slow") as (url, disconnected, _):
        adapter = HttpSearchAdapter(url, timeout=0.15)
        try:
            for _ in range(2):
                disconnected.clear()
                with pytest.raises(SearchError, match="timed out"):
                    await asyncio.wait_for(
                        adapter.search(SearchQuery("test"), make_parameters()), 1
                    )
                await asyncio.wait_for(disconnected.wait(), 1)
        finally:
            await adapter.close()


async def test_overload_rejected_and_cancellation_releases_connections():
    async with upstream("slow") as (url, disconnected, started):
        adapter = HttpSearchAdapter(url, timeout=5)
        searches = [
            asyncio.create_task(adapter.search(SearchQuery("test"), make_parameters()))
            for _ in range(MAX_CONCURRENT_SEARCHES)
        ]
        try:
            # Each task acquires its slot before its first network await.
            await asyncio.wait_for(started.wait(), 1)
            with pytest.raises(SearchError, match="capacity"):
                await adapter.search(SearchQuery("excess"), make_parameters())
            for task in searches:
                task.cancel()
            results = await asyncio.gather(*searches, return_exceptions=True)
            assert all(isinstance(result, asyncio.CancelledError) for result in results)
            await asyncio.wait_for(disconnected.wait(), 1)
            # The same adapter remains usable after cancelling live requests.
            result = await adapter.search(SearchQuery("retry"), make_parameters())
            assert result.results[0].title.value == "Fixture"

        finally:
            for task in searches:
                task.cancel()
            await asyncio.gather(*searches, return_exceptions=True)
            await adapter.close()


@pytest.mark.parametrize("mode", ["success", "malformed", "error"])
async def test_mcp_search_through_real_upstream(mode, caplog):
    async with upstream(mode) as (url, _, _):
        adapter = HttpSearchAdapter(url)
        try:
            with caplog.at_level(logging.DEBUG, logger="searxng"):
                async with Client(build_server(SearchUseCase(adapter))) as client:
                    result = await client.call_tool(
                        "web_search", {"query": "private-search-token"}
                    )
                    assert bool(result.is_error) == (mode != "success")
                    invalid = await client.call_tool(
                        "web_search", {"query": "test", "time_range": []}
                    )
                    assert invalid.is_error
                    assert "Time range" in invalid.content[0].text
            assert "private-search-token" not in caplog.text
        finally:
            await adapter.close()
