# Approved-submission inactive identity review — 2026-10-22

Behavioral batch; Sean authorized correcting the mappings and integrating to main.
No new scoring policy, clinical efficacy claim or identifier. Reviewed label payloads
remain unchanged. Private approvals/photos and frozen comparison records stay outside
the public repository at `~/pg_quality/submission_mapping_20261022/`.

Owner: `enhanced_normalizer.py::EnhancedDSLDNormalizer._process_other_ingredients_enhanced`,
`_map_inactive_name_prefer_other`, `_has_curated_other_ingredient_identity` and
`other_ingredients.json` — evidence: source matrix, glossary and `rg` for disclosure,
other-ingredient identity, forms expansion and all corrected names.
Will NOT create: a parallel parser/normalizer, registry, public field or numerical policy.

## Per-entry receipts

Sources below were opened and content-checked on 2026-10-22. These are source-derived
mixtures/preparations; no single-compound CID or new clinical identifier is asserted.
Existing identifiers and their prior claims are unchanged.

- **PII_HPMC:** add `veggie capsule hypromellose` with the chemistry retained.
  [Capsugel Vcaps Plus](https://www.capsugel.com/pharmaceutical-solutions/hard-empty-capsules/vcap-plus-hpmc-capsules)
  identifies the capsule material as HPMC; its [technical explanation](https://www.capsugel.com/knowledge-center/pharma/capsules/vcaps-plus-capsules)
  identifies hypromellose as HPMC. The actual approved label explicitly says hypromellose.
  [Plantcaps](https://www.capsugel.com/pharmaceutical-solutions/hard-empty-capsules/plantcaps-capsules)
  uses pullulan: generic vegetarian wording cannot establish HPMC. A parenthesized
  alias would be normalized to the generic words; use the shared literal-key lookup
  instead. Regression: bare `veggie capsule` remains unmapped.
- **NHA_RICE_BRAN_EXTRACT:** remove aliases naming hulls, flour, starch, the ambiguous
  typo `rice flower`, and generic rice extracts already owned by Rice Extract Blend.
  True bran aliases remain. No replacement asserted for the typo. Removing the
  `rice hull extract` false bran alias allows the existing part-aware fallback to
  resolve Rice Husk; no new extract-composition claim or hull-extract alias is added.
- **OI_RICE_HUSK:** `organic rice hulls` and Nu-FLOW now resolve here.
  [RIBUS](https://ribus.com/nu-flow/) identifies Nu-FLOW as rice hull material and
  recommends Rice Hulls/Rice Fiber labeling. This supports hull identity, not bran.
- **PII_RICE_FLOUR:** `certified organic rice flour` moves here.
  [BENEO organic products](https://www.beneo.com/solution-finder?_key_benefits=organic)
  distinguishes organic rice flour (Remyflo) from rice starch (Remy). Organic status
  does not change the named grain preparation.
- **PII_RICE_STARCH:** `pregelatinized rice starch` moves here.
  [BENEO rice starch](https://www.beneo.com/human-nutrition/human-nutrition-products/specialty-rice-ingredients/rice-starches)
  explicitly describes pregelatinised rice starch. It is not bran or flour.
- **NHA_STARCH_MODIFIED:** remove `pea starch`. The source plant alone does not
  establish chemical modification. Existing modified-starch aliases remain.
- **PII_PEA_STARCH:** precise source-specific inactive entry; organic and plain pea
  starch aliases, with modification/preparation left unspecified.
  [Roquette resources](https://www.roquette.com/media-center/resources/food_brochure)
  describes pea starch N-735 as native starch extracted from yellow peas with water.
  This disproves an automatic modified-starch interpretation; no particular supplier
  or preparation is assigned to the submitted product.
- **PII_OAT_FIBER:** precise inactive entry replaces generic-oat fallback for this name.
  [JRS oat fiber](https://www.jrs.eu/en/food-ingredients/products/vitacel-oat-fiber.php)
  describes oat-derived cell-wall fiber, distinct from whole grain or oat bran.
  No beta-glucan concentration, efficacy, amount or gluten-free status is inferred.
  Existing oat allergen recognition remains independent and retained.

## Parser and consumer review

The shared disclosure parser retains raw text. The cleaner expands only undosed,
unstructured inactive rows. All top-level conjunction parts must have curated
identities; whole curated names, unknown halves and malformed grouping remain intact.
Explicit blend lists expose every printed member, including unknown members. Ordinary
parenthesized source/form descriptions are not lists. Existing forms expansion owns
derived child paths; the original disclosure remains the structural display parent.
Structured quantities/forms/nested rows are never copied across new components.

Independent review reproduced and corrected display-ledger deduplication of children
sharing a source path, then identified recognition/mapping disagreement on parenthetical
capsule chemistry. Regressions cover both seams and the generic-capsule negative control.

Validation and integration results are recorded in the existing pending-items LEDGER.
Full-corpus regeneration and catalog/app release acceptance remain separate work.

## Measured result

At source `aec0088a`, 70 frozen raw labels were replayed through Clean, Enrich and
Score against `fa6fb2495`. The set covers all five current approved submissions,
65 native affected candidates/controls, and includes three unaffected control labels.
48 Clean/Enrich records change; 22 remain unchanged, including every control.
All five approvals have mapped active/inactive ingredients and canonical display
rows; creatine retains 20 kcal. The only numerical movement is NAC 66.3 to 65.8
from the existing microcrystalline-cellulose excipient deduction. No quality/safety
status changes or additive-signal losses occur. Native label 244301 also uses pea
starch in its active panel: its identity changes from Modified Starch to Pea Starch,
with its 50 g amount, role, numerical score and no-applicable-UL result preserved.
Source fingerprints prove the candidate remained fixed during capture.

All 114 existing stage manifests are stale (38 each Clean, Enrich and Score); the
next catalog regeneration must start at Clean. These source corrections do not
update the existing catalog, promote approvals or qualify an external release.
