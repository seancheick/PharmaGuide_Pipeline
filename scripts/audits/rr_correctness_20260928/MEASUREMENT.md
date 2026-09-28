# Correctness batch — replay measurement (2026-09-28)

Branch `claude/rr-correctness`, fixes for release-readiness findings RR-04, RR-07, RR-08, RR-09,
RR-10, RR-11 and register Q35 (audit in `scripts/audits/release_readiness_20260928/`, main checkout).
No `quality_score.json` change. Nothing here is a calibration choice; those are in
[CALIBRATION_PACKET.md](CALIBRATION_PACKET.md).

## Method

- Baseline: `65208a6d` (main when the batch started). Candidate: `212e5a1b`, which includes main
  `643e1569`; main's changes since the baseline touch only submission-review files, so every delta
  below comes from this batch.
- `scripts/audits/quality_redesign/replay.py snapshot` on frozen raw DSLD labels, clean → enrich →
  score, into `~/pg_quality/rr_fix/` (outside the repo):
  - sample of 143: the release-readiness audit sample (`~/pg_quality/rr_20260928/frozen`),
    route/archetype spread plus the products named in the window's commits;
  - targeted 222: every raw label each finding touches plus unaffected controls
    (`~/pg_quality/rr_fix/targeted_ids.json`, frozen in `frozen_targeted/`).
- Outputs: `base.jsonl` / `cand.jsonl` (sample), `tbase.jsonl` / `tcand.jsonl` (targeted); every
  label captured (143/143, 222/222). Delta script `~/pg_quality/rr_fix/delta.py`.

## Result

| Set | Labels | Totals move | Status changes | Route changes | BLOCKED/UNSAFE changes |
|---|---:|---:|---:|---:|---:|
| sample | 143 | 16 | 0 | 0 | 0 |
| targeted | 222 | 16 | 8 (not_scored → scored, Q35) | 0 | 0 |

Evidence display: 22 (sample) and 171 (targeted) authority-panel products change from
`not_yet_reviewed` to `assessed` with the same points (RR-11: the panel had been reviewed; only the
declared state was missing). 8 more gain `assessed` because they are now scored (Q35).

## Every mover, with its cause

| Product | Route | Before → after | Pillar | Cause |
|---|---|---|---|---|
| 233404, 233406 Keto Brain and Body Boost | generic | 40.4 → 59.1 | Form +9.6, Dose +3.1, Transp +6.0 | RR-07: FiberSMART read as an herb owner; fiber domain now; plus Nutrition Facts transparency fix |
| 275464 Fitbiotic | generic | 39.2 → 56.3 | Form +14.0, Dose +3.1 | RR-07, same cause |
| 17192, 177088, 212455, 214586, 242946, 252542, 25704, 259304, 54515 | fiber/generic/sports | +6.0 each (e.g. Psyllium 81.8 → 87.8) | Transparency | A printed Nutrition Facts line (Calories, Dietary Fiber) counted as an undisclosed active and blocked the full-disclosure credit (`generic_transparency._declared_active_count`, a981ff43/e6155012) |
| 223572, 248756, 271093, 321975, 322515, 323099, 323711, 328832 | multi, B-complex, generic | not_scored → 67.1–89.3 | all | Q35: salt token beside its compound (Quatrefolic, Metafolin), chelate descriptor (Albion) now match their IQM form |
| 232592 BioActive B-Complex | b_complex | 85.7 → 85.9 | Form +0.2 | Q35: folate now reads Metafolin |
| 220082, 220108, 220191, 220211, 221166 Wheybolic Ripped | sports | −2.6 each | Evidence | RR-04: the phantom "BCAA 22.4 g" row (the whole blend lent to one child) sat on the title-named Wheybolic Complex path and borrowed its title role; gone |
| 2219 Ravage Grape | sports | 27.5 → 26.0 | Dose −1.5 | RR-04: the creatine band came from the undisclosed "Creatine Module" total; the remaining 19.1 Dose is the off-list proxy (packet item 7) |
| 31148, 297614, 74903, 74861, 333872 | multi | −1.3 to −1.7 | Formulation | RR-04 in the shared gate (8250712e): a child lent its blend's total is not individually dosed, so panel dose coverage falls below 0.9 (e.g. 297614 1.00 → 0.89) and panel disclosure structure drops 2 → 1. The blend headers keep their printed mass |
| 321364, 219685, 69734, 27374 | multi | −0.2 to +0.1 | Formulation | Same cause, coverage stays on the same band; the lent row leaves the panel form average (±0.1) |
| 317611 Women's Ultra Mega Active | multi | −0.4 | Transparency | RR-09: a dosed blend Header keeps its mass, so the panel sees an opaque blend it had dropped |
| 69770, 63367, 9711 | multi | −0.2 to +0.1 | Dose / Form / Transp | RR-10: unsourced Chloride now an active row; enters the `rda_ul_data` panel (69770: 30 → 31 nutrients) and the form average (register D22) |

## Checks

- `scripts/test.sh fast` (corpus linked in): 17,701 passed, 127 skipped, 3 failed; the 3 are
  path-equality artifacts of the corpus symlink in `test_probiotic_structured_form_identity`
  (resolved vs link path). Log `~/pg_quality/rr_fix/fast_batch2.log`.
- Batch regression tests: `test_safety_assessment_incomplete_withholds.py`,
  `test_authority_panel_evidence_state.py`, `test_fiber_row_is_not_a_botanical_owner.py`,
  `test_blend_header_mass_stays_with_the_header.py`, `test_dosed_label_rows_keep_their_owner.py`,
  `test_salt_beside_its_compound.py`, each with real raw-label fixtures and an unaffected control.
- RR-08 is not visible in the replay (no resolver fails on real labels). Its test breaks the
  resolver on 12012 (→ `not_scored`, `safety_assessment_incomplete`, `not_assessed`) and keeps
  33360 BLOCKED.

## Not done here

One corpus pass from the clean stage and the release rung run after Sean's calibration decisions
and the merge, per AGENTS.md fix loop step 5.
