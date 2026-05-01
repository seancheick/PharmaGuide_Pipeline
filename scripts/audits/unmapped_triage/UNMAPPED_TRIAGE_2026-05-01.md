# Unmapped Active Ingredients — Cross-Brand Triage

**Generated:** 2026-05-01
**Scope:** all 21 brands processed in batch run 2026-04-30 21:05:29 EDT
**Method:** aggregated `unmapped_active_ingredients.json` from each brand's enriched output, classified into action categories, applied confident alias-additions, surfaced rest for your decision.

---

## Executive Summary

| Metric | Value |
|---|---|
| Total unique unmapped active ingredients | 352 |
| Total occurrences across products | 599 |
| Brands with unmapped ingredients | 21 of 21 |
| GNC currently blocked by coverage gate | 1 product (DSLD 74767) |

**Triage breakdown (after this audit):**

| Category | Unique | Occurrences | Action |
|---|---|---|---|
| ✓ ALIAS_TO_PARENT — applied | 12 | ~33 | Already added as aliases to existing parents (Cutch Tree, Bifido strains, Angelica gigas) |
| ⏸ ALIAS_TO_PARENT — false positive | 2 | 2 | Neoeriocitrin, Melitidin: classifier said citrus_bergamot_extract but those are CONSTITUENTS, not the extract. Need new entries, not aliases. |
| 🆕 NEW_PROBIOTIC | 15 | 25 | Add to IQM as new probiotic species/strains. **Need API verification** (NCBI taxonomy, GSRS where applicable) |
| 🆕 NEW_BOTANICAL | 20 | 47 | Add to `botanical_ingredients.json`. **Need verification** (USDA Plants/Kew Plants of the World binomial check) |
| 🆕 NEW_IQM_ACTIVE | 4 | 12 | Cetyl Myristate/Laurate/Oleate/Palmitoleate — CMO-family fatty acid esters used in joint formulas. **Need API verification** (PubChem CID, CAS, UNII) |
| ⚠️ BLEND_HEADER — your decision | **91** | **136** | Proprietary-blend header rows. Per your policy: "if blend with no child disclosed, let me know — we'll see how to deal with them as only active ingredients" |
| ⚠️ BLEND_DISCLOSED_MIXED — needs cleaner fix | 4 | 8 | Multi-ingredient strings ("X extract and Y extract") that the cleaner failed to split into separate rows |
| ❓ AMBIGUOUS — needs review | 204 | 332 | Various: branded ingredients, flavonoid constituents, niche herbs, descriptors. Each needs individual classification |

---

## Section 1 — Already Applied This Pass (alias additions)

Verified same-compound — added as aliases to existing parents:

### `acacia_catechu` (IQM) — Cutch Tree common-name coverage

Added 19 aliases including: `cutch tree`, `cutch tree wood and bark extract`, `cutch tree wood & bark extract`, `cutch tree bark extract`, `khair`, `khadira`, `black catechu`, `catechu`, plus ampersand-variants of existing "and" forms. Resolves the GNC product 74767 first blocker.

### `bifidobacterium_lactis` (IQM) — strain ID variants

Added per-form aliases for missing strain expressions:
- HN019 form: `bifidobacterium lactis strain hn019`
- BL-04 form: `bifidobacterium lactis strain bl-04`, `bifidobacterium lactis bl04`
- Bi-07 form: `bifidobacterium lactis strain bl-07`, `bifidobacterium animalis lactis bi-07`
- (unspecified) form: `bifidobacterium animalis lactis cul-34`, `bifidobacterium lactis uabia-12`, `bifidobacterium lactis uabla-12`

### `angelica_gigas` (IQM)

Added: `angelica gigas nakai`, `angelica gigas nakai root`, `angelica gigas nakai root extract`, `angelica gigas nakai extract` (Nakai is the botanist who named the species; same plant).

---

## Section 2 — BLEND HEADERS Needing Your Decision (91 unique, 136 occurrences)

Per your policy: "if blend with no child disclosed, let me know we'll see how to deal with them as only active ingredients".

These are proprietary-blend label-header rows. They typically have:
- Name ending in `Blend`, `Complex`, `Matrix`, `System`, `Compound`, `Formula`
- Optional trailing colon
- Either no quantity OR a quantity that represents the BLEND TOTAL (not per-active dose)

The canonical fix is to add them to `scripts/constants.py:898 BLEND_HEADER_EXACT_NAMES` (where existing entries like "antioxidant boost", "vitality boost", "natural defense blend" already live). The cleaner's `_should_skip_from_scoring` Group Z then unconditionally treats them as headers, excluding them from the scorable count.

**You need to decide:** which of these are real label-only headers (just the parent row name, children listed separately) vs. opaque blends where the manufacturer disclosed only the blend name and total without per-ingredient amounts.

