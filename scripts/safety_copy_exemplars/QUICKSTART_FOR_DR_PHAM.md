# PharmaGuide Clinical Copy — Full Authoring Guide

**For:** Dr. Pham
**Time commitment:** ~60 hours total across 3 files (can be done incrementally)
**What you're doing:** Rewriting clinician-voiced facts that are already
in the data as short, calm, layperson strings. This is **voicing**, not
new clinical research. Every fact, every PMID, every severity rating
stays exactly as you set it before.

Sean built a validator that catches every broken tone rule, so you can
not ship alarming or wrong-shaped copy by accident. Run it after every
entry.

---

## The three files

| # | File | Entries | Fields per entry | Time | Priority |
|---|---|---|---|---|---|
| 1 | `scripts/data/medication_depletions.json` | 68 | 4 | ~4 h | **Start here — fastest, highest UX win** |
| 2 | `scripts/data/banned_recalled_ingredients.json` | 139 | 3 | ~35 h | Medical-incident risk — metformin-banned case |
| 3 | `scripts/data/ingredient_interaction_rules.json` | 59 severe sub-rules | 3 each | ~20 h | Biggest "scary-for-everyone" win |

All three sit in `/Users/seancheick/Downloads/dsld_clean/scripts/data/`.
Edit with any text editor. Commit by batch (one medication family at a
time is ideal).

---

## Universal tone rules (all three files)

These apply to every string you write, regardless of file:

1. **Calm, share-not-alarm tone.** We are sharing what we know, not
   ordering the user to act.
2. **No SCREAMING.** No `STOP`, `DANGER`, `URGENT`, `CRITICAL`, `NEVER`.
   Medical acronyms (`MAOI`, `FDA`, `NSAID`, `SSRI`) are fine.
3. **No encyclopedic openers.** No *"X is a prescription drug that…"*,
   *"X is a synthetic stimulant that…"*. Lead with what the user needs
   to know, not a pharmacology definition.
4. **Conditional framing when the rule depends on user state.**
   *"If you take X…"* / *"When you…"* / *"People on X…"* — not
   *"Do not combine"* barked at every user.
5. **No unsupported claims.** Every copy must match the existing
   `mechanism` / `reason` / cited sources. If it says more than the
   source proves, cut or add a source.

---

## File 1 — `medication_depletions.json` (68 entries)

**Purpose:** Tell a user their medication may lower a nutrient over time
— calmly, and celebrate them if they're already covering it.

### 4 required fields + 1 optional copy field per entry

| Field | Length | Shown when |
|---|---|---|
| `alert_headline` | 20–60 chars | Always (item title) |
| `alert_body` | 60–200 chars | Nutrient NOT in user's stack |
| `acknowledgement_note` | 40–120 chars | Nutrient IS in user's stack |
| `monitoring_tip_short` | 40–120 chars | Always |
| `food_sources_short` **(optional)** | 40–160 chars | Detail expander + nudge sheet |

### Optional numeric thresholds

| Field | Type | When to set |
|---|---|---|
| `adequacy_threshold_mcg` | number | Nutrients normally dosed in micrograms |
| `adequacy_threshold_mg` | number | Nutrients normally dosed in milligrams |

**Pick exactly one threshold field per entry** (validator FAILS if both
are set). Skip thresholds entirely for doctor-managed nutrients
(potassium for diuretic users, thyroid hormones).

### How to pick mcg vs. mg vs. IU

This trips people up. The checker compares doses to thresholds — it
has to know the unit. You pick the one that matches the nutrient's
conventional label unit:

| Nutrient | Label unit | Use field | Example value |
|---|---|---|---|
| Vitamin B12, folate, biotin, iodine, selenium, vitamin K | mcg (μg) | `adequacy_threshold_mcg` | `500` means 500 mcg |
| Magnesium, calcium, zinc, iron, potassium, CoQ10, vitamin C | mg | `adequacy_threshold_mg` | `200` means 200 mg |
| Vitamin D, vitamin A | IU on label, but pipeline stores mass | `adequacy_threshold_mcg` | vitamin D: `25` means 25 mcg (≈ 1000 IU) |
| Vitamin E | IU on label, but pipeline stores mass | `adequacy_threshold_mg` | `15` means 15 mg α-tocopherol |

