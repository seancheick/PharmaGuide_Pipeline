# Complete submissions without a verified GTIN

Status: approved by Sean October 26, 2026, with four review amendments below. Implementation authorized, including tests, adversarial review, fixes and commit/push/merge. Real pipeline/catalog/App Store publication remain excluded.

## Goal and scope

A contributor holding the Natgrown bottle bearing `X002FLZ3X7` can submit its complete label evidence, resume after interruption, answer requested retakes, complete audited identity review, and produce an importable catalog product without inventing a UPC. The published product is discoverable by name and brand after Sean runs the catalog pipeline.

Sean selected submission, review, import and name search first. Alternate-code scanning, public alternate-code mappings, automatic FNSKU/ASIN classification, and a new product-identity registry are excluded. The existing numeric scanner continues to resolve only validated GTINs. No corpus run, production catalog publication or App Store release is part of implementation delivery. Publication behavior is proved with isolated fixtures; actual catalog publication remains Sean's later operation.

The actual Natgrown code is an identifier regression case, not proof of its ingredients, dose or manufacturer UPC. Its real approval still requires complete source label photographs; never fabricate those facts from the product name.

## Alternatives considered

1. Complete the existing submission lifecycle with optional GTIN and private observed-code evidence — recommended and selected scope. Extends current owners, supports legitimate bottles, retains human identity verification.
2. Capture-only intake held for a future resolver — smaller but leaves the product unable to complete review/import; does not satisfy the requested outcome.
3. Complete intake plus verified alternate-code lookup — adds public mappings, issuer/marketplace scope, ambiguity and scanner-format handling. Deferred explicitly by Sean.

## Owner check

Owner: `scripts/submission_review/gtin.py` — numeric comparison/check-digit policy; evidence: `rg -n 'def .*gtin|def .*upc' scripts` and current helper definitions. Extend this owner for exporter formatting validation rather than add another numeric policy. Preserve explicit detected UPC-E interpretation separately from established GTIN normalization.

Owner: app `lib/services/gtin.dart::GtinIdentity`, `lib/services/gtin_ocr_service.dart`, `lib/features/contributions/add_missing_product_sheet.dart`, `product_submissions_screen.dart`, existing capture/draft/intent services — evidence: searches for normalized_upc, prepareRetake and identity capture callers. Numeric parsing remains strict; submission identity becomes an explicit optional-GTIN structure carried by existing draft/intent owners.

Owner: existing `product_submissions`, reviewer draft/match-check/evidence rows, `product_submission_review_target_key`, approval revision snapshots and review-transition RPCs; reviewer Edge `match.ts`; pipeline `scripts/submission_review/serve.py::IdentityIndex` and existing console identity controls; importer `scripts/product_submission_import.py::build_manual_label`. Evidence: source-of-truth matrix/glossary search, RPC migration definitions and named callers. No alternate product-identifier owner is currently present in these searched submission seams.

Will NOT create another review engine, photo store, contribution ledger, scoring path, public lookup registry, product-ID scheme or release path. Existing `PG_SUB_<submission UUID>` remains stable.

## Proposed contract decisions requiring approval

- Keep `normalized_upc` as an optional check-digit-valid numeric GTIN candidate. It never holds letters, an invented fallback, a SKU, or a lot number.
- Extend the submission's existing private identity evidence with one structured identifier object: exact observed code (nullable when no code exists), contributor classification (`other`/unknown initially, with reviewer classification permitted), relevant issuer/scope if known, contributor brand/name and optional listing URL. Field names must reuse existing source fields where the implementation census finds an owner; no duplicate short/long labels.
- Preserve the observed text exactly, including case and meaningful punctuation. Validate size/control characters without silently rewriting the value; reject unsupported content with a visible error. A reviewed classification is distinct from an unverified contributor hint.
- Extend the existing match-check owner with an explicit label-review method and a reason-backed `new_product_verified` outcome for a sufficiently documented distinct product without GTIN. Existing GTIN `no_match_verified` semantics remain unchanged. No GTIN lookup result, empty search result, unknown code, or contributor assertion can generate the new decision automatically.
- Add a versioned identity section to the existing canonical approved-payload contract so the existing payload hash binds the identifier decision, chosen association/GTIN, evidence revision and relevant reviewer verification. Do not introduce a second approval hash. Existing versioned payloads/approvals remain valid and immutable; new no-GTIN approvals require the new contract. Keep legacy export fields for numeric approvals and reject contradictory mirrors.

## Concrete persisted representation

