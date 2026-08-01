# Offline benchmark contract

`sets/train/` is the development-facing fixture set. `sets/held-out/` is a
read-only regression set: normal benchmark commands never update either fixture
set, and no command accepts a held-out update option. Record a new baseline in
`baseline.json` only after review of a completed benchmark run.

Run the deterministic current implementation with:

```bash
python3 scripts/run-benchmarks.py
```

The runner dispatches each fixture to the current deterministic `harness_core`
learning, PR, or code-mapper function. It does not accept a JSON file of
claimed results. The harness adoption gate passes only when a baseline exists,
the train score strictly improves, and no fixture that passed in the baseline
fails in the current run. The command reports eligibility only; it does not
edit harness-tier files.

Every baseline records the complete sorted train and held-out case ID lists,
plus the passing IDs within each list. Evaluation fails before comparing scores
when either fixture universe differs. Scores must equal the corresponding
passed-ID counts, and the report lists per-case improvements and regressions;
adding a new fixture can therefore never masquerade as a candidate improvement.

The checked-in baseline is the replay of the exact current fixture inputs
against predecessor revision `7b017989ff7fd531b8606da6fef3ad6e1576bd1b`
(`feat: add portable skill adapter baseline`).  `source_case_outcomes` records
one boolean for every train and held-out ID, and the runner rejects missing or
contradictory evidence. The runner also resolves that exact commit locally,
loads its deterministic `harness_core` from a temporary archive without
changing the checkout, replays the current fixture inputs, and requires exact
agreement with every recorded outcome. A nonexistent revision or coordinated
revision/result forgery is therefore invalid. The replay produced these
observable outcomes:

| Set | Case | Predecessor result | Baseline |
| --- | --- | --- | --- |
| train | `learning-rootless-is-proposal` | rootless project change returned `APPLY`, not compatibility `PROPOSAL` | fail |
| train | `pr-actionable-converged` | `CONVERGED` | pass |
| train | `mapper-fallback-is-approximate` | `unavailable`, approximate | pass |
| train | `pr-local-audit-raw-report-redacted` | presentation-boundary operation did not exist | fail |
| held-out | `learning-harness-is-proposal` | `PROPOSAL` | pass |
| held-out | `pr-design-question-escalates` | `NEEDS_HUMAN` | pass |
| held-out | `mapper-uninitialized-is-not-healthy` | `not_initialized`, not approximate | pass |

Thus the genuine predecessor baseline is train `2/4` and held-out `3/3`.
The unchanged mapper held-out case is baseline coverage, not a candidate
improvement.

Learning fixtures without a trusted repository root are compatibility cases:
they must remain `PROPOSAL`, never `APPLY`.  PR presentation fixtures also
encode the local data boundary: `.harness/audit/` may retain the raw evidence
for reproduction, while any rendered report/evaluation surface containing the
same literal fails its fixture.  The runner never rewrites either fixture set.
