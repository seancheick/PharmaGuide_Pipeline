# Round 2a — Pregnancy / Lactation Authoring

**For:** Dr. Pham
**Estimated time:** ~2.5 h (15 verbatim reuses + 24 fresh writes; 2–4 min per fresh entry)
**File authored:** `scripts/data/ingredient_interaction_rules.json` → each rule's `pregnancy_lactation` block
**Workspace:** `scripts/safety_copy_exemplars/round_2_pregnancy_lactation_shell.json`
**Scope:** Round 2a. Round 2b (non-severe sub-rules) comes after.

---

## Why this round exists

Round 1 authored 77 severe sub-rules inside `condition_rules` and
`drug_class_rules`. End-to-end verification on a rebuild of the product
catalog showed a structural gap: a third block type — `pregnancy_lactation`
— also surfaces in the Flutter app as a severe warning but was outside
round 1 scope. 39 such blocks exist in the file, and they currently fall
back to unauthored mechanism strings in the app.

This round closes that gap. After round 2a, every severe-warning surface
in `ingredient_interaction_rules.json` will render authored copy.

---

## The three authored fields (same contract as round 1)

| Field | Length | Rules |
|---|---|---|
| `alert_headline` | 20–60 chars | No `!`, no SCREAM words (`STOP`, `AVOID`, `NEVER`, `DANGER`, `WARNING`, `URGENT`, `CRITICAL`) |
| `alert_body` | 60–200 chars | Must include conditional framing — `if you`, `when you`, `people who`, `talk to`, `discuss with`, `monitor`, `ask your` |
| `informational_note` | 40–120 chars | Must NOT contain imperative verbs — `stop`, `avoid`, `do not`, `don't`, `never`, `always` |

All round-1 nocebo guidance applies: calm share-not-alarm tone, no
catastrophizing modifiers, no absolute causal claims, no numeric stats
in body copy. See `AUTHORING_SOP.md` §Ground rules.

---

## Shortcut — 15 of 39 blocks copy verbatim from round 1

15 blocks belong to rules where round 1 already authored a pregnancy (or
lactation) `condition_rule` on the same subject at a matching severity
(`avoid` / `contraindicated`). For those, the shortcut is literal:
**copy the three round-1 fields into the pregnancy_lactation block,
unchanged.** The workspace JSON has pre-filled these so you just confirm
and move on (~3 sec per block, ~1 min total).

| Rule | Subject | Reused from |
|---|---|---|
| RULE_BANNED_7KETO_DHEA_PREGNANCY | 7-Keto DHEA | `condition_rules[0]` (pregnancy) |
| RULE_BANNED_EPHEDRA_PREGNANCY | Ephedra | `condition_rules[0]` (pregnancy) |
| RULE_BANNED_YOHIMBE_CONTRA | Yohimbe | `condition_rules[1]` (pregnancy) |
| RULE_INGREDIENT_ALOE_VERA | Aloe vera | `condition_rules[0]` (pregnancy) |
| RULE_IQM_BLACK_COHOSH_PREGNANCY | Black cohosh | `condition_rules[0]` (pregnancy) |
| RULE_IQM_DONG_QUAI_PREGNANCY | Dong quai | `condition_rules[0]` (pregnancy) |
| RULE_IQM_FEVERFEW_PREGNANCY | Feverfew | `condition_rules[0]` (pregnancy) |
| RULE_IQM_GOLDENSEAL_PREGNANCY | Goldenseal | `condition_rules[0]` (pregnancy) |
| RULE_INGREDIENT_ST_JOHNS_WORT | St John's Wort | `condition_rules[0]` (pregnancy) |
| RULE_IQM_YOHIMBE_PREGNANCY | Yohimbe | `condition_rules[0]` (pregnancy) |
| RULE_BOTAN_BLUE_COHOSH_PREGNANCY | Blue cohosh | `condition_rules[0]` (pregnancy) |
| RULE_BOTAN_MUGWORT_PREGNANCY | Mugwort | `condition_rules[0]` (pregnancy) |
| RULE_BOTAN_RUE_PREGNANCY | Rue | `condition_rules[0]` (pregnancy) |
| RULE_IQM_WILD_YAM_PREGNANCY | Wild yam | `condition_rules[0]` (pregnancy) |
| RULE_BANNED_CBD_INTERACTIONS | CBD | `condition_rules[2]` (pregnancy) |

---

## Pregnancy-vs-lactation framing

`pregnancy_lactation` blocks carry **two categories** that can disagree
— e.g., `pregnancy=avoid` but `lactation=monitor`. You author one set
of three fields, so the copy must hold both tenses without losing
clarity.

**Both categories avoid / contraindicated:**
> "Not recommended during pregnancy or breastfeeding. If you are
> pregnant or nursing, talk to your clinician before use."

