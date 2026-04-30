# Batch 2 — `harmful_additives.json` entries 41-80

**Date:** 2026-04-30 | **Vocab:** v1.0.0 LOCKED
**Scope:** `ADD_HYDROGENATED_COCONUT_OIL` … `ADD_SILICON_DIOXIDE` (alphabetical)

## Per-entry assignments (compact)

### Carrier oils (4)
| ID | Roles | Note |
|---|---|---|
| ADD_HYDROGENATED_COCONUT_OIL | `["carrier_oil"]` | Hydrogenated; trans-fat safety concern is B1 territory, not functional role |
| ADD_PALM_OIL | `["carrier_oil"]` | Refined edible oil |
| ADD_PARTIALLY_HYDROGENATED_CORN_OIL | `["carrier_oil"]` | Same — trans-fat safety captured separately |
| ADD_MINERAL_OIL | `["lubricant", "carrier_oil"]` | Petroleum-derived; both lubricates tablets and serves as inert carrier |

### Sugar alcohols (2)
| ID | Roles |
|---|---|
| ADD_HYDROGENATED_STARCH_HYDROLYSATE | `["sweetener_sugar_alcohol"]` |
| ADD_MALTITOL_MALITOL | `["sweetener_sugar_alcohol"]` |

### Sweeteners (3)
| ID | Roles | Note |
|---|---|---|
| ADD_ISOMALTOOLIGOSACCHARIDE | `["sweetener_natural", "prebiotic_fiber"]` | IMO has documented prebiotic effect (Hu 2020, Mizote 2016) |
| ADD_MALTOTAME | `["sweetener_artificial"]` | High-intensity artificial sweetener |
| ADD_NEOTAME | `["sweetener_artificial"]` | FDA 21 CFR 172.829 |
| ADD_PUREFRUIT_SELECT | `["sweetener_natural"]` | Branded monk fruit + stevia blend |
| ADD_SACCHARIN | `["sweetener_artificial"]` | E954 |

### Colorants (2)
| ID | Roles | Note |
|---|---|---|
| ADD_IRON_OXIDE | `["colorant_natural"]` | Clinician table 3A — mineral source, FDA 21 CFR 73.200 |
| ADD_RED40 | `["colorant_artificial"]` | FD&C Red No. 40 (21 CFR 74.340) |

### Preservatives — single-role (6)
| ID | Roles |
|---|---|
| ADD_METHYLPARABEN | `["preservative"]` |
| ADD_PROPYLPARABEN | `["preservative"]` |
| ADD_POTASSIUM_BENZOATE | `["preservative"]` |
| ADD_POTASSIUM_NITRATE | `["preservative"]` |
| ADD_POTASSIUM_NITRITE | `["preservative"]` |
| ADD_POTASSIUM_SORBATE | `["preservative"]` |

### pH regulators / processing (1)
| ID | Roles | Note |
|---|---|---|
| ADD_POTASSIUM_HYDROXIDE | `["ph_regulator", "processing_aid"]` | Strong base used to neutralize / adjust pH; FDA 21 CFR 184.1631 |

### Lubricants / Magnesium-family (3)
| ID | Roles | Note |
|---|---|---|
| ADD_MAGNESIUM_LAURATE | `["lubricant"]` | Calcium-soap analog |
| ADD_MAGNESIUM_CITRATE_LAURATE | `["lubricant"]` | Mixed Mg salt; lubricant family |
| ADD_MAGNESIUM_STEARATE | `["lubricant", "anti_caking_agent"]` | **Clinician spot-check** (Phase 5 verification); FDA 21 CFR 184.1440 |

### Tablet mechanics — fillers / binders (3)
| ID | Roles | Note |
|---|---|---|
| ADD_MICROCRYSTALLINE_CELLULOSE | `["filler", "binder"]` | **Clinician spot-check**; FDA 21 CFR 182.1745 |
| ADD_MALTODEXTRIN | `["filler"]` | Tablet bulking agent |
| ADD_MODIFIED_STARCH | `["filler", "binder", "thickener"]` | Modified food starch — multi-role |
| ADD_POLYDEXTROSE | `["filler"]` | Bulking agent / fiber filler |

### Tablet mechanics — binder / coating / glide (3)
| ID | Roles | Note |
|---|---|---|
| ADD_POLYVINYLPYRROLIDONE | `["binder"]` | PVP — the classic tablet binder; FDA 21 CFR 173.55 |
| ADD_SHELLAC | `["coating", "glazing_agent"]` | Both functions; FDA 21 CFR 184.1090 |
| ADD_SILICON_DIOXIDE | `["anti_caking_agent", "glidant"]` | **Clinician spot-check**; FDA 21 CFR 172.480 |

### Solvents / humectants (2)
| ID | Roles | Note |
|---|---|---|
| ADD_POLYETHYLENE_GLYCOL | `["solvent", "humectant"]` | PEG; FDA 21 CFR 172.820 |
| ADD_PROPYLENE_GLYCOL | `["solvent", "humectant"]` | FDA 21 CFR 184.1666 |

### Emulsifiers — Polysorbate family (4)
| ID | Roles |
|---|---|
| ADD_POLYSORBATE80 | `["emulsifier", "surfactant"]` |
| ADD_POLYSORBATE_20 | `["emulsifier", "surfactant"]` |
| ADD_POLYSORBATE_40 | `["emulsifier", "surfactant"]` |
| ADD_POLYSORBATE_65 | `["emulsifier", "surfactant"]` |

### Flavorings (2)
| ID | Roles | Note |
|---|---|---|
| ADD_MALTOL | `["flavor_natural", "flavor_enhancer"]` | Clinician table 3A — multi-role; sweet-taste enhancer |
| ADD_MSG | `["flavor_enhancer"]` | FDA 21 CFR 170.3(o)(11) — primary FDA functional class |

### Deferred (2)
| ID | Why |
|---|---|
| ADD_NICKEL | Contaminant — heavy metal; clinician Section 2A architectural exclusion |
| ADD_SENNA | Phase 4 move-to-actives (laxative drug, not excipient) per clinician Section 4F |

## Coverage summary

- Total in scope: **40**
- Roles assigned: **38**
- Deferred: **2** (1 contaminant + 1 Phase-4-actives)

After batch 2: **33+38 = 71/115 = 62% of `harmful_additives.json` populated.**
