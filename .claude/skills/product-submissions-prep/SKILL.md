---
name: product-submissions-prep
description: Prepare PharmaGuide product submissions for the human reviewer. Transcribe each new submission's label from its photographs into the reviewer console (agent_reader fetch/record/save), so the reviewer only opens, compares, ticks five fields and approves; also operate the machine extraction queue (preflight, status, drain, reconcile). Use it whenever someone mentions new submissions, pending or waiting products, transcribing labels, the reviewer console, getting submissions "ready to approve", the extraction worker or queue, or says product-submissions-prep, even if they never name the skill.
---

# Product submissions prep

A user photographs a supplement the catalog lacks. Before it can ship, a
human reviewer approves a label transcribed from those photographs. This skill
does everything up to that approval, so the reviewer's whole job is: **open,
compare each field with its crop, tick five fields, approve.**

Accuracy beats speed on every call. The catalog feeds safety verdicts and
scores; a wrong dose or a missed form becomes a wrong warning in someone's
hand. A field you leave empty and flag costs the reviewer ten seconds. A
plausible wrong value costs a patient.

## What you never do, and why

- **Never tick a field confirmation, approve, reject, or resolve a duplicate.**
  Those are the reviewer's attestations. The console keeps them as the
  reviewer's clicks; nothing here has a command for them, and there is no
  workaround worth looking for.
- **Never invent or infer a value.** Copy what is printed or leave it out.
  No dose back-calculated from a %DV, no unit "fixed" because it looks odd, no
  guessed digit, decimal point or punctuation mark. Unreadable is an answer.
- **Never fill a gap from a sibling SKU, the DSLD record or the web.** Those
  are cross-checks of identity at most. The photograph is the only source.
- **Never print submission ids, user ids, photo URLs or tokens.** Terminal
  output gets pasted into chats. Use aliases (`S18`).
- **Never touch another agent's work.** Work in your own branch/worktree,
  stage only your own paths, commit nothing you did not create.
- **Never put a photo, crop or viewer inside the repository folder**, not even
  a gitignored one. Scratch lives in `/tmp/pg_submissions/<alias>/`.