**Why not IU directly?** IU-to-mass conversion depends on the nutrient
form (vitamin D: 1 mcg = 40 IU; vitamin A: 1 mcg RAE = 3.33 IU retinol
or different for carotenes). The pipeline normalizes to mass units
before the adequacy check, so the threshold must be in mass units too.

**Sanity check:** if your threshold seems enormous, you're in the
wrong unit. 500 mcg B12 is standard; 500 **mg** B12 would be
500,000 mcg — the validator doesn't catch that yet, but Sean will
add a range-check per nutrient later.

### Depletion-specific rules (on top of universal)

The validator enforces 4 original rules plus 6 clinical-UX / nocebo rules
you (Dr. Pham) added in round 1 review. All are automatic.

**Original 4 (hard FAIL):**
- **No "Depleted by X" openers.** Reads as damage. Use *"May lower X
  over time"* or *"Can affect X long-term"*.
- **Body must contain onset language:** `over time | long-term | chronic
  | gradually | years | months | with regular use`. Depletion is chronic.
- **Acknowledgement is PURE validation.** No `risk | deficiency | avoid
  | worry | concern | danger | harm`. User already took care of this.
- **Tip uses soft verbs only:** `check | consider | monitor | watch |
  ask | discuss`. Never `stop | urgent | immediately | emergency`.

**Nocebo-safe additions (round 1 — hard FAIL):**
- **No numeric stats in body copy.** Percentages (`30%`) or ratios
  (`1 in 3`) read as "you're at significant risk" on a mobile card.
  Move them to `clinical_impact` — the expandable detail.
- **No absolute causal claims in body.** `will cause | always causes |
  leads to | results in` — depletion is probabilistic; prefer
  *"can lower"* / *"may reduce"*.
- **No acute-tense framing in body.** `suddenly | immediately |
  rapidly | quickly | acute | acutely` — depletion is chronic by
  definition.

**Nocebo-safe additions (round 1 — WARN, you should still resolve):**
- **Catastrophizing modifiers** in body/headline/tip: `severe | serious
  | dangerous | major | significant | critical`. Prime threat response.
  Note: `"significant"` is fine as the severity-tier **value** in the
  entry; avoid it in the user-facing copy fields.
- **Symptom list >2 terms in body.** Listing many symptoms primes users
  to feel them (nocebo). Cap at 2 in the body; move the rest to
  `clinical_impact`.
- **Body >3 sentences.** Mobile UI scans best at ≤2 sentences; 3+
  buries the lede.

### Food-sources rules (v5.2.1 — optional field)

- **Inclusive framing only** — `"Food sources include…"`, `"Found
  in…"`, `"Good sources are…"`. No imperative verbs (`eat`, `consume`,
  `increase`, `boost`, `incorporate`).
- **No alarm words** — the field is positive/affirmative. `deficiency |
  dangerous | severe | urgent | stop | avoid | at risk` all FAIL.
- **Length 40–160 chars** — slightly more room than the other fields
  because food lists run long.
- **Skip the field entirely** when food isn't a meaningful path
  (metformin/B12, PPI/B12, statin/CoQ10). OR use the explicit
  absorption-blocked hint pattern (see below).

### Example — Metformin + B12 (clinical-review round 1, canonical)

Already in the entry (unchanged):

```
mechanism:       "Metformin impairs B12 absorption by interfering with
                  a calcium-dependent intrinsic factor-B12 receptor…"
clinical_impact: "Up to 30% of long-term metformin users develop B12
                  deficiency. Causes peripheral neuropathy, megaloblastic
                  anemia, and cognitive changes."
onset_timeline:  "years"
```

You add:

