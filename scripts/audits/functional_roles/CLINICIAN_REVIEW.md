# Functional Roles — Clinician Review

**Reviewer:** Dr Pham
**Prepared:** 2026-04-30
**Scope:** Sign off on the controlled vocabulary of "functional roles" for excipients/inactive ingredients shown to PharmaGuide app users.
**Time estimate:** 60–90 min for full review.

---

## Why this review matters

Today, our app shows users a list like:

> *Other ingredients: magnesium stearate, silicon dioxide, microcrystalline cellulose, hypromellose...*

Users have no idea what those do. We want to show next to each one a chip like **"Lubricant"** or **"Coating"** that they can tap to read a one-sentence plain-English description with a regulatory reference.

To make this work we need:

1. **A locked vocabulary** of role IDs (proposed: 30 roles aligned with FDA 21 CFR 170.3(o) + EU E-numbers)
2. **Plain-language `notes` (≤200 chars)** for each role — what users will actually read
3. **A canonical mapping** from our existing 21 + 241 + 226 distinct category strings down to ~30 controlled values (existing data is full of duplicates and free-text proliferation that needs cleanup)
4. **A backfill plan per ingredient** — every entry gets `functional_roles: string[]` (multi-valued — acacia gum is genuinely fiber + binder + emulsifier + stabilizer)

Your sign-off here unlocks 22 backfill batches, 5,718+ regression tests pinned, and the final `coverage_gate.py` enforcement that gets us to **100% accuracy** before this ships.

---

## How to review

For each section, mark each row **`✓ APPROVE`**, **`✏️ EDIT — <your text>`**, or **`✗ REJECT`**. Free-text comments anywhere are welcome.

**Important:** the "5% gray area" section at the end is where we need your clinical judgment most — those are the ingredients GSRS / CFR can't auto-classify.

---

## Section 1 — Vocabulary review (30 roles)

Lean schema per role: `id` (stable), `name` (chip label), `notes` (≤200 char user copy), `regulatory_references[]`, `examples[]`. Source: `scripts/data/functional_roles_vocab.json`.

### 1A. Tablet/capsule mechanics (5)

| ID | Name | Proposed `notes` (user-facing) | Verdict |
|---|---|---|---|
| `binder` | Binder | Holds tablet ingredients together so the pill stays intact during handling and shipping. | |
| `disintegrant` | Disintegrant | Helps the tablet break apart in the stomach so the active ingredients can be absorbed. | |
| `lubricant` | Lubricant | Keeps powder from sticking to the tablet press during manufacturing. Inert in the body. | |
| `glidant` | Glidant | Improves powder flow during manufacturing so each tablet gets a consistent dose. | |
| `coating` | Coating | Outer film that makes capsules and tablets easier to swallow or protects them from stomach acid. | |

### 1B. Bulk / volume (1)

| ID | Name | Proposed `notes` | Verdict |
|---|---|---|---|
| `filler` | Filler | Adds bulk so a small dose can fit into a normal-sized tablet or capsule. | |

*Note: I collapsed `diluent` and `bulking_agent` into `filler` for V1 simplicity — they're functionally equivalent in the supplement context. **Should we split them?** ☐ Yes  ☐ No*

### 1C. Texture / structure (6)

| ID | Name | Proposed `notes` | Verdict |
|---|---|---|---|
| `emulsifier` | Emulsifier | Lets oil and water mix so the formula stays uniform — common in liquid and gel supplements. | |
| `surfactant` | Surfactant | Lowers surface tension to help ingredients dissolve and disperse evenly in liquid. | |
| `thickener` | Thickener | Increases viscosity — used in syrups, gummies, and gel caps for the right texture. | |
| `stabilizer` | Stabilizer | Keeps the formula from separating, settling, or losing potency over the product's shelf life. | |
| `gelling_agent` | Gelling Agent | Forms gels — the structural ingredient in soft-gel capsule shells and gummies. | |
| `humectant` | Humectant | Holds moisture in — keeps soft-gel capsules and gummies from drying out and cracking. | |

### 1D. Preservation (2)

| ID | Name | Proposed `notes` | Verdict |
|---|---|---|---|
| `preservative` | Preservative | Stops bacteria, yeast, and mold from growing in the product so it stays safe through its shelf life. | |
| `antioxidant` | Antioxidant | Prevents fats and oils in the product from going rancid, preserving freshness and potency. | |

