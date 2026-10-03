"""A deletion universe: order is fixed, kept steps require kept predecessors."""
from dataclasses import dataclass, field
import json
import re
from .jsonio import canonical, exact_keys


@dataclass(frozen=True)
class Step:
    id: str
    requires: tuple[str, ...] = ()
    payload: dict = field(default_factory=dict)

    def __post_init__(self):
        if type(self.id) is not str or not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", self.id):
            raise ValueError("invalid step ID")
        if type(self.requires) not in (tuple, list) or any(type(x) is not str for x in self.requires) or len(set(self.requires)) != len(self.requires):
            raise ValueError("requires must be unique step IDs")
        if type(self.payload) is not dict:
            raise ValueError("payload must be an object")
        object.__setattr__(self, "requires", tuple(self.requires))
        object.__setattr__(self, "payload", json.loads(canonical(self.payload)))

    def to_dict(self):
        return {"id": self.id, "requires": list(self.requires), "payload": self.payload}


@dataclass(frozen=True)
class Manifest:
    steps: tuple[Step, ...]
    target: dict

    def __post_init__(self):
        if type(self.steps) not in (list, tuple) or not 1 <= len(self.steps) <= 64 or any(type(s) is not Step for s in self.steps):
            raise ValueError("manifest requires 1..64 Step objects")
        seen = set()
        for step in self.steps:
            if step.id in seen or not set(step.requires) <= seen:
                raise ValueError("duplicate ID, missing prerequisite, forward dependency or cycle")
            seen.add(step.id)
        if type(self.target) is not dict or not self.target:
            raise ValueError("target must be a nonempty structured object")
        object.__setattr__(self, "steps", tuple(self.steps))
        object.__setattr__(self, "target", json.loads(canonical(self.target)))
        canonical(self.to_dict())

    @classmethod
    def from_dict(cls, value):
        exact_keys(value, ("steps", "target"))
        if type(value["steps"]) is not list:
            raise ValueError("steps must be a list")
        steps = []
        for raw in value["steps"]:
            exact_keys(raw, ("id",), ("requires", "payload"))
            steps.append(Step(raw["id"], raw.get("requires", ()), raw.get("payload", {})))
        return cls(tuple(steps), value["target"])

    def to_dict(self):
        return {"steps": [s.to_dict() for s in self.steps], "target": self.target}

    def select(self, ids):
        if type(ids) not in (tuple, list) or any(type(i) is not str for i in ids) or len(ids) != len(set(ids)):
            raise ValueError("candidate must contain unique IDs")
        wanted = set(ids)
        selected = tuple(s for s in self.steps if s.id in wanted)
        if tuple(s.id for s in selected) != tuple(ids):
            raise ValueError("candidate IDs must follow manifest order")
        if any(not set(s.requires) <= wanted for s in selected):
            raise ValueError("candidate is not dependency closed")
        return selected

    def remove_dependents(self, ids, remove):
        kept = set(ids) - {remove}
        for step in self.steps:
            if step.id in kept and not set(step.requires) <= kept:
                kept.remove(step.id)
        return tuple(s.id for s in self.steps if s.id in kept)
