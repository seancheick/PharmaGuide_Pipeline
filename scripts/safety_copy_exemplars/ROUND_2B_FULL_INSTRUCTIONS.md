# Round 2b (full) — Complete Non-Severe Sub-Rule Authoring

**For:** Review Team
**Estimated time:** ~4–6 hours (297 slots, but template-driven across 8 families)
**Supersedes:** Round 2b-α (the 14-rule subset) — that work is absorbed here
**File authored:** `scripts/data/ingredient_interaction_rules.json` — all remaining `condition_rules` and `drug_class_rules` sub-rules at severity ∈ {caution, monitor, info}
**Workspace:** `scripts/safety_copy_exemplars/round_2b_full_shell.json`

---

## Why full scope (not just 2b-α)

The 14-sub-rule 2b-α list would have closed *today's* null-alert events
in the current 4,240-product catalog. But three reasons push the scope
out to everything:

1. **Catalog growth.** Doses and formulations from new brands shift the
   dose-escalation surface. A sub-rule that never fires severe today
   could fire severe next sprint. Authoring all 297 makes File 3
   future-proof.
2. **Profile-matched users still see these.** Even when a non-severe
   sub-rule never escalates, a user with the matching condition or
   medication sees it as a soft note. Without authored copy they get
   raw mechanism text — the same UX bug round 1 killed, just narrower.
3. **Half-authored is maintenance debt.** Partial coverage means every
   time we touch the file someone has to remember which severities got
   the treatment. Consistency is cheaper to maintain than explain.

After this round, File 3 is fully clinically-reviewed end-to-end. No
deferred slice remains.

---

## The trick — 297 slots ≠ 297 writes

297 sub-rules fall under only **25 unique targets** across **8 clinical
families**. Most families have a dominant mechanism the copy can reuse
with ingredient substitution. The bleeding family alone (107 sub-rules,
36% of the round) is essentially one template applied across ~45
different bleeding-potentiating ingredients.

Realistic breakdown:

| Family | Sub-rules | Template approach |
|---|---:|---|
| **Bleeding** (anticoag / antiplatelet / bleeding-dis / NSAIDs / surgery) | 107 | One mechanism ("may increase bleeding risk"). Sub-templates by target — surgery gets "pause 2 weeks before", others get "talk to prescriber about monitoring." |
| **Cardiovascular** (antihypertensives / hypertension / heart) | 46 | Two templates — "may affect BP control" for drug-side; "caution with hypertension/heart condition" for condition-side. |
| **Metabolic** (hypoglycemics / diabetes / statins / cholesterol) | 45 | Two templates — glycemic (insulin/metformin, diabetes) and lipid (statins, cholesterol). Niacin-statin has a specific muscle/liver framing. |
| **CNS** (sedatives / seizure / anticholinergics / anticonvulsants) | 23 | One potentiation template for sedatives ("may increase drowsiness"); one caution template for seizure disorders ("lower seizure threshold"). |
| **Organ** (liver / kidney) | 22 | "Clearance is impaired" template — body mass-accumulates at high dose. |
| **Endocrine** (thyroid meds / thyroid disorder) | 21 | "Thyroid-axis interference" template. Iodine + selenium + tyrosine are the main subjects. |
| **Reproductive** (pregnancy / lactation / TTC) | 19 | Already mostly covered via round 2a PL-blocks. Many will be 2a-copy shortcuts. |
| **Immune** (immunosuppressants / autoimmune) | 14 | "May activate immune response" template. |

So you're really authoring **~12 templates**, then substituting
ingredient names across 297 slots. ~3-5 minutes per slot once the
family's template is set. The first template takes ~20 minutes to
design; subsequent ingredients in that family take 1-2 minutes each.

---

## Field contracts (unchanged)

| Field | Length | Notes |
|---|---|---|
| `alert_headline` | 20–60 chars | No SCREAM, no `!`. Softer than severe — *"Monitor with…"*, *"Caution with…"*, *"May affect…"* |
| `alert_body` | 60–200 chars | Conditional framing *required* (*"If you take X…"*, *"People on Y…"*). Must read safely at both severities — dose-escalation is invisible to you when writing. |
| `informational_note` | 40–120 chars | No imperatives (`stop`, `avoid`, `don't`, `never`, `always`). Use *"relevant to people on X"* framing. |

All round-1 nocebo guidance applies — see `AUTHORING_SOP.md` §Ground
rules.

---

## Workflow — work target-by-target, not rule-by-rule

