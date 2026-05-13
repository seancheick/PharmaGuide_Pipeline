# Proposal — manufacture_deduction_expl.json refresh (2026-05-13)

> **Author:** fda_weekly_sync_agent + Claude
> **Status:** PROPOSAL only. This document does NOT modify [scripts/data/manufacture_deduction_expl.json](../../scripts/data/manufacture_deduction_expl.json) — it surfaces gaps + suggestions for review. The framework is your scoring design; nothing changes until you sign off.

---

## TL;DR

The 16-code violation framework is healthy at the top (`CRI_UNDRUG`, `HIGH_CII`, `CRI_TOXIC`, `HIGH_CGMP_CRIT`, `CRI_CONTA` cover 84/89 entries today) but has gaps for **emerging 2025-26 enforcement patterns**:

- **GLP-1 receptor agonists** (semaglutide/tirzepatide/liraglutide) compounded as weight-loss "supplements" — no specific code
- **Anabolic-steroid spike** (testosterone, oxandrolone, stanozolol, methandrostenolone) — folded into the generic `CRI_UNDRUG` (which loses signal)
- **Pediatric-supplement modifier** — Agebox iKids-Growth case scored the same as adult product; kids' supplements arguably warrant +modifier
- **Botanical-substitution recalls** (yellow oleander → tejocote) — folded into `CRI_TOXIC` which loses provenance

Additionally, **8 of the 16 defined codes have 0 entries** (`CRI_ADVERS`, `CRI_INSP`, `HIGH_ADVERS`, `HIGH_MULT_CII`, `LOW_WARN`, `MOD_BRAND`, `MOD_CIII_MULT`, `MOD_DOC`). Some are dormant-but-reserved (legitimate); others may be redundant.

The `-25` total_deduction_cap may be **too lenient** for repeat drug-spikers — Pure Vitamins LLC just had 3 concurrent Class I sildenafil/tadalafil recalls (-69 total uncapped) and the cap pulls them back to -25 (= score 75, "Acceptable" band). That feels off.

---

## 1. Current state (as-of 2026-05-13)

### Codes in use vs. defined

| Code | Defined | In use | Coverage |
|---|---|---:|---|
| `CRI_UNDRUG` | ✓ | **37** | undeclared Rx drug spike (sildenafil, tadalafil, sibutramine, ...) |
| `HIGH_CII` | ✓ | 19 | generic Class II recall |
| `CRI_TOXIC` | ✓ | 11 | toxic substance recall (muscimol, oleander, lead) |
| `HIGH_CGMP_CRIT` | ✓ | 9 | critical CGMP violations |
| `CRI_CONTA` | ✓ | 8 | microbial / heavy-metal contamination |
| `CRI_ALLER` | ✓ | 3 | undeclared allergen (egg, peanut, tree nut, ...) |
| `MOD_CGMP` | ✓ | 1 | CGMP warning letter (non-critical) |
| `MOD_CIII_SING` | ✓ | 1 | single Class III recall |
| `CRI_ADVERS` | ✓ | 0 | serious adverse events (hospitalization, death) |
| `CRI_INSP` | ✓ | 0 | FDA inspection refusal |
| `HIGH_ADVERS` | ✓ | 0 | moderate adverse events |
| `HIGH_MULT_CII` | ✓ | 0 | multiple Class II recalls (count_threshold: 2) |
| `MOD_CIII_MULT` | ✓ | 0 | multiple Class III recalls |
| `MOD_BRAND` | ✓ | 0 | misbranding / labeling violation |
| `MOD_DOC` | ✓ | 0 | minor documentation violations |
| `LOW_WARN` | ✓ | 0 | minor administrative warning |

### Substance-overlap audit (banned_recalled vs deduction codes)

| Adulterant pattern (2025-26 FDA enforcement) | banned_recalled entries | Has dedicated code? |
|---|---:|---|
| sildenafil / tadalafil / vardenafil (ED drugs) | several | yes — `CRI_UNDRUG` |
| semaglutide (Ozempic) | 1 (BANNED_CONTAMINATED_GLP1) | **no** — folded into `CRI_UNDRUG` |
| tirzepatide (Mounjaro) | 1 | **no** — folded into `CRI_UNDRUG` |
| liraglutide (Saxenda) | **0** | **no** — completely uncatalogued |
| phentermine (weight loss) | **0** | **no** — completely uncatalogued |
| tianeptine ("gas station heroin") | 2 | yes — `CRI_TOXIC` |
| oxandrolone / stanozolol / methandrostenolone | 0 | **no** — folded into `CRI_UNDRUG` |
| kratom 7-OH concentrates | 2 | yes — `CRI_TOXIC` |
| delta-8 / HHC synthetic cannabinoids | 1 | partial — `CRI_TOXIC` for some |

