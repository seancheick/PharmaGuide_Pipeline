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
   under "Capsicum", Lactococcus cremoris stays L. cremoris, Olive leaf extract stays olive leaf.
   The group still decides when:
   - the printed name names the group's identity, as an alias or in so many words ("Vitamin E"
     first matched to its sunflower-oil source; "Neutral Protease" under "Protease"; "Ginger root
     extract" under "Ginger", whose IQM entry is the scoring identity);
   - the label proves neither identity;
   - the group's identity is a registered child (a refinement);
   - the supplied identity is a role or catch-all record (other ingredients, proprietary blends:
     natural colors, a fruit-and-vegetable powder record, an enzyme blend), or either side is the
     general blend owner ("Proprietary Blend" is a row role, so TamaFlex stays a blend);
   - keeping the label identity would drop an interaction rule the group's identity answers to
     (printed "Japanese Knotweed root extract" under "Hu Zhang" keeps resveratrol and its bleeding
     rule; cod liver oil keeps fish oil). Those identities need a reviewed interaction link before
     they can be corrected.
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

The display ledger keeps two identities per row: `canonical_id` is the printed (cleaner) identity
and `analysis.canonical_id` is the enricher's. Collapsing the row onto the enricher's identity was
not done here. The app's id set (`product_canonical_ids.dart::canonicalIdsForProduct`) unions the
core columns `key_ingredient_tags` and `ingredient_fingerprint` with the blob's ingredients, active
ledger rows and IQD ids, and the core columns already carry the spellings that matter (18219:
`["st_john_s_wort","st_johns_wort"]`; 12800's fingerprint includes caffeine). So collapsing the
ledger would not by itself drop those subjects from the app; an earlier blob-only count in this
branch overstated that. The real safety gap is on the pipeline side: profile warnings come only
from rule ids, and rows the enricher leaves unresolved for scoring reasons (blend headers such as
Ravage 1179 "Caffeine Blend", nested rows under non-therapeutic parents) fire no rule. That fix is
owned by the separate lost-safety-subjects lane and builds on this branch.

## Follow-up: which row object each consumer reads

The single field every consumer must read is the enricher's `ingredient_quality_data` row
`canonical_id` (projected to blob `ingredients[].canonical_id`). A key-name census (architecture
audit, 2026-10-19: `canonical_id` appears in 45 files outside the cleaner, `standardName` in 18)
does not show which of those read the cleaner's `activeIngredients` row rather than IQD rows, UL
flags or scoring-input rows (e.g. `scoring_v4/dose_safety.py` reads flag and scoring-row ids).
A row-object census, then routing any cleaner-row reader onto the IQD identity, is a separate
measured batch; this ADR's rule makes the two agree on the 2,311 rows where they diverged
wrongly.

## Rejected

- Moving identity ownership to the cleaner (the matrix and every consumer already follow the
  enricher; the cleaner lacks the IQM/form context the enricher uses).
- Treating every rewrite as a defect: most part/registry refinements and repairs are correct.
- Ingredient-specific exceptions for each wrong pair.
