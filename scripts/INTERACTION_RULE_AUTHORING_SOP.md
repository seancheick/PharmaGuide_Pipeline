# PharmaGuide Interaction Rule Authoring SOP

> Last updated: 2026-03-18 | Schema 5.1.0 | 45 rules, 14 conditions, 9 drug classes

## Scope
This SOP governs how to add or update contraindication/interaction alerts in:
- `scripts/data/clinical_risk_taxonomy.json` — controlled enums
- `scripts/data/ingredient_interaction_rules.json` — rule store

The interaction layer produces **warnings in the final DB detail blob** and powers the app's condition-based flagging. It does **not** change A/B/C/D scoring.

---

## Why These Files Exist

### `clinical_risk_taxonomy.json`
Controlled enums for:
- `conditions` (14): pregnancy, lactation, ttc, surgery_scheduled, hypertension, heart_disease, diabetes, bleeding_disorders, kidney_disease, liver_disease, thyroid_disorder, autoimmune, seizure_disorder, high_cholesterol
- `drug_classes` (9): anticoagulants, antiplatelets, nsaids, antihypertensives, hypoglycemics, thyroid_medications, sedatives, immunosuppressants, statins
- `severity_levels` (5): contraindicated, avoid, caution, monitor, info
- `evidence_levels` (4): established, probable, theoretical, insufficient

Each condition/drug class has: `id`, `label`, `description`, `app_category`, `sort_order`.

Purpose:
- deterministic behavior
- no free-text drift
- consistent UI/API labels
- app profile matching (user selects conditions → app matches against condition_id)

### `ingredient_interaction_rules.json`
Rule store keyed by canonical identity:
- `subject_ref: {db, canonical_id}`
- `condition_rules[]`
- `drug_class_rules[]`
- `dose_thresholds[]` (optional)
- `pregnancy_lactation` (optional)
- provenance (`sources`, `last_reviewed`, `review_owner`)

Purpose:
- exact, reproducible safety lookups from enrichment output
- condition_summary and drug_class_summary in export detail blob
- dose-dependent severity escalation

### Supported `subject_ref.db` values:
- `ingredient_quality_map`
- `other_ingredients`
- `harmful_additives`
- `banned_recalled_ingredients`
- `botanical_ingredients`

---

## How Rules Flow Through the Pipeline

```
1. Enrichment (enrich_supplements_v3.py)
   └── For each ingredient, looks up interaction_rules by (db, canonical_id)
   └── Emits interaction_profile: {ingredient_alerts[], condition_summary{}, drug_class_summary{}}
   └── Evaluates dose_thresholds against product serving amounts

2. Export (build_final_db.py)
   └── Reads interaction_profile from enriched data
   └── Emits condition_summary and drug_class_summary in detail blob
   └── Individual interaction warnings with dose_threshold_evaluation
   └── Per-condition aggregation: count, highest_severity, ingredients involved

3. Flutter App
   └── User sets health conditions in profile (e.g., diabetes, pregnancy)
   └── On product scan, app checks detail.condition_summary[user_condition]
   └── Instant flag if any ingredients have warnings for that condition
   └── Section F fit score computed on-device from reference_data + user profile
```

---

## Non-Negotiable Guardrails

1. No free-text matching in runtime safety logic.
   - Rules must resolve by exact canonical identity.

2. Do not add rule subjects that do not exist in source DBs.
   - Add/map canonical ID first, then add rule.

3. Do not invent enum values.
   - Use only taxonomy-defined condition/drug class/severity/evidence IDs.

4. Do not use marketing/blog sources as primary evidence.
   - Prefer NCCIH, NIH ODS, ACOG, LactMed, FDA, ADA, AHA.

5. Do not overstate severity.
   - `contraindicated/avoid` requires strong support.
   - Use `caution/monitor` when evidence is uncertain.
   - For diabetes: `monitor` is appropriate for supplements that mildly affect glucose (chromium, cinnamon) — the user may actually want insulin sensitivity support.

6. One rule per ingredient.
   - All conditions, drug classes, and dose thresholds go in ONE object per canonical_id.

---

## Authoritative Source Priority