---

## 2. Proposed changes

### 2A. Add 3 new CRITICAL subcategories (no rebalance of existing codes needed)

```json
"CLASS_I_GLP1_COMPOUNDED": {
  "base_deduction": -18,
  "description": "Class I recall — undeclared GLP-1 receptor agonist in supplement (semaglutide/Ozempic, tirzepatide/Mounjaro, liraglutide/Saxenda)",
  "examples": [
    "semaglutide compounded for Rx use only",
    "undeclared tirzepatide in weight-loss supplement",
    "underground 'GLP-1 peptide' supplement"
  ],
  "code": "CRI_GLP1"
},
"CLASS_I_ANABOLIC_SPIKE": {
  "base_deduction": -18,
  "description": "Class I recall — undeclared anabolic steroid or steroid-precursor in supplement (testosterone, oxandrolone, methandrostenolone, stanozolol, nandrolone)",
  "examples": [
    "undeclared testosterone in 'natural muscle builder'",
    "stanozolol spike in 'pre-workout'",
    "designer prohormone in 'testosterone booster'"
  ],
  "code": "CRI_ANABOLIC"
},
"CLASS_I_BOTANICAL_SUBSTITUTION": {
  "base_deduction": -20,
  "description": "Class I recall — toxic botanical substitution (yellow oleander as tejocote, ephedra as ma huang, comfrey as other herb)",
  "examples": [
    "yellow oleander substituted for tejocote",
    "ephedra-containing botanical mislabeled",
    "aristolochia in herbal preparation"
  ],
  "code": "CRI_BOT_SUB"
}
```

**Why these and not others:**
- GLP-1 compounding is the **fastest-growing** illegal supplement adulteration pattern in 2025-26. FDA classified it Class I in late 2024 (BANNED_CONTAMINATED_GLP1 in our DB). Today every GLP-1 spike collapses into `CRI_UNDRUG` (which also catches sildenafil) — separating it makes the brand-trust scoring honest about modality.
- Anabolic spike is mechanistically different from PDE5 inhibitor spike. A manufacturer caught with stanozolol is a different risk profile than one caught with sildenafil — both are -15 today, but a stanozolol manufacturer is more likely to be in the SARMs/peptide gray market, warranting -18.
- Botanical substitution (yellow oleander → tejocote) is recurring across brands (FDA 2024 advisory cited 5+ brands). It deserves its own code so we can audit the substitution pattern industry-wide.

### 2B. Add 1 new MODIFIER for pediatric supplements

```json
"PEDIATRIC_SUPPLEMENT": {
  "description": "Penalty modifier when the recalled product is a pediatric supplement (kids, infants, prenatal)",
  "additional_deduction": -3,
  "trigger": "product description contains 'kids' / 'children' / 'infant' / 'pediatric' / 'prenatal'",
  "label": "Pediatric supplement — children at elevated risk"
}
```

**Why:** Agebox iKids-Growth case (V087/V088 this session) — same severity-level deduction as an adult drink shot. Children have lower body mass, more sensitivity to dose-dependent risks, and the trust violation is qualitatively different. A -3 nudge is small but meaningful.

### 2C. Raise the `total_deduction_cap` floor for repeat Class-I drug-spike actors

**Current:** `total_deduction_cap: -25` (uniform).

**Proposed:** Add a graduated cap based on Class-I frequency:

```json
"total_deduction_cap": -25,
"total_deduction_cap_graduated": {
  "default": -25,
  "two_class_i_in_3_years": -35,
  "three_or_more_class_i_in_3_years": -50,
  "rationale": "Pure Vitamins LLC just had 3 concurrent Class I drug-spike recalls (V082-V084). Under the -25 cap, they retain a 'trusted' score floor of 75. A repeat-Class-I-drug-spike manufacturer should be capable of dropping into 'concerning' (50-69) or 'high_risk' (<49) territory."
}
```

