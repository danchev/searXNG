"""Tests for main entry points."""

from unittest.mock import Mock, patch


class TestMain:
    """Test main function."""

    @patch("searxng.__init__.serve")
    @patch("searxng.__init__.argparse.ArgumentParser")
    @patch("searxng.__init__.asyncio.run")
    def test_main_with_default_args(
        self, mock_asyncio_run: Mock, mock_argparser: Mock, mock_serve: Mock
    ) -> None:
        """Test main function with default arguments."""
        mock_parser = Mock()
        mock_argparser.return_value = mock_parser
        mock_args = Mock()
        mock_args.instance_url = "https://searx.party"
        mock_parser.parse_args.return_value = mock_args

        from searxng import main

        main()

        mock_argparser.assert_called_once()
        mock_parser.add_argument.assert_called()
        mock_asyncio_run.assert_called_once()

    @patch("searxng.__init__.serve")
    @patch("searxng.__init__.argparse.ArgumentParser")
    @patch("searxng.__init__.asyncio.run")
    def test_main_with_custom_url(
        self, mock_asyncio_run: Mock, mock_argparser: Mock, mock_serve: Mock
    ) -> None:
        """Test main function with custom instance URL."""
        mock_parser = Mock()
        mock_argparser.return_value = mock_parser
        mock_args = Mock()
        mock_args.instance_url = "https://custom.searx"
        mock_parser.parse_args.return_value = mock_args

        from searxng import main

        main()

        mock_asyncio_run.assert_called_once()

    @patch("sys.argv", ["searxng", "--instance-url", "https://test.com"])
    @patch("searxng.__init__.asyncio.run")
    @patch("searxng.__init__.serve")
    def test_main_as_script(self, mock_serve: Mock, mock_asyncio_run: Mock) -> None:
        """Test main function when called as a script."""
        import searxng

        # Call main directly
        if hasattr(searxng, "main"):
            searxng.main()
            mock_asyncio_run.assert_called()
