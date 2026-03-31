# How PharmaGuide Actually Works — Deep Dives

> Written for: investors, clinicians, partners, social content, pitch decks.
> Tone: Simple enough for anyone. Detailed enough to impress engineers.
> Updated: March 2026

---

# 1. FISH OIL — "We Don't Just Read The Label. We Do The Math."

## The Problem Everyone Else Ignores

Most apps see "Fish Oil 1000mg" on a label and say: *"You're taking fish oil. Cool."*

That tells you nothing. Here's what actually matters:

- **What FORM** is it? (Triglyceride? Ethyl Ester? Phospholipid?)
- **How much EPA and DHA** are actually inside that 1000mg?
- **Is that dose clinically meaningful** — or are you swallowing expensive pee?

A 1000mg fish oil softgel might only contain 300mg of actual EPA+DHA. The other 700mg? Filler fats. And if it's in ethyl ester form, your body absorbs **up to 50% less** than triglyceride form (Dyerberg et al., 2010).

**Nobody else checks this. We do.**

---

## How Our System Works

### Step 1: We Find The Real Numbers

We don't just read the "Fish Oil" header. We scan the entire supplement panel and pull out the **individual EPA and DHA amounts** — because those are the only numbers that matter.

```
Label says:          Fish Oil ............. 1200 mg
                       EPA ................ 360 mg
                       DHA ................ 240 mg

What most apps see:  "Fish Oil 1200mg" ✓ Done!

What we see:         EPA: 360 mg + DHA: 240 mg = 600 mg combined
                     Per serving (2 softgels/day): 600 mg × 2 = 1,200 mg/day
                     → Band: "AHA Cardiovascular Dose" ✅
```

We handle the math:
- **Unit conversion** — mg, g, mcg, µg all normalized automatically
- **Serving multiplication** — we calculate your actual daily intake, not just per-capsule amounts
- **Parent deduplication** — if the label lists "Total Omega-3s: 800mg" AND the individual EPA/DHA underneath, we don't double-count. We use the EPA + DHA line items only.

### Step 2: We Score The Form (Not All Fish Oil Is Equal)

This is where it gets real. The **form** of your omega-3 determines how much actually makes it into your bloodstream.

| Form | Bio Score | What It Means | The Verdict |
|---|---|---|---|
| **Re-esterified Triglyceride (rTG)** | 14/15 | Natural form, highest absorption, 70% better than EE (Dyerberg 2010) | The gold standard |
| **Krill Oil (Phospholipid)** | 14/15 | 1.3-1.6x better than standard TG, crosses blood-brain barrier easier (Ulven 2011) | Premium pick |
| **Emulsified (SMEDS/VESIsorb)** | 13/15 | Enhanced absorption via micro-emulsion technology (Qin 2017) | High-tech option |
| **Natural Triglyceride** | 12/15 | Natural form from whole fish, less concentrated but well-absorbed | Solid choice |
| **Algal DHA** | 12/15 | Plant-based, high purity, traditionally DHA-dominant | Best vegan option |
| **Ethyl Ester (EE)** | 9/15 | Chemically modified, 30% less absorbed, worse on empty stomach | The cheap form |
| **Flaxseed ALA** | 6/15 | Only 5-10% converts to EPA, less than 5% to DHA | Almost useless for omega-3 |
| **"Fish Oil" (unspecified)** | 8/15 | No form listed = assume the worst (probably ethyl ester) | Red flag |

**When a label just says "Fish Oil" without specifying the form, we give it an 8. Because if it were triglyceride, they'd brag about it.**

We detect branded forms too: Nordic Naturals rTG, Superba Krill, VESIsorb, MaxSimil, Life's DHA — each mapped to its correct form score.

### Step 3: We Compare Your Dose To Clinical Research

Here's where we go further than anyone. We take your **daily EPA+DHA total** and compare it against real clinical thresholds:

| Your Daily EPA+DHA | What Research Says | Bonus Points |
|---|---|---|
| **4,000+ mg** | Prescription-strength dose. Used in REDUCE-IT trial for hypertriglyceridemia. This is Lovaza/Vascepa territory. | **+2.0 pts** |
| **2,000+ mg** | EFSA-approved health claim for blood triglyceride reduction | **+2.0 pts** |
| **1,000+ mg** | AHA recommendation for cardiovascular disease patients | **+1.5 pts** |
| **500+ mg** | FDA qualified health claim minimum for heart health | **+1.0 pts** |
| **250+ mg** | EFSA adequate intake for general population (2012) | **+0.5 pts** |
| **Under 250 mg** | Below the minimum threshold set by any major health authority | **+0.0 pts** |

---

## Real Edge Cases We Handle

**The "Looks Good But Isn't" Case:**
> Product: "Ultra Omega-3 1200mg"
> - Header says 1200mg fish oil. Sounds great.
> - EPA: 180mg, DHA: 120mg = **300mg total EPA+DHA**
> - That's only **25% active omega-3**. The rest is filler fat.
> - At 1 serving/day, that's 300mg — barely above the EFSA minimum.
> - Our score: Low form bonus, minimal dose bonus. The label lied by omission.

