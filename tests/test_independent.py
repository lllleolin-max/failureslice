"""Separate mathematical oracle: expected values are set relations, not reducer calls."""
import itertools
import random
import unittest
from failureslice import EvidenceOracle, Manifest, Observation, Outcome, Step, reduce

TARGET = {"type": "original"}


def universe(steps):
    # Independent powerset construction; compare set membership rather than manifest.select.
    ids = [s.id for s in steps]
    return [frozenset(subset) for size in range(len(ids) + 1)
            for subset in itertools.combinations(ids, size)
            if all(set(s.requires) <= set(subset) for s in steps if s.id in subset)]


class IndependentCertificates(unittest.TestCase):
    def test_arbitrary_nonmonotone_predicates(self):
        rng = random.Random(1731)
        for trial in range(24):
            steps = tuple(Step(str(i), tuple(str(j) for j in range(i) if rng.random() < .22)) for i in range(6))
            permitted = universe(steps)
            target = {s for s in permitted if rng.random() < .28} | {frozenset(s.id for s in steps)}
            expected_size = min(map(len, target))
            expected = {s for s in target if len(s) == expected_size}
            m = Manifest(steps, TARGET)
            def callback(candidate):
                return Observation(Outcome.TARGET, TARGET) if frozenset(s.id for s in candidate) in target else Observation(Outcome.PASS)
            result = reduce(m, EvidenceOracle(m, callback, {"trial": trial}, max_calls=10000))
            self.assertTrue(result.complete)
            self.assertEqual({frozenset(s) for s in result.alternatives}, expected)
            self.assertEqual(len(result.candidate), expected_size)
            observed = {frozenset(e.candidate) for e in result.evaluations}
            self.assertEqual(observed, set(permitted))
            self.assertEqual(result.calls, len(permitted) * 2)
            self.assertFalse(any(t < frozenset(result.candidate) for t in target))

    def test_equal_minima_not_unique(self):
        m = Manifest(tuple(Step(x) for x in "abc"), TARGET)
        target = {frozenset("abc"), frozenset("a"), frozenset("b")}
        callback = lambda steps: Observation(Outcome.TARGET, TARGET) if frozenset(s.id for s in steps) in target else Observation(Outcome.PASS)
        r = reduce(m, EvidenceOracle(m, callback, {}))
        self.assertEqual({tuple(x) for x in r.alternatives}, {("a",), ("b",)})

    def test_every_resource_bound_prevents_false_certificate(self):
        m = Manifest(tuple(Step(x) for x in "abcd"), TARGET)
        for calls in (1, 2, 3, 15):
            r = reduce(m, EvidenceOracle(m, lambda _: Observation(Outcome.TARGET, TARGET), {}, max_calls=calls))
            self.assertFalse(r.complete)
        for states in (1, 2, 5, 15):
            r = reduce(m, EvidenceOracle(m, lambda _: Observation(Outcome.TARGET, TARGET), {}), max_states=states)
            self.assertFalse(r.complete)


if __name__ == "__main__":
    unittest.main()