```json
"alert_headline": "May lower vitamin B12 over time",
"alert_body": "With long-term use, metformin can reduce how well
  vitamin B12 is absorbed. Some people develop lower levels over years,
  which may show up as fatigue or tingling in the hands and feet.",
"acknowledgement_note": "Nice — you're taking B12, which aligns with
  guidance for long-term metformin use.",
"monitoring_tip_short": "Consider checking B12 levels every 2-3 years;
  easy to review at a routine visit.",
"food_sources_short": "Because metformin reduces B12 absorption, food
  sources may not be enough on their own — a supplement is often more
  reliable.",
"adequacy_threshold_mcg": 500
```

Notice what's *not* there — it went to the `clinical_impact` expander:

- ❌ "Up to 30% of long-term users" — numeric stat, alarm-forward
- ❌ "peripheral neuropathy, megaloblastic anemia, cognitive changes" —
  3+ symptom terms = nocebo priming

The body references **2** generic symptom cues ("fatigue or tingling")
instead of the full clinical list — enough to signal, not enough to
prime. The detailed clinical facts are still available in the
expandable detail section when the user taps "Why this happens."

---

### When food isn't enough — two honest patterns

Some depletions **cannot** be fixed by food alone. The reason matters,
so use the phrasing that matches the clinical mechanism:

**Pattern A — Absorption blocked.** Drug blocks the absorption pathway
even when the nutrient is plentiful in the diet.

> "Because &lt;drug&gt; reduces &lt;nutrient&gt; absorption, food sources may not
> be enough on their own — a supplement is often more reliable."

Use for:
- Metformin + B12 — blocks intrinsic-factor/B12 receptor on ileal mucosa
- PPI + B12 — low stomach acid; B12 not freed from food proteins

**Pattern B — Food-minimal.** Dietary sources are inherently low, so
food alone rarely reaches meaningful doses regardless of absorption.

> "Dietary &lt;nutrient&gt; is minimal — &lt;a few examples&gt; contain small
> amounts, but a supplement is usually the practical route."

Use for:
- Statin + CoQ10 — dietary CoQ10 (organ meats, fatty fish) is minimal

**Depletions where a normal inclusive food list IS appropriate:**

- Oral contraceptives + folate — leafy greens, lentils, fortified grains
- Corticosteroids + calcium — dairy, leafy greens, fortified milks
- Diuretics + potassium — bananas, potatoes, beans, tomatoes
- PPI + magnesium — leafy greens, nuts, seeds, whole grains
- SSRI + magnesium — same magnesium-rich foods

**Pattern C — Bespoke drug-mechanism framing.** The "depletion" is
actually the drug's *intended* mechanism of action, not a side effect.
Standard "X can lower Y" copy misrepresents the clinical reality. Use
reframed copy that treats the effect as designed, and signal *stability*
rather than supplementation.

> Headline: *"Warfarin changes how vitamin K works"*
> Body: *"Warfarin works by blocking vitamin K's role in clotting — this
> is long-term by design. Changes in vitamin K intake can shift your
> INR over weeks."*
> Tip: *"Consider keeping your vitamin K intake steady day to day;
> discuss changes with your prescriber."*

Use for:
- Warfarin + vitamin K (canonical example)
- Any future rule where the drug is *supposed* to modulate the
  nutrient: methotrexate + folate rescue dosing, enzyme-inducing
  anticonvulsants + vitamin K, etc.

No food list (because dietary K management is "keep it steady," not
"eat more"/"eat less" — a food list would actively mislead). No
adequacy threshold (the target is INR stability, not a mass dose).

Your clinical judgment decides which pattern fits. Sean's not making
that call — all four patterns are seeded in the exemplar file.

**See 8 worked examples across all four patterns:**
`scripts/safety_copy_exemplars/depletion_drafts.json`

### Validator command

```bash
python3 scripts/validate_safety_copy.py --depletions-only
```

---

## File 2 — `banned_recalled_ingredients.json` (139 entries)