**The "Proprietary Blend Fish Oil" Case:**
> Product: "Omega Performance Blend 800mg"
> - EPA and DHA listed inside a proprietary blend with no individual amounts
> - We **refuse to award the omega-3 dose bonus** — because we can't verify the actual EPA+DHA
> - Blend flagged separately with disclosure penalty

**The "Flaxseed Omega-3" Mislead:**
> Product: "Plant-Based Omega-3 1000mg" (flaxseed oil)
> - Contains ALA, not EPA/DHA
> - Body converts only 5-10% to EPA and <5% to DHA
> - 1000mg ALA ≈ 50-100mg EPA equivalent
> - Bio score: 6/15. Dose bonus: 0. We explain why.

**The "Premium Form + Good Dose" Winner:**
> Product: "Nordic Naturals Ultimate Omega"
> - Form: re-esterified triglyceride (rTG) → bio score 14/15
> - EPA: 650mg + DHA: 450mg = 1,100mg per serving, 2 servings/day = 2,200mg/day
> - Dose band: "High Clinical" → +2.0 bonus points
> - Premium form bonus: +0.5 (A2 section)
> - This product earns points at every checkpoint.

---

## The Math Behind The Score

For a fish oil product, here's how scores stack up across our system:

```
Section A — Ingredient Quality (max 25 pts)
  ├── A1: Bioavailability/Form     → rTG gets 14, EE gets 9
  ├── A2: Premium Form Bonus       → +0.5 per additional premium form (score ≥14)
  ├── A3: Delivery System          → MaxSimil/VESIsorb = +3 pts
  └── A6: Single-Ingredient Bonus  → Score ≥16 = +3 pts, ≥14 = +2 pts

Section B — Safety (max 30 pts)
  └── Standard safety checks (banned, harmful, allergens, blend transparency)

Section C — Evidence (max 20 pts)
  └── Omega-3 qualifies for 7 synergy clusters:
      • Cardiovascular Support (1000mg min)
      • Joint & Inflammation (1000mg min)
      • Mood Balance (EPA ≥1000mg min)
      • Focus & Attention (DHA ≥500mg min)
      • Prenatal Support (DHA ≥200mg min)
      • Inflammation Control (1000mg min)
      • Omega-3 Absorption Enhancement (phospholipid bonus)

Section D — Brand Trust (max 5 pts)

Omega-3 Dose Bonus — folded into Ingredient Quality (up to +2.0 in current config)
  └── Based on daily EPA+DHA total vs clinical thresholds
```

**A cheap ethyl ester fish oil with 300mg EPA+DHA could score 30-40 points lower than a premium rTG product with 2,200mg EPA+DHA.** Same category. Completely different quality. We show that difference.

---

---

# 2. PROPRIETARY BLENDS — "We Crack Open What They're Hiding"

## The Problem

A proprietary blend is the supplement industry's legal loophole. Companies can list ingredients but **hide how much of each is inside.** They just give you a total weight.

This means a "Testosterone Support Blend 800mg" with 6 ingredients could be:
- 790mg of the cheapest filler + 2mg each of the expensive stuff
- Or a genuinely balanced formula

**You literally cannot tell.** And that's the point.

Between 2017-2024, testosterone blend supplements had the **highest contamination rates** with banned substances (SARMs, prohormones, undeclared steroids). A 2018 JAMA study found **776 adulterated weight loss products** over a decade.

---

## Our 3-Level Disclosure Detection

We're the only system that doesn't just detect blends — we **grade how transparent they are:**

| Level | What We Found | What It Means |
|---|---|---|
| **FULL** | All sub-ingredients have individual amounts listed | Transparent. No penalty. |
| **PARTIAL** | Total blend weight declared, ingredients listed, but individual amounts missing | They're hiding the ratios. Penalty applied. |
| **NONE** | No total weight. No individual amounts. Just a list of names. | Maximum opacity. Maximum penalty. |

### The Penalty Formula

This isn't a guess. It's math.

```
Penalty = Base + (Coefficient × Impact Ratio)

Where:
  FULL:    Base = 0,  Coefficient = 0  → Penalty = 0 (always)
  PARTIAL: Base = 1,  Coefficient = 3  → Penalty = 1 + (3 × impact)
  NONE:    Base = 2,  Coefficient = 5  → Penalty = 2 + (5 × impact)

Impact Ratio = Hidden Mass ÷ Total Product Active Mass
```

**Impact measures how much of the product is hidden.** A tiny 50mg blend in a 3000mg multivitamin barely matters (low impact). A 500mg blend that IS the entire product? That's a massive red flag (high impact).

### Real Example — Walking Through The Math

**Product: "Alpha Male Energy Complex"**
- Total product actives: 1,500 mg
- Contains: "Stimulant Blend 250mg" (partial disclosure)
  - Caffeine: 80mg (disclosed)
  - Yohimbine: ??? (hidden)
  - Synephrine: ??? (hidden)