*Note: I collapsed `antimicrobial` into `preservative` (clinician-relevant distinction is preservative-vs-antioxidant; antimicrobial is a subset of preservative). **OK to merge?** ☐ Yes  ☐ No*

### 1E. Sensory (5)

| ID | Name | Proposed `notes` | Verdict |
|---|---|---|---|
| `colorant_natural` | Natural Colorant | Color from a natural source — vegetable, mineral, or animal. Approved without certification testing. | |
| `colorant_artificial` | Artificial Colorant | Synthetic dye that requires FDA batch certification. Some users prefer to avoid these. | |
| `flavoring` | Flavoring | Provides taste. May be 'natural flavor' (plant/animal-derived) or 'artificial flavor' (synthesized). | |
| `flavor_enhancer` | Flavor Enhancer | Strengthens or balances existing flavors — adds little taste of its own. | |

*Should `flavoring` split into `flavor_natural` and `flavor_artificial` like colorants do? ☐ Yes (split)  ☐ No (keep one)*

### 1F. Sweeteners (3)

| ID | Name | Proposed `notes` | Verdict |
|---|---|---|---|
| `sweetener_natural` | Natural Sweetener | Caloric sweetener from a natural source — provides sweetness and energy. | |
| `sweetener_artificial` | Artificial Sweetener | Zero- or low-calorie synthetic sweetener. Hundreds of times sweeter than sugar by weight. | |
| `sweetener_sugar_alcohol` | Sugar Alcohol | Lower-calorie sweetener (xylitol, erythritol, sorbitol). Can cause GI upset at high doses. | |

### 1G. Manufacturing aids (4)

| ID | Name | Proposed `notes` | Verdict |
|---|---|---|---|
| `anti_caking_agent` | Anti-Caking Agent | Prevents powders from clumping — keeps capsule contents free-flowing and easy to dose. | |
| `anti_foaming_agent` | Anti-Foaming Agent | Reduces foam during manufacturing — used in liquid and powder processing. | |
| `processing_aid` | Processing Aid | Used during manufacturing only — present in the final product at trace levels with no functional effect. | |
| `solvent` | Solvent | Liquid used to dissolve or extract other ingredients during manufacturing. | |

### 1H. Delivery / chemistry (4)

| ID | Name | Proposed `notes` | Verdict |
|---|---|---|---|
| `carrier_oil` | Carrier Oil | Edible oil that delivers fat-soluble actives (vitamins A/D/E/K, CoQ10, omega-3s) for absorption. | |
| `acidulant` | Acidulant | Adds tartness or lowers pH for taste, preservation, or absorption. | |
| `ph_regulator` | pH Regulator | Buffers the formula at a target pH — keeps actives stable and palatable. | |
| `propellant` | Propellant | Pressurizes spray and aerosol products. Rare in oral supplements; common in throat sprays. | |
| `glazing_agent` | Glazing Agent | Outer polish that gives tablets a shiny finish or seals capsules. Cosmetic/protective only. | |

### 1Z. Missing roles?

Anything important you'd add? Common candidates we considered and rejected (please overrule if needed):

- ☐ `chelating_agent` — usually folded into `preservative` (e.g., disodium EDTA). Keep separate?
- ☐ `enzyme` — when used as processing aid (e.g., pectinase). Keep distinct?
- ☐ `firming_agent` — FDA 21 CFR 170.3(o)(10), but rare in supplements. Skip?
- ☐ `sequestrant` — FDA 21 CFR 170.3(o)(26), overlaps with preservative/antioxidant. Skip?
- ☐ `texturizer` — FDA 21 CFR 170.3(o)(32), overlaps with thickener/gelling. Skip?

---

## Section 2 — Existing-category audit (your big concern)

The user flagged: **21 categories in `harmful_additives.json` may have duplicates; 241 categories in `other_ingredients.json` is way too many**. Both inputs feed the Flutter blob, so cleanup here is critical.

### 2A. `harmful_additives.json` category cleanup (115 entries → 21 distinct values)

Distribution and proposed canonicalization. **Confirm the right-hand column.**

