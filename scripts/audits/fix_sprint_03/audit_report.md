# Fix Sprint 03 — audit report

- **reviewer:** `lead_clinician_fix_sprint_03` · **2026-07-24**
- **content_hash (after):** `sha256:6ac4788dc7166310670a1b5e6c49fd86a2a0503651b28956501eed5cc2bec3d3`
  (pipeline pin; app-side parity pin updated in the app PR)
- **scope:** class-resolution defects only (diuretics, PPI, enzyme-inducing AEDs).
  Exactly 3 depletion records repointed, plus one drug-class taxonomy fix found
  in flight. No blanket repoints. No entry promoted to `verified`.

## Dispositions

| Change | Result |
|--------|--------|
| New `class:loop_and_thiazide_diuretics` (21 members, K-sparing excluded) | created, all rxcuis RxNorm-verified |
| `DEP_DIURETICS_POTASSIUM` → loop+thiazide, copy fix | repointed |
| `DEP_DIURETICS_MAGNESIUM` → loop+thiazide | repointed |
| `class:thiazide_diuretics` 3 misaligned rxcuis | corrected (found in flight) |
| New `class:enzyme_inducing_antiseizure_medications` (4 members) | created, RxNorm-verified |
| `DEP_ANTICONVULSANTS_VITAMIND` → enzyme-inducing AEDs | repointed |
| `DEP_ANTACIDS_VITAMINB12` → `class:proton_pump_inhibitors` | repointed |
| `DEP_ANTACIDS_MAGNESIUM` → PPI + citation corrected | repointed |

## Deliberately NOT touched (deferred to later entry-specific audits)

- Diuretics: `FOLATE` (triamterene-specific), `CALCIUM` (loop-specific),
  `THIAMINE` (furosemide-specific), `ZINC` (TBD) — stay on `class:diuretics`.
- Antacids: `CALCIUM`, `IRON`, `VITAMINC`, `ZINC` — stay on `class:antacids`.
- Anticonvulsants: `CALCIUM`, `FOLATE`, `VITAMINB12`, `VITAMINK`, `BIOTIN`,
  `LCARNITINE` — stay on `class:anticonvulsants`. `BIOTIN`/`LCARNITINE` are
  valproate-specific and must never enter the enzyme-inducing class.

## Safety hazard removed

`class:diuretics` mixed loop, thiazide, and **8 potassium-sparing** agents
(amiloride, spironolactone, eplerenone, triamterene, canrenone, finerenone, +
2 vaptans). The potassium/magnesium records therefore fired "you may be low on
potassium — eat bananas / consider K supplements" for potassium-sparing agents —
a hyperkalemia hazard. The two reviewed records now resolve only loop/thiazide
agents; a negative-membership regression proves no K-sparing rxcui can trigger
them.

## Landmine found in flight

`class:thiazide_diuretics` shipped 3 rxcuis positionally misaligned with their
names — its "quinethazone" row carried `9997` (**spironolactone**), "cicletanine"
carried `302285` (conivaptan), "methyclothiazide" carried `6774` (mersalyl). The
per-class schema test only compared list *lengths*, never `rxcui[i]↔name[i]`.
Corrected against RxNorm; a new cross-class pairing-consistency invariant
(`test_rxcui_name_pairing_consistent_across_classes`) makes it un-shippable
again.

## Citation defect taxonomy (this sprint)

| Category | Count | Where |
|----------|-------|-------|
| Misattributed citation | 1 | `DEP_ANTACIDS_MAGNESIUM`: PMID `22762246` is **Hess MW 2012, Aliment Pharmacol Ther** ("Systematic review: hypomagnesaemia induced by proton pump inhibition"), not the "Danziger … Kidney Int. 2013" label it carried. Real PMID, on-topic, label corrected to match the identifier. |
| Ghost citation | 0 | — |
| Placeholder source | 0 | — |
| Weak evidence | 0 | — |

Definitions: **ghost_citation** (PMID/URL unrelated) · **placeholder_source**
(generic source, not the specific relationship) · **misattributed_citation**
(real & relevant source, wrong author/title/journal label) · **weak_evidence**
(related but doesn't support the claim strength). The B12 citation (Lam JR, JAMA
2013 / PMID 24327038) was re-verified against PubMed and is correct.

## Permanent regressions added

- `test_rxcui_name_pairing_consistent_across_classes` — cross-class rxcui↔name
  alignment guard (catches the thiazide landmine class).
- `test_every_referenced_class_exists_has_members_and_resolves_rxcuis` — no dead
  / empty / non-resolving class reference from `medication_depletions.json`.
- Negative membership: no K-sparing agent in loop+thiazide; no valproate /
  oxcarbazepine in the enzyme-inducing class.
- Positive resolution: furosemide + hydrochlorothiazide → combined diuretic
  class; omeprazole → PPI; phenytoin/carbamazepine → enzyme-inducing AEDs.

## Remaining (app PR + rebuild)

Regenerate the bundled interaction SQLite (`drug_class_map`) and the med–nutrient
artifact into the app bundle, update the app-side parity pin
(`test/services/stack/med_nutrient_bundled_parity_test.dart`) to
`sha256:6ac4788d…`, and add the app-bridge resolution test (furosemide →
loop+thiazide, omeprazole → PPI, phenytoin → enzyme-inducing). Note: the app
bundle ships via Git LFS, whose budget is currently exhausted (see the CI-LFS
fix) — the regenerated blobs may need the budget restored before they push.
