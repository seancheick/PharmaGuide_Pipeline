# Submission extraction — the plan

One document. It replaces plan v3 and the two review threads it merges, so
there is one place to read and one place to change. Updated 2026-09-11 after
reconstructing the completed work through `64f65fbb` and running the saved
DSLD image experiment. Code and experiment receipts take priority over older
chat status summaries.

Standing constraints: extraction stays disabled; no `auto_approved` and no
approval-RPC change before the frozen holdout qualifies; one server-side
`LabelDraftExtractor`; a human clicks Approve; AI never mints identities,
scores or clinical claims; barcode stays required until that decision is
reversed in writing.

## Where things actually stand

Done and pushed: the draft envelope, worker and queue; deterministic checks;
the grounding verifier wired at the boundary; per-dimension benchmark
reporting with gates on identity, serving, dose, unit, blend nesting and warning presence; the
shared-preprocessing measurement; the barcode coverage tool; and the protocol
amendment that lets a pre-existing independent transcription serve as gold
when a person confirms the edition. `import-reference` is implemented
(`f6b02aa5`), with expanded comparison (`cd25fe81`) and shared GTIN validation
(`6f30948f`). Identity and serving gates landed in `fbcc5420`.

Not done: the frozen qualifying 20+40 set, a qualifying benchmark run, and
the later observation/automation stages. Development diagnostics are now
running; they are not held-out evaluations.

The unfinished reference-import hardening was retained and audited rather
than duplicated: shared Facts-row selection excludes Other Ingredients,
%DV is compared, unnamed draft rows require review, partial transcriptions
are protected, and draft hashes must belong to the product. Additional
reproduced fixes rehash the actual photo files, reject escaped gold paths
before writing, treat partial/unreadable statements as unresolved, and keep
model-invented row names out of the blinded refusal. These use the existing
benchmark path/hash/statement helpers and the same catalog comparator.
These reference-import changes are now committed in `eb988f69`; do not
reapply them as a new implementation.

Verification for this checkpoint: final affected submission/holdout slice
528 passed, 24 opt-in tests skipped; release profile 123 passed and all
subsequent artifact/live-identifier gates passed. The earlier broad fast
backstop passed 14,238 tests (66 skipped) before the last four regression
fixes; the final affected slice and release checks ran after those fixes.

### Recovered experiment checkpoint — do not restart image collection

The 60 high-resolution images downloaded with `64f65fbb` survived. All image
hashes verified. The manifest-selected set (2400px maximum width, WebP quality
95, 26,186,236 bytes) is now preserved outside `/tmp` at
`reports/submission_dsld_diagnostic_20260910/`. Extra unselected temporary
files were not imported. Production phone images were not changed.

The same directory contains the matching 60 raw DSLD records, 60 catalog
records, model-file hashes, exact prepared inputs for successful extractions,
per-product drafts/receipts, `summary.json`, and `pipeline_audit.json`.
These generated assets are gitignored local files, not remotely backed up by
a code push. The tracked plan records their location and results.

**RapidOCR baseline:** 60 attempted, 48 drafts, 11 failures, 1 abstention.
None of the returned drafts had an empty catalog-discrepancy list. Counts
include 549 catalog rows absent from drafts and 181 draft rows not matched to
the catalog. These are discrepancy counts, NOT clinical accuracy metrics:
the catalog is not independent raw-source gold, and the renders show complete
page-one package artwork rather than necessarily isolated Facts panels.

Full-artwork columns and tall marketing text bridge OCR row bands. On DSLD
739, a reproduced resulting name exceeded the envelope's 2,000-character
limit, but the baseline labeled it `provider_unavailable`. The shared extractor now distinguishes an
adapter-raised `LabelDraftError` as `model_failure`, with no leaked label text
and no invented cost. A two-product real-image rerun preserved 695's draft
and correctly reported 739 as `model_failure`; see
`reports/submission_dsld_ocr_typed_failure_20260910/`. The baseline is retained,
not silently rewritten. Remaining failures still need individual diagnosis.

**Audited rerun:** `reports/submission_dsld_audited_20260910/` preserves all
60 verified images and the current code hashes. Same outcomes: 48 drafts,
11 `model_failure`, 1 abstention. All 49 returned draft files (including the
abstention) are byte-identical to the baseline. The corrected comparator
reports 279 missing Facts rows instead of 549: 270 Other Ingredients rows
were previously charged to the wrong section. It additionally exposes 26
%DV discrepancies. This is a correction to measurement, not improved OCR.

**Existing pipeline audit, same 60 products:** all 60 cleaned-source records
available; zero BLOCKER/HIGH findings, 16 LOW missing inactive-contract
signals, 2 MEDIUM blend dose-disclosure findings. This audit consumes existing
stage artifacts; it is not a fresh full rebuild or independent clinical audit.

