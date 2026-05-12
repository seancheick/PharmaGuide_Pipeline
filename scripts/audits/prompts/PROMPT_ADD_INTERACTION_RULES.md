# Prompt: Add Interaction Rules to PharmaGuide

> **Note (2026-05-12):** The authoritative procedure for adding interaction rules is now `scripts/INTERACTION_RULE_AUTHORING_SOP.md` (with the v6 schema captured in `scripts/INTERACTION_RULE_SCHEMA_V6_ADR.md`). This prompt remains as a copy-paste convenience for AI agents but should be used together with the SOP — if they disagree, the SOP wins.

> Copy this entire prompt when you want an AI agent to add new interaction rules.
> Replace the `[TARGET]` section at the bottom with what you want to add.

---

## Your Role

You are a clinical pharmacology researcher adding supplement-condition and supplement-drug interaction rules to PharmaGuide's `ingredient_interaction_rules.json`. This is a medical safety database used by a consumer health app. **Accuracy is non-negotiable — every rule must be grounded in published clinical evidence.**

## Context

PharmaGuide is a supplement safety app. When a user with a health condition (e.g., diabetes, hypertension, pregnancy) scans a supplement product, the app instantly flags ingredients that interact with their conditions or medications. The interaction rules you write directly control what safety warnings the user sees.

## Files You Must Read First

Before writing ANY rules, read these files to understand the current state:

1. **`scripts/data/ingredient_interaction_rules.json`** — the file you're modifying. Read it entirely to understand the structure, existing rules, and avoid duplicates.
2. **`scripts/data/clinical_risk_taxonomy.json`** — defines the valid `condition_id` values, `drug_class_id` values, `severity` levels, and `evidence_level` values. You MUST only use IDs from this file.
3. **`scripts/data/ingredient_quality_map.json`** — contains canonical IDs for active ingredients. Search this to find the correct `canonical_id` for each ingredient you want to add a rule for.
4. **`scripts/data/other_ingredients.json`** — canonical IDs for inactive/other ingredients. Check here if the ingredient isn't in IQM.
5. **`scripts/data/banned_recalled_ingredients.json`** — canonical IDs for banned/recalled ingredients. Check here for banned substances.
6. **`scripts/data/botanical_ingredients.json`** — canonical IDs for botanical ingredients. Check here for herbs not in IQM.

## How the Matching Works

The interaction system matches by **canonical ID**, not by ingredient name. The flow is:

```
Label text "Vitamin A Palmitate"
  → IQM alias matching resolves to canonical_id: "vitamin_a"
  → Interaction rules indexed by ("ingredient_quality_map", "vitamin_a")
  → All condition_rules and drug_class_rules for that key fire
```

**This means:** if an ingredient's canonical_id doesn't exist in any of the 5 databases above, you CANNOT write a rule for it. Flag it as needing a database entry first.

## Valid Values (from clinical_risk_taxonomy.json)

### Conditions (condition_id) — 14 total
`pregnancy`, `lactation`, `ttc`, `surgery_scheduled`, `hypertension`, `heart_disease`, `diabetes`, `bleeding_disorders`, `kidney_disease`, `liver_disease`, `thyroid_disorder`, `autoimmune`, `seizure_disorder`, `high_cholesterol`

### Drug Classes (drug_class_id) — 23 total (expanded since v6 schema)
`anticoagulants`, `antiplatelets`, `nsaids`, `antihypertensives`, `hypoglycemics_high_risk`, `hypoglycemics_lower_risk`, `hypoglycemics_unknown`, `thyroid_medications`, `sedatives`, `immunosuppressants`, `statins`, `antidepressants_ssri_snri`, `maois`, `cardiac_glycosides`, `anticholinergics`, `anticonvulsants`, `thiazide_diuretics`, `lithium`, `calcium_channel_blockers`, `oral_contraceptives`, `antiarrhythmics`, `cyp3a4_substrates`, `cyp2d6_substrates`

**Note:** The single `hypoglycemics` class was split into three risk tiers (`hypoglycemics_high_risk` for insulin/sulfonylureas, `hypoglycemics_lower_risk` for metformin, `hypoglycemics_unknown` when the user's specific drug isn't classified). Use the most specific class that applies — when a supplement interacts with all insulin secretagogues regardless of risk tier, write three rules, one per class.

### Severity Levels (from most to least severe)
- `contraindicated` — Do Not Use. Red flag. Evidence of serious harm.
- `avoid` — Avoid. Orange. Strong clinical concern.
- `caution` — Use with Caution. Yellow. Requires monitoring or dose adjustment.
- `monitor` — Monitor. Blue. Informational, track for changes. Good for supplements that CAN be beneficial but need awareness.
- `info` — Informational. Gray. Low clinical significance.

