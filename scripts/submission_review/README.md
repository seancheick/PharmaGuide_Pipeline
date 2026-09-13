# Submission reviewer console

Local web tool for reviewing user product submissions: photos side-by-side,
a structured `manual_label_v1` editor, and the approve / reject / duplicate
decisions — all through the deployed `review-product-submissions` Edge
Function under the signed-in reviewer's own account.

## Run

```bash
bash scripts/submission_review/start.sh
```

Opens the console, starting it only if it is not already up — a second copy
would fail on the port, which reads like the console is broken when it is
merely already running. Takes a port (`start.sh 8899`) and `--no-open` to
print the URL instead of opening a browser. A cold start spends about half a
minute building its identity index before the page answers.

Reuse requires the console's health response to match the current server code.
An unrelated website or an older console is not treated as a successful start.
If the port is occupied, inspect the process shown by the launcher and stop only
the identified old console before retrying. Startup logs are private to your
account; a failed startup stops only the new process the launcher created.

To run the server directly instead:

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

## Solo development: start with one product

Automatic extraction must be explicitly configured and enabled; uploading alone
does not produce a machine draft while it is disabled. Do not enable a general
production queue merely to run a local experiment.

The shared preparer retains `prep_v1` (full-detail baseline). The opt-in
`prep_local_4mp_v1` profile bounds total prepared pixels to four million,
divided equally across **all** evidence photos, without discarding panels.
Set `prep_config_version` in the candidate/leased configuration; both the
development runner and worker use that same profile. Original hashes and exact
resize/crop geometry remain recorded. This is a new, unqualified candidate:
smaller inputs can lose small print and do not guarantee a model will finish.

The OCR reader retries sideways pages in bounded right-angle orientations.
An ambiguous orientation abstains; evidence boxes are mapped back to the
original photo, not shown at coordinates from the rotated reading.

1. Submit the product photographs in the app and run the existing extraction worker.
2. In this console, choose **Load readable fields into the editor**. This starts
   a development review and preserves the untouched machine output.
3. Use **Evidence** beside a row to inspect its source. **Original: supported** means the
   ingredient/amount/unit association has machine evidence; still check the photo.
   These badges describe the untouched machine reading, not later edits.
   **Original: check this** and **Original: not checked** require your own reading. Old extractions
   remain usable and show Not checked until extracted with the new verifier.
4. Edit incorrect values or printed forms, **Confirm** each checked row, and
   **Remove** invented rows with a reason. Add any missed rows with the existing
   ingredient controls. Use these controls during a development review; advanced
   JSON replacements that cannot be mapped unambiguously cannot produce a report.
5. Check the complete-label checkbox and **Save development report**. Download
   the summary and CSV. Your normal approval process is unchanged; the report can
   also be saved after approval while the development review remains open.

Completed records are private local files in `reports/submission_solo/`.
Saving rechecks your reviewer access and binds the original draft, mapper output,
and grounding to the stored extraction and evidence revision. Reports include
only the signed-in reviewer's records; browser-supplied verification cannot replace
the stored machine report.
The report uses each product's latest completed review. Working review marks
are session-local: save your completed report before switching products or
closing the page. The server still saves label corrections through its existing
workflow. Timing excludes hidden/unfocused windows and inactivity after 30 seconds;
use **Pause timer** for deliberate breaks. These are single-reviewer development
results, not a qualified accuracy claim or independent gold standard.

The app migration `20260913010000_submission_row_grounding.sql` exposes only the
grounding report through the existing reviewer-only RPC. Apply it to the review
backend before expecting row evidence; it makes no approval-policy changes.

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
