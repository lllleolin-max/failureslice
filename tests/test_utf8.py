"""Protocol-byte regression plus shared source/config reader and budget boundaries."""
from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from failureslice import CommandRunner, EvidenceOracle, Manifest, Outcome, Step, reduce
from failureslice.cli import main
from failureslice.jsonio import MAX_BYTES, MAX_INTEGER, canonical, loads, read

UNSUPPORTED = ("utf-16", "utf-32", "utf-16-le", "utf-16-be", "utf-32-le", "utf-32-be")
TARGET = {"kind": "encoding-regression", "message": "é汉字😀e\u0301"}


def write_oracle(root):
    script = root / "oracle.py"
    script.write_text("import json,sys\npayload=" + repr({"status": "FAIL", "signature": TARGET}) +
                      "\nsys.stdout.buffer.write(json.dumps(payload,ensure_ascii=False).encode(sys.argv[1]))\nraise SystemExit(1)\n", encoding="utf-8")
    return script


def runner_config(root, script, encoding):
    return {"command": [sys.executable, str(script), encoding, "{candidate}"], "cwd": str(root),
            "env": {k: os.environ[k] for k in ("SystemRoot", "WINDIR") if k in os.environ},
            "environment_identity": {"fixture": "UTF8-boundary"}, "code_inputs": [str(script)],
            "timeout_ms": 5000, "max_output": 4096}


class SharedUTF8ReaderTests(unittest.TestCase):
    def test_non_utf8_bytes_and_bytearrays_rejected_before_json(self):
        text = json.dumps({"message": TARGET["message"]}, ensure_ascii=False)
        for encoding in UNSUPPORTED:
            for raw in (text.encode(encoding), bytearray(text.encode(encoding))):
                with self.subTest(encoding=encoding, kind=type(raw).__name__), self.assertRaises(ValueError):
                    loads(raw)

    def test_legal_utf8_unicode_bytes_bytearrays_and_text(self):
        value = {"message": TARGET["message"], "values": [None, True, 1, 1.5]}
        raw = json.dumps(value, ensure_ascii=False).encode("utf-8")
        for source in (raw, bytearray(raw), raw.decode("utf-8")):
            self.assertEqual(loads(source), value)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "unicode.json"
            path.write_bytes(raw)
            self.assertEqual(read(path), value)
            self.assertEqual(path.read_bytes(), raw)

    def test_malformed_utf8_is_a_value_error(self):
        for raw in (b'"\xff"', b'"\xc0\xaf"', b'"\xed\xa0\x80"', b'"\xe2\x82"', b'\xef\xbb\xbf{}'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                loads(raw)
        with self.assertRaises(ValueError):
            loads('"\ud800"')

    def test_original_byte_depth_integer_and_duplicate_limits(self):
        payload = canonical({"message": TARGET["message"]})
        at_limit = b" " * (MAX_BYTES - len(payload)) + payload
        self.assertEqual(loads(at_limit), {"message": TARGET["message"]})
        self.assertEqual(loads(at_limit.decode("utf-8")), {"message": TARGET["message"]})
        for raw in (at_limit + b" ", (at_limit + b" ").decode("utf-8"), b'{"x":1,"x":2}',
                    b"[" * 33 + b"0" + b"]" * 33, str(MAX_INTEGER + 1).encode("utf-8")):
            with self.assertRaises(ValueError):
                loads(raw)
        self.assertEqual(loads(str(MAX_INTEGER).encode("utf-8")), MAX_INTEGER)

    def test_manifest_and_config_encoding_fail_before_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script = write_oracle(root)
            manifest = root / "manifest.json"
            config = root / "runner.json"
            manifest_text = json.dumps(Manifest((Step("setup"),), TARGET).to_dict(), ensure_ascii=False)
            config_text = json.dumps(runner_config(root, script, "utf-8"), ensure_ascii=False)
            for encoding in UNSUPPORTED:
                for invalid_input in ("manifest", "config"):
                    manifest.write_bytes(manifest_text.encode(encoding if invalid_input == "manifest" else "utf-8"))
                    config.write_bytes(config_text.encode(encoding if invalid_input == "config" else "utf-8"))
                    before = (manifest.read_bytes(), config.read_bytes())
                    report = root / f"{encoding}-{invalid_input}-report.json"
                    with patch("failureslice.cli.CommandRunner", side_effect=AssertionError("must not execute")), redirect_stderr(io.StringIO()):
                        self.assertEqual(main([str(manifest), str(config), "--out", str(report)]), 2)
                    self.assertFalse(report.exists())
                    self.assertEqual(before, (manifest.read_bytes(), config.read_bytes()))


class RealUTF8ProtocolTests(unittest.TestCase):
    def test_unsupported_oracle_bytes_are_error_and_cannot_certify(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script = write_oracle(root)
            manifest = Manifest((Step("setup"),), TARGET)
            for encoding in UNSUPPORTED:
                runner = CommandRunner(**runner_config(root, script, encoding))
                with self.subTest(encoding=encoding):
                    self.assertEqual(runner(manifest.steps).outcome, Outcome.ERROR)
                    result = reduce(manifest, EvidenceOracle(manifest, runner, runner.identity, max_calls=8), max_states=2)
                    self.assertFalse(result.complete)
                    self.assertEqual(result.certificate, "UNKNOWN")
                    self.assertTrue(all(e.outcome == Outcome.ERROR for e in result.evaluations))

    def test_utf8_unicode_survives_sdk_and_cli_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script = write_oracle(root)
            m = Manifest((Step("setup", payload={"note": "汉字😀"}),), TARGET)
            config = runner_config(root, script, "utf-8")
            runner = CommandRunner(**config)
            outcome = runner(m.steps)
            self.assertEqual(outcome.outcome, Outcome.OTHER)
            self.assertEqual(outcome.signature, TARGET)
            result = reduce(m, EvidenceOracle(m, runner, runner.identity, max_calls=4), max_states=2)
            self.assertTrue(result.complete)
            self.assertEqual(result.candidate, ())
            self.assertEqual(result.calls, 4)
            source, config_path, report = root / "manifest.json", root / "runner.json", root / "report.json"
            source.write_bytes(canonical(m.to_dict()))
            config_path.write_bytes(canonical(config))
            before = (source.read_bytes(), config_path.read_bytes())
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main([str(source), str(config_path), "--out", str(report), "--max-calls", "4", "--max-states", "2"]), 0)
            raw = report.read_bytes()
            parsed = json.loads(raw.decode("utf-8", errors="strict"))
            self.assertEqual(parsed["reduced_manifest"]["target"], TARGET)
            self.assertIn(TARGET["message"].encode("utf-8"), raw)
            self.assertTrue(parsed["result"]["complete"])
            self.assertEqual(before, (source.read_bytes(), config_path.read_bytes()))

    def test_output_budget_still_precedes_decoding(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script = root / "overflow.py"
            script.write_text("import sys\nsys.stdout.buffer.write(bytes([255])*129)\nraise SystemExit(1)\n", encoding="utf-8")
            config = runner_config(root, script, "utf-8") | {"max_output": 128}
            outcome = CommandRunner(**config)(())
            self.assertEqual(outcome.outcome, Outcome.ERROR)
            self.assertEqual(outcome.detail, "output budget exceeded")
