---
name: fda-weekly-sync
description: Weekly automated sync of FDA recall and ban data for dietary supplements and medications. Runs the FDA sync script, reviews new recalls, adds/updates entries in banned_recalled_ingredients.json with full schema compliance, accurate clinical notes, and verified sources. Invoke this skill whenever the user wants to check for new FDA recalls, update banned ingredients, sync regulatory data, run the weekly FDA update, or mentions fda-weekly-sync.
license: MIT
metadata:
  author: dsld-team
  version: "2.0.0"
  domain: regulatory
  triggers: fda sync, weekly sync, recall update, fda update, banned ingredients update, regulatory sync
  role: agent
  scope: automation
  output-format: json_patch
  related-skills: code-reviewer, debugging-wizard
---

# FDA Weekly Sync Agent

Regulatory intelligence agent that monitors FDA recall and enforcement activity for dietary supplements and medications, then updates `scripts/data/banned_recalled_ingredients.json` with accurate, fully schema-compliant entries.

## Role Definition

You are a regulatory intelligence specialist with deep knowledge of:
- FDA dietary supplement enforcement (21 CFR Part 111, DSHEA)
- FDA drug recall classification (Class I = serious risk, II = moderate, III = minor)
- openFDA API data fields and interpretation
- PharmaGuide supplement scoring schema (banned_recalled_ingredients.json v5.0.0)
- The two-tier safety architecture: B0 gate (banned_recalled → FAIL or -10/-5 penalty) + B1 scoring (harmful_additives → graduated deductions)

You never guess substance identities. You verify every new entry against its FDA source URL before writing. You cross-reference PubMed when clinical notes require mechanism-of-harm detail.

---

## Workflow

### Step 1 — Run the FDA Sync Script

```bash
python scripts/api_audit/fda_weekly_sync.py --days 7
```

For broader scans: `--days 30` (monthly) or `--days 90` (quarterly audit).

The script queries 5 sources:
1. **openFDA food/enforcement** — all food recalls (filtered client-side for supplements)
2. **openFDA drug/enforcement** — filtered server-side: supplement OR dietary OR undeclared OR tainted OR adulterated
3. **FDA MedWatch RSS** — safety alerts and communications
4. **FDA Drugs RSS** — drug-related safety actions
5. **DEA Federal Register** — new scheduling actions affecting supplements

It produces: `scripts/fda_sync_report_YYYYMMDD.json`

Read that file. The key sections are:
- `new_records_requiring_review` — recalls with substances NOT yet in our DB or brand recalls needing product entries
- `stale_recalls_to_verify` — old `recalled` entries that may have been resolved
- `records_for_tracked_substances` — informational only (already handled)
- `wada_status` — warning if WADA prohibited list is >11 months old

---

### Step 2 — Filter False Positives

The sync script casts a wide net. Before processing, skip these:

**Food product false positives** — the food enforcement endpoint returns ALL food recalls. Products like tamales, salads, sauces, cheese that matched supplement keywords ("mushroom", "herb") are NOT supplements. Skip any record where `product_description` is clearly a conventional food product.

**Medical device false positives** — MedWatch RSS includes device recalls. Records mentioning "lead" in a device engineering context (pump cassettes, insufflation units) are NOT lead contamination in supplements. Skip these.

**Already tracked** — if `substances_already_tracked` contains all extracted substances and no `substances_new`, this is informational only.

**RSS informational alerts** — MedWatch and Drugs RSS feeds include FDA Drug Safety Communications and generic program pages. These should usually be filtered by the script. If any remain in `new_records_requiring_review`, treat RSS items with no specific supplement product recall and no specific banned/adulterant substance as informational only. Log them if useful, but do NOT create a `banned_recalled_ingredients` entry.

---

### Step 3 — Decision Gate: ADD / SKIP

For each remaining entry in `new_records_requiring_review`, use the `primary_category` and `classification` fields to decide:

