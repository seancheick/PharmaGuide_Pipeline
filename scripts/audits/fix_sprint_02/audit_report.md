# Fix Sprint 02 — audit report

- **content_hash:** `sha256:12f7597461fd5c94762abeb32781cf3f8767bef457df4ad154c95b11845db120`
  (pinned in both repos)
- **reviewer:** `lead_clinician_fix_sprint_02` · **2026-07-23**
- **corpus after:** verified **15** · needs_revision **5** · rejected **1** ·
  unverified **59** (total 80)
- **scope:** exactly 3 records, as directed. Not broadened.

## Dispositions

| Entry | Result | Key change |
|-------|--------|------------|
| DEP_STATINS_COQ10 | **verified** (severity→mild) | relationship kept; causal myopathy + routine-supplementation claims removed; conflicting supplementation meta-analyses both cited |
| DEP_CORTICOSTEROIDS_CALCIUM | **verified** | narrowed to prolonged systemic use; universal calcium dose → guideline-directed fracture-risk assessment |
| DEP_CORTICOSTEROIDS_VITAMIND | **verified**, **retyped `depletion` → `monitoring_stability`** | CYP24A1/hepatic mechanism deleted as unsupported; reframed as bone-health monitoring |

## Field-level results

`verified | needs_revision | unsupported | not_applicable` — entry-level status is
the roll-up (`verified` only when every published field passes). Full per-field
detail with actions is in `research.md`.

| Field | statins→CoQ10 | cortico→Ca | cortico→vitD |
|-------|---------------|------------|--------------|
| relationship | verified | verified | **unsupported** (as depletion) → retyped |
| scope | verified | needs_revision | needs_revision |
| mechanism | needs_revision | needs_revision | **unsupported** |
| clinical impact | **unsupported** | needs_revision | needs_revision |
| monitoring | **unsupported** | verified | verified |
| recommendation | **unsupported** | **unsupported** | **unsupported** |
| consumer copy | needs_revision | needs_revision | **unsupported** |
| citations | needs_revision | needs_revision | needs_revision |
| comparison amount | **unsupported** | **unsupported** | **unsupported** |
| relationship type | verified | verified | **unsupported** → retyped |

## Defect tally (this sprint)

| Category | Count | Where |
|----------|-------|-------|
| Causal overstatement | 2 | statins (CoQ10→myopathy), cortico→vitD ("can lower vitamin D") |
| Universal recommendation | 3 | statins (routine 100–200 mg), cortico→Ca ("All patients should take…"), cortico→vitD (1,000–4,000 IU) |
| Unsupported dose | 3 | 100–200 mg CoQ10; 1,000–1,500 mg Ca; up to 4,000 IU vitamin D |
| Overly broad route or drug scope | 2 | both corticosteroid records (systemic vs inhaled/topical/short-course) |
| Mechanism error | 2 | CYP24A1 described as hepatic; "cardiac CoQ10 particularly affected" |
| Placeholder citation | 3 | NIH-ODS CoQ10 / Calcium / Vitamin D fact sheets, none of which support the drug-specific claim |
| Unsupported comparison amount | 3 | `adequacy_threshold_mg` 100 (CoQ10) and 500 (Ca), `adequacy_threshold_mcg` 25 (vitD) — all **removed** |
| Ghost PMID | 0 | — |

## Citations added (all PubMed content-verified)

26192349 · 8463436 · 30371340 · 32179207 (statins) — 37845798 · 14687590
(corticosteroids). Both statin-supplementation meta-analyses are cited
deliberately because they **disagree**; the copy states the uncertainty rather
than picking a side.

## Carried forward

`class:corticosteroids` still cannot be resolved to *systemic-only, >3-month*
exposure by the app. Scope is stated in the copy but cannot yet gate firing —
the same drug-class-resolver gap as Sprint 3 (diuretics / antacids /
anticonvulsants). Not to be mistaken for completed narrowing.