**Pregnancy stronger than lactation (avoid vs. caution):**
> "Not recommended during pregnancy. If you are pregnant, talk to your
> obstetrician; during breastfeeding, discuss with your clinician."

**Dose-dependent (vitamins A, C, E; iodine):**
> "Safe at prenatal doses; higher intakes raise risk. If you are
> pregnant or nursing, keep total intake within standard prenatal
> limits and talk to your clinician."

**Lactation-specific (B6 high dose, sage):**
> "At supplement doses, may reduce milk supply. If you are
> breastfeeding, talk to your clinician before using concentrated forms;
> prenatal-dose / culinary amounts remain appropriate."

---

## Six edge-case rules flagged

These fresh writes need extra care because the copy must hold two
different stances at once:

1. **RULE_INGREDIENT_CAFFEINE** — `pregnancy=monitor`, `lactation=caution`.
   Total caffeine from all sources (coffee, tea, supplements) adds to
   a 200 mg/day pregnancy ceiling. Body must signal "sum all sources,"
   not "stop caffeine."

2. **RULE_IQM_GUARANA** — Same as caffeine but ingredient-specific.
   Copy should explicitly tie guarana's caffeine into the same budget.

3. **RULE_IQM_IODINE_PREGNANCY_EXCESS** — Iodine is **required** during
   pregnancy (prenatal RDA). The threshold only fires on excess. Copy
   must validate standard prenatal intake while flagging excess.

4. **RULE_IQM_FOLATE_TTC / RULE_IQM_INOSITOL_TTC / RULE_IQM_VITAMIN_B12_COBALAMIN_TTC** —
   "Continue under care" rules. Folate and B12 supplementation started
   pre-conception should continue through pregnancy as part of prenatal
   care. Copy must be reassuring, not suppressive.

5. **RULE_IQM_VITAMIN_A_PREGNANCY_DOSE** — Preformed retinol is
   teratogenic at high dose; beta-carotene is not. Copy must call out
   preformed-retinol sensitivity without discouraging prenatal-dose
   vitamin A generally.

6. **RULE_IQM_VITAMIN_B6_LACTATION** — Normal prenatal B6 is fine;
   pharmacologic doses can suppress prolactin. Copy must distinguish
   the two dose ranges.

---

## Five exemplar patterns for the 24 fresh writes

### Pattern 1 — Teratogen / abortifacient / "not established as safe"

**Applies to (8):** RULE_IQM_BERBERINE_DIABETES, RULE_IQM_BITTER_MELON_DIABETES,
RULE_IQM_KAVALACTONES_LIVER, RULE_IQM_VALERIAN_LIVER,
RULE_IQM_SAW_PALMETTO_LIVER, RULE_IQM_RED_CLOVER, RULE_IQM_VANADIUM_DIABETES,
RULE_IQM_DHEA_TTC

```
alert_headline:     Not recommended in pregnancy or breastfeeding
alert_body:         <Ingredient> has <uterotonic / hormone-active / absent
                    safety data>. If you are pregnant or breastfeeding, do
                    not use <ingredient> unless specifically directed by
                    your clinician.
informational_note: <Ingredient> has <property> — relevant to anyone
                    pregnant, planning pregnancy, or breastfeeding.
```

### Pattern 2 — Hormonally active (stronger in pregnancy)

**Applies to (3):** RULE_IQM_LICORICE_HYPERTENSION,
RULE_BOTANICAL_LICORICE_ROOT, RULE_INGREDIENT_GINSENG

```
alert_headline:     Hormone-active — caution in pregnancy
alert_body:         <Ingredient> has <hormonal mechanism>. If you are
                    pregnant, talk to your obstetrician before use;
                    safer alternatives may be available. Breastfeeding
                    use should be discussed with your clinician.
informational_note: <Ingredient> is hormone-active — relevant to anyone
                    pregnant, planning pregnancy, or breastfeeding.
```

### Pattern 3 — Dose-sensitive nutrient

**Applies to (4):** RULE_IQM_VITAMIN_A_PREGNANCY_DOSE,
RULE_IQM_VITAMIN_C_PREGNANCY_EXCESS, RULE_IQM_VITAMIN_E_PREGNANCY_EXCESS,
RULE_IQM_IODINE_PREGNANCY_EXCESS

```
alert_headline:     Keep intake within prenatal range
alert_body:         <Nutrient> is required during pregnancy, but higher
                    intakes can raise risk. If you are pregnant or
                    breastfeeding, monitor total intake from all sources
                    and talk to your clinician if in doubt.
informational_note: <Nutrient> is prenatal-appropriate within standard
                    intake — higher doses warrant clinician review.
```

### Pattern 4 — Lactation-specific (milk-supply effect)

