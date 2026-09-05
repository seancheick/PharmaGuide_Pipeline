# Source-owned structural totals and primary mass dominance — 2026-09-05

## Defect (handoff §5)

`test_ps_complex_total_does_not_dilute_its_only_evidenced_active` was RED at
checkpoint `dcd38005` (1 failed / 175 passed across the seven-file focused set).
DSLD 213475 declares 100 mg phosphatidylserine inside a 500 mg SerinAid complex.
The evidence match links to the real child row, but the primary evidence floor
was 0 with the complex present and 18 without it.

Root cause, traced in production code: `_active_mass_index` in
`scoring_v4/modules/generic_evidence.py` took the heaviest mass over every
scoring row, including `product_level_evidence` structural totals. The 500 mg
header set the maximum, so the 0.5 primary-mass fraction demanded 250 mg and
the 100 mg child failed it. The real enriched label carries a third row as
well: the enricher's proprietary-blend projection at synthetic path
`activeIngredients[0]`, whose `linked_rows` name only that synthetic path even
though the blend record itself stores `source_row_ref: ingredientRows[1]`.

## Real source shapes (hash-verified public fixtures)

`cloud_source_lineage_fixtures.json` projection and source-batch SHA-256 were
re-verified before use (all three match).

- 213475 Nature's Way: `ingredientRows[1]` complex 500 mg (blend_header_total)
  owns `ingredientRows[1].nestedRows[0]` PS 100 mg; candidate scoring rows are
  the child, the identity-bearing header projection and the synthetic
  `activeIngredients[0]` projection (both 500 mg).
- 218600 Solgar: reverse hierarchy — PS 200 mg at `ingredientRows[2]` owns the
  supplying 1,000 mg complex at `ingredientRows[2].nestedRows[0]`. The cleaned
  label keeps that complex as a flat row whose path and `parentBlend` record the
  nesting; the enricher nests it.
- 218838 Solgar: 500 mg complex, 100 mg PS and 60 mg PC are flat siblings with
  no owner link anywhere in the source. No linkage is inferred from the shared
  canonical id; the total keeps competing and the case is an explicit
  unresolved source-lineage item (`test_real_218838_sibling_rows_without_owner_links_stay_unresolved`).

## One lineage decision, three consumers

`scoring_input_contract.primary_mass_competitor_rows(product, rows)` is the
single place that decides which rows compete for mass dominance:

- A `product_level_evidence` structural total is not a separate active when the
  source tree proves it is the physical source of, or the material supplying, a
  quantified label active: the label row is the same row, is nested under the
  total, or is the total's ancestor.
- Synthetic `activeIngredients[i]` provenance resolves through the product's
  actual tree (`_resolve_source_tree_path`); canonical or name similarity never
  creates lineage (`test_synthetic_projection_resolves_through_the_product_tree_not_identity`).
- An owned total leaves the competition only when mass-comparable label rows
  stand in for it: the linked active and every member of the total's own
  subtree must carry a comparable mass (`_role_mass_mg`). An undisclosed member
  (`nested_display_only`, quantity 0/NP) or one declared only in activity, CFU or
  IU units keeps the total competing as an opaque aggregate. No remainder is
  assigned to any child.
- Unlinked totals, row-level `label_active_projection` rows and totals without
  a mass-quantified linked active always compete. Rows are returned unchanged.

Reused rather than duplicated: the existing `.nestedRows[` ancestry predicate
(`_is_nested_under`, now delegating to `_path_is_nested_under`), the existing
active-tree walker hoisted out of `required_identity_conflicts` as
`_source_tree_rows`, and the contract's own mass parser `_role_mass_mg`.

Consumers in `generic_evidence.py`: `_active_mass_index` (primary floor and the
verified-primary-ingredient recovery threshold; every row is still indexed at
its real mass, only competitors set the maximum, and the competitor set is
derived from the same row list because projected rows are rebuilt on every
contract call), `_mass_dominant_essential_canonical` (nutrition-authority floor)
and `_has_primary_collagen_peptide_identity`.

Not changed: `profile_owner_candidate_rows`, which removes only fully
mass-reconciled projections from identity/profile owner selection. It answers
a different question with a different criterion; both express blend-projection
redundancy and are a candidate for later unification, listed below.

## Verification

