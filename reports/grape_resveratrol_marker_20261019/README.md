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

## Replay

Every raw label mentioning resveratrol, knotweed, Hu Zhang, Polygonum cuspidatum or BioVin, every
label whose row notes name a marker keyword, and 200 controls (1,478), main 2e80642ca vs this
branch, `--full --blob`. Per-product list: `replay_changes.tsv`.

- **Rules added (11)**: RULE_INGREDIENT_CURCUMIN ×6 (turmeric rows whose notes declare 95%
  curcuminoids: 1851, 3514, 16374, 69625, 82607, 228978); RULE_IQM_RESVERATROL_BLEEDING ×5 (BioVin
  269265, 302705; knotweed declaring 50% 251683, 98% 232731; knotweed + grape header declaring 35%
  2502).
- **Rules removed (14)**: RULE_IQM_RESVERATROL_BLEEDING on 13 Alive! multivitamins whose
  "Japanese Knotweed Root Extract" (0 NP in a blend) declares no resveratrol, and 58854 DHEA
  Complete, whose header "Japanese Knotweed extract and whole Red Grape extract blend" declares
  35% trans-resveratrol but has no identity (header follow-up). **For Sean.**
- **Reworded (215)**: the qualified advisory text on every product carrying the resveratrol rule.
- **0 score changes, 0 product_safety_status changes.**
