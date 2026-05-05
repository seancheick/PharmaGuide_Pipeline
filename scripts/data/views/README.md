# Interaction Rule Views & Authoring Tools

Read-only Markdown slices of `scripts/data/ingredient_interaction_rules.json` for clinician review, plus a CLI authoring helper that writes safely back to the single source of truth.

> **Source of truth:** `scripts/data/ingredient_interaction_rules.json` — one rule object per ingredient (`subject_ref.canonical_id`), with all conditions, drug classes, dose thresholds, and pregnancy/lactation data nested inside that one object. **Do not split this file.** See `scripts/INTERACTION_RULE_AUTHORING_SOP.md`.
>
> The `*.md` files in this directory are **regenerated views**. They exist only to make the 10 K-line JSON readable by condition or drug class. Editing them does nothing — they are overwritten on every regeneration.

---

## Directory layout

```
scripts/data/views/
├── README.md                    ← this file (hand-written, not regenerated)
├── REPORT.md                    ← auto-generated regeneration report (overwritten on every run)
├── pregnancy_lactation.md       ← aggregate of all rules with a pregnancy_lactation block
├── by_condition/
│   ├── pregnancy.md             ← every rule that mentions condition_id=pregnancy
│   ├── hypertension.md
│   ├── diabetes.md
│   └── … (14 total — one per condition_id in clinical_risk_taxonomy.json)
└── by_drug_class/
    ├── anticoagulants.md
    ├── antihypertensives.md
    ├── nsaids.md
    └── … (21 total — one per drug_class_id in clinical_risk_taxonomy.json)
```

Each view is a Markdown table:

```
| canonical_id | db | severity | evidence | alert_headline | mechanism |
```

Subjects are sorted by `canonical_id` so the same ingredient appears in the same row position across views — easy to scan diffs.

---

## Workflow

```
┌──────────────────────────────────────────────────────────────────────┐
│ 1. READ      open scripts/data/views/by_condition/<condition>.md    │
│              (clinician sees only that condition slice)              │
│                                                                      │
│ 2. ADD       python3 scripts/tools/add_rule.py …                    │
│              (validates taxonomy, refuses duplicates, writes back   │
│               to the single ingredient_interaction_rules.json)      │
│                                                                      │
│ 3. REGENERATE  python3 scripts/tools/split_rules_by_condition.py   │
│              (refreshes all views from the updated JSON)            │
│                                                                      │
│ 4. TEST      python3 -m pytest scripts/tests/ -k interaction       │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Commands

### 1) Regenerate all views

```bash
python3 scripts/tools/split_rules_by_condition.py
```

**What it does**
- Loads `scripts/data/ingredient_interaction_rules.json` and `scripts/data/clinical_risk_taxonomy.json`.
- For each rule, scatters its `condition_rules[]` and `drug_class_rules[]` into per-condition and per-drug-class buckets.
- Writes one Markdown file per non-empty bucket, sorted by `subject_ref.canonical_id`.
- Writes the `pregnancy_lactation.md` aggregate (every rule with an authored `pregnancy_lactation` block).
- Writes `REPORT.md` with current counts and last-regeneration marker.

**Inputs**
- `scripts/data/ingredient_interaction_rules.json` — the single source of truth.
- `scripts/data/clinical_risk_taxonomy.json` — provides `label` and `category` for each condition/drug-class.

**Outputs (overwrites every run)**
- `scripts/data/views/by_condition/<condition_id>.md` — one per condition with at least one rule.
- `scripts/data/views/by_drug_class/<drug_class_id>.md` — one per drug class with at least one rule.
- `scripts/data/views/pregnancy_lactation.md` — pregnancy/lactation aggregate table.
- `scripts/data/views/REPORT.md` — current counts and last regeneration marker.

**Does NOT touch**
- `ingredient_interaction_rules.json` (read-only).
- `clinical_risk_taxonomy.json` (read-only).
- `README.md` (this file is hand-written).
- Any pipeline script or test.

**Sample stdout**
```
Wrote 14 condition view(s), 21 drug-class view(s) to scripts/data/views
```

**When to run**
- After every batch of `add_rule.py` invocations.
- Before opening a PR for clinician review.
- After any manual edit to `ingredient_interaction_rules.json`.

---

### 2) Add a condition rule

```bash
python3 scripts/tools/add_rule.py \
  --db ingredient_quality_map \
  --canonical-id ginger \
  --condition pregnancy \
  --severity caution \
  --evidence limited \
  --mechanism "Ginger may stimulate uterine activity at therapeutic doses; first-trimester safety data are limited." \
  --action "Discuss culinary versus therapeutic doses with an obstetric provider before use." \
  --alert-headline "Discuss ginger use in pregnancy" \
  --alert-body "Ginger can be used short-term for nausea, but therapeutic doses during pregnancy should be reviewed with your obstetric provider." \
  --informational-note "Culinary amounts are generally considered safe; supplement-strength doses are the concern." \
  --source "https://www.nccih.nih.gov/health/ginger" \
  --source "https://ods.od.nih.gov/factsheets/Ginger-HealthProfessional/"
