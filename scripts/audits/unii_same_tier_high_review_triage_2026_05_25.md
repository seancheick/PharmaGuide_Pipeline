# UNII Same-Tier High-Review Triage

Generated: 2026-05-25

Source report:

- `scripts/audits/unii_same_tier_conflicts_2026_05_25.json`
- `scripts/audits/unii_same_tier_conflicts_2026_05_25.md`

## Scope

This is a report-only triage of the `41` `high_review` groups from the UNII
same-tier scanner. No reference data was changed.

The scanner already separates runtime-equivalent warning groups into:

- `152` info-level IQM parent/form self-duplicates
- `16` ordinary review groups
- `41` high-review groups

This file classifies the `41` high-review groups into data-model buckets so the
next pass can make small, defensible fixes instead of broad UNII rewrites.

## Triage Summary

| Bucket | Count | Risk | Recommended next action |
|---|---:|---|---|
| Policy / safety-tier overlay carrying a compound UNII | 1 | High | Fix first; umbrella policy entries should not masquerade as one compound unless intentionally exact. |
| Safety/allergen inherited synonym groups | 3 | Low-medium | Likely exonerate/suppress after confirming names are same allergen source. |
| IQM cross-parent structural duplicates | 2 | High | Fix or explicitly exonerate; these can alter active parent routing. |
| Botanical / standardized same-source variants | 24 | Medium | Build a structured exoneration relationship (`base_botanical`, `standardized_extract`, `branded_extract`) before suppressing runtime warnings. |
| Flavor / food-source derivatives | 8 | Medium-high | Verify individually; flavors/purees/powders may not be the same ingredient identity despite sharing source UNII. |
| Excipient brand/synonym variants | 3 | Medium | Most likely exoneration candidates, but verify compound-vs-mixture boundaries. |

## Fix Order

1. **P0: Policy/safety + IQM structural duplicates**
   - `88XHZ13131` synthetic food acids vs fumaric acid
   - `6DU9Y533FA` vanadium / vanadyl sulfate cross-parent
   - `L11K75P92J` calcium / dicalcium phosphate cross-parent

2. **P1: Flavor / food-source derivatives**
   - These are most likely to produce wrong user-facing identity if blindly
     exonerated. They need per-entry source validation.

3. **P2: Botanical/standardized source variants**
   - Mostly expected same-source modeling. Do not remove UNIIs reflexively.
     Add a structured exoneration model first.

4. **P3: Safety/allergen inherited synonym groups + excipient brand synonyms**
   - Likely low-risk suppress/exonerate candidates after lightweight review.

## P0 Findings

### `88XHZ13131` — policy watchlist vs compound

Records:

- `banned_recalled_ingredients.json` → `BANNED_ADD_SYNTHETIC_FOOD_ACIDS` (`Policy Watchlist: Synthetic Food Acids`)
- `other_ingredients.json` → `OI_FUMARIC_ACID` (`Fumaric Acid`)

Assessment:

- This is the highest-risk modeling smell in the set.
- A policy umbrella entry should not carry a single compound UNII unless the
  policy is intentionally scoped to that exact compound.
- Runtime first-write at tier 1 means the UNII can resolve to the policy label
  instead of the concrete compound.

Recommended next action:

- Inspect `BANNED_ADD_SYNTHETIC_FOOD_ACIDS` and decide whether it is a broad
  policy umbrella or an exact fumaric-acid entry.
- If broad, remove or replace the UNII with a note explaining why the umbrella
  has no exact UNII.
- If exact, rename/scope the policy entry so it is not a misleading category.

### `6DU9Y533FA` — vanadium / vanadyl sulfate cross-parent

Records:

- `ingredient_quality_map.json` → `vanadium.forms[vanadyl sulfate]`
- `ingredient_quality_map.json` → `vanadyl_sulfate`

Assessment:

- True IQM structural duplicate: the same UNII exists both as a form under
  `vanadium` and as its own parent.
- This is not just warning noise; it can decide which active parent wins.

Recommended next action:

- Decide whether `vanadyl_sulfate` should remain a standalone parent or only a
  form of `vanadium`.
- Test-first data cleanup once the modeling decision is made.

### `L11K75P92J` — calcium / dicalcium phosphate cross-parent + filler

Records:

- `ingredient_quality_map.json` → `calcium.forms[dicalcium phosphate]`
- `ingredient_quality_map.json` → `dicalcium_phosphate`
- `other_ingredients.json` → `PII_DICALCIUM_PHOSPHATE`

Assessment:

- Same chemical identity is modeled as active calcium form, standalone IQM
  parent, and inactive filler.
