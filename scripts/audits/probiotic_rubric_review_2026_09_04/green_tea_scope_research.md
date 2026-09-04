# Green-tea evidence identity and preparation scope — 2026-09-04

## Verified sources and bounded conclusion

The parent audit task content-verified the two existing references through live
NCBI EFetch on 2026-09-04 before authorizing this correction. This task does not
add a paper, identifier, clinical-dose cutoff, or evidence-strength upgrade.

- [PMID 38031409](https://pubmed.ncbi.nlm.nih.gov/38031409/): *The effects of green
  tea extract supplementation on body composition, obesity-related hormones and
  oxidative stress markers: a grade-assessed systematic review and dose-response
  meta-analysis of randomised controlled trials.* The verified abstract reports
  59 RCTs and 3,802 participants. The intervention family is green-tea extract;
  the bounded supported outcomes concern weight/body composition and selected
  oxidative-stress measures, not every botanical preparation bearing the species
  name.
- [PMID 19597519](https://pubmed.ncbi.nlm.nih.gov/19597519/): *The effects of green
  tea on weight loss and weight maintenance: a meta-analysis.* The verified
  intervention context concerns catechins/EGCG with caffeine and modest weight
  outcomes. It does not authorize automatic transfer to whole-leaf matcha or a
  theanine-targeted preparation.

This is an ingredient/preparation matching correction, not a complete clinical
review, systemic-bioavailability assessment, proof of efficacy at every amount,
or evidence that excluded products are ineffective. No dose is inferred from
extract mass or a constituent percentage. Safety decisions are unchanged.

## Observed source labels and causal seam

- DSLD 213472: `Green Tea (leaf) extract`, 10 mg, its own Polyphenol form; row
  `ingredientRows[10]`.
- DSLD 217338: `standardized Green Tea extract`, 15 mg, its own 50% Polyphenols
  form; row `ingredientRows[17]`.
- Their primary identities correctly project to `green_tea`. The old evidence
  match depended on stale `standardName=Green Tea Extract`; the corrected name
  exposed missing exact aliases. Existing normalization matches the first label
  through `green tea leaf extract` and the second through
  `standardized green tea extract`. No new matcher normalization is needed.
- Matcha 311037–311040 and 326246 say `Matcha Green Tea, Powder`; 43947 and 63463
  say `organic Green Tea`. Neither literal establishes an extract/catechin
  preparation. Replayed old generic matches must pass the current scope again.
- Hemp+ Relax 232933 retains primary `green_tea`, not `l_theanine`, and declares
  an owned L-Theanine form standardized to 98%. The scope excludes explicitly
  theanine-targeted preparations without computing a constituent dose or
  changing primary identity. An independently verified `l_theanine` primary is
  also excluded by the record's canonical exclusion.
- The parent inventory of 311 existing green-tea matches found additional
  explicit extract spellings: `Green Tea (Camellia sinensis) extract` (14),
  `Green Tea (Camellia sinensis) (leaf) extract` (2), `Green Tea leaves extract`
  (14, including case variants), and `Green Tea decaffeinated extract` (6).
  These exact normalized source terms are allowed by the same preparation
  scope; an arbitrary `extract` elsewhere in the product is not proof.

## Verified preparation names — identity only

The parent task checked official indexed technical content on 2026-09-04:

- [Indena Greenselect Phytosome](https://www.indena.com/us/product/greenselect-phytosome/?lang=us)
  identifies a standardized catechin green-tea leaf extract, including
  EGCG/catechins. Direct opening returned HTTP 403; the parent read the official
  indexed technical content.
- [Indena Greenselect](https://www.indena.com/cn/product/greenselect/) identifies
  the unformulated material as green-tea dry extract, with 60% polyphenols and
  40% EGCG in the official technical content.
- [Thorne Green Tea Phytosome](https://www.thorne.com/ingredients/green-tea-phytosome)
  independently identifies the preparation family on the manufacturer's site.

`greenselect` and `green tea phytosome` therefore establish extract preparation
scope when named on the linked source row. This does not add branded clinical
evidence, infer a dose, or make a comparative bioavailability claim. No blanket
`sunphenon` term is added: the parent's manufacturer review found that the brand
family also includes theanine, fluoride and concentrated-caffeine preparations.

An independently identified `caffeine` primary cannot borrow catechin/extract
evidence merely because its source form names green-tea extract. Caffeine named
as a constituent of a green-tea extract primary does not by itself exclude that
extract. This is an identity/preparation distinction, not a caffeine dose or
safety decision.

## Open provenance issue — deliberately not corrected

`INGR_GREEN_TEA.total_enrollment` is 1,210, whereas the verified abstract of
PMID 38031409 reports 3,802 participants. The aggregate may refer to another
anchor; its provenance is unresolved. Do not substitute the newer count or
claim aggregate verification. Existing numeric strength/count fields, effect
classification, and score magnitudes remain untouched. Legacy broad endpoint
metadata is not newly validated by this bounded preparation-scope review.

## Implemented boundary and verification

The existing clinical applicability gate now accepts three optional, validated
record-owned constraints: `require_source_label_form`,
`excluded_canonical_ids`, and `excluded_form_terms`. Only `INGR_GREEN_TEA` opts
into this source-only preparation contract. It uses original source text and
owned forms, preferring immutable taxonomy forms when present; generated form
IDs, matched forms, and an IQD duplicate's generated name cannot establish
preparation proof. An existing active source owner also retains its explicit
non-exposure disposition. Defaults for all other records remain unchanged.

The green-tea record requires extract/catechin terms, excludes independently
identified `l_theanine` and `caffeine` primaries and explicitly named theanine
forms/preparations, and retains its existing effect classification,
enrollment/counts and scoring magnitudes. These exclusions are evidence
applicability only, not safety blocks or catalog quarantine.

Test-first sequence through `scripts/test.sh fast`:

- Exact source extract discovery: 2 failures, then 2 passes.
- Replayed whole-leaf/species matches: 3 failures, then 5 passes.
- Generated form/name and IQD duplicate bypasses: 5 failures, then 11 passes.
- Theanine label/form/Hemp and canonical exclusions: 4 failures, then 15 passes.
- Final scoped regression file plus existing clinical applicability, confidence,
  hyphen matching and source-dose suites: **119 passed** (1.85 seconds reported
  by pytest). Includes malformed new policies, missing links, source-owner
  priority, legacy IQD-only provenance, unchanged default policy behavior, and
  independent L-theanine evidence.

Four full-product, in-memory clean replays (no artifact writes):

| DSLD ID | Evidence result | Evidence pillar | Total score |
| --- | --- | --- | --- |
| 213472 | Existing extract evidence restored at its own row | 15.2 | 68.2 |
| 217338 | Existing extract evidence restored at its own row | 15.9 | 67.2 |
| 311037 | No extract credit; old match rejected as form mismatch | 0.0 | 46.5 |
| 232933 | L-theanine evidence retained; old generic extract match excluded | 4.1 | 33.6 |

All four remain `scored`; their primary green-tea identity is unchanged. The two
restored totals equal the controlled pre-projection totals. The parent audit
owns the subsequent broader corpus comparison and independent review.

## Independent-review correction — source-reference bypass

Independent review reproduced a bypass: an original Matcha row plus a generated
IQD extract row without a source reference could satisfy an old match whose
reference list was empty. The previous exact-name fallback admitted the
generated row and emitted an applicable assessment with `source_row_ref=null`.

The source-only path now uses original active owners exclusively whenever any
original row exists. A legacy IQD-only source remains usable only when no
original owner exists. Every source-only eligible row must have a nonblank
string source reference. An old match without references may still resolve an
exact source-name match to a genuinely referenced owner; unique-canonical
guessing remains available only to the unchanged default policy path.

The exact reviewer reproduction failed before the correction (1 failure), then
passed. Missing, empty, whitespace and numeric owner references plus canonical-
only fallback produced a second RED group (9 failures), then passed. Additional
controls cover absent/empty match references, forged unrelated IQD references,
an original owner missing its own reference, valid exact legacy fallbacks,
legacy IQD-only provenance, and unchanged default policies. Final bounded
backstop: **148 passed in 2.17 seconds**. The clinical record, numerical strength,
identity producer and main workspace were not changed by this correction.

## Exact source-variant backstop

The four inventory extract spellings produced four failing preparation-scope
assertions before adding their exact normalized terms, then passed. The
verified Greenselect/Green Tea Phytosome names and caffeine-primary exclusion
produced three failures before their record-level correction; the
caffeine-constituent control already passed. The bounded five-file adjacent
backstop then passed **156 tests in 1.92 seconds**. These later corrections are
registry-only; the source-reference runtime remains unchanged.

Four additional full-product in-memory replays used the existing cleaned source
files under the main workspace's `scripts/products/output_<brand>/cleaned/`;
no input or output artifacts were written. All four kept a verified
`green_tea_extract` primary and matched the existing clinical record through
their valid `Green Tea Extract` standard name. The source-term additions admit
the actual labels without adding discovery aliases.

| DSLD ID / brand | Source row | Literal extract spelling | Evidence / total |
| --- | --- | --- | --- |
| 82369 / CVS | `ingredientRows[1]` | Green Tea (Camellia sinensis) (leaf) extract | 12.5 / 62.8 |
| 12031 / GNC | `ingredientRows[24]` | Green Tea leaves extract | 16.7 / 72.6 |
| 181895 / Life Extension | `ingredientRows[3]` | Green Tea decaffeinated extract | 12.3 / 51.8 |
| 182730 / Pure Encapsulations | `ingredientRows[39]` | Green Tea (Camellia sinensis) extract | 16.7 / 79.5 |

CVS 82369 was outside the parent's selected replay union, so an additional
isolated control replay imported the untouched detached-control modules. Its
`scored` status, all six pillar values, and total 62.8 were identical to the
candidate. The other three remain in the parent's broader replay comparison.

The parent's final source inventory also confirms that Sunphenon 333900 and
Catechins 18541 have their own `Green Tea Leaf Extract` source forms; no blanket
Sunphenon or catechin-brand alias is required. GreenSelect 24966, Green Tea
Phytosome 284226 and the TeaSlender 231826 nested row name the reviewed extract
preparations in their source-owned label/forms. Black Tea 312254 instead names
black tea with a generic `Camellia sinensis Leaf Extract` form: that species-only
form does not establish green-tea preparation scope and is not added as an
allowed green-tea term. No additional discovery aliases or scope rules were
introduced for these inventory results.

## Final real-label corrections: nested owner and full EGCG spelling

The complete comparison exposed two distinct remaining joins; neither is a
reason to broaden extract eligibility to arbitrary source forms.

- **20009, Green Tea Complex:** its 400 mg structural parent owns separately
  disclosed 250 mg powder and 150 mg extract rows. The previous primary-row
  collector selected the parent as a same-canonical proxy and missed the
  quantified child. Primary collectors now use the existing strict dose
  source-owner join, with ancestors excluded; RDA/UL uses the same join with
  ancestors retained as lineage context. This removes the duplicate selection
  algorithm. Undosed/display-only children do not become exposures or borrow
  the parent's total. The regression was RED (1 failed, 2 passed), then GREEN
  with the adjacent preparation tests (79 passed). The real-label replay
  retains green-tea evidence at the **150 mg child's own source reference**.
  Evidence becomes 6.3, rather than the old 12.5 based on an inapplicable
  400 mg parent amount. Restoring the match is not restoring the wrong dose.
- **328410, Cytokine Supress with EGCG:** the source explicitly declares
  `Epigallocatechin Gallate`, 300 mg, canonical `egcg`, category
  `non-nutrient/non-botanical`, with its own green-tea leaf-extract source form.
  The original reduced fixture incorrectly kept category `botanical` and
  therefore did not reproduce the missing match. Correcting the fixture to
  the actual category produced **2 failures** while both similar-catechin
  negatives passed. The existing `egcg` discovery alias now also accepts its
  two verified full chemical spellings; the same source-preparation gate
  accepts these exact spellings. No broad catechin/family alias is added.

Chemical identity verified on 2026-09-04 through
[NCI's EGCG definition](https://www.cancer.gov/publications/dictionaries/cancer-terms/def/egcg),
[NCI's epigallocatechin-gallate definition](https://www.cancer.gov/publications/dictionaries/cancer-drug/def/epigallocatechin-gallate),
and [PubChem CID 65064](https://pubchem.ncbi.nlm.nih.gov/compound/65064).
The live PUG REST property response returned `C22H18O11`, InChIKey
`WMBWREPUVVBILR-WIYYLYMNSA-N`. No identifier was added to the production data.
Epigallocatechin and epicatechin gallate remain distinct, unmatched aliases.
This spelling repair changes neither the existing evidence strength nor the
record's dose, enrollment, outcome or clinical-approval fields.

The shared owner collector also feeds synergy and formulation enrichment.
The final impact check therefore expands beyond the initial green-tea cases
to all stored nested-source products, comparing candidate and unchanged
`cea87d01` implementations against identical clean inputs. This remains a
read-only impact audit, not an operational rebuild or release acceptance.
