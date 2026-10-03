"""Executed disclosed ddmin variants, not an incumbent performance claim."""
import argparse
import json
import os
from pathlib import Path
import sys
from failureslice import CommandRunner, EvidenceOracle, Manifest, Outcome, Step, reduce

ROOT = Path(__file__).resolve().parents[1]


def ddmin(manifest, runner, budget, closure, same_signature):
    calls = 0
    records = []
    cache = {}
    initial = tuple(s.id for s in manifest.steps)
    def construct(ids):
        ids = set(ids)
        if closure:
            for step in reversed(manifest.steps):
                if step.id in ids:
                    ids.update(step.requires)
        return tuple(s.id for s in manifest.steps if s.id in ids)
    def evaluate(ids):
        nonlocal calls
        ids = construct(ids)
        if ids in cache:
            return cache[ids]
        if calls + 2 > budget:
            return "UNKNOWN"
        results = []
        for _ in range(2):
            observation = runner(tuple(s for s in manifest.steps if s.id in ids))
            calls += 1
            kind = observation.outcome.value
            if observation.outcome == Outcome.OTHER:
                kind = "TARGET" if observation.signature == manifest.target else "OTHER"
            results.append(kind)
        kind = results[0] if results[0] == results[1] else "INCONSISTENT"
        records.append({"candidate": list(ids), "outcome": kind, "fresh_calls": 2})
        cache[ids] = kind
        return kind
    def interesting(ids):
        kind = evaluate(ids)
        return kind == "TARGET" if same_signature else kind in ("TARGET", "OTHER", "INVALID")
    candidate = initial
    interesting(initial)
    granularity = 2
    while len(candidate) >= 2 and calls < budget:
        partitions = [candidate[i * len(candidate) // granularity:(i + 1) * len(candidate) // granularity] for i in range(granularity)]
        changed = False
        for subset in partitions:
            next_ids = construct(subset)
            if len(next_ids) < len(candidate) and interesting(next_ids):
                candidate, granularity, changed = next_ids, max(2, granularity - 1), True
                break
        if changed:
            continue
        for subset in partitions:
            next_ids = construct(tuple(x for x in candidate if x not in subset))
            if len(next_ids) < len(candidate) and interesting(next_ids):
                candidate, granularity, changed = next_ids, max(2, granularity - 1), True
                break
        if changed:
            continue
        if granularity == len(candidate):
            break
        granularity = min(len(candidate), granularity * 2)
    if candidate and interesting(()) and calls < budget:
        candidate = ()
    kind = evaluate(candidate)
    return {"candidate": list(candidate), "size": len(candidate), "target_reproduced": kind == "TARGET",
            "outcome": kind, "calls": calls, "invalid_calls": sum(r["fresh_calls"] for r in records if r["outcome"] == "INVALID"),
            "certificate": "ddmin tested local heuristic only", "transcript": records}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    output = Path(args.out)
    if output.exists():
        parser.error("output must be new")
    release = Manifest.from_dict(json.loads((ROOT / "examples" / "release.json").read_text(encoding="utf-8")))
    cases = [("alternate-signature", release, "release", 512), ("standard-success", release, "standard-success", 512),
             ("nonmonotone", Manifest((Step("schema"), Step("seed", ("schema",)), Step("noise-a"), Step("noise-b")), release.target), "nonmonotone", 512),
             ("adverse-budget", Manifest(release.steps + tuple(Step(f"noise-{i}") for i in range(6)), release.target), "standard-success", 60)]
    report = {"synthetic": True, "incumbent_executed": False, "repetitions": 2, "cases": []}
    fixture = ROOT / "examples" / "release_oracle.py"
    for name, manifest, mode, budget in cases:
        runner = CommandRunner([sys.executable, str(fixture), mode, "{candidate}"], ROOT,
                               {k: os.environ[k] for k in ("SystemRoot", "WINDIR") if k in os.environ},
                               {"fixture": mode}, [fixture])
        results = {"unstructured-blind-ddmin": ddmin(manifest, runner, budget, False, False),
                   "closed-blind-ddmin": ddmin(manifest, runner, budget, True, False),
                   "closed-signed-ddmin": ddmin(manifest, runner, budget, True, True)}
        o = EvidenceOracle(manifest, runner, runner.identity, max_calls=budget)
        exact = reduce(manifest, o).to_dict()
        exact["target_reproduced"] = any(e["candidate"] == exact["candidate"] and e["outcome"] == "TARGET" for e in exact["evaluations"])
        exact["invalid_calls"] = sum(e["fresh_calls"] for e in exact["evaluations"] if e["outcome"] == "INVALID")
        results["failureslice-exact"] = exact
        report["cases"].append({"case": name, "budget": budget, "initial_size": len(manifest.steps), "results": results})
        print(name, {key: {k: v for k, v in value.items() if k in ("size", "calls", "invalid_calls", "target_reproduced", "certificate")} for key, value in results.items()}, flush=True)
    with output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2)


if __name__ == "__main__":
    main()
