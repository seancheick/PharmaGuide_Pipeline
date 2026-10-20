# Lost safety subjects — October 19, 2026

Question: which label ingredients that have an interaction/profile rule get no warning, and why?
The app's pregnancy, condition and medication warnings come only from rule ids the pipeline writes
into the detail blob, so a rule the pipeline misses is invisible to the user.

## Method

- `missed_warnings.py` (coordinator's probe, copied unchanged) on the accepted 951a05415 capture
  (`~/pg_quality/corpus_20261019_post167/baseline_951a05415_unpinned.jsonl.records`, 15,414 labels):
  2,169 active label rows in 1,371 products whose rule did not fire.
- `classify_missed.py` assigns every row one cause from the enricher row at the same
  `raw_source_path`, using the production helpers `interaction_subject_refs` and
  `label_row_establishes_presence`. `*_covered_by_fired_rule` = every target of the missed rule is
  already warned at the same or higher severity by a rule that did fire. Output:
  `classified_951.out`, `classified_951.json.gz`.

| Class | Rows | Verdict |
|---|---:|---|
| `subject_reached_form_scope` | 1,113 | Correct non-warning. 1,097 are fiber; the only fiber rule is konjac glucomannan. The rest are vitamin A rows outside the preformed-retinol scope. |
| `subject_reached_not_present` | 625 | Correct non-warning: measured zeros ("Iron 0 mg", "Vitamin D 0 mcg"). |
| `subject_reached_header_not_scanned` | 59 | **Defect F1.** A blend header keeps its identity, but the scan skipped every IQM header. 29 are "Fiber Blend" (form scope keeps them silent), so 30 are real. |
| `identity_nulled` (+ covered) | 60 (+30) | **Defect F2**, not in this PR: `resolve_identity` drops the cleaner's identity on non-scorable rows. |
| `identity_swapped` (+ covered) | 192 (+87) | Identity owner (ADR-0005) and decisions for Sean; see below. |
| other | 3 | Two `excluded_nutrition_fact` rows (sodium, omega-3) plus one vitamin E additive row: a dose-threshold rule with a positive amount, left as is. |

## F1 — fixed (commit on this branch)

`enrich_supplements_v3.py::SupplementEnricherV3._collect_interaction_profile` and
`_is_interaction_label_row`:
- A blend header that keeps a specific identity and is present on the label is an interaction subject.
- Its amount is the blend's, never the substance's dose (D1c): dose rules read the amount as
  unknown, and no marker row is derived from a header.
- A header whose interaction subject (itself, its family or its twin) a present row inside it also
  answers to leaves that row as the subject: LAB4 Probiotics over its strains, a turmeric blend over
  its turmeric row.
- Other headers are scanned last, so a header only adds what no other row already warns about.
- `_blend_header_scope_row`: a header's declared forms still confirm the plant part for a
  part-scoped rule ("Stinging Nettle Root Extract" never meets the leaf glucose rule).

Tests: `scripts/tests/test_interaction_blend_header_subject.py`, 8 tests on 7 real labels.
Each test failed on the code it guards against: 4 on main, 2 on the first F1 version, 1 on the
second.

### Replay

Cohort: `cohort.json`, built by `cohort.py` from the 951 capture.
- 1,617 affected labels: every product with an identified header, an erased non-scorable
  identity, or a defect-class missed row.
- 600 seeded random controls.

Runs (`replay.py snapshot --full --blob`, receipts in `~/pg_quality/lost_subjects_20261019/`):
- `main_base.jsonl` on main 3c45aa69c versus `main_cand3.jsonl` on the final F1 code.
- 2,217 products: 26 changed, 26 rules added, 0 removed.
- `compare --all-paths`: only `enriched` interaction_profile/safety_hits paths and blob
  `warnings`/`interaction_summary` paths changed.
- Clean and Score records are byte-identical; no `quality_score_v4_100` or `product_safety_status`
  change; 0 of 600 controls changed.
- Re-check after rebasing onto main 941d273d3 (#178, #180, #182 merged): 91 labels (the 26, the
  40 named cases, 30 controls) give the same 26 additions and nothing else.

Every change is listed in `f1_changes.tsv` (header row, amount, identity, declared forms, targets);
`f1_replay_warning_diff.out` has the per-product diff. Classification:
- 24 are correct new warnings: the header names its substance.
  - Chondroitin Complex / Chondroitin Sulfate Complex: 2
  - Coenzyme Q10 complex: 3
  - Turmeric blends and complexes: 7
  - Curcumin Phytosome / C3 Complex: 2
  - Paractin andrographis: 2
  - Valerian root complex: 1
  - Quercetin phytosome: 2
  - Probiotic headers ("Lactobacillus acidophilus Blend" ×3, "Ultra Probiotics"): 4
  - Stinging & Dwarf Nettle root (blood-pressure rule only): 1
- 2 follow a curated identity whose precision is the identity owner's call:
  - 295773 Seneactiv → `ginseng`: a curated IQM alias, but its forms are Panax notoginseng and
    Rosa roxburghii.
  - 302654 Krill Oil → `fish_oil`: repaired by its DSLD group; it ties to the algae/omega-3
    subject-family follow-up.

The headers named on the brief: 12144, 247322, 278010 and 65963 gain their rules. Con-Cret
creatine (317610) and Siliphos (336352) already warned on main, because main's cleaner no longer
calls them headers.

## Not fixed here (owner, evidence, next step)

- **F2, erased identity on non-scorable rows** (`identity_integrity.resolve_identity`,
  `retained_unscoreable_canonical`):
  - Cases: "Caffeine Blend" (1179/12800/28981), "Lactobacillus" ×45, "Arginine" ×27 (the cleaner
    proved it by UNII 94ZLA3W45F), Chondroitin Sulfate Complex 17471, aloe, yerba mate, cinnamon,
    lion's mane.
  - Experiment: keep the supplied id unless the label names another, on the identity tip plus F1.
    40-label cohort: +12 rules, 0 removed.
  - But it moves scores (17471 71.7→76.9, 297685 62.8→66.1) and fails
    `test_disclosed_pea_protein_blend_keeps_source_evidence_without_individual_dose` and #181's
    `test_export_carries_the_enricher_identity_even_when_unresolved`.
  - The identity lane handed this branch to this lane, to land after PR #181 merges, with a
    narrower rule and a `/pg-scoring-change` measurement.
- **"Proprietary Blend" group → `BLEND_GENERAL`** (`blend_general_951.out`):
  - 48 products lose a rule on a label-named substance. Examples: 269286/269589
    "Saw Palmetto 320 mg" (Prosterol = saw palmetto berry extract; the saw palmetto rule includes
    pregnancy: avoid), Ester-C, MicroActive CoQ10, Green Tea extract 178791, 33 probiotic headers.
  - This is ADR-0005 point 2 policy.
- **Identity group rewrites** (identity lane, #181): olive leaf → olive fruit extract (12),
  schisandra fruit → `schisandra` (8). Japanese knotweed → resveratrol and cod/krill oil → fish
  oil need reviewed links.
- **Decisions for Sean:**
  - Green tea: standardized `green_tea` is described as a Camellia sinensis extract and carries
    the alias "green tea extract", yet a recorded decision (TEA_LEAF in
    `test_botanical_interaction_subjects.py`) keeps it from the `green_tea_extract` rules.
    182855 "Green Tea (Camellia sinensis) extract 100 mg" therefore gets no green tea
    liver/hypertension warning (16 products on the 951 capture).
  - `RULE_INGREDIENT_OMEGA_3` (heart disease, informational) is authored on IQM `omega_3`
    ("Minor Omega-3 Fatty Acids & SPM Precursors"), so fish-oil "Omega-3 Fatty Acids" rows (120)
    never meet it. Fish oil's own bleeding rule does fire.
  - `_is_generic_unspecified_omega3` sends every generic "Omega-3 Fatty Acids" total to
    `fish_oil`, whatever its algal parent (293409, 278454, 323711).
  - 42683/43191 Nordic Naturals Algae Omega are label-correction candidates: the raw DSLD form
    says "Fish Oil".
  - Prenatal "Omega-3 DHA" (269824/270736) routes to `PII_PURIFIED_FISH_OIL`, a carrier oil, so
    the fish-oil rule is lost.
- **Next in this lane:** a reviewed `algae_oil` → omega-3 interaction link, sourced through
  `/data-fix`, then a fail-first test on 305211 once #181 is on main.