**Why:** The user (Sean) explicitly mentioned the cap during framework design. Looking at the actual data — Pure Vitamins LLC, Mohamed Hagar, StuffbyNainax, 123Herbals all run the drug-spike pattern repeatedly. A static -25 floor lets them retain "Acceptable" status. The graduated cap is more honest.

### 2D. Retire or merge 8 unused codes (optional cleanup)

Decision needed on each:

| Code | Action |
|---|---|
| `CRI_ADVERS` (serious adverse events) | **Keep** — reserved for death/hospitalization recalls, those happen |
| `CRI_INSP` (inspection refusal) | **Keep** — rare but legitimate |
| `HIGH_ADVERS` (moderate AEs) | **Keep** — reserved |
| `HIGH_MULT_CII` (multiple Class II) | Auto-detected by repeat_violation modifier; consider **merging** |
| `MOD_CIII_MULT` | Auto-detected; consider **merging** |
| `MOD_BRAND` (misbranding) | **Keep** — generic catch for label violations |
| `MOD_DOC` (documentation) | **Keep** — rare but legitimate |
| `LOW_WARN` | **Keep** — minor admin warning |

Recommendation: keep all 16 for forward compatibility. The unused ones don't cost anything and remove the framework guesswork next time a novel violation type appears.

### 2E. Update `_metadata.version` and `_metadata.last_updated`

```json
"_metadata": {
  ...
  "schema_version": "5.0.0",
  "version": "2.1",       ← bump from "2.0"
  "last_updated": "2026-05-13"
}
```

The framework spec itself moved (added 3 codes + 1 modifier + graduated cap). The pre-existing test_manufacture_deduction_expl_contract.py would catch the section-count bump automatically (5 → 5, no change), and the existing `db_integrity_sanity_check.check_manufacture_deduction_expl` would catch any structural drift.

---

## 3. Out-of-scope but related

These came up during the session and might warrant separate proposals later, NOT in this commit:

1. **Severity for `inactive_policy: ignore_if_inactive` substances** — currently no entries use this; if/when one is added, scoring needs clear rules.
2. **`legal_status_enum` vs `clinical_risk_enum` overlap** — both fields exist; some entries have inconsistent pairings (e.g., legal_status=adulterant + clinical_risk=moderate). Worth a clinical-review pass.
3. **`export_restricted` ban_context** — only 2 entries use it (DHEA, 7-keto-DHEA). The skill skips it as B0 penalty path; if more substances get this context (e.g., melatonin in some jurisdictions), scoring needs to be clarified.

---

## 4. If you approve the proposal

The implementation is straightforward — 1 commit, ~80 lines:

1. Patch [scripts/data/manufacture_deduction_expl.json](../../scripts/data/manufacture_deduction_expl.json) with the 3 new subcategories + 1 new modifier + graduated cap + version bump
2. Extend [scripts/tests/test_manufacture_deduction_expl_contract.py](../../scripts/tests/test_manufacture_deduction_expl_contract.py) to pin the 3 new codes + 1 new modifier
3. Optionally re-run [scripts/api_audit/fda_manufacturer_violations_sync.py](../../scripts/api_audit/fda_manufacturer_violations_sync.py) so any GLP-1 / anabolic / pediatric / botanical-substitution recalls in the existing data get re-classified to the new codes (existing entries default to whatever code the classifier inferred at sync time; manual re-classification is also fine)
4. Update [.claude/skills/fda-weekly-sync/SKILL.md](../../.claude/skills/fda-weekly-sync/SKILL.md) to document the new codes so future syncs use them

**Estimated impact:**
- 0 schema breakage (additive change, no field renames)
- All current `manufacturer_violations` entries keep their existing codes (backwards-compat)
- Future syncs can classify into the more-specific new codes — increases scoring fidelity

---

## 5. What I will NOT do without your explicit approval

- Modify `total_deduction_cap` — your -25 floor was a deliberate scoring choice. The graduated cap is suggested, not imposed.
- Re-classify the 37 `CRI_UNDRUG` entries currently in `manufacturer_violations.json` — that re-classification touches real production data and should be a separate decision after you approve the codes.
- Touch the `score_thresholds` (trusted/acceptable/concerning/high_risk bands) — those are downstream of the deduction math and would need to be re-validated against the new cap math.

Awaiting sign-off.