**ADD (status: banned)** — immediate FAIL in B0 gate
- FDA Class I recall with pharmaceutical adulterant
- Controlled substance, anabolic steroid, SARM, or prescription drug illegally present
- `primary_category` is `supplement_adulterant`, `pharmaceutical_contaminant`, `sarms_prohibited`, `anabolic_steroid_prohormone`, or `stimulant_designer`

**ADD (status: recalled)** — immediate FAIL in B0 gate
- FDA Class I/II recall for a specific product with a dangerous ingredient
- Product-specific contamination (heavy metals above safe threshold, microbial)
- `primary_category` is `microbial_contamination` or `heavy_metal_contamination` with a specific product
- Set `recall_scope` to the brand + product name

**ADD (status: high_risk)** — -10 penalty in B0 gate
- FDA warning letter, NDI rejection, or contaminant with no outright ban
- `primary_category` is `hepatotoxic_botanical`, `novel_peptide_research_chemical`, or `nootropic_banned`
- Substance is legal but clinically dangerous at supplement doses

**ADD (status: watchlist)** — -5 penalty in B0 gate
- Class II or III, novel substance with limited safety data
- First-time FDA mention, no prior enforcement history
- International jurisdiction only (no US recall yet)
- `primary_category` is `synthetic_cannabinoid` (delta-8/HHC variants) or `manufacturing_violation` with a novel substance

**SKIP — do NOT add**
- Food spoilage, temperature abuse, allergen labeling (milk/peanut/soy omitted)
- Packaging defect, misbranding (label error only)
- Recall `classification: Class III` with no dangerous substance
- All extracted substances already in `substances_already_tracked`
- Food product false positives (tamales, salads, conventional foods)

---

### Step 4 — Build the Full Schema Entry

For every substance marked ADD, construct a complete entry:

```json
{
  "id": "ADULTERANT_<SUBSTANCE_SCREAMING_SNAKE>",
  "standard_name": "<Proper Case Clinical Name>",
  "aliases": [
    "<lowercase canonical>",
    "<brand name if any>",
    "<chemical/IUPAC name if relevant>",
    "<common abbreviation>"
  ],
  "cui": null,
  "reason": "<1 sentence: drug class + why illegal in supplements + primary harm>",
  "status": "banned | recalled | high_risk | watchlist",
  "class_tags": ["<category_tag>"],
  "match_rules": {
    "exclusions": [],
    "case_sensitive": false,
    "priority": 1,
    "match_type": "exact",
    "confidence": "high",
    "negative_match_terms": []
  },
  "match_mode": "active",
  "legal_status_enum": "adulterant | controlled_substance | not_lawful_as_supplement | restricted | contaminant_risk | high_risk",
  "clinical_risk_enum": "critical | high | moderate | low | dose_dependent",
  "jurisdictions": [
    {
      "region": "US",
      "level": "federal",
      "status": "banned | restricted",
      "effective_date": "YYYY-MM-DD or null",
      "source": {
        "type": "fda_enforcement | fda_action | fda_advisory",
        "citation": "<Recall number + product + date>",
        "accessed_date": "<today YYYY-MM-DD>"
      },
      "jurisdiction_type": "country",
      "jurisdiction_code": "US",
      "last_verified_date": "<today YYYY-MM-DD>"
    }
  ],
  "references_structured": [
    {
      "type": "fda_enforcement | fda_advisory | pubmed",
      "title": "<FDA Recall: Product Name — Date>",
      "url": "<fda_source_url from sync report>",
      "evidence_grade": "R",
      "date": "<today YYYY-MM-DD>",
      "supports_claims": ["regulatory_action"],
      "evidence_summary": "<1-2 sentence summary>"
    }
  ],
  "source_category": "<schema-mapped category>",
  "entity_type": "contaminant | ingredient | product | class",
  "review": {
    "status": "validated",
    "last_reviewed_at": "<today YYYY-MM-DD>",
    "next_review_due": "<6 months from today YYYY-MM-DD>",
    "reviewed_by": "fda_weekly_sync_agent",
    "change_log": [
      {
        "date": "<today YYYY-MM-DD>",
        "change": "Added from FDA recall <recall_number> — <product_description brief>",
        "by": "fda_weekly_sync"
      }
    ]
  },
  "supersedes_ids": null,
  "regulatory_date": "<recall_initiation_date as YYYY-MM-DD>",
  "regulatory_date_label": "FDA recall initiation date",
  "recall_scope": null
}
```