```
Step 1: Calculate hidden mass
  Blend total: 250mg
  Disclosed amounts: 80mg (Caffeine)
  Hidden mass: 250 - 80 = 170mg

Step 2: Calculate impact ratio
  Impact = 170mg ÷ 1,500mg = 0.113 (11.3% of product is hidden)

Step 3: Apply penalty formula (PARTIAL)
  Penalty = 1.0 + (3.0 × 0.113) = 1.0 + 0.339 = -1.34 points

170mg of unknown stimulants. Could be yohimbine.
Could be synephrine. You'd never know without us.
```

### The Penalty Table (Quick Reference)

| Disclosure | Impact = 0% | Impact = 25% | Impact = 50% | Impact = 100% |
|---|---|---|---|---|
| **Full** | 0.00 | 0.00 | 0.00 | 0.00 |
| **Partial** | -1.00 | -1.75 | -2.50 | -4.00 |
| **None** | -2.00 | -3.25 | -4.50 | -7.00 |

Maximum total blend penalty across all blends: **-10.0 points** (cap).

---

## 14 Blend Categories We Track

We don't just detect "a blend." We classify what KIND of blend it is — because the risks are completely different:

| Category | Risk | Why It Matters |
|---|---|---|
| **Stimulant Blends** | HIGH | Hidden caffeine stacking. Synephrine + yohimbine without labeling. Cardiovascular risk. |
| **Testosterone Blends** | HIGH | Highest contamination rate 2017-2024. SARMs, prohormones, undeclared steroids found by FDA. |
| **Weight Loss Blends** | HIGH | Sibutramine (banned) is the #1 adulterant. 776 adulterated products found over a decade (JAMA 2018). |
| **Nootropic Blends** | HIGH | Undeclared modafinil analogs. Serotonergic interactions with antidepressants. |
| **Pump/Nitric Oxide** | MODERATE | Hidden vasodilators. Hypotension risk. Excessive nitrate dosing. |
| **Adaptogen Blends** | MODERATE | 10-100x potency variance in raw botanicals. Ashwagandha thyroid effects. |
| **Hydration Blends** | MODERATE | Undisclosed sodium/potassium content. Electrolyte imbalance risk. |
| **Beauty/Collagen** | MODERATE | Undisclosed collagen doses. Biotin interference with lab tests. |
| **Superfood/Greens** | LOW | Doses usually too small for therapeutic effect. Heavy metal risk. |
| **Probiotic Blends** | LOW | Total CFU dominated by cheap filler strains. Strain-specific dosing unknown. |
| **Enzyme Blends** | LOW | Activity units (FCC/USP) not disclosed per enzyme. |
| **Delivery Tech** | LOW | Hidden allergens (soy lecithin, shellac). CYP3A4 interactions. |
| **Protein/Amino** | LOW | Protein spiking with cheap glycine/taurine. Unknown whey/casein ratios. |
| **General** | LOW | Complete opacity. Micro-dosing hidden behind marketing names. |

---

## Edge Cases We Handle

**Single-ingredient false positive:**
> A product flags Vitamin D as `proprietaryBlend: true` (data cleaning artifact). But it has no nested sub-ingredients. Our system checks: *Does it actually have children?* No → **not a blend.** False positive rejected.

**Non-proprietary aggregates:**
> "Total Cultures: 50 Billion CFU" with 5 probiotic strains underneath. This is a **math rollup**, not a proprietary blend. We filter these out: "Total Cultures", "Total Omega 3s", "Total Omega 6s" → not scored as blends.

**Deduplication (5mg bucket tolerance):**
> Both our detector and our data cleaner independently find the same blend. One says 502mg, the other says 500mg (parsing variance). We bucket them into 5mg groups: both round to 500 → **same blend, merged, scored once.** No double-penalties.

---

---

# 3. HARMFUL ADDITIVES — "107 Substances. Each One Verified By Hand."

## The Problem

The "Other Ingredients" section of a supplement label is where companies bury the stuff they don't want you to think about. Flow agents. Artificial colors. Preservatives. Sweeteners.

Some are harmless. Some are IARC Group 1 carcinogens.

Most apps skip this section entirely. **We audit every single line.**

---

## What We Track

**107 harmful additives**, each verified in our March 2026 audit:

- **25 HIGH severity** — artificial dyes, trans fats, acrylamide, BHA/BHT
- **54 MODERATE severity** — artificial sweeteners, certain preservatives
- **38 LOW severity** — minor flow agents, some thickeners

Every entry includes:
- **Mechanism of harm** — not just "bad," but WHY (e.g., "Metabolized to glycidamide, which forms DNA adducts and causes genotoxicity")
- **Regulatory status across 3 jurisdictions** — US FDA, EU/EFSA, WHO
- **Scientific references** — DOI links to actual studies
- **ADI values** — Acceptable Daily Intake where applicable
- **Population warnings** — children, pregnant women, kidney disease, etc.
- **All known aliases and E-numbers**

---

## How We Score Them

```
CRITICAL severity  →  -3.0 points  (formaldehyde, colloidal silver)
HIGH severity      →  -2.0 points  (artificial dyes, trans fats, acrylamide)
MODERATE severity  →  -1.0 points  (acesulfame K, artificial sweeteners)
LOW severity       →  -0.5 points  (minor flow agents)

Cumulative. Capped at -8.0 points maximum.
Deduplicated by additive ID (same additive can't penalize twice).
```