Add `identifier` JSON to the existing private submission/evidence-revision records, with exactly these contributor fields: `observed_code` (string up to128 characters or null), `code_type` (`other`, `amazon_fnsku`, `amazon_asin`, `manufacturer_sku`, `retailer_sku`, `lot` or `none`; contributor hint only), `issuer` (string up to200 or null), `brandName` and `fullName` (existing field vocabulary; required nonempty strings up to300), `listing_url` (HTTP(S) URL up to2048 or null), and `no_code` (boolean). No code means observed_code=null, code_type=none, no_code=true; supplying a code requires no_code=false. Reject contradictory states. Preserve exact text; reject control characters instead of silently stripping them. Optional empty strings become null only in optional metadata, never by rewriting an observed code. A real numeric GTIN path may omit this object for legacy compatibility.

Freeze this object into the existing evidence revision manifest. A no-code declaration belongs to that revision; it cannot waive a later revision's code evidence or be changed without invalidating verification. Retakes retain or replace it explicitly, using the same existing evidence revision owner.

Extend the existing match-check record with `identity_method` (`gtin` or `label_review`), nullable canonical_gtin14 for label_review only, and `identifier_decision` JSON: `code_type` (reviewed classification), `issuer` (reviewed scope or null), `verified_gtin` (validated numeric string or null), `package` (required reviewed package/size description up to300 for label_review), and `reason` (required substantive identity rationale5–2000 characters). Existing `outcome`, matched/candidate product IDs, index revision and evidence binding remain their current owners. The record's reviewer is authenticated server provenance, never supplied as a contributor field.

New approvals use schema_version=`manual_label_v2` with canonical JSON exactly `{label: <existing manual_label_v1 label object>, identity: {observed: <frozen contributor identifier object or null>, decision: <frozen reviewed decision>, identity_method: <method>, outcome: <match outcome>, matched_dsld_id: <ID or null>, correction_target_dsld_id: <ID or null>, edition_of_dsld_id: <ID or null>, evidence_revision: <integer>, evidence_manifest_sha256: <hash>, match_check_id: <existing bigint as JSON integer>}}`. Required keys are explicit and nullable only as described; unknown keys fail validation. Legacy manual_label_v1 remains accepted under its current numeric requirements. Decisions with a verified GTIN must match normalized_upc exactly under existing GTIN equivalence, and association mirrors must agree with the envelope. Database approval constructs/binds this envelope from stored verified rows rather than trusting contributor or arbitrary reviewer JSON flags.

Hash/validate the entire private canonical v2 envelope with the existing payload_sha256. Then the importer extracts ONLY envelope.label, validates that with the existing label validator, and explicitly projects permitted label fields into the manual label. Never spread the whole envelope into a public artifact. The existing public approval digest is deliberately retained as a hash-only audit commitment for current provenance/release consumers; it is not an alternate lookup identifier or an anonymity guarantee. Raw observed identifiers, URLs and rationale remain private. This explicit digest policy is part of the contract being proposed for Sean's approval; no new public field or second approval hash is added.

Before implementation, complete the target-field census. Widen the existing selected/matched/correction/edition catalog-ID validators consistently across SQL, Edge, console and importer from digits-only to the already-established product ID grammar: numeric IDs or `PG_SUB_[0-9A-F]{32}`. Keep existing field names and meanings; never accept arbitrary strings or create a second target field. This is necessary to associate an unnumbered bottle with an existing submission-origin product.

## Contributor flow and lifecycle

The normal entry keeps its strict UPC/GTIN field. Add “My code contains letters / I can’t find a UPC.” The alternative collects the printed code if available, brand and full product name, optional listing URL, and the existing package/label photographs. The user can choose “Other / not sure” and is never required to know FNSKU terminology.

The existing barcode evidence category covers the alternate printed-code photo as well as numeric barcode photos. For a genuinely absent code, record an explicit no-code declaration and require adequate package evidence; do not require a fictitious barcode photo or waive Supplement Facts, ingredients, directions or warnings. Evidence completeness stays in the existing shared manifest/finalization owner, with identical rules in capture and backend.

The contributor's entry is evidence, not product verification. No-GTIN entry does not assert catalog absence. Catalog matching remains available when a validated numeric candidate exists. For alternate/no-code input, capture continues to human review without pretending that an exact GTIN lookup occurred.

Use the existing submission UUID as the lifecycle anchor: initial capture, consent, saved photos, sign-in continuation, retries and retakes retain it. Draft matching must not collapse all missing-GTIN records or merge equal observed codes. Old numeric drafts/intents remain readable. Error/retry paths preserve the original code and photos; server failures cannot turn the attempt into new intake with a different UUID.

Requested and interrupted retakes load by submission UUID and evidence request/revision, not by reconstructing identity from a UPC. The existing prepareRetake/submitRetake and evidence revision owners are extended, not replaced.