- This likely needs context routing rather than a single global deletion:
  dicalcium phosphate can be an active mineral source or an excipient.

Recommended next action:

- Keep the active-mineral path and inactive-filler path distinct by context.
- Do not remove the filler entry blindly; make the rule explicit.

## Safety / Allergen Inherited Synonym Groups

These groups appear high-review because their effective runtime tier is
allergen/safety. They look like same-source or same-allergen identity variants.

| UNII | Records | Initial disposition |
|---|---|---|
| `3C3Y389JBU` | `wheatgrass_powder`, `wheatgrass` | Likely exonerate: powder vs base wheatgrass. |
| `48268V50D5` | `casein`, `PII_MICELLAR_CASEIN` | Likely exonerate: micellar casein is casein context. |
| `86507VZR9K` | `barley_grass`, `barley_grass_powder` | Likely exonerate: powder vs base barley grass. |

Recommended next action:

- Add these to an exoneration/suppression model only after confirming the
  runtime payload is the desired safety/allergen payload.

## Botanical / Standardized Same-Source Variants

These are likely the dominant source of noisy warnings. Most represent a base
botanical plus a standardized or branded extract that legitimately shares the
same source UNII.

Do **not** treat these as wrong identifiers by default. The better durable fix
is to model the relationship explicitly:

- `base_botanical`
- `standardized_extract`
- `branded_extract`
- `plant_part_or_preparation`

| UNII | Records | Initial disposition |
|---|---|---|
| `11MSQ4JG7G` | `himematsutake`, `agaricus_blazei` | Same-source mushroom naming; exoneration candidate. |
| `1A64QN2D2F` | `shiitake_mushroom`, `shiitake` | Same-source naming; exoneration candidate. |
| `1L29G6428X` | `tart_cherry_fruit`, `tart_cherry` | Same-source fruit/base; exoneration candidate. |
| `31T0FF0472` | `astaxanthin_haematococcus_pluvialis`, `astazine` | Branded/source variant; exoneration candidate. |
| `3S5ITS5ULN` | `rhodiola_rosea_root`, `rhodiola` | Plant-part/base; exoneration candidate. |
| `46AM2VJ0AW` | `acai_berry`, `acai` | Same-source fruit/base; exoneration candidate. |
| `654825W09Z` | `fenugreek_seed`, `fenugreek` | Plant-part/base; exoneration candidate. |
| `714783Y9Z0` | `danshen`, `salvia_miltiorrhiza` | Common name/Latin name; exoneration candidate. |
| `HP7119212T` | `maca_root`, `maca` | Plant-part/base; exoneration candidate. |
| `J617U5X7NN` | `cordyceps_mushroom_powder`, `cordyceps_militaris` | Preparation/species; exoneration candidate after species check. |
| `KM66971LVF` | `black_pepper`, `NHA_BLACK_PEPPER_EXTRACT`, `black_pepper_extract` | Base/extract/branded-functional overlap; exoneration candidate, but scoring context matters. |
| `QI7G114Y98` | `echinacea_purpurea_aerial`, `echinacea_purpurea` | Plant-part/base; exoneration candidate. |
| `SCJ765569P` | `holy_basil_leaf`, `holy_basil` | Plant-part/base; exoneration candidate. |
| `V038D626IF` | `ashwagandha_root`, `ashwagandha`, `ksm_66_ashwagandha` | Base/branded extract; exoneration candidate with branded-form routing preserved. |
| `XDD2WEC9L5` | `acerola_cherry`, `NHA_WEST_INDIAN_CHERRY` | Common-name synonym; exoneration candidate. |
| `Y8P1YR4920` | `shatavari_root`, `shatavari` | Plant-part/base; exoneration candidate. |
| `0MVO31Q3QS` | `cran_max`, `flowens`, `pacran` | Branded cranberry variants; exoneration candidate, but brand-specific routing matters. |
| `597E9BI3Z3` | `burdock_root_powder`, `burdock_root` | Preparation/base; exoneration candidate. |
| `KYV09BQ2YN` | `suma_root`, `suma` | Plant-part/base; exoneration candidate. |
| `MN25R0HH5A` | `white_mulberry`, `mulberry` | Species/common-name scope needs verification. |
| `7UI036LFRJ` | `caralluma`, `caralluma_fimbriata` | Common/species naming; exoneration candidate. |
| `BIA2SO6F5B` | `galega_officinalis`, `goats_rue` | Latin/common-name synonym; exoneration candidate. |
| `JC71GJ1F3L` | `myrrh_resin`, `myrrh_resin_extract` | Preparation/base; exoneration candidate. |

