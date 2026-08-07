# Supplement label review — KEVIN

You need nothing except this file. Fill in the blanks under each product and
email the file back. **Please don't retype or reformat anything else.**

## What we're asking

We built software that scores supplement labels for quality. Before we trust
it, we want to know whether it agrees with a pharmacist reading the same label.
You score them blind; we compare afterwards. **We are not asking you to endorse
any product**, or to judge it for a particular patient.

## Three rules

1. **Don't look up what PharmaGuide says** about these products — app, website,
   or repository. Your independence is the whole point.
2. **If you accidentally see one of our scores, say so** in that product's
   `ODD:` line. It's not harmless — we drop that product — but not knowing is
   far worse.
3. **Don't compare notes** with the other reviewers until everyone's file is in.

## For each product

Read the label facts, then **verify the material dose, evidence, safety and
certification claims against primary or official sources** — PubMed, NIH ODS,
FDA, USP/NSF. That checking is the task; scoring off the label alone isn't.
List what you used on the `SOURCES:` line.

Then fill in the block. **Whole or half points only** (12, 12.5, 13).

| Line | Range | The question |
|---|---:|---|
| `FORMULATION` | 0–20 | Are the ingredient forms and formulation choices appropriate? 0 = materially poor · 10 = mixed/uncertain · 20 = consistently strong |
| `DOSE` | 0–20 | Are the daily doses plausibly effective without material excess? 0 = unusable or unsafe · 10 = partial/uncertain · 20 = well supported |
| `EVIDENCE` | 0–20 | Does human research support these actives, forms, doses **and intended use**? 0 = none comparable · 10 = limited/mixed · 20 = strong and directly comparable |
| `TRANSPARENCY` | 0–15 | Does the label disclose **identities, amounts, serving basis and blends**? 0 = materially opaque · 7.5 = partial · 15 = complete |
| `VERIFICATION` | 0–15 | Is there **product-specific** independent testing? 0 = contrary evidence · 7.5 = partial/mixed · 15 = strong product-specific proof. A certification named on the label is a *claim* — the question is whether the exact product appears in the certifier's own records. Brand- or facility-level claims are not product-specific. **If you cannot establish anything either way, enter 7.5** (our defined neutral) **and write `Verification 7.5 = neutral, nothing establishable` in `WHY:`** so we can tell that apart from a real partial-verification 7.5. |
| `QUALITY` | 0–10 | **Catalog/product-level** signals only: recalls, contamination, adulteration, substantiated manufacturing-quality problems, or material additive concerns. 0 = severe known concern · 5 = material caution/uncertainty · 10 = none known. **Ordinary dose-related risk belongs in DOSE and SAFETY — don't penalise the same ingredient a third time here.** |

**Don't add them up — we do that.**

`SAFETY:` is judged separately from quality. One of:

- `blocked` — safe use depends on a missing prerequisite (e.g. butterbur with no
  PA-free processing stated)
- `unsafe` — the labeled regimen itself creates a serious, established concern
- `caution` — elevated dose, uncertain long-term safety, or a narrower safety
  margin, without a clear expectation of serious harm
- `no_known_concern` — nothing known after you looked
- `not_assessed` — you genuinely couldn't judge

For `blocked`/`unsafe`/`caution`, name the substance or dose on the `DRIVER:`
line and cite it. **Under-warning is the worse error** — if torn, flag it.

**Exceeding a UL is not automatically `unsafe`.** A Tolerable Upper Intake Level
is a population risk threshold, not the dose where toxicity begins. Passing one
generally supports a dose penalty and often `caution`; reserve `unsafe` for a
labeled regimen posing a serious, reasonably established risk at that actual
dose, form and duration. Form matters — a total with the form unspecified
shouldn't mechanically become `unsafe`.

`CONFIDENCE:` `high` / `moderate` / `low`  ·  `LABEL ENOUGH?:` `yes` / `no`

`SOURCES:` semicolon-separated, each a PMID, DOI or official URL —
`PMID 12345678; https://ods.od.nih.gov/factsheets/Zinc-HealthProfessional/`.
Please prefer primary literature and official bodies (PubMed, NIH ODS, FDA,
NCCIH, USP/NSF) over consumer health sites.

**Evidence cutoff: assess information publicly available as of the date this
file was sent.** Certification directories and recall notices change; we need
all three reviewers judging the same world.

`ODD:` leave as `none` unless something compromised the *rating* — you saw a
score, found a conflict, or couldn't reach a source. **Our data defects don't
go here** (see below) — put those in `LABEL ENOUGH?: no`.

## Scope

Product-level, not personalised. Consider drug/condition interactions only where
they make the *product* a concern. Please don't score down for a personalised
interaction — that's handled elsewhere and wasn't asked of the software either.

Don't treat a missing fact as good or bad. If a label doesn't state third-party
testing, that's neither proof it happened nor that it didn't — put the
uncertainty in the score and lower your confidence.

**Totals vs. their constituent forms.** Where a nutrient total is followed by
amounts for the forms that make it up, **the first amount is the total — do not
add the components to it.** Example: `Magnesium 135 mg` followed by `55 mg` and
`80 mg` is 135 mg per serving, not 270 mg. Affected products carry a
`⚠ DATA NOTE`.

## Our known data gaps — not your problem, don't report them

Our extraction is imperfect. Where a product is affected you'll see a
**`⚠ DATA NOTE`** right in its block. Across your 120 products: **14 have an
ingredient quantity of 0**, **10 have an ingredient with no unit**, and
**7 show a servings-per-day below 1** (one is 0.044 — plainly wrong).

For any of these: set `LABEL ENOUGH?: no`, mention it in `WHY:` if you like, and
move on. **Don't put them in `ODD:`** — that field excludes the product from the
analysis, and these are our defects, not protocol breaches.

**Which serving to dose against:** normally the **maximum** labeled daily
serving. But for the 7 products flagged with a broken frequency, **assume
1 serving per day** and set confidence `low` — that rule wins even if the
product also shows a range.

## Conflicts of interest

The 41 brands in this set are listed at the end. If you have a financial,
employment, consulting or research relationship with any of them, you can't
review this set — it's all-or-nothing, since all reviewers rate all products.

## Time

This is 120 products with source checking. Realistically **10+ hours.** Work in
batches over several days — that's fine. **If that's too much, tell us before
you start**, not partway through; a smaller set means formally re-cutting the
study, which is a fine outcome but has to be decided up front.

If a product is genuinely unratable, still give six numbers — score what the
label supports, then set `CONFIDENCE: low`, `LABEL ENOUGH?: no` and
`SAFETY: not_assessed`. **Please don't leave any score blank**; a blank drops
that product for all three reviewers.

## Sending it back

Email this same file, filled in. Return to: `_______________`
By: `_______________`

Ask us anything about the process. The one thing we can't tell you is what our
software scored a product — that's the thing your review is testing.

---

## 1. Immune Booster

**Brand:** Doctor's Best
**Servings/day:** 1

**Actives:**
- Zinc — 23.0 mg (209.0% DV)
- Echinacea — 400.0 mg
- European Elder — 300.0 mg

**Other ingredients:** Hypromellose, Microcrystalline Cellulose, Maltodextrin, Silicon Dioxide, Magnesium Stearate

