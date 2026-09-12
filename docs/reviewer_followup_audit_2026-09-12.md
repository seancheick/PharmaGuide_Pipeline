# Reviewer follow-up audit — 2026-09-12

Audited pipeline changes through `cd76f893` and app changes through `8b8391c`.

## Confirmed fixes retained

- Reviewer extraction reads use the signed-in reviewer's RPC, not a direct
  service-role table read. Production migration presence and execute grants
  were checked; service_role and anon cannot call it.
- Draft saves wait until the saved review has loaded. This fixes a real blank
  draft overwrite that was not addressed by the earlier approved-label loader.
- Sunflower phosphatidylserine aliases are parent-scoped, the inactive closing
  period parser is shared, and proprietary-blend transparency wording lives
  in the canonical scorer. These are not submission-only processing copies.

## Additional defects fixed

- Focus-only raw JSON protection lost unapplied text after blur. Preserve edits
  until Apply or a deliberate submission switch. Unapplied JSON blocks approval
  rather than silently approving the older structured payload.
- A late barcode response could update a different selected submission. Fence
  responses to the request, submission, and evidence revision/manifest.
- Repeating an unchanged barcode check erased its recorded outcome. Retain it
  only for the same identity index and GTIN; changed, blocked, or failed checks
  invalidate it. The existing pre-approval identity recheck remains mandatory.
- The extraction-reader migration was absent from the shared local test chain.
  Add it and exercise permissions, revision/submission isolation, latest-first
  ordering, and the five-draft cap against the actual database function.

Four initial regressions failed before the UI fix; the focused pipeline/import/
mapping/scoring suite then passed 178 tests. The database harness passed 106
cases; the reviewer backend passed 59 tests and type-checking.
The broader console slice passed 104 tests; 11 opt-in local HTTP-stack tests
were skipped (not counted as end-to-end production verification).

## Product/release state at audit time

Production confirms URO approved with payload SHA prefix `7b0243cbbb5d`; its
normal Product_Submissions scored artifact is 78.1/100, scored, SAFE. Adrenal
Complex and Prenatal Advanced remain submitted; Align remains under_review.
No approvals, rejection decisions, images, or product data were changed here.

The user's release process was actively running. No parallel catalog build,
full backstop, or cleanup of its lock/output/imported raw record was performed.
Refresh the console after saving/applying work to load the UI changes; no new
backend deployment is needed for these UI/test fixes. Browser behavior was
verified in executable regression tests, not a claimed manual phone run.
