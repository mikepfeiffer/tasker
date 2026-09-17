"""Check local settings without starting a server or touching the demo database."""

import io
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from app import main


class StartupTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name) / "Tasker démo"
        self.root.mkdir()
        self.enterContext(patch("app.ROOT", self.root))
        self.enterContext(patch.dict(os.environ, {}, clear=True))
        self.factory = self.enterContext(patch("app.create_app"))

    def assert_started_on(self, port):
        self.factory.return_value.run.assert_called_once_with(
            host="127.0.0.1", port=port, debug=False, load_dotenv=False,
        )

    def test_missing_env_file_uses_default_port(self):
        main([])
        self.assert_started_on(5050)

    def test_env_beside_app_sets_port_and_keeps_future_key_out_of_output(self):
        # A BOM and a path with spaces cover common Windows editor/setup choices.
        (self.root / ".env").write_text(
            'TASKER_PORT="5051" # classroom port\nOPENAI_API_KEY=bogus-classroom-key\n',
            encoding="utf-8-sig",
        )
        output = io.StringIO()
        with redirect_stdout(output), redirect_stderr(output):
            main([])
        self.assert_started_on(5051)
        self.assertEqual(os.environ["OPENAI_API_KEY"], "bogus-classroom-key")
        self.assertNotIn("bogus-classroom-key", output.getvalue())

    def test_existing_environment_overrides_env_file(self):
        (self.root / ".env").write_text("TASKER_PORT=5051\n", encoding="utf-8")
        os.environ["TASKER_PORT"] = "5052"
        main([])
        self.assert_started_on(5052)

    def test_explicit_port_overrides_even_an_invalid_environment_value(self):
        (self.root / ".env").write_text("TASKER_PORT=5051\n", encoding="utf-8")
        os.environ["TASKER_PORT"] = "not-a-port"
        main(["--port", "5053"])
        self.assert_started_on(5053)

    def test_invalid_ports_fail_before_creating_the_app(self):
        for value in ("", "not-a-port", "0", "-1", "65536"):
            for source in ("environment", "flag"):
                with self.subTest(value=value, source=source):
                    os.environ["TASKER_PORT"] = value if source == "environment" else "5050"
                    arguments = [] if source == "environment" else ["--port", value]
                    output = io.StringIO()
                    with redirect_stderr(output), self.assertRaises(SystemExit) as error:
                        main(arguments)
                    self.assertEqual(error.exception.code, 2)
                    self.assertIn("port", output.getvalue())
                    self.assertNotIn("Traceback", output.getvalue())
        self.factory.assert_not_called()

    def test_help_works_with_an_invalid_local_port(self):
        (self.root / ".env").write_text("TASKER_PORT=not-a-port\n", encoding="utf-8")
        output = io.StringIO()
        with redirect_stdout(output), self.assertRaises(SystemExit) as error:
            main(["--help"])
        self.assertEqual(error.exception.code, 0)
        self.assertIn("TASKER_PORT", output.getvalue())
        self.factory.assert_not_called()


if __name__ == "__main__":
    unittest.main()
