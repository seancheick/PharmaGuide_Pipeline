# IQM Collision Cleanup Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Remove dangerous cross-parent IQM aliases, add narrow disambiguation only where dual identity is legitimate, and harden normalization against confirmed identity loss.

**Architecture:** Use TDD around live collision cases first, then make the smallest data and matcher changes that preserve current safe routing. Prefer data cleanup where a term unambiguously names one compound; prefer code disambiguation only for true multi-identity labels like fish-oil families and mineral complexes.

**Tech Stack:** Python, pytest, JSON reference DBs, official regulatory/identity sources.

---

### Task 1: Lock dangerous collisions with failing tests
- Modify: `scripts/tests/test_enrichment_regressions.py`
- Modify: `scripts/tests/test_ingredient_quality_map_schema.py`
- Add tests for `calcium ascorbate`, `calcium pantothenate`, `nicotinamide riboside`, `nicotinamide mononucleotide`, `MaquiBright`, and `vitexin`.

### Task 2: Clean IQM data for unambiguous aliases
- Modify: `scripts/data/ingredient_quality_map.json`
- Remove dangerous aliases from the wrong parents and keep them only on the chemically correct parent.
- Remove generic non-identity aliases like `molecular distilled`, `triglyceride form`, and `phospholipid form` where they create parent collisions.

### Task 3: Add narrow disambiguation for legitimate shared identities
- Modify: `scripts/enrich_supplements_v3.py`
- Keep explicit preferred-parent resolution only for true dual-identity cases such as `Life's DHA` and `concentrated fish oil`.

### Task 4: Re-scan normalization for identity loss
- Modify: `scripts/tests/test_pipeline_regressions.py` if needed.
- Patch only confirmed identity-destructive preprocessing beyond the already-fixed `oil` case.

### Task 5: Verify
- Run: `PYTHONPATH=scripts python3 -m pytest scripts/tests/test_enrichment_regressions.py scripts/tests/test_pipeline_regressions.py scripts/tests/test_ingredient_quality_map_schema.py scripts/tests/test_db_integrity.py -q`
- Run: `python3 scripts/db_integrity_sanity_check.py --strict`
