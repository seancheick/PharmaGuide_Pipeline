# Evidence completion inventory

Baseline: `880b17a7`. This is a registry/state inventory, not a fresh
product-exposure count. The committed enriched corpus is not current enough to
support current affected-product counts; those come from the final clean corpus
pass.

## Completion state

- Research-required registry queue: **0**. All 754 literature records satisfy
  the resolver provenance gate (753 PubMed-verified; one identity-only
  classification).
- Probiotics: 132 strains, no unreviewed evidence levels, no identity-verified
  strain missing a literature review, and all 157 study contexts clinician
  approved. The 78 reviewed-zero strains are terminal determinations: 50
  combination-only, 26 no human research found, two uncontrolled-only.
- Omega: six reviewed purpose records. Three feed scoring; preterm-birth,
  depression and atrial-fibrillation contexts remain explicit non-scoring
  research records.
- The eight closure fixtures resolve completely. Tesnor reaches reviewed
  trials; Sytrinol is reviewed with the current amount judgment still attached
  pending the Evidence→Dose transfer.
- Seven September 28 formula records have bounded no-qualifying-trial searches:
  anabolic muscle primer, muscle buffering system, thermo energy matrix,
  organic golden milk blend, organic USA farmed green juice blend, raw organic
  sprout and fiber blend, and raw fitbiotic blend.
- 249 verified records are applicability-unestablished: 234 have no qualifying
  study; 15 preserve research that cannot transfer across form, preparation,
  drug, or combination boundaries.
- 24 verified identity-material-unresolved records remain terminal holds until
  better label identity appears. They are not a literature search queue.
- 153 records correctly use `no_qualifying_human_evidence`.

## Correctness defect found by the inventory — resolved

Twelve completed reviews used obsolete `effect_direction:
no_qualifying_evidence`, while the resolver recognizes the canonical registry
states. Current code consequently misreported them as reviewed applicable
evidence. The affected canonicals were arugula,
oi_guar_gum, carob, oleanolic_acid, buchu_leaf, goldenrod, lima_bean,
nha_total_terpene_lactones, oi_galactose, pediococcus_pentosaceus,
sweet_clover and withaferin_a.

Resolved in `3900e66a5`, `8e4b4605` and `6202b374`: ten bounded searches now
use `no_qualifying_human_evidence`; the Ginkgo analytical-marker record keeps
its stronger `identity_material_unresolved` lock; and isolated withaferin A
keeps `applicability_unestablished`. Production-boundary regressions cover all
twelve and a full-registry census forbids the obsolete token. No resolver alias
or second accepted spelling was added.

The registry metadata now records 754 verified records and the canonical
`data_batch` workflow updated `last_updated`. The landed batch check reports
exactly the twelve expected record changes and zero problems. Related tests:
279 passed, with the separate Ravage cinnamon expected failure unchanged.
