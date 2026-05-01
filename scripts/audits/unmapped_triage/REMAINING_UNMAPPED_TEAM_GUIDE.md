# Remaining Unmapped Ingredients — Team Mapping Guide

**Source triage:** `scripts/audits/unmapped_triage/unmapped_triage_2026-05-01.json` (AMBIGUOUS bucket, 204 items)
**Last automated pass:** 2026-05-01 (101 items resolved via Batches A–E across 14 commits this session)
**Remaining (after exec decisions D1/D3/D4 applied):** ~63 items

This document is for the team to work through item-by-item. Each section explains:
- WHY these items can't be auto-resolved
- WHAT decision is needed
- HOW to apply the fix when the decision is made

---

## ✅ Executive Decisions — APPLIED 2026-05-01 (commit `0e74c8e`)

| # | Category | Decision | Status |
|---|---|---|---|
| **D1** | Trace mineral systems / rare earths (~30 items) | **Option A approved** — single `NHA_TRACE_MINERAL_SOLUTION` entry covering all 50+ rare-earth + heavy elements, no scoring impact. | ✅ DONE |
| **D2** | Opaque blends | System already correct (4-state classifier + B5 transparency penalty). No action. | ✅ NO-OP |
| **D3** | Source ambiguity — Algae Protein (high-frequency first) | **Approved** — generic `algae_protein` IQM entry created with multi-source notes; bio_score=5 conservative; species-specific (chlorella/spirulina) excluded so disclosed labels route correctly. | ✅ DONE |
| **D4** | SPMs (Resolvins / Protectins) | **Approved** — map as omega-3 SPM precursor aliases (17-HDHA form) with notes that products typically contain precursors, not actual resolvins. | ✅ DONE |
| **D5** | Probiotic strains (S. rattus/uberis/oralis BLIS) | **Require clinician sign-off** — no exceptions. | ⏳ AWAITING CLINICIAN |
| **D6** | Cleaner artifacts | **Approved** — fix in `clean_dsld_data.py` parser (separate change). | ⏳ TODO (cleaner-side) |
| **D7** | Alias candidates | **Approved** — proceed with strict API-verification workflow (Section "CATEGORY 7" below). | ⏳ TEAM EXECUTING |
| **OPT** | `confidence_level` schema field | **Approved** — added to new entries (verified / inferred / unresolved). Backfill across existing entries in follow-on migration. | 🟡 IN PROGRESS |

**After executive decisions, remaining team work is concentrated in:**
- D5 (clinician sign-off needed) — 4 items
- D6 (cleaner-side fix) — ~12 items
- D7 (verifiable alias candidates) — ~15 items
- Branded blend headers (per-product DSLD verification) — ~20 items
- Niche single-occurrences requiring research — ~12 items

---

## 🆕 Optional improvement: `confidence_level` field (executive-approved)

New schema field on data entries to track verification state. Three values:

```json
{
  "confidence_level": "verified",   // API-verified identifiers + reviewed
  "confidence_level": "inferred",   // Generic/multi-source; bio_score conservative
  "confidence_level": "unresolved"  // Pending clinician/policy decision
}
```

**Where applied so far:**
- `NHA_TRACE_MINERAL_SOLUTION` → `verified` (executive policy decision documented)
- `algae_protein` → `inferred` (generic source, conservative scoring)

**Backfill plan (follow-on PR):**
- All existing entries with full UNII + CUI + clinical evidence → `verified`
- Entries with stub data quality or generic CUIs → `inferred`
- Entries flagged for clinician review → `unresolved`

This enables UI tier display ("Verified" badge), audit gating (release-block on too many unresolved), and avoids silent assumptions.

---

## Strict workflow rules (apply to every item)

These are non-negotiable per `feedback_user_strict_chemistry_verification.md` and `critical_clinical_data_integrity.md`:

1. **API verification before alias-add.** Same name ≠ same compound. Verify chemical identity via PubChem CID + CAS, NCBI Taxonomy taxid, UMLS CUI, or FDA UNII before treating an alias as same-compound.
2. **No bulk alias-adds.** Each entry is a hypothesis needing verification.
3. **Verify parent before creating new entry.** Search existing IQM/botanical_ingredients/standardized_botanicals/other_ingredients for the candidate's CUI/CAS/standard_name/aliases. If a same-compound parent exists, alias to it; do not duplicate.
4. **No bypassing or loosening.** When a coverage gate fails, fix the data correctly — never widen the gate.
5. **Run `scripts/api_audit/audit_species_alignment.py`** after a botanical batch to catch any species-level cross-contamination introduced.
6. **Atomic commits, one batch at a time.** Each commit should be reviewable in isolation. Tests must pass before commit.

**Verification commands:**

```bash
# UMLS CUI verification
python3 scripts/api_audit/verify_cui.py --search "<name or binomial>"
python3 scripts/api_audit/verify_cui.py --cui C0123456

# UNII verification
grep -i "<name>" scripts/data/fda_unii_cache.json

# PubChem CID / CAS — use external API or Anthropic Bash via WebFetch (subagent)

# Coverage check after additions
python3 /tmp/coverage_check.py    # or rebuild from scripts/audits/unmapped_triage/

# Species/chemistry audit
python3 scripts/api_audit/audit_species_alignment.py
python3 scripts/api_audit/audit_species_alignment.py --strict   # release gate
```

---

## CATEGORY 1 — Branded blend headers (~20 items)

**Decision required:** For each branded blend, check the actual product label data in DSLD. Is the blend a header with disclosed children rows, or an opaque proprietary blend?

**Reference:** `scripts/audits/unmapped_triage/BLEND_HANDLING_POLICY.md` — 4-state classifier (DISCLOSED_BLEND / BLEND_HEADER / OPAQUE_BLEND / fake-transparency).

**How to verify per item:**
1. Find a product containing the blend in DSLD raw JSON
2. Check `category`, `quantity.unit`, and `nestedRows` fields
3. If `category: "blend"` + has `nestedRows` → **DISCLOSED_BLEND** (skip in scoring; score children)
4. If `category: "blend"` + `quantity.unit: "NP"` + no nestedRows + valid following ingredient siblings → **BLEND_HEADER** (add to `scripts/constants.py:BLEND_HEADER_EXACT_NAMES`)
5. If `category: "blend"` + has quantity (mg) but no nestedRows → **OPAQUE_BLEND** (B5 transparency penalty fires)
6. If has nestedRows but all children quantity=0 or NP → **OPAQUE_BLEND** (fake transparency)

| Count | Item | Likely class | Action |
|---|---|---|---|
| 8 | Wheybolic Protein Complex | BLEND_HEADER (GNC trade name) | Verify; if header, add to BLEND_HEADER_EXACT_NAMES |
| 3 | Blend (Non-Nutrient/Non-Botanical) | BLEND_HEADER (literal) | Add to BLEND_HEADER_EXACT_NAMES |
| 2 | Advanced Power Maximizer | BLEND_HEADER (likely) | Verify per-product |
| 2 | Elite Pump Factor | BLEND_HEADER (likely) | Verify |
| 2 | Hardcore Test Amplifier: | BLEND_HEADER (trailing colon) | Verify |
| 2 | Hyper-Thermogenic Trigger | BLEND_HEADER (likely) | Verify |
| 2 | Joint & Skin Support: | BLEND_HEADER (trailing colon) | Verify |
| 2 | Lean Muscle Support | BLEND_HEADER (likely) | Verify |
| 2 | N.O. Pump Charger | BLEND_HEADER (likely) | Verify |
| 2 | Sustained Protein Blend | BLEND_HEADER (literal) | Verify |
| 1 | Anabolic Maximizer | BLEND_HEADER | Verify |
| 1 | Anabolic Maximizer with OT2 | BLEND_HEADER (Garden of Life) | Verify |
| 1 | Anabolic Muscle Primer | BLEND_HEADER | Verify |
| 1 | Anabolic Power Charger | BLEND_HEADER | Verify |
| 1 | Brain & Circulatory Support | BLEND_HEADER | Verify |
| 1 | Hardcore Power & Recovery Maximizer | BLEND_HEADER | Verify |
| 1 | PM Metabolic Optimizer | BLEND_HEADER | Verify |
| 1 | Skin Structure & Antioxidant Support | BLEND_HEADER | Verify |
| 1 | Thermo-Metabolic Activator | BLEND_HEADER | Verify |
| 1 | Blend | BLEND_HEADER (literal) | Add to BLEND_HEADER_EXACT_NAMES |