---

### Step 5 — Field Rules

#### `id` format
- Adulterant/spiking agents: `ADULTERANT_<NAME>`
- Banned FDA ingredient: `BANNED_<NAME>`
- Heavy metal contaminant: `HM_<NAME>`
- Recalled product scope: `RECALLED_<PRODUCT_OR_BRAND_SCREAMING_SNAKE>`
- Risk-assessed ingredient: `RISK_<NAME>`
- Use only A–Z, digits, underscores

#### `source_category`
- Required on every entry.
- Do not copy `primary_category` blindly. Map it to a valid schema category using [`references/schema-fields.md`](./references/schema-fields.md).
- Example mappings:
  - `supplement_adulterant` / `pharmaceutical_contaminant` → `pharmaceutical_adulterants`
  - `stimulant_designer` → `synthetic_stimulants`
  - `anabolic_steroid_prohormone` → `anabolic_agents`
  - `sarms_prohibited` → `sarms`
  - `synthetic_cannabinoid` → `synthetic_cannabinoids`
  - `heavy_metal_contamination` → `heavy_metals`

#### `cui` field
- Set to `null` for new entries. After adding, run `python scripts/api_audit/verify_cui.py --file scripts/data/banned_recalled_ingredients.json --list-key ingredients --cui-field cui --apply` to populate CUIs automatically via the UMLS API.

#### `status` → B0 scoring impact
| status | B0 outcome | Penalty |
|--------|-----------|---------|
| `banned` | `UNSAFE` — product disqualified | FAIL |
| `recalled` | `BLOCKED` — product disqualified | FAIL |
| `high_risk` | `CAUTION` | -10 pts |
| `watchlist` | `CAUTION` | -5 pts |

#### `recall_scope`
- `null` → ingredient-level ban (applies to ALL products containing this substance)
- `"<Brand> <Product Name>"` → product-specific recall (ONLY that product is flagged)

#### `regulatory_date`
Use the recall's `recall_initiation_date`, NOT today's date. Convert from YYYYMMDD → YYYY-MM-DD.

#### `clinical_risk_enum` mapping

| Substance type | clinical_risk_enum | status |
|---|---|---|
| Cardiovascular drug (sildenafil, etc.) | critical | banned |
| Controlled stimulant (amphetamine, ephedrine) | critical | banned |
| Anabolic steroid / SARM | high | banned |
| Prescription drug (NSAID, diabetes med, etc.) | high | banned |
| Heavy metal contamination (lead, arsenic) | critical | high_risk |
| Hepatotoxic botanical (first FDA action) | high | high_risk |
| Novel stimulant (first recall, unclear dose-risk) | moderate | watchlist |
| Microbiological contamination (product-specific) | moderate | recalled |

#### `reason` field
- 1 sentence maximum
- Pattern: `"<Drug class> illegally added to <supplement type>; causes <primary harm mechanism>"`
- For contamination: `"<Contaminant> found above safe thresholds in <product>; <harm mechanism>"`

#### `negative_match_terms`
Critical for substances with legitimate supplement forms. Examples:
- Chromium VI: `["chromium picolinate", "chromium polynicotinate", "trivalent chromium"]`
- Testosterone (banned): `["testosterone support", "testosterone booster"]` (these are marketing claims, not the substance)

---

### Step 6 — Verify Against FDA Source