### Real Example

**Product with 3 harmful additives found:**
```
1. Acrylamide (contaminant)     → HIGH    → -2.0
2. Acesulfame Potassium         → MODERATE → -1.0
3. FD&C Yellow #5 (Tartrazine)  → HIGH    → -2.0
                                            ------
                          Total penalty:    -5.0 points
                          (under 8.0 cap, applied in full)
```

---

## Our Color Detection System (This One's Special)

Colors are the trickiest part of supplement labels. "Colors" could mean beet juice (great) or Red 40 (terrible). We built a **3-priority classification system:**

```
PRIORITY 1 — Explicit Artificial Dyes (ALWAYS flag)
  "Red 40", "FD&C Yellow 5", "Blue 1 Lake", "Tartrazine"
  → Instant harmful match. No ambiguity.

PRIORITY 2 — Explicit Natural Dyes (NEVER flag)
  "Beet juice", "Anthocyanins", "Gardenia blue", "Turmeric color"
  → Cleared. Even if it's listed in a suspicious context.

PRIORITY 3 — Indicator Matching (Ambiguous terms)
  140 natural indicator terms vs 120 artificial indicator terms
  Only used when no explicit match exists.
```

**Why this matters:** A product listing "Colors (from beet juice and turmeric)" won't get penalized. A product listing "Colors (Red 40, Blue 1)" will. And "Colors" alone with no context gets investigated, not assumed.

---

## Corrections We Made That Others Still Get Wrong

During our March 2026 audit, we found **11 critical factual errors** in industry-wide databases:

| Substance | What Others Say | What's Actually True |
|---|---|---|
| **Mineral Oil** | IARC Group 2B (possibly carcinogenic) | **IARC Group 1 (confirmed carcinogen)** — untreated/mildly treated mineral oils |
| **Carrageenan** | "Removed from USDA organic list" | **USDA kept it in 2018**, overriding NOSB recommendation |
| **Neotame** | ADI of 18 mg/kg | **ADI is 0.3 mg/kg (US) and 10 mg/kg (EU as of 2025)** — 60x error |
| **E153 (Carob Color)** | FDA approved | **Not FDA-approved** for food use in the US |

These aren't minor details. Mineral Oil being Group 1 vs Group 2B is the difference between "probably fine" and "confirmed carcinogen." We got it right. Most databases still haven't.

---

---

# 4. BANNED INGREDIENTS — "137 Substances. Punctuation Can't Fool Us."

## The Problem

Banned ingredients don't always announce themselves. They hide behind:
- Chemical aliases (DMHA = 2-Amino-5-Methylhexane = Octodrine = 2-Aminoisoheptane)
- Punctuation tricks (IGF-1 vs IGF–1 vs IGF 1 vs igf1)
- Marketing names ("Jack3d Advanced Formula" contained DMAA)
- Near-miss spellings (Dymethazine vs Dimethazine)

A basic text search misses most of these. **Our system catches them all.**

---

## Our 4-Layer Matching Engine

### Layer 1: Exact Match (Confidence: 100%)
```
Ingredient text → normalize → compare against all 137 entries + aliases
"Ephedra" → "ephedra" → MATCH → BANNED
```

### Layer 2: Alias Match (Confidence: 90%)
Every banned substance has **all known aliases** registered:
```
DMHA has 8+ aliases:
  "2-aminoisoheptane", "octodrine", "valerophenone",
  "2-amino-6-methylheptane", "dimethylhexylamine",
  "2-aminoheptane", "amidrine", "2-amino-5-methylhexane"

Any of these → MATCH → BANNED
```

### Layer 3: Token-Bounded Match (Confidence: 70%)
Pattern matching with word boundaries — prevents partial matches:
```
Pattern: (?<![a-z0-9]) + term + (?![a-z0-9])

"IGF-1" in "contains IGF-1 for recovery" → MATCH ✅
"IGF" in "IGFBP3 binding protein"        → NO MATCH ✅ (boundary blocks it)
```

### Layer 4: Negation Detection (Anti-False-Positive)
We check if the ingredient is being **claimed as absent:**
```
"Ephedra-free formula"     → negated → NOT flagged ✅
"Free from ephedra"        → negated → NOT flagged ✅
"Contains no ephedra"      → negated → NOT flagged ✅
"Without ephedra"          → negated → NOT flagged ✅
"Non-ephedra thermogenic"  → negated → NOT flagged ✅
```

---

## The Punctuation Problem (And How We Solved It)

Most databases match text literally. So "IGF-1" matches but "IGF–1" (with an em-dash) doesn't. Or "IGF 1" (with a space) doesn't.

**Our normalization pipeline handles this:**

```
Input:  "IGF–1"  (em-dash)    → normalize → "igf-1"  → MATCH
Input:  "IGF 1"  (space)      → normalize → "igf 1"  → key: "igf_1" → MATCH
Input:  "igf1"   (no sep)     → normalize → "igf1"   → key: "igf1"  → MATCH
Input:  "IGF-1"  (hyphen)     → normalize → "igf-1"  → MATCH

All four: same substance. All four: caught.
```