---

## CATEGORY 2 — Trace mineral solution / rare earth elements (~30 items)

**Decision required:** Policy decision on how to handle "Ocean-derived trace minerals" / "Clay-Derived Trace Mineral Solution" products that list every element on the periodic table including rare earths and toxic metals.

**Background:** Brands like Concentrace, Trace Minerals Research, etc. list 70+ elements at trace (ppb-ppm) levels. None of these elements have nutritional bioavailability scoring — they are present in source water/clay rather than added intentionally. Many (Pb, Hg, Cd, Tl, U) are toxic at higher exposure but considered safe at ppb levels.

**Three policy options:**

**Option A (recommended):** Single `trace_mineral_solution` entry in `other_ingredients.json` with:
- `category: "mineral_blend"`
- `is_additive: false`
- Notes documenting that individual elemental listings (rare earths + heavy metals) on these products are at non-bioactive trace levels
- Aliases covering all 30+ elements as variants (Lanthanum, Cerium, etc.)
- This treats them as one entry that doesn't impact scoring

**Option B:** Add each rare earth as a no-score `other_ingredients` entry (lots of work, no scoring value).

**Option C:** Cleaner-side fix — strip these descriptor-only entries from active ingredient parsing in `clean_dsld_data.py`.

**Items affected:**

```
3× Ocean-derived trace minerals in a base of green alfalfa grass
1× Clay-Derived Trace Mineral Solution
1× Minerals    (literal generic)

Lanthanides (15): Lanthanum, Cerium, Praseodymium, Neodymium,
  Samarium, Europium, Gadolinium, Terbium, Dysprosium, Holmium,
  Erbium, Thulium, Ytterbium, Lutetium  (+ Promethium not listed)

Other rare elements (15+): Barium, Beryllium, Cesium, Gallium,
  Hafnium, Indium, Iridium, Niobium, Palladium, Platinum, Gold,
  Rhenium, Rhodium, Ruthenium, Scandium, Tantalum, Tellurium,
  Thallium, Thorium, Titanium, Tungsten, Uranium, Yttrium,
  Zirconium

(Note: Sulphur, Sulfur on this list — these ARE nutritionally relevant
as elemental S or via cysteine/methionine. Should be split off into a
proper sulfur entry separate from rare earths.)
```

---

## CATEGORY 3 — Source-disambiguation needed (~6 items)

**Decision required:** Each entry's exact source / form is unspecified.

| Count | Item | Question | Resolution path |
|---|---|---|---|
| 3 | Algae Protein | Spirulina? Chlorella? Schizochytrium? Generic blend? | If clinician confirms commercial usage = mostly spirulina/chlorella blend → create generic `algae_protein` entry with both as source aliases |
| 2 | whole Algal Protein | Same as above | Same path |
| 1 | Whole Algal protein | Capitalization variant of above | Same |
| 1 | Green Algae Whole Plant Extract | Spirulina (cyanobacteria, technically blue-green algae) or Chlorella | Verify via product context |
| 2 | Glucosamine Salt | HCl? Sulfate? | Strict rule says don't bulk-alias. Either: (a) clinician policy decision to map to glucosamine_hcl as default, or (b) leave unmapped pending product-specific check |
| 1 | Sulphur | Elemental S? Sulfate? Cysteine/methionine source? | Likely `Trace Mineral Solution` element; but if standalone, needs separate sulfur entry |
| 1 | Insulin | Bovine insulin? Plant insulin (= insulin-like polysaccharide)? | Almost certainly OCR error or label typo for "Inulin" — verify on actual product |