- RED reproduced at checkpoint: `1 failed, 175 passed in 5.23s` (floor 0.0 vs 18.0).
- Expanded tests first (import RED), then implementation; the same file is now
  11 passed, including the real-label lineage cases, the partially disclosed
  blend, the stranger-tree resolution, the helper contract and the
  activity-unit stand-in refinement.
- Seven-file focused set plus every test touching the changed seams:
  **489 passed** (`test.sh fast`, 7.39 s).
- Real-label probes through the candidate enricher and production scorer:
  213475 60.8 → 75.9 (evidence 3.8 → 18.9), 218600 60.3 → 75.4 (3.8 → 18.9),
  218838 unchanged 61.5.

## Matched comparison on the affected population

Inventory scan over all 15,415 manifest-owned enriched products (read-only,
54 s): 647 products have a different competitor set under the helper. Dropped
row reasons: identity_bearing_blend_header_mass 680, ..._from_nested_child 652,
proprietary_blend_total_from_botanical_child 149, enzyme_activity_unit 115,
product_level_cfu 62, omega_epa_dha_aggregate 45, protein/EAA 6. Most of these
never set a mass maximum (activity, CFU, same-row duplicates), which is why the
harness comparison, not the scan, owns the numbers.

Targets: 774 = the 647 ∪ every product that lost or gained an evidence match in
`corpus_preparation_continuation_accepted.json` (excluding the prior zinc /
beta-carotene scoping) ∪ the handoff §6 IDs. Both runs used the same inputs,
targets and authenticated baseline, full re-enrichment of every target, and the
same harness; only `--implementation-root` differed.

| Run | Implementation | Report | SHA-256 |
| --- | --- | --- | --- |
| A control | detached worktree at `dcd38005` | `corpus_source_ownership_control_dcd38005_targets.json` | `0887cbcd766e7535c8cd6f7529207d52a1b6dd7f9cbbc7fbc9a3c0d73205a38f` |
| B1 candidate (before refinement) | feature worktree | `corpus_source_ownership_candidate_targets.json` | `507c547d1f1ebc2830693314e161f1756dd9097fe28dff5f6255f5c513a827ea` |
| B2 candidate (final) | feature worktree | `corpus_source_ownership_candidate_targets_v2.json` | `48ea3765cf7a8ae2d9c9cafae6223766e1eabb011fcf6572f095ebb8f3dc71ca` |

A → B2 over 774 products: 55 candidate records differ, 40 with a score change,
all upward (+0.7 to +15.1), evidence pillar only; 0 status, module, route,
confidence or matched-evidence-set changes; 11 tier and 3 verdict changes;
generic 35, sports 5. The other 15 differ only in pillar reason text.

B1 → B2 (the activity-unit refinement) reverted exactly three products:
Wobenzym N 29499 (69.8 → 63.6) and MegaZymes 43649/43650 (69.1 → 65.3). Their
"Pancreatin 300 mg" style headers have only activity-unit children, so nothing
mass-comparable stands in for the 300 mg and the header must keep competing.

Reviewed by cause (every changed product inspected through candidate detail):
header-owned single actives (PS, quercetin, curcumin/turmeric, tocotrienols,
ashwagandha in reconciled blends); multi-blend sports formulas where the
heaviest *active* (e.g. 5 g creatine or leucine) now sets the maximum instead
of a 10–12 g marketing-blend header; MEGA 3/6/9 oil blends where the 1,440 mg
omega-3 child is the heaviest disclosed active. These follow the existing
0.5-fraction rule as written; none introduces a new match, dose or weight.

## Findings for review (not changed here)

1. **Brand scope of BRAND_PHOSPHATIDYLSERINE.** Level `branded-rct`, aliases
   `serinaid` and `phosphatidylserine`; its own notes say the evidence is
   ingredient-level. Live PubMed titles: PMID 20523044 is a PS-DHA trial, PMID
   21103034 is soybean-derived PS; neither is SerinAid-specific. The branded
   floor tier (18 rather than 14) therefore reaches Solgar 218600 exactly as it
   already reached un-nested generic PS labels before this fix. A registry scan
   finds 15 of 56 branded entries carrying a generic alias (astareal/
   astaxanthin, quatrefolic/methylfolate, optiferrin/lactoferrin, cognizin/
   citicoline, suntheanine/l-theanine, optimsm/msm, bioperine/piperine,
   magtein, sunfiber/phgg, hmb, lj100/eurycoma, relora, uc-ii, biocell, the PS
   entry). This is a clinical/policy disposition (branded-vs-generic tier), not
   an engineering fix; no bulk alias or id change was made.
