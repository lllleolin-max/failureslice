"""Cache observations, never favorable votes. Evidence is conditional on identity."""
from dataclasses import dataclass
from enum import Enum
import hashlib
import json
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

    def __post_init__(self):
        if type(self.outcome) is not Outcome:
            raise ValueError("observation outcome must be Outcome")
        if type(self.detail) is not str or len(self.detail.encode("utf-8")) > 4096:
            raise ValueError("detail must be a string of at most 4096 UTF-8 bytes")
        if self.outcome in (Outcome.TARGET, Outcome.OTHER):
            if type(self.signature) is not dict or not self.signature:
                raise ValueError("failure observation needs a nonempty signature object")
        elif self.signature is not None:
            raise ValueError("non-failure observation must not carry a signature")
        canonical(self.to_dict())

    def to_dict(self):
        return {"outcome": self.outcome.value, "signature": self.signature, "detail": self.detail}


@dataclass(frozen=True)
class Evaluation:
    candidate: tuple[str, ...]
    key: str
    outcome: Outcome
    observations: tuple[Observation, ...]
    fresh_calls: int
    context: str = ""
    context_stable: bool = True

    def to_dict(self):
        return {"candidate": list(self.candidate), "key": self.key, "outcome": self.outcome.value,
                "observations": [o.to_dict() for o in self.observations], "fresh_calls": self.fresh_calls,
                "context": self.context, "context_stable": self.context_stable}


class EvidenceOracle:
    def __init__(self, manifest, callback, identity, repetitions=2, max_calls=1000):
        self.manifest, self.callback, self.identity = manifest, callback, identity
        self.repetitions = integer(repetitions, "repetitions", 1, 100)
        self.max_calls = integer(max_calls, "max_calls", 1, 1_000_000)
        canonical(identity() if callable(identity) else identity)
        self.calls = 0
        self._history = {}
        self._unstable_keys = set()

    def context_id(self):
        identity = self.identity() if callable(self.identity) else self.identity
        return hashlib.sha256(canonical({"manifest": self.manifest.to_dict(), "oracle": identity,
                                        "repetitions": self.repetitions})).hexdigest()

    @staticmethod
    def _decode(raw):
        value = json.loads(raw)
        return Observation(Outcome(value["outcome"]), value["signature"], value["detail"])

    @property
    def history(self):
        """Detached audit snapshots; mutating a returned signature cannot rewrite evidence."""
        return {key: tuple(self._decode(raw) for raw in rows) for key, rows in self._history.items()}

    def evaluate(self, ids, refresh=False):
        steps = self.manifest.select(ids)
        context = self.context_id()
        target_signature = canonical(self.manifest.target)
        identity = self.identity() if callable(self.identity) else self.identity
        key = hashlib.sha256(canonical({"candidate": [s.to_dict() for s in steps], "oracle": identity,
                                        "target": self.manifest.target, "repetitions": self.repetitions,
                                        "context": context})).hexdigest()
        history = self._history.setdefault(key, [])
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
                    category = Outcome.TARGET if canonical(observation.signature) == target_signature else Outcome.OTHER
                    observation = Observation(category, observation.signature, observation.detail)
                # Store immutable canonical bytes, detached from caller-owned dictionaries.
                history.append(canonical(observation.to_dict()))
            except Exception:
                history.append(canonical(Observation(Outcome.ERROR, detail="oracle callback rejected or raised").to_dict()))
            try:
                stable = self.context_id() == context
            except Exception:
                stable = False
            if not stable:
                self._unstable_keys.add(key)
                break
        observations = tuple(self._decode(raw) for raw in history)
        # Diagnostic metadata (e.g. a measured duration) is not failure identity.
        # Keep it in the transcript, but compare only the actual classified result.
        distinct = {canonical({"outcome": o.outcome.value, "signature": o.signature}) for o in observations}
        if key in self._unstable_keys:
            outcome = Outcome.ERROR
        elif len(distinct) > 1:
            outcome = Outcome.INCONSISTENT
        elif len(history) < self.repetitions or self.calls - start < needed:
            outcome = Outcome.UNKNOWN
        else:
            outcome = observations[0].outcome
        return Evaluation(tuple(ids), key, outcome, observations, self.calls - start, context, key not in self._unstable_keys)