The shell (`round_2b_full_shell.json`) is sorted so all entries for the
same target are contiguous. Author process per target:

1. **Open the target batch.** E.g., all 38 `anticoagulants` sub-rules.
2. **Design the template once.** Look at 2–3 source mechanisms across
   the batch to calibrate voice. Drop one fully-authored entry as the
   reference.
3. **Apply across the batch.** Same headline / body / info shape, swap
   the ingredient name and (if needed) the specific mechanism clause.
   5-15 ingredients fit the shared template directly; outliers need
   minor tweaks.
4. **Skim-review the batch.** Do 38 copies read coherently? Does any
   ingredient feel overstated or understated?
5. **Validate.** Run the command below. Fix anything it flags.
6. **Move to next target.**

Order I'd recommend (biggest-family first, max momentum):

1. **Bleeding family** (107) — anticoag, bleeding-dis, antiplatelets,
   NSAIDs, surgery. ~90 min total.
2. **Cardiovascular** (46) — antihypertensives, hypertension, heart.
   ~45 min.
3. **Metabolic** (45) — hypoglycemics, diabetes, statins, cholesterol.
   ~45 min.
4. **CNS** (23), **Organ** (22), **Endocrine** (21). ~45 min combined.
5. **Reproductive** (19), **Immune** (14). ~30 min — many shortcuts here.

---

## Family exemplar templates

### Bleeding (107 sub-rules across 5 targets)

Same mechanism — the ingredient has antiplatelet / anticoagulant
activity — but the conditional clause varies by target:

**Target: anticoagulants / antiplatelets / NSAIDs (drug-class, 75 sub-rules)**

```
alert_headline:     May add to bleeding-med effects
alert_body:         <Ingredient> has mild <antiplatelet / anticoagulant>
                    activity and may add to the bleeding risk of
                    prescription thinners. If you take <drug-class>,
                    talk to your prescriber before adding <ingredient>.
informational_note: <Ingredient> can affect platelet or clotting
                    function — relevant to people on <drug-class>.
```

**Target: bleeding_disorders (condition, 24 sub-rules)**

```
alert_headline:     Caution with bleeding disorders
alert_body:         <Ingredient> has mild antiplatelet activity and
                    may increase bleeding risk. If you have a bleeding
                    disorder, talk to your hematologist before adding
                    <ingredient>.
informational_note: <Ingredient> can affect platelet function —
                    relevant to people with a bleeding disorder.
```

**Target: surgery_scheduled (condition, 8 sub-rules, all caution)**

```
alert_headline:     Pause before scheduled surgery
alert_body:         <Ingredient> can affect bleeding or anesthesia.
                    If you have surgery scheduled, discuss with your
                    surgeon about pausing <ingredient> two weeks
                    before the procedure.
informational_note: <Ingredient> can affect perioperative bleeding —
                    relevant to anyone with surgery planned.
```

### Cardiovascular (46 across 3 targets)

**Target: antihypertensives (drug-class, 20 sub-rules)**

```
alert_headline:     May affect blood-pressure control
alert_body:         <Ingredient> can <lower / raise> blood pressure,
                    which may <add to / counter> the effect of
                    antihypertensive medications. If you take
                    antihypertensives, talk to your prescriber.
informational_note: <Ingredient> affects blood pressure — relevant
                    to people on antihypertensive medications.
```

**Target: hypertension / heart_disease (conditions, 26 sub-rules)**

```
alert_headline:     Caution with <hypertension / heart disease>
alert_body:         <Ingredient> can <mechanism — raise BP / affect
                    rhythm / increase HR>. If you have <condition>,
                    talk to your cardiologist before adding
                    <ingredient>.
informational_note: <Ingredient> affects <cardiovascular pathway>
                    — relevant to people with <condition>.
```

### Metabolic (45 across 4 targets)

**Target: hypoglycemics / diabetes (33 sub-rules)**

```
alert_headline:     May affect blood-sugar control
alert_body:         <Ingredient> can lower blood sugar and may add
                    to diabetes-medication effects. If you take a
                    diabetes medication or have diabetes, talk to
                    your prescriber and monitor glucose when adding
                    <ingredient>.
informational_note: <Ingredient> affects glycemic control — relevant
                    to people with diabetes or on glucose-lowering
                    medications.
```

**Target: statins / high_cholesterol (12 sub-rules — niacin-heavy)**

