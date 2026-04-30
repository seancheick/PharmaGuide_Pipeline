# Batch 1 — `harmful_additives.json` entries 1-40 (alphabetical by id)

**Date:** 2026-04-30
**Scope:** First 40 entries (`ADD_ACESULFAME_K` … `ADD_HFCS`)
**Vocab:** `data/functional_roles_vocab.json` v1.0.0 (LOCKED, 32 roles)
**Clinician basis:** `scripts/audits/functional_roles/CLINICIAN_REVIEW.md` Sections 2A, 3A, 4F

## Assignment rules applied

1. **Per clinician Section 2A:** `contaminant`-category entries get `functional_roles=[]` (unintended impurities, NOT functional ingredients)
2. **Multi-role splits per clinician table 3A:** `preservative_antioxidant` → `["preservative","antioxidant"]`; `fat_oil` → `["carrier_oil"]`; ambiguous `sweetener` (8 entries) → split per-entry by source
3. **Per-entry verification (no defaulting) per clinician Section 2A:** `colorant` and pearlescent mineral colorants verified case-by-case
4. **Deferred entries** (assigned `[]` for batch 1, with rationale below): Candurin Silver (per-product source verification), Caramel Color (V1.1 attribute layer for class i-iv disambiguation), Cupric Sulfate (Phase 4 move-to-actives)

## Per-entry assignments

### Sweeteners — artificial (3)

| ID | UNII | Roles | Evidence |
|---|---|---|---|
| ADD_ACESULFAME_K | 23OV73Q5G9 | `["sweetener_artificial"]` | E950; FDA approved as non-nutritive sweetener (21 CFR 172.800). Clinician table 3A. |
| ADD_ADVANTAME | 3ZA6810AWX | `["sweetener_artificial"]` | FDA-approved high-intensity sweetener (21 CFR 172.803). |
| ADD_ASPARTAME | Z0H242BBR1 | `["sweetener_artificial"]` | E951; FDA 21 CFR 172.804. |

### Sweeteners — natural / nutritive (5)

| ID | UNII | Roles | Evidence |
|---|---|---|---|
| ADD_CANE_SUGAR | C151H8M554 | `["sweetener_natural"]` | Sucrose; clinician table 3A. |
| ADD_CANE_MOLASSES | LSU3YX0KZO | `["sweetener_natural", "flavor_natural", "colorant_natural"]` | Multi-role per clinician table 3A — molasses serves as sweetener, dark color, and characteristic flavor. |
| ADD_DEXTROSE | 5SL0G7R0OK | `["sweetener_natural"]` | D-glucose; nutritive sweetener (21 CFR 184.1857). |
| ADD_FRUCTOSE | 6YSS42VSEV | `["sweetener_natural"]` | Levulose; nutritive sweetener (21 CFR 184.1866). |
| ADD_HFCS | XY6UN3QB6S | `["sweetener_natural"]` | High Fructose Corn Syrup; FDA classifies as natural-source nutritive sweetener (21 CFR 184.1866 reference). |
| ADD_D_MANNOSE | PHA4727WTP | `["sweetener_natural"]` | D-mannose is a monosaccharide; mildly sweet but qualifies as natural-source nutritive. |

### Sugar alcohol (1)

| ID | UNII | Roles | Evidence |
|---|---|---|---|
| ADD_ERYTHRITOL | RA96B954X6 | `["sweetener_sugar_alcohol"]` | Polyol sugar alcohol (21 CFR 184; E968). Clinician table 3A. |

### Colorants — artificial (4)

| ID | UNII | Roles | Evidence |
|---|---|---|---|
| ADD_BLUE1 | H3R47K3TBD | `["colorant_artificial"]` | FD&C Blue No. 1; certifiable color (21 CFR 74.101). Clinician table 3A. |
| ADD_BLUE2 | L06K8R7DQK | `["colorant_artificial"]` | FD&C Blue No. 2 (21 CFR 74.102). |
| ADD_GREEN3 | 9J3VQ0Y6BV | `["colorant_artificial"]` | FD&C Green No. 3 (21 CFR 74.203). |
| ADD_ALUMINUM_LAKE_GENERIC | — | `["colorant_artificial"]` | Aluminum Lakes are dye-on-substrate insoluble pigments used in tablet coatings; functionally artificial colorant. |