**Local vision smoke:** installed `qwen3-vl:latest` (8.8B, Q4_K_M), pinned to
`901cae73216286ea8c5aba8b46d307ff7188f737285ec500c795a12f05225d28`, was tried
on DSLD 695 via the existing Ollama adapter, on an isolated cloud-disabled
daemon. It returned an empty reading and failed closed. Receipt:
`reports/submission_dsld_qwen_smoke_20260910/`. This was NOT a 4B test and
does not qualify or disqualify all possible Qwen configurations.

A follow-up simple reading of the same prepared image returned the printed
Turmeric name and 500 mg amount. The production structured request returned
an empty answer while its separate `thinking` field contained template keys.
This isolates a structured-response integration issue, not a missing model.
Do not parse the thinking field as a validated draft or count the simple
reading as qualification. The temporary diagnostic daemon was stopped;
the operator's normal Ollama daemon was not changed.

### OCR panel isolation — 2026-09-11

The existing OCR adapter now uses a recognized Supplement Facts heading to
bound its OCR column and stops before recognized footers. It retains original
input/photo provenance; no image-preparation fork or new mapper was added.
Multiple recognized panels abstain rather than combining possible editions.
An untagged marketing dose no longer selects a Facts panel. A single explicitly
tagged, cropped panel can still be read without its heading. These are
conservative geometry heuristics, not guaranteed panel detection; rules v3
must be evaluated independently of v2.

Saved rerun: `reports/submission_dsld_ocr_panel_20260911/`, same 60 images,
51 drafts, 9 abstentions, zero adapter failures. This is NOT qualification or
an accuracy improvement claim. Catalog missing-row findings increased from
279 to 573, while unmatched draft rows fell from 181 to 99. The remaining
readings are incomplete: DSLD 695 still treats collapsed
`ServingSizeOneCapsule` as an ingredient; DSLD 739 still merges dense adjacent
rows (including Alpha Lipoic Acid and Quercetin). Bounds may also omit boxes.
The previous baseline remains untouched for comparison.

Next bounded chunk: fix dense-row separation and collapsed serving-header
recognition in this same adapter, preserving wrapped-name and blend tests.
Re-run these saved images before broader model experiments. Do not enable
extraction or promote these drafts; warnings, identity and completeness still
fail the intended standard.

Verification: 14,256 fast-tier tests passed, 66 skipped. The focused adapter
and diagnostic slice passed 29 tests; the three new panel-selection regressions
were first demonstrated failing before the fix. The diagnostic fixture was
updated to keep exercising invalid-draft classification behind a real heading.
The targeted release invocation also completed successfully: 29 tests plus
the standard artifact/freshness and live-identifier gates. No catalog rebuild
or production deployment was performed.

### OCR row follow-up and Gemini availability — 2026-09-11

Continued in the same OCR adapter, not a replacement parser. Three reproduced
defects now have regression coverage: collapsed `ServingSizeOneCapsule` is
serving text rather than an ingredient; distinct amount-only boxes separate
overlapping dense rows; and a dose plus standalone %DV without a readable name
retains an unidentified partial row rather than naming it `25%`. Standalone
%DV boxes now populate the existing percent field. Wrapped-name tests remain.
Rules v4 was an intermediate measured run; v5 includes the unidentified-row
fix. Historical receipts are not overwritten.

The same 60 images were rerun under
`reports/submission_dsld_ocr_rows_v4_20260911/` (intermediate) and
`reports/submission_dsld_ocr_rows_v5_20260911/` (final). Final outcomes: 50
drafts, 10 abstentions, no adapter failures. Missing-row findings fell from
573 at v3 to 404 at v5, still above the earlier v2 count of 279; these are
catalog comparisons, not independent accuracy measurements. Thirteen rows
are explicitly unreadable. DSLD 695 now has one ingredient and the printed
serving text. DSLD 739 has 16 rows instead of one merged row, but still misses
early nutrients and has OCR misspellings. No qualification is claimed.
Next OCR work should address header/row boundaries and ambiguous missing-name
or multi-amount rows, using the preserved geometry rather than guessed text.
Verification: 540 affected submission/holdout tests passed, 24 opt-in skips;
32 focused adapter/diagnostic tests passed. All three new defect tests were
observed failing before their fixes. The full fast suite was not rerun for
this bounded follow-up; its previous checkpoint remains recorded above.
The targeted release run passed its 32 tests and artifact/identity gates, then
failed the final citation gate on a PubMed HTTP 400 batch response. An unchanged
rerun of `verify_backed_studies_citations.py --strict` passed all 449 PMIDs
(zero not-found); no clinical data was edited and no gate was bypassed.

