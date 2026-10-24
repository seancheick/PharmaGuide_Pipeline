# Residual exact-label source correction — October 24, 2026

Runtime candidate: `e600050d67201ec90b8be22d22f0ff9e3c7a3658`; baseline: `39b2457e84ebd3a5831233aef35ef12eefc1ff85`.

Owner: `scripts/enhanced_normalizer.py::_apply_label_corrections` and label-display construction — evidence: exact raw paths, source PDFs, fail-first hierarchy, note-ownership and exported-depth regressions.
Owner: `scripts/normalization.py::extract_enzyme_activity` — evidence: printed activity units and existing activity/display callers.
Owner: `scripts/enrich_supplements_v3.py::_collect_proprietary_data` — evidence: existing source_descriptor and canonical disclosure consumers.
Will NOT create: another classifier, registry, scorer, public field, invented mass/activity conversion, benchmark or clinical approval.

## 275412 — RAW Enzymes Women 50 & Wiser

[Exact NIH archived label](https://api.ods.od.nih.gov/dsld/s3/pdf/275412.pdf), edition REWW90L-111114, UPC 658010115643. PDF SHA-256: `972fed921a162cffa75500dbead06a2901740202ba826814bc9fe214b2e76334`.

Visual source inspection establishes a 620 mg parent containing three groups (7 protein, 12 carbohydrate and 1 fat enzyme entries). A horizontal rule separates the 31 mg probiotic blend. Nattokinase 67 FU, SOD 5 SOD Units and mineral activators 1 mg remain separate. The correction changes working hierarchy while retaining original API source paths, and fixes the exported display depth through the same owner. It does not assign individual enzyme masses.

The API copied the probiotic blend's 500,000,000 CFU total into both species notes. That produced a false 1,000,000,000 CFU sum. Exact-path, name, amount, unit and original-note guards now place 500 million CFU on the blend only. Individual species counts remain unknown. “At time of blending” is retained; no expiry guarantee is inferred. A conflicting revision fails before any correction is applied.

Native Hemicellulase 1,248 HCU, Pectinase 65 PGU, Xylanase 840 XU and SOD 5 SOD Units are recognized and displayed by the shared activity owner. No conversion to mg or clinical adequacy was introduced. Unknown individual quantities and genuine blend limitations remain.

## 182990 — Mineral₂O

[Exact NIH archived label](https://api.ods.od.nih.gov/dsld/s3/pdf/182990.pdf), M2OPv1. PDF SHA-256: `d78376726f9ab58bd0db596afa43973d2daa027a6e09e4c5e33096020445133e`.

[Manufacturer brochure](https://www.pureencapsulationspro.com/media/18_10_Broch_NewProd_FIN_web.pdf), printed page 8, describes the naturally varying Great Salt Lake material and separate mineral sources. The exact frozen label controls quantities: calcium 50 mg, magnesium 150 mg, chloride 245 mg, sodium 6 mg and potassium **50 mg**. The brochure's 45 mg potassium belongs to a different edition and is not imported.

The 700 mg naturally occurring matrix uses the existing source_descriptor disposition rather than becoming a second elemental exposure or opaque list of separately formulated actives. Seven printed trace-element ranges remain ranges. Neither precise trace exposure nor a complete clinically usable profile is established. Existing clinical/benchmark holds remain; this source correction does not clear them.

## Shared defect class and control

232243's [exact NIH label](https://api.ods.od.nih.gov/dsld/s3/pdf/232243.pdf), Extraordinary Enzymes L01706E, confirms 12 enzyme entries including 4,000 HCU, 50 endo-PGU and 600 XU. The distinct ENDO-PGU qualifier is preserved. Existing whole-formula evidence anchors are not individual component doses. HDU display compatibility and per-mass concentration rejection remain covered.

## Bounded verification

Frozen raw replay: **22 products, zero errors**, unchanged inputs, 443 runtime source-file bindings. Only three totals change, through Transparency: 275412 62.9→66.2; 182990 61.7→70.2; 232243 42.9→52.7. Nineteen controls retain their totals. Dose, Evidence, Formulation, Verification and Safety pillar values, quality statuses, safety decisions, warnings and release-assessment/clinical blockers remain unchanged. Printed names, masses, nutrient quantities and canonical identities do not change. Seven previously missing native activity values and three corrected parent links are intentional changes. The derived probiotic total changes separately from one billion to 500 million CFU.

Fail-first coverage includes source revisions, missing/duplicate children, atomic note correction, CFU ownership, qualified assay units, conflicting units, unknown component quantities and exported hierarchy. Final named owner/consumer slice: **665 passed**. Final local rung: **546 passed / 24 declared optional-service skips**, skip guard passes. Independent source review found no remaining blocker in this bounded correction.

Unchanged Flutter ingredient, hierarchy and label-confidence consumer tests: **85 passed**. [Whole-fast CI40090782652](https://github.com/seancheick/PharmaGuide_Pipeline/actions/runs/40090782652) on exact runtime `e600050d67201ec90b8be22d22f0ff9e3c7a3658` passes **23,771 tests / 192 declared skips**, all four groups and skip guards green. Report-only follow-up changes no qualified runtime, data, configuration or test source. No whole-corpus rerun, catalog publication, real app import or clinical approval occurred. The user's recent 114 stage manifests match the pre-batch source; these corrections make all 38 Clean, 38 Enrich and 38 Score manifests stale. The next authorized regeneration must start at **Clean**. No manifest was restamped.

Scientific closure remains distinct from implementation. The existing clinical review handoff remains authoritative for required clinician approvals and unresolved benchmark applicability. Full-corpus integrity and real consumer verification remain pending rebuilt outputs.


## Adversarial follow-up — correction scope

Audited merged runtime e600050d6 at main e3939fd5, including changed production code/data, correction preconditions, hierarchy/CFU repeat application, typed activity handling, original source bindings and exported consumer metadata. One confirmed guard defect: the 182990 entry omitted the existing raw_source_path fence. Product ID, exact name and 700 mg amount matched, but a second physical row with those values inherited the source_descriptor exception. The current archived label has only one such row; the earlier measured result is unaffected.

Owner: `scripts/enhanced_normalizer.py::_apply_label_corrections` and the existing correction182990 — evidence: duplicate-row probe and a failing owner regression. Will NOT create: new matcher, clinical policy, scoring authority or public field. Resolution: set the existing `raw_source_path` to the reviewed `ingredientRows[5]`. No production algorithm changes. The regression proves a second physical row receives no exception, and an additional regression proves hierarchy/CFU correction is idempotent. The initial exported-row test encountered cleaner deduplication rather than the guard; the final fail-first test exercises the correction owner and failed on the incorrect exception before the fix.

Runtime candidate: `e8474a704302a7a65f6e918118c1bb85d7d99e08`. Named owner tests: **266 passed**. Exact data-batch check: only corrections/182990 changed, zero problems. New frozen22-label replay has **zero changed products** across Clean/Enrich/Score, zero errors, unchanged inputs and443runtime source bindings. This is a bounded replay, not a corpus rebuild. Existing consumer verification remains applicable because no app source or exported assessment changes. No further defect was found in this bounded adversarial review; that is not a guarantee that all possible inputs are bug-free. Final local: **546 passed /24 declared optional-service skips**, skip guard passed. Both saved PDF checksums still match the recorded source receipts. [Whole-fast CI40109157375](https://github.com/seancheick/PharmaGuide_Pipeline/actions/runs/40109157375) on exact runtime e8474a70 passes **23,773 tests /192 declared skips**, all four groups and skip guards green. Report-only follow-up changes no qualified runtime, data, config or tests.
