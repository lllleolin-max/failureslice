"""Bounded local deletion and finite exhaustive certification, no monotonicity assumption."""
from dataclasses import dataclass
from itertools import combinations
from .jsonio import integer
from .oracle import Outcome


@dataclass(frozen=True)
class Result:
    candidate: tuple[str, ...]
    certificate: str
    complete: bool
    evaluations: tuple
    calls: int
    states: int
    alternatives: tuple[tuple[str, ...], ...] = ()

    def to_dict(self):
        return {"candidate": list(self.candidate), "size": len(self.candidate), "certificate": self.certificate,
                "complete": self.complete, "calls": self.calls, "states": self.states,
                "alternatives": [list(a) for a in self.alternatives],
                "evaluations": [e.to_dict() for e in self.evaluations]}


def reduce(manifest, oracle, mode="exact", max_states=100_000):
    integer(max_states, "max_states", 1, 1_000_000)
    if mode not in ("exact", "local"):
        raise ValueError("mode must be exact or local")
    initial = tuple(s.id for s in manifest.steps)
    evaluations = [oracle.evaluate(initial)]
    states = 1
    incumbent = initial
    if evaluations[0].outcome != Outcome.TARGET:
        return Result(initial, "INITIAL_NOT_TARGET", False, tuple(evaluations), oracle.calls, states)
    if mode == "exact":
        minima = [initial]
        complete = True
        stop = False
        for size in range(len(initial)):
            for ids in combinations(initial, size):
                if states >= max_states:
                    complete, stop = False, True
                    break
                states += 1
                try:
                    manifest.select(ids)
                except ValueError:
                    continue
                evaluation = oracle.evaluate(ids)
                evaluations.append(evaluation)
                if evaluation.outcome == Outcome.TARGET:
                    if len(ids) < len(incumbent):
                        incumbent, minima = ids, [ids]
                    elif len(ids) == len(incumbent):
                        minima.append(ids)
                elif evaluation.outcome not in (Outcome.PASS, Outcome.OTHER):
                    complete = False
                if oracle.calls >= oracle.max_calls and evaluation.outcome == Outcome.UNKNOWN:
                    stop = True
                    break
            if stop:
                break
        certificate = "CARDINALITY_MINIMUM_AND_INCLUSION_MINIMAL" if complete else "UNKNOWN"
        return Result(incumbent, certificate, complete, tuple(evaluations), oracle.calls, states, tuple(minima))
    # A deletion removes that step and all dependent steps, never adds setup.
    complete = True
    while True:
        changed = False
        for step_id in incumbent:
            if states >= max_states:
                return Result(incumbent, "UNKNOWN", False, tuple(evaluations), oracle.calls, states)
            ids = manifest.remove_dependents(incumbent, step_id)
            states += 1
            evaluation = oracle.evaluate(ids)
            evaluations.append(evaluation)
            if evaluation.outcome == Outcome.TARGET:
                incumbent, changed = ids, True
                break
            if evaluation.outcome not in (Outcome.PASS, Outcome.OTHER):
                complete = False
        if not changed:
            break
    return Result(incumbent, "TESTED_DEPENDENT_DELETIONS_ONLY" if complete else "UNKNOWN", complete,
                  tuple(evaluations), oracle.calls, states)