```
alert_headline:     May add to <statin / cholesterol med> effects
alert_body:         <Ingredient> can affect lipid metabolism and
                    shares muscle / liver pathways with statins.
                    If you take a statin or have cholesterol issues,
                    talk to your prescriber before adding
                    <ingredient>.
informational_note: <Ingredient> affects lipid / liver pathways —
                    relevant to people on lipid-lowering therapy.
```

### CNS (23 across 4 targets)

**Target: sedatives / anticholinergics / anticonvulsants (15 sub-rules)**

```
alert_headline:     May add to <drug-class> drowsiness
alert_body:         <Ingredient> has mild sedative effects. If you
                    take <drug-class>, talk to your prescriber before
                    adding <ingredient> — the combination can
                    increase drowsiness or affect alertness.
informational_note: <Ingredient> has sedative activity — relevant
                    to people on <drug-class>.
```

**Target: seizure_disorder (8 sub-rules, all caution)**

```
alert_headline:     Caution with seizure disorder
alert_body:         <Ingredient> may affect seizure threshold in
                    susceptible people. If you have a seizure
                    disorder, talk to your neurologist before adding
                    <ingredient>.
informational_note: <Ingredient> may lower seizure threshold —
                    relevant to people with a seizure disorder.
```

### Organ (22 across 2 targets)

**Target: liver_disease / kidney_disease (22 sub-rules)**

```
alert_headline:     Caution with <liver / kidney> disease
alert_body:         <Ingredient> is cleared via the <liver / kidney>
                    and may accumulate when clearance is impaired.
                    If you have <condition>, talk to your clinician
                    about safe intake.
informational_note: <Ingredient> depends on <organ> clearance —
                    relevant to people with <condition>.
```

### Endocrine (21 across 2 targets)

**Target: thyroid_medications / thyroid_disorder (21 sub-rules)**

```
alert_headline:     May affect thyroid function
alert_body:         <Ingredient> affects thyroid hormone
                    <synthesis / absorption / clearance>. If you
                    take thyroid medication or have a thyroid
                    condition, talk to your endocrinologist about
                    timing and monitoring.
informational_note: <Ingredient> affects thyroid pathways —
                    relevant to people with thyroid conditions
                    or on thyroid medication.
```

### Immune (14 across 2 targets)

**Target: immunosuppressants / autoimmune (14 sub-rules)**

```
alert_headline:     Caution with <autoimmune condition / transplant meds>
alert_body:         <Ingredient> has mild immune-modulating activity.
                    If you <have autoimmune condition / take
                    immunosuppressants>, talk to your specialist
                    before adding <ingredient>.
informational_note: <Ingredient> affects immune function — relevant
                    to people with autoimmune conditions or on
                    immune-modulating medications.
```

### Reproductive (19 — mostly pregnancy/lactation/TTC)

Many of these can pull directly from round 2a PL-block copy if the
same rule has a populated pregnancy_lactation block. The shell
pre-populates these as shortcuts where the target matches.

For fresh writes, use the round 2a patterns adapted to the non-severe
tense (e.g., "Consult your clinician" instead of "Do not use").

---

## Shortcuts — 9 slots are pre-filled

The shell has 9 entries where the same rule already has authored copy
on the same target (from round 1 severe or round 2a PL-blocks). Those
carry the full copy in `shortcut_from_existing`. Just confirm the copy
reads correctly at the softer severity and move on.

---

## Validation

```bash
python3 scripts/validate_safety_copy.py --interaction-rules-only --strict
```

Green in strict mode means File 3 is fully authored. Intermediate
progress — run non-strict to see which sub-rules still lack copy:

```bash
python3 scripts/validate_safety_copy.py --interaction-rules-only
```

---

## When you hand back

I'll:
1. Run the validator on `--strict` mode and confirm 0 warnings.
2. Run a full-catalog rebuild (15 brands, 4,240 products).
3. Confirm every non-severe interaction warning in every product blob
   carries authored copy.
4. Run the Python test suite.
5. Commit with round-2b-full co-authorship.

File 3 clinical review is then done end-to-end. No deferred slice.

---

## Questions / flags

- Any target where the template feels wrong for a specific ingredient
  → flag in `authoring_notes`, we'll write a one-off.
- Any sub-rule where the source `mechanism` is wrong / overstated →
  flag, we'll correct the source.
- Any target where you want a different template than the one above →
  tell me, I'll adjust and re-scope.

Not in a rush. Take breaks between families — template fatigue is
real. Ping when ready.
