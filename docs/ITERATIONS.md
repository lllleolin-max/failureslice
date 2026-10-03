# Review corrections / 自审修正

Initial implementation `db8e99c53842e67b6d47bbb4660e474b2dfd8340` completed the package, SDK, registered CLI, tests, real process fixtures, contrast and bilingual documentation. An exact archive ordinary wheel passed 19 tests and the installed console demo (size=3, calls=56, states=64) before correction cycles. The initial output-overflow test startup budget and archive-check pipe encoding needed harness corrections; these are **not** counted as cycles. All three substantive correction commits below are direct children of the stated before commits; no initial feature chunks are relabeled review cycles.

The unchanged safe-output probes are `tools/review_probes.py`. Commands run that file using the fresh installed venv Python produced by `python tools/archive_check.py SHA --suite --label LABEL`; probes therefore import ordinary wheels from exact Git archives, without editable install, source overlays or PYTHONPATH. Raw host paths/logs remain in ignored `.local/`; tracked safe receipts preserve exact SHAs, test counts, module digests, actual probe output and exit codes. Verification date: 2026-10-03, Windows/Python 3.14. Remote CI remains unknown.

## Cycle 1: metadata was confused with failure identity

Before: `db8e99c53842e67b6d47bbb4660e474b2dfd8340`. Newly discovered: repeated identical target signature with `detail='duration=1'` then `detail='duration=2'` produced INCONSISTENT because the cache compared the entire observation JSON. This falsely rejected a valid same-signature reproducer for changing diagnostic metadata. `review_probes.py diagnostic_metadata` before: exit 1, `passed=false`, outcome INCONSISTENT, two observations.

Correction: compare classified outcome and structured signature, preserve every diagnostic detail in the transcript. After: `5ac8cdb6c2bdbe0eeadbfe1312156e7d5cf5f2f9` (direct parent is before SHA). The same probe exited 0, TARGET/two observations; ordinary archive wheel suite: 20 tests PASS; all seven module byte sequences equal canonical Git blobs, archive, wheel and installed package. Different outcomes/signatures still yield INCONSISTENT. A finite repeat count still cannot prove absence of rare flakes.

## Cycle 2: external mutation could rewrite historical signatures

Before: `5ac8cdb6c2bdbe0eeadbfe1312156e7d5cf5f2f9`. Newly discovered: Observation was frozen only shallowly. Modifying a caller-owned returned signature dictionary or an Evaluation signature also modified the cache's historical observations. `review_probes.py mutable_observations` before: exit 1; zero fresh calls; cached TARGET while both recorded signatures had changed to `report-mutation`. This violated the evidence-retention contract.

Correction: store canonical immutable observation bytes internally; every Evaluation and `history` view reconstructs detached signature dictionaries. After: `c14e8bfaed60d5ee8c8108985786d51310dc366d` (direct parent is before SHA). Unchanged probe exit 0, zero fresh calls, both signatures remain `import-original`; ordinary archive wheel suite: 21 tests PASS and seven modules byte-equal. Refresh still appends contradictory real observations and permanently classifies them INCONSISTENT for that key. Deliberately editing private internal implementation state is outside the SDK contract.

## Cycle 3: a certificate mixed declared environments

Before: `c14e8bfaed60d5ee8c8108985786d51310dc366d`. Newly discovered: cache keys changed with identity, but the reducer aggregated results across those different environments into one exact certificate. A callback changed declared environment version during the empty-subset observation. `review_probes.py declared_identity_drift` before: exit 1, `complete=true`, CARDINALITY_MINIMUM_AND_INCLUSION_MINIMAL, eight calls. Such evidence cannot establish a minimum under one declared environment.

Correction: pin full manifest/oracle/repetition context for a reduction; bind it into each cache key; check declared context after actual callbacks; retain raw observations but mark unstable context and stop with UNKNOWN. After: `3a9e2e15b3a997ce9e105ea69990e5d3cd4c40c9` (direct parent is before SHA). Same probe exit 0, `complete=false`, UNKNOWN, three actual calls. Ordinary archive wheel: 23 tests PASS, installed console demo PASS, four-case real contrast PASS, all seven modules byte-equal. The prior two unchanged probes also PASS. Excluded transient environment changes remain undetectable; this fix does not create statistical or OS isolation guarantees.

Subsequent validation hardening rejects null runner path collections, mistyped Observation details and signatures on non-failure observations with actionable ValueError/CLI exit 2, rather than escaping as a TypeError traceback. It adds protocol/exit mismatch and hardlink-alias tests; this extra change is not used to inflate the required three cycles. See final verification receipts for the current suite and exact artifact.
