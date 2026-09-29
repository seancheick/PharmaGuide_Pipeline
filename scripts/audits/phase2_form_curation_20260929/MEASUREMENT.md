# Frozen raw replay

`scripts/audits/quality_redesign/replay.py` ran Clean → Enrich → Score over 14 freshly fetched raw
DSLD labels, comparing branch HEAD `30c4c46a` with this change.

- 11 labels moved from `not_scored` to `scored` because their disclosed mineral or vanadium source
  is now recognized.
- One already-scored Bis-Glycinato OxoVanadium label moved 85.7 → 85.8 in Formulation.
- Two controls were unchanged. One is the unresolved phosphorus-oxide label, which remains held.
- No route changed. No scored label became unscored.
- Newly scored totals span 51.3–85.6. These are release candidates for the later corpus/calibration
  phase; this phase does not publish them.

The concise machine-readable result is `replay_summary.json`. Full frozen inputs, snapshots, and
the complete delta remain under `~/pg_quality/phase2_20260929/run4`.

## Release-readiness sample

The same pre-Phase-2 baseline and candidate were replayed over the existing 143-label frozen
release-readiness set. Thirty-nine records changed at any captured field. The scoring behavior was:

- 6 labels moved from `not_scored` to `scored`, with candidate totals from 62.1 to 84.8.
- 28 already-scored labels changed numerically: 24 decreased and 4 increased. All movement was in
  Formulation, from -2.3 to +0.7 points (mean -0.54 among changed numeric scores).
- No scoring route changed and no scored label became unscored.
- The largest decrease was 2.3 points. This is the intended effect of applying one strict
  nondisclosure floor instead of historical per-parent exceptions.

Full snapshots and delta are `~/pg_quality/phase2_20260929/rr143_{base,candidate}.jsonl` and
`~/pg_quality/phase2_20260929/rr143_delta.json`.