```

**What it does**
1. Validates `--db` against the 5 supported subject databases (`ingredient_quality_map`, `banned_recalled_ingredients`, `harmful_additives`, `botanical_ingredients`, `other_ingredients`).
2. Validates `--condition`, `--severity`, `--evidence` against `clinical_risk_taxonomy.json` enums. Unknown values exit with the full list of valid IDs.
3. Enforces v5.2 authored-copy lengths:
   - `--alert-headline` must be 20–60 chars.
   - `--alert-body` must be 60–200 chars.
   - `--informational-note` must be 40–120 chars.
   - `--informational-note` is **required** when severity is `avoid` or `contraindicated`.
4. Looks up an existing rule by `(db, canonical_id)`:
   - **If found** → appends a new entry to `condition_rules[]` on that rule. Refuses if the same `condition_id` is already present (prints the offending rule id and exits non-zero).
   - **If not found** → creates a brand-new rule object with `id = RULE_<DB_SHORT>_<CANON>_<CONDITION_UPPER>`, empty `drug_class_rules[]` / `dose_thresholds[]` / `pregnancy_lactation{}` , today's `last_reviewed`.
5. Updates `_metadata.total_entries`, `_metadata.total_rules`, `_metadata.last_updated`.
6. Writes the file back with `indent=2`, UTF-8 preserved, trailing newline.

**Required arguments**
| Flag | Purpose |
|---|---|
| `--db` | Subject database. One of the 5 supported values. |
| `--canonical-id` | Exact id within that DB (e.g. `ginger`, `BANNED_EPHEDRA`). |
| `--condition` *or* `--drug-class` | Mutually exclusive — pick one. |
| `--severity` | Taxonomy enum (`info`, `monitor`, `caution`, `avoid`, `contraindicated`). |
| `--evidence` | Taxonomy enum (`insufficient`, `theoretical`, `probable`, `established`, …). |
| `--mechanism` | 1–2 sentence biological/clinical reason. |
| `--action` | 1–2 sentence directive starting with a verb (Avoid, Monitor, Discuss…). |

**Optional arguments**
| Flag | Default / Behavior |
|---|---|
| `--source URL` | Repeatable. Authoritative URLs (NCCIH, NIH ODS, ACOG, LactMed, FDA, PubMed). |
| `--alert-headline TEXT` | Flutter-shown headline (20–60 chars). |
| `--alert-body TEXT` | Flutter-shown body (60–200 chars). |
| `--informational-note TEXT` | Required for `avoid`/`contraindicated` (40–120 chars). |
| `--reviewer NAME` | Defaults to `pharmaguide_clinical_team` (SOP standard). |
| `--dry-run` | Prints the action and JSON preview, makes no file changes. |

**Sample success output**
```
OK: appended condition 'pregnancy' to RULE_IQM_GINGER_BLEEDING
File: scripts/data/ingredient_interaction_rules.json (145 rules)
```

**Sample dedupe rejection**
```
ERROR: subject ginger already has a condition rule for 'surgery_scheduled'
       (rule id: RULE_IQM_GINGER_BLEEDING). Edit that entry directly or remove it first.
