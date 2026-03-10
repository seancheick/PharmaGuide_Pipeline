# PharmaGuide Pipeline Infographic — "From Label to Truth"

> **Format:** Vertical scrolling infographic (Instagram carousel / TikTok static / LinkedIn post)
> **Vibe:** Fun, bold, slightly nerdy, trust-building. Think "How It's Made" meets sci-fi lab.
> **Illustration style:** Hand to Nano Banana — playful characters, clean icons, bold colors.

---

## HERO PANEL — The Hook

**Headline:**
> "You see a supplement label. We see 47,000 lines of truth."

**Subtext:**
> Most apps scan a barcode. PharmaGuide reverse-engineers the entire bottle.

**Visual:** Split screen — LEFT: a blurry supplement label. RIGHT: the same label exploding into colorful data streams, molecules, scores, and checkmarks.

---

## PANEL 1 — RAW CHAOS 🏭

**Title:** "Step 1: We Swallow the Raw Data"

**Copy:**
> Every supplement starts as messy government data — misspelled names, weird units, Greek letters, trademark symbols, and marketing fluff.
>
> **We ingest it all.** 130,000+ products from the NIH Dietary Supplement Label Database.

**Fun fact callout:**
> "µg, mcg, μg — that's the SAME thing written 3 different ways. We catch all of them."

**Visual:** A conveyor belt of chaotic supplement bottles entering a machine. Labels are messy, fonts are wild, some are upside down.

**Data points to show:**
- 130,000+ products processed
- Unicode normalization (α → alpha, β → beta, µg → mcg)
- Smart quote cleanup (7 different apostrophe variants — yes, really)
- Trademark™ and ® symbol stripping

---

## PANEL 2 — THE BRAIN 🧠

**Title:** "Step 2: We Speak Every Ingredient's Language"

**Copy:**
> "Cholecalciferol" sounds scary. It's just Vitamin D3.
> "Ascorbic Acid"? That's Vitamin C.
> "Croscarmellose Sodium"? That's a tablet disintegrant — it helps the pill dissolve.
>
> We translate **every single ingredient** into plain English so you actually know what you're taking.

**Visual:** A translator booth with ingredients walking in wearing lab coats and walking out in casual clothes with name tags. "Cholecalciferol" walks in → "Vitamin D3 ☀️" walks out.

**Real examples from our system:**
| Scary Label Name | What It Actually Is |
|---|---|
| Cholecalciferol | Vitamin D3 |
| Pyridoxine HCl | Vitamin B6 |
| Croscarmellose Na | Disintegrant (helps pill dissolve) |
| Stearic Acid | Flow Agent (manufacturing helper) |
| Cellulose | Plant Fiber (capsule shell) |
| dl-Alpha Tocopheryl Acetate | Synthetic Vitamin E |
| Methylcobalamin | Active Vitamin B12 |
| Retinyl Palmitate | Preformed Vitamin A |

---

## PANEL 3 — ACTIVE vs INACTIVE SPLIT ⚔️

**Title:** "Step 3: We Separate What WORKS from What DOESN'T"

**Copy:**
> Every supplement has two types of ingredients:
> - **Active ingredients** — the stuff that's supposed to help you (vitamins, minerals, herbs)
> - **Inactive ingredients** — fillers, binders, coatings, colors, flavors
>
> Most apps ignore the inactive list. **We don't.** Because that's where the sneaky stuff hides.

**Visual:** A sorting machine with two conveyor belts — GREEN belt for active ingredients (glowing, healthy), RED belt for inactive ingredients being inspected under a magnifying glass.

**Stat callout:**
> "We classify 535+ excipients and inactive ingredients — each tagged as natural or synthetic, with their exact function."

---

## PANEL 4 — THE FORM MATTERS 🔬

**Title:** "Step 4: Same Vitamin. VERY Different Quality."

**Copy:**
> Not all Vitamin D is the same. Not all fish oil is the same. Not all CoQ10 is the same.
>
> **The FORM of an ingredient determines how much your body actually absorbs.**
>
> We score 500+ ingredients across multiple forms — because "Vitamin E" on a label could mean 6 completely different things.

**Visual:** A podium/ranking scene. Three versions of the same vitamin standing on 1st, 2nd, 3rd place podiums with their bioavailability scores.

**Real scoring examples:**

### Fish Oil — The Big One 🐟
| Form | Bio Score | Absorption | Verdict |
|---|---|---|---|
| Triglycerides (rTG) | 10 + 2 bonus | Best | ✅ The real deal |
| Phospholipids (Krill) | 11 | High | ✅ Premium |
| Ethyl Esters | 9 | Lower | ⚠️ Standard/cheap form |

