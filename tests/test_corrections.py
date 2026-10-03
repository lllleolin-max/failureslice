import unittest
from failureslice import EvidenceOracle, Manifest, Observation, Outcome, Step, reduce


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

    def test_declared_context_cannot_change_during_certificate(self):
        target = {"kind": "original"}
        for mode in ("exact", "local"):
            m = Manifest((Step("a"), Step("b")), target)
            identity = {"version": 1}
            def callback(steps):
                if len(steps) < 2:
                    identity["version"] = 2
                    return Observation(Outcome.PASS)
                return Observation(Outcome.TARGET, target)
            r = reduce(m, EvidenceOracle(m, callback, identity), mode=mode)
            self.assertFalse(r.complete)
            self.assertEqual(r.certificate, "UNKNOWN")
            self.assertFalse(r.evaluations[-1].context_stable)
            self.assertEqual(r.evaluations[-1].observations[0].outcome, Outcome.PASS)

    def test_manifest_mutation_during_callback_is_not_evidence(self):
        target = {"kind": "original"}
        m = Manifest((Step("a", payload={"version": 1}),), target)
        def callback(steps):
            steps[0].payload["version"] = 2
            return Observation(Outcome.TARGET, target)
        e = EvidenceOracle(m, callback, {}).evaluate(("a",))
        self.assertEqual(e.outcome, Outcome.ERROR)
        self.assertFalse(e.context_stable)