Gemini's two failed public labels (739 and 2502) were each retried once in this
turn and both again returned HTTP 503. See the local-only
`reports/submission_dsld_gemini38_availability_20260911/`. No automatic retry
loop, alternate key, paid upgrade, private upload or production adapter was
introduced. The one successful prior reading remains encouraging but does
not establish availability or qualification.

One bounded comparator run used the already available `gemini-3-flash-preview`
with the same prompt and settings, saved at
`reports/submission_dsld_gemini3flash_smoke_20260911/`. All three requests
returned HTTP 200, but none yielded an accepted draft: 695 pointed a child at
a non-blend header, 739 omitted the required `abstain_reason`, and 2502 stopped
without completing its reading. This distinguishes the earlier HTTP failures
from content/contract failures. No output was repaired or promoted. Next hosted
work must address these explicit contract failures without a second schema
owner, then repeat a bounded public-image test before a larger comparison.

### Gemini public-image smoke — 2026-09-11

At the operator's explicit request, tested the configured Gemini key with
public DSLD images only. Model discovery succeeded. Google's current pricing
lists `gemini-3.8-flash` with a free tier; the key's actual billing tier was
not independently verified. Free-tier data-use terms are not suitable for
silently forwarding private submissions. No worker/provider registry changed.

The diagnostic reuses the existing instruction, image preparation, envelope
assembly/validator and catalog comparator, without a repair mapper. DSLD 695
returned a valid draft, with its correct 500 mg amount, one-capsule serving,
048107076009 barcode, Other Ingredients and physician/pre-surgery warning.
Visual spot-check agrees on those fields. Three catalog differences remain:
brand wording, form detail and Other Ingredients punctuation. Those differences
do not by themselves establish which source is wrong. No gold was authored.

DSLD 739 returned HTTP 503 twice (one bounded retry); 2502 returned HTTP 503
on its first attempt. Thus this smoke produced ONE validated draft across
three selected products, not a successful three-product benchmark. Availability
is unresolved, and no accuracy or qualification rate is claimed. Model version
and token usage were saved; the diagnostic identifier hash is explicitly NOT
a model-weights digest. Cost was not verified as zero.

Receipts: local gitignored `reports/submission_dsld_gemini38_smoke_20260911/`,
`reports/submission_dsld_gemini38_retry_20260911/`, and
`reports/submission_dsld_gemini38_third_20260911/`. The one-off orchestration is
`reports/gemini_public_dsld_probe_20260911.py`; it is not a production adapter.
Next Gemini step: a bounded availability retest, then a tested hosted adapter
behind the same extractor with explicit retention and usage accounting before
any private submission or qualifying run. Do not automatically rerun all 60.

Sources checked: https://ai.google.dev/gemini-api/docs/pricing and
https://ai.google.dev/api/generate-content.

### Qwen follow-up — 2026-09-11

No new model was downloaded. Ollama 0.34.0 runs the installed Qwen3-VL
8.8B digest above. The same image and request through `/api/chat` still
returned an empty final answer. Removing forced JSON reached a 4096-token
context ceiling without a final answer. An explicit raw-template image probe
was refused with HTTP 400 (tokenization failure). These are diagnostic
experiments, not alternate production paths.

The adapter had pinned output length but inherited context size from the
daemon. The single request template now pins `num_ctx=16384`, retaining the
12000-token output ceiling and 180-second request deadline. Version v5 was
tested locally and still returned an empty Qwen3-VL answer. Version v6 adds
explicit field-wrapper, serving-quantity and disclosure instructions after
the next candidate ignored the original shorthand. Both settings and text
remain part of the one prompt fingerprint; old configurations fail closed.
The validator and approval path were not relaxed; thinking-only JSON still
cannot become a draft.

The already-installed `qwen3.5:latest` (9.7B Q4_K_M), digest
`6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7`,
returned final JSON but omitted required field objects and source references.
On DSLD 695, its v5 reading also confused ingredient mass with serving amount
and contradicted its Other Ingredients disclosure. The v6 reading corrected
those two items but still lacked field wrappers and omitted a barcode digit.
Both readings omitted the visible physician-consultation / pre-surgery warning
while retaining marketing statements. This is a safety-relevant omission,
not just JSON formatting. Checked against the saved 695 artwork, not inferred
from our export.
Do not add an output-repair mapper or fabricate sources to make this pass.