1. NCCIH (https://www.nccih.nih.gov/health/)
2. NIH ODS Health Professional Fact Sheets (https://ods.od.nih.gov/)
3. ACOG
4. LactMed
5. FDA
6. ADA, AHA, ACC clinical guidelines
7. PubMed systematic reviews / meta-analyses

Rules without solid sources should be deferred.

---

## Rule Writing Standards

Each rule must include:
- `id` — stable, unique (e.g., `RULE_INGREDIENT_CAFFEINE`, `RULE_BANNED_YOHIMBE_CONTRA`)
- `subject_ref` — exact canonical target `{db, canonical_id}`
- at least one of: `condition_rules[]`, `drug_class_rules[]`, `pregnancy_lactation`
- `last_reviewed` — ISO date
- `review_owner` — always `"pharmaguide_clinical_team"`

Each condition/drug rule must include:
- target id (`condition_id` or `drug_class_id`) — from taxonomy
- `severity` — from taxonomy severity_levels
- `evidence_level` — from taxonomy evidence_levels
- `mechanism` — 1-2 sentences, clinical, explain the biological WHY
- `action` — 1-2 sentences, starts with a verb (Monitor, Avoid, Do not use, Separate dosing)
- `sources[]` — at least one credible URL (NCCIH, NIH ODS, PubMed, FDA)

---

## Dose Threshold Policy

Use `dose_thresholds[]` only when you have a defensible numeric cutoff from authoritative guidance (e.g., ACOG 200mg caffeine/day pregnancy limit).

Required fields:
- `scope`: `condition` or `drug_class`
- `target_id`
- `basis`: `per_day` or `per_serving`
- `comparator`: one of `>`, `>=`, `<`, `<=`, `==`
- `value` (number)
- `unit`
- `severity_if_met` — severity when threshold is exceeded
- `severity_if_not_met` — severity when threshold is NOT exceeded (optional)

If dose conversion is not possible at runtime, the base severity is retained.

---

## Current Coverage Status

### Conditions with rules:
- `pregnancy`: 19 rules
- `hypertension`: 13 rules
- `diabetes`: 13 rules
- `surgery_scheduled`: 5 rules
- `kidney_disease`: 2 rules

### Conditions needing rules:
- `lactation`, `ttc`, `heart_disease`, `bleeding_disorders`, `liver_disease`, `thyroid_disorder`, `autoimmune`, `seizure_disorder`, `high_cholesterol`

### Drug classes with thin coverage:
- `nsaids`: 0 rules
- `antiplatelets`: 1 rule
- `thyroid_medications`: 1 rule
- `sedatives`: 1 rule
- `immunosuppressants`: 1 rule
- `statins`: 1 rule

---

## Required Workflow (Every Change)

1. Confirm canonical target exists in source DB.
2. Confirm taxonomy IDs exist.
3. Add/update rule with authoritative sources.
4. Run tests:
   ```bash
   cd scripts && python3 -m pytest tests/test_interaction_tracker.py tests/test_db_integrity.py tests/test_clinical_schema_compat.py -q
   ```
5. Run full suite:
   ```bash
   cd scripts && python3 -m pytest tests/ -q
   ```
6. Update `_metadata.total_entries` and `_metadata.last_updated` in the JSON.

---

## What Not To Do

- Do not add rules for ambiguous ingredient identities.
- Do not add contraindication logic directly inside scoring formulas.
- Do not copy evidence claims without linked sources.
- Do not bypass strict validation.
- Do not silently add new severity/condition labels outside taxonomy.
- Do not create duplicate entries — one object per ingredient.

---

## Change Control Checklist

- [ ] Canonical target exists in allowed source DB
- [ ] Taxonomy enums reused (no ad-hoc values)
- [ ] Sources are authoritative and current
- [ ] Severity level matches evidence strength
- [ ] `last_reviewed` and `review_owner` set
- [ ] `_metadata.total_entries` updated
- [ ] All tests pass
- [ ] No duplicate rule entries

---

## Reusable Agent Prompt

For batch-adding new rules with AI assistance, see `scripts/PROMPT_ADD_INTERACTION_RULES.md`. That prompt includes the full JSON schema, all valid enum values, research protocol, and quality checklist.