| Current value | Count | Proposed canonical | Why | Verdict |
|---|---|---|---|---|
| `excipient` | 16 | `excipient` (keep) | Generic safety bucket for inactive add-ons | |
| `preservative` | 15 | `preservative` (keep) | Standard | |
| `emulsifier` | 12 | `emulsifier` (keep) | Standard | |
| `colorant_artificial` | 8 | `colorant_artificial` (keep) | Standard | |
| `sweetener` | 8 | **SPLIT** — re-assign each per-entry to `sweetener_natural` / `sweetener_artificial` / `sweetener_sugar_alcohol` | Generic "sweetener" doesn't differentiate user concern | |
| `sweetener_artificial` | 7 | `sweetener_artificial` (keep) | Standard | |
| `filler` | 7 | `filler` (keep) | Standard | |
| `contaminant` | 6 | `contaminant` (keep — safety category, NOT a functional role) | These shouldn't have `functional_roles[]` — they're not intentional | |
| `sweetener_sugar_alcohol` | 6 | `sweetener_sugar_alcohol` (keep) | Standard | |
| `fat_oil` | 5 | **MERGE → `carrier_oil`** | All 5 are oil carriers (canola, corn, etc.) | |
| `flavor` | 4 | **MERGE → `flavoring`** | Spelling normalization | |
| `preservative_antioxidant` | 4 | **SPLIT → `preservative` + `antioxidant`** (multi-valued) | BHA/BHT do both — array, not single value | |
| `processing_aid` | 3 | `processing_aid` (keep) | Standard | |
| `sweetener_natural` | 3 | `sweetener_natural` (keep) | Standard | |
| `colorant` | 2 | **REVIEW PER ENTRY** — Iron Oxide → `colorant_natural`; Candurin Silver → `colorant_artificial`(?) | Generic "colorant" is ambiguous | ☐ Confirm per-entry mapping |
| `colorant_natural` | 2 | `colorant_natural` (keep) | Standard | |
| `phosphate` | 2 | **REPLACE → `ph_regulator` + `chelating`(?)** | Phosphate is a chemical class, not a function | |
| `nutrient_synthetic` | 2 | **REVIEW** — does `Synthetic B Vitamins` belong here at all? | This isn't a functional role — these are nutrients, not excipients | ☐ Remove from `harmful_additives`? |
| `mineral_compound` | 1 | **REVIEW** — `Cupric Sulfate` — chemical class, not function. Re-categorize as `processing_aid`? | | |
| `stimulant_laxative` | 1 | **REVIEW** — `Senna` — this is an active ingredient, not a functional role | ☐ Move out of `harmful_additives`? | |
| `artificial_color` | 1 | **MERGE → `colorant_artificial`** | Spelling duplicate | |

**Net result after cleanup:** ~12 canonical category values for `harmful_additives` (down from 21):
`excipient`, `preservative`, `antioxidant`, `emulsifier`, `colorant_artificial`, `colorant_natural`, `sweetener_natural`, `sweetener_artificial`, `sweetener_sugar_alcohol`, `filler`, `flavoring`, `carrier_oil`, `processing_aid`, `contaminant`.

**Plus separately:** `functional_roles[]` array per entry (multi-valued — captures secondary roles).

### 2B. `other_ingredients.json` category cleanup (673 entries → 241 distinct values, **132 of which appear ONLY ONCE**)

This is where the proliferation problem is severe. Top 30 are reasonable; long-tail is mostly typos and over-specific buckets that should collapse.

**Top 30 categories — proposed mapping:**

