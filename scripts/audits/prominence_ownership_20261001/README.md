# Phase 2 — generic Evidence prominence ownership

Status: **PINNED CODEX AUDIT IMPLEMENTED AND MEASURED; FINAL FAST PASSED; NOT INTEGRATED.**
Codex fixes through `9f7837e8` extend Claude production `b43a048f` on the isolated
`codex/quality-completion` branch. Claude subsequently advanced production to `68cae99a`
(fetched feature tip `002d2683`); those later changes require reconciliation and a new candidate
checkpoint. Main remains outside this audit. No push or catalog release authorized/performed by this Codex audit; Claude has pushed its feature branch for review.
Historical Claude progress below is preserved as history, superseded by the dated audit receipt
for Codex validation status. Older numbers do not validate a later candidate.

## Measured results (final source `68cae99a`)

All arms are complete Clean→Enrich→Score captures of frozen raw DSLD labels with
`scripts/audits/quality_redesign/replay.py`; every capture reports `exit_code 0`,
`source_unchanged true`, full product coverage and the same input manifest as its baseline.
Baselines ran on `e8687b39` (clean detached worktree `prominence-base`); candidates on the
isolated detached worktree `prominence-final` at `68cae99a`. Outputs live in
`~/pg_quality/prominence_20261001/`; every changed product of every arm is listed with its
cause columns in `replay_*_changed.md` in this folder (produced by `classify_movers.py`).
Earlier candidate runs are archived in `superseded_*` folders there.

| Arm | Inputs (manifest SHA-256) | Baseline output | Candidate output | Result |
|---|---|---|---|---|
| Targeted, 2,781 labels | `2b314063…5c41c` | `9ba85f1a…2b5` | `e7f37b56…b067` | 2,654 identical; 14 totals move, **all down**; tiers Good→Needs improvement 2, Needs improvement→Poor 2; 113 metadata-only |
| Controls, 1,259 labels (Codex set: 542 probiotic, 717 others) | `cbe04144…8286` | Codex `a20cea18…ea72` (head `3ee91eae`; all 434 source hashes equal to `e8687b39`) | `a345a53c…ff95` | 1,252 identical; **0 score moves**; 7 readiness-metadata-only (omega/probiotic) |
| Brand identifiers, 48 labels | `4f62f9a2…55ea` | `66a228a2…b5a` | `b7dea4de…7d7` | 47 identical; 219249 readiness lists `BRAND_UCII` on its "UC-II Type II Collagen Complex 20 mg" adjunct row |
| Raw coverage, 2,964 labels | `6a4b4807…086a` | `cohort2_baseline` | `3df7e371…54b9` | 2,908 identical; 52 totals move, **all down**; tiers Good→Needs improvement 6, Needs improvement→Poor 7; 4 metadata/no-score |
| D26 counterfactual (four stand-ins removed) | targeted + raw coverage | final candidate | `d79b4eaf…95f6`, `333c5336…a87c` | 793 and 22 totals up, none down (D26 packet) |