This applies to every banned substance. Delta-8 THC alone has **11 registered aliases** covering every way a label might write it.

---

## False Positive Prevention (Just As Important)

Catching banned substances is useless if you also false-flag safe products. We have **3 defense layers:**

### Defense 1: Negative Match Terms
Each banned entry can have terms that **cancel the match:**
```
IGF-1 negative terms (20 total):
  "igf binding protein", "igfbp", "igf-bp", "lr3", "long r3",
  "deer antler", "deer antler velvet", "colostrum", "bovine colostrum"...

Product: "Contains IGFBP-3 (IGF Binding Protein)"
  → "igf" found... but "igf binding protein" is a negative term
  → CLEARED. Not flagged. ✅
```

### Defense 2: Allowlist / Denylist
Explicit overrides for known edge cases:
```
ALLOW_IGF1:  Allows controlled matching of "igf-1" and "igf 1"
DENY_IGF_BINDING_PROTEIN:  Regex blocks "igf[-\s]+binding[-\s]+protein"
DENY_IGFBP:  Regex blocks "igfbp\d*"
DENY_IGF1_LR3:  Blocks IGF-1 LR3 variants (different substance)
```

### Defense 3: Context Requirements
For high-collision categories (like colorants), we require **explicit context:**
```
"Orange B" is a banned dye.
But "Orange Extract" contains the word "orange."

Our rule: Only flag "Orange B" if the text also contains
  "dye", "color", "colour", "fd&c", "fdc", "lake", or "pigment"

"Orange Extract (citrus sinensis)" → no color context → NOT flagged ✅
"FD&C Orange B Lake"               → color context   → FLAGGED ✅
```

---

## Scoring: Hard Fails vs Penalties

Not all banned substances are scored the same:

| Status | What Happens | Example |
|---|---|---|
| **Banned** | Product **FAILS immediately**. No score. Hard block. | Ephedra, DMAA, DNP, Sibutramine |
| **Recalled** | Product **FAILS immediately**. Specific product recall. | Hydroxycut (historical), specific lot recalls |
| **High Risk** | **-10 point penalty** + warning flag | Delta-8 THC, certain gray-market compounds |
| **Watchlist** | **-5 point penalty** + caution flag | Substances under regulatory review |

**A single banned ingredient = instant fail. No amount of good ingredients can save the score.** That's by design.

---

## Real Edge Cases

**DMHA and its 8+ identities:**
> A pre-workout lists "2-Amino-5-Methylhexane" — sounds like an amino acid to most people. Our system recognizes it as DMHA (banned stimulant linked to cardiac events). Flagged and failed, regardless of which of its 8 aliases appears on the label.

**IGF-1 vs IGFBP3:**
> IGF-1 (Insulin-like Growth Factor 1) is banned. IGFBP3 (IGF Binding Protein 3) is a completely different, safe substance. They share the letters "IGF." A basic search flags both. Our denylist regex correctly blocks IGFBP variants while still catching actual IGF-1.

**"PHO-Free" Claims:**
> PHO (Partially Hydrogenated Oils) is banned. But a product claiming "PHO-Free" is doing the RIGHT thing. Our negation detector catches "{term}-free" patterns and clears the flag instead of raising it.

**Delta-8 THC (The Gray Zone):**
> Not fully "banned" federally (2018 Farm Bill loophole), but high-risk. We classify it as `high_risk` with a -10 point penalty rather than an instant fail — reflecting the actual legal/safety reality rather than being absolutist.

---

---

# 5. RECALLED SUPPLEMENTS — "We Know The Difference Between A Bad Ingredient And A Bad Batch"

## Why This Is Harder Than It Sounds

There's a critical difference between:
- **Ingredient-level ban:** "Ephedra is banned everywhere, forever, in all products"
- **Product-level recall:** "This specific SKU of this specific brand was contaminated in this batch"

Most databases treat them the same. We don't.

---

## How We Handle Product-Level Recalls

```
Entity type: "product" (not "ingredient")

Matching logic:
  → Match against PRODUCT NAME (not ingredient name)
  → Only check first ingredient slot (slot 0)
  → Respect recall_scope: "batch_specific" vs "brand_wide"
  → No token-bounded matching (too imprecise for product names)
```

**Batch-specific recalls** only match exact product names — because recalling one batch of Brand X doesn't mean every Brand X product is bad.

**Brand-wide recalls** can match against brand name as fallback — because the entire brand's process is compromised.

---

## The Safety Verdict

| Finding | Result |
|---|---|
| Banned ingredient found (exact/alias match) | **PRODUCT FAILS** — hard block, no score |
| Recalled product matched | **PRODUCT FAILS** — hard block, no score |
| High-risk substance found | **-10 points** + `B0_HIGH_RISK_SUBSTANCE` flag |
| Watchlist substance found | **-5 points** + `B0_WATCHLIST_SUBSTANCE` flag |
| Harmful additive found | **-0.5 to -3.0 per additive** (cumulative, capped at -8.0) |

---

---

# 6. WHY THIS SYSTEM KEEPS GETTING BETTER