### CoQ10
| Form | Bio Score | Why |
|---|---|---|
| Ubiquinol (reduced) | 14 | Already active, highest absorption |
| Ubiquinone (oxidized) | 11 | Body must convert it first |

### Vitamin A
| Form | Bio Score | Absorption |
|---|---|---|
| Retinyl Palmitate | 14 | 70-90% — preformed, ready to use |
| Beta-Carotene | 10 | 8-65% — body converts at ~12:1 ratio |

**Callout bubble:**
> "When a label says 'Fish Oil' without specifying the form — we flag it. Because ethyl ester fish oil absorbs up to 50% less than triglyceride form."

---

## PANEL 5 — BLEND BUSTER 🕵️

**Title:** "Step 5: We Crack Open Proprietary Blends"

**Copy:**
> A "proprietary blend" is when a company lists ingredients but **hides how much of each is inside.**
>
> It's legal. It's common. And it's how companies stuff blends with cheap fillers while putting the expensive stuff in trace amounts.
>
> **We're the only app that detects blend disclosure levels.**

**Visual:** A locked vault being cracked open. Inside: a blend label with some amounts visible and some hidden behind question marks.

**Our 3-level disclosure detection:**

| Level | What It Means | Our Verdict |
|---|---|---|
| 🟢 FULL | Total amount + all individual amounts listed | Transparent — good sign |
| 🟡 PARTIAL | Total amount OR some amounts listed | Hiding something |
| 🔴 NONE | No amounts whatsoever | Maximum red flag |

**We detect 14 blend categories:**
- ⚡ Stimulant Blends (hidden caffeine stacking)
- 💪 Testosterone Blends (highest contamination risk — SARMs, prohormones found 2017-2024)
- 🔥 Weight Loss Blends (hidden banned compounds)
- 🧠 Nootropic Blends
- 🦴 Joint/Pain Blends
- 🛡️ Immune/Liver/Prostate Blends
- ...and more

**Stat callout:**
> "Testosterone blend supplements had the highest rate of contamination with banned substances between 2017-2024. We flag every single one."

---

## PANEL 6 — THE SAFETY WALL 🚨

**Title:** "Step 6: We Run It Through 4 Safety Databases"

**Copy:**
> Before we score anything, every ingredient passes through our safety gauntlet:

**Visual:** An ingredient walking through 4 checkpoint gates, each with a different guard/scanner.

### Gate 1: BANNED & RECALLED 🚫
> **137 permanently banned items** — from ephedra to DMAA to SARMs
> - Punctuation-proof matching (IGF-1, IGF–1, igf1, IGF 1 — all caught)
> - Brand-qualified detection (won't false-flag "Amazing Grass" for a different company's recall)
> - Analog detection (DMHA and all its chemical aliases)

### Gate 2: HARMFUL ADDITIVES ⚠️
> **110 harmful additives** — each audit-verified March 2026
> - Severity levels: Critical / High / Moderate / Low
> - Real regulatory status per country (US, EU, WHO)
> - Mechanism of harm + scientific references with DOI links
>
> *Example: We know Mineral Oil is IARC Group 1 carcinogen — not Group 2B like some databases still say.*

### Gate 3: ALLERGEN DETECTION 🤧
> **17 major allergens** (FDA FALCPA + EU Annex II)
> - Soy, milk, eggs, peanuts, tree nuts, fish, shellfish, wheat, sesame...
> - **Smart negation:** "Free from peanuts" CLEARS the flag (not triggers it)
> - Even catches hidden allergens: fermented soy (natto) still contains allergenic proteins

### Gate 4: EXCIPIENT SAFETY CHECK 🔍
> **535+ inactive ingredients classified**
> - Natural vs. synthetic tagging
> - GRAS (Generally Recognized As Safe) status
> - Function labeling (preservative, flow agent, coating, colorant)

---

## PANEL 7 — DOSAGE INTELLIGENCE 📊

**Title:** "Step 7: Too Little? Too Much? We Know."

**Copy:**
> Taking 10% of the recommended dose? Useless.
> Taking 500% of the upper limit? Dangerous.
>
> We check every nutrient against RDA (Recommended Daily Allowance) and UL (Upper Limit) values — and score accordingly.

**Visual:** A thermometer/gauge for each nutrient showing the zones.

**Our 5 adequacy bands:**

