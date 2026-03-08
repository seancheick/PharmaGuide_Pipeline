# Unmapped Resolution Prompt Design

**Goal:** Rewrite the unmapped-resolution prompt so it matches the current cleaner, enricher, routing precedence, raw DSLD verification workflow, and clinical evidence standards.

**Architecture:** Use one master SOP-style prompt that first classifies each unmapped case before deciding whether it is a data addition, alias addition, structural/filter issue, routing bug, precedence bug, or fallback-scoring gap. The prompt should force raw DSLD inspection for suspicious items and require source-backed identity/clinical notes before database changes.

**Key decisions:**
- Make clean-stage unmapped the primary backlog for DB growth.
- Treat enrich-stage unmapped and fallback reports as QA/bug surfaces, not proof of true gaps.
- Route actives to IQM by default, inactives to other DBs by default, but let harmful/banned override when source-backed.
- Require a small shadow rerun after code fixes so bug fixes are verified in-pipeline, not just by unit tests.
- Require PMID/DOI in notes when available and authoritative sources for branded or clinical identity claims.
