# Resveratrol from grape and knotweed — October 20, 2026

Sean, 2026-10-19:
- ADR-0005 accepted with an amendment: preserving a warning must not force an incorrect identity;
  Japanese knotweed keeps its plant identity and reaches applicable resveratrol warnings through a
  source-qualified relationship.
- Resveratrol: keep the grape-extract identity and recognize explicitly declared resveratrol
  separately; for anticoagulants/antiplatelets/bleeding disorders keep a clearly qualified
  advisory (clinical significance at this amount uncertain), with no proven-risk wording, no
  arbitrary cutoff, no medication adjustment and no quality penalty; the same evidence standard
  for BioVin and knotweed.

## Changes

1. **Identity.** The Hu Zhang / Reynoutria plant names ("hu zhang", "hu zhang extract", "hu zhang
   root extract", "hu zhang hydroethanolic extract", "Reynoutria japonica root extract") were
   aliases of the resveratrol compound (form "resveratrol (unspecified)"), so the DSLD group "Hu
   Zhang" turned knotweed rows into resveratrol. Hu Zhang is the root and rhizome of Polygonum
   cuspidatum (PMID 33388645), so they moved to botanical `japanese_knotweed`. BioVin stays grape.
2. **Constituent route (existing marker owner).**
   - `botanical_marker_contributions.json`: new `grape` → resveratrol entry (standardization_required,
     PMID 12926863: trans-resveratrol measured in red wine, grape skins and byproducts); knotweed's
     gate lowered from 50% to the same 1% (any declared percentage).
   - `_compute_delivers_markers` reads the row's printed note ("5% Trans-Resveratrol"), and records
     `declared_standardization_pct`.
   - `_derived_marker_interaction_rows`: a declared percentage on a row with no amount of its own,
     or on a blend header, still declares the marker; its analysis-only row carries no amount.
3. **RULE_IQM_RESVERATROL_BLEEDING copy** (bleeding disorders, anticoagulants, antiplatelets):
   states that whether supplement amounts matter in people is uncertain; no "monitor INR", no
   "dose may need reduction", no "limit dose", no mg cutoff. Severity, materiality (presence),
   sources and gates unchanged. Sources verified by content: MSKCC resveratrol page (in vitro
   platelet inhibition, clinical relevance not established; blood-thinner precaution), PMID
   26947597 = PMC5090816 (mouse warfarin study, correctly described as mouse), PMID 24563374
   (pregnant nonhuman primates). `verify_interaction_rules_citations.py --strict`: PASS.
4. **ADR-0005**: status "Accepted with amendment (Sean, 2026-10-19)", amendment text, implementation
   notes; the generic guard stays for other pairs (cod liver oil).

No resveratrol or knotweed entry exists in `curated_interactions/` (checked all three files).

## Knotweed → resveratrol relationship (audit follow-up, October 20, 2026)

Sean's amendment calls for a source-qualified relationship from knotweed itself, not one that
depends on a declared percentage. It lives in
`identity/interaction.py::BOTANICAL_CONSTITUENT_SOURCE` (`japanese_knotweed` → IQM `resveratrol`),
for interaction lookup only; scoring still credits resveratrol only through a declared percentage
(the marker route). Sources, read by content:
- PMID 30901974: Hu Zhang rhizome is "one of the richest natural sources of resveratrol".
- PMID 33388645: resveratrol is among its five major quantified constituents.
- PMID 16830819: resveratrol is highest in root and rhizome (~0.4%).

Grape stays linked only by a declared percentage, the standard its evidence supports.

## Replay

Every raw label mentioning resveratrol, knotweed, Hu Zhang, Polygonum cuspidatum or BioVin, every
label whose row notes name a marker keyword, and 200 controls (1,478 labels). Base main 3d7fe8adf
vs this branch, `--full --blob`. Records: `~/pg_quality/lostsubj_pr199_20261020/`
(`base_rv.jsonl`, `cand_rv.jsonl`, `fulldiff_rv.out`).

- **Rules added (11):**
  - RULE_INGREDIENT_CURCUMIN ×6, on turmeric rows whose notes declare 95% curcuminoids: 1851,
    3514, 16374, 69625, 82607, 228978.
  - RULE_IQM_RESVERATROL_BLEEDING ×5: BioVin 269265, 302705; knotweed declaring 50% (251683) and
    98% (232731); knotweed + grape header declaring 35% (2502).
- **Rules removed: 0.** The 13 Alive! multivitamins with undeclared "Japanese Knotweed Root
  Extract", and 58854 DHEA Complete, keep the qualified advisory through the knotweed
  relationship.
- **Reworded:** the qualified advisory text on every product carrying the resveratrol rule.
- **0 score changes, 0 product_safety_status changes.**
- Merged main 3d7fe8adf; the IQM conflict was re-applied with `data_batch.py check`.
- Slow file `test_clean_unmapped_alias_regressions.py` (BioVin → Grape pin), run by name: pass.
  No other SLOW_TEST_FILES entry pins BioVin, cabbage palm, wheatgrass or green bell pepper.
