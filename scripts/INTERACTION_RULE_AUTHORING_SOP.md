# PharmaGuide Interaction Rule Authoring SOP

## Scope
This SOP governs how to add or update contraindication/interaction alerts in:
- `/Users/seancheick/.claude-worktrees/dsld_clean/peaceful-ritchie/scripts/data/clinical_risk_taxonomy.json`
- `/Users/seancheick/.claude-worktrees/dsld_clean/peaceful-ritchie/scripts/data/ingredient_interaction_rules.json`

The interaction layer is **alerts-only** by default and does **not** change A/B/C/D scoring.

---

## Why These Files Exist

### `clinical_risk_taxonomy.json`
Controlled enums for:
- `conditions`
- `drug_classes`
- `severity_levels`
- `evidence_levels`

Purpose:
- deterministic behavior
- no free-text drift
- consistent UI/API labels

### `ingredient_interaction_rules.json`
Rule store keyed by canonical identity:
- `subject_ref: {db, canonical_id}`
- `condition_rules[]`
- `drug_class_rules[]`
- optional `dose_thresholds[]`
- provenance (`sources`, `last_reviewed`, `review_owner`)

Purpose:
- exact, reproducible safety lookups from enrichment output

---

## Non-Negotiable Guardrails

1. No free-text matching in runtime safety logic.
   - Rules must resolve by exact canonical identity.

2. Do not add rule subjects that do not exist in source DBs.
   - Add/map canonical ID first, then add rule.

3. Do not invent enum values.
   - Use only taxonomy-defined condition/drug class/severity/evidence IDs.

4. Do not use marketing/blog sources as primary evidence.
   - Prefer NCCIH, NIH ODS, ACOG, LactMed, FDA.

5. Do not overstate severity.
   - `contraindicated/avoid` requires strong support.
   - Use `caution/monitor` when evidence is uncertain.

---

## Supported `subject_ref.db` Values (Current)

- `ingredient_quality_map`
- `other_ingredients`
- `harmful_additives`
- `banned_recalled_ingredients`

If a target is only in `botanical_ingredients` or `standardized_botanicals`, add/move canonical support first or extend code support intentionally.

---

## Authoritative Source Priority

1. NCCIH
2. NIH ODS (Health Professional Fact Sheets)
3. ACOG
4. LactMed
5. FDA

Rules without solid sources should be deferred.

---

## Rule Writing Standards

Each rule should include:
- `id` (stable, unique)
- `subject_ref` (exact canonical target)
- at least one of:
  - `condition_rules[]`
  - `drug_class_rules[]`
  - `pregnancy_lactation`
- `last_reviewed` (ISO date)
- `review_owner`

Each condition/drug rule should include:
- target id (`condition_id` or `drug_class_id`)
- `severity`
- `evidence_level`
- short `mechanism`
- clear `action`
- non-empty `sources[]`

Dose thresholds are optional and should be added only when explicit guideline thresholds exist.

---

## Dose Threshold Policy

Use `dose_thresholds[]` only when you have a defensible numeric cutoff from authoritative guidance.

Required fields:
- `scope`: `condition` or `drug_class`
- `target_id`
- `basis`: `per_day` or `per_serving`
- `comparator`: one of `>`, `>=`, `<`, `<=`, `==`
- `value` (number)
- `unit`
- `severity_if_met`
- optional `severity_if_not_met`

If conversion is not possible in runtime, the base severity is retained.

---

## Required Workflow (Every Change)

1. Confirm canonical target exists in source DB.
2. Confirm taxonomy IDs exist.
3. Add/update rule with authoritative sources.
4. Run strict integrity validation:
   - `python3 /Users/seancheick/.claude-worktrees/dsld_clean/peaceful-ritchie/scripts/db_integrity_sanity_check.py --strict`
5. Run interaction/db tests:
   - `python3 -m pytest /Users/seancheick/.claude-worktrees/dsld_clean/peaceful-ritchie/scripts/tests/test_interaction_tracker.py /Users/seancheick/.claude-worktrees/dsld_clean/peaceful-ritchie/scripts/tests/test_db_integrity.py -q`
6. Re-enrich affected products only:
   - `python3 /Users/seancheick/.claude-worktrees/dsld_clean/peaceful-ritchie/scripts/rerun_affected_enrichment.py --prefix <output_prefix> --auto-changed-from-git --run-enrich --run-score`

---

## What Not To Do

- Do not add rules for ambiguous ingredient identities.
- Do not add contraindication logic directly inside scoring formulas.
- Do not copy evidence claims without linked sources.
- Do not bypass strict validation.
- Do not silently add new severity/condition labels outside taxonomy.

---

## Change Control Checklist

- [ ] Canonical target exists in allowed source DB
- [ ] Taxonomy enums reused (no ad-hoc values)
- [ ] Sources are authoritative and current
- [ ] Severity level matches evidence strength
- [ ] `last_reviewed` and `review_owner` set
- [ ] Strict sanity check passes
- [ ] Interaction/db tests pass
- [ ] Affected-only re-enrich completed