### Colorants — natural (1)

| ID | UNII | Roles | Evidence |
|---|---|---|---|
| ADD_CARMINE_RED | — | `["colorant_natural"]` | Cochineal extract; natural pigment (21 CFR 73.100). Allergen note carried separately. |

### Colorants — DEFERRED (2)

| ID | UNII | Roles | Why deferred |
|---|---|---|---|
| ADD_CANDURIN_SILVER | — | `[]` | Per clinician Section 2A: "Candurin is a brand name covering multiple formulations; mica-based pearlescent alone isn't a sufficient guarantee." Per-product source verification required before role assignment. |
| ADD_CARAMEL_COLOR | T9D99G2B1R | `[]` | Per clinician Section 4F: "No hard-coded default. Per-class data required: Class I/II unambiguously natural; Class III/IV contain 4-MEI byproduct (Prop 65)." Resolved in V1.1 via `attributes.caramel_class` enum + B1 safety logic. |

### Preservatives + antioxidants (4)

| ID | UNII | Roles | Evidence |
|---|---|---|---|
| ADD_BHA | REK4960K2U | `["preservative", "antioxidant"]` | Clinician table 3A — preservative_antioxidant split. FDA 21 CFR 172.110/184.1733. |
| ADD_BHT | 1P9D0Z171K | `["preservative", "antioxidant"]` | Clinician table 3A. FDA 21 CFR 172.115. |
| ADD_CALCIUM_DISODIUM_EDTA | 8U5D034955 | `["preservative", "antioxidant"]` | Clinician table 3A. Chelating-mode preservative folded per Section 1Z (chelating_agent excluded role; covered by preservative+antioxidant). FDA 21 CFR 172.120. |
| ADD_DISODIUM_EDTA | — | `["preservative", "antioxidant"]` | Same family/role as Calcium Disodium EDTA. 21 CFR 172.135. |

### Emulsifiers / multi-role hydrocolloids (3)

| ID | UNII | Roles | Evidence |
|---|---|---|---|
| ADD_CARBOXYMETHYLCELLULOSE | K679OBS311 | `["emulsifier", "thickener", "stabilizer"]` | CMC. Clinician table 3A. FDA 21 CFR 182.1745. |
| ADD_CARRAGEENAN | 5C69YCD2YJ | `["emulsifier", "thickener", "gelling_agent", "stabilizer"]` | Clinician table 3A — quad-role hydrocolloid. FDA 21 CFR 172.620. |
| ADD_FATTY_ACID_POLYGLYCEROL_ESTERS | — | `["emulsifier", "surfactant"]` | Polyglycerol esters of fatty acids (E475 family). Surface-active emulsifier. |

### Carrier oils (2)

| ID | UNII | Roles | Evidence |
|---|---|---|---|
| ADD_CANOLA_OIL | N4G8379626 | `["carrier_oil"]` | Clinician table 3A — fat_oil → carrier_oil. |
| ADD_CORN_OIL | 8470G57WFM | `["carrier_oil"]` | Same family as canola; refined edible oil used as fat-soluble vehicle. |

### Tablet/capsule mechanics — disintegrants (2)

| ID | UNII | Roles | Evidence |
|---|---|---|---|
| ADD_CROSCARMELLOSE_SODIUM | M28OL1HH48 | `["disintegrant"]` | Internally cross-linked sodium CMC; standard tablet super-disintegrant (USP-NF). |
| ADD_CROSPOVIDONE | 2S7830E561 | `["disintegrant"]` | Cross-linked PVP; standard super-disintegrant (USP-NF). |

### Tablet/capsule mechanics — lubricants / flow agents (5)