## Living Databases, Not Static Lists

Every database in our system is versioned (currently **Schema v5.0**) and actively maintained:

| Database | Entries | Last Updated | Update Frequency |
|---|---|---|---|
| Ingredient Quality Map | 541 ingredients, 32,157 variations | March 2026 | Continuous |
| Banned & Recalled | 137 entries | March 2026 | As FDA acts |
| Harmful Additives | 107 entries (audit-verified) | March 2026 | Quarterly audit |
| Clinical Studies | 177 ingredients backed | March 2026 | Monthly |
| Certifications | 45 rules (USP, NSF, GMP, etc.) | February 2026 | As programs update |
| Color Indicators | 260 terms (140 natural, 120 artificial) | February 2026 | As needed |
| Interaction Rules | 28 deterministic rules | Active | As literature publishes |

## Self-Auditing Architecture

- **Form Fallback Audit Report** — Every time an ingredient's specific form doesn't match our database, it gets logged. We currently track **708 form fallback instances** with 87 flagged as "forms differ" (likely scoring inaccuracies). These drive database expansion priorities.

- **Unmapped Ingredient Tracker** — Every ingredient we can't classify gets logged with occurrence counts and category inference. High-frequency unmapped ingredients get added to the database in the next update cycle.

- **Match Ledger** — Every single match is logged with: domain, method (exact/normalized/pattern/fuzzy), priority, and confidence. Full audit trail. No black boxes.

## The Numbers

```
33 reference databases
541 scored ingredients across multiple bioavailability forms
137 banned substances with analog + punctuation matching
107 harmful additives (hand-audited, 11 critical errors corrected)
177 clinically-backed ingredients with PubMed references
45 certification detection rules
28 drug/condition interaction rules
14 proprietary blend categories with 3-level disclosure scoring
260 color classification terms
272 fuzzy-match safety rules (preventing D2/D3, EPA/DHA confusion)
32,157 ingredient lookup variations
40,943 total indexed entries

All of it deterministic. All of it traceable.
All of it getting better every week.
```

---

---

# 7. PROBIOTICS & PREBIOTICS — "We Don't Count Bacteria. We Identify Them."

## The Problem

The probiotic market is the Wild West of supplements. Here's what most apps do:

> "Contains probiotics. 50 Billion CFU. Looks good!"

That tells you **nothing.** Here's what actually matters:

- **Which strains?** "Lactobacillus" is a genus with hundreds of species. "Lactobacillus rhamnosus GG" is a specific, clinically-studied strain with 1,000+ publications and 250+ clinical trials. They are NOT the same thing.
- **How many CFU of EACH strain?** A "50 Billion CFU" blend could be 49.9 billion of the cheapest filler strain and 100 million of the one that actually works.
- **Do they survive your stomach?** Most probiotics die in stomach acid before reaching your gut. The delivery format matters as much as the strain.
- **"At manufacture" vs "at expiration"?** A product with "50 Billion CFU at time of manufacture" might have 5 billion left by the time you take it. Only "at expiration" guarantees mean anything.

**We check all of this.**

---

## Step 1: We Identify Strains, Not Just Species

Most systems see "Lactobacillus acidophilus" and call it a day. We go deeper — to the **strain ID level.**

We track **42 clinically-relevant strains**, each mapped to their published research:

| Strain | ID | What Research Shows | Studies |
|---|---|---|---|
| **Lactobacillus rhamnosus GG** | LGG | Gold standard. Diarrhea prevention, immune support, pediatric GI | 1,000+ papers, 250+ trials |
| **Saccharomyces boulardii CNCM I-745** | Florastor | Traveler's diarrhea, C. diff prevention, antibiotic-associated diarrhea | 100+ RCTs |
| **Bifidobacterium lactis BB-12** | BB-12 | Immune modulation, digestive health, infant formula standard | 300+ publications |
| **Bifidobacterium lactis HN019** | HOWARU/DR10 | Immune function, gut transit time | 50+ studies |
| **Lactobacillus acidophilus NCFM** | NCFM | Lactose intolerance, immune function | 60+ publications |
| **Lactobacillus casei Shirota** | Yakult strain | Gut barrier, immune modulation | 100+ publications |
| **Lactobacillus plantarum 299v** | Lp299v | IBS symptom relief, iron absorption | 20+ RCTs |
| **Bifidobacterium infantis 35624** | Bifantis | IBS (all subtypes), gut inflammation | Phase III trial data |
| **Streptococcus salivarius K12** | BLIS K12 | Throat and ear health, oral immunity | 30+ studies |
| **Streptococcus salivarius M18** | BLIS M18 | Dental health, cavity prevention | 15+ studies |
| **Bacillus coagulans GBI-30, 6086** | GanedenBC30 | IBS, immune function, protein absorption | 25+ studies |
| **Lactobacillus reuteri DSM 17938** | BioGaia Protectis | Infant colic, GI health | 200+ publications |
| **Lactobacillus reuteri Prodentis** | Prodentis | Periodontal disease, oral health | 40+ studies |