| Current | Count | Proposed canonical | Verdict |
|---|---|---|---|
| `oil_carrier` | 34 | `carrier_oil` | |
| `flavor_natural` | 31 | `flavoring` (with `notes` flagging "natural") | |
| `emulsifier` | 22 | `emulsifier` | |
| `sweetener_natural` | 19 | `sweetener_natural` | |
| `colorant_natural` | 19 | `colorant_natural` | |
| `branded_botanical_complex` | 18 | **NOT a functional role** — keep as a separate `is_branded_complex: bool` flag; entry should also get `functional_roles[]` based on its actual function | ☐ Approve carve-out |
| `marketing_descriptor` | 17 | **NOT a functional role** — flag for retirement; these are label noise, not real ingredients | ☐ Approve retirement |
| `fiber_prebiotic` | 15 | `filler` (primary) + clinician-set `prebiotic_fiber_role`(?) | ☐ Add `prebiotic_fiber` as 31st role? |
| `descriptor_component` | 15 | **NOT a functional role** — retire | ☐ Approve retirement |
| `botanical_extract` | 14 | **NOT an excipient** — these are actives that got misfiled here | ☐ Move to active-ingredient pipeline? |
| `flavoring` | 13 | `flavoring` | |
| `source_descriptor` | 11 | **NOT a functional role** — retire | ☐ Approve retirement |
| `thickener_stabilizer` | 10 | **SPLIT** — assign both `thickener` and `stabilizer` to `functional_roles[]` | |
| `animal_glandular_tissue` | 10 | **NOT an excipient** — these are actives | ☐ Move to active pipeline? |
| `phytochemical_marker` | 9 | **NOT a functional role** — retire (these describe ingredients, not function) | |
| `branded_complex` | 9 | Same as `branded_botanical_complex` — flag, not role | |
| `coating` | 8 | `coating` | |
| `amino_acid_derivative` | 7 | **NOT an excipient** | ☐ Move? |
| `filler_binder` | 7 | **SPLIT** — `filler` + `binder` | |
| `filler` | 7 | `filler` | |
| `label_descriptor` | 6 | **NOT a functional role** — retire | |
| `solvent` | 6 | `solvent` | |
| `fruit_concentrate` | 6 | **NOT an excipient** — flavoring? active? Per-entry review | ☐ Per-entry |
| `colorant` | 6 | **REVIEW PER ENTRY** | ☐ |
| `processing_aid` | 5 | `processing_aid` | |
| `fiber_plant` | 5 | `filler` (or new `prebiotic_fiber` if approved above) | |
| `capsule_material` | 5 | `coating` + `gelling_agent` (gelatin = both) | |
| `acidity_regulator` | 5 | `ph_regulator` | |
| `glandular_tissue` | 4 | NOT an excipient | ☐ Move? |
| `functional_ingredient` | 4 | NOT an excipient — clinician review per entry | |

**Long-tail (132 categories appearing ONLY ONCE):** my proposal is **delete all 132** as a class and re-categorize each entry into the canonical vocab. Clinician spot-check a few:

- `binder_coating_thickener` → `binder` + `coating` + `thickener` (multi-role) ☐
- `filler_opacifier_colorant` → `filler` + `colorant_artificial` (multi-role) ☐
- `humectant_solvent` → `humectant` + `solvent` (multi-role) ☐
- `flow_agent_anticaking` → `glidant` + `anti_caking_agent` (multi-role) ☐
- `gelling_agent_natural` → `gelling_agent` ☐
- `coating_film_former` → `coating` ☐

**Net result after cleanup:** ~30 canonical category values for `other_ingredients` (down from 241), with secondary roles surfaced via the new multi-valued `functional_roles[]` field.

### 2C. `additive_type` field — drop entirely?

`other_ingredients.additive_type` has 226 distinct values (almost as proliferated as `category`). Examples of the problem:

- `descriptor` (73), `functional` (43), `natural_colorant` (26), `natural_flavor` (23), `bioactive_constituent` (20), `processing_aid` (20), `emulsifier` (19), `proprietary_complex` (16), …

**My recommendation:** drop `additive_type` entirely after Phase 4. It overlaps `category` poorly and `functional_roles[]` does the multi-valued job correctly.

**Clinician confirms:** ☐ Drop  ☐ Keep (please explain)

---

## Section 3 — Sample backfill (50 entries, evidence-attached)

The proposed `functional_roles[]` for representative entries spanning all role buckets. Each is seeded from existing `category`/`additive_type`/`common_uses` and verified against UNII + CFR sections via FDA GSRS.

### 3A. `harmful_additives.json` (15 sampled)