**Purpose:** Fix medically-wrong derived warnings. The old copy told
patients their prescribed metformin was "banned" — it's only banned as
an undeclared supplement adulterant. That's a clinical incident waiting
to happen. This authoring closes that gap permanently.

### 3 fields to add per entry

| Field | Length | Purpose |
|---|---|---|
| `ban_context` | enum | `substance` / `adulterant_in_supplements` / `watchlist` / `export_restricted` |
| `safety_warning` | 50–200 chars | Detail-pane warning copy |
| `safety_warning_one_liner` | 20–80 chars | Banner copy (one sentence) |

### `ban_context` — pick one

- **`substance`** — the molecule itself is controlled/illegal. Examples:
  DMAA, ephedra, phenibut, BMPEA. Alarm is appropriate.
- **`adulterant_in_supplements`** — a legitimate prescription drug (or
  elsewhere-controlled substance) found undeclared in supplements. The
  ban applies to the adulterated supplement, NOT to the prescribed drug.
  Examples: metformin, meloxicam, sibutramine, sildenafil, tadalafil,
  phenolphthalein. **Copy must separate the two contexts.**
- **`watchlist`** — FDA warning letters issued, no formal ban.
- **`export_restricted`** — restricted outside US but legal here.

### Banned-recalled-specific rules (on top of universal)

- **NEVER** start `safety_warning` with `"{standard_name} is …"` —
  that's the old derivation template that caused the bug.
- For `adulterant_in_supplements`: the warning MUST contain text like
  *"in supplement"*, *"within supplement"*, *"found in supplement"*, or
  *"as an adulterant in dietary…"*. This guardrail protects patients on
  prescribed versions of the drug.
- `safety_warning` must contain a risk/action verb: `stop | avoid |
  consult | risk | linked | caused | associated | do not | talk to`.
- `safety_warning_one_liner` must end with `.` or `!` and contain no
  semicolons.

### Example — Metformin (adulterant case)

Already in the entry (unchanged):

```
standard_name: "Metformin"
recall_status: "banned"
reason: "Metformin is a prescription antidiabetic drug…"
```

You add:

```json
"ban_context": "adulterant_in_supplements",
"safety_warning": "A prescription diabetes drug found undeclared in
  weight-loss supplements — risk of dangerous low blood sugar. Stop
  the supplement and talk to your doctor. Does not affect prescribed
  metformin.",
"safety_warning_one_liner": "Prescription drug hidden in supplements.
  Stop and consult your doctor."
```

Notice: the one-liner never uses the word "metformin." A patient on
prescribed metformin must not read this and think their medication was
banned.

**See 7 worked examples across all 4 ban_context families:**
`scripts/safety_copy_exemplars/banned_recalled_drafts.json`

### Validator command

```bash
python3 scripts/validate_safety_copy.py --banned-recalled-only
```

### Batch by `ban_context`

- Do all 15 `adulterant_in_supplements` entries first — highest clinical
  risk. Same disambiguation pattern repeats.
- Then ~50 `substance` entries (DMAA, ephedra, etc.).
- Then ~20 `watchlist` entries.
- Then the remaining ~55 recalled ingredients.

---

## File 3 — `ingredient_interaction_rules.json` (59 severe sub-rules)

**Purpose:** Stop firing "AVOID" alarms at users who don't have the
triggering condition/medication. A user not on diabetes meds shouldn't
see "AVOID" when they scan berberine.

### Scope