Recommended next action:

- Build a first-class UNII exoneration table or extend the existing UNII
  allowlist so the runtime warning can be suppressed only for reviewed
  relationships.
- Keep branded-form routing tests around KSM-66, cranberry brands, black pepper
  extract, and astaxanthin brands before suppressing.

## Flavor / Food-Source Derivatives

These should not be blanket-exonerated. A flavor, puree, powder, or broad
fruit/vegetable blend can share a source UNII while serving a different label
role.

| UNII | Records | Initial disposition |
|---|---|---|
| `4J2TY8Y81V` | `strawberry`, `NHA_STRAWBERRY_PUREE`, `OI_NATURAL_STRAWBERRY_FLAVOR` | Verify; flavor may not be equivalent to fruit/puree. |
| `5EVU04N5QU` | `NHA_ORANGE_CRYSTALS`, `NHA_ORANGE_FLAVOR` | Verify; flavor/crystals role distinction. |
| `5MG5Z946UO` | `carob`, `OI_CAROB_CARAMEL`, `PII_CAROB_STJOHNS_BREAD` | Verify; mixed carob/caramel entry is suspicious. |
| `6PQP1V1B6O` | `NHA_ANNATTO_VARIANTS`, `NHA_FRUIT_VEG_POWDERS`, `OI_ANNATTO_EXTRACT` | Verify; `Fruit & Vegetable Powders` carrying annatto UNII is suspicious. |
| `B423VGH5S9` | `NHA_APPLE_PUREE_CONCENTRATE`, `NHA_NATURAL_APPLE_FLAVOR`, `PII_APPLE_FLAVOR` | Verify; flavor vs puree identity distinction. |
| `TJR6B3R47P` | `millet`, `PII_MILLET_FLOUR` | Likely exonerate but verify food-source context. |
| `Y9H1V576FH` | `PII_HONEY`, `PII_HONEY_FLAVOR` | Verify; flavor is not necessarily honey ingredient. |
| `XDD2WEC9L5` | `acerola_cherry`, `NHA_WEST_INDIAN_CHERRY` | Also listed above as common-name synonym; likely lower risk than flavor entries. |

Recommended next action:

- Triage these with FDA UNII cache + DSLD examples before any suppression.
- Treat `NHA_FRUIT_VEG_POWDERS` and flavor entries as highest priority within
  this bucket.

## Excipient Brand / Synonym Variants

| UNII | Records | Initial disposition |
|---|---|---|
| `230OU9XXE4` | `NHA_MONO_DIGLYCERIDES`, `PII_GLYCEROL_MONOSTEARATE` | Verify compound-vs-mixture boundary. |
| `3OWL53L36A` | `PII_PARTECK`, `PII_PEARLITOL` | Likely branded mannitol variants; exoneration candidate. |
| `C4YAD5F5G6` | `PII_GLYCEROL_MONOOLEATE`, `PII_GLYCERYL_MONOOLEATE` | Likely synonym; exoneration/merge candidate. |
| `E89I1637KE` | `NHA_PARTIALLY_HYDROLYZED_GUAR_GUM`, `OI_GUAR_GUM` | Verify; partially hydrolyzed form may need distinct context. |
| `FZ989GH94E` | `NHA_PVP`, `PII_KOLLIDON` | Likely branded PVP; exoneration candidate. |

Recommended next action:

- Split true synonyms/brands from mixture-vs-specific-compound differences.
- Exonerate brand synonyms only after FDA-cache name verification.

## Proposed Next Slice

**Slice 1: P0 data-model cleanup plan, no data edit yet.**

Inputs:

- `88XHZ13131`
- `6DU9Y533FA`
- `L11K75P92J`

Deliverable:

- One short spec deciding the data model for each group.
- API verification for the exact UNIIs involved.
- TDD plan for any data edit.

Why first:

- These are the only groups where the scanner strongly suggests an actual
  parent/routing or policy-scope defect rather than a normal source-form
  relationship.

**Slice 2: UNII exoneration model for source-form relationships.**

Deliverable:

- Structured allowlist entries with relationship type and reviewer rationale.
- Runtime-warning suppression only when the `(UNII, tier, involved entry ids)`
  matches the reviewed relationship.

Why second:

- It removes most warning noise without deleting correct identifiers.

**Slice 3: Food/flavor derivative verification.**

Deliverable:

- Per-entry verify/fix decisions for flavor, puree, crystal, powder, and
  broad-source entries.

Why third:

- These have higher ambiguity than botanical base/extract relationships and
  need real examples before cleanup.
