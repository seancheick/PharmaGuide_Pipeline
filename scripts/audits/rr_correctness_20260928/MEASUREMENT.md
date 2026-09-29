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

## Packet decisions applied (Sean, 2026-09-28)

Commits 99e160bc..90b94f87 on the same branch. Replay: baseline `212e5a1b`-equivalent code
(`wt_cand` at 99e160bc, whose only change is an audit script) against `42817875`, on the 143
sample, 222 targeted, 356 dosed-Chloride and 575 ranged-directions labels. 90b94f87 (review fix)
touches only a case none of these labels has (a title-embedded row-level mass as the heaviest row
of a sports product). No status, route or BLOCKED/UNSAFE change in any set.

| Set | Labels | Totals move | Down | Up |
|---|---:|---:|---:|---:|
| sample | 143 | 11 | 9 | 2 |
| targeted | 222 | 14 | 13 | 1 |
| chloride | 356 | 21 | 20 | 1 |
| ranged | 575 (556 scored) | 118 | 118 | 0 |

| Item | Commit | Movers (examples) | Cause |
|---|---|---|---|
| 7 release gate | 99e160bc | none (audit only) | `audit_scoring` reports `SCORING_SAFETY_ASSESSMENT_INCOMPLETE` |
| 1 form references | 342fc582 | none (test only) | 655 IQM parent references pinned |
| 5 chloride | b22a91a8, 57a83a39 | 69770 +0.2 (back to its pre-batch value); Transparency −0.1 to −3.0 on products whose macro lines (protein, carbohydrate, fiber) counted as active mass: Re-Size 42176 −3.0, Amplified Mass XXX 75181 −2.7, Energy & Metabolism ×4 −0.5 to −1.8, Airborne ×12 −0.1, Raw Organic Fiber 299755 −1.7 | a Nutrition Facts row earns no adequacy credit (UL kept) and is not label active mass, so a proprietary blend's hidden share is no longer diluted by macro grams |
| 2 daily basis | f20b75ef | ranged set: 93 Dose movers, all down, mean −6.8; glucosamine/MSM 182940 80.5 → 66.6, GS-500 184231 87.5 → 75.4, HMB 312819 74.5 → 65.2, N-Acetyl Glucosamine 311082 −9.1, Inulin 252551 −8.8; Evidence at the minimum: ALCAR 293877/307547 −7.3, CogniPhos 309486 −4.9 (now sub-clinical) | adequacy at the minimum directed daily use; excess at the maximum. Label directions checked on 7 movers, all genuine ranges (e.g. "2 capsules, 1-3 times daily"; 315703's own directions say one lozenge a day while DSLD allowed 2). Projected ~170 corpus products (joint ~48, fiber ~28), all down |
| 6 sports off-list | fd79fc35, 90b94f87 | Ravage 2219/28981 26.0 → 10.7, 1179 40.6 → 25.3, 12800 33.7 → 23.5; Wheybolic ×2 −0.7/−0.8, LIT ×2 −0.8 | an opaque blend total is not an off-list primary; calcium/niacin adequacy no longer stands in for sports Dose |
| 3 evidence review | 42817875 | all 8 products now show a reviewed state (7 `applicability_unestablished`, Fitbiotic `assessed`); Tesnor 315089 38.9 → 42.9 and Sytrinol 54775 42.8 → 49.5 (Formulation) | 7 literature records + 2 clinical entries; the botanical profile rates a branded extract with a clinical entry at the top of the form scale (existing policy). Evidence stays 0: Sytrinol's 150 mg is below the 300 mg studied dose; Tesnor is a DSLD blend heading, which evidence matching never reads (open question below) |

Checks: `scripts/test.sh fast` 17,694 passed, 170 skipped, 0 failed (no corpus link; log
`~/pg_quality/rr_fix/fast_packet.log`). Fresh-context review of the code diff: one bug (fixed in
90b94f87), docstring and comment gaps (fixed), sleep payload now reports the top daily amount.