## Reviewer flow and coordination

The existing console shows the exact observed code, classification, contributor identity hints and associated photos. A syntactic X-prefix is not proof of Amazon provenance or a product association. Listing links are displayed as untrusted references, never fetched by privileged backend code.

Extend the current identity index/search service to expose name/brand candidates from both released catalog and full indexed corpus. Include source revision/freshness and bounded candidate IDs in the existing evidence-bound match receipt. Reviewers must examine label/package/formulation differences; a fuzzy or empty result is not proof of absence. Stale or incomplete indexes prevent a final identity decision rather than silently authorizing a new product.

Reviewer outcomes:

1. Verify a manufacturer GTIN from evidence; validate it, rerun exact matching, and choose the existing same-product/correction/edition outcomes.
2. Associate the label with an existing catalog product after verification, including existing PG_SUB products, using the current association owner. Preserve correction-versus-edition semantics.
3. Record explicit `new_product_verified` without GTIN after checking complete label evidence and name/brand candidates, with a required identity rationale and fresh checklist. Ambiguous/unresolved identity remains blocked from approval.

Extend `product_submission_review_target_key` and the existing conflict-check owner. Retain existing catalog/GTIN targets; for no-GTIN proposals compute `label:<normalized brandName>:<normalized fullName>` from verified label fields. Normalization here is Unicode NFC, lowercase and collapse whitespace; it is solely a coordination bucket, never product identity equivalence. Package/formulation differences are checked from the frozen label plus reviewed package description. Same-name different formulations require an explicit existing separate-edition decision, not an automatic merge or an unreviewed bucket escape.

Because one product can move between these keys, all identity-changing approval, reopen and GTIN/association correction transactions acquire one shared transaction-scoped identity advisory lock first, before submission row and sorted target locks. This is a short database-only serialization fence for a solo-review workload, not a new queue/registry. No image upload or remote index request occurs while it is held. Extend existing transition owners consistently to preserve a single lock order.

Inside that transaction, recalculate current and prior-approved target bindings, and query currently pending-approved submissions plus released catalog candidates for the selected catalog ID, verified GTIN and coarse label bucket. Compare this exact candidate set to the evidence-bound reviewed receipt; a newly conflicting pending approval or changed target rejects the attempt and requires refresh/review. Retain existing index freshness checks. Two submissions sharing a currently known ID/GTIN/bucket cannot approve under independent locks, and moving a correction between keys cannot bypass its old binding. Different issuers' equal code strings never participate in this key or cause a merge. Manual review cannot guarantee detection of every differently named duplicate; the product must not claim that a name search proves global absence.

Later identity changes use reopen/reapprove on the same submission. A newly verified UPC requires an exact conflict check before approval; it never silently remaps the existing stable product ID. If exact matching returns only the same PG_SUB or no conflict, keep the established product ID. If a different released product matches, block the revision and retain the old released record. Do not reassign that published PG_SUB, create an alias, migrate saved/stack references or apply its correction to another product in this feature. Any eventual merge/reassociation of two already-published identities requires a separately specified resolution; an initial unpublished submission can still select an existing product normally. Previous released metadata remains active until a valid correction ships.

## Backend, importer and export

Use a new forward migration and extend existing RPC owners and OAuth/reviewer checks. Old numeric clients remain compatible; no ambiguous RPC overloads, loose direct table writes or broader grants. Inspect current deployed/source wrapper signatures before choosing the optional argument shape. User-provided classifications cannot attest reviewer verification.

Private observed identity and verified decisions are frozen in immutable numbered approvals alongside the existing evidence manifest. Editing identity invalidates related match receipt and checklist attestations. Reopening, purged evidence replacement, cleanup, lost-response idempotency, stale revision/hash checks, account deletion and one-time points preserve the repaired contracts.

Extend the service export and importer pinned schemas together. A null GTIN is accepted only for the new approval contract with an authorized, evidence-bound reviewed identity decision. Reject legacy missing-product null GTINs, malformed/conflicting fields and stale revisions. Retain exact-revision image/download/promotion fences and journal recovery.

Manual labels retain stable PG_SUB IDs (or an explicitly reviewed existing target) and omit UPC when unknown. Different no-GTIN products do not share blank-key collision ownership. A later verified UPC changes the reviewed identifier, not the established ID; conflicts fail closed.

Strip private observed codes, listing URLs, contributor identity metadata and reviewer rationale before public manual-label/catalog/repository artifacts. Keep needed private approval import receipts in existing ignored private staging. Only the reviewed GTIN, ordinary product label identity and existing hash-only approval provenance enter public catalog fields. No new public alternate-identifier mapping is exported.