| ID | UNII | Roles | Evidence |
|---|---|---|---|
| ADD_CALCIUM_LAURATE | 0YIV695L8O | `["lubricant"]` | Calcium salt of lauric acid; same family as magnesium stearate (calcium soap). |
| ADD_CALCIUM_CITRATE_LAURATE | — | `["lubricant"]` | Mixed calcium salt; lubricant family. |
| ADD_CALCIUM_SILICATE | S4255P4G5M | `["anti_caking_agent", "glidant"]` | FDA 21 CFR 184.1191 — recognized GRAS flow agent and anti-caking. |
| ADD_CALCIUM_ALUMINUM_PHOSPHATE | — | `["processing_aid", "anti_caking_agent"]` | Used in tableting as a flow / anti-cake agent in some formulations. |

### Fillers / bulking (3)

| ID | UNII | Roles | Evidence |
|---|---|---|---|
| ADD_CASSAVA_DEXTRIN | — | `["filler"]` | Tapioca maltodextrin; clinician table 3A. |
| ADD_CORN_SYRUP_SOLIDS | 9G5L16BK6N | `["filler", "sweetener_natural"]` | Multi-role: serves as both bulk extender and sweetener at typical inclusion levels. |

### Flavorings — artificial (1)

| ID | UNII | Roles | Evidence |
|---|---|---|---|
| ADD_ARTIFICIAL_FLAVORS | — | `["flavor_artificial"]` | Per clinician Section 2A: `flavor` → `flavor_natural`/`flavor_artificial` per-entry. "Artificial Flavors" entry is unambiguously artificial. |

### Contaminants — `[]` per clinician Section 2A (5 entries)

These are unintended impurities (heavy-metal contamination, neoformed during processing, migration from packaging). They are **not** functional ingredients and **must not** receive `functional_roles[]`.

| ID | Why no roles |
|---|---|
| ADD_ACRYLAMIDE | Process-induced contaminant; IARC 2A; no functional role |
| ADD_ANTIMONY | Heavy metal contamination; no functional role |
| ADD_BISPHENOL_F | Packaging migration contaminant; no functional role |
| ADD_BISPHENOL_S | Packaging migration contaminant; no functional role |

### Deferred to Phase 4 (move-to-actives) — `[]` for batch 1

| ID | Why deferred |
|---|---|
| ADD_CUPRIC_SULFATE | Per clinician Section 4F: "Move to actives (copper source). Trace processing-level use of a specific product → that product's entry gets processing_aid." Phase 4 work — physical relocation out of harmful_additives. Batch 1 leaves entry-level `functional_roles=[]`. |

## Coverage summary for batch 1

- Total entries in scope: **40**
- Roles assigned: **33** (with ≥1 role)
- Deferred (intentional `[]`):
  - Contaminants: **4** (Acrylamide, Antimony, Bisphenol F, Bisphenol S)
  - V1.1-required disambiguation: **2** (Candurin Silver, Caramel Color)
  - Phase 4 move-to-actives: **1** (Cupric Sulfate)
  - Subtotal deferred: **7**

After batch 1: **33/115 = 29% of `harmful_additives.json` populated.**

The 9 deferred entries will be revisited:
- Contaminants → never (architectural; clinician explicitly excluded)
- V1.1 entries → resolved when `attributes.caramel_class` and per-product Candurin source verification land
- Cupric Sulfate → Phase 4 cleanup pass

## Verification checklist

- [x] Every assigned role is a member of the locked 32-ID vocab
- [x] No multi-role assignment exceeds 4 (Carrageenan = 4, max)
- [x] Contaminants assigned `[]`
- [x] Cane Molasses multi-role matches clinician's exact 3-tuple
- [x] BHA / BHT / EDTA-family preservative+antioxidant split applied
- [x] All `fat_oil` → `carrier_oil` rename applied
- [x] Disintegrants assigned (Croscarmellose Sodium, Crospovidone) — both recognized USP-NF super-disintegrants
- [x] Calcium Silicate's FDA GRAS flow-agent role (CFR 184.1191) reflected as `["anti_caking_agent","glidant"]`
