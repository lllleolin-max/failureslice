import argparse
from pathlib import Path
import sys
from .jsonio import canonical, exact_keys, read
from .model import Manifest
from .oracle import EvidenceOracle
from .reducer import reduce
from .runner import CommandRunner


def main(argv=None):
    parser = argparse.ArgumentParser(description="Reduce a declared finite manifest preserving target failure identity")
    parser.add_argument("manifest")
    parser.add_argument("runner", help="explicit local argv/cwd/env config")
    parser.add_argument("--out", required=True, help="new report file; existing destination rejected")
    parser.add_argument("--mode", choices=("exact", "local"), default="exact")
    parser.add_argument("--max-calls", type=int, default=1000)
    parser.add_argument("--max-states", type=int, default=100000)
    parser.add_argument("--repetitions", type=int, default=2)
    args = parser.parse_args(argv)
    try:
        source_paths = [Path(args.manifest).resolve(strict=True), Path(args.runner).resolve(strict=True)]
        output = Path(args.out).resolve()
        if output in source_paths or output.exists():
            raise ValueError("output must be a new destination distinct from inputs")
        manifest = Manifest.from_dict(read(source_paths[0]))
        raw = read(source_paths[1])
        exact_keys(raw, ("command", "cwd", "env", "environment_identity"), ("code_inputs", "timeout_ms", "max_output"))
        runner = CommandRunner(**raw)
        oracle = EvidenceOracle(manifest, runner, runner.identity, args.repetitions, args.max_calls)
        result = reduce(manifest, oracle, args.mode, args.max_states)
        report = {"schema": "failureslice/1", "result": result.to_dict(),
                  "reduced_manifest": {"steps": [s.to_dict() for s in manifest.select(result.candidate)], "target": manifest.target}}
        with output.open("xb") as stream:
            stream.write(canonical(report) + b"\n")
        print(f"{result.certificate}: size={len(result.candidate)} calls={result.calls} states={result.states}")
        return 0 if result.complete else 3
    except (ValueError, OSError) as exc:
        print(f"failureslice: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
