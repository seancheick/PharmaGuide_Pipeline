# Fix Sprint 01 — audit report

- **content_hash:** `sha256:d14a0d8f0501f82d4f1c4efb902931262843d9cd0dad43aeceff09bf2a873280`
  (pinned in both repos: `test_medication_depletions_artifact.py` +
  `med_nutrient_bundled_parity_test.dart`)
- **reviewer:** `lead_clinician_fix_sprint_01` · **2026-07-23**
- **corpus after:** verified **12** · needs_revision **8** · rejected **1** ·
  unverified **59** (total 80)
- **new standing gate:** `test_med_nutrient_ul_safety.py` — no publication-ready
  entry may recommend above a conservative UL without a `dose_exemption`.

## Changes (4 entries)

| Entry | Result | Defect categories | Citation action |
|-------|--------|-------------------|-----------------|
| DEP_LEVOTHYROXINE_CALCIUM | verified | mechanism/impact overstatement (40%), out-of-scope claims | kept Singh 10838651 + 11716045 (verified on-topic) |
| DEP_LEVOTHYROXINE_IRON | verified | placeholder source, overstatement (30–45%), out-of-scope claims | NIH-ODS → Campbell 1443969 (controlled trial) |
| DEP_OCP_VITAMINB6 | verified (downgraded) | evidence overstatement, **dose > UL**, placeholder source | NIH-ODS → Wilson 21967158 |
| DEP_OCP_FOLATE | rejected | relationship premise unsupported, placeholder source | NIH-ODS → Wilson 21967158 (the contradicting review) |

## Defect tally (this sprint)

| Category | Count | Where |
|----------|-------|-------|
| Placeholder source replaced | 3 | levo-Fe, OCP-B6, OCP-folate |
| Mechanism/recommendation overstatement corrected | 3 | levo-Ca (40%), levo-Fe (30–45%), OCP-B6 (dose) |
| Dose exceeds accepted UL | 1 | OCP-B6 (now UL-gated) |
| Relationship premise unsupported → rejected | 1 | OCP-folate |
| Ghost PMID | 0 | — |

## Cross-batch note

A full defect ledger across all batches is deferred to avoid fabricated counts —
reconstruct per-category tallies from each batch's `research.md` when needed.
Established so far: **batch_01 = 2 ghost PMIDs** (19174283 calf-diarrhea cited as
Haugen; 3003511 E. coli aspartate-kinase cited as Altura magnesium). batch_02 = 0
ghosts. fix_sprint_01 = 0 ghosts.