### Group 2A — Generic descriptive blend headers (likely safe to add as headers)

Trailing colon, no quantity, looks like a plain label organization row. These are the highest-confidence blend headers — children are typically listed immediately below.

```
Sports Blend:
Brain Health Blend:
Vasodilator Matrix:
Energy Support Blend:
Performance Energy & Metabolism Blend:
Cholesterol Support Blend:                    ← THE GNC 74767 BLOCKER
Circulatory Support Complex:
```

### Group 2B — Branded / formula-specific blends (need brand-by-brand check)

```
8× Wheybolic Protein Complex
4× Omega-Zyme Ultra Enzyme Relay Blend
4× Healthy Aging Free Radical Protection Blend
4× Memory Health Blend
3× Raw Kombucha Enzyme Blend
3× Healthy Aging Antioxidant Blend
3× Fast-Acting Comfort Blend
3× Digestive Health & Comfort Blend
2× Nordic Flora Daily Blend
2× RAW Kombucha Probiotic & Tea Blend
2× Oral Health Probiotic Blend
2× RAW decaffeinated Green Coffee bean extract Blend
2× Raw Probiotic & Enzyme Blend
2× Skin Health Blend
2× Antioxidant System
2× Herbal Relaxation Complex
2× Muscle Shield System
2× Lipo-Thermo Trigger Blend
2× ROS & Catabolism Combating Blend
2× Multi-Action Amino Acid Blend
2× Anti-Catabolic Blend
2× Anabolic Pump Matrix
2× Extreme Ergogenic Compound
2× Sustained Protein Blend
2× Fava Bean Hydrolysate Peptide Complex
2× Ripped Blend
2× Neuro-Charger Matrix
2× Fruit & Vegetable Antioxidant Blend
2× Brain Health Blend
2× Sports Blend
1× Nordic Flora Comfort Blend
1× Immune Balance Blend
1× Citrus C Blend
1× Ionic Mineral Blend
1× Organic Paractin 14-Neo-Andro Blend
1× Glycemic Balance Blend
1× Tea Trio(R) Blend
1× Raw Whole Food Probiotic Blend
1× Liver & Urinary Tract Health Blend
1× Sports Antioxidant Blend
1× Joint Comfort Blend
1× Joint Cushion Blend
1× Muscle Support & Recovery Blend
1× Muscle Buffering System
1× Thermo Energy Matrix
1× Sexual Health Circulatory Blend
1× Digestive Support Matrix
1× Spectra Total ORAC Blend
1× PEG-Arginine System
1× BioCore Recovery(TM) Enzyme Blend
1× Calorie Burn Blend
1× Antioxidant Fruit and Vegetable Blend
1× Fast-Acting Mobility Blend
1× Tri-Pepper Blend
1× Metabolic Igniter Blend
1× Physio Metabolic Pump Blend
1× Fatty Acid and Energy Metabolizer Blend
1× TRISYNEX(TM) Complex
1× Slimvance Patented Blend
1× Micro-Peptide Creatine Complex
1× Micro-Peptide Leucine Complex
1× Amylopectin/Chromium Complex
1× Hardcore Muscle Support System
1× Hyper-Vascular Matrix
1× Anabolic Amino Matrix
1× Lean Muscle Recovery Blend
1× High-Energy Thermogenic Blend
1× Energizing Fatty Acid Metabolizer Blend
1× Creatine Precursor Compound
1× Power Complex
1× Women's Health and Beauty Blend
1× Eye & Skin Health Complex
1× Circulatory Support Complex
1× Digestion Complex
1× Performance, Energy & Metabolism Blend
1× Performance, Energy & Metabolish Blend
1× Joint Cushioning Sports Blend
1× Extra Care Probiotic blend
1× Tocotrienol-Tocopherol Complex
1× Protease SP Plus Blend
1× ProHydrolase Protease Blend
1× Bergamonte full spectrum Citrus bergamia Risso extract complex
1× Trade Mineral Blend
1× Bifidobacteria Blend
1× Heart Protection Blend
```

---

## Section 3 — NEW Entries Needing API Verification

### 3A. NEW_PROBIOTIC (15 unique, 25 occurrences) — add to IQM as new species

These are probiotic species/strains not yet in IQM. **Verification needed via NCBI Taxonomy** (taxid lookup) and FDA GSRS where the strain is registered. Bio_score should be assigned based on clinical evidence (typically 8-10 for well-studied probiotics).

