from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from failureslice import CommandRunner, Observation, Outcome
from failureslice.cli import main


class ProtocolAndCLITests(unittest.TestCase):
    def test_sdk_types_rejected(self):
        for args in (("PASS", None, ""), (Outcome.PASS, {"kind": "wrong"}, ""), (Outcome.TARGET, {}, ""), (Outcome.PASS, None, 1)):
            with self.assertRaises(ValueError):
                Observation(*args)
        with tempfile.TemporaryDirectory() as tmp:
            for kwargs in ({"code_inputs": None}, {"cwd": 1}):
                config = dict(command=[sys.executable, "{candidate}"], cwd=tmp, env={}, environment_identity={"v": 1})
                config.update(kwargs)
                with self.assertRaises(ValueError):
                    CommandRunner(**config)

    def test_existing_hardlink_alias_is_rejected_before_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            original = Path(tmp) / "manifest.json"
            original.write_text('{"steps":[{"id":"a"}],"target":{"kind":"original"}}', encoding="utf-8")
            runner = Path(tmp) / "runner.json"
            runner.write_text('{}', encoding="utf-8")
            alias = Path(tmp) / "alias.json"
            os.link(original, alias)
            before = original.read_bytes()
            with patch("failureslice.cli.CommandRunner", side_effect=AssertionError("must not execute")), redirect_stderr(io.StringIO()):
                self.assertEqual(main([str(original), str(runner), "--out", str(alias)]), 2)
                self.assertEqual(main([str(original), str(runner), "--out", str(original)]), 2)
            self.assertEqual(before, original.read_bytes())

    def test_unknown_runner_fields_and_null_paths_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "manifest.json"
            manifest.write_text('{"steps":[{"id":"a"}],"target":{"kind":"original"}}', encoding="utf-8")
            runner = Path(tmp) / "runner.json"
            config = dict(command=[sys.executable, "{candidate}"], cwd=tmp, env={}, environment_identity={"v": 1})
            for field in ({"extra": 1}, {"code_inputs": None}, {"timeout_ms": True}):
                runner.write_text(json.dumps(config | field), encoding="utf-8")
                output = Path(tmp) / "new.json"
                with redirect_stderr(io.StringIO()):
                    self.assertEqual(main([str(manifest), str(runner), "--out", str(output)]), 2)
                self.assertFalse(output.exists())

    def test_real_protocol_mismatch_never_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / "oracle.py"
            for text in ('print(\'{"status":"PASS"}\'); raise SystemExit(1)', 'print(\'{"status":"FAIL","signature":{}}\'); raise SystemExit(1)', 'print(\'{"status":"PASS","status":"FAIL"}\'); raise SystemExit(1)', 'print(\'{"status":"unknown"}\')'):
                script.write_text(text, encoding="utf-8")
                env = {k: os.environ[k] for k in ("SystemRoot", "WINDIR") if k in os.environ}
                r = CommandRunner([sys.executable, str(script), "{candidate}"], tmp, env, {"v": 1}, [script])
                self.assertEqual(r(()).outcome, Outcome.ERROR)