| Standard name | UNII | Existing `category` | Proposed `functional_roles[]` | Verdict |
|---|---|---|---|---|
| Acesulfame Potassium (Ace-K) | 23OV73Q5G9 | sweetener_artificial | `["sweetener_artificial"]` | |
| FD&C Blue No. 1 | H3R47K3TBD | colorant_artificial | `["colorant_artificial"]` | |
| Carrageenan | 5C69YCD2YJ | emulsifier | `["emulsifier", "thickener", "gelling_agent", "stabilizer"]` (multi-role) | |
| Carboxymethylcellulose (CMC) | K679OBS311 | emulsifier | `["emulsifier", "thickener", "stabilizer"]` | |
| Calcium Disodium EDTA | 8U5D034955 | preservative | `["preservative"]` | |
| Cane Sugar | C151H8M554 | sweetener | `["sweetener_natural"]` | |
| Cane Molasses | LSU3YX0KZO | sweetener | `["sweetener_natural"]` | |
| Canola Oil (Refined) | N4G8379626 | fat_oil | `["carrier_oil"]` | |
| Maltol | 3A9RD92BS4 | flavor | `["flavoring", "flavor_enhancer"]` | |
| Erythritol | RA96B954X6 | sweetener_sugar_alcohol | `["sweetener_sugar_alcohol"]` | |
| BHA | REK4960K2U | preservative_antioxidant | `["preservative", "antioxidant"]` | |
| BHT | 1P9D0Z171K | preservative_antioxidant | `["preservative", "antioxidant"]` | |
| Cassava Dextrin (Tapioca Maltodextrin) | — | filler | `["filler"]` | |
| Tetrasodium Diphosphate | O352864B8Z | phosphate | `["ph_regulator", "preservative"]` | |
| Iron Oxide | 1K09F3G675 | colorant | `["colorant_natural"]` | |

### 3B. `other_ingredients.json` (35 sampled)

| Standard name | UNII | CFR sections | Existing `category` | `additive_type` | Proposed `functional_roles[]` | Verdict |
|---|---|---|---|---|---|---|
| Acacia Gum | 5C5403N26O | 21 CFR 184.1330 | fiber_prebiotic | natural_fiber | `["stabilizer", "thickener", "emulsifier", "filler"]` (Dr Pham: add `prebiotic_fiber` if we approve role 31?) | |
| Activated Carbon | 2P3VWU3H10 | — | processing_aid | adsorbent | `["processing_aid"]` | |
| Agar | PFR724VXVV | — | thickener_stabilizer | gelling_agent | `["gelling_agent", "thickener", "stabilizer"]` | |
| Alcohol (Ethanol) | 3K9958V90M | 21 CFR 184.1293 | solvent | processing_aid | `["solvent", "preservative"]` | |
| Allulose | QCC18LNG3E | — | sweetener_natural | rare_sugar_sweetener | `["sweetener_natural"]` | |
| Apple Flavor | B423VGH5S9 | — | flavor_natural | natural_flavor | `["flavoring"]` | |
| Aqueous Film Coating | — | — | coating | film_coating | `["coating"]` | |
| Arrowroot | — | — | filler_binder | filler | `["filler", "binder"]` | |
| Beet Fiber | 3CK0EOO6FA | — | filler | filler | `["filler"]` | |
| Black Pepper Extract | KM66971LVF | — | botanical_extract | bioenhancer | **NOT excipient** — move to actives? | ☐ |
| Canola Lecithin | — | — | emulsifier | emulsifier | `["emulsifier"]` | |
| Cellulose Gum | K679OBS311 | 21 CFR 173.310 | thickener_stabilizer | texture_modifier | `["thickener", "stabilizer", "emulsifier"]` | |
| Chia Seed Meal | NU0OLX06F8 | — | filler_binder | seed_filler | `["filler", "binder"]` | |
| Cinnamon (Natural Flavoring) | 5S29HWU6QB | — | flavoring | spice_flavoring | `["flavoring"]` | |
| Decaglycerol Monolaurate | — | — | emulsifier | emulsifier | `["emulsifier", "surfactant"]` | |
| Deionized Water | — | — | solvent | processing_aid | `["solvent"]` | |
| FD&C Blue #1 | H3R47K3TBD | 21 CFR 74.101 | colorant | synthetic_colorant | `["colorant_artificial"]` | |
| Gelatin Capsule | 2G86QN327L | — | capsule_material | gelatin_capsule | `["coating", "gelling_agent"]` | |
| Kaolin | 24H4NWX5CO | 21 CFR 186.1256 | filler | mineral_filler | `["filler", "anti_caking_agent"]` | |
| Phosphoric Acid | E4GA8884NN | — | acidity_regulator | pH_adjuster | `["acidulant", "ph_regulator"]` | |
| Sodium Acid Sulfate | BU8V88OWIQ | — | acidity_regulator | buffering_agent | `["ph_regulator"]` | |
| Hypromellose (HPMC) | 3NXW29V3WO | 21 CFR 172.874 | capsule_material | capsule_shell | `["coating", "binder", "thickener"]` | |
| Magnesium Stearate | 70097M6I30 | 21 CFR 184.1440 | (not in OI; in HA) | — | `["lubricant", "anti_caking_agent"]` | |
| Microcrystalline Cellulose | OP1R32D61U | 21 CFR 182.1745 | filler | filler | `["filler", "binder"]` | |
| Silicon Dioxide | ETJ7Z6XBU4 | 21 CFR 172.480 | (varies) | (varies) | `["anti_caking_agent", "glidant"]` | |
| Sunflower Lecithin | 2222YL81N9 | — | emulsifier | emulsifier | `["emulsifier"]` | |
| Stearic Acid | 4ELV7Z65AP | 21 CFR 184.1090 | excipient | lubricant | `["lubricant"]` | |
| Polysorbate 80 | 6OZP39ZG8H | 21 CFR 172.840 | emulsifier | emulsifier | `["emulsifier", "surfactant"]` | |
| Glycerin | PDC6A3C0OX | 21 CFR 182.1320 | humectant | solvent | `["humectant", "solvent", "sweetener_sugar_alcohol"]` | |
| Annatto Extract | 6PQP1V1B6O | 21 CFR 73.30 | colorant_natural | natural_colorant | `["colorant_natural"]` | |
| Beeswax | 7G1J5DA97F | 21 CFR 184.1973 | coating | wax | `["glazing_agent", "coating"]` | |
| Carnauba Wax | R12CBM0EIZ | 21 CFR 184.1978 | coating | wax | `["glazing_agent", "coating"]` | |
| Shellac | 46N107B71O | 21 CFR 184.1090 | coating | resin | `["glazing_agent", "coating"]` | |
| Xanthan Gum | TTV12P4NEE | 21 CFR 172.695 | thickener_stabilizer | thickener | `["thickener", "stabilizer", "emulsifier"]` | |
| MCT Oil | — | — | oil_carrier | mct_carrier | `["carrier_oil"]` | |

