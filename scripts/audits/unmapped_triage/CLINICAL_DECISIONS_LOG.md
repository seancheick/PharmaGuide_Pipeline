# Clinical Decisions Log

This file is the **authoritative record of clinical/policy decisions** that
affect data integrity. Decisions here are referenced by data files via
`clinical_notes` fields and by code via the `BLOCKED_PROBIOTIC_STRAINS` /
`HOLD_PROBIOTIC_STRAINS` constants in `scripts/constants.py`.

Format per decision:
- **Date** — ISO date
- **Decision class** — REJECT / HOLD / APPROVE / POLICY
- **Items** — affected data
- **Reasoning** — clinical/safety rationale
- **Action taken** — code/data changes that resulted

When a decision is updated or reversed, **append a new entry** rather than
edit the old one. The full history is the audit trail.

---

## 2026-05-01 — Probiotic strain safety decisions

**Source:** Clinician response to `CLINICIAN_REVIEW_REQUEST_2026-05-01.md` Priority 1.

**Approach:** Conservative — hold all BLIS Streptococcus strains until stronger strain-level human safety data is confirmed; reject the two with documented pathogen-genus risk.

### REJECT (do not add as IQM probiotic entries)

| Strain | Reason |
|---|---|
| **S. uberis KJ2™** | Streptococcus uberis is historically a bovine mastitis pathogen. Strain-level human-use safety data insufficient at this time. **Do not score as probiotic.** Products listing this strain remain unmapped (will not match any IQM probiotic parent). |
| **S. oralis JH145™** | Streptococcus oralis includes opportunistic-pathogen strains. Strain-level human-use efficacy data for JH145 insufficient. **Do not score as probiotic.** |

**Action:**
- Do NOT create IQM entries for these strains
- Items remain in unmapped triage
- Future product scans hitting these labels will surface in unmapped pool for product-team awareness

### HOLD (do not score yet, revisit when data improves)

| Strain | Reason |
|---|---|
| **S. rattus JH145™** | Streptococcus rattus is dental-caries-associated genus. Need confirmation JH145 is a non-cariogenic, well-characterized strain before scoring. |
| **S. oralis KJ3™** | Same reasoning as JH145 — strain-level data insufficient. |

**Action:**
- Same as REJECT (no IQM entry, surface in unmapped) but flagged as HOLD rather than permanent rejection
- Re-review when BLIS publishes peer-reviewed strain-specific human safety + efficacy data

### POLICY (general)

| Genus | Rule |
|---|---|
| **Enterococcus** | Strain-level only. NEVER bulk-add. Each strain must be individually evaluated for VRE / vancomycin-resistance and pathogen-vs-probiotic profile. |
| **Streptococcus oral-cavity probiotics** | Conservative-by-default — require strain-level human safety data + peer-reviewed efficacy before adding to IQM. BLIS-branded products marketed for oral health are not auto-approved. |

---

## 2026-05-01 — SPM mapping policy

**Source:** Clinician response Priority 2.

**Decision:** Generic family terms (`Resolvins`, `Protectins`, `SPMs`) map to omega-3 SPM precursor (17-HDHA form). Specific named compounds (`Resolvin D5`, `Protectin DX`, etc.) get distinct IQM entries with verified PubChem CIDs.

**Action taken:**
- Stripped `Resolvin D5` / `Protectin DX` aliases from 17-HDHA precursor (commit `a541826`)
- Created `resolvin_d5` (CUI C3492734, CID 24932575) and `protectin_dx` (CUI C3886642, CID 11968800) as distinct IQM entries
- Both have `bio_score=7` placeholder + `review_status=needs_review` pending clinical bio_score confirmation
- Added permanent guard test `scripts/tests/test_cross_compound_alias_guard.py` to prevent regression

---

## 2026-05-01 — Algae Protein generic scoring

**Source:** Clinician response Priority 3.

**Decision:** Confirm `algae_protein` (generic source) entry with `bio_score=5`, `confidence_level=inferred`. Should NOT carry strong scoring weight — treat as low-confidence informational ingredient.

**Action taken:**
- Notes updated to document policy explicitly
- `dosage_importance` reduced from 1.0 → 0.5 to reflect "no strong scoring weight"
- Source-specific entries (chlorella, spirulina) remain unaffected and continue to score per their own profiles

---

## 2026-05-01 — Botanical wording adjustments

**Source:** Clinician response Priority 4.

| Entry | Change |
|---|---|
| `tu_fu_ling` | Removed TCM jargon ("clears damp-heat, detoxifies"). Replaced with consumer-friendly description ("anti-inflammatory and detoxifying tonic, particularly for skin conditions and joint discomfort"). |
| `bergamot_essential_oil` | Confirmed as WARNING NOTE only, NOT a B1 safety penalty. Notes clarify: oral supplement-grade flavor doses are below documented phototoxicity threshold; photosensitivity concern is primarily topical. Display warning to users; do not deduct from score. |
| `nutmeg_essential_oil` | Phrasing softened: "neurological effects at very high oral doses" (was "psychoactive at high oral doses"). Threshold ≥5g whole nutmeg confirmed accurate. |

**Action taken:** Notes fields updated in `botanical_ingredients.json`.

---

## 2026-05-01 — Glucosamine Salt source/form policy

**Source:** Clinician response Priority 5.

**Decision:** Leave `Glucosamine Salt` UNMAPPED. Don't default to either HCl or sulfate form. Surface for product-specific verification when encountered.

**Action taken:** No alias added. Item remains in remaining_unmapped_2026-05-01.json.

---

## 2026-05-01 — Branded blend headers policy

**Source:** Clinician response Priority 6.

**Decision:** **Opaque-by-default** — when a brand blend has no disclosed children rows in DSLD, treat as OPAQUE_BLEND (B5 transparency penalty fires). Allowlist (BLEND_HEADER_EXACT_NAMES in `scripts/constants.py`) is reserved for blends with **consistently verified disclosed children** across multiple products.

**Action taken:** Existing 4-state classifier and BLEND_HANDLING_POLICY.md remain authoritative. Team work on per-product verification proceeds under this policy.

---

## How this log connects to data files

- Entries with `clinical_notes` containing "per clinician decision YYYY-MM-DD" reference this log
- Code-level constants (e.g., `BLOCKED_PROBIOTIC_STRAINS` in `scripts/constants.py`) implement the REJECT / HOLD decisions
- Test guards (e.g., `test_cross_compound_alias_guard.py`) make decisions machine-enforceable

When updating a clinical decision, update both this log AND the corresponding data fields/constants/tests.
