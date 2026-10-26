# ADR-0006 — Observed identifiers are evidence; reviewed identity owns publication

**Status:** Accepted by Sean, 2026-10-26, including activation/lineage/null/rejection amendments.
**Matrix concepts:** submission_product_identity, approved_submission_label_contract.

## Ownership and scope

The app's existing submission, evidence, match-check and approval RPCs own identity review. `product_submission_review_target_key` owns target coordination; catalog activation participates in the same identity concurrency control. The pipeline importer owns validation and private-to-public projection of approved labels. Existing `GtinIdentity` and Python `scripts/submission_review/gtin.py` own numeric interpretation; consumers do not delete letters before validation.

Support a complete no-GTIN submission lifecycle and normal product name/brand discovery after publication. Alternate-code scanning and public alternate-code lookup mappings are excluded. Existing evidence storage, review engine, approval revisions, product IDs, release gates and contribution ledger remain the owners.

## Private identifier contract

Existing submission/evidence records gain `identifier` JSON, optional for legacy numeric intake:

- `observed_code`: exact string, maximum128 characters; or null only for no code.
- `code_type`: contributor hint, one of other, amazon_fnsku, amazon_asin, manufacturer_sku, retailer_sku, lot, none.
- `issuer`: nullable string maximum200.
- `brandName`, `fullName`: required nonempty strings maximum300, reusing label vocabulary.
- `listing_url`: optional HTTP(S) string maximum2048; untrusted evidence, not a privileged fetch target.
- `no_code`: boolean; true exactly when observed_code=null and code_type=none.

Preserve observed text/case/punctuation; reject control characters and oversize input rather than truncate/filter it into another identifier. A contributor hint cannot attest reviewer verification. Freeze this object and no-code declaration into the existing evidence revision/manifest. No-code waives only barcode evidence for that revision; it never waives required label evidence. No-GTIN drafts/intents are keyed by submission UUID, never a shared blank identifier or unverified SKU.

The existing match-check owner adds identity_method gtin|label_review and nullable canonical_gtin14 for label_review only. Its identifier_decision contains reviewed code_type, nullable issuer, nullable check-digit-valid verified_gtin, reviewed package description (required for label_review, max300) and substantive identity reason5–2000 characters. A new_product_verified outcome is an explicit reviewer decision after complete candidate review; neither unknown code nor an empty suggestion page authorizes it. Existing no_match_verified remains a GTIN decision. Match-check IDs retain their existing bigint type, represented as JSON integers; no new UUID owner.

## Immutable approval/export contract

New manual_label_v2 canonical payload:

```
{label: <manual_label_v1 label object>,
 identity: {observed: <frozen identifier or null>,
   decision: <frozen identifier_decision>, identity_method, outcome,
   matched_dsld_id, correction_target_dsld_id, edition_of_dsld_id,
   evidence_revision, evidence_manifest_sha256, match_check_id}}
```

The database binds the identity portion from stored reviewer/evidence facts. The existing canonical payload hash covers the entire envelope; no second approval hash. Historical v1 approvals stay immutable/valid under their existing numeric rules. A v2 export's normalized_upc is authoritative from the frozen reviewed decision: equivalent to verified_gtin or both null. Mutable parent candidates cannot fill an unverified/null GTIN. Contradictions fail import.

The importer validates the entire envelope/hash, then explicitly selects `label` before existing label validation/materialization. Never spread identity metadata into public manual labels. Raw observed codes, URLs and rationale remain private. Existing public hash-only approval provenance remains a deliberate audit commitment needed by release consumers; it is not an alternate-code lookup key or an anonymity guarantee.

Existing association fields accept numeric catalog IDs and PG_SUB_ plus32 uppercase hex characters (39 characters); all bounds and consumers agree. B correcting A's submission-origin product preserves A's PG_SUB product ID and pharmaguide_submission:A-UUID lineage, while B is the new approved evidence source. Adding a GTIN later keeps this identity only when there is no other published-ID conflict. A conflict blocks correction/promotion, retains the released record, and requires a separately scoped published-identity resolution; no incidental ID remap, alias or saved-reference migration.

## Concurrency and candidate completeness

Identity approval/reopen/edits, catalog activation and active search-generation mutations acquire one shared identity transaction advisory lock before row/target/manifest locks. Use existing transaction owners, not a new queue. No network/image upload occurs under the lock.

No-GTIN brand/name coordination uses normalized NFC/lowercase/collapsed-whitespace pairs encoded unambiguously (canonical JSON pair/hash), never colon concatenation or a raw code as product identity. This is a conservative conflict-review bucket, not an automatic merge. Existing catalog and GTIN target keys retain their semantics.

Under lock, revalidate complete relevant released and pending-approved candidates against the reviewed generation/set, including old and newly selected bindings. Limited suggestions are not completeness proof. Both activation-first and approval-first orderings must fail closed on new conflicts, even when the release approval list is empty or unrelated. Refuse conflicting activation or block affected stale approvals from promotion without modifying immutable snapshots. Revision/hash release fences remain necessary and mandatory.

## Lifecycle compatibility and verification

Transport retries, interrupted captures, sign-in continuation and requested retakes retain UUID/evidence lineage. Explicit resubmission after rejection preserves the existing new submission plus resubmissionOf link; no-GTIN paths support both behaviors.

Required evidence: real-owner synthetic lifecycle through isolated export/name search; numeric/letter/OCR controls; no-GTIN recovery and retake/rejection flows; two-connection activation conflicts with empty/unrelated approval lists; stable PG_SUB lineage/later-UPC controls; privacy projection; stale approval/image/promotion refusal; historical and one-time-points compatibility. No actual catalog/App Store publication is implied by source qualification or test fixtures.
