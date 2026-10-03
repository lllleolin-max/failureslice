"""Exact Git archive -> ordinary wheel -> fresh venv; logs contain no host paths."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile


def run(argv, cwd=None):
    result = subprocess.run(argv, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONPATH": "", "PYTHONNOUSERSITE": "1"})
    if result.returncode:
        # Preserve raw diagnostics only in ignored private destination, not safe receipts.
        raise RuntimeError(f"command failed with exit {result.returncode}: {result.stdout[-1000:].decode(errors='replace')}")
    return result.stdout.decode(errors="replace")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("sha")
    p.add_argument("--suite", action="store_true")
    p.add_argument("--demo", action="store_true")
    p.add_argument("--contrast", action="store_true")
    p.add_argument("--label", default="run")
    args = p.parse_args()
    root = Path(__file__).resolve().parents[1]
    sha = run(["git", "rev-parse", args.sha], root).strip()
    if not args.label.replace("-", "").isalnum():
        p.error("label must contain letters, digits or hyphens")
    base = root / ".local" / f"archive-{sha[:12]}-{args.label}"
    base.mkdir(parents=True, exist_ok=False)
    archive = base / "source.zip"
    run(["git", "archive", "--format=zip", f"--output={archive}", sha], root)
    source = base / "source"
    with zipfile.ZipFile(archive) as z:
        z.extractall(source)
    run([sys.executable, "-m", "venv", str(base / "venv")])
    python = base / "venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    wheel_dir = base / "wheels"
    run([str(python), "-I", "-m", "pip", "wheel", str(source), "--no-deps", "--wheel-dir", str(wheel_dir)])
    wheel = next(wheel_dir.glob("*.whl"))
    run([str(python), "-I", "-m", "pip", "install", "--no-deps", str(wheel)])
    site = Path(run([str(python), "-I", "-c", "import sysconfig,failureslice;from pathlib import Path;site=Path(sysconfig.get_path('purelib'));assert Path(failureslice.__file__).resolve().parent == (site/'failureslice').resolve();print(site)"]).strip())
    tracked = run(["git", "ls-tree", "-r", "--name-only", sha], root).splitlines()
    modules = [f for f in tracked if f.startswith("src/") and f.endswith(".py")]
    digests = {}
    with zipfile.ZipFile(wheel) as z:
        for filename in modules:
            blob = subprocess.check_output(["git", "show", f"{sha}:{filename}"], cwd=root)
            archived = (source / filename).read_bytes()
            member = filename.removeprefix("src/")
            installed = (site / member).read_bytes()
            assert blob == archived == z.read(member) == installed, filename
            digests[member] = hashlib.sha256(blob).hexdigest()
    receipt = {"sha": sha, "version": wheel.name, "module_bytes_equal": digests, "import_location_verified": True, "python": sys.version.split()[0], "checks": {}}
    if args.suite:
        receipt["checks"]["suite"] = run([str(python), "-I", "-m", "unittest", "discover", "-s", str(source / "tests"), "-v"], source)
    if args.demo:
        receipt["checks"]["registered_console_demo"] = run([str(python), "-I", str(source / "tools" / "demo.py"), str(base / "demo")], source)
    if args.contrast:
        receipt["checks"]["contrast"] = run([str(python), "-I", str(source / "tools" / "contrast.py"), "--out", str(base / "contrast.json")], source)
    (base / "receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps({"sha": sha, "version": wheel.name, "modules_equal": len(digests), "checks": list(receipt["checks"])}))


if __name__ == "__main__":
    main()