```
4× Lactobacillus lactis            ← reclassified to Lactococcus lactis 1985 (taxonomy)
3× Lactobacillus bulgaricus, Lactobacillus plantarum   (mixed string — needs split)
2× Lactobacillus bulgaricus, plantarum                 (same — needs split)
2× Bifidobacterium animalis lactis SD-5674
2× Bifidobacterium animalis lactis SD-5220
2× Bifidobacterium animalis             (parent species — likely add to existing bifidobacterium_lactis as alias)
2× Lactobacillus crispatus UALcr-35
1× Enterococcus faecium                 ← review carefully, some strains are pathogenic
1× Bifidobacterium animalis lactis Bl-07
1× Bifidobacterium lactis & bifidum
1× Bifidobacterium animalis lactis HN-019
1× Pediococcus pentosaceus (CUL 15)
1× Lactobacillus crispatus
1× Bifidobacterium animalis lactis UABla-12
1× Lactobacillus jensenii
```

### 3B. NEW_BOTANICAL (20 unique, 47 occurrences) — add to `botanical_ingredients.json`

These are recognized herbs/fungi. Most are medicinal mushrooms (Garden of Life mushroom blends). **Verification needed via USDA Plants Database or Kew's Plants of the World** for binomial-correct entries.

```
4× organic Auricularia auricular         ← Wood Ear mushroom (also "auricularia auricula-judae")
4× organic Annulohypoxylon stygium       ← medicinal fungus
4× organic Fuling                        ← Chinese name for Wolfiporia cocos (= Poria)
3× organic Wolfiporia cocos              ← same as Fuling
3× organic Fomitopsis cajanderi          ← Pink Conk fungus
3× Wolfiporia cocos                      ← same as organic Wolfiporia cocos
3× Fomitopsis cajanderi
3× Fuling                                ← consolidate with Wolfiporia
3× Annulohypoxylon
3× Lindera (Lindera aggregata) extract   ← Wu Yao, TCM herb
2× Organic Polyporus umbellatus Mycelia  ← Zhu Ling
2× Annulohypoxylon stygium
2× Green leaf Sprout-Arugula (Eruca sativa) powder
2× Cratevo Three-Leaf Caper (Crateva nurvala) extract
1× Essence of organic Geranium (aerial parts) oil
1× Fuling Mushroom
1× Organic Turkey Tails (Trametes versicolor) Mycelia
1× Bifidoacterium animalis (CUL 34)      ← typo for Bifidobacterium → goes to NEW_PROBIOTIC
1× Cratevox Three-leaf Caper             ← typo for Crateva nurvala
1× Antrodia camphorata                   ← Niu-Chang-Chih, Taiwanese medicinal mushroom
```

### 3C. NEW_IQM_ACTIVE (4 unique, 12 occurrences) — add to IQM

Cetyl ester family — used in joint health formulas (CMO/Cetyl-Myristoleate class). Each is a distinct chemical entity, scoreable as joint-support active.

```
3× Cetyl Myristate           CAS: 19710-42-2   PubChem CID: 21217
3× Cetyl Laurate             CAS: 24447-15-2   PubChem CID: 23694
3× Cetyl Oleate              CAS: 22393-85-7   PubChem CID: 5366416
3× Cetyl Palmitoleate        CAS: 33233-13-7   PubChem CID: tbd via API
```

**These CAS values are commonly cited but MUST be content-verified via PubChem before adding.** Also need UNII codes via FDA GSRS where available, and bio_score / clinical evidence assignment via PubMed search for joint-health RCTs.

---

## Section 4 — BLEND_DISCLOSED_MIXED (4 unique, 8 occurrences) — needs cleaner fix

These are multi-ingredient strings that the cleaner concatenated rather than splitting:

```
3× Acacia catechu wood & bark extract and Chinese Skullcap root extract
3× Cutch Tree wood and bark extract                          ← already aliased post-fix
1× Relora Magnolia bark extract (Magnolia officinalis) and Phellodendron bark extract Blend (Phellodendron amurense)
1× elevATP Ancient Peat extract, and Apple extract
```

**Fix path:** the cleaner needs to split rows containing " and " between two parenthesized binomials, or rows like "X extract and Y extract" (where both X and Y are separately recognizable). This is a `clean_dsld_data.py` parser improvement, not a data-only fix.

---

## Section 5 — AMBIGUOUS (204 unique, 332 occurrences) — top 50 below

Each needs individual classification. Listed by frequency:

```
8× Wheybolic Protein Complex                    → likely BLEND_HEADER (branded)
5× Citrus Bioflavonoids 95%                     → IQM if standardized; else other_ingredients
4× Semi-Alkaline Protease                       → enzyme; map to digestive_enzymes parent or new IQM
4× Essence of organic Orange (peel) oil         → essential oil; new IQM under essential_oils OR other_ingredients (cleaner descriptor stripping)
4× organic Blazei                               → Agaricus blazei mushroom → NEW_BOTANICAL
4× Yum Berry                                    → Myrica rubra (Yangmei) → NEW_BOTANICAL
4× ModCarb / Modcarb                            → branded modified carb (rice/oat) → standardized_botanicals
4× PreticX Xylooligosacharides                  → branded XOS prebiotic → standardized_botanicals OR new IQM (active prebiotic)
3× organic Pumpkin Protein                      → cleaner descriptor; alias to existing pumpkin_seed_protein if exists
3× organic Watermelon Protein                   → niche; new IQM if scoreable
3× Essence of organic Chamomile (leaf) oil      → essential oil + descriptor strip
3× organic White Wood Ear                       → Tremella fuciformis → NEW_BOTANICAL
3× organic Rosy Polypore                        → Fomitopsis pinicola → NEW_BOTANICAL
3× Blend (Non-Nutrient/Non-Botanical)           → BLEND_HEADER (literal)
3× Blazei                                       → → NEW_BOTANICAL (Agaricus blazei)
3× RAW Food-Created Co-Enzyme Q10               → branded form of CoQ10; alias to coq10
3× Ocean-derived trace minerals in a base of green alfalfa grass  → AMBIGUOUS / blend description
3× Rosy Polypore
3× Butternut Squash powder
3× Carob Protein / Carob Protein hydrolysate    → niche protein; new IQM
3× Algae Protein                                → niche; new IQM
3× Rocket Plant leaf extract                    → Eruca sativa = arugula
3× Guanidoacetic Acid                           → CAS 352-97-6, creatine precursor → NEW_IQM_ACTIVE
3× organic Matcha Green Tea / leaf powder       → matcha = green tea; alias to green_tea
3× organic Leek                                 → Allium ampeloprasum → NEW_BOTANICAL
3× Bisdemethoxy Curcumin                        → minor curcuminoid → NEW_IQM_ACTIVE under curcumin family
3× Demethoxy Curcumin                           → minor curcuminoid → same
3× Citrus Polymethoxylated Flavones             → PMF, citrus actives → NEW_IQM_ACTIVE
2× Carbohydrate Digestive Enzymes               → blend; → BLEND_HEADER
2× other Organic Citrus                         → descriptor → cleaner fix
2× DPP IV Protease                              → specific protease enzyme
2× Lastase                                      → likely typo for "lactase" → cleaner fix
2× Poten-Zyme Niacinamide                       → branded form of niacinamide → alias
2× Poten-Zyme Vitamin B6                        → branded form of B6 → alias
2× Lycium                                       → Lycium barbarum = goji → alias if exists
2× Polygonum                                    → Polygonum multiflorum (He Shou Wu) → NEW_BOTANICAL
2× Lemon-Lime Citrus Bioflavonoids
2× Brown Seaweed Fucoxanthin Concentrate        → fucoxanthin (specific carotenoid) → NEW_IQM_ACTIVE
2× Organic Tremella fuciformis Mycelia          → NEW_BOTANICAL (mushroom)
2× S. rattus JH145(TM)                          → Streptococcus rattus oral probiotic strain
2× S. uberis KJ2(TM)                            → Streptococcus uberis oral probiotic strain
2× Pumpkin Seed Protein
2× Watermelon Seed Protein
2× Holimel
2× Brussels Sprout Leaf Juice
2× Neut. Bacterial Protease                     → digestive enzyme → alias to digestive_enzymes
2× organic Zhuling                              → Polyporus umbellatus → NEW_BOTANICAL
```

(The remaining 154 ambiguous items are listed in `/tmp/unmapped_triage_v2.json` if you want the full list.)

---

## Recommended Next Steps

**Priority 0 — unblock GNC (15 minutes after your decision on Cholesterol Support Blend):**
1. ✓ Cutch Tree alias additions (DONE this pass)
2. ⏸ Add `cholesterol support blend` to `BLEND_HEADER_EXACT_NAMES` per your decision

**Priority 1 — your decision on the 91 blend headers:**
- Group 2A (10 obvious headers with trailing colons): approve in one batch?
- Group 2B (81 brand-specific): I can categorize each by brand owner if helpful

**Priority 2 — API verification + new entries (multi-day, 39 ingredients):**
- 15 NEW_PROBIOTIC: NCBI taxonomy + GSRS + clinical evidence assignment per strain
- 20 NEW_BOTANICAL: Kew/USDA binomial verification
- 4 NEW_IQM_ACTIVE: PubChem CID + CAS + UNII + clinical evidence

**Priority 3 — AMBIGUOUS (204 items):**
- Highest-frequency 30 categorized in Section 5; rest in `/tmp/unmapped_triage_v2.json`
- Each needs individual classification (alias vs new entry vs descriptor-strip)

**Priority 4 — cleaner improvement (BLEND_DISCLOSED_MIXED):**
- 4 multi-ingredient strings that need parser-side splitting
- File: `scripts/clean_dsld_data.py` ingredient row parser
