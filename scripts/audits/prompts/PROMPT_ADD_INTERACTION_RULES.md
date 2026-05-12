# Prompt: Add Interaction Rules to PharmaGuide

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

### Conditions (condition_id)
`pregnancy`, `lactation`, `ttc`, `surgery_scheduled`, `hypertension`, `heart_disease`, `diabetes`, `bleeding_disorders`, `kidney_disease`, `liver_disease`, `thyroid_disorder`, `autoimmune`, `seizure_disorder`, `high_cholesterol`

### Drug Classes (drug_class_id)
`anticoagulants`, `antiplatelets`, `nsaids`, `antihypertensives`, `hypoglycemics`, `thyroid_medications`, `sedatives`, `immunosuppressants`, `statins`

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

## Current Coverage Gaps

Conditions with NO interaction rules yet:
- `lactation` — 0 rules (partially covered via pregnancy_lactation blocks)
- `ttc` — 0 rules
- `heart_disease` — 0 rules
- `bleeding_disorders` — 0 rules
- `liver_disease` — 0 rules
- `thyroid_disorder` — 0 rules
- `autoimmune` — 0 rules
- `seizure_disorder` — 0 rules
- `high_cholesterol` — 0 rules

Drug classes with thin coverage:
- `nsaids` — 0 rules
- `antiplatelets` — 1 rule
- `thyroid_medications` — 1 rule
- `sedatives` — 1 rule
- `immunosuppressants` — 1 rule
- `statins` — 1 rule

## After Writing Rules

1. Run tests: `cd scripts && python3 -m pytest tests/ -q`
2. All 2672+ tests must pass
3. Verify the JSON is valid: `python3 -c "import json; json.load(open('data/ingredient_interaction_rules.json'))"`

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