---

## CATEGORY 4 — SPMs (Resolvins / Protectins) — clinician decision

**Background:** Resolvins and protectins are endogenous omega-3-derived specialized pro-resolving mediators (SPMs). Most products labeled "Resolvins" or "Protectins" actually contain SPM **precursors** (14-HDHA, 17-HDHA, 18-HEPE — already in IQM under `omega_3` parent), not the resolvins themselves.

**Decision needed:** Is "Resolvins" / "Protectins" on a label a marketing claim (alias to omega_3 SPM precursor section) or a literal compound (need new IQM entry with PubChem-verified identifiers)?

**Items:**
```
1× Resolvins
1× Protectins
1× Resolvin D5    (specific resolvin — has PubChem CID 24932575)
1× Protectin DX   (specific protectin — has PubChem CID 11968800)
```

**Resolution path:** If clinician approves, add as aliases on `omega_3` SPM precursor forms with notes that products labeling "Resolvins" typically contain SPM precursors per Stubbs et al. analysis. For specific compounds (Resolvin D5, Protectin DX), create new IQM forms with PubChem CIDs.

---

## CATEGORY 5 — Probiotic strain safety review (clinician sign-off)

**Background:** These are oral-cavity Streptococcus strains marketed as BLIS-branded probiotics (BLIS Technologies). The genus Streptococcus includes both probiotic and pathogenic species, so strain-level safety assessment is required.

**Items:**
```
2× S. rattus JH145(TM)        # branded BLIS strain
2× S. uberis KJ2(TM)          # branded BLIS strain — historically a bovine mastitis pathogen
1× S. oralis JH145(TM)        # branded BLIS strain
1× S. oralis KJ3(TM)          # branded BLIS strain
```

**Decision:** Clinician must verify strain-level FDA / NIH safety profile and confirm these specific BLIS strains have documented probiotic efficacy in oral health applications.

**Memory reference:** `feedback_user_strict_chemistry_verification.md` flagged Enterococcus faecium and Streptococcus genus risks (VRE, pathogenic strains).

---

## CATEGORY 6 — Pure descriptors / cleaner-side fix (~7 items)

**Decision:** These are not ingredients — they are label artifacts that the cleaner picked up. Fix in `scripts/clean_dsld_data.py` ingredient row parser.

```
2× Cream                                    # serving description
2× Isoflavone Content Per Serving           # label heading
2× other Organic Citrus                     # descriptor leftover
1× Typical Fatty Acid Profile Per Capsule   # label heading
1× Isomer E                                 # specifying ratio context, not ingredient
1× together containing the Isomer E ratio   # label fragment
1× from Green Tea Leaf Extract              # source descriptor (has "from" prefix — already known cleaner bug per memory project_enricher_prefix_from_bug.md)
1× esterified fatty acid carbons of myristate  # description fragment
1× naturally occurring Vitamin C Metabolites   # marketing claim
1× organic Tapioca Syrup solids             # could be aliased to existing tapioca syrup entry
1× organic White Wood                       # ambiguous — Tremella? Or descriptor?
1× {Chondroitin} Sodium                     # OCR/punctuation artifact — likely sodium chondroitin sulfate, alias to chondroitin parent
```

---

## CATEGORY 7 — Same-compound aliases (verifiable, ~15 items)

**These should be straightforward additions** if your team can verify same-compound chemistry:

