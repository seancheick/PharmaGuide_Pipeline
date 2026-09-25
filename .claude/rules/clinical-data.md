---
paths:
  - "scripts/data/**"
  - "scripts/api_audit/**"
---

# Clinical data rules (loaded when working in scripts/data or scripts/api_audit)

Curated data is medical-grade: one corrupt entry discredits the whole product.

- **Use the `data-fix` skill** for any curated-data correction: one entry at a time, verify it,
  test it, then move to the next. Never script a bulk rewrite of entries.
- **Verify each identifier against the live API, by content.**
  - PMID: `scripts/api_audit/verify_all_citations_content.py`. The title/abstract must match the
    claimed topic. Existence gates have passed ghost refs before ("valid 87, invalid 0" with 12
    wrong-topic PMIDs).
  - CUI: `verify_cui.py` · RXCUI: `verify_interactions.py` · UNII: `verify_unii.py` ·
    CAS/CID: `verify_pubchem.py` · NCT: `verify_clinical_trials.py` · RDA/UL: `verify_rda_uls.py`.
  - A reused identifier is verified again, the same as a new one. No API access means no write:
    tell Sean.
- **Before adding an IQM, botanical or probiotic entry,** search existing entries by CUI, CAS and
  name, and confirm same-compound chemistry (CID/InChI). Name or marketing overlap is not identity.
- **Changing a structured value** (severity, dose, identifier) means updating every free-text field
  in that entry that mentions it, and asserting the old phrase is gone.
- **Keep `_metadata` accurate** (`schema_version`, `last_updated`, `total_entries`). Never
  hand-copy those values into docs.
- **After every edit:** `scripts/test.sh fast -k <topic>` and report the output.
- A PreToolUse hook (`~/.claude/hooks/pharmaguide-data-guard.js`) reprints these verification
  commands on every JSON edit here. Treat it as a checklist, not noise.