Photographs may be opened by hosted models (owner's decision, 2026-09-27):
looking at the photo yourself is the most accurate reader available.

**This job needs a model that can see images.** Before anything else, open
one fetched photo and describe it in one line. If you cannot view it, stop
and tell the owner. Do not build viewers or read the label through OCR and
pixel tricks instead: on 2026-09-28 an agent that could not see spent over
two hours that way and still left two defects a look at the photo would have
caught (a dropped Other Ingredients list, a truncated barcode).

## Setup

Run from the `dsld_clean` repository root.

```bash
source scripts/python_env.sh                 # sets $PG_PYTHON (Python 3.13)
set -a; source .env; set +a                  # agent_reader reads the keys from the environment
export PG_REVIEWER_EMAIL=<reviewer account>  # ask the owner if it is not set
R="$PG_PYTHON scripts/submission_review/extraction/agent_reader.py"
```

Use `$R` unquoted (`"$R"` is one command name and fails; in zsh, which the Bash tool
is, write `${=R}`), and run every
Python helper of your own with `$PG_PYTHON`, never bare `python3` (on this Mac
that is Xcode's interpreter, without the repo's packages).

`.env` must hold `SUPABASE_URL`, the anon/publishable key and the service-role
key. It is gitignored, so a fresh worktree has none: symlink the main
checkout's (`ln -s <main checkout>/.env .env`). Requests run as `PG_REVIEWER_EMAIL` until a machine reviewer account
exists. Work files go to `/tmp/pg_submissions/<alias>/`
(`PG_SUBMISSION_WORKDIR` overrides).

## Transcribing new submissions

### 1. See what is waiting

```bash
$R list
```

Only open submissions are listed, each with what already exists, e.g.
`[draft agent/<model> v3 · saved review]` or `[no draft · blank saved review]`.

- An agent draft plus a saved review may be finished: run `$R verify SNN`.
  If it says READY, skip it. Redoing finished work is the costliest mistake
  in this job, and a second reading only muddies the draft the reviewer sees.
- A **blank** saved review is the console's empty form, saved when someone
  opened the submission before any reading existed. It is nobody's work;
  transcribe normally and `save` replaces it.
- Any ticks: the review is the reviewer's. Leave it alone.

### 2. Fetch evidence and the OCR lead

```bash
$R fetch S18 S19
```

Per submission: `photos/NN_<category>.jpg` (hash-checked against the
evidence), `photos.json` (photo number → `photo_id`), and `reading.json`, an
OCR machine reading in draft format. **The OCR reading is a lead, never the
answer**: it misreads small print, splits lines, and drops columns. A second
`fetch` refreshes the photos but keeps an existing `reading.json` (someone's
work); `--force` replaces it with a new OCR lead.

### 3. Read the label properly

Open every photo yourself at full resolution and read every panel: front
(brand, product name), Supplement Facts (serving size, servings per
container, every row with amount, unit and %DV), Other Ingredients,
directions, warnings, storage, distributor, certifications.

For anything small, ambiguous or dense, look closer before you write it:

- crop and enlarge the region (e.g. PIL: `Image.open(p).crop(box).resize(...)`)
  and view the crop, rather than reading a dose off a shrunken whole photo;
- run a second engine as a cross-check: `tesseract <photo> stdout --psm 4`;
- where OCR and your reading disagree, look again at the crop: the photograph
  decides, not either reader.

Rejoining fragments of a line by hand is where transcription errors are
born, so re-read a whole line or block as one crop instead.

Time-box a stubborn glyph: one zoomed crop and one tesseract pass. If it is
still ambiguous, mark the field `partial` (or leave it out) and flag it.
Pixel forensics, glyph-width measurement and curve straightening are not part
of this job. Dash style (`-` vs `–`) does not matter. A barcode is copied only
when every digit is crisp, including the leading zeros (Trader Joe's prints 8
digits, e.g. `0067 1422`); otherwise leave it null: the console checks the
barcode against the catalog itself.

### 4. Write `reading.json`

Correct the OCR lead in place until it says exactly what the label prints.
The draft format and the per-field rules are in
[references/label-conventions.md](references/label-conventions.md); read it
before your first submission. The essentials:

- every field is `{value, status, confidence, sources}`; `status` is `read`,
  `partial`, `unreadable` or `not_present`, and only `read`/`partial` carry
  a value;
- every `read`/`partial` value names its source: `photo_id`, the exact printed
  `supporting_text`, and a `region` (normalized 0–1 box on that photo) that
  becomes the crop the reviewer compares against, so draw it tight;
- one row per printed line; a printed "(as X)" goes into `form_text`; only a
  blend header has children (`parent_index`).

Then check every box you drew:

```bash
$R sheet S18        # writes regions_sheet.png: one labelled crop per cited region
```

Open the sheet and look at each crop. Each one becomes the image beside the
reviewer's tick; a box that shows the neighbouring line, or clips the start of
a sentence, makes a correct value look unsupported. Redraw and re-run until
every crop shows exactly its text. (On the first live run this caught two of
twenty boxes.)

### 5. Record the draft

```bash
$R record S18 --model <your model id, e.g. claude-opus-5-5 or gpt-5-codex>
```

This refuses a malformed reading (with the exact path) and convention
defects: a printed "(as X)" with no `form_text`, a %DV read as an amount, a
read Other Ingredients list not disclosed as `present` (it would be dropped
from the label), and a "read" barcode that is not a whole GTIN.
Then it runs the deterministic checks and an **independent OCR grounding**
pass, records the draft, and writes `label.json` + `unresolved.json`.

Every `re-read <field>` line means independent OCR could not find your quote
on your cited photo. Expect many on curved, glossy bottles: on the first live
run the checker read three lines off a perfectly legible Supplement Facts
panel, and it drops printed symbols such as ™ (so `NORTH STAR LABS™` never
matches `NORTH STAR LABS`). So a low score is not proof you are wrong, and a
high one is not proof you are right. What it demands is that you re-open
each listed field zoomed, confirm it character by character (tesseract on the
crop is a good second opinion), and report the grounded count honestly.
Never trim or bend a quote to make the checker pass: the quote is what the
label prints. Fix `reading.json` and `record` again only if the photo shows
you were wrong; a new record replaces the old draft.

### 6. Complete `label.json`

`label.json` is the reviewer's label, pre-filled from your reading.
`unresolved.json` lists what a draft cannot carry. Add, never change:

- `ingredientGroup` on every row, `physicalState`, statement types, daily
  servings, serving unit/quantity when the draft only had text. Rules in the
  reference file;
- if a value the reading supplied is wrong, the reading is wrong: fix
  `reading.json` and `record` again. `save` refuses a `label.json` that
  changes the reading, so the draft beside each tick and the label agree.

### 7. Save

```bash
$R save S18
```

It checks the label against the reading, the catalog importer and the server
validator, then saves the review. Zero diagnostics or it does not save.
Then read back what the server holds:

```bash
$R verify S18 --model <your model id>   # must end "READY for the reviewer"
```

A submission is done only when `verify` says READY. Paste its output in your
report.

### 8. Hand over

The reviewer opens the console (`bash scripts/submission_review/start.sh`,
http://127.0.0.1:8765). Opening a prepared submission records a clean barcode
check, preselects the front photo and starts the review by itself; beside each
Confirm tick it shows your quotes and a crop of your region. A barcode already
in the catalog is left for the reviewer: say so.

Report, then stop:

1. table: alias · brand · product name · rows with amounts · serving
   size/unit/per container · physicalState · findings · grounding (n/m);
2. anything unreadable, what you did (zoomed, second engine, left empty) and
   which fields are lower confidence;
3. judgment calls, flagged as such (daily servings, ingredientGroup,
   physicalState, statement types);
4. confirmation that nothing was ticked, approved or committed outside your
   own branch.

## Operating the extraction queue

The machine worker drafts submissions on its own, under its own account, when
the owner has enabled it. You only run it within caps and report.

```bash
python3 scripts/prepare_product_submissions.py preflight   # stop if it refuses
python3 scripts/prepare_product_submissions.py status
python3 scripts/prepare_product_submissions.py --mode fake run --max-jobs 2
python3 scripts/prepare_product_submissions.py --mode local run \
    --max-jobs 10 --max-seconds 900 --max-microcents 100000
python3 scripts/prepare_product_submissions.py reconcile --job-id <id> --fencing-token <token>
```

Never enable extraction to make a run happen: the switch names a qualified
provider, model digest, prompt version, retention policy and spending cap,
and that is the owner's decision. `stopped_because` is the field that matters:

| Value | Meaning | Action |
|---|---|---|
| `queue_empty` | nothing left | none |
| `job_limit` / `time_limit` | your cap | run again if wanted |
| `budget_exhausted` / `run_budget_reached` | spending cap | owner decides |
| `completion_unknown` | a result may have saved | `reconcile`; never re-run blind |
| `cost_unknown` / `queue_unavailable` | spend or database unknown | stop and report |

`model_failure` (engineering) and `unreadable_evidence` (a retake request for
the reviewer) are different problems. Stop and report when preflight refuses,
the budget is gone, one failure code dominates, or the pinned configuration is
not the one that qualified on the frozen holdout.

## Known failure modes

- **`finding critical: barcode_mismatch`** after a whole, crisp barcode: the
  bottle's barcode is not the one the submission was filed under (S19: label
  `0067 1422`, filed `00671477`). Usually the user scanned a neighbouring
  product. Approving would attach this label to someone else's barcode.
  Finish the transcription, put the mismatch first in your report, and leave
  the decision to the reviewer: correct the barcode in the console's Barcode
  panel (it keeps the filed value in a log and reopens the catalog check), or
  send a retake request or reject.

- **Barcode check says the index is rebuilding.** Another pipeline run is
  rewriting the corpus; the console refuses mid-write on purpose. The reviewer
  retries **Check the catalog** when it finishes. Not your bug.
- **A photo reads blank.** Usually the lot/expiry stamp or a glare-heavy
  barcode. Confirm its category; never claim text that is not there.
- **`record` refuses with "evidence revision is stale".** The submitter
  added photos. `fetch` again and re-read.