**Applies to (2):** RULE_IQM_VITAMIN_B6_LACTATION, RULE_IQM_SAGE_LACTATION

```
alert_headline:     May affect milk supply at higher doses
alert_body:         <Ingredient> at supplement doses may reduce milk
                    supply via <mechanism>. If you are breastfeeding,
                    talk to your clinician before using concentrated
                    forms; prenatal-dose / culinary amounts are fine.
informational_note: <Ingredient> at high doses can affect lactation —
                    relevant to anyone breastfeeding.
```

### Pattern 5 — Continue under care (TTC → pregnancy transition)

**Applies to (4):** RULE_IQM_FOLATE_TTC, RULE_IQM_VITAMIN_B12_COBALAMIN_TTC,
RULE_IQM_INOSITOL_TTC, RULE_IQM_FISH_OIL_BLEEDING

```
alert_headline:     Continue under prenatal care
alert_body:         <Nutrient> started before pregnancy should continue
                    through pregnancy and breastfeeding as part of
                    prenatal support. If you are pregnant or
                    breastfeeding, discuss dosing with your obstetrician.
informational_note: <Nutrient> is part of standard prenatal support —
                    relevant to anyone pregnant or breastfeeding.
```

### Specials — caffeine / guarana / fenugreek (3)

**RULE_INGREDIENT_CAFFEINE / RULE_IQM_GUARANA:**

```
alert_headline:     Caffeine adds up — watch total intake
alert_body:         Caffeine crosses the placenta and passes into breast
                    milk. If you are pregnant or breastfeeding, monitor
                    total caffeine from coffee, tea, chocolate, and
                    supplements against a 200 mg/day ceiling.
informational_note: Caffeine crosses the placenta — relevant to anyone
                    pregnant or breastfeeding.
```

**RULE_IQM_FENUGREEK_DIABETES** (pregnancy avoid, lactation sometimes used):

```
alert_headline:     Not recommended during pregnancy
alert_body:         Fenugreek has uterotonic activity and may lower
                    maternal blood sugar. If you are pregnant, talk to
                    your obstetrician before use; during lactation, use
                    under clinician guidance if milk-supply support is
                    the goal.
informational_note: Fenugreek has uterotonic activity — relevant to
                    anyone pregnant or planning pregnancy.
```

---

## Two workflow options

### Option A — shell-first (recommended)

1. Open `scripts/safety_copy_exemplars/round_2_pregnancy_lactation_shell.json`.
2. For each of the 39 blocks, fill
   `fields_to_author.alert_headline` / `alert_body` / `informational_note`.
   The 15 reusable blocks are already pre-filled — confirm and move on.
3. Save.
4. Run the merge script (Sean will provide) to push the authored fields
   into `scripts/data/ingredient_interaction_rules.json`:

   ```bash
   python3 scripts/merge_round_2_pl_shell.py
   ```

### Option B — direct-edit

1. Open `scripts/data/ingredient_interaction_rules.json`.
2. For each `pregnancy_lactation` block, add the three fields directly
   alongside the existing `mechanism` / `notes` / `evidence_level`.
3. Save.

Either workflow produces the same final state. Option A is easier to
review as a PR because the diff is contained.

---

## Validator command

Round 1's validator covers `condition_rules` and `drug_class_rules` but
not `pregnancy_lactation` blocks (yet). For this round, run the round-1
validator to confirm your work hasn't broken the surfaces already
authored:

```bash
python3 scripts/validate_safety_copy.py --interaction-rules-only
```

Sean will extend `validate_safety_copy.py` to cover
`pregnancy_lactation` blocks in a follow-up once the shell is filled
in. Until then, treat the field-length rules, conditional-framing
requirement, and imperative-verb ban above as the contract — review by
eye and by ad-hoc grep.

---

## What's next — round 2b preview

One more authoring pass remains:

- **Round 2b** — non-severe sub-rules (severity ∈ {caution, monitor,
  info}) across `condition_rules` and `drug_class_rules`. ~52 sub-rules.
  These are profile-silent in the Flutter app (a user without the
  matching condition/drug doesn't see them), so they are lower-risk
  than round 2a. Scope and exemplars will live in
  `ROUND_2B_CAUTION_MONITOR_INSTRUCTIONS.md` once round 2a is complete.

---

## Where this fits

| Round | Scope | Status |
|---|---|---|
| Round 1 | `condition_rules` + `drug_class_rules` severity ∈ {avoid, contraindicated}; `medication_depletions`; `banned_recalled_ingredients` | **Complete** |
| Round 2a | `pregnancy_lactation` blocks (39) | **This round** |
| Round 2b | `condition_rules` + `drug_class_rules` severity ∈ {caution, monitor, info} | Queued |