```
|  0-25% RDA  |  DEFICIENT     |  ❌ 0 points — why bother?        |
| 25-75% RDA  |  SUBOPTIMAL    |  ⚠️ 1 point — not enough          |
| 75-150% RDA |  OPTIMAL       |  ✅ 3 points — sweet spot!         |
|150-300% RDA |  HIGH          |  🟡 2 points — more isn't better   |
|  >300% RDA  |  EXCESSIVE     |  ❌ 0 points — waste of money      |
```

**Over Upper Limit alerts:**
- ⚠️ Caution: 100-150% UL
- 🟠 Warning: 150-300% UL
- 🔴 Critical: >300% UL

**Fun fact:**
> "Some multivitamins pack 16,667% of your daily B12. That's not a feature — that's your body flushing money down the toilet."

---

## PANEL 8 — SMART PAIRINGS 🤝

**Title:** "Step 8: We Spot the Power Combos"

**Copy:**
> Some ingredients supercharge each other. We detect these pairings automatically.

**Visual:** Two ingredients high-fiving with a lightning bolt between them.

**Real examples:**
- 🌶️ **Black Pepper (Piperine) + Turmeric (Curcumin)** → Absorption boost of **2,000%+**
- 🧈 **Fat-soluble vitamins (A, D, E, K) + Dietary fat** → Dramatically better absorption
- 🍊 **Vitamin C + Iron** → Enhanced iron absorption
- 🔬 **Liposomal delivery** → We detect enhanced delivery systems (liposomal, nanoparticle, enteric coating)

**Callout:**
> "If your turmeric supplement doesn't have piperine or a liposomal delivery system, you're absorbing almost nothing."

---

## PANEL 9 — THE INTERACTION ENGINE ⚡

**Title:** "Step 9: We Check What Clashes"

**Copy:**
> That supplement might be great on its own — but what about with your medications? Your health conditions? Your pregnancy?
>
> We run every ingredient through our interaction matrix.

**Visual:** A web/network diagram showing ingredients connected to conditions and drug classes with colored severity lines.

**Severity levels:**
- 🔴 **CONTRAINDICATED** — Do NOT take. Period.
- 🟠 **AVOID** — Seriously reconsider.
- 🟡 **CAUTION** — Talk to your doctor.

**Real rule examples:**
- Ephedra + Pregnancy → 🔴 CONTRAINDICATED
- Ephedra + Blood pressure meds → 🟠 AVOID
- Aloe Vera (oral) + Pregnancy → 🟠 AVOID
- Propylene Glycol + Kidney Disease → 🟡 CAUTION

**Stat callout:**
> "28 clinically-verified interaction rules — each backed by medical literature. Not guesses. Not AI hallucinations. Deterministic, peer-reviewed rules."

---

## PANEL 10 — CLINICAL EVIDENCE 📚

**Title:** "Step 10: We Back It With Science"

**Copy:**
> Every ingredient is linked to peer-reviewed clinical studies.
>
> We don't just say "Vitamin D is good for bones." We link to the actual PubMed study, with the evidence grade and the clinical dosage used.

**Visual:** A bookshelf of research papers with study grades floating above them like report cards.

**Evidence grades:**
- **A** — Strong, multiple RCTs
- **B** — Good, consistent evidence
- **C** — Limited but promising
- **D** — Preliminary/weak
- **R** — Retrospective only

**Callout:**
> "3,571 clinical study references. Each with PubMed ID, publication year, claim category, and evidence grade."

---

## PANEL 11 — FINAL SCORE 🏆

**Title:** "Step 11: The Verdict"

**Copy:**
> After all 10 checks, every product gets a transparent, explainable score.
>
> No black boxes. No mystery algorithms. Every point earned or lost is traceable back to the evidence.

**Visual:** A supplement bottle with a holographic score badge, surrounded by all the factors that contributed to its score — like a character stats screen in a video game.

**Score components visualized as a radar chart:**
- 🧬 Bioavailability (form quality)
- 📊 Dosage adequacy (RDA/UL)
- 🛡️ Safety (banned/harmful/allergen)
- 🔍 Transparency (blend disclosure)
- 🤝 Synergy (absorption enhancers)
- 📚 Evidence (clinical backing)
- 🏭 Quality (certifications: NSF, USP, GMP)

**Scoring penalties shown:**
- Harmful additive found (critical) → **-5 points**
- Harmful additive found (high) → **-3 points**
- Proprietary blend (no disclosure) → **penalty applied**
- Banned ingredient found → **instant fail / flagged**
- Allergen-free certified → **+2 bonus**

---

## PANEL 12 — THE RESULT (User View) 📱

**Title:** "What YOU See"