Every arm: Evidence is the only pillar that moves; status, route, Safety/Hygiene, Dose,
Formulation, Transparency and Verification are unchanged for every product. In total **66
distinct products move, all down, 17 crossing a quality tier**; every probiotic in every arm keeps
its score (the approved probiotic model's inputs are unchanged, defect 19).

**Coverage.** 7,015 distinct raw labels were replayed (22 overlap between the targeted and control sets, 13 between targeted and brand-identifier). The raw-coverage cohort holds every raw label (of 15,414) not already frozen whose
label prints a blend total over at least one undisclosed member (1,464 → 52 movers) plus a seeded
random 1,500 of the other 9,902 labels (→ **0 movers**). The 8,402 labels never replayed all lack
that structure; 0 of 1,500 bounds their mover rate below about 0.2% (rule of three).

### Every product whose score moves

| ids | products | total | Evidence | cause |
|---|---|---|---|---|
| 219048, 219049, 270532, 317119, 333746 | Fiber Fusion Daily | e.g. 75.8 → 61.8 (Good → NI) | 20 → 6 | psyllium floor 18 rested on the 3.1 g four-fiber blend total (defect 2) |
| 79233, 227922, 230979, 76540 | Thisilyn Daily Cleanse / Cleanse Part II / Part II Digestive Health / Fiber Formula | e.g. 71.8 → 57.8 | 20 → 6–10 | psyllium floor 18 on 1.3–3.4 g five- or six-fiber blend totals (defect 2) |
| 328062 | Sleep Tonight | 72.8 → 59.7 (Good → NI) | 20 → 6.9 | Sensoril floor 18 on the 250 mg two-member blend total (defect 2) |
| 2219, 28981 | Ravage Grape / Fruit Punch | 30.7 → 22.0 | 20 → 11.3 | creatine floor 18 on the 3.1 g ten-member creatine module total (defect 2) |
| 2221, 36992, 42235, 42236, 42237, 63923 | Re-Built Mass (six flavors) | −6.1 to −7.8 | 20 → 12.2–13.9 | creatine floor 18 on the 10 g ten-member "Advanced Creatine Complex" total (defect 2) |
| 28973 | ReBuilt Mass Chocolate | 67.6 → 63.2 | floor 18 creatine → 14 protein | same creatine complex total; the protein floor (its own disclosed amount) remains (defect 2) |
| 74753, 176055 | Amplified Creatine XXX | 38.7 → 29.8 | 18 → 0 floor | creatine floor on the 10 g six-member "Micronized Creatine Matrix Blend" total (defect 2) |
| 40581, 40595 | fucoPROTEIN | 62.0 → 53.6, 62.4 → 54.0 (NI → Poor) | 15.6 → 7.2 | protein floor 14 on the 15 g four-member protein blend total (defect 2) |
| 37217, 37224 | Rare Vanilla / Chocolate Fudge | 48.3 → 43.3 | 12.2 → 7.2 | glycine floor 11 on the 6.2 g three-member "Creatine Precursors" total (defect 2) |
| 5773, 5820, 5883, 25594, 27420, 45104, 70327, 79192, 315848 | Thermo Igniter 12X / X12 / Ultra Energy Generator | −8.4 each (three NI → Poor) | floor 14 → 0 | caffeine floor on the ~240 mg three-member thermogenic blend total (defect 2) |
| 5817, 5863, 18473, 297644, 333753 | Amplified Muscle Igniter 4X / FYI / Kidney Bladder | −3.4 to −9.6 | floor 14 → 0 | ginger root floor on four- to seven-member herbal blend totals (defect 2) |
| 5816, 5873, 25593, 30565 | Amplified Maxertion N.O. / Muscle Fatigue Buffer | −3.7 | floor 6.6 → 0 | L-arginine floor on the two-member "PEG-Arginine System" total (defect 2) |
| 62116, 178632, 327953, 332914 | Echinacea & Goldenseal | −4.8 to −5.1 (two NI → Poor) | floor 9.35 → 0 | echinacea floor on two- to seven-member herbal blend totals (defect 2) |
| 40598, 273822 | Purify / Perfect Cleanse Purify | 65.1 → 61.4 | floor 14 → 0 | milk thistle floor on the 1 g six-member blend total (defect 2) |
| 184497, 199530 | Change-O-Life | 49.8 → 45.5 | floor 6.6 → 0 | black cohosh floor on the six-member blend total (defect 2) |
| 251338, 254958 | Centrum Immune & Digestive Support | 54.3 → 44.7 | floor 14 → 0 | inulin floor on the 400 mg three-member botanical blend total (defect 2) |
| 273825, 321361 | Raw Cleanse Organ Detox / Organ Detox | 52.9 → 48.9 | floor 11 → 0 | chlorella floor on the 2 g four-member greens blend total (defect 2) |
| 327398, 327399 | Grass Fed Collagen Protein | 48.7 → 39.1 | floor 14 → 0 | collagen-peptide floor on the 22 g four-member protein blend total (defect 2) |
| 82935 | Stress Hormone Balancing Blend | 55.4 → 43.8 (NI → Poor) | floor 14 → 0 | phosphatidylserine floor on the 400 mg two-member total (defect 2) |
| 251578, 251594, 308198, 323062 | Ex-Stress / Garlic Parsley / Glucosamine Chondroitin / Calming Day | −0.6 to −7.0 | floor → 0 | lemon balm, garlic, MSM and taurine floors on two- to six-member blend totals (defect 2) |
| 241676, 268562, 268575, 326268 | Collagen Love / Multi-Collagen Complex / Multi Collagen 1600 mg | −6.3 each (one NI → Poor) | 6.3 → 0 | collagen record recovered from a blend total lent to its first member (three four-member blends; 241676 has one member, see notes) (defect 12) |

Each member keeps its Evidence ownership and research points; only the floor or recovered record
that read a blend total as the member's dose is gone. Exact per-product values:
`replay_targeted_changed.md` and `replay_raw_coverage_changed.md`.

### Changes without a score movement

- Targeted 113: 102 readiness/confidence metadata from role materiality (defect 3; more disclosed
  rows are `material`) including the 20 BCAA labels, whose recovery now matches baseline;
  3 turmeric labels lose a narrowing re-stamp (defect 7); 3 valerian recoveries (315311, 333901,
  333903: a 200 mg major row with its own amount that passes the retained stand-in; points
  already covered); 6 owner-set additions (63330, 63475, 210738, 229547, 297666, 328292; defect 3).
- Raw coverage 4: 273823 and 40604 lose a magnesium authority floor that rested on the lent
  "Epsom Salt" blend total (their pipeline already exceeds 10); two floor-only changes with no
  total movement (classified in `replay_raw_coverage_changed.md`).
- Controls 7 and brand 1: readiness metadata as above; no control product changes score.

### Reproduction

```
P=/Users/seancheick/.pyenv/versions/3.13.3/bin/python
R=scripts/audits/quality_redesign/replay.py
$P $R freeze-raw --raw-root ~/Downloads/PharmaGuide_Datasets/staging/brands --ids <ids.json> --frozen-root <F> --manifest <F>/manifest.json
$P $R snapshot --checkout <worktree at e8687b39> --products-root <F> --manifest <F>/manifest.json --out base.jsonl --workers 4
$P $R snapshot --checkout <worktree at b43a048f> --products-root <F> --manifest <F>/manifest.json --out cand.jsonl --workers 4
```

Id lists: `targeted_ids.json` (stored-corpus movers of every draft plus canaries),
`brand_identifier_ids.json`, `cohort2_ids.json` (`select_cohort.py` in this folder, seed 20261001).
The counterfactual arm is a scratch detached worktree at `b43a048f` patched by
`counterfactual_patch.py` (never committed). Classify with
`classify_movers.py <checkout> base.jsonl cand.jsonl out.json out.md`. Run snapshots only from a checkout nothing commits to: the harness also checks HEAD.

## Combined integration candidate — October 1

Codex is reconciling latest Claude source `68cae99a` with the independently audited member-total safeguards and the Q51 unit-map replacement. Earlier receipts apply only to their named sources. Combined regression, replay and final checkpoint results will be recorded before main integration.