| Count | Item | Likely parent | Verification |
|---|---|---|---|
| 1 | Lychee Berry Extract | Already exists in IQM (line 52055 area, Litchi chinensis) — confirm | Already covered? |
| 1 | CurQfen | Already aliased on curcumin (line 20862) | Already covered? |
| 1 | Goji Berry Fruit Juice, Powder | goji_berry parent | Add as alias |
| 1 | Matcha Green Tea, Powder | green_tea (matcha already aliased) | Add comma-variant |
| 1 | decaffeinated Black Tea | black_tea parent — verify exists | Add as alias |
| 1 | Cupuacu Fruit Powder | NEW entry (Theobroma grandiflorum) | Verify CUI: search `Theobroma grandiflorum` |
| 1 | Capuacu Fruit Powder | Typo of Cupuacu | Add as typo alias to Cupuacu entry |
| 1 | Cubeb fruit powder | NEW entry (Piper cubeba) | Verify CUI; UNII probably exists |
| 1 | Fermented Soy Bean Powder | soy/soybean parent | Add as alias |
| 1 | Bruteridine | citrus_bergamot constituent (related to brutieridine) | Verify — likely typo |
| 1 | Campestrol | likely typo of campesterol (phytosterol) | Verify; alias to phytosterols |
| 1 | Isoflavone Glycoside | soy_isoflavones parent | Verify |
| 1 | Zingibain | ginger protease enzyme — alias to digestive_enzymes or ginger | Verify |
| 1 | Amniogen(R) | branded — verify what it actually is | Research brand |
| 1 | ISS BIF | unknown abbreviation — research before action | Surface |

**Workflow per item:**
1. Run `python3 scripts/api_audit/verify_cui.py --search "<name>"` — get CUI
2. Check `scripts/data/fda_unii_cache.json` for UNII
3. Search existing data files for parent (`grep "<latin name or CUI>" scripts/data/*.json`)
4. If parent exists with same CUI/UNII → alias to parent's appropriate form
5. If no parent → create new entry with verified identifiers, follow the pattern of recently-added entries (yangmei, butternut_squash, horse_gram, etc.)
6. Update `_metadata.total_entries` count
7. Update relevant test count assertion (e.g., `scripts/tests/test_b05_functional_roles_integrity.py`)
8. Run `python3 -m pytest scripts/tests/test_clean_unmapped_alias_regressions.py scripts/tests/test_b05_functional_roles_integrity.py scripts/tests/test_phase_6_attributes.py` — all must pass
9. Run `python3 scripts/db_integrity_sanity_check.py` — must report 0 errors
10. Run `python3 scripts/api_audit/audit_species_alignment.py` — review SAME_GENUS findings against documented allowlist
11. Atomic commit per batch with detailed message

---

## CATEGORY 8 — Special cases / single-occurrence niche

```
1× CurQfen                                 # branded curcumin-fenugreek complex (already aliased)
```

(Most niche items resolved into Categories 6 or 7 above.)

---

## How to extend this guide

When a team member resolves a category, update this file:
- Move resolved items from their category to a "RESOLVED" log at the bottom
- Note the commit hash that addressed them
- Update remaining count

---

## Reference: recent commits this session (workflow examples to mirror)

| Commit | What it shows |
|---|---|
| `4efa6be` | Splitting wrong-genus CUI + creating new species entry (Myrica) |
| `ba8fbe3` | Multi-entry batch fix with separate species (chopchini/sarsaparilla/catjang/horse_gram) |
| `295520a` | Family-level conflation fix (butternut tree vs squash) — both new entry + alias strip |
| `e4eb91e` | New EO entries with full UNII + CUI verification (4 essential oils) |
| `0c9460f`, `f2e7af3`, `9c8409d` | Pure alias-batch commits with no new entries |

Each commit has a detailed message documenting WHY the change was made and which API verifications were performed. Mirror this format.

---

## Reference: documents to read first

- `CLAUDE.md` — engineering principles (no hallucinated identifiers, accuracy over speed, atomic commits)
- `scripts/api_audit/README.md` — API audit tooling reference
- `scripts/audits/unmapped_triage/BLEND_HANDLING_POLICY.md` — 4-state blend classifier
- `scripts/GLOSSARY.md` — IQM/scoring terminology

Memory references (in `~/.claude/projects/-Users-seancheick-Downloads-dsld-clean/memory/`):
- `feedback_user_strict_chemistry_verification.md`
- `feedback_verify_parent_before_new_entry.md`
- `feedback_no_bulk_api_enrichment.md`
- `critical_no_hallucinated_citations.md`
- `critical_clinical_data_integrity.md`
- `project_blend_classifier_4state.md`