**We match abbreviations too:** "L. rhamnosus GG" = "Lactobacillus rhamnosus GG" = LGG. Same strain, multiple label formats, one canonical identity.

---

## Step 2: We Parse CFU Like Pharmacists, Not Like Label Readers

CFU (Colony Forming Units) appears on labels in a dozen different formats. We normalize all of them:

```
"50 Billion CFU"          → 50,000,000,000 CFU  ✅
"500 Million CFU"         → 500,000,000 CFU     ✅
"1.5 B CFU"               → 1,500,000,000 CFU   ✅
"10 Billion Viable Cells" → 10,000,000,000 CFU  ✅ (treated as CFU equivalent)
"5 Billion Live Cultures" → 5,000,000,000 CFU   ✅
```

### The "At Manufacture" vs "At Expiration" Problem

This is the dirty secret of the probiotic industry:

```
Label A: "50 Billion CFU at time of manufacture"
Label B: "50 Billion CFU guaranteed through expiration"

Same number. COMPLETELY different meaning.
```

Probiotics die over time. A product with 50 billion at manufacture might have **5-10 billion** by the time you buy it off the shelf — especially if it wasn't refrigerated properly.

**We detect the guarantee type:**
- "At expiration" / "Through shelf life" / "Guaranteed through [date]" → **Accepted**
- "At time of manufacture" / "When manufactured" → **Not accepted for bonus qualification**

Only products that guarantee CFU **at expiration** qualify for our strict gating criteria.

---

## Step 3: We Score Delivery Format (Do They Even Survive Your Stomach?)

Here's a fact most people don't know: **up to 99% of standard probiotic capsules are destroyed by stomach acid** before reaching the intestine. The delivery format is everything.

| Delivery Format | Bio Score | Survival Rate | Shelf Stability | The Verdict |
|---|---|---|---|---|
| **Delayed-Release Capsules** (DRCaps) | 14/15 | 90%+ survive to intestine | Good | Gold standard for non-spore strains |
| **Spore-Based** (Bacillus coagulans) | 14/15 | >90% (inherent) | Excellent — no refrigeration needed | Nature's own armor. Survives heat, acid, bile. |
| **Liposomal Encapsulation** | 16/17 | Enhanced | Good | Premium tech. Targeted intestinal release. |
| **Synbiotic** (freeze-dried + prebiotic) | 15/17 | 95-99% (during drying) | Good | Prebiotics improve colonization after delivery |
| **Liquid Suspension** | 15/17 | ~60% | Poor — needs cold storage | Fast uptake but unstable |
| **Standard Powder** | 13/17 | 40-60% | Variable | No protection. Sensitive to moisture and heat. |

**A 50 billion CFU powder with 40% survival = 20 billion reaching your gut.**
**A 10 billion CFU delayed-release capsule with 90% survival = 9 billion reaching your gut.**

The powder "looks" 5x better on the label. It's actually about the same. We score accordingly.

---

## Step 4: The Scoring Math

### Default Probiotic Bonus (up to 3 points)

```
CFU Bonus:       +1.0 pt  if total CFU > 1 billion
Diversity Bonus: +1.0 pt  if ≥ 3 distinct strains identified
Prebiotic Bonus: +1.0 pt  if prebiotic ingredient detected (FOS, inulin, GOS)

Total = min(3.0, CFU + Diversity + Prebiotic)
```

### Extended Probiotic Scoring (up to 10 points — for dedicated probiotic products)

| Component | Threshold | Points |
|---|---|---|
| **CFU Count** | ≥ 50 billion | +4.0 |
| | ≥ 10 billion | +3.0 |
| | > 1 billion | +2.0 |
| | > 0 | +1.0 |
| **Strain Diversity** | ≥ 10 strains | +4.0 |
| | ≥ 6 strains | +3.0 |
| | ≥ 3 strains | +2.0 |
| | > 0 | +1.0 |
| **Clinical Strains** | ≥ 5 recognized | +3.0 |
| | ≥ 3 recognized | +2.0 |
| | ≥ 1 recognized | +1.0 |
| **Survivability** | Delayed-release / enteric / spore-based detected | +2.0 |
| **Prebiotic Pairing** | FOS, inulin, or GOS detected | +1.0 |

```
Extended Total = min(10.0, CFU + Diversity + Clinical + Survivability + Prebiotic)
```

---

## Step 5: Synergy Clusters (Probiotic Combos That Research Supports)

We don't just score individual strains — we detect **clinically-validated strain combinations:**

### Probiotic & Gut Health Cluster
> **Required:** Probiotics + prebiotics (FOS/inulin/GOS) or postbiotics
> **Min doses:** Probiotics ≥ 1 billion CFU, Inulin ≥ 5,000mg
> **S. boulardii special threshold:** ≥ 5 billion CFU (higher than general)
> **Bonus:** +1 point (Tier 1 — strong evidence)

### Immune Probiotic Blend
> **Required:** LGG + L. acidophilus + B. bifidum + B. lactis
> **Min dose:** 10 billion CFU each
> **Bonus:** +1 point (Tier 1)

### Gut Barrier Probiotic Blend
> **Required:** S. boulardii (5B) + L. plantarum (10B) + L. reuteri + B. infantis
> **Bonus:** +1 point (Tier 1)