```

**Sample validation rejection**
```
ERROR: unknown condition 'pregnancyy'. Valid: ['autoimmune', 'bleeding_disorders', 'diabetes', …]
```

---

### 3) Add a drug-class rule

```bash
python3 scripts/tools/add_rule.py \
  --db ingredient_quality_map \
  --canonical-id ginger \
  --drug-class anticoagulants \
  --severity caution \
  --evidence moderate \
  --mechanism "Ginger inhibits platelet aggregation in vitro; clinical bleeding signal is weak but plausible at high doses." \
  --action "Monitor for bruising or bleeding; separate doses or hold before procedures." \
  --alert-headline "Talk to your provider if on blood thinners" \
  --alert-body "Ginger has mild antiplatelet effects in lab studies. If you take anticoagulants, ask your provider before adding supplemental doses." \
  --source "https://www.nccih.nih.gov/health/ginger"
```

Same workflow as #2 but appends to `drug_class_rules[]` and the dedupe check uses `drug_class_id`. `--informational-note` is optional here unless severity is `avoid`/`contraindicated`.

---

### 4) Preview without writing

Add `--dry-run` to any `add_rule.py` invocation:

```bash
python3 scripts/tools/add_rule.py … --dry-run
```

**Sample**
```
DRY RUN — would: created new rule RULE_INGREDIENT_TURMERIC_PREGNANCY
Sub-rule preview:
{
  "condition_id": "pregnancy",
  "severity": "caution",
  …
}
```

The taxonomy + length + dedupe checks all run; only the disk write is skipped. Safe for review with a clinician before commit.

---

### 5) Verify after each batch

```bash
python3 -m pytest scripts/tests/test_db_integrity.py \
                  scripts/tests/test_no_duplicate_drug_class_rules.py \
                  scripts/tests/test_condition_vocab_contract.py \
                  scripts/tests/test_drug_class_vocab_contract.py \
                  scripts/tests/test_evidence_level_vocab_contract.py \
                  scripts/tests/test_severity_vocab_contract.py \
                  scripts/tests/test_safety_copy_production.py \
                  scripts/tests/test_validate_safety_copy.py -q
```

Catches schema drift, duplicate drug-class rules within a subject, and authored-copy length violations. Run before every commit.

For full coverage:

```bash
python3 -m pytest scripts/tests/ -k interaction
```

---

## What these tools do **not** do

- Do **not** modify the pipeline scripts (`enrich_supplements_v3.py`, `score_supplements.py`, `build_final_db.py`).
- Do **not** change the JSON schema, key names, or rule ID format used by Flutter.
- Do **not** author `dose_thresholds[]` — those need numeric clinical guidance and should be added by hand following SOP §"Dose Threshold Policy".
- Do **not** author the `pregnancy_lactation` aggregate block — same reason.
- Do **not** verify your sources. URLs are stored as-is; verify NCCIH / NIH ODS / PubMed content yourself before commit (per `critical_no_hallucinated_citations` and the SOP source-priority list).

---

## Why this layout

The data model is **ingredient-keyed**: one rule object per ingredient with all conditions/drug classes nested inside. Splitting the JSON file by condition would fragment a single ingredient (e.g., ginger) across `pregnancy.json`, `bleeding.json`, `surgery_scheduled.json`, `anticoagulants.json`, `antiplatelets.json` — re-introducing the duplicate-detection problem you wanted to solve, complicating pipeline loading, and breaking the "one rule per ingredient" SOP rule.

The view layer gives a clinician a per-condition reading experience with zero changes to the data contract or pipeline behavior.

---

## Related docs

- `scripts/INTERACTION_RULE_AUTHORING_SOP.md` — clinical authoring SOP (sources, severity ladder, change-control checklist).
- `scripts/PROMPT_ADD_INTERACTION_RULES.md` — reusable AI agent prompt for batch rule drafting.
- `scripts/data/clinical_risk_taxonomy.json` — controlled enums (conditions, drug classes, severity, evidence).
