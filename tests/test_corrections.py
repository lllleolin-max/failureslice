import unittest
from failureslice import EvidenceOracle, Manifest, Observation, Outcome, Step


class CorrectionTests(unittest.TestCase):
    def test_diagnostic_variation_is_not_failure_variation(self):
        target = {"kind": "import-original"}
        m = Manifest((Step("a"),), target)
        details = iter(["duration=1", "duration=2"])
        o = EvidenceOracle(m, lambda _: Observation(Outcome.TARGET, target, next(details)), {"v": 1})
        e = o.evaluate(("a",))
        self.assertEqual(e.outcome, Outcome.TARGET)
        self.assertEqual([x.detail for x in e.observations], ["duration=1", "duration=2"])

    def test_observation_signatures_are_detached_from_cache(self):
        target = {"kind": "import-original"}
        shared = dict(target)
        m = Manifest((Step("a"),), target)
        o = EvidenceOracle(m, lambda _: Observation(Outcome.TARGET, shared), {"v": 1})
        e = o.evaluate(("a",))
        shared["kind"] = "external-mutation"
        e.observations[0].signature["kind"] = "report-mutation"
        o.history[e.key][0].signature["kind"] = "history-view-mutation"
        reused = o.evaluate(("a",))
        self.assertEqual(reused.fresh_calls, 0)
        self.assertTrue(all(x.signature == target for x in reused.observations))
