# Batch 3 — `harmful_additives.json` entries 81-115 (final)

**Date:** 2026-04-30 | **Vocab:** v1.0.0 LOCKED
**Scope:** `ADD_SLIMSWEET` … `ADD_YELLOW6` (35 entries)

## Per-entry assignments

### Sweeteners (5)
| ID | Roles |
|---|---|
| ADD_SLIMSWEET | `["sweetener_natural"]` (branded monk fruit/erythritol blend) |
| ADD_SUCRALOSE | `["sweetener_artificial"]` |
| ADD_SUGAR_ALCOHOLS | `["sweetener_sugar_alcohol"]` |
| ADD_SYRUPS | `["sweetener_natural"]` |
| ADD_THAUMATIN | `["sweetener_natural"]` (high-intensity natural sweet protein, E957) |

### Sugar alcohols (2)
| ID | Roles | Note |
|---|---|---|
| ADD_SORBITOL | `["sweetener_sugar_alcohol", "humectant"]` | E420 — also functions as humectant in soft-gels and gummies |
| ADD_XYLITOL | `["sweetener_sugar_alcohol"]` |

### Colorants (4)
| ID | Roles |
|---|---|
| ADD_SODIUM_COPPER_CHLOROPHYLLIN | `["colorant_natural"]` (FDA 21 CFR 73.125) |
| ADD_UNSPECIFIED_COLORS | `["colorant_artificial"]` (default — generic "color added" without disclosure typically signals certified artificial) |
| ADD_YELLOW5 | `["colorant_artificial"]` |
| ADD_YELLOW6 | `["colorant_artificial"]` |

### Preservatives — single-role (4)
| ID | Roles |
|---|---|
| ADD_SODIUM_BENZOATE | `["preservative"]` |
| ADD_SODIUM_NITRATE | `["preservative"]` |
| ADD_SODIUM_NITRITE | `["preservative"]` |
| ADD_SORBIC_ACID | `["preservative"]` |

### Preservatives + antioxidants — sulfite family + synthetic antioxidants (5)
Sulfites are dual-function: antimicrobial + reducing/antioxidant.

| ID | Roles |
|---|---|
| ADD_SODIUM_METABISULFITE | `["preservative", "antioxidant"]` |
| ADD_SODIUM_SULFITE | `["preservative", "antioxidant"]` |
| ADD_SULFUR_DIOXIDE | `["preservative", "antioxidant"]` |
| ADD_SYNTHETIC_ANTIOXIDANTS | `["preservative", "antioxidant"]` |
| ADD_TBHQ | `["preservative", "antioxidant"]` (E319 phenolic antioxidant; FDA 21 CFR 172.185) |

### Phosphates → ph_regulator (3) per clinician 2A
Drop weak preservative claim — `phosphate` was a chemical class, not a function.

| ID | Roles |
|---|---|
| ADD_SODIUM_TRIPOLYPHOSPHATE | `["ph_regulator"]` |
| ADD_TETRASODIUM_DIPHOSPHATE | `["ph_regulator"]` |
| ADD_SODIUM_HEXAMETAPHOSPHATE | `["emulsifier", "ph_regulator"]` (this one IS a known emulsifier in dairy/protein systems) |

### pH regulators / processing (1)
| ID | Roles |
|---|---|
| ADD_SODIUM_ALUMINUM_PHOSPHATE | `["ph_regulator", "processing_aid"]` |

### Emulsifiers / surfactants (4)
| ID | Roles | Note |
|---|---|---|
| ADD_SODIUM_CASEINATE | `["emulsifier", "stabilizer"]` | Milk protein emulsifier |
| ADD_SODIUM_LAURYL_SULFATE | `["emulsifier", "surfactant"]` | SLS — anionic surfactant |
| ADD_SORBITAN_MONOSTEARATE | `["emulsifier", "surfactant"]` | Span 60; E491 |
| ADD_SOY_MONOGLYCERIDES | `["emulsifier"]` | E471 family |

### Lubricants / fillers (2)
| ID | Roles | Note |
|---|---|---|
| ADD_STEARIC_ACID | `["lubricant"]` | Clinician table 3B (other_ingredients section); FDA 21 CFR 184.1090 |
| ADD_TAPIOCA_FILLER | `["filler"]` | Refined tapioca starch — bulk filler |

### Flavorings (1)
| ID | Roles | Note |
|---|---|---|
| ADD_VANILLIN | `["flavor_artificial"]` | Default to artificial — entry exists in `harmful_additives` specifically because synthetic-source vanillin dominates the supplement market; products using natural vanilla extract are typically labeled distinctly |

### Deferred (4)

| ID | Why |
|---|---|
| ADD_TIN | Contaminant — heavy metal |
| ADD_SYNTHETIC_B_VITAMINS | Phase 4 move-to-actives — clinician 4F: "active-form quality belongs in IQ /25, not functional roles" |
| ADD_SYNTHETIC_VITAMINS | Same — actives, not excipients |
| ADD_TIME_SORB | Per-product source verification needed (branded sustained-release excipient covering multiple cellulose-based formulations) — V1.1 |

## Coverage summary

- Total in scope: **35**
- Roles assigned: **31**
- Deferred: **4** (1 contaminant + 2 nutrient_synthetic actives + 1 V1.1 branded)

After batch 3: **33+38+31 = 102/115 = 89% of `harmful_additives.json` populated.**

The remaining 13 entries (architecturally-deferred): 6 contaminants + 2 nutrient_synthetic actives + 4 V1.1-deferred (Caramel Color, Candurin Silver, Time-Sorb, Cupric Sulfate) + 1 Phase 4 move (Senna). All intentional `[]` per clinician decisions.

**`harmful_additives.json` Phase 3 backfill complete after this batch.**