There are 129 total rules, but only the **59 with severity `avoid` or
`contraindicated`** need authored copy right now (they're what fires).
`caution` / `monitor` / `info` rules are suppressed without a profile
match, so they can wait.

### 3 fields to add per sub-rule

Each rule has `condition_rules[]` and/or `drug_class_rules[]` sub-rules.
Author these fields on each sub-rule with severity in
{`avoid`, `contraindicated`}:

| Field | Length | Shown when |
|---|---|---|
| `alert_headline` | 20–60 chars | Always (item title) |
| `alert_body` | 60–200 chars | User's profile matches (condition/drug) |
| `informational_note` | 40–120 chars | Profile does NOT match (silent-label) |

### Interaction-rule-specific rules (on top of universal)

- `alert_headline` has no trailing `!`.
- `alert_body` for `avoid` / `contraindicated` MUST contain conditional
  framing: `if you | when you | people who | do not combine | talk to |
  discuss with | monitor | ask your`.
- `informational_note` MUST NOT contain imperative verbs: `stop | avoid |
  do not | never | always`. The user is not on the triggering profile —
  this reads as context, not a command.

### Example — Berberine + diabetes meds

Already in the sub-rule (unchanged):

```
condition_id:   "hypoglycemics" (drug class)
severity:       "avoid"
mechanism:      "Berberine activates AMPK, increases insulin
                 sensitivity… additive hypoglycemia risk is
                 clinically significant."
action:         "Do not combine with diabetes medications without
                 physician oversight."
```

You add:

```json
"alert_headline": "May boost your diabetes medication",
"alert_body": "Berberine lowers blood sugar with effects comparable to
  metformin. If you take a diabetes medication, monitor glucose closely
  and talk to your prescriber before adding berberine.",
"informational_note": "Berberine has blood-sugar-lowering effects
  relevant to people on diabetes medications."
```

Notice the three voices:

- **Headline** (always shown): warm, neutral.
- **Body** (profile matches): conditional — "if you take…", "talk to your
  prescriber". Never "DO NOT."
- **Note** (no profile match): educational, never imperative. The user
  isn't on diabetes meds; they're just reading about the ingredient.

**See 5 more worked examples:**
`scripts/safety_copy_exemplars/interaction_rules_drafts.json`

### Validator command

```bash
python3 scripts/validate_safety_copy.py --interaction-rules-only
```

---

## Your universal workflow (same for every file)

1. Open the file in a text editor.
2. Find the entry/rule you're authoring.
3. Read the existing clinician fields (`mechanism`, `reason`, `clinical_impact`).
4. Add the new fields per this guide.
5. Save.
6. Run the file's validator command (shown above).
7. **Green OK** → commit; **Red error** → read the message, fix, re-run.

The validator tells you exactly which entry, which field, and which rule
failed. You cannot guess.

---

## When every file is done — the release gate

Run strict mode across all three:

```bash
python3 scripts/validate_safety_copy.py --strict
```

Strict mode fails on any missing field, not just bad copy. When this
passes, all three authored copy surfaces ship to the Flutter app on the
next sync.

---

## What you are NOT doing

- ❌ Reading new PubMed articles
- ❌ Making new clinical decisions
- ❌ Rewriting `mechanism` / `clinical_impact` / `reason` — those stay
- ❌ Changing severity classifications
- ❌ Verifying PMIDs or CUIs (already done)
- ❌ Deciding which rules fire for which users (already modeled)

## What you ARE doing

- ✅ Voicing existing clinical facts as short layperson strings
- ✅ Classifying bans by context (substance vs adulterant vs watchlist)
- ✅ Setting dose thresholds for "adequate coverage" where sensible
- ✅ Letting the validator catch tone mistakes before ship

---

## Recommended order

1. **Week 1 — Depletions** (~4 h). Fast, pattern-heavy, huge UX win.
2. **Week 2–3 — Banned-recalled adulterant family first** (~5 h for the
   15 adulterant entries). Closes the metformin-banned clinical-incident
   risk. Rest of banned_recalled is ~30 h.
3. **Week 4+ — Interaction rules** (~20 h across the 59 severe sub-rules).

If time is limited, do depletions + the 15 adulterant banned_recalled
entries first. Those alone eliminate the highest-risk surfaces.

---

## Stuck?

Every exemplar file in `scripts/safety_copy_exemplars/` shows worked
examples that already pass the validator. When in doubt, copy the
rhythm of the closest exemplar.

For anything the validator doesn't catch — "is this claim supported by
the mechanism?" type judgment calls — ping Sean.
