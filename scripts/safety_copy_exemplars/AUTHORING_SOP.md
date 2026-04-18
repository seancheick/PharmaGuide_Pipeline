# Safety-Copy Authoring SOP (Path C)

**Scope:** Three files share this authoring pattern:

1. `scripts/data/banned_recalled_ingredients.json` — `ban_context` +
   `safety_warning` + `safety_warning_one_liner`
2. `scripts/data/ingredient_interaction_rules.json` — `alert_headline` +
   `alert_body` + `informational_note` per sub-rule
3. `scripts/data/medication_depletions.json` — `alert_headline` +
   `alert_body` + `acknowledgement_note` + `monitoring_tip_short` per entry

**Why:** One derived template string produced user-facing medical warnings
for 139 ingredients in production with no clinician review. See
`HANDOFF_PIPELINE_SAFETY_DATA.md`. Authoring these fields under the
validator contract closes that class of bug permanently.

## Ground rules

1. **No batch edits.** Author one entry, run the validator, verify the
   entry passes, commit. Batch = silent regressions.
2. **No claims beyond sources.** The entry's existing `reason` /
   `references_structured` / rule `sources` are the factual basis. If the
   authored copy says more than the sources support, the source must be
   added or the claim cut.
3. **Adulterant guardrail is non-negotiable.** Any entry with
   `ban_context == "adulterant_in_supplements"` MUST include text
   matching `(in|within|found in|as an adulterant in) … (supplement|
product|dietary)`. A patient on the prescribed medication must read
   the warning and understand the ban applies to the adulterated
   supplement, not to their prescription.

## Workflow

### Step 1 — Pick a batch

Batches of 5-10 entries per PR, grouped by `ban_context` (or interaction-
rule family). Rationale: patterns repeat within a family, safety review
goes faster.

Suggested order by clinical risk:

1. `ban_context == "adulterant_in_supplements"` (~15 entries) — highest
   clinical-incident risk (metformin-banned case).
2. `ban_context == "substance"` for popular substances (ephedra, DMAA,
   yohimbe, bitter orange, 7-hydroxymitragynine, BMPEA, phenibut).
3. Interaction rules with `severity ∈ {avoid, contraindicated}` — 59
   sub-rules total.
4. `ban_context == "watchlist"` — lower acute risk but high mislabeling
   signal.
5. Remaining substance-level bans.
6. Interaction rules with `severity ∈ {caution, monitor}` — optional
   during transition (these are suppressed without profile anyway).

### Step 2 — Draft against the exemplars

Open `scripts/safety_copy_exemplars/banned_recalled_drafts.json` and
`interaction_rules_drafts.json` for reference templates. Every draft in
those files passes the validator in `--strict` mode.

Patterns to reuse:

| Family                           | Headline pattern                                                     | Body pattern                                                                                                                           | Note pattern                                                                   |
| -------------------------------- | -------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------ |
| adulterant                       | "Prescription drug in supplements"                                   | "… is a prescription …. When found undeclared in supplements, … Stop the supplement, keep your prescribed …, and talk to your doctor." | (none — already critical)                                                      |
| substance (banned)               | "FDA-banned stimulant/drug/…"                                        | "FDA banned … in YYYY after it was linked to … Stop and consult a doctor."                                                             | (none)                                                                         |
| watchlist                        | "Not approved for supplements"                                       | "… is approved only for …, not for dietary supplements. Its presence is associated with …"                                             | (none)                                                                         |
| interaction / avoid (drug class) | "May boost/reduce your <X> medication"                               | "… If you take <X>, … talk to your prescriber before …"                                                                                | "<ingredient> has <mechanism> — relevant to people taking <X> medications."    |
| interaction / contraindicated    | "Do not combine with <X>"                                            | "… If you take <X>, … do not combine."                                                                                                 | "<ingredient> has <mechanism> — relevant to people on <X>."                    |
| interaction / pregnancy          | "Do not use during pregnancy"                                        | "… If you are pregnant, do not use …"                                                                                                  | "<ingredient> has <risk> — relevant to anyone pregnant or planning pregnancy." |
| depletion — any                  | "May lower <nutrient> over time" / "Can affect <nutrient> long-term" | "Long-term <medication> use can gradually reduce <nutrient>. <layperson onset context>. <optional symptom cue>."                       | "Consider checking <nutrient>…" / "Consider asking your doctor about…"         |