### Mood-Gut Axis Blend (The Psychobiotic Stack)
> **Required:** L. helveticus + B. longum + L. casei + B. breve
> **Min dose:** 10 billion CFU each
> **Bonus:** +1 point (Tier 2 — moderate evidence)
> *This is the "psychobiotic" research frontier — strains shown to modulate the gut-brain axis.*

---

## Real Edge Cases We Handle

**The "50 Billion CFU But It's Mostly Filler" Case:**
> Product: "Ultra Probiotic 50 Billion — 12 Strains"
> - 50 billion total CFU — sounds impressive
> - But 45 billion is Lactobacillus acidophilus (the cheapest, most generic strain)
> - Only 500 million each of the 10 other strains including LGG and BB-12
> - The clinically-relevant strains are in **trace amounts**
> - Our system: detects strain diversity (+points) but notes the clinical strains are underdosed relative to synergy cluster thresholds

**The "At Manufacture" Trap:**
> Product: "Garden Fresh Probiotics — 100 Billion CFU"
> - Fine print: "at time of manufacture"
> - Standard powder format, no delayed-release, ships unrefrigerated
> - Estimated shelf degradation: 40-60% by purchase date
> - Our system: CFU guarantee type = "at_manufacture" → **does not qualify** for strict gating bonus. Standard powder delivery → bio score 13/17. Reality check applied.

**The Spore-Based Advantage:**
> Product: "Bacillus coagulans GBI-30 — 2 Billion CFU"
> - Only 2 billion CFU — looks small on paper
> - But it's spore-based: >90% survives stomach acid, no refrigeration needed, excellent shelf stability
> - Clinical strain GBI-30 detected → clinical strain bonus
> - Survivability coating detected (inherent to Bacillus) → +2.0 pts
> - Our system: rewards the strain that actually reaches your gut, not the one that dies on the way there

**The "Total Cultures" Non-Blend:**
> Product lists "Total Cultures: 30 Billion CFU" with 5 strains underneath
> - This is a **math rollup** — not a proprietary blend
> - Our system: filters "Total Cultures" as a non-proprietary aggregate → **no blend penalty**
> - Each strain scored individually for diversity and clinical relevance

**The Prebiotic Multiplier:**
> Product: "Synbiotic Complete" — 25 Billion CFU + 5g Inulin + FOS
> - Probiotics detected: diversity bonus ✅
> - Prebiotics detected (inulin + FOS): prebiotic bonus ✅
> - Synbiotic delivery format: bio score 15/17
> - Gut Health synergy cluster: probiotics ≥ 1B ✅, inulin ≥ 5g ✅ → cluster qualified → +1 synergy point
> - This product earns points at every checkpoint because it's doing everything right

---

## The Clinical Evidence Chain

Every strain we track links back to peer-reviewed research with our evidence scoring:

```
Evidence Level Multipliers:
  Product-human study:  1.0x  (highest — this specific product was tested)
  Branded-RCT:          0.8x  (branded strain like Florastor tested in RCT)
  Ingredient-human:     0.65x (general ingredient, human studies)
  Strain-clinical:      0.6x  (specific strain, clinical evidence)
  Preclinical:          0.3x  (animal/in-vitro only)

Base points per study type:
  Systematic review / meta-analysis:  6 pts
  RCT (single):                       4 pts
  Clinical strain evidence:           4 pts
  Observational:                      2 pts
```

**Example: Saccharomyces boulardii CNCM I-745 (Florastor)**
```
Study type:      clinical_strain (4 base pts)
Evidence level:  branded-rct (0.8x multiplier)
Score:           4 × 0.8 = 3.2 evidence points

This strain has FDA-acknowledged GRAS status for food use,
100+ RCTs, and is the ONLY yeast-based probiotic with
extensive clinical data for C. difficile prevention.
```

---

## What Makes Our Probiotic Scoring Unique

```
42 clinically-relevant strains tracked (not just genus/species)
6 delivery format tiers scored by actual gut survival rates
CFU guarantee type detection (manufacture vs expiration)
4 probiotic synergy clusters with strain-specific dose thresholds
Genus abbreviation matching (L. rhamnosus = Lactobacillus rhamnosus)
Strain ID matching (ATCC, DSM, NCFM, GG, K12, BB-12, HN019...)
"Total Cultures" rollup detection (no false blend penalties)
Prebiotic pairing detection (FOS, inulin, GOS)
Spore-based strain recognition (inherent survivability scoring)
Psychobiotic cluster detection (mood-gut axis research frontier)
```

Most apps: *"Contains probiotics."*
PharmaGuide: *"Contains Lactobacillus rhamnosus GG (LGG) at 10 billion CFU guaranteed through expiration, in delayed-release capsules with 90%+ gut survival, paired with 5g inulin prebiotic, qualifying for the Immune Probiotic and Gut Health synergy clusters, backed by 250+ clinical trials."*

**That's the difference.**

---

> *"Other apps scan barcodes. We decode molecules."*
>
> **PharmaGuide** — pharmaguide.io
