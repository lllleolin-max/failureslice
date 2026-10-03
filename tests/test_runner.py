import ctypes
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from failureslice import CommandRunner, EvidenceOracle, Manifest, Outcome, Step

FIXTURE = Path(__file__).resolve().parents[1] / "examples" / "release_oracle.py"
TARGET = {"type": "sqlite3.IntegrityError", "message": "UNIQUE constraint failed: users.email", "operation": "duplicate-import"}


def env():
    return {k: os.environ[k] for k in ("SystemRoot", "WINDIR") if k in os.environ}


def runner(mode, **kwargs):
    return CommandRunner([sys.executable, str(FIXTURE), mode, "{candidate}"], FIXTURE.parent,
                         env(), {"fixture": "synthetic-v1"}, [FIXTURE], **kwargs)


class RealRunnerTests(unittest.TestCase):
    def test_timeout_and_output_are_real(self):
        for mode, expected in (("timeout", Outcome.TIMEOUT), ("overflow", Outcome.ERROR)):
            before = time.monotonic()
            outcome = runner(mode, timeout_ms=2000 if mode == "overflow" else 100, max_output=128)(())
            self.assertEqual(outcome.outcome, expected)
            self.assertLess(time.monotonic() - before, 5)

    def test_setup_signature_and_pass_are_separate(self):
        r = runner("release")
        self.assertEqual(r(()).outcome, Outcome.PASS)
        self.assertEqual(r((Step("seed", ("schema",)),)).outcome, Outcome.INVALID)
        other = r((Step("schema"), Step("legacy-import", ("schema",))))
        self.assertEqual(other.signature["type"], "json.JSONDecodeError")
        steps = (Step("schema"), Step("seed", ("schema",)), Step("duplicate-import", ("seed", "schema")))
        m = Manifest(steps, TARGET)
        self.assertEqual(EvidenceOracle(m, r, r.identity).evaluate(tuple(s.id for s in steps)).outcome, Outcome.TARGET)

    def test_actual_alternating_fixture(self):
        with tempfile.TemporaryDirectory() as tmp:
            argv = [sys.executable, str(FIXTURE), "alternating", "{candidate}", str(Path(tmp) / "state")]
            r = CommandRunner(argv, tmp, env(), {"fixture": "alternating"}, [FIXTURE])
            m = Manifest((Step("a"),), TARGET)
            self.assertEqual(EvidenceOracle(m, r, r.identity).evaluate(("a",)).outcome, Outcome.INCONSISTENT)

    def test_changed_script_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / "oracle.py"
            script.write_text('print(\'{"status":"PASS"}\')', encoding="utf-8")
            r = CommandRunner([sys.executable, str(script), "{candidate}"], tmp, env(), {"v": 1}, [script])
            first = r.identity()
            script.write_text('print(\'{"status":"INVALID"}\'); raise SystemExit(1)', encoding="utf-8")
            self.assertNotEqual(first, r.identity())

    def test_child_process_tree_terminated(self):
        with tempfile.TemporaryDirectory() as tmp:
            script, pidfile = Path(tmp) / "spawn.py", Path(tmp) / "pid"
            script.write_text("import subprocess,sys,time\nfrom pathlib import Path\np=subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)'])\nPath(sys.argv[1]).write_text(str(p.pid))\ntime.sleep(30)\n", encoding="utf-8")
            r = CommandRunner([sys.executable, str(script), str(pidfile), "{candidate}"], tmp, env(), {"v": 1}, [script], timeout_ms=400)
            self.assertEqual(r(()).outcome, Outcome.TIMEOUT)
            self.assertTrue(pidfile.exists())
            pid = int(pidfile.read_text())
            if os.name == "nt":
                kernel = ctypes.WinDLL("kernel32", use_last_error=True)
                kernel.OpenProcess.restype = ctypes.c_void_p
                kernel.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
                kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
                kernel.CloseHandle.argtypes = [ctypes.c_void_p]
                handle = kernel.OpenProcess(0x100000, 0, pid)
                if handle:
                    self.assertEqual(kernel.WaitForSingleObject(handle, 1000), 0)
                    kernel.CloseHandle(handle)
            else:
                # A killed child may briefly remain a zombie until init reaps it.
                proc = Path(f"/proc/{pid}/stat")
                if proc.exists():
                    self.assertEqual(proc.read_text().split()[2], "Z")

    def test_argv_not_shell(self):
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / "args.py"
            script.write_text("import sys\nassert sys.argv[1] == '$(echo unsafe);&'\nprint('{\"status\":\"PASS\"}')", encoding="utf-8")
            r = CommandRunner([sys.executable, str(script), '$(echo unsafe);&', "{candidate}"], tmp, env(), {"v": 1}, [script])
            self.assertEqual(r(()).outcome, Outcome.PASS)


if __name__ == "__main__":
    unittest.main()
