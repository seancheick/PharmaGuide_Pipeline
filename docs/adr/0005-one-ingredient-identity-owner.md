# ADR-0005 — One ingredient-identity owner; the printed label beats a DSLD group

**Status:** PROPOSED (needs Sean's merge; branch `claude/upbeat-montalcini-ef2f53`)
**Date:** 2026-10-19
**Matrix concept:** `canonical_ingredient_id` (owner `scripts/enrich_supplements_v3.py`, deciding
through `scripts/identity_integrity.py::resolve_identity`)

## Decision

1. **One owner.** The enricher decides each label row's `canonical_id`. The cleaner's
   `canonical_id` (`scripts/enhanced_normalizer.py`) is an input the enricher may keep, refine to a
   registered child, or repair only on recorded evidence (`identity_disposition`,
   `canonical_id_before`, `identity_resolution_rationale`). Nothing downstream re-decides it.
2. **A DSLD `ingredientGroup` is a group, never more specific than its row.** When the printed name
   is an exact curated alias of the supplied identity (and the resolver reads it as nothing else),
   the group may not replace it with a different plant, species, plant part or preparation:
   organic Wheat Grass stays wheatgrass under "Couch Grass", Green Bell Pepper stays bell pepper
   under "Capsicum". The group still repairs when the printed name names the group's identity
   ("Vitamin E" first matched to its sunflower-oil source), when the label proves neither identity,
   and when it refines to a registered child. "Proprietary Blend" is a row role, not a substance:
   the general blend owner is neither protected nor overridden by this rule (TamaFlex stays a blend).
3. **A curated alias is evidence, so a wrong alias is a data defect**, fixed through `/data-fix`
   (first batch: diacetylactis, ElevATP, olive juice extract, sweet wormwood).
4. **Export carries the owner's decision.** Detail-blob `ingredients[].canonical_id` is the
   enricher's identity, including "unresolved" (`is_mapped: false`); the cleaner's id never refills
   it. The display ledger keeps its documented split: the row's `canonical_id` is the printed
   identity and `analysis.canonical_id` is the enricher's (see Open decision).
5. **A gate proves the line on every build.** `scripts/audit_raw_to_final.py --all` runs in
   `rebuild_dashboard_snapshot.sh` (and so in release): every raw DSLD row has a ledger entry, no
   ledger or exported row points at a row the label lacks, ledger names equal the raw text, exported
   identity equals the enricher's, and a changed amount or unit carries the cleaner's recorded
   reason (selected serving column, reviewer-signed correction, or %DV dose correction).

## Context

Line integrity audit, October 19, 2026 (`reports/line_integrity_audit_20261019/`, measured on the
951a05415 full capture): row accounting was perfect, but identity was decided twice and 2,311
rows were rewritten from an identity the printed label names to the DSLD group's (189 green bell
pepper → chili, 70 wheatgrass → couch grass, 34 L. cremoris → L. lactis, 42 ginger extract →
ginger; Olive leaf extract → olive fruit extract dropped its interaction rule). The precedence came
from commit 9f0daf180 (July 13, "rank declared taxonomy above aliases"), which recorded no rationale.
Measurements and receipts: `reports/identity_line_20261019/research.md`.

## Consequences

- Blend children are interaction subjects (decision D1), so these identities move warnings; every
  changed interaction outcome is reviewed with the replay measurement before merge.
- A curated alias now decides more rows; alias errors surface as identity errors and go to
  `/data-fix`, not to a new matcher exception.
- The snapshot needs the raw DSLD root (`dataset_paths.brand_dataset_root`, exported by
  `batch_run_all_datasets.sh`); without it the line gate fails closed.

## Open decision (Sean)

The app builds its stack-interaction and safety-alert id set from the union of blob `ingredients`,
active `display_ingredients` rows and IQD ids (`product_canonical_ids.dart`). The ledger row's
printed identity therefore reaches the app even where the enricher left a row unresolved
(e.g. a "Caffeine Blend" header). Making the ledger row carry only the enricher's identity would
remove interaction-rule subjects from that app set (951 capture: St John's wort in 2 products,
caffeine 3, L-arginine 27, among others), so it was not changed here.

## Rejected

- Moving identity ownership to the cleaner (the matrix and every consumer already follow the
  enricher; the cleaner lacks the IQM/form context the enricher uses).
- Treating every rewrite as a defect: most part/registry refinements and repairs are correct.
- Ingredient-specific exceptions for each wrong pair.
