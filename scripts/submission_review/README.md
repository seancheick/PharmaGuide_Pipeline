# Submission reviewer console

Local web tool for reviewing user product submissions: photos side-by-side,
a structured `manual_label_v1` editor, and the approve / reject / duplicate
decisions — all through the deployed `review-product-submissions` Edge
Function under the signed-in reviewer's own account.

## Run

```bash
SUPABASE_URL=... SUPABASE_ANON_KEY=... \
  python3 scripts/submission_review/serve.py \
  --catalog-db scripts/dist/pharmaguide_core.db
```

Open http://127.0.0.1:8765/ — the server binds loopback only.

Both env vars also load from the repo `.env`. The anon (publishable) key is
the public client credential; the service key is never used here.

## Sign-in

Passwordless, same as the app: enter the reviewer email → a 6-digit code
arrives by email → enter it. Requirements:

- the account exists in the project (`shouldCreateUser: false` — the console
  never creates accounts);
- the account's **user id** is listed in the Edge Function's
  `PRODUCT_SUBMISSION_REVIEWER_IDS` secret (comma-separated uuids);
- the project's magic-link / OTP email template includes `{{ .Token }}` so
  the 6-digit code is actually delivered.

## Review flow

1. **Queue** (left): open submissions, oldest first; filter by status/kind.
2. **Evidence**: photos render in capture order with their evidence-category
   tags. Click to open full size. Signed URLs live 5 minutes; the console
   refreshes them automatically while a submission is open.
3. **Label**: fill brand/name/servings + the ingredient rows table (or edit
   the raw JSON). Every declared row on the label goes in — dose accuracy
   here feeds real safety math. The advisory sha preview is informational;
   the server recomputes and enforces its own canonical hash.
4. **Decide**:
   - *Start review* → `under_review` (approval is only reachable from here);
   - *Approve* → submits the payload; the pipeline picks it up on the next
     release (`--fetch` → clean → enrich → score → build → promote);
   - *Reject* → requires a resolution code; `other` requires a user-facing
     detail (≤280 chars, shown verbatim in the app);
   - *Duplicate* → `already_in_catalog` takes a catalog `dsld_id` (use the
     built-in catalog search), `duplicate_submission` takes the approved
     twin's submission uuid.

Every transition pushes a generic notification to the submitter's devices
and is recorded in the immutable review-event audit trail.

## Review SLAs and judgment calls

- Reject with a *retakeable* code (`photo_quality`, `missing_panel`,
  `label_unreadable`, `product_identity_mismatch`) whenever better or
  product-matched photos would fix it — the app tells
  the user exactly what to redo.
- `not_a_supplement` is for food, cosmetics, medical devices, and drugs.
- When the label shows a product the catalog already has, prefer
  `already_in_catalog` with the dsld id — the user gets a link instead of
  a dead end.
- Approving writes catalog data consumed by safety scoring: transcribe
  doses and units exactly as printed; blend headers and nested rows follow
  the `manual_label_v1` conventions (see
  `scripts/product_submission_import.py`).