---

## Section 4 — The 5% gray area (where we need your clinical judgment)

Entries where GSRS / CFR are silent or ambiguous. **Please fill in `functional_roles[]` for each.** If an entry doesn't belong in the inactives category at all (e.g. it's actually an active), mark **MOVE**.

### 4A. Multi-role botanicals where one role isn't in CFR

| Standard name | Existing classification | What we know | Your `functional_roles[]` |
|---|---|---|---|
| Acacia Gum | fiber_prebiotic | CFR lists as stabilizer/thickener/emulsifier; clinical lit also recognizes prebiotic role | |
| Inulin | fiber_prebiotic | Same — CFR silent on prebiotic | |
| FOS (Fructooligosaccharides) | fiber_prebiotic | Same | |
| Psyllium husk | fiber_plant | Bulk fiber + binder | |

**If you want a `prebiotic_fiber` role added (would make this a 31-role vocab), tick:** ☐ Yes  ☐ No (keep fiber under `filler`)

### 4B. Branded complexes (need disambiguation)

| Standard name | Existing classification | Question |
|---|---|---|
| BioCell Collagen Complex | branded_complex | Is this an active (collagen for joint support) or an excipient blend? My read: **active**, should not have functional_roles. | ☐ Active  ☐ Excipient |
| LactoSpore | branded_complex | Probiotic strain — **active**? | |
| Tonalin CLA | branded_complex | Active fatty acid? | |
| Verisol Collagen Peptides | branded_complex | Active | |

### 4C. Animal glandular tissue

