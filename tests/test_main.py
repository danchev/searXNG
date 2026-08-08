"""Tests for main entry points."""

from unittest.mock import Mock, patch

import pytest

from searxng import main
from searxng.server import (
    DEFAULT_HOST,
    DEFAULT_INSTANCE_URL,
    DEFAULT_PORT,
    DEFAULT_TRANSPORT,
)


def _run_main(argv: list[str]) -> Mock:
    """Run main() with the given argv, capturing the serve() coroutine args."""
    with (
        patch("sys.argv", ["searxng", *argv]),
        patch("searxng.asyncio.run") as mock_run,
        patch("searxng.serve", new_callable=Mock) as mock_serve,
    ):
        main()
        mock_run.assert_called_once()
    return mock_serve


class TestMain:
    """Test the command line entry point."""

    def test_uses_defaults_when_no_args_given(self) -> None:
        """Every serve() argument defaults to the documented value."""
        mock_serve = _run_main([])

        mock_serve.assert_called_once_with(
            instance_url=DEFAULT_INSTANCE_URL,
            timeout=30,
            transport=DEFAULT_TRANSPORT,
            host=DEFAULT_HOST,
            port=DEFAULT_PORT,
        )

    def test_defaults_to_stdio_on_loopback(self) -> None:
        """The server must not listen on a public interface by default."""
        kwargs = _run_main([]).call_args.kwargs

        assert kwargs["transport"] == "stdio"
        assert kwargs["host"] == "127.0.0.1"

    def test_accepts_custom_instance_url(self) -> None:
        """A custom --instance-url reaches serve()."""
        kwargs = _run_main(["--instance-url", "https://custom.searx"]).call_args.kwargs

        assert kwargs["instance_url"] == "https://custom.searx"

    def test_accepts_custom_timeout(self) -> None:
        """A custom --timeout reaches serve()."""
        kwargs = _run_main(["--timeout", "5"]).call_args.kwargs

        assert kwargs["timeout"] == 5

    def test_accepts_http_transport_options(self) -> None:
        """--transport/--host/--port reach serve()."""
        kwargs = _run_main(
            ["--transport", "http", "--host", "0.0.0.0", "--port", "9000"]
        ).call_args.kwargs

        assert kwargs["transport"] == "http"
        assert kwargs["host"] == "0.0.0.0"
        assert kwargs["port"] == 9000

    def test_rejects_unknown_transport(self) -> None:
        """argparse rejects a transport outside the supported choices."""
        with (
            patch("sys.argv", ["searxng", "--transport", "sse"]),
            patch("searxng.asyncio.run"),
            pytest.raises(SystemExit) as exc_info,
        ):
            main()

        assert exc_info.value.code == 2

    @pytest.mark.parametrize("port", ["0", "65536", "-1"])
    def test_rejects_out_of_range_port(self, port: str) -> None:
        """A port outside 1-65535 exits with argparse's usage error."""
        with (
            patch("sys.argv", ["searxng", "--port", port]),
            patch("searxng.asyncio.run"),
            pytest.raises(SystemExit) as exc_info,
        ):
            main()

        assert exc_info.value.code == 2

    def test_rejects_non_positive_timeout(self) -> None:
        """A non-positive timeout exits with argparse's usage error."""
        with (
            patch("sys.argv", ["searxng", "--timeout", "0"]),
            patch("searxng.asyncio.run"),
            pytest.raises(SystemExit) as exc_info,
        ):
            main()

        assert exc_info.value.code == 2

    def test_rejects_invalid_log_level(self) -> None:
        """An unknown --log-level is rejected by argparse."""
        with (
            patch("sys.argv", ["searxng", "--log-level", "LOUD"]),
            patch("searxng.asyncio.run"),
            pytest.raises(SystemExit) as exc_info,
        ):
            main()

        assert exc_info.value.code == 2

    def test_configures_logging_to_stderr(self) -> None:
        """Logs must not go to stdout, which carries the MCP protocol."""
        with (
            patch("sys.argv", ["searxng", "--log-level", "DEBUG"]),
            patch("searxng.asyncio.run"),
            patch("searxng.serve", new_callable=Mock),
            patch("searxng.logging.basicConfig") as mock_basic_config,
        ):
            main()

        kwargs = mock_basic_config.call_args.kwargs
        assert kwargs["level"] == "DEBUG"
        assert kwargs["stream"] is not None

    def test_keyboard_interrupt_exits_cleanly(self) -> None:
        """Ctrl-C shuts the server down without a traceback."""
        with (
            patch("sys.argv", ["searxng"]),
            patch("searxng.asyncio.run", side_effect=KeyboardInterrupt),
            patch("searxng.serve", new_callable=Mock),
        ):
            main()  # must not raise

    def test_invalid_instance_url_exits_cleanly(self) -> None:
        """A malformed --instance-url is reported as a usage error, not a traceback.

        InstanceUrl validation happens lazily inside serve(), so a bad URL
        surfaces here as a ValueError raised from asyncio.run(); main() must
        translate that into argparse's clean one-line error instead of letting
        it propagate as an unhandled exception.
        """
        with (
            patch("sys.argv", ["searxng", "--instance-url", "not-a-url"]),
            patch(
                "searxng.asyncio.run",
                side_effect=ValueError(
                    "Instance URL must be an absolute http(s) URL, got: not-a-url"
                ),
            ),
            patch("searxng.serve", new_callable=Mock),
            pytest.raises(SystemExit) as exc_info,
        ):
            main()

        assert exc_info.value.code == 2