The current product catalog supports identity/name independently of UPC. Verify core export, search hydration, Flutter name/brand search, detail routes, saved/stack references and null UPC parsing with a fixture that traverses actual clean/enrich/score/export consumers. No consumer may filter out a reviewed product solely because UPC is absent.

## Eliminate lossy numeric conversion

Observed probe of current exporter: X036000291452 becomes036000291452;036000291453 is accepted despite invalid checksum. Neither implies that a real published record is corrupted.

Route export normalization through the existing numeric policy: allow only explicitly supported whitespace/hyphen formatting, then validate width/check digit. Reject letters before removing any formatting. Keep UPC-E expansion only where its detected/ambiguous representation is explicitly handled by the existing GTIN owner; never reinterpret an established EAN-8 silently.

Remove digitsOnly input behavior that deletes pasted letters before validation. The numeric entry should retain invalid text long enough to explain the error or offer alternate-code entry. OCR must use alphanumeric token boundaries and the shared parser; neither labeled nor fallback extraction may extract a valid numeric substring from X036000291452 or036000291452X. Audit other normalization callers and fix the same defect class at its actual owners, with focused regressions.

## Acceptance and verification

- Numeric GTIN controls retain leading zeroes, valid check digits, EAN-8/UPC-E interpretation, unique and ambiguous catalog behavior.
- X002FLZ3X7 survives input, drafts, sign-in continuation, upload, review and approval intact. Same code under different issuers/products never causes an automatic merge.
- X036000291452, trailing-letter variants, OCR tokens and invalid-checksum controls never become GTINs. Formatting-only numeric controls still work.
- A no-GTIN fixture completes submit, interrupted resume, requested/interrupted retake, evidence verification, reviewed identity, approval, image retrieval, materialization, isolated export/publication, name/brand lookup and product detail. No runtime owner is mocked away at the integration boundary under test; external services may be simulated.
- Two different no-GTIN products remain distinct; same reviewed coordination bucket serializes conflicting approvals; existing catalog and pending-approved candidates are covered.
- Learning a GTIN later preserves product/submission IDs, immutable approval history, one-time points and old released availability. Existing-ID conflicts and stale concurrent approval/reopen/publication attempts refuse safely.
- Purged/replaced photos, authorization/OAuth restrictions, oversized input, legacy/null parsing, interrupted importer writes and approval withdrawal remain covered.
- Prove private observed codes/URLs/rationale do not enter public manual labels, blobs, core DB or source-control diff.

Use fail-first owner tests, named pipeline suites through scripts/test.sh, SQL/Deno/Flutter owner/consumer tests, the canonical migration assembly/disposable replay and applicable local rung. Measure numeric-normalization deltas with bounded frozen affected/control label replay; do not regenerate the corpus. Add real flow tests and iOS26+ screenshots for the new entry UI, then independent adversarial review and exact candidate CI in both repositories. Fix accepted findings before merging under existing authorization.

Before approved backend deployment, confirm no active pipeline/release, assemble migrations from pinned merged commits, inspect dry run, deploy forward migration then affected Edge functions, and run schema/grant/health/stale refusal and unchanged prior-business checks. Do not reopen an unrelated real submission or award test points in production. Actual catalog and App Store publication remain excluded.

## Approved review amendments (October 26)

1. Catalog activation and every active search-generation mutation take the shared identity transaction lock before row/manifest locks. Both activation→approval and approval→activation orderings revalidate complete relevant candidate sets, including empty/unrelated release approval lists. A conflicting new generation must refuse activation or make the affected pending approval ineligible for promotion without mutating its immutable snapshot. Test with two connections; keep revision/hash fences.
2. Existing PG_SUB target support includes39-character length limits and lineage. B correcting A's product keeps A's established PG_SUB ID and `pharmaguide_submission:<A UUID>` lineage while B supplies new approval/evidence provenance. Audit every target validator and downstream consumer, not just the regex.
3. Frozen v2 `identity.decision.verified_gtin` controls export; normalized_upc is equivalent or both null. Never fill null from mutable parent candidate. Import rejects null/numeric or mismatched contradictions.
4. Transport retry, interrupted capture, sign-in continuation and requested retakes keep UUID. Explicit resubmission after rejection keeps the existing new UUID plus resubmissionOf link; include no-GTIN rejected-resubmission coverage.

Encode normalized brand/name pairs unambiguously (canonical JSON array plus namespace/hash, never delimiter concatenation). A limited suggestion page is not the full conflict set: enumerate exact relevant conflicts or fail closed before finalization. Record accepted ownership and contract decisions in source_of_truth_matrix.json, an accepted ADR and the app architecture decision owner. No additional approval needed for implementation details within this contract.
