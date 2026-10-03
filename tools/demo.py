"""Prepare explicit host-local config; invoke the installed registered console script."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import sysconfig


def main():
    p = argparse.ArgumentParser()
    p.add_argument("destination", help="new directory")
    args = p.parse_args()
    dest = Path(args.destination)
    dest.mkdir(parents=True, exist_ok=False)
    root = Path(__file__).resolve().parents[1]
    fixture = root / "examples" / "release_oracle.py"
    config = {"command": [sys.executable, str(fixture), "release", "{candidate}"],
              "cwd": str(dest.resolve()), "env": {k: os.environ[k] for k in ("SystemRoot", "WINDIR") if k in os.environ},
              "environment_identity": {"fixture": "synthetic-SQLite-v1", "python": sys.version.split()[0]},
              "code_inputs": [str(fixture)], "timeout_ms": 5000, "max_output": 65536}
    runner = dest / "runner.json"
    runner.write_text(json.dumps(config), encoding="utf-8")
    scripts = Path(sysconfig.get_path("scripts"))
    console = scripts / ("failureslice.exe" if os.name == "nt" else "failureslice")
    return subprocess.run([str(console), str(root / "examples" / "release.json"), str(runner),
                           "--out", str(dest / "report.json")], check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