**Copy:**
> All of that — 47,000 lines of code, 33 reference databases, 500+ ingredient forms, 137 banned substance checks, 110 harmful additive audits — distilled into one clean, simple screen:

**Visual:** A beautiful phone mockup showing:
1. **Overall Score** (e.g., 82/100) with color badge
2. **What's inside** — plain English ingredient list with quality tags
3. **What to watch** — flagged harmful additives or allergens
4. **Interactions** — alerts for your specific conditions/meds
5. **Evidence** — tap any ingredient to see the science

---

## CLOSING PANEL — The Mic Drop 🎤

**Headline:**
> "Other apps scan barcodes. We decode molecules."

**Subtext:**
> PharmaGuide — The most sophisticated supplement intelligence engine in the world.

**By the numbers (footer stats):**
| Metric | Value |
|---|---|
| Products analyzed | 130,000+ |
| Reference databases | 33 |
| Ingredient forms scored | 500+ with multi-form bioavailability |
| Banned substances tracked | 137 |
| Harmful additives audited | 110 (verified March 2026) |
| Excipients classified | 535+ |
| Clinical study references | 3,571 |
| Interaction rules | 28 clinically-verified |
| Allergens detected | 17 (FDA + EU) |
| Blend categories detected | 14 |
| Fuzzy match safety rules | 272 (preventing D2/D3, EPA/DHA confusion) |
| Unit conversion precision | Form-aware (Vitamin A IU differs by source!) |

---

## CAROUSEL VERSION (Instagram / LinkedIn)

For a 10-slide carousel, use these panels:

| Slide | Title | Key Visual |
|---|---|---|
| 1 | "You see a label. We see 47,000 lines of truth." | Split: blurry label → data explosion |
| 2 | "We translate the scary names" | Translator booth with before/after |
| 3 | "We know WHICH form you're getting" | Fish oil podium (TG vs EE vs PL) |
| 4 | "We crack proprietary blends" | Vault cracking open, disclosure levels |
| 5 | "4 safety gates. Zero mercy." | Checkpoint gates (banned/harmful/allergen/excipient) |
| 6 | "Too little? Too much? We know." | Thermometer gauge with 5 zones |
| 7 | "We spot the power combos" | Piperine + Curcumin high-five = 2000% boost |
| 8 | "We check YOUR interactions" | Web diagram: ingredients ↔ conditions |
| 9 | "Every claim backed by science" | 3,571 studies, evidence grade cards |
| 10 | "Other apps scan barcodes. We decode molecules." | Phone mockup + stats footer |

---

## NANO BANANA ILLUSTRATION NOTES

**Character suggestions:**
- A tiny scientist character (the "PharmaGuide Brain") who guides the viewer through each step
- Ingredients as little characters with personalities (Vitamin D3 is sunny and confident, Ethyl Ester fish oil looks nervous and sweaty)
- The proprietary blend as a shady character in a trench coat hiding ingredients
- Banned substances as cartoon villains getting caught at checkpoints
- The final score as a glowing trophy/badge

**Color palette suggestion:**
- Primary: Deep teal/green (trust, health)
- Accent: Bright coral/orange (energy, alerts)
- Warning: Amber/red gradient (safety flags)
- Background: Clean white or soft cream

**Style:** Clean line art with bold fills, slight 3D depth, playful but not childish. Think Duolingo meets scientific precision.

---

## SOCIAL COPY OPTIONS

**Instagram caption:**
> Ever wonder what's REALLY in your supplements? 👀
>
> We built the most advanced supplement scoring engine in the world. 47,000 lines of code. 33 databases. 500+ ingredient forms scored.
>
> Swipe to see how we go from raw label → full truth →
>
> #supplements #health #transparency #pharmaguide #supplementscience

**LinkedIn post:**
> Most supplement apps scan a barcode and show you the label you already have.
>
> We reverse-engineer every ingredient — identifying the exact chemical form, scoring bioavailability, detecting proprietary blend deception, cross-referencing 137 banned substances and 110 harmful additives, checking drug interactions, and backing every claim with peer-reviewed clinical studies.
>
> 130,000+ products. 33 reference databases. 3,571 clinical study references.
>
> This is what supplement transparency actually looks like.

**Twitter/X thread starter:**
> Most supplement apps: "Here's your label info 📋"
>
> PharmaGuide: "Your fish oil uses ethyl esters (50% less absorption), has 2 hidden harmful additives, a proprietary blend with zero disclosure, and interacts with your blood pressure medication."
>
> Here's how we do it 🧵👇
