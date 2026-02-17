# Alias Overlap Online Comparison + Action Plan

Generated: 2026-02-16

## Scope
- Full overlap list: `scripts/reports/alias_overlap_inventory.md`
- Total overlaps: 105
- Files with overlaps: `other_ingredients.json` (72), `standardized_botanicals.json` (18), `botanical_ingredients.json` (9), `backed_clinical_studies.json` (5), `rda_therapeutic_dosing.json` (1)

## Source-Backed Decisions (High Priority)

### 1) True synonym collisions: merge to one canonical alias owner
- `acacia gum` / `gum arabic` / `arabic gum` / `e414`:
  - Keep one canonical ingredient owner (`ACACIA`/`GUM ARABIC`) and remove duplicates from umbrella entries.
  - Source basis: FDA UNII ACACIA includes these synonyms and E-414 mappings.
- `hpmc` / `hypromellose`:
  - Keep on one HPMC chemical owner; remove from any capsule-form pseudo-entry unless context includes `capsule/shell`.
  - Source basis: FDA UNII Hypromellose maps HPMC + Hydroxypropyl methylcellulose naming.
- `carboxymethyl cellulose` / `cellulose gum` / `sodium carboxymethylcellulose` / `cmc`:
  - Consolidate under one sodium CMC owner; avoid duplicate alias ownership across multiple cellulose entries.
  - Source basis: FDA UNII CMC records show these as mapped synonyms.

### 2) Species-level botanical collisions: do not alias species token to cultivar-specific entry
- `brassica oleracea` currently overlaps broccoli/cabbage.
  - Action: keep species token only on a neutral species-level entry or remove from cultivar entries.
- `capsicum annuum` overlaps cayenne/green bell pepper.
  - Action: same treatment; keep cultivar-specific aliases separate.
- Source basis: NCBI taxonomy treats these as species-level groupings with multiple varieties/cultivars.

### 3) Brand-vs-generic clinical collisions: generic aliases must not resolve to branded entries
- `mk-7`, `methylfolate`, `5-mthf`, `astaxanthin`, `quercetin phytosome` collisions.
  - Action:
    - Generic aliases stay on generic entries.
    - Branded entries keep only brand-distinct aliases (e.g., `MenaQ7`, `Quatrefolic`, `AstaReal`), not generic chemical names.
- Source basis: NIH ODS uses generic vitamin forms (e.g., menaquinone-7) while brand names are commercial labels.

### 4) Plant vs extract/oil form collisions: enforce context tokens
- `peppermint` vs `peppermint oil` style collisions.
  - Action: oil/extract aliases require context token (`oil`, `extract`, `essential oil`).
- `turmeric` vs `curcumin` / combined phrases.
  - Action: keep compound-level aliases on curcumin entry; whole-herb aliases on turmeric entry; remove ambiguous combined alias forms.
- Source basis: NCCIH differentiates whole herb and concentrated/active components.

### 5) Umbrella class collisions in other_ingredients
- Many overlaps are between broad classes and specific items (`natural flavors`, `natural orange flavor`, `natural colors`, etc.).
  - Action:
    - Broad class entries should NOT own specific flavor/color aliases.
    - Keep broad aliases only on class entries and specific aliases only on specific entries.

## Implementation Plan (Practical)

1. `other_ingredients.json` cleanup (largest risk, 72 collisions)
- Remove specific aliases from umbrella entries (`NATURAL_FLAVORS`, `NATURAL_COLORS`, `NATURAL_GUMS`, etc.).
- Keep each specific alias owned by exactly one specific entry.
- Add `alias_policy` metadata optionally (`exact_only`, `needs_context`) for future enforcement.

2. `standardized_botanicals.json` cleanup (18 collisions)
- Merge duplicate entities representing same botanical into one canonical record where possible.
- For pairs that must remain separate (e.g., whole plant vs branded extract), split aliases by context requirement.

3. `botanical_ingredients.json` cleanup (9 collisions)
- Remove species-level aliases from cultivar-specific records.
- Prefer canonical latin/binomial alias ownership at the most general valid level only.

4. `backed_clinical_studies.json` cleanup (5 collisions)
- Enforce: branded entries cannot own generic aliases.
- Keep generic aliases only on generic evidence entries.

5. Regression checks (must run after each file)
- Re-run overlap inventory script.
- Assert zero collisions for high-risk files (`backed_clinical_studies.json`, `botanical_ingredients.json`).
- For `other_ingredients.json`, allow only documented intentional class-level collisions if any remain.

## Suggested Acceptance Criteria
- No alias appears in more than one entry, unless explicitly listed in a small `allowed_collisions` config reviewed by human.
- 0 high-risk collisions (banned, clinical, botanicals).
- Match determinism: same input ingredient always maps to same canonical record.

## Sources
- FDA UNII (ACACIA): https://precision.fda.gov/uniisearch/srs/unii/5C5403N26O
- FDA UNII (HYPROMELLOSE/HPMC): https://precision.fda.gov/uniisearch/srs/unii/36sfw2jz0w
- FDA UNII (CMC / Cellulose gum mapping): https://precision.fda.gov/uniisearch/srs/unii/M9J9397QWS
- NIH ODS Vitamin K fact sheet (generic MK-7 form context): https://ods.od.nih.gov/pdf/factsheets/VitaminK-Consumer.pdf
- NCBI taxonomy (Brassica oleracea): https://www.ncbi.nlm.nih.gov/Taxonomy/Browser/wwwtax.cgi?id=3712
- NCBI taxonomy (Capsicum annuum): https://www.ncbi.nlm.nih.gov/Taxonomy/Browser/wwwtax.cgi?id=4072
- NCCIH Cat's Claw (Uncaria tomentosa naming): https://www.nccih.nih.gov/health/catclaw/
- NCCIH Peppermint oil (peppermint vs oil context): https://www.nccih.nih.gov/health/peppermint-oil
- NCCIH Turmeric (turmeric vs curcumin context): https://www.nccih.nih.gov/health/turmeric
- FDA GRAS letter (coffee fruit extract naming caution): https://www.fda.gov/media/138898/download