Receipts are local under `reports/submission_dsld_qwen_context_v5_20260911/`,
`reports/submission_dsld_qwen35_v5_20260911/`,
`reports/submission_dsld_qwen35_v6_20260911/`, and
`reports/submission_dsld_qwen_probes_20260911/`. A further unchanged v6 smoke
on DSLD 695, 739 and 2502 returned three `model_failure` outcomes; receipts
are in `reports/submission_dsld_qwen35_v6_three_20260911/`. None constitutes gold or
qualification. Current installed candidates are not ready for submission
extraction; this is not a claim that every Qwen variant is unsuitable.
The isolated cloud-disabled diagnostic daemon was stopped after the runs;
the operator's normal daemon and installed models were left intact.
Verification: 533 submission/holdout tests passed (24 opt-in skips); a
targeted release invocation ran the 34 adapter/diagnostic tests plus all
standard artifact and live-identifier gates, successfully. This follow-up did
not rerun the full 123-test release slice from the previous checkpoint.

### OCR dose safety, row boundaries, Gemini diagnosis — 2026-09-11

Continued in the same OCR adapter, comparator and shared instruction; no new
extractor, parser or schema owner. Each defect below was reproduced on a real
DSLD image, pinned by a test written to fail first, then fixed.

**Doses.** Three readings produced wrong doses, the error class gated at zero.
OCR turns "1,000 mg" into "1.000 mg", read as 1 mg (8718, 758, 746). Of 98,377
printed catalog doses only 34 are a 1-999 value with exactly three decimals,
against 5,746 written with a thousands comma, so such an OCR reading is now
unreadable rather than guessed; typed DSLD transcriptions are unaffected. A
number inside a parenthetical constituent line no longer beats the row's own
dose box (699: 6.25 mg read for 25 mg). One or two letters glued to a dose are a
misread digit, not a prefix (745: "T0mcg" read as 0 mcg). A name printed right
of the dose column belongs to a second column (778: Choline given Riboflavin's
50 mg). Separately, "1,667%" was parsed as 667% even when OCR read the comma
correctly; the percent parser now reads thousands.

**Rows.** On a dense panel every box touches the next, so the heading, the
first rows and the first dose chained into one band, which began with
"Supplement Facts" and was dropped whole — 739 lost Calories, Carbohydrate and
Vitamin C 1,000 mg. Headings are now excluded before banding, and a row is
anchored by any right-hand number, not only a dose with its unit. A number with
no name is an unidentified row, not a name ("59"). "Servings per" and "Amount
per" are headings in any spacing, and "Servings Per Bottle" is now read.