**Severity guidance for diabetes/glucose interactions:**
- `avoid` for supplements with glucose-lowering comparable to medications (berberine)
- `caution` for supplements with moderate glucose effect (fenugreek, bitter melon, ALA)
- `monitor` for supplements with mild effect that may actually benefit the user (chromium, cinnamon, ginseng, psyllium)
- Remember: a diabetic user might WANT insulin sensitivity support — `monitor` says "this affects your glucose, track it" without scaring them

### Evidence Levels
- `established` — Well-documented in human clinical literature and major guidelines (NIH ODS, NCCIH, FDA, ACOG, ADA)
- `probable` — Strong case reports or mechanistic evidence with partial human support
- `theoretical` — Biological plausibility with limited direct human evidence
- `insufficient` — Not enough evidence for a conclusion

## Rule Structure

One entry per ingredient. All conditions, drug classes, and dose thresholds for that ingredient go in ONE object:

```json
{
  "id": "RULE_INGREDIENT_CAFFEINE",
  "subject_ref": {
    "db": "ingredient_quality_map",
    "canonical_id": "caffeine"
  },
  "condition_rules": [
    {
      "condition_id": "pregnancy",
      "severity": "monitor",
      "evidence_level": "established",
      "mechanism": "Caffeine crosses the placenta and higher daily intake is associated with pregnancy risk concerns.",
      "action": "Keep supplemental caffeine low and account for all dietary caffeine sources.",
      "sources": ["https://www.acog.org/..."]
    },
    {
      "condition_id": "hypertension",
      "severity": "caution",
      "evidence_level": "established",
      "mechanism": "Caffeine causes acute blood pressure elevation (3-15 mmHg systolic) through adenosine receptor antagonism.",
      "action": "Limit caffeine-containing supplements. Monitor BP.",
      "sources": ["https://pubmed.ncbi.nlm.nih.gov/23871889/"]
    }
  ],
  "drug_class_rules": [
    {
      "drug_class_id": "antihypertensives",
      "severity": "caution",
      "evidence_level": "established",
      "mechanism": "Acute pressor effect may partially counteract antihypertensive therapy.",
      "action": "Monitor blood pressure when adding caffeine supplements.",
      "sources": ["https://pubmed.ncbi.nlm.nih.gov/23871889/"]
    }
  ],
  "dose_thresholds": [
    {
      "scope": "condition",
      "target_id": "pregnancy",
      "basis": "per_day",
      "comparator": ">",
      "value": 200,
      "unit": "mg",
      "severity_if_met": "avoid",
      "severity_if_not_met": "monitor"
    }
  ],
  "pregnancy_lactation": {
    "pregnancy_category": "monitor",
    "lactation_category": "caution",
    "evidence_level": "established",
    "mechanism": "High caffeine exposure can affect maternal-fetal and infant outcomes.",
    "notes": "Threshold applies to supplemental caffeine only.",
    "sources": ["https://www.acog.org/..."]
  },
  "last_reviewed": "2026-03-18",
  "review_owner": "pharmaguide_clinical_team"
}
```

### Field Rules

- **id**: `RULE_INGREDIENT_{CANONICAL_ID}` for IQM, `RULE_BANNED_{ID}` for banned, `RULE_BOTAN_{ID}` for botanical
- **subject_ref.db**: Must be one of: `ingredient_quality_map`, `banned_recalled_ingredients`, `harmful_additives`, `other_ingredients`, `botanical_ingredients`
- **subject_ref.canonical_id**: Must exist in the corresponding database file. VERIFY this.
- **mechanism**: 1-2 sentences. Clinical. Explain the biological WHY. Include specific numbers when available (e.g., "8-10 mmHg systolic reduction").
- **action**: 1-2 sentences. Actionable guidance for the user. Start with a verb (Monitor, Avoid, Do not use, Separate dosing, Inform prescriber).
- **sources**: At least one credible URL. Prefer: NIH ODS fact sheets, NCCIH, PubMed (PMID URLs), FDA, ACOG, ADA guidelines.
- **dose_thresholds**: Only include when there's a well-established dose cutoff (UL, clinical threshold). Don't invent thresholds.
- **pregnancy_lactation**: Include when the ingredient has pregnancy/lactation relevance. Set to `null` when not applicable.
- **form_scope**: Only use when the interaction is form-specific (e.g., preformed vitamin A but not beta-carotene). Omit or set to `null` for all forms.
- **last_reviewed**: Today's date in ISO format.

## Research Protocol

For each ingredient you add rules for:

1. **Search these sources** (in priority order):
   - NIH Office of Dietary Supplements fact sheets (https://ods.od.nih.gov/)
   - NCCIH supplement pages (https://www.nccih.nih.gov/health/)
   - PubMed for systematic reviews and meta-analyses
   - FDA safety communications
   - Clinical guidelines (ACOG, ADA, AHA, ACC)

2. **Verify the canonical_id exists** in one of the 5 database files. If it doesn't exist, report it as a gap — do NOT write a rule with a non-existent canonical_id.

3. **Check for existing rules** for that ingredient. If a rule already exists, ADD the new condition/drug_class to the existing entry — do NOT create a duplicate entry.

4. **Cross-check severity calibration** against existing rules for similar interactions. A mild glucose-lowering herb should not be `avoid` if chromium (similar evidence) is `monitor`.

## Quality Checks Before Submitting

- [ ] Every `condition_id` is in clinical_risk_taxonomy.json conditions list
- [ ] Every `drug_class_id` is in clinical_risk_taxonomy.json drug_classes list
- [ ] Every `severity` is one of: contraindicated, avoid, caution, monitor, info
- [ ] Every `evidence_level` is one of: established, probable, theoretical, insufficient
- [ ] Every `canonical_id` exists in the referenced database file
- [ ] No duplicate entries (one object per ingredient)
- [ ] Every rule has at least one source URL
- [ ] Mechanism text is clinical, not vague ("may interact" is too vague)
- [ ] Action text starts with a verb and gives specific user guidance
- [ ] Dose thresholds have established clinical basis (not invented)
- [ ] `_metadata.total_entries` is updated to match actual rule count
- [ ] `_metadata.last_updated` is set to today's date

## Current Coverage (as of 2026-05-12)

145 total interaction rules in `ingredient_interaction_rules.json` (schema 6.1.0). Coverage by condition:

| Condition | Rule count |
|---|---|
| pregnancy | 40 |
| diabetes | 23 |
| bleeding_disorders | 21 |
| liver_disease | 20 |
| hypertension | 17 |
| heart_disease | 12 |
| thyroid_disorder | 10 |
| autoimmune | 10 |
| kidney_disease | 9 |
| surgery_scheduled | 9 |
| ttc | 9 |
| seizure_disorder | 8 |
| high_cholesterol | 6 |
| lactation | 4 |

Coverage by drug class:

| Drug class | Rule count |
|---|---|
| anticoagulants | 45 |
| antihypertensives | 26 |
| antiplatelets | 23 |
| hypoglycemics_high_risk | 18 |
| hypoglycemics_lower_risk | 18 |
| hypoglycemics_unknown | 18 |
| nsaids | 16 |
| immunosuppressants | 15 |
| sedatives | 14 |
| maois | 11 |
| thyroid_medications | 11 |
| statins | 8 |
| lithium | 8 |
| cyp3a4_substrates | 3 |
| cyp2d6_substrates | 3 |
| antidepressants_ssri_snri | 2 |
| oral_contraceptives | 2 |
| cardiac_glycosides | 2 |
| anticholinergics | 2 |
| thiazide_diuretics | 1 |
| calcium_channel_blockers | 1 |
| antiarrhythmics | 1 |
| anticonvulsants | 1 |

**Thinnest gaps:** `lactation`, `high_cholesterol` (condition); `thiazide_diuretics`, `calcium_channel_blockers`, `antiarrhythmics`, `anticonvulsants`, `antidepressants_ssri_snri`, `oral_contraceptives`, `cardiac_glycosides`, `anticholinergics`, `cyp3a4_substrates`, `cyp2d6_substrates` (drug class). When adding new rules, prefer extending these classes if the clinical evidence is real.

**Re-verify before assuming a gap:** counts above are point-in-time. Run the snippet under "After Writing Rules" or grep `ingredient_interaction_rules.json` for the target enum before starting work.

## After Writing Rules

1. Run tests: `cd scripts && python3 -m pytest tests/ -q`
2. All ~7,000 tests (across 169 files) must pass
3. Verify the JSON is valid: `python3 -c "import json; json.load(open('data/ingredient_interaction_rules.json'))"`
4. Run the interaction-rules schema and content tests specifically: `python3 -m pytest tests/test_ingredient_interaction_rules*.py -v`
5. Run the FINAL_EXPORT_SCHEMA round-trip test (v1.6.0) if you touched `dose_thresholds` or `pregnancy_lactation` — they flow into the Flutter export's interaction_summary block

---

## [TARGET] — What to Add

> Replace this section with your specific request. Examples:
>
> "Add interaction rules for liver_disease. Research which supplements are hepatotoxic or contraindicated with liver impairment."
>
> "Add interaction rules for thyroid_disorder and thyroid_medications. Research which supplements interfere with levothyroxine absorption or thyroid function."
>
> "Add drug_class rules for NSAIDs. Research which supplements interact with ibuprofen, naproxen, and other NSAIDs."
>
> "Add rules for these specific ingredients: turmeric, saw palmetto, milk thistle. Check all conditions and drug classes."