2. `scoring_v4/modules/sports.py` and `fiber_digestive.py` pass
   `apply_primary_floor=True`; the `score_evidence` docstring says only the
   generic module does. The five sports changes above follow from that
   pre-existing opt-in.
3. Bio-Quercetin 325831 (10 mg quercetin phytosome) receives an 11.9 floor: the
   floor has no dose gate when the registry entry lacks `min_clinical_dose`
   (pre-existing fail-open; see memory on v4 no-reference doses).
4. 17186 Nature's Bounty: a "Glucosamine Chondroitin Complex 3,500 mg" header
   whose constituents are DSLD `forms` (no nested rows) projects as a 3,500 mg
   `vitamin_c` identity-bearing total (dose 18.2/20, evidence via the essential
   authority floor). Pre-existing, unchanged by this fix, and safety-relevant:
   a multi-constituent form header must not anchor to one constituent.
5. Two mass parsers exist: `botanical_profile._mass_mg` (blank unit → mg) and
   `scoring_input_contract._role_mass_mg` (blank unit → None). The helper uses
   the contract's.
6. 218838 sibling lineage stays unresolved until the source proves ownership.

## Concurrent cloud branch (`origin/claude/probiotic-evidence-audit-1xp12h`)

A cloud continuation started from the same checkpoint and pushed two commits
while this local continuation was in progress. Its `79b37e35` fixes the same
defect with a per-entry competing-mass calculation inside
`generic_evidence.py` (`_row_physical_source_refs`, `_same_physical_source`,
`_competing_active_mass`), applied to the primary floor and the
verified-primary recovery only. Neither branch reverts the other; the feature
branch remote was still at `dcd38005` when this work was pushed.

Measured, same inputs and same real labels through each implementation:

| Label | checkpoint `dcd38005` | cloud `19ebfbbf` | this branch |
| --- | --- | --- | --- |
| 213475 Nature's Way PS 100 mg | 60.8 (floor 0) | 60.8 (floor 0) | 75.9 (floor 18) |
| 218600 Solgar PS 200 mg | 60.3 (floor 0) | 75.4 (floor 18) | 75.4 (floor 18) |
| 218838 Solgar PS Complex | 61.5 (floor 0) | 61.5 (floor 0) | 61.5 (floor 0) |

The cloud rule assumes the synthetic proprietary-blend projection's
`linked_rows` reach the original tree; on the real enriched label they contain
only `activeIngredients[0]`, so that 500 mg row keeps competing and the
handoff's primary defect remains on the real product. Its own nine test cases
(reverse hierarchy, sibling non-linkage, owned sibling constituent, synthetic
links through/not through the tree, the three aggregate locks) all pass
unchanged against this branch's implementation (`9 passed`). The cloud rule
also has no guard for undisclosed blend members or activity-unit stand-ins,
and does not reach `_mass_dominant_essential_canonical` or the collagen gate.

Its second commit `19ebfbbf` (source-required applicability terms ignore
enrichment-derived `forms` when `raw_taxonomy` is absent) is a small,
plausible tightening with two tests; it is compatible with the Ceylon scope
added here (which reads source taxonomy forms). It was not cherry-picked so
that the frozen full-corpus comparison stays attributable; recommended for
independent verification and adoption on the feature branch afterwards.
A third harness run of the cloud implementation on the same 774 targets is
recorded in the return package for side-by-side numbers.

Cloud run on the same 774 targets (`corpus_source_ownership_cloud_1xp12h_targets.json`,
SHA-256 `095e57ebe1af3b5779baf43401a65cf91d8b1584bfbadbeab3d9a3ca2361b11a`):
29 upward score changes versus the checkpoint, a strict subset of this
branch's 40. The 13 products only this branch changes are exactly the cases
where the enricher's synthetic `activeIngredients[i]` projection (213475,
Daily Energy, Daily Maca Plus) or a multi-header formula (Myopower, Anabolic
Sleep, Toco-Sorb) is involved. No product moves in opposite directions.