Rules v6-v9 were intermediate; v10 produced the following development results.
Same 60 images, same comparator
for both columns (v5 re-scored with today's comparator for a fair comparison):

| | v5 | v10 |
|---|---|---|
| Products drafted | 50 | 55 |
| Doses read | 321 | 351 |
| Wrong doses against the catalog | 5 | 0 |
| OCR readings at thousandfold risk | 10 | 0 |
| Headings read as rows | 8 | 0 |
| Catalog rows missed | 253 | 215 |

These are development results on images used to find the bugs, and the catalog
is not independent gold. They are not qualification. Receipts:
`reports/submission_dsld_ocr_rows_v10_20260911/` (v6-v9 kept as intermediates).

**Writer and comparator now share one nesting rule.** `_blend_parents` decides
a row's parent for both gold_rows and the comparator; before, a reading
identical to what the writer produces was refused on every label with a
nutrition-fact sub-row or EPA under Fish Oil. Verified: across 400 real
records such a reading now yields no row disagreements.

**Gemini's three contract failures have identified failure modes, not an
accuracy clearance.** 2502
stopped with MAX_TOKENS after 11,517 of 12,000 tokens went to thinking (the
probe sets no thinking limit). 739 returned an object wrapped in a
one-element list. 695 nested a standardization line ("95% Curcuminoids") under
an ordinary ingredient, which the contract only allows under a blend header.
The shared instruction (now `label-draft-local-v7`; v6 fails closed) states
"one object, never an array" and where standardization lines and constituents
go. No output is unwrapped or repaired. OCR grounding of the one valid Gemini
reading located 5 of 9 claims, including the dose; the 4 it missed were
stylized or tiny text, and Gemini's barcode matches the catalog exactly.

**Audit update, 2026-09-11:** the configured key successfully returned model
discovery and a tiny `gemini-3-flash-preview` generation (HTTP 200, one
candidate, STOP). The earlier invalid-key result is not a current blocker;
its cause was not established. No alternate credentials were used or printed.
This proves availability for those requests, not image-extraction accuracy.
After the operator replaced `.env`'s `GEMINI_API_KEY`, a separate generation
check explicitly cleared the inherited key before using the existing env
loader: HTTP 200, one candidate, STOP. The updated file's key works too.

**OCR audit correction:** v11 marks multiple pure-dose boxes in one row as
unreadable, even if their values agree. The adapter has not resolved alternate
serving columns or adjacent ingredient columns and must not choose the first
dose. Two regression cases reproduced v10's incorrect `read` status before
the fix. The v11 rerun is retained at
`reports/submission_dsld_ocr_columns_v11_20260911/`: 55 drafts, 5 abstentions,
zero catalog amount disagreements, but 25 unit findings, 56 identity findings,
and 362 missing-row findings. These counts come from the diagnostic summary
and are not the differently filtered v10 table's denominator.

**Grounding audit correction:** a claimed number present on the page formerly
masked an absent unit (500 IU could be marked grounded on a page printing
500 mg). The existing verifier now requires every component returned missing
by its own claim matcher, not only missing numeric components. A failing-first
regression covers it. This remains a page-text presence report, not proof of
correct row association, complete transcription, or approval eligibility.

**Gemini bounded retest:** the new `.env` key completed all three public-label
requests with v7 plus `thinkingConfig.thinkingLevel=minimal`, supported by
https://ai.google.dev/gemini-api/docs/generate-content/thinking. All three
failed validation because `serving.amount.unit_text` was outside the value
wrapper. The shared instruction itself ambiguously described amount fields;
v8 now explicitly specifies the nested field wrapper for serving and ingredient
amounts, with a regression asserting the actual transmitted instruction.
No adapter repairs were added and validation was not relaxed.

The v8 retest yielded one valid draft (695), while 739 supplied an empty amount
unit and 2502 attached sources to a `not_present` percent-DV field. All returned
HTTP 200. Receipts are in `reports/submission_dsld_gemini3flash_v7_20260911/`
and `reports/submission_dsld_gemini3flash_v8_20260911/`. The one-off probe and
raw responses remain local diagnostic artifacts, not production adapters or
independent gold. A valid draft is not an accuracy clearance.

**Output-contract follow-up (2026-09-11):** shared prompt v11 explicitly
requires partial status for a printed number without a printed unit, and empty
sources for absent/unreadable fields. The validator and output mapping are
unchanged; no units are invented and no invalid responses repaired. Six added
tests cover the transmitted instructions plus acceptance/rejection at the real
adapter boundary. Flash-Lite v9 passed 2/3; its remaining Calories amount had
null unit but incorrectly used read status. The explicit final status check in
v10 yielded **3/3 valid drafts** with `gemini-3.5-flash-lite` on public DSLD
695, 739, 2502 (HTTP 200, STOP). Final v11 clarifies that exactly one missing
amount component is partial, while both missing remain unreadable; its fresh
three-label run also passed 3/3. These nine development calls are not holdout
qualification and do not establish a general schema-success rate.

Receipts: `reports/submission_dsld_gemini35lite_v9_20260911/` and
`reports/submission_dsld_gemini35lite_v10_20260911/` and
`reports/submission_dsld_gemini35lite_v11_20260911/`. The v10 responses consumed
24,641 total tokens across three calls. Accuracy remains unresolved: comparisons
flag product-name, form-text, other-ingredient and blend-header differences;
some are representation differences, not yet adjudicated errors. No automatic
approval, production provider registration, or extraction enablement occurred.
The final v11 run consumed 25,502 total tokens. Its saved prompt fingerprint
matches the final shared instruction. Verification: full fast suite 14,287
passed / 66 skipped; final affected extraction suite 123 passed after the last
prompt/test edit. Full release command also passed: 123 release tests plus
strict artifact, source-of-truth and live-identifier checks. No catalog was
rebuilt or published.

**Three-label accuracy review (2026-09-11, AI-assisted development review):**
reviewed the saved v11 drafts, the downloaded DSLD label images, the raw JSON
records, and the catalog disagreement receipts. No new API calls, no gold
attestations, no source-data edits. These already-seen images remain development
data, not an independent holdout. This review is not a two-person sign-off.

| Check | Observed result | Scope/limitation |
| --- | --- | --- |
| Row coverage | 1 + 21 + 7 = 29 rows present | Reviewed row alignment; not generic position-only matching |
| Primary numeric amounts | 29/29 agree with raw DSLD | Does not assess every embedded standardization number |
| Explicit dose units | 28/28 agree with raw DSLD | Calories has no printed unit; draft correctly retains 20 with unknown unit, not an invented kcal |
| Numeric %DV | 19/19 agree with raw DSLD | Printed historical label values, not recalculated modern daily values |
| Visible barcode digits | 695 and 2502 match image and raw | 739 image has none; draft abstains |
| Full extraction clearance | NOT PASSED | Serving inference, missing fields, identity omissions, and reference disagreements remain |

**Actual extraction issues (not catalog formatting):**

- 695: `servings_per_container=100` is marked read, but the image only prints
  100 capsules and a one-capsule serving. Raw DSLD has null servings per
  container. The draft inferred rather than transcribed that field. Its
  `basis_text` says Serving Size although Amount Per Serving is printed.
- 2502: similarly infers `servings_per_container=60` from the package count.
  `basis_text` is not_present despite a visible Amount Per Serving heading.
  Product name omits the prominently printed 100 mg strength.
- 739: product name contains only the flavor, omitting 1,000 mg Vitamin C.
  Structured `serving.amount` is null despite the correctly read size string
  1 packet (8.3 g); `basis_text` also misses Amount Per Serving. Treat this
  as incomplete, not permission for the downstream mapper to invent data.
- Statement completeness is not established. Principal directions/warnings
  are retained, but examples of missing printed text include 2502's instruction
  to read the entire label before use and multiple marketing statements.
  Do not infer 100% statement coverage from preserved core warnings.

**Reference/comparison findings, kept separate from model errors:**

- 739 image prints Total Carbohydrate / Sugars; raw DSLD names them Total
  Carbohydrates / Sugar. The draft follows the image. The catalog comparator
  reports both as missing/extra because both have 5 g and its safe fallback
  refuses ambiguous amount-only matching. Do not add a fuzzy auto-match.
- The Calories 20 finding comes from the catalog projection leaving the
  `{Calories}` pseudo-unit unparsed. The raw record contains quantity 20.
  This is not an invented dose in the draft.
- 739 raw forms are incomplete relative to the image (including Calcium,
  Phosphorus, Potassium, Zinc and Thiamin). A richer image transcription is
  not automatically a hallucination just because the form arrays differ.
- 2502 raw green-tea notes say minimum 9% polyphenols; the image and draft
  say 90%. This is an explicit source conflict, not a model dose error.
  Preserve the original record; a source correction needs separate evidence
  and review, not rewriting gold to match the candidate.
- 2502 Whole grape extract includes Polygonum cuspidatum in the printed
  combined row. Raw DSLD categorizes it as blend with no nested rows; the
  draft preserves the second botanical in form_text but marks ordinary row.
  This requires a reviewed contract interpretation, not forcing either
  shape to agree by silently flattening or inventing child doses.
- Terminal punctuation, case, botanical detail and moving printed qualifiers
  into form_text account for several other discrepancies. GNC's label brand
  line, raw brand and shortened catalog brand are also different surfaces.
- The catalog disagreement helper does NOT compare serving fields or
  statements. Its docstring incorrectly called it the only adjudication list;
  corrected that claim. The benchmark already owns serving and statement
  checks; do not build another evaluator or call an empty catalog diff an
  accuracy pass.
- 695's GNC-procedure/USP-standard text is a transcribed manufacturer claim,
  not a verified third-party certificate. Nothing here awards certification
  credit or proves a registry match.

Review inputs: `reports/submission_dsld_gemini35lite_v11_20260911/*.draft.json`,
the manifest-pinned images in `reports/submission_dsld_diagnostic_20260910/`,
and raw `staging/brands/{GNC/695,Emergen_C/739,Life_Extension/2502}.json`.
Draft SHA256 values: 695 `27af4d534e60e6f2bfe8bd96e74d66983815ac1109feb0ad4be8d8523df8c167`;
739 `ac9ab2f16fd640894634b6cbac22d4d833b6981d2d005280e269246cdafc6f25`;
2502 `0929f95d62cefc169c3bef95d4e9848de50efeeec5a48abf0a7c4e54404731ae`.
Raw SHA256 values: 695 `a997d48732f6a6d1bce4dd1394dc3d4d34f01e97840a73447f18b60ce0acaa1b`;
739 `867e5687b28bb343df1b7751f4d9dc05edd67ec3cce9d27600c2cd8a66de3d0b`;
2502 `2ae48e5fec46071262f53d144bbc46d18ce72847cfa11ee8c69f95e902fb5a24`.

### Gemini: 60-label run, accuracy review, model comparison — 2026-09-11

Public DSLD images only, free tier, within a stated call budget. No output was
repaired; the envelope validator is unchanged and still owns acceptance.

**60-label run** (`gemini-3.5-flash-lite`, v11, thinking minimal): 54 of 60
validated. Five hit the 12,000-token answer cap with no thinking used — labels
of 26-99 Facts rows, since every field carries value, status, confidence and a
source. One network failure. Of 402 doses claimed, OCR independently found 389
(97%) printed on the label.

**What the 38 dose differences from the catalog were.** 29 are Calories rows
the catalog cannot hold as a number (`20 {Calories}`); OCR confirms Gemini's
number is printed in every one. One is a probiotic count. Seven are on 4283,
which prints two serving columns (1 tsp, and 3 tsp "Advanced Usage"): five are
correct 1-tsp values where the catalog used 3 tsp. Two are real errors: Vitamin
A printed "667 - 1,042 IU" and Vitamin D "4 - 10 IU" were reported as the low
end only, understating fat-soluble vitamins. No wrong unit ("I.U." is a
spelling our unit vocabulary does not recognise). Blend members were filed
wrongly: 180692's 23 members merged into one row, and 18102's went into the
blend's form_text — the latter partly caused by the v7 form_text wording.
Codex's review of three labels added inferred servings per container (695,
2502), a missed basis heading, incomplete product names, and a DSLD error (9%
vs 90% polyphenols) where Gemini read the label correctly.

