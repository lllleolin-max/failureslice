import unittest
from failureslice import EvidenceOracle, Manifest, Observation, Outcome, Step, reduce
from failureslice.jsonio import loads

T = {"kind": "original", "site": "import"}


class ModelTests(unittest.TestCase):
    def test_prerequisites_and_order(self):
        m = Manifest((Step("a"), Step("b", ("a",)), Step("c", ("b",))), T)
        self.assertEqual(m.remove_dependents(("a", "b", "c"), "a"), ())
        for ids in (("b",), ("b", "a"), ("a", "a"), ("unknown",)):
            with self.assertRaises(ValueError):
                m.select(ids)
        for steps in ((Step("a", ("b",)), Step("b", ("a",))), (Step("a"), Step("a"))):
            with self.assertRaises(ValueError):
                Manifest(steps, T)

    def test_strict_json(self):
        for raw in (b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":9007199254740992}', b'[' * 40 + b'0' + b']' * 40, b'"\xff"'):
            with self.assertRaises(ValueError):
                loads(raw)

    def test_integer_bools(self):
        m = Manifest((Step("a"),), T)
        for kw in ({"repetitions": True}, {"max_calls": True}, {"max_calls": 0}):
            with self.assertRaises(ValueError):
                EvidenceOracle(m, lambda _: Observation(Outcome.PASS), {}, **kw)


class EvidenceTests(unittest.TestCase):
    def test_alternation_not_favorable_vote(self):
        m = Manifest((Step("a"),), T)
        outcomes = iter([Observation(Outcome.TARGET, T), Observation(Outcome.PASS)])
        o = EvidenceOracle(m, lambda _: next(outcomes), {"v": 1})
        e = o.evaluate(("a",))
        self.assertEqual(e.outcome, Outcome.INCONSISTENT)
        self.assertEqual(len(e.observations), 2)
        self.assertEqual(o.evaluate(("a",)).fresh_calls, 0)

    def test_refresh_retains_contradiction(self):
        m = Manifest((Step("a"),), T)
        outcomes = iter([Observation(Outcome.TARGET, T)] * 2 + [Observation(Outcome.PASS)] * 2)
        o = EvidenceOracle(m, lambda _: next(outcomes), {"v": 1})
        self.assertEqual(o.evaluate(("a",)).outcome, Outcome.TARGET)
        refreshed = o.evaluate(("a",), refresh=True)
        self.assertEqual(refreshed.outcome, Outcome.INCONSISTENT)
        self.assertEqual(len(refreshed.observations), 4)
        self.assertEqual(o.evaluate(("a",)).outcome, Outcome.INCONSISTENT)

    def test_identity_content_target_and_repetitions(self):
        m = Manifest((Step("a", payload={"x": 1}),), T)
        identity = {"config": 1}
        o = EvidenceOracle(m, lambda _: Observation(Outcome.TARGET, T), identity)
        first = o.evaluate(("a",))
        self.assertEqual(o.evaluate(("a",)).fresh_calls, 0)
        identity["config"] = 2
        self.assertNotEqual(first.key, o.evaluate(("a",)).key)
        m.steps[0].payload["x"] = 2
        self.assertEqual(o.evaluate(("a",)).fresh_calls, 2)

    def test_other_signature_never_target(self):
        m = Manifest((Step("a"),), T)
        o = EvidenceOracle(m, lambda _: Observation(Outcome.TARGET, {"kind": "different"}), {})
        r = reduce(m, o)
        self.assertEqual(r.certificate, "INITIAL_NOT_TARGET")

    def test_partial_repetition_is_unknown(self):
        m = Manifest((Step("a"),), T)
        o = EvidenceOracle(m, lambda _: Observation(Outcome.TARGET, T), {}, max_calls=1)
        self.assertEqual(o.evaluate(("a",)).outcome, Outcome.UNKNOWN)

    def test_local_not_exact_nonmonotone(self):
        m = Manifest(tuple(Step(i) for i in "abcd"), T)
        target_sets = {frozenset("abcd"), frozenset("ab")}
        callback = lambda steps: Observation(Outcome.TARGET, T) if frozenset(s.id for s in steps) in target_sets else Observation(Outcome.PASS)
        local = reduce(m, EvidenceOracle(m, callback, {}), "local")
        exact = reduce(m, EvidenceOracle(m, callback, {}), "exact")
        self.assertEqual(local.candidate, tuple("abcd"))
        self.assertEqual(local.certificate, "TESTED_DEPENDENT_DELETIONS_ONLY")
        self.assertEqual(exact.candidate, tuple("ab"))

    def test_invalid_unknown_not_minimum(self):
        m = Manifest((Step("a"),), T)
        callback = lambda steps: Observation(Outcome.TARGET, T) if steps else Observation(Outcome.INVALID)
        r = reduce(m, EvidenceOracle(m, callback, {}))
        self.assertFalse(r.complete)
        self.assertEqual(r.certificate, "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
