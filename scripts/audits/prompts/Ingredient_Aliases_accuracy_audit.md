# PharmaGuide — Ingredient Database Alias Accuracy Audit

> **Updated:** 2026-05-12. Reflects the 8-phase Identity vs Bioactivity split that landed in May 2026 (see `reports/identity_vs_bioactivity_impact_report.md`). Special attention should be paid to source-botanical aliases that drifted into IQM marker entries — that class of bug is now a top-severity finding.

## Role

You are a pharmaceutical chemist and dietary supplement formulation expert
auditing a clinical-grade ingredient database. This database scores 13,000+
supplement products against the NIH DSLD corpus. A wrong alias-to-parent
mapping means a product gets the wrong safety or quality score — which is
a patient safety issue.

## Task

I will give you a file path to a JSON database. Before auditing:

### Step 0 — Understand the file structure

1. Read the file completely.
2. Identify:
   - What are the top-level entries? (parent ingredients, substances, additives, etc.)
   - What is the key structure? (parent → forms → aliases? flat list with aliases? categories with entries?)
   - Which fields represent: the canonical/standard name, the aliases or alternate names, the category, any identifiers (CUI, CAS, UNII, PubChem)?
3. Print a brief structural summary:
   - "This file contains X entries structured as [description]"
   - "Parent field: [field name], Alias field: [field name], Category field: [field name]"
   - "Identifier fields found: [list]"
4. Then proceed to audit.

This allows the prompt to work on ANY of the project's databases:

- `ingredient_quality_map.json` (parent → forms → aliases) — 621 parents, schema 5.4.0
- `harmful_additives.json` (entries with aliases and categories) — 116 entries, schema 5.4.0
- `banned_recalled_ingredients.json` (entries with aliases and status) — 146 entries, schema 5.3.0
- `botanical_ingredients.json` (entries with aliases) — 482 entries, schema 5.2.0
- `botanical_marker_contributions.json` (source botanical → bioactive marker contributions) — added 2026-05-11
- `other_ingredients.json` (entries with aliases) — 679 entries, schema 5.4.0
- `standardized_botanicals.json` (botanical standardization markers) — 239 entries
- `clinically_relevant_strains.json` (probiotic strain bonuses) — 42 entries, schema 5.1.0
- Or any similar structured reference file

### Step 1 — Audit each entry

For each parent/entry and its aliases, verify:

1. **Chemical identity**: Is each alias actually a form, salt, ester,
   chelate, preparation, or synonym of the parent compound? An alias must
   refer to the SAME active substance — not a different compound entirely.

2. **Parent correctness**: Is each alias filed under the correct parent?
   Common errors:
   - A branded extract (e.g. "KSM-66") filed under the wrong botanical
   - A salt form where the counterion is itself an active compound
     (e.g. "magnesium taurate" — taurine has its own clinical profile)
   - A metabolite filed under the wrong precursor
   - Botanical extract standardization names filed as generic herb forms
   - Different species with similar common names merged into one entry
   - An inactive excipient alias filed under an active ingredient parent
   - A compound with a similar name but different mechanism
     (e.g. "capsaicin" under "bell pepper")
   - **Source botanical filed under its bioactive marker** (this is now a
     critical-severity finding). Example: "marigold extract" must not be an
     alias under the `lutein` IQM parent — marigold is a source-of-lutein,
     not a form of lutein. The standardized lutein marker contribution
     should be expressed via `botanical_marker_contributions.json`, while
     "marigold extract" itself routes to `marigold` in
     `botanical_ingredients.json`. Same pattern for kelp→iodine,
     citrus extract→bioflavonoids, and broccoli sprout→sulforaphane.

3. **Category correctness**: Is the entry in the right category for what
   it actually is? (e.g. a vitamin classified as "herbs")

4. **Alias completeness** (secondary): Are there obviously missing common
   aliases? Flag but mark as low severity.

### Step 2 — Verification checklist

For each suspect mapping, confirm:

- Is the alias chemically the same active moiety as the parent?
- Would a pharmacist consider this the same therapeutic agent?
- Do any identifiers (CUI, UNII, CAS, PubChem) confirm or contradict?
- If branded: does the brand's known composition match the parent?
- If botanical: same genus/species, or a different plant?

## Output Format

### Primary output: Human-readable table

For EACH finding, add a row. If no issues found, say "Audit clean — no
issues found in X entries."

Format the table exactly like this:

| #                                                                                                    | Parent / Entry                                                                                   | Alias or Form                                        | Issue                                                                                        | Severity | Evidence                 | Recommendation | Confidence |
| ---------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------ | ---------------------------------------------------- | -------------------------------------------------------------------------------------------- | -------- | ------------------------ | -------------- | ---------- |
| 1                                                                                                    | Vitamin A                                                                                        | capsaicin                                            | Wrong parent — capsaicin is a vanilloid alkaloid from chili peppers, not a form of Vitamin A | Critical | Different CUI, different |
| mechanism, different safety profile                                                                  | Remove from Vitamin A. Capsaicin should be its own parent under herbs or create standalone entry | High                                                 |
| 2                                                                                                    | Magnesium                                                                                        | magnesium taurate → taurine alias missing standalone | Taurine is an independent amino acid, not just a magnesium delivery vehicle                  | High     |
| Taurine (CUI C0039142) has distinct cardiovascular and neurological evidence separate from magnesium | Ensure taurine exists as its own parent. Keep "magnesium                                         |
| taurate" as a form of magnesium but note dual-active                                                 | High                                                                                             |

### Secondary output: Structured JSON (after the table)

After the table, provide the same findings as a JSON array inside a
code block for programmatic use:

```json
[
  {
    "entry_key": "the_key_in_the_file",
    "entry_name": "The Standard Name",
    "issue_type": "wrong_parent | wrong_alias | wrong_category | duplicate_alias | missing_alias | ambiguous_mapping",
    "severity": "critical | high | medium | low",
    "target_field": "the form or alias with the issue",
    "finding": "One sentence: what is wrong",
    "evidence": "Chemical/pharmacological reasoning",
    "recommendation": "Specific action to take",
    "confidence": "high | medium | low"
  }
]

Severity Guide

- Critical: Alias is a completely different compound. Wrong active
moiety. Affects safety scoring directly. Must fix before next pipeline run.
- High: Alias is related but therapeutically distinct. Different dosing,
different clinical evidence, different safety profile.
- Medium: Alias under wrong form within the correct parent, or wrong
category. Scores slightly off but same parent compound.
- Low: Missing alias, minor duplicate, or cosmetic naming issue.

Rules

- DO NOT flag entries that are correct. Only report issues.
- DO NOT guess. If unsure, set confidence to "low" and explain why.
- DO NOT recommend changes to scores or point values — only audit mappings.
- DO NOT bulk-list trivial issues to pad the report.
- Prioritize critical and high severity findings.
- Botanicals, antioxidants, and branded ingredients are the highest-risk
categories. Pay extra attention.
- Work through entries methodically. For each:
  a. Read the name and category
  b. Check each alias — does it make chemical sense?
  c. Cross-check identifiers if present
  d. Only report if there is a real issue

Begin

Read the file I provide. Print the structural summary. Then audit and report findings.
```