**Shared instruction v12-v15**, one owner: a blend's members are rows, never
form_text or one merged row; a printed dose range is partial, never one end; a
second serving column is flagged `serving_basis_ambiguous`; servings per
container is never computed from a package count; basis_text is the printed
heading; product name in full; a field not printed is still a field object;
%DV is never partial; only `field|null` fields may be null. Gemini's answer cap
raised to 65,536 (the model's limit, verified). v4-v14 fail closed.

**Retest and comparison.** v12 on Flash-Lite fixed 4283's ranges and flagged
its two servings, split 180692 into 18 member rows, stopped inferring 695's
servings, read the basis heading, and completed 758 (26/26 rows). It did not
fix 18102 (members still in form_text), 2502 (still infers 60, though the
label prints only "60 Vegetarian Capsules") or 247106 (35 of 99 rows).
On the four hardest labels under v13:

| | 3.5 Flash-Lite | 3.5 Flash | Gemma 4 26B |
|---|---|---|---|
| Valid drafts | 3/4 | 2/4 | 0/4 |
| 2502 servings not invented | no | yes | - |
| 18102 blend members as rows | invalid | yes (8 + 2) | - |

Gemma 4 31B returned HTTP 500 on every request, including plain text. 3.5
Flash follows the substantive rules Flash-Lite breaks; its two failures are
shapes, not inventions. One persists: 739's servings per container stays a
bare `null` through v12, v14 and v15, so wording does not fix it. It fails
closed. 247106 (99 rows, 11 blends) lists blend headers without members in
both models; OCR reads about 25 row names at this resolution, so the print is
likely too small in a full-page render — a capture problem, not a rule.

Receipts (local, gitignored): `submission_dsld_gemini35lite_v11_all60_20260911/`,
`..._gemini35lite_v12_retest_...`, `..._gemini35lite_v13_hard_...`,
`..._gemini35flash_v13_hard_...`, `..._gemini35flash_v14_hard_...`,
`..._gemini35flash_v15_739_...`, `..._gemma4_26b_v13_hard_...`. None is gold or
qualification. The one-off probe gained a paced, capped, quota-stopping mode;
it is still not a production adapter.

**Resume here:** (1) read `gemini-3.5-flash`'s free-tier limits in AI Studio —
they were not in the recorded dashboard snapshot, and it is the better reader;
(2) decide schema-constrained generation for hosted output, generated from the
existing contract owner rather than a second schema, since wording has stopped
fixing shape slips; (3) if quota allows, run 3.5 Flash on the 60 development
images with the OCR double-check, reusing nothing across configurations; (4)
treat the densest labels as a capture problem (fine print), not a model one.
Do not tune a frozen holdout on these images. Production extraction stays
disabled.

Repeatable diagnostic entry point (new output directory each run):

```bash
~/.pyenv/versions/3.13.3/bin/python scripts/diagnose_dsld_extraction.py \
  --manifest reports/submission_dsld_diagnostic_20260910/diagnostic_manifest.json \
  --output reports/submission_dsld_next_run \
  --raw-root /Users/seancheick/Downloads/PharmaGuide_Datasets/staging/brands
```

Use `--limit` for a bounded development smoke. For a local vision model add
`--provider ollama --model <installed-tag> --model-digest <full-digest>` and
`--endpoint <cloud-disabled-loopback-daemon>`. No models are downloaded and no
queue, approval, gold, catalog or production settings are written.

## What is actually blocking

**Not a blocker for DSLD development diagnostics:** the saved PDF renders and
raw JSON can be compared now. They expose extraction and pipeline problems
without claiming real-world qualification.

**Still required for physical-package qualification:** real bottles, real photographs, and one person deciding that a record
describes the package in their hand. Tools can select candidates, match
barcodes, compare records, generate templates, compute coverage, list
disagreements and score runs. None can make that judgement, and no amount of
model agreement substitutes for it.

## Phase 1 — `import-reference` implemented; assemble and freeze remains

`prepare_holdout_set.py import-reference` writes a proposed gold record from a
confirmed catalog candidate. It must: load the candidate through the existing
identity index; verify the record fingerprint; compare record against the
photographed label; refuse unresolved disagreements; require explicit
physical-label confirmation; write atomically; update the manifest hash; and
leave an immutable audit record of source and reviewer. It imports an
independent transcription and never a draft.

Then: choose a risk-stratified set, photograph every panel, confirm each
edition against the package, settle disagreements, freeze hashes and
attestations. Two human checks for discrepancies, high-risk products and a
random sample regardless of route. Products with no reliable catalog match
take the two-person transcription route.

Measured sourcing notes: `dv_only` is invisible in all 15,103 catalog records
because DSLD carries a quantity for essentially every row, so it must be found
by eye. CFU and AFU exist but are rare and are printed as compound units
("Billion AFU"); the coverage tool now reads those correctly.

**Capture UX runs in parallel here, not at the end.** The preprocessing
measurement says a Facts panel spanning under about a third of the frame loses
dose rows before any model sees them, so framing guidance protects the
benchmark's own inputs. With it: adaptive panel coverage rather than a fixed
checklist, camera/library choice, reusing one photo for several roles, retake
and resume, OCR UPC suggestion with manual entry, and Sentry events.

## Phase 2 — benchmark

RapidOCR and `qwen3-vl:4b` through one `LabelDraftExtractor`. Reported
separately: identity, product name, serving, row presence, dose, unit, blend
parentage, warning presence, warning wording, printed detail, other
ingredients, provenance, abstention. Two denominators each, because fields
within one label are not independent observations. Gates at 100% on dose,
unit, identity, serving, blend nesting and warning presence. A critical numeric or unit error
blocks automation regardless of confidence or agreement between extractors.

Shared preprocessing is tested separately, and independent-extractor agreement
counts as evidence only alongside that test — two readers of one prepared
photograph share its losses.

## Phase 3 — observation mode

Extraction runs in production and approves nothing. Every submission still
gets human review. Grounding and deterministic checks report. Agreement is
measured by field and severity against gold. Shadow samples are compared with
human decisions.

## Phase 4 — selective automation

Only after qualification. Low-risk, independently agreeing fields become
auto-candidates; dose, units, warnings, identity and complex blends stay in
human review. Automated decisions carry a distinct disposition and remain
reversible. Permanent random human sampling continues.

## Phase 5 — promotion and operations

Promotion through the existing clean → enrich → score path, never a second
one, with periodic full-rebuild parity checks proving incremental equals full.
Then the points ledger, scheduled monitoring, certificate re-checks, and
shadow-bank expansion.

## Identity and lifecycle (own batches)

**Canonical identity**, reusing `formula_fingerprint` and `label_record`
rather than a second edition-ID system: optional GTIN, brand, product name,
package/net quantity, manufacturer/distributor, formula fingerprint, immutable
label-edition evidence digest, market status. Product family is separate from
label edition.

**No-GTIN submissions** would use that same record with `identity_pending`:
stronger human review, front label plus Facts plus manufacturer plus net
quantity, no auto-approval, no publication until identity is confirmed, and
the label-edition identity generated only after human verification. **This
reverses the written decision of 2026-09-08 that barcode stays required, so it
needs explicit sign-off before any code moves.** It is one identity system
with an optional GTIN, never a second submission architecture.

**The lifecycle** — draft, submitted, extraction complete, label review,
retake required or label verified, enrichment pending, scored, release
validation, catalog ready, released — is the right shape, and one contract
shared by app, Supabase, worker, console, importer and catalog builder is the
right rule. But states already exist across all six with live data, so this is
an audit of every current state and consumer, then one migration, never a
parallel vocabulary. A verified label must not disappear because enrichment or
scoring fails.

**Certificates** are label claims. Distinguish printed claim, exact product or
SKU verification, brand-only, expired, and unresolved. Evidence contributes to
the verification pillar only and never overrides ingredient safety, dose
warnings, clinical evidence or personal fit.

## Two things this plan will not do

**Thresholds are not chosen from the results.** A gate picked after seeing the
score is not a gate, it is a description. `HOLDOUT.md` freezes gates before
any result and consumes each candidate once. That they are engineering targets
rather than regulatory guarantees is true and already how the protocol reads;
a threshold may be revised for the *next* frozen round through a dated
amendment.

**No second brain.** Every concern keeps one owner: GTIN identity in
`gtin.py`, catalog lookup in the console's identity index, mass-unit spelling
in `normalization.canonicalize_mass_unit`, row reading and text normalization
in `benchmark.py`, label validation in `envelope.py`, approval in the database.
This rule has been broken three times in this work — a second draft-to-label
mapper, a second validator, and a local unit table that missed 820 rows and
hid AFU entirely. Each was deleted rather than kept in sync. A near-duplicate
still stands: `_strip_parenthetical_groups` is nested inside a function in
`enrich_supplements_v3.py` and cannot be imported, so `catalog_gold` has its
own. Lifting it is a change to the enricher and belongs in its own batch.