### Depletion-specific tone rules (schema v5.2)

Depletion is chronic (onset months-to-years), not acute. The tone is
deliberately calmer than interaction rules. Four authored fields per
entry, validated by `validate_safety_copy.py`:

- `alert_headline` (20-60 chars) — no "Depleted by X" framing (reads as
  medication damaging the user); prefer "May lower X over time" or
  "Can affect X long-term."
- `alert_body` (60-200 chars) — must include onset framing
  (`over time | long-term | chronic | gradually | may develop | years |
months | with regular use`). Depletion is chronic; the copy must signal
  that.
- `acknowledgement_note` (40-120 chars) — shown when the user is
  **already covering** the depletion. This is pure validation. MUST NOT
  contain caution verbs (`risk | deficiency | avoid | worry | danger |
harm | concern | watch out | urgent`). Open with warmth ("Nice —",
  "Good —", "You're taking \_\_\_ — …").
- `monitoring_tip_short` (40-120 chars) — always shown. Must contain a
  soft action verb (`check | consider | monitor | watch | ask | discuss |
review`) and MUST NOT contain loud verbs (`stop | urgent | immediately |
avoid | emergency | critical`).

Optional:

- `adequacy_threshold_mcg` / `adequacy_threshold_mg` — minimum dose that
  qualifies as adequate coverage (vs partial). Below the threshold,
  Flutter renders the depletion as "partial coverage" rather than
  "covered" — the app says "You're taking some B12, but metformin users
  typically need 1000 mcg." Don't author a threshold for depletions
  where dosing is tightly doctor-managed (e.g., potassium for diuretic
  users).

### Step 3 — Run the validator

```bash
# Authoring mode — fails only on outright rule violations.
python3 scripts/validate_safety_copy.py

# Strict mode — additionally fails on missing fields. Run this before PR.
python3 scripts/validate_safety_copy.py --strict --banned-recalled-only
python3 scripts/validate_safety_copy.py --strict --interaction-rules-only
```

### Step 4 — Clinical review

Reviewer signs off by checking the entry against:

- [ ] Copy accurately reflects the cited reason / regulatory basis
- [ ] No claims beyond what the sources support
- [ ] Adulterant entries clearly say "in supplement" or equivalent
- [ ] No encyclopedic openers (`"X is a prescription/synthetic/FDA …"`)
- [ ] Tone is user-directed, not clinician-directed
- [ ] Length within bounds

### Step 5 — Commit, one entry at a time

```bash
# Example — do NOT batch-edit the file.
python3 -c "import json; …"  # one-entry mutation
python3 scripts/validate_safety_copy.py
git add scripts/data/banned_recalled_ingredients.json
git commit -m "safety-copy: author ADULTERANT_METFORMIN Path C fields"
```

## Validator contract (enforced at build time)

See `scripts/validate_safety_copy.py`. Summary:

### banned_recalled per-entry

- `ban_context ∈ {substance, adulterant_in_supplements, watchlist, export_restricted}`
- `safety_warning`
  - 50 ≤ length ≤ 200
  - Must NOT start with `"{standard_name} is "`
  - Must NOT start with encyclopedic opener (`"X is a prescription/synthetic/FDA ..."`)
  - Must contain ≥ 1 risk/action verb: `stop | avoid | consult | risk | linked | caused | associated | do not | talk to`
  - For adulterant_in_supplements: must contain adulterant guardrail phrase
- `safety_warning_one_liner`
  - 20 ≤ length ≤ 80
  - Must end with `.` or `!`
  - No semicolons

### interaction_rules per sub-rule

- `alert_headline`: 20-60 chars, no all-caps words, no trailing `!`
- `alert_body`: 60-200 chars; for severity ∈ {avoid, contraindicated}, must contain conditional framing
- `informational_note`: 40-120 chars, no imperative verbs (`stop | avoid | do not | never | always`)

## Release gate

Once all entries authored:

```bash
# Must pass in strict mode before a release build.
python3 scripts/validate_safety_copy.py --strict
```

If strict passes, the release build proceeds and the Flutter contract
test flips back to positive assertions on the new fields (see
HANDOFF_PIPELINE_SAFETY_DATA.md §Reference paths).