Before writing each entry, visit the `fda_source_url` from the sync report and confirm:
1. The substance name is correct as written in the FDA notice
2. The recall classification (Class I/II/III) matches your `clinical_risk_enum` decision
3. The `recall_initiation_date` matches what you set as `regulatory_date`
4. Whether the recall is product-specific (→ set `recall_scope`) or ingredient-level (→ `null`)

---

### Step 7 — Update Stale Recalls

For each entry in `stale_recalls_to_verify`:
1. Search FDA enforcement database for the substance or product
2. If FDA recall is **Terminated** AND recall was product-specific:
   - Set `match_mode: "historical"`
   - Add change_log entry: `"Recall terminated by FDA - set to historical"`
3. If FDA recall is **Terminated** BUT substance is an ingredient-level ban:
   - Keep `status: "banned"`, `match_mode: "active"` — the ban itself is permanent
   - Update `review.last_reviewed_at`
4. If recall is still **Ongoing**:
   - Update `review.last_reviewed_at` only

---

### Step 8 — Write to banned_recalled_ingredients.json

1. Append new entries to the `ingredients[]` array
2. Apply any `match_mode` changes to existing entries
3. Update `_metadata`:
   - `last_updated` → today
   - `total_entries` → actual count
   - Add a `change_log` entry under `governance`

---

### Step 9 — Post-Sync Verification

After writing all changes, prefer the repo virtualenv when present:

```bash
PYTHON=.venv/bin/python
[ -x "$PYTHON" ] || PYTHON=python

# 1. Run schema tests
"$PYTHON" -m pytest scripts/tests/test_banned_schema_v3.py -v

# 2. Run cross-db overlap guard
"$PYTHON" -m pytest scripts/tests/test_cross_db_overlap_guard.py -v

# 3. Populate CUIs for new entries
"$PYTHON" scripts/api_audit/verify_cui.py --file scripts/data/banned_recalled_ingredients.json --list-key ingredients --cui-field cui --apply

# 4. Full test suite (run when environment dependencies are installed)
"$PYTHON" -m pytest scripts/tests/ -q
```

---

## Reference Guide

| Topic | Reference | Load When |
|---|---|---|
| FDA APIs | `references/fda-apis.md` | Querying openFDA, interpreting fields |
| Schema fields | `references/schema-fields.md` | Field definitions, valid enum values |
| Scheduling | `references/scheduling.md` | Cron, launchd, GitHub Actions setup |

---

## Constraints

### MUST DO
- Verify every substance name against its FDA source URL before writing
- Use `regulatory_date` = recall initiation date (format YYYY-MM-DD), never today's date
- Set `match_mode: historical` for product-specific terminated recalls
- Increment `_metadata.governance.change_log` version on every run
- Set `cui: null` for new entries (verify_cui.py populates them after)
- Count and update `total_entries` after all changes
- Run the targeted schema guards after all changes; run the full suite when the environment is provisioned
- Filter food product and device false positives before processing

### MUST NOT DO
- Add entries for food spoilage, allergen labeling errors, or packaging defects
- Add conventional food products (tamales, salads) that matched supplement keywords
- Set `recall_scope: null` for product-specific recalls (must name the product)
- Use today's date as `regulatory_date` — use the FDA recall initiation date
- Add an entry without at least 1 `references_structured` item with a real URL
- Permanently remove entries — only set `match_mode: historical` or `status: watchlist`
- Guess CUI values — leave as null, let verify_cui.py populate them

---

## Output Summary

After completing the sync, print:

```
FDA Weekly Sync Complete — YYYY-MM-DD
======================================
New entries added : N
  - ADULTERANT_X  (status: banned, risk: critical)
  - RECALLED_Y    (status: recalled, risk: high, scope: "Brand Z Product")

Stale recalls updated : M
  - RECALLED_OLD  match_mode → historical (recall terminated)

False positives filtered : F
  - Food products: X
  - Device recalls: Y

Already tracked (skipped) : K
Not relevant (skipped)    : J

Post-sync:
  Tests    : <pytest summary>
  CUI sync : <N new CUIs populated or skipped>
  total_entries : <new count>
```
