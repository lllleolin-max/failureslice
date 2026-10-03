"""Unchanged adversarial SDK probes reused against historical installed wheels."""
import argparse
import json
from failureslice import EvidenceOracle, Manifest, Observation, Outcome, Step, reduce

T = {"kind": "import-original"}


def diagnostic_metadata():
    m = Manifest((Step("a"),), T)
    count = [0]
    def callback(_):
        count[0] += 1
        return Observation(Outcome.TARGET, T, detail=f"duration={count[0]}")
    e = EvidenceOracle(m, callback, {"v": 1}).evaluate(("a",))
    return e.outcome == Outcome.TARGET, {"outcome": e.outcome.value, "observations": len(e.observations)}


def mutable_observations():
    m = Manifest((Step("a"),), T)
    shared = dict(T)
    o = EvidenceOracle(m, lambda _: Observation(Outcome.TARGET, shared), {"v": 1})
    first = o.evaluate(("a",))
    shared["kind"] = "external-mutation"
    first.observations[0].signature["kind"] = "report-mutation"
    reused = o.evaluate(("a",))
    actual = [x.signature for x in reused.observations]
    return reused.outcome == Outcome.TARGET and all(x == T for x in actual), {"outcome": reused.outcome.value, "signatures": actual, "fresh_calls": reused.fresh_calls}


def declared_identity_drift():
    m = Manifest((Step("a"), Step("b")), T)
    identity = {"version": 1}
    def callback(steps):
        if len(steps) < 2:
            identity["version"] = 2
            return Observation(Outcome.PASS)
        return Observation(Outcome.TARGET, T)
    r = reduce(m, EvidenceOracle(m, callback, identity))
    return not r.complete and r.certificate == "UNKNOWN", {"complete": r.complete, "certificate": r.certificate, "calls": r.calls}


CASES = {"diagnostic_metadata": diagnostic_metadata, "mutable_observations": mutable_observations,
         "declared_identity_drift": declared_identity_drift}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("case", choices=CASES)
    args = p.parse_args()
    passed, observed = CASES[args.case]()
    print(json.dumps({"case": args.case, "passed": passed, "observed": observed}, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