**Quality claims stated on the label:** none stated (not evidence testing didn't happen)
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*
```
ID: PG-2E9C2336183F
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 2. Alive! Kids Chewable Multivitamin Orange & Berry

**Brand:** Nature's Way
**Servings/day:** 1

**Actives:**
- Vitamin A — 450.0 mcg (150.0% DV)
- Vitamin C — 90.0 mg (600.0% DV)
- Vitamin D — 15.0 mcg (100.0% DV)
- Vitamin E — 7.5 mg (125.0% DV)
- Thiamin — 1.2 mg (240.0% DV)
- Riboflavin — 1.3 mg (260.0% DV)
- Niacin — 5.75 mg (96.0% DV)
- Vitamin B6 — 1.7 mg (340.0% DV)
- Folate — 200.0 mcg DFE (133.0% DV)
- Folate — 119.0 mcg
- Vitamin B12 — 1.5 mcg (167.0% DV)
- Biotin — 5.0 mcg (63.0% DV)
- Pantothenic Acid — 3.75 mg (188.0% DV)
- Choline — 5.5 mg (3.0% DV)
- Calcium — 19.5 mg (3.0% DV)
- Iron — 2.5 mg (36.0% DV)
- Phosphorus — 9.75 mg (2.0% DV)
- Iodine — 75.0 mcg (83.0% DV)
- Magnesium — 6.3 mg (8.0% DV)
- Zinc — 1.8 mg (60.0% DV)
- Manganese — 1.15 mg (96.0% DV)
- Molybdenum — 22.5 mcg (132.0% DV)
- Citrus Bioflavonoid Complex — 15.0 mg

**Blend — Orchard Fruits & Garden Veggies Powder Blend** (total: amount NOT disclosed)
- Acai, Powder — amount NOT disclosed
- Apple, Powder — amount NOT disclosed
- Asparagus, Powder — amount NOT disclosed
- Banana, Powder — amount NOT disclosed
- Beet, Powder — amount NOT disclosed
- Blueberry, Powder — amount NOT disclosed
- Broccoli, Powder — amount NOT disclosed
- Brussels Sprout, Powder — amount NOT disclosed
- Cabbage, Powder — amount NOT disclosed
- Carrot, Powder — amount NOT disclosed
- Cauliflower, Powder — amount NOT disclosed
- Cherry, Powder — amount NOT disclosed
- Cranberry, Powder — amount NOT disclosed
- Cucumber, Powder — amount NOT disclosed
- Grape, Powder — amount NOT disclosed
- Orange, Powder — amount NOT disclosed
- Pea, Powder — amount NOT disclosed
- Pear, Powder — amount NOT disclosed
- Pineapple, Powder — amount NOT disclosed
- Plum, Powder — amount NOT disclosed
- Pomegranate, Powder — amount NOT disclosed
- Pumpkin, Powder — amount NOT disclosed
- Raspberry, Powder — amount NOT disclosed
- Spinach, Powder — amount NOT disclosed
- Strawberry, Powder — amount NOT disclosed
- Tomato, Powder — amount NOT disclosed

**Other ingredients:** Fructose, Sorbitol, Natural Flavors, Magnesium Stearate, Citric Acid, Turmeric, Vegetable Juice, Malic Acid, Silica, Gelatin

**Quality claims stated on the label:** none stated (not evidence testing didn't happen)
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*

> **⚠ DATA NOTE** — **Vitamin C 90.0 mg shown as 600.0% DV is internally inconsistent** (~0x off the usual amount for that %DV) — one of the two figures is our extraction error. Judge on whichever you find credible and say which in `WHY:`; **Magnesium 6.3 mg shown as 8.0% DV is internally inconsistent** (~0x off the usual amount for that %DV) — one of the two figures is our extraction error. Judge on whichever you find credible and say which in `WHY:`; **Zinc 1.8 mg shown as 60.0% DV is internally inconsistent** (~0x off the usual amount for that %DV) — one of the two figures is our extraction error. Judge on whichever you find credible and say which in `WHY:`
```
ID: PG-2A6B099D369A
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 3. Omega Blood Sugar

**Brand:** Nordic Naturals
**Servings/day:** 1

**Actives:**
- Chromium — 200.0 mcg (571.0% DV)
- Alpha Lipoic Acid — 300.0 mg
- EPA — 455.0 mg
- DHA — 315.0 mg

**Other ingredients:** purified deep sea Fish Oil, Softgel Capsule, Beeswax, D-Alpha-Tocopherol, Rosemary extract

**Quality claims stated on the label:** Friend of the Sea
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*
```
ID: PG-E9F14BA9D91D
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 4. Precision BCAA Sour Gummy

**Brand:** GNC Beyond Raw
**Servings/day:** 1

**Actives:**
- Calcium — 70.0 mg (5.0% DV)
- Magnesium — 50.0 mg (12.0% DV)
- Chromium — 1000.0 mcg (2857.0% DV)
- Potassium — 240.0 mg (5.0% DV)
- Leucine — 5.0 Gram(s)
- Isoleucine — 2.5 Gram(s)
- Valine — 2.5 Gram(s)
- Betaine Anhydrous — 2.5 Gram(s)

**Blend — Velositol Amylopectin Chromium Complex** (total: amount NOT disclosed)

**Other ingredients:** Natural and Artificial flavors, Citric Acid, Malic Acid, Tartaric Acid, Sucralose, Acesulfame Potassium, Calcium Carbonate, Calcium Silicate, Sunflower Lecithin, FD&C Red #40, Polyglycerol Polyricinoleate, fractionated Coconut Oil, Citrus Oil, Olive Oil, Mono and Diglycerides, Oat Oil

**Quality claims stated on the label:** none stated (not evidence testing didn't happen)
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*

> **⚠ DATA NOTE** — **Leucine 5.0** is the TOTAL; the entries after it are its constituent forms. Do NOT add them to it
```
ID: PG-66D0CA1DBB43
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 5. Liquid Elderberry

**Brand:** SR Sports Research
**Servings/day:** 1

**Actives:**
- Proprietary Blend (Herb/Botanical) — 192.0 mg

**Blend — Proprietary Herbal Blend** (total: amount NOT disclosed)
- Astragalus root extract — amount NOT disclosed
- Black Elderberry extract — amount NOT disclosed
- Echinacea purpurea Tops Extract — amount NOT disclosed
- Propolis Resin Extract — amount NOT disclosed
- Sage leaf extract — amount NOT disclosed
- Slippery Elm bark extract — amount NOT disclosed

**Other ingredients:** non-GMO Vegetable Glycerin, purified Water

**Quality claims stated on the label:** none stated (not evidence testing didn't happen)
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*
```
ID: PG-719F946A757A
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 6. FiberMend

**Brand:** Thorne
**Servings/day:** 1

**Actives:**
- Rice Bran — 2.5 Gram(s)
- Arabinogalactan — 300.0 mg
- Pectin — 150.0 mg
- GreenSelect — 50.0 mg

**Other ingredients:** none listed

**Quality claims stated on the label:** heavy-metal tested, purity verified, label accuracy verified, NSF Contents Certified
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*
```
ID: PG-01FF3E30FBEE
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 7. PRE Pre-Workout Complex Peach Mango

**Brand:** Nutricost Performance
**Servings/day:** 1

**Actives:**
- Thiamin — 50.0 mg (4170.0% DV)
- Niacin — 25.0 mg NE (160.0% DV)
- Vitamin B6 — 60.0 mg (3530.0% DV)
- Vitamin B12 — 200.0 mcg (8330.0% DV)
- Citrulline — 6000.0 mg
- Beta-Alanine — 3000.0 mg
- Taurine — 2000.0 mg
- Agmatine — 500.0 mg
- Tyrosine — 500.0 mg
- Theanine — 300.0 mg
- Caffeine — 300.0 mg
- Theobromine — 200.0 mg
- Huperzine — 200.0 mcg

**Other ingredients:** Natural Flavors, Calcium Silicate, Silica, Sucralose, Beta-Carotene, Beet, Powder

**Quality claims stated on the label:** GMP certified/compliant
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*

> **⚠ DATA NOTE** — **Beta-Alanine 3000.0** is the TOTAL; the entries after it are its constituent forms. Do NOT add them to it
```
ID: PG-695DB97F8B65
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 8. HMB

**Brand:** GNC Beyond Raw Chemistry Labs
**Servings/day:** 1

**Actives:**
- Vitamin D — 13.0 mcg (65.0% DV)
- HMB — 3.0 Gram(s)

**Other ingredients:** none listed

**Quality claims stated on the label:** none stated (not evidence testing didn't happen)
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*
```
ID: PG-7F36C9F6FBF0
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 9. Oil of Oregano Softgels 150 mg

**Brand:** BulkSupplements.com
**Servings/day:** 1

**Actives:**
- oregano — 150.0 mg

**Other ingredients:** Soybean Oil, Gelatin, Glycerin, Water, Purified

**Quality claims stated on the label:** none stated (not evidence testing didn't happen)
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*
```
ID: PG-D29A35289E17
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 10. L-Lysine 1,000 mg

**Brand:** Nutricost
**Servings/day:** 1

**Actives:**
- Lysine — 1000.0 mg

**Other ingredients:** Gelatin, Stearic Acid, Rice Flour

**Quality claims stated on the label:** GMP certified/compliant
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*
```
ID: PG-1DBDDF0210EB
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 11. Immune Protect with Paractin

**Brand:** Life Extension
**Servings/day:** 1

**Actives:**
- Vitamin C (unspecified) — 50.0 mg (56.0% DV)
- Beta-Glucans — 100.0 mg

**Other ingredients:** Vegetable Cellulose, Microcrystalline Cellulose, Maltodextrin, Silica, Stearic Acid

**Quality claims stated on the label:** none stated (not evidence testing didn't happen)
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*
```
ID: PG-AAE7B8C4803C
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 12. Ginger Root 550 mg

**Brand:** GNC Herbal Plus
**Servings/day:** 1

**Actives:**
- Ginger — 550.0 mg

**Other ingredients:** Cellulose, Gelatin

**Quality claims stated on the label:** none stated (not evidence testing didn't happen)
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*
```
ID: PG-553CA0D81360
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 13. Wheybolic Cookies and Cream

**Brand:** GNC AMP Advanced Muscle Performance
**Servings/day:** 1–2

**Actives:**
- Calcium — 100.0 mg (8.0% DV)
- Chromium — 250.0 mcg (714.0% DV)
- Potassium — 140.0 mg (3.0% DV)
- Leucine — 5.0 Gram(s)
- Isoleucine — 1.25 Gram(s)
- Valine — 1.25 Gram(s)

**Blend — Velositol Amylopectin Chromium Complex** (total: amount NOT disclosed)

**Blend — Digestive Enzyme Blends** (total: amount NOT disclosed)

**Blend — Wheybolic Protein Complex** (total: amount NOT disclosed)

**Blend — General Proprietary Blends** (total: amount NOT disclosed)

**Blend — Wheybolic Complex** (total: amount NOT disclosed)
- Branched-Chain Amino Acids — 7.5 Gram(s)

**Blend — Wheybolic Protein Complex** (total: amount NOT disclosed)
- Whey Protein Isolate — amount NOT disclosed
- Whey Protein isolate — amount NOT disclosed
- hydrolyzed Whey Protein — amount NOT disclosed

**Blend — Glutamic Acid and Glutamine** (total: amount NOT disclosed)
- Glutamic Acid — amount NOT disclosed
- Glutamine — amount NOT disclosed

**Other ingredients:** Natural and Artificial flavors, Chocolate Flavored Sprinkles, Lecithin, Creamer, Salt, Gum Blend, Sucralose, Titanium Dioxide, Acesulfame Potassium, Caramel color

**Quality claims stated on the label:** purity verified, Informed Choice
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*
```
ID: PG-EFB27830A227
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 14. Re-Built Mass XP Strawberry

**Brand:** GNC Beyond Raw
**Servings/day:** 1

**Actives:**
- Medium chain triglycerides — 4.0 Gram(s)
- Conjugated Linoleic Acid — 1.0 Gram(s)
- Oat Fiber — 0.0 unit not stated
- Whey Protein — 23.0 Gram(s)
- Whey Protein — 17.0 Gram(s)
- Casein Protein — 12.0 Gram(s)
- Whey Protein — 8.0 Gram(s)
- Calcium — 520.0 mg (40.0% DV)
- Iron — 1.5 mg (8.0% DV)
- Magnesium — 580.0 mg (138.0% DV)
- Potassium — 460.0 mg (9.0% DV)
- Creatine — 5.0 Gram(s)
- Creatine MagnaPower — 2.5 Gram(s)
- Creatine — 2.5 Gram(s)
- Glycocyamine — 1.0 Gram(s)
- Arginine — 1.0 Gram(s)
- Glycine — 1.0 Gram(s)
- METHIONINE — 1.0 Gram(s)
- Leucine — 8.9 Gram(s)
- Isoleucine — 3.7 Gram(s)
- Valine — 3.5 Gram(s)
- Betaine Anhydrous — 2.5 Gram(s)
- Calcium HMB — 500.0 mg

**Blend — Digestive Enzyme Blends** (total: amount NOT disclosed)

**Blend — Advanced Creatine Complex** (total: amount NOT disclosed)
- Creatine — 5.0 Gram(s)
- micronized Guanidinoacetate — 1.0 Gram(s)
- L-Arginine, Micronized — 1.0 Gram(s)
- Glycine, Micronized — 1.0 Gram(s)
- L-Methionine, Micronized — 1.0 Gram(s)

**Blend — Hyper-Anabolic Complex** (total: amount NOT disclosed)

**Blend — ModCarb Grain Blend** (total: amount NOT disclosed)
- organic Amaranth — amount NOT disclosed
- organic Buckwheat — amount NOT disclosed
- organic Chia — amount NOT disclosed
- organic Millet — amount NOT disclosed
- organic Oat Bran — amount NOT disclosed
- organic Quinoa — amount NOT disclosed

**Blend — Hyper-Anabolic Complex** (total: amount NOT disclosed)
- Branched-Chain Amino Acids — 16.1 Gram(s)
- BetaPower Betaine Anhydrous — 2.5 Gram(s)
- Calcium HMB — 500.0 mg
- Digestive Enzyme Blend — 225.0 mg

**Blend — Digestive Enzyme Blend** (total: amount NOT disclosed)
- Aminopeptidase — amount NOT disclosed
- Protease — amount NOT disclosed

**Other ingredients:** Carb Blend, Protein Blend, Fat Blend, Natural and Artificial flavor, Acacia, Polydextrose, Salt, Cellulose Gum, Citric Acid, Sucralose, Acesulfame Potassium, Red 40

**Quality claims stated on the label:** none stated (not evidence testing didn't happen)
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*

> **⚠ DATA NOTE** — 1 ingredient(s) show quantity 0 — our extraction gap, treat as undisclosed; 1 ingredient(s) have no unit — our extraction gap, treat as undisclosed; **Creatine 5.0** is the TOTAL; the entries after it are its constituent forms. Do NOT add them to it
```
ID: PG-F1F4A29ACC94
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 15. Sweet Defense

**Brand:** Nature's Way
**Servings/day:** 3

**Actives:**
- Vitamin A — 1.5 mg (167.0% DV)
- Vitamin C — 200.0 mg (222.0% DV)
- Thiamin — 25.0 mg (2083.0% DV)
- Riboflavin — 25.0 mg (1923.0% DV)
- Niacin — 115.0 mg (719.0% DV)
- Vitamin B6 — 8.0 mg (471.0% DV)
- Vitamin B12 — 25.0 mcg (1042.0% DV)
- Pantothenic Acid — 100.0 mg (2000.0% DV)
- Choline — 40.0 mg (7.0% DV)
- Zinc — 10.0 mg (91.0% DV)
- Manganese — 2.3 mg (100.0% DV)
- Potassium — 50.0 mg (1.0% DV)
- Inositol — 200.0 mg
- METHIONINE — 100.0 mg
- Adrenal powder — 65.0 mg
- Betaine Hydrochloride — 50.0 mg
- Wild Yam — 50.0 mg
- Goldenseal — 10.0 mg

**Other ingredients:** Gelatin, Magnesium Stearate, Silica, Titanium Dioxide color

**Quality claims stated on the label:** none stated (not evidence testing didn't happen)
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*
```
ID: PG-1CD23F9FB8B8
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 16. BCAA 3:1:2 Powder 1500 mg

**Brand:** BulkSupplements.com
**Servings/day:** 1–2

**Actives:**
- Leucine — 750.0 mg
- Isoleucine — 250.0 mg
- Valine — 500.0 mg

**Other ingredients:** Sunflower Lecithin

**Quality claims stated on the label:** none stated (not evidence testing didn't happen)
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*

> **⚠ DATA NOTE** — **Leucine 750.0** is the TOTAL; the entries after it are its constituent forms. Do NOT add them to it
```
ID: PG-655BA8C8528C
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 17. Keto Omega-3 1400 mg

**Brand:** Sports Research
**Servings/day:** 1

**Actives:**
- Fish — 0.0 unit not stated
- Fish Oil — 0.0 unit not stated
- EPA — 840.0 mg
- DHA — 380.0 mg
- Astaxanthin — 500.0 mcg
- Medium chain triglycerides — 2.0 Gram(s)

**Blend — Keto Omega-3 Complex** (total: amount NOT disclosed)
- Phospholipids — 200.0 mg
- Astaxanthin — 500.0 mcg
- Salmon Oil — amount NOT disclosed
- Superba2 — amount NOT disclosed
- Wild Alaska Pollock — amount NOT disclosed

**Other ingredients:** Fish Gelatin, Glycerin, Water, Purified, Tocopherols

**Quality claims stated on the label:** GMP certified/compliant
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*

> **⚠ DATA NOTE** — 2 ingredient(s) show quantity 0 — our extraction gap, treat as undisclosed; 2 ingredient(s) have no unit — our extraction gap, treat as undisclosed
```
ID: PG-723E253A1BDE
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 18. Myopower BCAA Cherry Limeade

**Brand:** GNC AMP Advanced Muscle Performance
**Servings/day:** 1

**Actives:**
- Vitamin D — 26.0 mcg (130.0% DV)
- Calcium — 540.0 mg (42.0% DV)
- Creatine — 3.54 Gram(s)
- Creatine — 1.0 Gram(s)
- Creatine — 460.0 mg
- Leucine — 5.0 Gram(s)
- Isoleucine — 2.5 Gram(s)
- Valine — 2.5 Gram(s)
- Glutamine — 5.0 Gram(s)
- Calcium HMB — 3.0 Gram(s)
- Betaine Anhydrous — 2.5 Gram(s)
- Vitamin D — 13.0 mcg (65.0% DV)
- Calcium — 270.0 mg (21.0% DV)
- Creatine — 1.77 Gram(s)
- Creatine — 500.0 mg
- Creatine — 230.0 mg
- Leucine — 2.5 Gram(s)
- Isoleucine — 1.25 Gram(s)
- Valine — 1.25 Gram(s)
- Glutamine — 2.5 Gram(s)
- Calcium HMB — 1.5 Gram(s)
- Betaine Anhydrous — 1.25 Gram(s)

**Blend — General Proprietary Blends** (total: amount NOT disclosed)

**Blend — Tri-Creatine Complex** (total: amount NOT disclosed)

**Blend — Tri-Creatine Complex** (total: amount NOT disclosed)

**Blend — Tri-Creatine Complex** (total: amount NOT disclosed)
- Creatine — 3.54 Gram(s)
- Creatine — 1.0 Gram(s)
- Creatine — 460.0 mg
- Creatine — 1.77 Gram(s)
- Creatine — 500.0 mg
- Creatine — 230.0 mg

**Other ingredients:** Citric Acid, Natural and Artificial flavors, Tartaric Acid, Malic Acid, Fruit and Vegetable juice, Calcium Silicate, Silicon Dioxide, Gum Arabic, Cellulose Gum, Sucralose, Acesulfame Potassium

**Quality claims stated on the label:** none stated (not evidence testing didn't happen)
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*

> **⚠ DATA NOTE** — **Leucine 5.0** is the TOTAL; the entries after it are its constituent forms. Do NOT add them to it
```
ID: PG-93DEE7631A90
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 19. Vitamin B Complex

**Brand:** Nutricost
**Servings/day:** 1

**Actives:**
- Vitamin C — 40.0 mg (44.0% DV)
- Thiamin — 60.0 mg (5000.0% DV)
- Riboflavin — 75.0 mg (5769.0% DV)
- Niacin — 35.0 mg NE (219.0% DV)
- Vitamin B6 — 50.0 mg (2941.0% DV)
- Folate — 400.0 mcg DFE (100.0% DV)
- Vitamin B12 — 1000.0 mcg (41667.0% DV)
- Biotin — 600.0 mcg (2000.0% DV)
- Pantothenic Acid — 100.0 mg (2000.0% DV)
- Inositol — 50.0 mg
- Choline — 50.0 mg

**Other ingredients:** Dicalcium Phosphate, Hypromellose, Stearic Acid, Rice Flour, Calcium Silicate

**Quality claims stated on the label:** GMP certified/compliant
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*

> **⚠ DATA NOTE** — **Pantothenic Acid 100.0** is the TOTAL; the entries after it are its constituent forms. Do NOT add them to it
```
ID: PG-D4C831D41DA9
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 20. Porcine Collagen Powder 2500 mg

**Brand:** BulkSupplements.com
**Servings/day:** 1–4

**Actives:**
- Collagen — 2500.0 mg

**Other ingredients:** none listed

**Quality claims stated on the label:** none stated (not evidence testing didn't happen)
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*
```
ID: PG-E6414AD93CD7
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 21. Amplified N.O. Loaded V2 Fruit Punch

**Brand:** GNC Pro Performance AMP
**Servings/day:** 1

**Actives:**
- Vitamin D — 2000.0 IU (500.0% DV)
- Niacin — 40.0 mg (200.0% DV)
- Betaine — 5.0 Gram(s)
- Beta-Alanine — 3.6 Gram(s)
- Creatine — 2.5 Gram(s)
- Creatine — 750.0 mg
- Glycocyamine — 70.0 mg
- Alpha-Ketoglutarate — 20.0 mg
- METHIONINE — 10.0 mg
- Arginine — 810.0 mg
- Citrulline — 450.0 mg
- Arginine AKG — 200.0 mg
- Arginine — 180.0 mg
- Resveratrol — 60.0 mg
- Yohimbe — 50.0 mg
- Rhodiola — 40.0 mg
- Caffeine — 300.0 mg
- L-Carnitine — 100.0 mg

**Blend — Power and Performance Matrix** (total: amount NOT disclosed)

**Blend — N.O. Accelerator Blend** (total: amount NOT disclosed)

**Blend — Energizing Fatty Acid Metabolizer Blend** (total: amount NOT disclosed)

**Blend — Power and Performance Matrix** (total: amount NOT disclosed)
- Betaine — 5.0 Gram(s)
- CarnoSyn — 3.6 Gram(s)
- Creatine HCl — 2.5 Gram(s)
- micronized Creatine Monohydrate — 750.0 mg
- Guanidinoacetate — 70.0 mg
- Alpha-Ketoglutarate — 20.0 mg
- L-Methionine — 10.0 mg

**Blend — N.O. Accelerator Blend** (total: amount NOT disclosed)
- L-Arginine — 810.0 mg
- L-Citrulline — 450.0 mg
- Arginine AKG — 200.0 mg
- L-Arginine, Micronized — 180.0 mg
- resVida Trans-Resveratrol — 60.0 mg
- Yohimbe bark powder — 50.0 mg
- Rhodiola rosea extract — 40.0 mg

**Blend — Energizing Fatty Acid Metabolizer Blend** (total: amount NOT disclosed)
- Caffeine Anhydrous — 300.0 mg
- L-Carnitine — 100.0 mg

**Other ingredients:** Citric Acid, Natural and Artificial flavors, Malic Acid, Lecithin, Gum Blend, Tartaric Acid, Calcium Silicate, Silicon Dioxide, Sucralose, Acesulfame Potassium, FD&C Red #40

**Quality claims stated on the label:** purity verified, Informed Choice
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*
```
ID: PG-95C76F9CEBC8
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 22. Precision BCAA Tropical Punch

**Brand:** GNC Beyond Raw
**Servings/day:** 1

**Actives:**
- Calcium — 40.0 mg (4.0% DV)
- Magnesium — 60.0 mg (15.0% DV)
- Potassium — 130.0 mg (4.0% DV)
- Leucine — 5.0 Gram(s)
- Isoleucine — 2.5 Gram(s)
- Valine — 2.5 Gram(s)
- Prickly Pear Cactus — 1.0 Gram(s)

**Other ingredients:** Natural and Artificial flavors, Citric Acid, Malic Acid, Sucralose, Soy Oil and Lecithin Blend, Acesulfame Potassium, Calcium Silicate, FD&C Red #40

**Quality claims stated on the label:** none stated (not evidence testing didn't happen)
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*

> **⚠ DATA NOTE** — **Leucine 5.0** is the TOTAL; the entries after it are its constituent forms. Do NOT add them to it
```
ID: PG-2168B4FFA765
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 23. Amplified 100% Whey Protein Cookies & Cream

**Brand:** GNC Pro Performance AMP
**Servings/day:** 1–2

**Actives:**
- Calcium — 90.0 mg (9.0% DV)
- Potassium — 160.0 mg (5.0% DV)

**Blend — Amino Acceleration System** (total: amount NOT disclosed)
- BioCore Edge(TM) Blend — amount NOT disclosed

**Blend — Micronized Amino Acids** (total: amount NOT disclosed)
- Glutamine — amount NOT disclosed
- Leucine — amount NOT disclosed

**Blend — BioCore Edge(TM) Blend** (total: amount NOT disclosed)
- Peptidase — amount NOT disclosed
- Protease — amount NOT disclosed

**Other ingredients:** Protein Blend, Natural and Artificial flavors, Sunfiber(R) partially hydrolyzed Guar Gum, Polydextrose, Cookie Bits, Polyethylene Glycol, Lecithin, Salt, Titanium Dioxide, Acesulfame Potassium, Sucralose

**Quality claims stated on the label:** none stated (not evidence testing didn't happen)
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*
```
ID: PG-B7FAF442CD30
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 24. Iron Bisglycinate

**Brand:** Thorne
**Servings/day:** 1

**Actives:**
- Iron — 25.0 mg (139.0% DV)

**Other ingredients:** Hypromellose, Microcrystalline Cellulose, Leucine, Silicon Dioxide

**Quality claims stated on the label:** heavy-metal tested, purity verified, label accuracy verified, NSF Sport
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*
```
ID: PG-FC7D426B5131
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 25. B-Complex

**Brand:** GNC Select
**Servings/day:** 1

**Actives:**
- Thiamin — 3.0 mg (250.0% DV)
- Riboflavin — 3.0 mg (231.0% DV)
- Niacin — 20.0 mg (125.0% DV)
- Vitamin B6 — 2.0 mg (118.0% DV)
- Vitamin B12 — 6.0 mcg (250.0% DV)
- Pantothenic Acid — 10.0 mg (200.0% DV)
- Calcium — 134.0 mg (10.0% DV)

**Other ingredients:** Dicalcium Phosphate, Microcrystalline Cellulose, Stearic Acid, Croscarmellose Sodium, Hydroxypropyl Methylcellulose, Magnesium Stearate, Polyethylene Glycol, Triethyl Citrate, Acetoglycerides, Polysorbate 80, Titanium Dioxide, Blue #1 Lake, Red #40, Red #40 Lake, Yellow #6 Lake, Carnauba Wax

**Quality claims stated on the label:** none stated (not evidence testing didn't happen)
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*
```
ID: PG-370A36D46083
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 26. Life Extension Mix Capsules without Copper

**Brand:** Life Extension
**Servings/day:** 1

**Actives:**
- Vitamin A (mixed) — 1500.0 mcg RAE (167.0% DV)
- Vitamin C — 970.0 mg (1078.0% DV)
- Vitamin D — 50.0 mcg (250.0% DV)
- Vitamin E — 67.0 mg (447.0% DV)
- Thiamin — 125.0 mg (10417.0% DV)
- Riboflavin — 50.0 mg (3846.0% DV)
- Niacin — 190.0 mg NE (1188.0% DV)
- Vitamin B6 — 105.0 mg (6176.0% DV)
- Vitamin B6 — 100.0 mg
- Vitamin B6 — 5.0 mg
- Vitamin B9 — 680.0 mcg DFE (170.0% DV)
- Vitamin B12 — 600.0 mcg (25000.0% DV)
- Vitamin B7 — 3000.0 mcg (10000.0% DV)
- Vitamin B5 — 600.0 mg (12000.0% DV)
- Vitamin B5 — 5.0 mg
- Calcium — 140.0 mg (11.0% DV)
- Iodine — 150.0 mcg (100.0% DV)
- Magnesium — 420.0 mg (100.0% DV)
- Zinc — 35.0 mg (318.0% DV)
- Selenium — 200.0 mcg (364.0% DV)
- Manganese — 1.0 mg (43.0% DV)
- Chromium — 500.0 mcg (1429.0% DV)
- Molybdenum — 125.0 mcg (278.0% DV)
- Potassium — 35.0 mg (1.0% DV)
- N-Acetyl Cysteine — 600.0 mg
- Inositol — 250.0 mg
- Bitter Orange Citrus Bioflavonoids — 200.0 mg
- Blueberry — 0.0 unit not stated
- Taurine — 200.0 mg
- Blueberry — 150.0 mg
- Ashwagandha — 125.0 mg
- Silymarin — 100.0 mg
- Betaine — 100.0 mg
- Pomegranate — 85.0 mg
- Vitamin E — 60.0 mg
- bilberry — 30.0 mg
- Grape — 25.0 mg
- Leucoselect Grape seed Proanthocyanidin extract — 25.0 mg
- Quercetin — 15.0 mg
- Quercetin — 5.0 mg
- Bromelain — 15.0 mg
- Lutein — 15.0 mg
- Zeaxanthin — 465.0 mcg
- Sesame Seed Lignan Extract — 10.0 mg
- Luteolin — 8.0 mg
- Apigenin — 5.0 mg
- Boron — 3.0 mg
- Lycopene — 3.0 mg
- Delphinidin — 2.0 mg
- C3G — 1.25 mg

**Blend — Fruit/Berry Proprietary Blend** (total: amount NOT disclosed)
- Blackberry powder — amount NOT disclosed
- Blueberry powder — amount NOT disclosed
- Cranberry powder — amount NOT disclosed
- European Elder powder — amount NOT disclosed
- Persimmon, Powder — amount NOT disclosed
- Plum powder — amount NOT disclosed
- Sweet Cherry powder — amount NOT disclosed

**Blend — Broccoli Concentrate Blend** (total: amount NOT disclosed)
- Broccoli extract — amount NOT disclosed
- Broccoli powder — amount NOT disclosed

**Other ingredients:** Gelatin, Maltodextrin, Silica, Microcrystalline Cellulose, Stearate, Starch

**Quality claims stated on the label:** none stated (not evidence testing didn't happen)
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*

> **⚠ DATA NOTE** — 1 ingredient(s) show quantity 0 — our extraction gap, treat as undisclosed; 1 ingredient(s) have no unit — our extraction gap, treat as undisclosed; **Vitamin B6 105.0** is the TOTAL; the entries after it are its constituent forms. Do NOT add them to it
```
ID: PG-1D9CBDF5812A
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 27. Colostrum 500 mg

**Brand:** Nutricost
**Servings/day:** 1

**Actives:**
- Colostrum — 500.0 mg

**Other ingredients:** Gelatin, Rice Flour, Magnesium Stearate, Silicon Dioxide

**Quality claims stated on the label:** none stated (not evidence testing didn't happen)
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*
```
ID: PG-0383094573F7
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 28. Control & Reduce Fruit Punch

**Brand:** GNC Total Lean
**Servings/day:** 2

**Actives:**
- Potassium — 70.0 mg (2.0% DV)
- L-Carnitine — 1.0 Gram(s)
- Garcinia — 500.0 mg

**Other ingredients:** Polydextrose, Natural and Artificial flavors, Malic Acid, Citric Acid, Calcium Silicate, Sucralose, Acesulfame Potassium, FD&C Red #40

**Quality claims stated on the label:** none stated (not evidence testing didn't happen)
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*
```
ID: PG-7FF5F469B005
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 29. EmulsiSorb K2/D3 Liquid

**Brand:** Pure Encapsulations
**Servings/day:** 6.1

**Actives:**
- Vitamin D — 25.0 mcg (125.0% DV)
- vitamin k2 — 90.0 mcg

**Other ingredients:** Water, Purified, Glycerin, Cellulose, Lemon Oil, Xanthan Gum, Extra Virgin Olive Oil, Citric Acid, Potassium Sorbate, Stevia Leaf Extract, Rosemary Leaf Extract, Mixed Tocopherols

**Quality claims stated on the label:** none stated (not evidence testing didn't happen)
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*

> **⚠ DATA NOTE** — servings-per-day of 6.1 looks implausible and may be our extraction defect — sanity-check against the labeled directions
```
ID: PG-27D1E2CB43AC
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 30. Jarro-Dophilus EPS 25 Billion CFU

**Brand:** Jarrow Formulas
**Servings/day:** 1

**Actives:**
- Proprietary Blend — 413.0 mg

**Blend — Proprietary Probiotic Blend** (total: amount NOT disclosed)
- Bifidobacterium breve R0070 — amount NOT disclosed
- Bifidobacterium longum BB536 — amount NOT disclosed
- Lacticaseibacillus casei R0215 — amount NOT disclosed
- Lacticaseibacillus rhamnosus R0011 — amount NOT disclosed
- Lactiplantibacillus plantarum R1012 — amount NOT disclosed
- Lactobacillus helveticus R0052 — amount NOT disclosed
- Lactococcus lactis lactis R1058 — amount NOT disclosed
- Pediococcus acidilactici R1001 — amount NOT disclosed

**Other ingredients:** Potato Starch, Hydroxypropyl Methylcellulose, Water, Hypromellose, Ethylcellulose, Sodium Alginate, Medium Chain Triglyceride, Oleic Acid, Stearic Acid, Magnesium Stearate, Ascorbic Acid

**Quality claims stated on the label:** none stated (not evidence testing didn't happen)
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*
```
ID: PG-11E2CA6057D3
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 31. Essential Amino Acids

**Brand:** GNC Pro Performance
**Servings/day:** 1–2

**Actives:**
- Micro-Peptide Essential Amino Complex — 1600.0 mg
- Whey Protein — 100.0 mg

**Blend — Micro-Peptide Essential Amino Complex** (total: amount NOT disclosed)
- L-Histidine — amount NOT disclosed
- L-Isoleucine — amount NOT disclosed
- L-Leucine — amount NOT disclosed
- L-Lysine — amount NOT disclosed
- L-Methionine — amount NOT disclosed
- L-Phenylalanine — amount NOT disclosed
- L-Threonine — amount NOT disclosed
- L-Tryptophan — amount NOT disclosed
- L-Valine — amount NOT disclosed

**Other ingredients:** Cellulose, Stearic Acid, Titanium Dioxide, Magnesium Stearate, Vegetable Acetoglycerides, natural Vanilla Mint flavor, Caramel color, Stevia leaf extract

**Quality claims stated on the label:** none stated (not evidence testing didn't happen)
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*
```
ID: PG-064FBE2FDBB7
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 32. Homocysteine Resist

**Brand:** Life Extension
**Servings/day:** 1

**Actives:**
- Riboflavin — 25.0 mg (1923.0% DV)
- Vitamin B6 (unspecified) — 100.0 mg (5882.0% DV)
- Vitamin B9 — 8500.0 mcg DFE (2125.0% DV)
- Vitamin B12 — 1000.0 mcg (41667.0% DV)

**Other ingredients:** Microcrystalline Cellulose, Vegetable Cellulose, Stearic Acid, Silica, Rice Extract Blend

**Quality claims stated on the label:** none stated (not evidence testing didn't happen)
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*
```
ID: PG-E20F794EDAE9
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 33. Amplified N.O. Loaded V2 Watermelon

**Brand:** GNC Pro Performance AMP
**Servings/day:** 1

**Actives:**
- Vitamin D — 1000.0 IU (250.0% DV)
- Niacin — 20.0 mg (100.0% DV)
- Betaine — 2.5 Gram(s)
- Beta-Alanine — 1.8 Gram(s)
- Creatine — 1.25 Gram(s)
- Creatine — 750.0 mg
- Glycocyamine — 35.0 mg
- Alpha-Ketoglutarate — 10.0 mg
- METHIONINE — 5.0 mg
- Arginine — 810.0 mg
- Citrulline — 225.0 mg
- Arginine AKG — 100.0 mg
- Arginine — 90.0 mg
- Resveratrol — 30.0 mg
- Yohimbe — 25.0 mg
- Rhodiola — 20.0 mg
- Caffeine — 150.0 mg
- L-Carnitine — 50.0 mg

**Blend — Power and Performance Matrix** (total: amount NOT disclosed)

**Blend — N.O. Accelerator Blend** (total: amount NOT disclosed)

**Blend — Energizing Fatty Acid Metabolizer Blend** (total: amount NOT disclosed)
- Caffeine Anhydrous — 150.0 mg
- L-Carnitine — 50.0 mg

**Blend — Power and Performance Matrix** (total: amount NOT disclosed)
- Betaine — 2.5 Gram(s)
- CarnoSyn — 1.8 Gram(s)
- Creatine HCl — 1.25 Gram(s)
- micronized Creatine Monohydrate — 750.0 mg
- Guanidinoacetate — 35.0 mg
- Alpha-Ketoglutarate — 10.0 mg
- L-Methionine — 5.0 mg

**Blend — N.O. Accelerator Blend** (total: amount NOT disclosed)
- L-Arginine — 810.0 mg
- L-Citrulline — 225.0 mg
- Arginine AKG — 100.0 mg
- L-Arginine, Micronized — 90.0 mg
- resVida Trans-Resveratrol — 30.0 mg
- Yohimbe bark powder — 25.0 mg
- Rhodiola rosea extract — 20.0 mg

**Other ingredients:** Natural and Artificial flavors, Citric Acid, Malic Acid, Gum Blend, Lecithin, Calcium Silicate, Silicon Dioxide, Sucralose, Tartaric Acid, Beet color, Acesulfame Potassium

**Quality claims stated on the label:** purity verified, Informed Choice
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*
```
ID: PG-810453D1B6DE
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 34. Extra Strength Probiotic Juicy Apple

**Brand:** OLLY
**Servings/day:** 1

**Actives:**
- Bacillus Coagulans — 66.0 mg
- Bacillus Subtilis — 50.0 mg

**Other ingredients:** Cane Sugar, Glucose Syrup, Water, Gelatin, Lactic Acid, Natural flavors, Citric Acid, Tartaric Acid, Mixed Tocopherols, Coloring

**Quality claims stated on the label:** none stated (not evidence testing didn't happen)
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*
```
ID: PG-C713BDB0F7EE
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 35. Golden Milk

**Brand:** Garden of Life MyKind Organics
**Servings/day:** 1

**Actives:**
- Iron — 1.0 mg (6.0% DV)
- Potassium — 50.0 mg (2.0% DV)
- Organic Golden Milk Blend — 3.2 Gram(s)

**Blend — Probiotic Blend** (total: amount NOT disclosed)
- Bifidobacterium lactis Bl-04 — amount NOT disclosed
- Lactobacillus acidophilus La-14 — amount NOT disclosed

**Blend — Organic Golden Milk Blend** (total: amount NOT disclosed)
- Ashwagandha — amount NOT disclosed
- Black Pepper — amount NOT disclosed
- Cardamom — amount NOT disclosed
- Cinnamon — amount NOT disclosed
- Coconut Water, Powder — amount NOT disclosed
- Ginger — amount NOT disclosed
- Organic Turmeric Blend — amount NOT disclosed
- Tapioca Fiber — amount NOT disclosed

**Blend — Organic Turmeric Blend** (total: amount NOT disclosed)
- Turmeric — amount NOT disclosed
- Turmeric root extract — amount NOT disclosed
- organic fermented Turmeric — amount NOT disclosed

**Other ingredients:** Organic flavors

**Quality claims stated on the label:** none stated (not evidence testing didn't happen)
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*
```
ID: PG-25E70418F299
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 36. Stress B-Complex

**Brand:** Thorne
**Servings/day:** 1–3

**Actives:**
- Thiamin — 50.0 mg (4167.0% DV)
- Riboflavin — 28.6 mg (2200.0% DV)
- Riboflavin — 25.0 mg
- Riboflavin — 3.6 mg
- Niacin — 80.0 mg (500.0% DV)
- Vitamin B6 — 28.4 mg (1671.0% DV)
- Vitamin B6 — 25.0 mg
- Vitamin B6 — 3.4 mg
- Folate — 334.0 mcg DFE (84.0% DV)
- Folate — 200.0 mcg
- Vitamin B12 — 100.0 mcg (4167.0% DV)
- Biotin — 80.0 mcg (267.0% DV)
- Pantothenic Acid — 250.0 mg (5000.0% DV)
- Choline — 14.0 mg (3.0% DV)

**Other ingredients:** Hypromellose, Microcrystalline Cellulose, Calcium Laurate, Silicon Dioxide

**Quality claims stated on the label:** heavy-metal tested, purity verified, label accuracy verified, NSF Contents Certified
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*

> **⚠ DATA NOTE** — **Riboflavin 28.6** is the TOTAL; the entries after it are its constituent forms. Do NOT add them to it
```
ID: PG-D8AA753A2379
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 37. Whey To Go Protein Powder Unflavored

**Brand:** Solgar
**Servings/day:** 1

**Actives:**
- Vitamin D — 0.0 mcg
- Calcium — 60.0 mg (4.0% DV)
- Iron — 0.2 mg
- Potassium — 210.0 mg (4.0% DV)

**Other ingredients:** Whey Protein concentrate, Sunflower Lecithin

**Quality claims stated on the label:** none stated (not evidence testing didn't happen)
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*

> **⚠ DATA NOTE** — 1 ingredient(s) show quantity 0 — our extraction gap, treat as undisclosed
```
ID: PG-36708F435DB4
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 38. PRE Pre-Workout Complex Blue Raspberry

**Brand:** Nutricost Performance
**Servings/day:** 1

**Actives:**
- Thiamin — 50.0 mg (4170.0% DV)
- Niacin — 25.0 mg NE (160.0% DV)
- Vitamin B6 — 60.0 mg (3530.0% DV)
- Vitamin B12 — 200.0 mcg (8330.0% DV)
- Citrulline — 6000.0 mg
- Beta-Alanine — 3000.0 mg
- Taurine — 2000.0 mg
- Agmatine — 500.0 mg
- Tyrosine — 500.0 mg
- Theanine — 300.0 mg
- Caffeine — 300.0 mg
- Theobromine — 200.0 mg
- Huperzine — 200.0 mcg

**Other ingredients:** Natural Flavors, Malic Acid, Citric Acid, Calcium Silicate, Silica, Sucralose, Blue Spirulina

**Quality claims stated on the label:** GMP certified/compliant
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*

> **⚠ DATA NOTE** — **Beta-Alanine 3000.0** is the TOTAL; the entries after it are its constituent forms. Do NOT add them to it
```
ID: PG-29AD138914AC
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 39. Iron Chelate with Ferrochel 36 mg

**Brand:** Nutricost
**Servings/day:** 1

**Actives:**
- Iron — 36.0 mg (200.0% DV)

**Other ingredients:** Rice Flour, Hypromellose, Magnesium Stearate

**Quality claims stated on the label:** none stated (not evidence testing didn't happen)
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*
```
ID: PG-C612F4B7431D
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 40. Menopause Formula

**Brand:** GNC Women's
**Servings/day:** 1

**Actives:**
- Black Cohosh — 160.0 mg

**Other ingredients:** Cellulose, Gelatin, Maltodextrin

**Quality claims stated on the label:** none stated (not evidence testing didn't happen)
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*
```
ID: PG-6B5C78DF8E99
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 41. BCAA 1000 mg

**Brand:** Nutricost Performance
**Servings/day:** 1

**Actives:**
- Leucine — 500.0 mg
- Isoleucine — 250.0 mg
- Valine — 250.0 mg

**Other ingredients:** Gelatin, Rice Flour, Magnesium Stearate, Microcrystalline Cellulose

**Quality claims stated on the label:** GMP certified/compliant
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*

> **⚠ DATA NOTE** — **Leucine 500.0** is the TOTAL; the entries after it are its constituent forms. Do NOT add them to it
```
ID: PG-4606803BD408
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 42. Emotional Wellness

**Brand:** Pure Encapsulations
**Servings/day:** 1–3

**Actives:**
- Vitamin B6 — 6.7 mg (394.0% DV)
- 5-HTP — 100.0 mg
- Tyrosine — 100.0 mg
- GABA — 200.0 mg
- Theanine — 100.0 mg
- Rhodiola — 100.0 mg
- Passionflower — 85.0 mg

**Other ingredients:** Vegetarian Capsule, Ascorbyl Palmitate

**Quality claims stated on the label:** none stated (not evidence testing didn't happen)
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*

> **⚠ DATA NOTE** — **GABA 200.0** is the TOTAL; the entries after it are its constituent forms. Do NOT add them to it
```
ID: PG-7BF4C151BCD5
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 43. Herbal Immune Balance Sinus

**Brand:** Garden of Life
**Servings/day:** 1

**Actives:**
- Vitamin C — 250.0 mg (280.0% DV)
- Vitamin D — 25.0 mcg (125.0% DV)
- Saccharomyces boulardii — 250.0 mg
- Butterbur — 100.0 mg
- Beta-Glucans — 10.0 mg

**Blend — Herbal Immune Support Blend** (total: amount NOT disclosed)
- Acerola Cherry — amount NOT disclosed
- Angelica — amount NOT disclosed
- Citrus Bioflavonoid — amount NOT disclosed
- Elderberry Fruit Extract — amount NOT disclosed
- Ginger — amount NOT disclosed
- Lemon Balm — amount NOT disclosed
- Olive Leaf Extract — amount NOT disclosed

**Blend — Sinus Enzyme Blend** (total: amount NOT disclosed)
- Bromelain — amount NOT disclosed
- Protease — amount NOT disclosed

**Blend — RAW Citrus C Blend** (total: amount NOT disclosed)
- Amla, Raw — amount NOT disclosed
- Citrus Bioflavonoids — amount NOT disclosed

**Other ingredients:** Potato Starch, Cellulose

**Quality claims stated on the label:** none stated (not evidence testing didn't happen)
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*
```
ID: PG-C63EFDE88116
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 44. PreNatal Nutrients

**Brand:** Pure Encapsulations
**Servings/day:** 1

**Actives:**
- Vitamin A — 2400.0 mcg (267.0% DV)
- Vitamin C — 70.0 mg (78.0% DV)
- Vitamin D — 25.0 mcg (125.0% DV)
- Vitamin E — 12.0 mg (80.0% DV)
- Vitamin K (unspecified) — 90.0 mcg (75.0% DV)
- Thiamin — 1.6 mg (133.0% DV)
- Riboflavin — 1.7 mg (131.0% DV)
- Niacin — 20.0 mg (125.0% DV)
- Vitamin B6 — 2.2 mg (129.0% DV)
- Folate — 1667.0 mcg DFE (417.0% DV)
- Vitamin B9 — 1000.0 mcg
- Vitamin B12 — 2.6 mcg (108.0% DV)
- Biotin — 300.0 mcg (1000.0% DV)
- Pantothenic Acid — 6.0 mg (120.0% DV)
- Choline — 100.0 mg (18.0% DV)
- Calcium — 200.0 mg (15.0% DV)
- Iron — 27.0 mg (150.0% DV)
- Iodine — 150.0 mcg (100.0% DV)
- Magnesium — 80.0 mg (19.0% DV)
- Zinc — 15.0 mg (136.0% DV)
- Selenium — 70.0 mcg (127.0% DV)
- Copper — 1.0 mg (111.0% DV)
- Manganese — 2.0 mg (87.0% DV)
- Chromium — 120.0 mcg (343.0% DV)
- Molybdenum — 75.0 mcg (167.0% DV)

**Blend — Proprietary Mixed Carotenoid Blend** (total: amount NOT disclosed)
- Lutein — amount NOT disclosed
- Lycopene — amount NOT disclosed
- Zeaxanthin — amount NOT disclosed

**Other ingredients:** Cellulose, Water, Ascorbyl Palmitate

**Quality claims stated on the label:** none stated (not evidence testing didn't happen)
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*
```
ID: PG-023E4313E170
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 45. Super B Energy Complex

**Brand:** Nature Made
**Servings/day:** 1

**Actives:**
- Thiamin — 1.5 mg (100.0% DV)
- Riboflavin — 1.7 mg (100.0% DV)
- Niacin — 20.0 mg (100.0% DV)
- Vitamin B6 — 2.0 mg (100.0% DV)
- Folate — 400.0 mcg (100.0% DV)
- Vitamin B12 — 6.0 mcg (100.0% DV)
- Biotin — 300.0 mcg (100.0% DV)
- Pantothenic Acid — 10.0 mg (100.0% DV)

**Other ingredients:** Soybean Oil, Gelatin, Dibasic Calcium Phosphate, Glycerin, yellow Beeswax, Water, Colors added, Soy Lecithin, Resin

**Quality claims stated on the label:** none stated (not evidence testing didn't happen)
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*
```
ID: PG-26B55677FA72
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 46. Garcinia Cambogia Extract (60% HCA)

**Brand:** BulkSupplements.com
**Servings/day:** 1–3

**Actives:**
- Garcinia — 500.0 mg

**Other ingredients:** none listed

**Quality claims stated on the label:** none stated (not evidence testing didn't happen)
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*
```
ID: PG-7983AC0537CA
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 47. Daily Immune

**Brand:** Pure Encapsulations
**Servings/day:** 1

**Actives:**
- Vitamin C — 200.0 mg (222.0% DV)
- Vitamin D — 10.0 mcg (50.0% DV)
- Zinc — 10.0 mg (91.0% DV)
- Quercetin — 200.0 mg
- European Elder — 150.0 mg
- lemon balm — 200.0 mg
- Arabinogalactan — 200.0 mg
- Aloe vera (Aloe barbadensis) extract — 50.0 mg
- Maitake Mushroom — 150.0 mg
- Astragalus — 75.0 mg
- Eleuthero — 0.0 unit not stated

**Other ingredients:** Cellulose, Water

**Quality claims stated on the label:** none stated (not evidence testing didn't happen)
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*

> **⚠ DATA NOTE** — 1 ingredient(s) show quantity 0 — our extraction gap, treat as undisclosed; 1 ingredient(s) have no unit — our extraction gap, treat as undisclosed; **Arabinogalactan 200.0** is the TOTAL; the entries after it are its constituent forms. Do NOT add them to it
```
ID: PG-002B9397C329
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 48. Basic B Complex

**Brand:** Thorne
**Servings/day:** 1–3

**Actives:**
- Thiamin — 110.0 mg (9167.0% DV)
- Vitamin B2 — 10.0 mg (769.0% DV)
- Niacin — 140.0 mg (875.0% DV)
- Niacin — 130.0 mg
- Niacin — 10.0 mg
- Vitamin B6 (unspecified) — 10.0 mg (588.0% DV)
- Folate — 667.0 mcg (167.0% DV)
- Vitamin B9 (methyltetrahydrofolate) — 400.0 mcg
- Vitamin B12 — 400.0 mcg (16667.0% DV)
- Biotin — 400.0 mcg (1333.0% DV)
- Pantothenic Acid — 110.0 mg (2200.0% DV)
- Choline — 28.0 mg (5.0% DV)

**Other ingredients:** Hypromellose capsule, Microcrystalline Cellulose, Calcium Laurate, Leucine, Magnesium Citrate, Silicon Dioxide

**Quality claims stated on the label:** none stated (not evidence testing didn't happen)
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*

> **⚠ DATA NOTE** — **Niacin 140.0** is the TOTAL; the entries after it are its constituent forms. Do NOT add them to it
```
ID: PG-B94328E47826
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 49. Magnesium CitraMate

**Brand:** Thorne
**Servings/day:** 1–3

**Actives:**
- Magnesium — 135.0 mg (32.0% DV)
- Magnesium — 55.0 mg
- Magnesium — 80.0 mg

**Other ingredients:** Hypromellose, Medium Chain Triglyceride Oil

**Quality claims stated on the label:** heavy-metal tested, purity verified, label accuracy verified, NSF Contents Certified
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*

> **⚠ DATA NOTE** — **Magnesium 135.0** is the TOTAL; the entries after it are its constituent forms. Do NOT add them to it
```
ID: PG-F715707D8FA8
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 50. NutraSea Omega-3 Softgels Fresh Mint Flavored

**Brand:** Nature's Way
**Servings/day:** 1

**Actives:**
- Fish Oil — 1.8 Gram(s)
- EPA — 750.0 mg
- DHA — 500.0 mg

**Other ingredients:** Gelatin, Glycerin, purified Water, Natural flavor, Mixed Tocopherols, Sunflower Oil, Rosemary extract, Ascorbyl Palmitate

**Quality claims stated on the label:** none stated (not evidence testing didn't happen)
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*
```
ID: PG-024D4950CC18
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 51. PRE Pre-Workout Complex Grape

**Brand:** Nutricost Performance
**Servings/day:** 0.065

**Actives:**
- Thiamin — 50.0 mg (4170.0% DV)
- Niacin — 25.0 mg NE (160.0% DV)
- Vitamin B6 — 60.0 mg (3530.0% DV)
- Vitamin B12 — 200.0 mcg (8330.0% DV)
- Citrulline — 6000.0 mg
- Beta-Alanine — 3000.0 mg
- Taurine — 2000.0 mg
- Agmatine — 500.0 mg
- Tyrosine — 500.0 mg
- Theanine — 300.0 mg
- Caffeine — 300.0 mg
- Theobromine — 200.0 mg
- Huperzine — 200.0 mcg

**Other ingredients:** Natural Flavors, Tartaric Acid, Calcium Silicate, Silica, Citric Acid, Sucralose, Fruit Juice

**Quality claims stated on the label:** GMP certified/compliant
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*

> **⚠ DATA NOTE** — servings-per-day below 1 is our defect — assume **1 serving/day**; **Beta-Alanine 3000.0** is the TOTAL; the entries after it are its constituent forms. Do NOT add them to it
```
ID: PG-6E40D3FAE99F
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 52. Psyllium Seed Husk 500 mg

**Brand:** GNC Natural Brand
**Servings/day:** 3

**Actives:**
- Psyllium fiber — 1000.0 mg

**Other ingredients:** Gelatin, Cellulose, Oat Bran powder

**Quality claims stated on the label:** none stated (not evidence testing didn't happen)
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*
```
ID: PG-F3B4F55D8319
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 53. Prostate+

**Brand:** Garden of Life Dr. Formulated Probiotics
**Servings/day:** 1

**Actives:**
- Vitamin D — 25.0 mcg (125.0% DV)
- cranberry — 500.0 mg

**Blend — Men's Probiotic Blend** (total: amount NOT disclosed)
- Bifidobacterium animalis lactis — amount NOT disclosed
- Bifidobacterium animalis subsp. lactis — amount NOT disclosed
- Bifidobacterium bifidum — amount NOT disclosed
- Bifidobacterium breve — amount NOT disclosed
- Bifidobacterium longum — amount NOT disclosed
- Bifidobacterium longum infantis — amount NOT disclosed
- Lactobacillus acidophilus — amount NOT disclosed
- Lactobacillus brevis — amount NOT disclosed
- Lactobacillus bulgaricus — amount NOT disclosed
- Lactobacillus casei — amount NOT disclosed
- Lactobacillus gasseri — amount NOT disclosed
- Lactobacillus paracasei — amount NOT disclosed
- Lactobacillus plantarum — amount NOT disclosed
- Lactobacillus rhamnosus — amount NOT disclosed
- Lactobacillus salivarius — amount NOT disclosed

**Blend — Organic Prebiotic Fiber Blend** (total: amount NOT disclosed)
- Acacia Fiber — amount NOT disclosed
- organic Potato — amount NOT disclosed

**Other ingredients:** Cellulose

**Quality claims stated on the label:** none stated (not evidence testing didn't happen)
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*
```
ID: PG-73768E384096
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 54. Re-Built Mass Vanilla Cake Batter

**Brand:** GNC Beyond Raw
**Servings/day:** 1

**Actives:**
- Calcium — 500.0 mg (50.0% DV)
- Potassium — 500.0 mg (14.0% DV)
- Leucine — 6.2 Gram(s)
- Leucine — 0.0 unit not stated
- Betaine Anhydrous — 3.0 g
- Quercetin — 1.0 g
- Fenugreek — 600.0 mg
- HMB powder — 500.0 mg

**Blend — Advanced Creatine Complex** (total: amount NOT disclosed)
- Creatine AKG — amount NOT disclosed
- Creatine Ethyl Ester HCl — amount NOT disclosed
- L-Arginine, Micronized — amount NOT disclosed
- L-Glycine, Micronized — amount NOT disclosed
- L-Methionine, Micronized — amount NOT disclosed
- micronized AKG — amount NOT disclosed
- micronized Creatine Monohydrate — amount NOT disclosed
- micronized Guanidinoacetate — amount NOT disclosed

**Blend — Leucine** (total: amount NOT disclosed)
- Calcium Caseinate — amount NOT disclosed
- L-Leucine — amount NOT disclosed
- Soy Protein isolate — amount NOT disclosed
- Whey Protein concentrate — amount NOT disclosed
- Whey Protein isolate — amount NOT disclosed
- hydrolyzed Whey Peptides — amount NOT disclosed

**Blend — BioCore Edge (Non-Nutrient/Non-Botanical)** (total: amount NOT disclosed)
- Peptidase — amount NOT disclosed
- Protease — amount NOT disclosed

**Other ingredients:** Carbohydrate Blend, Protein Blend, Fat Blend, Natural and Artificial flavors, Titanium Dioxide, Lecithin, Salt, Acesulfame Potassium, Sucralose

**Quality claims stated on the label:** none stated (not evidence testing didn't happen)
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*

> **⚠ DATA NOTE** — 1 ingredient(s) show quantity 0 — our extraction gap, treat as undisclosed; 1 ingredient(s) have no unit — our extraction gap, treat as undisclosed
```
ID: PG-FEDFB08C241D
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 55. Preseries Lean Pre-Workout Tropical Punch

**Brand:** Transparent Labs
**Servings/day:** 0.06

**Actives:**
- Zinc — 15.0 mg (136.0% DV)
- Copper — 1.0 mg (111.0% DV)
- Iodine — 225.0 mcg (150.0% DV)
- Chromium — 200.0 mcg (571.0% DV)
- Selenium — 55.0 mcg (100.0% DV)
- Citrulline malate — 6000.0 mg
- Beta-Alanine — 2000.0 mg
- Betaine Anhydrous — 1500.0 mg
- Acetyl-L-Carnitine — 1000.0 mg
- Choline — 500.0 mg
- Theanine — 180.0 mg
- Caffeine — 180.0 mg
- Theobromine — 50.0 mg
- Huperzine — 100.0 mcg

**Other ingredients:** Natural Flavors, Calcium Silicate, Silicon Dioxide, Stevia Extract, Rebaudioside M, Beet, Powder

**Quality claims stated on the label:** none stated (not evidence testing didn't happen)
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*

> **⚠ DATA NOTE** — servings-per-day below 1 is our defect — assume **1 serving/day**; **Betaine Anhydrous 1500.0** is the TOTAL; the entries after it are its constituent forms. Do NOT add them to it
```
ID: PG-6FE4012DDE66
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 56. FloraPro-LP Probiotic

**Brand:** Thorne
**Servings/day:** 1

**Actives:**
- Probiotic Blend — 120.0 mg

**Blend — Probiotic Blend** (total: amount NOT disclosed)
- Lactobacillus plantarum DSM-6595 — amount NOT disclosed

**Other ingredients:** Microcrystalline Cellulose, Hydroxypropyl Methylcellulose, Pectin, Rice Bran Extract, Sodium Carbonate, Turmeric

**Quality claims stated on the label:** none stated (not evidence testing didn't happen)
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*
```
ID: PG-27F7990EDD5A
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 57. Precision BCAA Mango Melon

**Brand:** GNC Beyond Raw
**Servings/day:** 1

**Actives:**
- Calcium — 70.0 mg (5.0% DV)
- Magnesium — 50.0 mg (12.0% DV)
- Chromium — 1000.0 mcg (2857.0% DV)
- Potassium — 240.0 mg (5.0% DV)
- Leucine — 5.0 Gram(s)
- Isoleucine — 2.5 Gram(s)
- Valine — 2.5 Gram(s)
- Betaine Anhydrous — 2.5 Gram(s)

**Blend — Velositol Amylopectin Chromium Complex** (total: amount NOT disclosed)

**Other ingredients:** Natural and Artificial flavors, Citric Acid, Malic Acid, Sucralose, Acesulfame Potassium, Calcium Carbonate, Calcium Silicate, Sunflower Lecithin, FD&C Yellow #6, Polyglycerol Polyricinoleate, fractionated Coconut Oil, Citrus Oil, Olive Oil, Mono and Diglycerides, Oat Oil, Silica

**Quality claims stated on the label:** none stated (not evidence testing didn't happen)
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*

> **⚠ DATA NOTE** — **Leucine 5.0** is the TOTAL; the entries after it are its constituent forms. Do NOT add them to it
```
ID: PG-E032C859178D
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 58. Platinum Series Restore Immune with Zinc

**Brand:** Garden of Life Dr. Formulated
**Servings/day:** 1

**Actives:**
- Vitamin D — 20.0 mcg (100.0% DV)
- Zinc — 11.0 mg (100.0% DV)

**Blend — Restore Immune Probiotic Blend** (total: amount NOT disclosed)
- Bacillus subtilis DE111 — amount NOT disclosed
- Bifidobacterium animalis lactis BL818 — amount NOT disclosed
- Bifidobacterium bifidum Bb-06 — amount NOT disclosed
- Bifidobacterium infantis Bi-26 — amount NOT disclosed
- Bifidobacterium longum Bl-05 — amount NOT disclosed
- Lactobacillus acidophilus La-14 — amount NOT disclosed
- Lactobacillus acidophilus NCFM — amount NOT disclosed
- Lactobacillus bulgaricus Lb-87 — amount NOT disclosed
- Lactobacillus casei Lc-11 — amount NOT disclosed
- Lactobacillus gasseri Lg-36 — amount NOT disclosed
- Lactobacillus paracasei Lpc-37 — amount NOT disclosed
- Lactobacillus plantarum Lp-115 — amount NOT disclosed
- Lactobacillus rhamnosus GG — amount NOT disclosed

**Blend — Pre- & Post-biotic Blend** (total: amount NOT disclosed)
- Immuno-LP20 — amount NOT disclosed
- organic Acacia Fiber — amount NOT disclosed
- organic Potato — amount NOT disclosed

**Other ingredients:** non-GMO Vegetable Cellulose

**Quality claims stated on the label:** none stated (not evidence testing didn't happen)
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*
```
ID: PG-70B72879EB5C
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 59. Advanced Multi-Billion Dophilus

**Brand:** Solgar
**Servings/day:** 1–2

**Actives:**
- Proprietary Blend — 0.0 unit not stated

**Blend — Advanced Multi-Billion Dophilus Complex** (total: amount NOT disclosed)
- B. lactis, BB-12 — amount NOT disclosed
- L. acidophilus, LA-5 — amount NOT disclosed
- L. paracasei, L. CASEI 431 — amount NOT disclosed
- L. rhamnosus GG, LGG — amount NOT disclosed

**Other ingredients:** Vegetable Cellulose

**Quality claims stated on the label:** none stated (not evidence testing didn't happen)
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*

> **⚠ DATA NOTE** — 1 ingredient(s) show quantity 0 — our extraction gap, treat as undisclosed; 1 ingredient(s) have no unit — our extraction gap, treat as undisclosed
```
ID: PG-9F1484B84FC8
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 60. L-Citrulline

**Brand:** BulkSupplements.com
**Servings/day:** 0.33–0.66

**Actives:**
- Citrulline — 3.0 Gram(s)

**Other ingredients:** none listed

**Quality claims stated on the label:** none stated (not evidence testing didn't happen)
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*

> **⚠ DATA NOTE** — servings-per-day below 1 is our defect — assume **1 serving/day**
```
ID: PG-792FF8A754FD
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 61. Omega-3 1055 mg Fish Oil 1250 mg

**Brand:** Sports Research
**Servings/day:** 1

**Actives:**
- Fish Oil — 1250.0 mg
- EPA — 690.0 mg
- DHA — 310.0 mg

**Other ingredients:** Fish Gelatin, Glycerin, Water, Purified, Tocopherols

**Quality claims stated on the label:** GMP certified/compliant, heavy-metal tested, purity verified, IFOS, Friend of the Sea
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*
```
ID: PG-3D30DE8D22F3
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 62. Amplified Wheybolic Extreme 60 Ripped French Vanilla

**Brand:** GNC Pro Performance AMP
**Servings/day:** 1–2

**Actives:**
- Niacin — 6.6 mg (33.0% DV)
- Calcium — 90.0 mg (9.0% DV)
- Potassium — 130.0 mg (4.0% DV)
- Glutamine — 10.0 Gram(s)
- Leucine — 10.0 Gram(s)
- Leucine — 0.0 unit not stated
- Arginine — 1.0 Gram(s)
- Alanine — 3.0 Gram(s)
- Tyrosine — 2.0 Gram(s)
- METHIONINE — 1.5 Gram(s)
- L-Carnitine — 1.0 Gram(s)
- Caffeine — 66.0 mg
- Piperine — 1.6 mg

**Blend — Amino Acid Blend** (total: amount NOT disclosed)
- Glutamine — 10.0 Gram(s)
- Leucine — 10.0 Gram(s)
- Arginine — 1.0 Gram(s)

**Blend — Digestive Enzyme Blends** (total: amount NOT disclosed)

**Blend — Metabolizer Matrix** (total: amount NOT disclosed)

**Blend — Shredded Complex** (total: amount NOT disclosed)

**Blend — Amino Acceleration System** (total: amount NOT disclosed)

**Blend — Glutamine** (total: amount NOT disclosed)
- as Whey Protein isolate — amount NOT disclosed
- hydrolyzed Whey Protein — amount NOT disclosed

**Blend — Leucine** (total: amount NOT disclosed)
- L-Leucine, Micronized — amount NOT disclosed
- as Whey Protein isolate — amount NOT disclosed
- hydrolyzed Whey Protein — amount NOT disclosed

**Blend — Arginine** (total: amount NOT disclosed)
- as Whey Protein isolate — amount NOT disclosed
- hydrolyzed Whey Protein — amount NOT disclosed

**Blend — Metabolizer Matrix** (total: amount NOT disclosed)
- Alanine — 3.0 Gram(s)
- Tyrosine — 2.0 Gram(s)
- Methionine — 1.5 Gram(s)
- L-Carnitine — 1.0 Gram(s)

**Blend — Alanine** (total: amount NOT disclosed)
- as Whey Protein isolate — amount NOT disclosed
- hydrolyzed Whey Protein — amount NOT disclosed

**Blend — Tyrosine** (total: amount NOT disclosed)
- as Whey Protein isolate — amount NOT disclosed
- hydrolyzed Whey Protein — amount NOT disclosed

**Blend — Methionine** (total: amount NOT disclosed)
- as Whey Protein isolate — amount NOT disclosed
- hydrolyzed Whey Protein — amount NOT disclosed

**Blend — Shredded Complex** (total: amount NOT disclosed)
- Svetol Green Coffee extract — 133.0 mg
- Caffeine — 66.0 mg
- Capsimax(TM) Capsicum Extract — 33.0 mg
- Brown Seaweed — 16.0 mg
- Piperine beadlets — 1.6 mg

**Blend — Enzyme Matrix Blend** (total: amount NOT disclosed)
- Enzyme Blend — amount NOT disclosed

**Blend — Enzyme Matrix Blend** (total: amount NOT disclosed)
- Aminogen — amount NOT disclosed
- Carbogen — amount NOT disclosed

**Blend — Enzyme Blend** (total: amount NOT disclosed)
- Alpha-Galactosidase — amount NOT disclosed
- Amylase — amount NOT disclosed
- Bromelain — amount NOT disclosed
- CereCalase — amount NOT disclosed
- Glucoamylase — amount NOT disclosed
- Invertase — amount NOT disclosed
- Lactase — amount NOT disclosed
- Lipase — amount NOT disclosed
- Peptidase — amount NOT disclosed
- Protease — amount NOT disclosed
- Protease 3 — amount NOT disclosed
- Protease 4.5 — amount NOT disclosed
- Protease 6 — amount NOT disclosed

**Other ingredients:** Protein Blend, Natural and Artificial flavors, Lecithin, Titanium Dioxide, Non-Fat Milk Powder, Cellulose Gum, Sucralose, Salt, Acesulfame Potassium

**Quality claims stated on the label:** none stated (not evidence testing didn't happen)
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*

> **⚠ DATA NOTE** — 1 ingredient(s) show quantity 0 — our extraction gap, treat as undisclosed; 1 ingredient(s) have no unit — our extraction gap, treat as undisclosed; **Glutamine 10.0** is the TOTAL; the entries after it are its constituent forms. Do NOT add them to it
```
ID: PG-75FA95380F6A
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 63. Sublingual Liquid B Complex

**Brand:** Nature's Bounty
**Servings/day:** 1–4

**Actives:**
- Vitamin B2 — 1.7 mg (131.0% DV)
- Niacin — 20.0 mg (125.0% DV)
- Vitamin B6 — 2.0 mg (118.0% DV)
- Vitamin B12 — 1200.0 mcg (50000.0% DV)
- Pantothenic Acid — 30.0 mg (600.0% DV)

**Other ingredients:** purified Water, Sorbitol, Vegetable Glycerin, Citric Acid, Natural Flavors, Potassium Sorbate

**Quality claims stated on the label:** none stated (not evidence testing didn't happen)
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*
```
ID: PG-80F98E05CB6B
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 64. Soy Protein Isolate Powder 30 g

**Brand:** BulkSupplements.com
**Servings/day:** 1

**Actives:**
- Vitamin D — 0.0 mcg
- Iron — 2.7 mg (15.0% DV)
- Calcium — 0.0 mg
- Potassium — 190.0 mg (4.0% DV)

**Other ingredients:** Soy Protein Isolate

**Quality claims stated on the label:** none stated (not evidence testing didn't happen)
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*

> **⚠ DATA NOTE** — 2 ingredient(s) show quantity 0 — our extraction gap, treat as undisclosed
```
ID: PG-871F14BFF5B2
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 65. Women's Ultra Mega Without Iron & Iodine

**Brand:** GNC Women's Ultra Mega
**Servings/day:** 1

**Actives:**
- Vitamin A — 5000.0 IU (100.0% DV)
- Vitamin C — 200.0 mg (333.0% DV)
- Vitamin D — 1600.0 IU (400.0% DV)
- Vitamin E — 30.0 IU (100.0% DV)
- Vitamin K (unspecified) — 80.0 mcg (100.0% DV)
- Thiamin — 50.0 mg (3333.0% DV)
- Riboflavin — 50.0 mg (2941.0% DV)
- Niacin — 50.0 mg (250.0% DV)
- Vitamin B6 — 50.0 mg (2500.0% DV)
- Folate — 400.0 mcg (100.0% DV)
- Vitamin B12 — 50.0 mcg (833.0% DV)
- Biotin — 300.0 mcg (100.0% DV)
- Pantothenic Acid — 50.0 mg (500.0% DV)
- Calcium — 500.0 mg (50.0% DV)
- Magnesium — 100.0 mg (25.0% DV)
- Zinc — 15.0 mg (100.0% DV)
- Selenium — 200.0 mcg (286.0% DV)
- Copper — 2.0 mg (100.0% DV)
- Manganese — 2.0 mg (100.0% DV)
- Chromium — 120.0 mcg (100.0% DV)
- Molybdenum — 75.0 mcg (100.0% DV)
- Choline — 10.0 mg
- Inositol — 10.0 mg
- Silicon — 4.0 mg
- Boron — 2.0 mg
- Lycopene — 950.0 mcg
- Lutein — 950.0 mcg
- Zeaxanthin — 190.0 mcg
- Astaxanthin — 50.0 mcg
- Vanadium — 10.0 mcg

**Blend — Superfoods Fruit & Vegetable Blend** (total: amount NOT disclosed)

**Blend — Beauty Blend** (total: amount NOT disclosed)

**Other ingredients:** Cellulose, Titanium Dioxide, Vegetable Acetoglycerides, natural Vanilla flavor, Chlorophyll, Sucralose

**Quality claims stated on the label:** none stated (not evidence testing didn't happen)
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*

> **⚠ DATA NOTE** — **Chromium 120.0 mcg shown as 100.0% DV is internally inconsistent** (~3x off the usual amount for that %DV) — one of the two figures is our extraction error. Judge on whichever you find credible and say which in `WHY:`; **Folate 400.0** is the TOTAL; the entries after it are its constituent forms. Do NOT add them to it
```
ID: PG-1A9AF3262F69
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 66. Elderberry Gummies

**Brand:** Nutricost Kids
**Servings/day:** 1

**Actives:**
- Vitamin C — 45.0 mg (50.0% DV)
- Zinc — 3.8 mg (35.0% DV)
- European Elder — 50.0 mg
- European Elder — 1750.0 mg

**Other ingredients:** Glucose Syrup, Isomalt, Sugar, Glucose, Pectin, Citric Acid, Sodium Citrate, Natural Flavors, Vegetable Oil

**Quality claims stated on the label:** GMP certified/compliant
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*
```
ID: PG-4B2D70E06B73
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 67. Hair, Skin & Nails Gummy Tropical Fruit

**Brand:** GNC Women's
**Servings/day:** 1

**Actives:**
- Vitamin C — 15.0 mg (25.0% DV)
- Vitamin E — 15.0 IU (50.0% DV)
- Biotin — 2500.0 mcg (833.0% DV)

**Other ingredients:** Glucose Syrup, Sucrose, Gelatin, Corn Starch, Modified, Citric Acid, Lactic Acid, natural Fruit Flavor, Other Natural Flavors, Turmeric, Black Carrot Juice Concentrate, Annatto, Coconut Oil, Fractionated, Carnauba Wax, Beeswax

**Quality claims stated on the label:** none stated (not evidence testing didn't happen)
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*
```
ID: PG-6551FC6AB919
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 68. Super Vitamin B-Complex

**Brand:** Spring Valley
**Servings/day:** 1

**Actives:**
- Vitamin C — 150.0 mg (167.0% DV)
- Thiamin — 100.0 mg (8333.0% DV)
- Riboflavin — 20.0 mg (1538.0% DV)
- Niacin — 25.0 mg (156.0% DV)
- Vitamin B6 — 2.0 mg (118.0% DV)
- Folate — 680.0 mcg DFE (170.0% DV)
- Folate — 400.0 mcg
- Vitamin B12 — 15.0 mcg (625.0% DV)
- Biotin — 30.0 mcg (100.0% DV)
- Vitamin B5 — 5.5 mg (110.0% DV)

**Other ingredients:** Calcium Carbonate, Ascorbic Acid, Thiamine Mononitrate, Microcrystaline Cellulose, Sorbitol, Nicotinamide, Starch, Calcium D-Pantothenate, Cyanocobalamin, Hydroxypropyl Methylcellulose, Magnesium Stearate, Polyvinyl Alcohol, Pyridoxine Hydrochloride, Silicon Dioxide

**Quality claims stated on the label:** none stated (not evidence testing didn't happen)
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*
```
ID: PG-F6E646457025
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 69. HMB 1,000 mg Unflavored

**Brand:** Nutricost
**Servings/day:** 1

**Actives:**
- Calcium — 140.0 mg (10.0% DV)
- calcium beta-hydroxy-beta-methylbutyrate monohydrate — 1000.0 mg

**Other ingredients:** none listed

**Quality claims stated on the label:** none stated (not evidence testing didn't happen)
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*
```
ID: PG-17E37AE79E21
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 70. Parsley Extract

**Brand:** BulkSupplements.com
**Servings/day:** 1–2

**Actives:**
- Parsley — 1000.0 mg

**Other ingredients:** none listed

**Quality claims stated on the label:** none stated (not evidence testing didn't happen)
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*
```
ID: PG-649072F3F9EE
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 71. Precision BCAA Tropical Punch

**Brand:** GNC Beyond Raw
**Servings/day:** 1

**Actives:**
- Calcium — 70.0 mg (5.0% DV)
- Magnesium — 50.0 mg (12.0% DV)
- Chromium — 1000.0 mcg (2857.0% DV)
- Potassium — 240.0 mg (5.0% DV)
- Leucine — 5.0 Gram(s)
- Isoleucine — 2.5 Gram(s)
- Valine — 2.5 Gram(s)
- Betaine Anhydrous — 2.5 Gram(s)

**Blend — Micronized BCAA Blend** (total: amount NOT disclosed)
- L-Leucine — 5.0 Gram(s)
- L-Isoleucine — 2.5 Gram(s)
- L-Valine — 2.5 Gram(s)

**Blend — Velositol Amylopectin Chromium Complex** (total: amount NOT disclosed)

**Blend — Power & Performance Blend:** (total: amount NOT disclosed)

**Blend — Power & Performance Blend:** (total: amount NOT disclosed)
- BetaPower Betaine Anhydrous — 2.5 Gram(s)
- Levagen — 150.0 mg

**Other ingredients:** Natural and Artificial flavors, Citric Acid, Malic Acid, Sucralose, Acesulfame Potassium, Calcium Carbonate, Calcium Silicate, Sunflower Lecithin, FD&C Red #40, Polyglycerol Polyricinoleate, fractionated Coconut Oil, Citrus Oil, Olive Oil, Mono and Diglycerides, Oat Oil

**Quality claims stated on the label:** none stated (not evidence testing didn't happen)
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*

> **⚠ DATA NOTE** — **Leucine 5.0** is the TOTAL; the entries after it are its constituent forms. Do NOT add them to it
```
ID: PG-5540B9BE5D5A
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 72. Creatine Monohydrate 5000 Unflavored

**Brand:** GNC Pro Performance
**Servings/day:** 1

**Actives:**
- Creatine — 5000.0 mg

**Other ingredients:** none listed

**Quality claims stated on the label:** none stated (not evidence testing didn't happen)
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*
```
ID: PG-FEAE0BAEC6CC
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 73. RapidDrive Pre-Workout Amino Complex Fruit Punch

**Brand:** GNC Pro Performance
**Servings/day:** 1

**Actives:**
- Beta-Alanine — 3200.0 mg
- Leucine — 3000.0 mg
- Isoleucine — 1000.0 mg
- Valine — 1000.0 mg
- Arginine — 1000.0 mg
- Taurine — 1000.0 mg
- L-Carnitine — 500.0 mg
- AKG — 100.0 mg
- Citrulline — 50.0 mg

**Other ingredients:** Natural and Artificial flavors, Citric Acid, Malic Acid, Lecithin, Sucralose, FD&C Red #40

**Quality claims stated on the label:** none stated (not evidence testing didn't happen)
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*

> **⚠ DATA NOTE** — **Leucine 3000.0** is the TOTAL; the entries after it are its constituent forms. Do NOT add them to it
```
ID: PG-97871A89AC38
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 74. B-Complex Orange

**Brand:** GNC
**Servings/day:** 1

**Actives:**
- Riboflavin — 1.7 mg (131.0% DV)
- Niacin — 20.0 mg (125.0% DV)
- Vitamin B6 — 2.0 mg (118.0% DV)
- Vitamin B12 — 1000.0 mcg (41667.0% DV)
- Vitamin B5 — 30.0 mg (600.0% DV)

**Other ingredients:** purified Water, Glycerin, Citric Acid, Sodium Acid Sulfate, Natural flavors, Sucralose, Gum Blend, Potassium Sorbate, Sodium Hexametaphosphate, Sodium Benzoate, Acesulfame Potassium

**Quality claims stated on the label:** none stated (not evidence testing didn't happen)
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*
```
ID: PG-EA24F8F85E58
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 75. Amplified N.O. Loaded V2 Blue Raspberry

**Brand:** GNC Pro Performance AMP
**Servings/day:** 1

**Actives:**
- Vitamin D — 2000.0 IU (500.0% DV)
- Niacin — 40.0 mg (200.0% DV)
- Betaine — 5.0 Gram(s)
- Beta-Alanine — 3.6 Gram(s)
- Creatine — 2.5 Gram(s)
- Creatine — 1.5 Gram(s)
- Glycocyamine — 70.0 mg
- Alpha-Ketoglutarate — 20.0 mg
- METHIONINE — 10.0 mg
- Arginine — 1.62 Gram(s)
- Citrulline — 450.0 mg
- Arginine AKG — 200.0 mg
- Arginine — 180.0 mg
- Resveratrol — 60.0 mg
- Yohimbe — 50.0 mg
- Rhodiola — 40.0 mg
- Caffeine — 300.0 mg
- L-Carnitine — 100.0 mg

**Blend — Power and Performance Matrix** (total: amount NOT disclosed)

**Blend — N.O. Accelerator Blend** (total: amount NOT disclosed)

**Blend — Energizing Fatty Acid Metabolizer Blend** (total: amount NOT disclosed)
- Caffeine Anhydrous — 300.0 mg
- Carnitine — 100.0 mg

**Blend — Power and Performance Matrix** (total: amount NOT disclosed)
- Betaine — 5.0 Gram(s)
- CarnoSyn — 3.6 Gram(s)
- Creatine HCl — 2.5 Gram(s)
- micronized Creatine Monohydrate — 1.5 Gram(s)
- Guanidinoacetate — 70.0 mg
- Alpha-Ketoglutarate — 20.0 mg
- L-Methionine — 10.0 mg

**Blend — N.O. Accelerator Blend** (total: amount NOT disclosed)
- L-Arginine — 1.62 Gram(s)
- L-Citrulline — 450.0 mg
- Arginine AKG — 200.0 mg
- L-Arginine, Micronized — 180.0 mg
- resVida Trans-Resveratrol — 60.0 mg
- Yohimbe bark powder — 50.0 mg
- Rhodiola rosea extract — 40.0 mg

**Other ingredients:** Natural and Artificial flavors, Citric Acid, Malic Acid, Lecithin, Calcium Silicate, Silicon Dioxide, Sucralose, Tartaric Acid, Acesulfame Potassium, FD&C Blue #2, FD&C Blue #1

**Quality claims stated on the label:** purity verified, Informed Choice
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*
```
ID: PG-3F3DF54E40BD
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 76. Amplified Creatine XXX Fruit Punch

**Brand:** GNC Pro Performance AMP
**Servings/day:** 1

**Actives:**
- Calcium — 48.0 mg (5.0% DV)
- Resveratrol — 30.0 mg

**Blend — Proprietary Amino Acid Complex** (total: amount NOT disclosed)
- L-Glutamine — amount NOT disclosed
- L-Histidine — amount NOT disclosed
- L-Isoleucine — amount NOT disclosed
- L-Leucine — amount NOT disclosed
- L-Lysine — amount NOT disclosed
- L-Methionine — amount NOT disclosed
- L-Phenylalanine — amount NOT disclosed
- L-Threonine — amount NOT disclosed
- L-Valine — amount NOT disclosed

**Blend — Micronized Creatine Matrix Blend** (total: amount NOT disclosed)
- Glycine, Micronized — amount NOT disclosed
- L-Arginine, Micronized — amount NOT disclosed
- L-Methionine, Micronized — amount NOT disclosed
- micronized Alpha-Ketoglutarate — amount NOT disclosed
- micronized Creatine Monohydrate — amount NOT disclosed
- micronized Guanidinoacetate — amount NOT disclosed

**Other ingredients:** Dextrose, Natural and Artificial flavors, Citric Acid, Silicon Dioxide, Calcium Silicate, Lecithin, Malic Acid, Sucralose, FD&C Red #40

**Quality claims stated on the label:** purity verified, Informed Choice
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*
```
ID: PG-E5DF516B31C7
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 77. Creatine Monohydrate 700 mg

**Brand:** BulkSupplements.com
**Servings/day:** 1

**Actives:**
- Creatine — 2800.0 mg

**Other ingredients:** Hypromellose Capsules

**Quality claims stated on the label:** none stated (not evidence testing didn't happen)
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*
```
ID: PG-A00BA302A81F
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 78. Sambucus Cough Relief + Immune Gummy

**Brand:** Nature's Way
**Servings/day:** 2–3

**Actives:**
- Vitamin C — 45.0 mg (50.0% DV)
- Zinc — 3.75 mg (34.0% DV)
- elderberry — 50.0 mg
- Elderberry (unspecified) — 3200.0 mg

**Other ingredients:** Cane Sugar, Tapioca Syrup, Water, Purified, Pectin, Natural Flavors, Citric Acid, Sodium Citrate, Beeswax

**Quality claims stated on the label:** none stated (not evidence testing didn't happen)
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*
```
ID: PG-DDA0598EE29F
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 79. B Complex Natural Strawberry Flavor

**Brand:** vitafusion
**Servings/day:** 1

**Actives:**
- Vitamin C — 15.0 mg (25.0% DV)
- Niacin — 20.0 mg (100.0% DV)
- Vitamin B6 — 2.0 mg (100.0% DV)
- Folate — 400.0 mcg (100.0% DV)
- Vitamin B12 — 30.0 mcg (500.0% DV)
- Biotin — 75.0 mcg (25.0% DV)
- Vitamin B5 — 10.0 mg (100.0% DV)
- Inositol — 7.0 mg

**Other ingredients:** Glucose Syrup, Sucrose, Water, Gelatin, Citric Acid, Coconut Oil, Color, Lactic Acid, Natural flavor

**Quality claims stated on the label:** none stated (not evidence testing didn't happen)
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*
```
ID: PG-A8E93FC94DA4
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 80. Probiotic Complex with Fiber Unflavored

**Brand:** GNC Probiotic
**Servings/day:** 2

**Actives:**
- BiMuno B-Gos Galactooligosaccharides — 1.37 Gram(s)

**Blend — LAB4 Probiotics** (total: amount NOT disclosed)
- Bifidobacterium animalis subsp. lactis (CUL 34) — amount NOT disclosed
- Bifidobacterium bifidum (CUL 20) — amount NOT disclosed
- Lactobacillus acidophilus (CUL 21) — amount NOT disclosed
- Lactobacillus acidophilus (CUL 60) — amount NOT disclosed

**Other ingredients:** Sunfiber, Potato Maltodextrin

**Quality claims stated on the label:** none stated (not evidence testing didn't happen)
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*
```
ID: PG-54FEC5F192F8
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 81. Creatine Advance XR Unflavored

**Brand:** GNC Pro Performance
**Servings/day:** 1

**Actives:**
- Creatine Blend — 5.0 Gram(s)
- Creatine Precursors — 100.0 mg

**Blend — Creatine Blend** (total: amount NOT disclosed)
- Creatine AKG — amount NOT disclosed
- Creatine Ethyl Ester HCl — amount NOT disclosed
- OT2 Creatine — amount NOT disclosed
- micronized Creatine Monohydrate — amount NOT disclosed

**Blend — Creatine Precursors** (total: amount NOT disclosed)
- Alpha-Ketoglutarate — amount NOT disclosed
- Guanidinoacetate — amount NOT disclosed
- L-Arginine — amount NOT disclosed
- L-Methionine — amount NOT disclosed

**Other ingredients:** Natural flavor, Hydrogenated Vegetable Oil, Monoglycerides

**Quality claims stated on the label:** purity verified, Informed Choice
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*
```
ID: PG-671E47AADA59
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 82. EPA/DHA Vegetarian

**Brand:** Pure Encapsulations
**Servings/day:** 1

**Actives:**
- EPA — 155.0 mg
- DHA — 310.0 mg

**Other ingredients:** Algal Oil, Vegetarian Caplique Capsule, high Oleic Sunflower Oil, Sunflower Lecithin, Rosemary leaf extract, Mixed Tocopherols, Ascorbyl Palmitate, Silica

**Quality claims stated on the label:** none stated (not evidence testing didn't happen)
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*
```
ID: PG-E8D907057C8C
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 83. Asian Ginseng

**Brand:** Nature's Way
**Servings/day:** 2

**Actives:**
- Asian Ginseng root extract — 550.0 mg

**Other ingredients:** plant-derived Capsule, Magnesium Stearate

**Quality claims stated on the label:** none stated (not evidence testing didn't happen)
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*
```
ID: PG-AFE7623B1434
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 84. Basic Prenatal

**Brand:** Thorne
**Servings/day:** 1

**Actives:**
- Vitamin A — 1.05 mg (81.0% DV)
- beta-carotene — 450.0 mcg
- Vitamin A — 600.0 mcg
- Vitamin C — 150.0 mg (125.0% DV)
- Vitamin D — 25.0 mcg (167.0% DV)
- Vitamin E — 33.5 mg (176.0% DV)
- Vitamin K — 100.0 mcg (111.0% DV)
- Thiamin — 5.0 mg (357.0% DV)
- Riboflavin — 5.0 mg (313.0% DV)
- Niacin — 30.0 mg (167.0% DV)
- Vitamin B6 — 12.0 mg (600.0% DV)
- Folate — 1.7 mg DFE (283.0% DV)
- Vitamin B9 (methyltetrahydrofolate) — 1.0 mg
- Vitamin B12 — 200.0 mcg (7142.0% DV)
- Biotin — 50.0 mcg (143.0% DV)
- Pantothenic Acid — 18.0 mg (257.0% DV)
- Choline — 110.0 mg (20.0% DV)
- Calcium — 180.0 mg (14.0% DV)
- Calcium — 90.0 mg
- Calcium — 90.0 mg
- Iron — 45.0 mg (167.0% DV)
- Iodine — 150.0 mcg (52.0% DV)
- Magnesium — 90.0 mg (23.0% DV)
- Magnesium — 45.0 mg
- Magnesium — 45.0 mg
- Zinc — 25.0 mg (192.0% DV)
- Selenium — 50.0 mcg (71.0% DV)
- Copper — 2.0 mg (154.0% DV)
- Manganese — 5.0 mg (192.0% DV)
- Chromium — 100.0 mcg (222.0% DV)
- Boron — 1.0 mg

**Other ingredients:** Hypromellose, Calcium Laurate

**Quality claims stated on the label:** heavy-metal tested, purity verified, label accuracy verified, NSF Contents Certified
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*

> **⚠ DATA NOTE** — **Calcium 180.0** is the TOTAL; the entries after it are its constituent forms. Do NOT add them to it
```
ID: PG-3A5D688494B3
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 85. Omega-3 Lemon

**Brand:** Nordic Naturals
**Servings/day:** 1

**Actives:**
- EPA — 330.0 mg
- DHA — 220.0 mg

**Other ingredients:** purified deep sea Fish Oil, Gelatin, Glycerin, Water, natural Lemon flavor, natural Lemon flavor, D-Alpha-Tocopherol, Rosemary Extract

**Quality claims stated on the label:** Friend of the Sea
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*
```
ID: PG-09BD646BF268
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 86. B-Complex Plus

**Brand:** Pure Encapsulations
**Servings/day:** 1–2

**Actives:**
- Thiamin — 100.0 mg (8333.0% DV)
- Riboflavin — 12.7 mg (977.0% DV)
- Niacin — 108.0 mg (675.0% DV)
- Vitamin B6 — 16.7 mg (982.0% DV)
- Folate — 667.0 mcg DFE (167.0% DV)
- Vitamin B9 — 400.0 mcg
- Vitamin B12 — 400.0 mcg (16667.0% DV)
- Biotin — 400.0 mcg (1333.0% DV)
- Pantothenic Acid — 100.0 mg (2000.0% DV)

**Other ingredients:** Cellulose, Water, Ascorbyl Palmitate

**Quality claims stated on the label:** none stated (not evidence testing didn't happen)
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*
```
ID: PG-5480DE1C70F8
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 87. Fortify Adult Probiotic 50 Billion Extra-Strength

**Brand:** Nature's Way
**Servings/day:** 1

**Actives:**
- Proprietary Blend (non-nutrient/non-botanical) — 525.0 mg

**Blend — Fortify Daily Proprietary Probiotic Blend** (total: amount NOT disclosed)
- Bifidobacteria Blend — amount NOT disclosed
- Lactobacilli Blend — amount NOT disclosed

**Blend — Lactobacilli Blend** (total: amount NOT disclosed)
- HOWARU — amount NOT disclosed
- L. acidophilus LA-14 — amount NOT disclosed
- L. paracasei LPC-37 — amount NOT disclosed
- L. plantarum LP-115 — amount NOT disclosed
- L. rhamnosus GG — amount NOT disclosed
- Lacticaseibacillus casei Lc-11 — amount NOT disclosed

**Blend — Bifidobacteria Blend** (total: amount NOT disclosed)
- B. animalis lactis BI-07 — amount NOT disclosed
- B. animalis lactis BL-04 — amount NOT disclosed
- Bifidobacterium — amount NOT disclosed

**Blend — Bifidobacteria Blend** (total: amount NOT disclosed)
- HOWARU — amount NOT disclosed

**Other ingredients:** Cellulose, Hypromellose, Gellan Gum, Magnesium Stearate, Silica

**Quality claims stated on the label:** none stated (not evidence testing didn't happen)
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*
```
ID: PG-77190ED8D127
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 88. Vitamin E Softgels 303 mg

**Brand:** BulkSupplements.com
**Servings/day:** 1

**Actives:**
- Vitamin E — 303.0 mg (2020.0% DV)

**Other ingredients:** Soy Oil, Bovine Gelatin, Water, Purified

**Quality claims stated on the label:** none stated (not evidence testing didn't happen)
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*
```
ID: PG-C010A4CFEDFF
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 89. Life Extenstion Mix Powder Without Copper

**Brand:** Life Extension
**Servings/day:** 0.25

**Actives:**
- Vitamin A — 5000.0 IU (100.0% DV)
- Vitamin C — 2000.0 mg (3333.0% DV)
- Vitamin D — 2000.0 IU (500.0% DV)
- Vitamin E — 100.0 IU (333.0% DV)
- Thiamin — 125.0 mg (8333.0% DV)
- Vitamin B2 — 50.0 mg (2941.0% DV)
- Niacin — 190.0 mg (950.0% DV)
- Vitamin B6 — 105.0 mg (5250.0% DV)
- Vitamin B6 — 100.0 mg
- Vitamin B6 — 5.0 mg
- Vitamin B9 — 400.0 mcg (100.0% DV)
- Vitamin B12 — 600.0 mcg (10000.0% DV)
- Biotin — 3000.0 mcg (1000.0% DV)
- Pantothenic Acid — 600.0 mg (6000.0% DV)
- Pantethine — 5.0 mg
- Calcium — 460.0 mg (46.0% DV)
- Iodine — 150.0 mcg (100.0% DV)
- Magnesium — 400.0 mg (100.0% DV)
- Zinc — 35.0 mg (233.0% DV)
- Selenium — 200.0 mcg (286.0% DV)
- Manganese — 1.0 mg (50.0% DV)
- Chromium — 500.0 mcg (417.0% DV)
- Molybdenum — 125.0 mcg (167.0% DV)
- Potassium — 35.0 mg (1.0% DV)
- N-Acetyl Cysteine — 600.0 mg
- Taurine — 200.0 mg
- Inositol — 250.0 mg
- phosphatidylcholine — 150.0 mg
- Choline — 120.0 mg
- Boron — 3.0 mg
- Betaine — 100.0 mg
- Bitter Orange Citrus Bioflavonoids — 200.0 mg
- Blueberry — 0.0 unit not stated
- Blueberry — 150.0 mg
- Silymarin — 100.0 mg
- Pomegranate — 85.0 mg
- Vitamin E — 60.0 mg
- bilberry — 30.0 mg
- Leucoselect Grape seed Proanthocyanidin extract — 25.0 mg
- Grape — 25.0 mg
- Bromelain — 15.0 mg
- Delphinidin — 2.0 mg
- Lutein — 15.0 mg
- Zeaxanthin — 465.0 mcg
- Sesame Seed Lignan Extract — 10.0 mg
- Luteolin — 8.0 mg
- Lycopene — 3.0 mg
- C3G — 1.25 mg
- Pterostilbene — 0.5 mg
- Apigenin — 5.0 mg

**Blend — Fruit/Berry Proprietary Blend** (total: amount NOT disclosed)
- Blackberry powder — amount NOT disclosed
- Blueberry powder — amount NOT disclosed
- Cranberry powder — amount NOT disclosed
- European Elder powder — amount NOT disclosed
- Persimmon, Powder — amount NOT disclosed
- Plum powder — amount NOT disclosed
- Sweet Cherry powder — amount NOT disclosed

**Other ingredients:** Maltodextrin, Stevia extract, Medium Chain Triglycerides, natural Orange flavor, Silica

**Quality claims stated on the label:** none stated (not evidence testing didn't happen)
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*

> **⚠ DATA NOTE** — servings-per-day below 1 is our defect — assume **1 serving/day**; **Chromium 500.0 mcg shown as 417.0% DV is internally inconsistent** (~3x off the usual amount for that %DV) — one of the two figures is our extraction error. Judge on whichever you find credible and say which in `WHY:`; 1 ingredient(s) show quantity 0 — our extraction gap, treat as undisclosed; 1 ingredient(s) have no unit — our extraction gap, treat as undisclosed; **Vitamin B6 105.0** is the TOTAL; the entries after it are its constituent forms. Do NOT add them to it
```
ID: PG-C7A77BE2D674
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 90. BCAA 6 g Pink Drink

**Brand:** Nutricost Women
**Servings/day:** 1

**Actives:**
- Calcium — 200.0 mg (15.0% DV)
- Phosphorus — 185.0 mg (15.0% DV)
- Potassium — 145.0 mg (4.0% DV)
- Magnesium — 41.0 mg (10.0% DV)
- Vitamin D — 25.0 mcg (130.0% DV)
- Folate — 400.0 mcg DFE (100.0% DV)
- Biotin — 300.0 mcg (1000.0% DV)
- Leucine — 3000.0 mg
- Isoleucine — 1500.0 mg
- Valine — 1500.0 mg
- Coconut — 4300.0 mg
- Coconut — 1290.0 mg
- Hyaluronic Acid — 100.0 mg
- Dog Rose — 50.0 mg
- cranberry — 400.0 mcg

**Other ingredients:** Natural & Artificial Flavors, Malic Acid, Citric Acid, Sucralose, Silicon Dioxide, Mica Based Pearlescent, Dextrose, Red 3, Red 40 Lake, Blue 1, Blue 2 Lake, Yellow 6, Acesulfame Potassium, Beet, Powder

**Quality claims stated on the label:** GMP certified/compliant
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*

> **⚠ DATA NOTE** — **Leucine 3000.0** is the TOTAL; the entries after it are its constituent forms. Do NOT add them to it
```
ID: PG-C1FCD92C77F4
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 91. Daily Omega Natural Fruit Flavor

**Brand:** Nordic Naturals
**Servings/day:** 1

**Actives:**
- Vitamin D — 500.0 IU (125.0% DV)
- EPA — 325.0 mg
- DHA — 225.0 mg

**Other ingredients:** purified deep sea Fish Oil, Softgel Capsule, natural Lemon flavor, D-Alpha-Tocopherol, Rosemary extract

**Quality claims stated on the label:** Friend of the Sea
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*
```
ID: PG-63E1BA8D0D21
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 92. Beanaid

**Brand:** CVS Pharmacy
**Servings/day:** 1

**Actives:**
- Alpha Galactosidase — 0.0 unit not stated

**Other ingredients:** 100% Gelatin capsule

**Quality claims stated on the label:** none stated (not evidence testing didn't happen)
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*

> **⚠ DATA NOTE** — 1 ingredient(s) show quantity 0 — our extraction gap, treat as undisclosed; 1 ingredient(s) have no unit — our extraction gap, treat as undisclosed
```
ID: PG-FB127D88AB6B
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 93. Wheybolic Alpha Strawberries and Cream

**Brand:** GNC AMP Advanced Muscle Performance
**Servings/day:** 1–2

**Actives:**
- Calcium — 90.0 mg (7.0% DV)
- Chromium — 125.0 mcg (357.0% DV)
- Potassium — 110.0 mg (2.0% DV)
- Leucine — 3.1 Gram(s)
- Creatine — 0.75 Gram(s)
- Betaine Anhydrous — 0.625 Gram(s)
- Fenugreek — 150.0 mg

**Blend — MyoTOR (Sphaeranthus-Mango Blend)** (total: amount NOT disclosed)

**Blend — Velositol Amylopectin Chromium Complex** (total: amount NOT disclosed)

**Blend — Digestive Enzyme Blends** (total: amount NOT disclosed)

**Blend — General Proprietary Blends** (total: amount NOT disclosed)

**Other ingredients:** Protein Blend, Natural & Artificial flavor, Sunflower Creamer, Red Beet powder, Salt, Citric Acid, Gum Blend, Sunflower Lecithin, Sucralose, Acesulfame Potassium, Silicon Dioxide

**Quality claims stated on the label:** purity verified, Informed Choice
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*
```
ID: PG-3C76D567E9D1
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 94. GS-750 Glucosamine Sulfate Extra Strength

**Brand:** Nature's Way
**Servings/day:** 1

**Actives:**
- Glucosamine Sulfate — 1.5 Gram(s)

**Other ingredients:** Cellulose, Hypromellose, Magnesium Stearate, Glycerin

**Quality claims stated on the label:** none stated (not evidence testing didn't happen)
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*
```
ID: PG-038D6F74A37E
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 95. BCAA 2:1:1

**Brand:** BulkSupplements.com
**Servings/day:** 1

**Actives:**
- Leucine — 3000.0 mg
- Isoleucine — 1500.0 mg
- Valine — 1500.0 mg

**Other ingredients:** Sunflower Lecithin

**Quality claims stated on the label:** none stated (not evidence testing didn't happen)
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*

> **⚠ DATA NOTE** — **Leucine 3000.0** is the TOTAL; the entries after it are its constituent forms. Do NOT add them to it
```
ID: PG-446B854BA2E7
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 96. Amplified Wheybolic Extreme 60 Strawberry

**Brand:** GNC Pro Performance AMP
**Servings/day:** 1–2

**Actives:**
- Calcium — 260.0 mg (26.0% DV)
- Potassium — 350.0 mg (10.0% DV)
- Leucine — 3.3 Gram(s)
- L-Carnitine — 500.0 mg

**Blend — MicroSorb(TM) Amino Acid Complex** (total: amount NOT disclosed)
- Arginine — amount NOT disclosed
- Glutamine — amount NOT disclosed

**Blend — Digestive Enzyme Blends** (total: amount NOT disclosed)

**Blend — Amino Acceleration System** (total: amount NOT disclosed)
- Aminogen — amount NOT disclosed
- Carbogen — amount NOT disclosed
- Enzyme Matrix Blend — amount NOT disclosed

**Blend — Enzyme Matrix Blend** (total: amount NOT disclosed)
- Alpha-Galactosidase — amount NOT disclosed
- Amylase — amount NOT disclosed
- Bromelain — amount NOT disclosed
- CereCalase — amount NOT disclosed
- Glucoamylase — amount NOT disclosed
- Invertase — amount NOT disclosed
- Lactase — amount NOT disclosed
- Lipase — amount NOT disclosed
- Peptidase — amount NOT disclosed
- Protease — amount NOT disclosed
- Protease 3 — amount NOT disclosed
- Protease 4.5 — amount NOT disclosed
- Protease 6 — amount NOT disclosed

**Other ingredients:** Protein Blend, Natural and Artificial flavors, Polydextrose, Lecithin, Citric Acid, Malic Acid, Sucralose, FD&C Red #40, Acesulfame Potassium

**Quality claims stated on the label:** none stated (not evidence testing didn't happen)
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*
```
ID: PG-4037B4FC778B
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 97. Daily DHA Natural Fruit Flavor

**Brand:** Nordic Naturals
**Servings/day:** 1

**Actives:**
- Fish Oil — 0.0 unit not stated
- EPA — 205.0 mg
- DHA — 480.0 mg

**Other ingredients:** purified deep sea Fish Oil, Soft Gel Capsule, natural Strawberry flavor, D-Alpha-Tocopherol, Rosemary extract

**Quality claims stated on the label:** Friend of the Sea
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*

> **⚠ DATA NOTE** — 1 ingredient(s) show quantity 0 — our extraction gap, treat as undisclosed; 1 ingredient(s) have no unit — our extraction gap, treat as undisclosed
```
ID: PG-1C15B3200B41
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 98. PureLean Whey Natural Vanilla Bean Flavor

**Brand:** Pure Encapsulations
**Servings/day:** 1

**Actives:**
- Protein — 21.0 Gram(s) (42.0% DV)

**Other ingredients:** Whey Protein Isolate, Sunflower Lecithin, Vanilla Bean Flavor, Natural, Stevia Leaf Extract

**Quality claims stated on the label:** none stated (not evidence testing didn't happen)
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*
```
ID: PG-592B4A4760BB
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 99. Myrrh Extract 650 mg

**Brand:** Nutricost
**Servings/day:** 1

**Actives:**
- Myrrh — 650.0 mg

**Other ingredients:** Hypromellose, Rice Flour, Stearic Acid

**Quality claims stated on the label:** none stated (not evidence testing didn't happen)
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*
```
ID: PG-477EA41A3F43
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 100. KSM-66

**Brand:** Transparent Labs
**Servings/day:** 1

**Actives:**
- Ashwagandha — 600.0 mg

**Other ingredients:** Rice Flour, Hypromellose, Magnesium Stearate

**Quality claims stated on the label:** none stated (not evidence testing didn't happen)
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*
```
ID: PG-7404D0F2E692
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 101. Whey Protein Concentrate 25 g Vanilla

**Brand:** Nutricost
**Servings/day:** 1

**Actives:**
- Vitamin D — 0.0 mcg
- Calcium — 170.0 mg (15.0% DV)
- Iron — 0.0 mg
- Potassium — 130.0 mg (4.0% DV)
- Phosphorus — 134.0 mg (10.0% DV)
- Magnesium — 20.0 mg (4.0% DV)

**Other ingredients:** Whey Protein Concentrate, Sunflower Lecithin, Natural Flavors, Sodium Chloride, Sucralose

**Quality claims stated on the label:** GMP certified/compliant
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*

> **⚠ DATA NOTE** — 2 ingredient(s) show quantity 0 — our extraction gap, treat as undisclosed
```
ID: PG-4E6E70CADB83
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 102. Whey Protein Concentrate Powder 30 g

**Brand:** BulkSupplements.com
**Servings/day:** 1

**Actives:**
- Vitamin D — 0.0 mcg
- Calcium — 162.0 mg (10.0% DV)
- Iron — 0.0 mg
- Potassium — 126.0 mg (2.0% DV)

**Other ingredients:** Whey Protein Concentrate, Sunflower Lecithin

**Quality claims stated on the label:** none stated (not evidence testing didn't happen)
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*

> **⚠ DATA NOTE** — 2 ingredient(s) show quantity 0 — our extraction gap, treat as undisclosed
```
ID: PG-3D73F9CEC0A9
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 103. Fortify Daily Prebiotic Fiber Raspberry Lemonade Flavored

**Brand:** Nature's Way
**Servings/day:** 0.414

**Actives:**
- Guar — 3.2 Gram(s)
- Chicory fiber — 120.0 mg

**Other ingredients:** Sorbitol, Natural Flavors, Beet Juice, Citric Acid, Mannitol, Stevia leaf extract, Silica

**Quality claims stated on the label:** none stated (not evidence testing didn't happen)
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*

> **⚠ DATA NOTE** — servings-per-day below 1 is our defect — assume **1 serving/day**
```
ID: PG-CF4E0B6A83AC
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 104. Clear Mixing Super Fiber With Probiotics

**Brand:** GNC Natural Brand
**Servings/day:** 1

**Actives:**
- LAB4 — 1000000000.0 Viable Cells

**Blend — LAB4** (total: amount NOT disclosed)
- Bifidobacterium bifidum (CUL 20) — amount NOT disclosed
- Bifidobacterium lactis — amount NOT disclosed
- Lactobacillus acidophilus (CUL 60) — amount NOT disclosed
- Lactobacillus acidophilus (CUL-21) — amount NOT disclosed

**Other ingredients:** Sunfiber(R) partially hydrolyzed Guar Gum

**Quality claims stated on the label:** none stated (not evidence testing didn't happen)
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*
```
ID: PG-B3E2E9683FF9
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 105. Quercetin Immune+

**Brand:** Garden of Life Dr. Formulated
**Servings/day:** 1

**Actives:**
- Vitamin C — 90.0 mg (100.0% DV)
- Zinc — 90.0 mg (100.0% DV)
- Quercetin — 570.0 mg
- Quercetin — 500.0 mg
- Bacillus Subtilis — 5.0 mg

**Blend — Vitamin C** (total: amount NOT disclosed)
- Acerola Cherry extract — amount NOT disclosed
- Rose Hips fruit extract — amount NOT disclosed

**Other ingredients:** organic Tapioca Dextrose, organic Gum Arabic, organic Maltodextrin, organic Sunflower Lecithin, organic Palm Oil, organic Rice hulls

**Quality claims stated on the label:** none stated (not evidence testing didn't happen)
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*

> **⚠ DATA NOTE** — **Zinc 90.0 mg shown as 100.0% DV is internally inconsistent** (~8x off the usual amount for that %DV) — one of the two figures is our extraction error. Judge on whichever you find credible and say which in `WHY:`
```
ID: PG-4F2B50E00EED
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 106. EFA Essentials

**Brand:** Pure Encapsulations
**Servings/day:** 1–2

**Actives:**
- Fish Oil — 1914.0 mg
- EPA — 570.0 mg
- DHA — 430.0 mg
- Borage Oil — 300.0 mg
- Gamma Linolenic Acid — 50.0 mg

**Other ingredients:** Gelatin, Glycerin, Water, natural Lemon flavor, Rosemary leaf extract, natural Tocopherols, Ascorbyl Palmitate

**Quality claims stated on the label:** none stated (not evidence testing didn't happen)
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*
```
ID: PG-F1B9DE5F15FF
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 107. PRE Pre-Workout Complex Watermelon

**Brand:** Nutricost Performance
**Servings/day:** 1

**Actives:**
- Thiamin — 50.0 mg (4170.0% DV)
- Niacin — 25.0 mg NE (160.0% DV)
- Vitamin B6 — 60.0 mg (3530.0% DV)
- Vitamin B12 — 200.0 mcg (8330.0% DV)
- Citrulline — 6000.0 mg
- Beta-Alanine — 3000.0 mg
- Taurine — 2000.0 mg
- Agmatine — 500.0 mg
- Tyrosine — 500.0 mg
- Theanine — 300.0 mg
- Caffeine — 300.0 mg
- Theobromine — 200.0 mg
- Huperzine — 200.0 mcg

**Other ingredients:** Natural Flavors, Tartaric Acid, Calcium Silicate, Silica, Sucralose, Citric Acid, Beet, Powder

**Quality claims stated on the label:** GMP certified/compliant
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*

> **⚠ DATA NOTE** — **Beta-Alanine 3000.0** is the TOTAL; the entries after it are its constituent forms. Do NOT add them to it
```
ID: PG-4E969AFCA1B4
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 108. Daily Energy B Complex

**Brand:** Nature's Way Fatigued to Fantastic!
**Servings/day:** 1

**Actives:**
- Thiamin — 75.0 mg (6250.0% DV)
- Riboflavin — 75.0 mg (5769.0% DV)
- Niacin — 50.0 mg (313.0% DV)
- Vitamin B6 — 50.0 mg (2941.0% DV)
- Folate — 800.0 mcg DFE (200.0% DV)
- Folate — 480.0 mcg
- Vitamin B12 — 500.0 mcg (20833.0% DV)
- Pantothenic Acid — 50.0 mg (1000.0% DV)
- Choline — 40.0 mg (7.0% DV)

**Other ingredients:** plant-derived Capsule, Potassium Bicarbonate, Sodium Croscarmellose, Cellulose, Magnesium Stearate

**Quality claims stated on the label:** none stated (not evidence testing didn't happen)
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*
```
ID: PG-513F7290EA3D
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 109. 5 Day Elderberry Immune Berry Flavor

**Brand:** Life Extension
**Servings/day:** 8

**Actives:**
- Vitamin C — 125.0 mg (139.0% DV)
- Zinc — 10.0 mg (91.0% DV)
- elderberry — 90.0 mg

**Other ingredients:** Sorbitol, Xylitol, Stearic Acid, Strawberry flavor, Silica, Citric Acid, Taste Modifier, Stevia Extract, Maltodextrin

**Quality claims stated on the label:** none stated (not evidence testing didn't happen)
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*

> **⚠ DATA NOTE** — servings-per-day of 8 looks implausible and may be our extraction defect — sanity-check against the labeled directions
```
ID: PG-3B4535CCF789
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 110. Curcumin Phytosome 1000 mg

**Brand:** Thorne
**Servings/day:** 2

**Actives:**
- Curcumin — 1.0 Gram(s)

**Other ingredients:** Hypromellose, Leucine, Calcium Laurate, Silicon Dioxide, Calcium Citrate, Microcrystalline Cellulose

**Quality claims stated on the label:** heavy-metal tested, purity verified, label accuracy verified, NSF Contents Certified
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*
```
ID: PG-7D12FCA504AD
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 111. Re-Grow Vanilla Cream

**Brand:** GNC Beyond Raw
**Servings/day:** 1–2

**Actives:**
- Vitamin D — 1000.0 IU (250.0% DV)
- Calcium — 1000.0 mg (100.0% DV)
- Potassium — 700.0 mg (20.0% DV)
- Leucine — 12.0 Gram(s)
- Isoleucine — 6.0 Gram(s)
- Valine — 6.0 Gram(s)
- D-Aspartic Acid — 500.0 mg
- Sweet Orange — 100.0 mg
- Lutein — 5.0 mg
- Zeaxanthin — 1.0 mg
- Glutamine — 10.0 Gram(s)
- Tyrosine — 1.0 Gram(s)
- Tryptophan — 500.0 mg

**Blend — Fast-Acting Proprietary Blend (Herb/Botanical)** (total: amount NOT disclosed)
- Chinese Skullcap root extract — amount NOT disclosed
- Cutch Tree bark extract — amount NOT disclosed

**Blend — Hardcore Muscle Feeder** (total: amount NOT disclosed)

**Blend — Maximum Muscle Recovery Optimizer** (total: amount NOT disclosed)

**Blend — Nutrient Delivery Maximizer** (total: amount NOT disclosed)

**Other ingredients:** Protein Blend, Natural and Artificial flavors, Creamer, Cellulose Gum, Polyethylene Glycol, Lecithin, Titanium Dioxide, Sucralose, Acesulfame Potassium

**Quality claims stated on the label:** none stated (not evidence testing didn't happen)
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*

> **⚠ DATA NOTE** — **Leucine 12.0** is the TOTAL; the entries after it are its constituent forms. Do NOT add them to it
```
ID: PG-2BD9B19A0579
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 112. Daily Probiotics

**Brand:** Sports Research
**Servings/day:** 1

**Actives:**
- Daily Probiotic Blend — 285.0 mg
- Fiber Inulin Blend — 60.0 mg

**Blend — Daily Probiotic Blend** (total: amount NOT disclosed)
- Bifidobacterium animalis lactis — amount NOT disclosed
- Bifidobacterium bifidum — amount NOT disclosed
- Bifidobacterium breve — amount NOT disclosed
- Bifidobacterium longum infantis — amount NOT disclosed
- Bifidobacterium longum longum — amount NOT disclosed
- Lactobacillus acidophilus — amount NOT disclosed
- Lactobacillus casei — amount NOT disclosed
- Lactobacillus fermentum — amount NOT disclosed
- Lactobacillus paracasei — amount NOT disclosed
- Lactobacillus plantarum — amount NOT disclosed
- Lactobacillus rhamnosus GG — amount NOT disclosed
- Lactococcus lactis — amount NOT disclosed

**Blend — Fiber Inulin Blend** (total: amount NOT disclosed)
- Acacia senegal — amount NOT disclosed
- Apple Fiber — amount NOT disclosed
- Inulin — amount NOT disclosed

**Other ingredients:** Starch, Hypromellose, Gellan Gum, Water, Purified, L-Leucine, Pectin

**Quality claims stated on the label:** GMP certified/compliant
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*
```
ID: PG-2CB66194BCEE
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 113. Creatine Monohydrate 3500

**Brand:** GNC Pro Performance
**Servings/day:** 1

**Actives:**
- Creatine — 3.5 Gram(s)

**Other ingredients:** Gelatin

**Quality claims stated on the label:** none stated (not evidence testing didn't happen)
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*
```
ID: PG-0D23AB17C2A2
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 114. Keratin 500 mg

**Brand:** Double Wood Supplements
**Servings/day:** 1

**Actives:**
- Keratin Peptides, Hydrolyzed — 500.0 mg

**Other ingredients:** Hypromellose, Magnesium Stearate

**Quality claims stated on the label:** none stated (not evidence testing didn't happen)
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*
```
ID: PG-CA14A61BB672
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 115. MediClear Orange Vanilla Flavored

**Brand:** Thorne
**Servings/day:** 1

**Actives:**
- Vitamin A — 1.5 mg (167.0% DV)
- beta-carotene — 900.0 mcg
- Vitamin A — 600.0 mcg
- Vitamin C — 300.0 mg (333.0% DV)
- Vitamin D — 10.0 mcg (50.0% DV)
- Vitamin E — 80.6 mg (537.0% DV)
- Vitamin E — 73.9 mg
- Vitamin E — 6.7 mg
- Vitamin E — 98.5 mg
- Thiamin — 12.0 mg (1000.0% DV)
- Vitamin B2 — 5.0 mg (385.0% DV)
- Niacin — 38.0 mg (237.0% DV)
- Niacin — 30.0 mg
- Niacin — 8.0 mg
- Vitamin B6 (unspecified) — 10.0 mg (588.0% DV)
- Folate — 500.0 mcg DFE (125.0% DV)
- Vitamin B9 — 300.0 mcg
- Vitamin B12 — 50.0 mcg (2083.0% DV)
- Biotin — 150.0 mcg (500.0% DV)
- Pantothenic Acid — 50.0 mg (1000.0% DV)
- Choline — 11.0 mg (2.0% DV)
- Calcium — 300.0 mg (23.0% DV)
- Iron — 2.0 mg (11.0% DV)
- Magnesium — 150.0 mg (36.0% DV)
- Zinc — 10.0 mg (91.0% DV)
- Selenium — 70.0 mcg (127.0% DV)
- Manganese — 1.5 mg (65.0% DV)
- Chromium — 100.0 mcg (286.0% DV)
- Molybdenum — 50.0 mcg (111.0% DV)
- Potassium — 100.0 mg (2.0% DV)
- Glycine — 1.65 Gram(s)
- Medium chain triglycerides — 1.5 Gram(s)
- Glutamine — 500.0 mg
- Lysine — 500.0 mg
- Milk Thistle — 250.0 mg
- Taurine — 110.0 mg
- Methylsulfonylmethane — 100.0 mg
- Betaine Anhydrous — 50.0 mg
- Greenselect — 50.0 mg
- Glutathione — 30.0 mg
- Boron — 100.0 mcg
- Lutein — 60.0 mcg
- Vanadium — 50.0 mcg

**Blend — Proprietary Blend** (total: amount NOT disclosed)
- Pea Protein isolate — amount NOT disclosed
- Rice Protein — amount NOT disclosed

**Other ingredients:** pure Cane Molasses, Vanilla flavoring, Orange flavoring, Silicon Dioxide, Purefruit Select

**Quality claims stated on the label:** none stated (not evidence testing didn't happen)
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*

> **⚠ DATA NOTE** — **beta-carotene 900.0** is the TOTAL; the entries after it are its constituent forms. Do NOT add them to it
```
ID: PG-9634533A61D6
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 116. Fish Oil Omega-3s

**Brand:** GNC Pro Performance
**Servings/day:** 1

**Actives:**
- none listed with an amount

**Other ingredients:** Fish Oil, Bovine Gelatin, Glycerin, Ethylcellulose, Water, Purified, Ammonium Hydroxide, Medium Chain Triglyceride, Mixed Tocopherols, Oleic Acid, Sodium Alginate, Stearic Acid

**Quality claims stated on the label:** purity verified, Informed Choice
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*
```
ID: PG-4E5070405C96
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 117. Psyllium Husk 1,500 mg

**Brand:** Nutricost
**Servings/day:** 1

**Actives:**
- Psyllium fiber — 1500.0 mg

**Other ingredients:** Hypromellose, Rice Flour

**Quality claims stated on the label:** none stated (not evidence testing didn't happen)
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*
```
ID: PG-BDDFF32A0FCF
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 118. XR Series BCAA Advanced XR Berry Fusion

**Brand:** GNC Pro Performance
**Servings/day:** 0.047

**Actives:**
- Leucine — 10.0 Gram(s)
- Isoleucine — 2.0 Gram(s)
- Valine — 2.0 Gram(s)

**Other ingredients:** Natural and Artificial flavors, Citric Acid, Hydrogenated Vegetable Oil, Malic Acid, Monoglycerides, Sucralose, FD&C Red #40

**Quality claims stated on the label:** purity verified, Informed Choice
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*

> **⚠ DATA NOTE** — servings-per-day below 1 is our defect — assume **1 serving/day**
```
ID: PG-816ABA55FC3C
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 119. Primadophilus Probifia Pearls

**Brand:** Nature's Way
**Servings/day:** 1

**Actives:**
- Proprietary Blend (Metabolite, constituent, extract, isolate, or combination of these) — 15.0 mg

**Blend — Proprietary Probiotic Blend** (total: amount NOT disclosed)
- Bifidobacterium animalis lactis — amount NOT disclosed
- Bifidobacterium bifidum — amount NOT disclosed
- Bifidobacterium breve — amount NOT disclosed
- Bifidobacterium infantis — amount NOT disclosed
- Bifidobacterium longum — amount NOT disclosed

**Other ingredients:** Coconut Oil, Palm Oil, Fish Gelatin, Vegetable Glycerin, Soy Lecithin, Pectin, Silicon Dioxide

**Quality claims stated on the label:** none stated (not evidence testing didn't happen)
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*
```
ID: PG-DB610C0D5410
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

## 120. Pre-Workout Complex Blue Raspberry

**Brand:** Nutricost Women
**Servings/day:** 0.088–0.175

**Actives:**
- Thiamin — 15.0 mg (1250.0% DV)
- Niacin — 20.0 mg (130.0% DV)
- Vitamin B6 — 20.0 mg (1180.0% DV)
- Folate — 340.0 mcg DFE (90.0% DV)
- Vitamin B12 — 125.0 mcg (5210.0% DV)
- Citrulline — 4000.0 mg
- Beta-Alanine — 2000.0 mg
- Betaine Anhydrous — 1200.0 mg
- AAKG — 750.0 mg
- Agmatine — 500.0 mg
- NALT — 300.0 mg
- Theanine — 200.0 mg
- Caffeine — 200.0 mg
- Norvaline — 100.0 mg
- Theobromine — 100.0 mg
- Huperzine — 50.0 mcg

**Other ingredients:** Natural Flavors, Malic Acid, Citric Acid, Calcium Silicate, Silicon Dioxide, Sucralose, Blue Spirulina

**Quality claims stated on the label:** GMP certified/compliant
*(These are label claims only. Whether the exact product appears in the certifier's own records is yours to establish.)*

> **⚠ DATA NOTE** — servings-per-day below 1 is our defect — assume **1 serving/day**; **Agmatine 500.0** is the TOTAL; the entries after it are its constituent forms. Do NOT add them to it
```
ID: PG-6BE317D1D8F7
FORMULATION (0-20):
DOSE (0-20):
EVIDENCE (0-20):
TRANSPARENCY (0-15):
VERIFICATION (0-15):
QUALITY (0-10):
SAFETY:
DRIVER:
CONFIDENCE:
LABEL ENOUGH?:
SOURCES:
WHY:
ODD: none
```

---

# Brands in this set (conflict check)

- BulkSupplements.com
- CVS Pharmacy
- Doctor's Best
- Double Wood Supplements
- GNC
- GNC AMP Advanced Muscle Performance
- GNC Beyond Raw
- GNC Beyond Raw Chemistry Labs
- GNC Herbal Plus
- GNC Natural Brand
- GNC Pro Performance
- GNC Pro Performance AMP
- GNC Probiotic
- GNC Select
- GNC Total Lean
- GNC Women's
- GNC Women's Ultra Mega
- Garden of Life
- Garden of Life Dr. Formulated
- Garden of Life Dr. Formulated Probiotics
- Garden of Life MyKind Organics
- Jarrow Formulas
- Life Extension
- Nature Made
- Nature's Bounty
- Nature's Way
- Nature's Way Fatigued to Fantastic!
- Nordic Naturals
- Nutricost
- Nutricost Kids
- Nutricost Performance
- Nutricost Women
- OLLY
- Pure Encapsulations
- SR Sports Research
- Solgar
- Sports Research
- Spring Valley
- Thorne
- Transparent Labs
- vitafusion
