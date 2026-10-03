"""Cache observations, never favorable votes. Evidence is conditional on identity."""
from dataclasses import dataclass
from enum import Enum
import hashlib
from .jsonio import canonical, integer


class Outcome(str, Enum):
    TARGET = "TARGET"
    PASS = "PASS"
    OTHER = "OTHER"
    INVALID = "INVALID"
    TIMEOUT = "TIMEOUT"
    ERROR = "ERROR"
    INCONSISTENT = "INCONSISTENT"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class Observation:
    outcome: Outcome
    signature: dict | None = None
    detail: str = ""

    def to_dict(self):
        return {"outcome": self.outcome.value, "signature": self.signature, "detail": self.detail}


@dataclass(frozen=True)
class Evaluation:
    candidate: tuple[str, ...]
    key: str
    outcome: Outcome
    observations: tuple[Observation, ...]
    fresh_calls: int

    def to_dict(self):
        return {"candidate": list(self.candidate), "key": self.key, "outcome": self.outcome.value,
                "observations": [o.to_dict() for o in self.observations], "fresh_calls": self.fresh_calls}


class EvidenceOracle:
    def __init__(self, manifest, callback, identity, repetitions=2, max_calls=1000):
        self.manifest, self.callback, self.identity = manifest, callback, identity
        self.repetitions = integer(repetitions, "repetitions", 1, 100)
        self.max_calls = integer(max_calls, "max_calls", 1, 1_000_000)
        canonical(identity() if callable(identity) else identity)
        self.calls = 0
        self.history = {}

    def evaluate(self, ids, refresh=False):
        steps = self.manifest.select(ids)
        identity = self.identity() if callable(self.identity) else self.identity
        key = hashlib.sha256(canonical({"candidate": [s.to_dict() for s in steps], "oracle": identity,
                                        "target": self.manifest.target, "repetitions": self.repetitions})).hexdigest()
        history = self.history.setdefault(key, [])
        start = self.calls
        needed = self.repetitions if refresh else max(0, self.repetitions - len(history))
        for _ in range(needed):
            if self.calls >= self.max_calls:
                break
            self.calls += 1
            try:
                observation = self.callback(steps)
                if type(observation) is not Observation or type(observation.outcome) is not Outcome:
                    raise ValueError("oracle must return Observation")
                canonical(observation.to_dict())
                if observation.outcome in (Outcome.TARGET, Outcome.OTHER):
                    if type(observation.signature) is not dict or not observation.signature:
                        raise ValueError("failure needs a structured signature")
                    category = Outcome.TARGET if canonical(observation.signature) == canonical(self.manifest.target) else Outcome.OTHER
                    observation = Observation(category, observation.signature, observation.detail)
                history.append(observation)
            except Exception:
                history.append(Observation(Outcome.ERROR, detail="oracle callback rejected or raised"))
        distinct = {canonical(o.to_dict()) for o in history}
        if len(distinct) > 1:
            outcome = Outcome.INCONSISTENT
        elif len(history) < self.repetitions or self.calls - start < needed:
            outcome = Outcome.UNKNOWN
        else:
            outcome = history[0].outcome
        return Evaluation(tuple(ids), key, outcome, tuple(history), self.calls - start)