10 entries categorized as `animal_glandular_tissue` (e.g., bovine adrenal, porcine pancreas). My read: these are actives, not excipients. **Confirm:** ☐ Move to actives  ☐ Keep here (and we'll need to invent a `glandular_extract` role)

### 4D. "Marketing descriptor" / "label_descriptor" / "source_descriptor" entries

~50 entries have categories like `marketing_descriptor`, `label_descriptor`, `descriptor_component` — these aren't real ingredients, they're label phrasing fragments (e.g. "Standardized to 50% Curcuminoids"). My recommendation: **retire from `other_ingredients.json` entirely**. These shouldn't render as chips in the UI.

**Confirm retirement:** ☐ Yes  ☐ No (I want to handle them how?)

### 4E. "Phytochemical_marker"

9 entries describing standardization markers (e.g., "≥95% piperine"), not ingredients. Same recommendation as 4D — **retire**. ☐ Yes  ☐ No

### 4F. Specific ambiguous individual entries

| Standard name | Question |
|---|---|
| Senna (currently in harmful_additives as `stimulant_laxative`) | This is an active laxative, not an excipient. Keep here for the safety penalty, OR move to actives? |
| Synthetic B Vitamins / Synthetic Vitamins (currently `nutrient_synthetic`) | These are nutrients, not excipients. Keep in `harmful_additives` for the synthetic-form flag, OR remove? |
| Cupric Sulfate (currently `mineral_compound`) | Chemical class, not function. Treat as `processing_aid` or remove? |
| Caramel Color | colorant_artificial OR colorant_natural? CFR allows both forms. Per-product, but default? |
| Activated Carbon | `processing_aid` only, or also `colorant`? (sometimes used as black pigment) |

---

## Section 5 — User-facing copy review

Every `notes` string above will be shown verbatim to non-clinicians. Please flag anything that is:

- Too clinical (jargon users won't understand)
- Misleading (overpromises safety or harm)
- Alarming when it shouldn't be (e.g., we don't want users panicking that *every* binder is bad)
- Underselling real concerns (e.g., artificial sweeteners' "some users prefer to avoid" — too soft? too strong?)

Free-text comments below per role-letter:

- 1A (mechanics): _______________________
- 1B (bulk): _______________________
- 1C (texture): _______________________
- 1D (preservation): _______________________
- 1E (sensory): _______________________
- 1F (sweeteners): _______________________
- 1G (manufacturing): _______________________
- 1H (delivery): _______________________

---

## Section 6 — Sign-off

After you've gone through Sections 1-5:

| Item | Approved? | Comments |
|---|---|---|
| 30-role vocabulary (Section 1) | ☐ | |
| `harmful_additives` category cleanup (Section 2A) | ☐ | |
| `other_ingredients` category collapse (Section 2B) | ☐ | |
| Drop `additive_type` field (Section 2C) | ☐ | |
| Sample backfill mappings (Section 3) | ☐ | |
| 5% gray-area resolutions (Section 4) | ☐ | |
| User-facing copy (Section 5) | ☐ | |

**Reviewer signature / date:** _______________________

---

## Appendix — what happens after sign-off

1. We finalize `scripts/data/functional_roles_vocab.json` v1.0.0 (this exact file's lean schema, 5 fields per role)
2. We add `functional_roles: string[]` to all 3 reference data files; every entry starts empty
3. We run **22 backfill batches** (~40 entries each), atomic-commit, regression-tested per batch:
   - 3 batches for `harmful_additives.json`
   - 17 batches for `other_ingredients.json`
   - 2 batches for `botanical_ingredients.json`
4. Each batch ships `scripts/audits/functional_roles/batch_NN/research.md` with UNII/CFR evidence per entry
5. Final coverage gate: **every** shipping entry has at least one role from the controlled vocab. Anything missing fails the release.
6. Flutter team integrates: bundles the vocab JSON as an asset, renders chips per role with tap-to-read modal pulling from `notes` + `regulatory_references` + `examples`.

**Total estimated calendar:** 5–6 weeks from your sign-off to 100% coverage.

---

*Appendix files referenced:*
- `scripts/data/functional_roles_vocab.json` — the lean vocab (you can read raw JSON if helpful)
- `scripts/data/harmful_additives.json` — 115 entries to backfill
- `scripts/data/other_ingredients.json` — 673 entries to backfill
- `scripts/data/botanical_ingredients.json` — minor cleanup
- `/Users/seancheick/.claude/plans/golden-painting-umbrella.md` — full implementation plan
