---
name: prepare-product-submissions
description: Operate the product submission extraction queue from a terminal. Reports queue state, drains pending submissions within explicit caps, and triages the result for a human reviewer. Invoke when the user wants to check submission extraction status, run the extraction worker, drain the queue, triage submissions, or mentions prepare-product-submissions.
license: MIT
metadata:
  author: dsld-team
  version: "1.0.0"
  domain: submissions
  triggers: submission queue, extraction status, drain submissions, triage submissions, prepare submissions
  role: operator
  scope: automation
  output-format: text
  related-skills: verify-data, diagnose
---

# Prepare Product Submissions

Runs the extraction queue for user-submitted products and hands the reviewer a
readable account of what happened. It is an operator's tool, not a decision
maker.

## What this skill may never do

These are not style preferences. Each one exists because the alternative has a
victim.

- **Never approve, reject, resolve a duplicate, or publish anything.** Approval
  requires a human `auth.uid()` in the reviewer allowlist and a saved reviewer
  draft with every critical field attested. The database enforces this; do not
  look for a way around it.
- **Never transcribe a label in chat.** Drafts belong in the reviewer console,
  bound to an evidence revision and a payload digest. A label pasted into a
  conversation is attached to nothing and attestable by nobody.
- **Never print user identifiers, photo URLs or submission ids.** `DrainReport`
  deliberately carries counts and failure codes only. Terminal output gets
  pasted into chats.
- **Never enable extraction to make a run happen.** The switch is a database
  row and turning it on requires naming a qualified provider, model digest,
  prompt version, retention policy and spending cap. If the queue is disabled,
  that is the answer.
- **Never send a photograph anywhere the owner has not agreed to.** The local
  adapter refuses non-loopback endpoints and cloud-proxied models on purpose.

## Sequence

Run from the pipeline repository root.

1. **Preflight.** Confirms credentials, the enabled switch, the pinned
   configuration and the remaining budget. Stop here if it refuses.

   ```bash
   python3 scripts/prepare_product_submissions.py preflight
   ```

2. **Status.** How much work is waiting, and how old the oldest item is.

   ```bash
   python3 scripts/prepare_product_submissions.py status
   ```

3. **Run**, always inside explicit caps. `--mode fake` exercises the whole
   path without a model and is the right first run after any configuration
   change. `--max-seconds` is an admission window: it stops new jobs starting
   and never interrupts one already running.

   ```bash
   python3 scripts/prepare_product_submissions.py --mode fake run --max-jobs 2
   python3 scripts/prepare_product_submissions.py --mode local run \
       --max-jobs 10 --max-seconds 900 --max-microcents 100000
   ```

4. **Reconcile** if a run reported `completion_unknown`. A lost acknowledgement
   may mean the work committed; this checks that one job rather than repeating
   it. Both identifiers come from the run's own output.

   ```bash
   python3 scripts/prepare_product_submissions.py reconcile \
       --job-id <id> --fencing-token <token>
   ```

5. **Hand over to the console.** Extraction produces drafts; people approve.

   ```bash
   python3 scripts/submission_review/serve.py --port 8765
   ```

## Reading the report

`stopped_because` is the field that matters:

| Value | Meaning | Action |
|---|---|---|
| `queue_empty` | nothing left | none |
| `job_limit` / `time_limit` | your cap, not a fault | run again if wanted |
| `budget_exhausted` / `run_budget_reached` | spending cap reached | owner decides, not you |
| `completion_unknown` | a result may or may not have saved | run `reconcile`; never re-run blind |
| `cost_unknown` | spend could not be established | stop and report |
| `queue_unavailable` | the database refused or was unreachable | stop and report |

`failure_codes` counts typed failures. `model_failure` (the model fell over) and
`unreadable_evidence` (a careful human could not read it either) are different
problems and lead to different actions: the first is an engineering matter, the
second is a retake request the reviewer decides on.

## When to stop and ask

Stop and report to the owner, rather than working around it, when:

- preflight refuses for any reason;
- the budget is exhausted or spend is unknown;
- the same failure code dominates a run — that is a configuration problem, not
  a queue to keep draining;
- extraction is disabled, or the pinned configuration is not the one that
  qualified on the frozen holdout.
