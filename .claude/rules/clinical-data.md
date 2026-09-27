---
paths:
  - "scripts/data/**"
  - "scripts/api_audit/**"
---

# Clinical data rules (loaded when working in scripts/data or scripts/api_audit)

Curated data is medical-grade: one corrupt entry discredits the whole product.

- **Use the `data-fix` skill** for curated-data work: batch related entries by topic, check each
  entry's identity and sources on its own and record a result per entry, apply the batch with one
  script through `scripts/data_batch.py` (load, explicit per-entry patch, save), prove it with
  `data_batch.py check FILE --since <ref> --expect <keys>`, then verify, test and fix the batch
  together. Never pipe verifier output into data unreviewed (`--apply` flags included).
- **Verify each identifier against the live API, by content.**
  - PMID: `scripts/api_audit/verify_all_citations_content.py` (reads every citation in
    `scripts/data`; interaction rules also `verify_interaction_rules_citations.py --strict`). The
    title/abstract must match the claimed topic. Existence gates have passed ghost refs before
    ("valid 87, invalid 0" with 12 wrong-topic PMIDs).
  - CUI: `verify_cui.py` · RXCUI: `verify_interactions.py` · UNII: `verify_unii.py` ·
    CAS/CID: `verify_pubchem.py` · NCT: `verify_clinical_trials.py` · RDA/UL: `verify_rda_uls.py`.
  - A reused identifier is verified again, the same as a new one. No API access means no write:
    tell Sean.
  - In a batch, `--changed-since <ref>` makes both citation verifiers check only the entries the
    batch changed, one result line each.
- **Before adding an IQM, botanical or probiotic entry,** search existing entries by CUI, CAS and
  name, and confirm same-compound chemistry (CID/InChI). Name or marketing overlap is not identity.
- **A studied dose is not a warning threshold.** A `min_effective_dose` floor needs threshold
  evidence; otherwise the rule fires on presence. See the dose-floor section of
  `scripts/INTERACTION_RULE_AUTHORING_SOP.md`.
- **Changing a structured value** (severity, dose, identifier) means updating every free-text field
  in that entry that mentions it, and asserting the old phrase is gone.
- **Keep `_metadata` accurate.** `data_batch.save` recounts `total_entries` and the IQM statistics
  and bumps `last_updated`; `schema_version` and file-specific counts are yours. Never hand-copy
  those values into docs. Data files are canonical JSON (`test_data_batch.py` pins it).
- **Tests, once per batch:** `scripts/test.sh fast -k <topic>` after the batch is applied, fix every
  failure, then `scripts/test.sh fast` before the commit. Report the output.
- A PreToolUse hook (`~/.claude/hooks/pharmaguide-data-guard.js`) prints this checklist the first
  time a session edits each data file. Treat it as a checklist, not noise.
