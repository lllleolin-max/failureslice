"""Fresh archive wheels replay unchanged review probes, preserving filename-only receipts."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
CYCLES = [
    ("diagnostic_metadata", "db8e99c53842e67b6d47bbb4660e474b2dfd8340", "5ac8cdb6c2bdbe0eeadbfe1312156e7d5cf5f2f9"),
    ("mutable_observations", "5ac8cdb6c2bdbe0eeadbfe1312156e7d5cf5f2f9", "c14e8bfaed60d5ee8c8108985786d51310dc366d"),
    ("declared_identity_drift", "c14e8bfaed60d5ee8c8108985786d51310dc366d", "3a9e2e15b3a997ce9e105ea69990e5d3cd4c40c9")]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--label", required=True)
    p.add_argument("--out", required=True)
    args = p.parse_args()
    output = Path(args.out)
    if output.exists():
        p.error("output must be new")
    receipts = {}
    for sha in dict.fromkeys(sha for _, before, after in CYCLES for sha in (before, after)):
        subprocess.run([sys.executable, str(ROOT / "tools" / "archive_check.py"), sha, "--suite", "--label", args.label], check=True)
        base = ROOT / ".local" / f"archive-{sha[:12]}-{args.label}"
        receipt = json.loads((base / "receipt.json").read_text(encoding="utf-8"))
        suite = receipt["checks"]["suite"]
        receipts[sha] = {"sha": sha, "modules": receipt["module_bytes_equal"], "tests": int(re.search(r"Ran (\d+) tests", suite).group(1)),
                         "python": receipt["python"], "suite_pass": suite.rstrip().endswith("OK")}
    results = []
    for case, before, after in CYCLES:
        records = []
        for sha, expected in ((before, 1), (after, 0)):
            base = ROOT / ".local" / f"archive-{sha[:12]}-{args.label}"
            python = base / "venv" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
            r = subprocess.run([str(python), str(ROOT / "tools" / "review_probes.py"), case], stdout=subprocess.PIPE)
            observed = json.loads(r.stdout)
            assert r.returncode == expected, (case, sha, r.returncode)
            records.append({"sha": sha, "exit": r.returncode, "probe": observed})
        parent = subprocess.check_output(["git", "rev-parse", f"{after}^"], cwd=ROOT).decode().strip()
        assert parent == before
        results.append({"case": case, "direct_parent_verified": True, "runs": records})
    safe = {"probe_sha256": hashlib.sha256((ROOT / "tools" / "review_probes.py").read_bytes()).hexdigest(),
            "archives": list(receipts.values()), "cycles": results}
    with output.open("x", encoding="utf-8") as stream:
        json.dump(safe, stream, indent=2)
    print(json.dumps({"historical_archives": len(receipts), "before_fail_after_pass_cycles": len(results)}))


if __name__ == "__main__":
    main()
