#!/usr/bin/env python3
"""Phase 2: Migrate digestive_enzymes umbrella into discrete canonical enzyme identities.

Applies:
1. Adds 9 discrete canonical entries to ingredient_quality_map.json:
   - lactase (CUI: C0083183, UNII: 37515NWH9U)
   - alpha_galactosidase (CUI: C0002268)
   - pancreatin (CUI: C0030304, UNII: 040L83973U)
   - protease (CUI: C5200997)
   - lipase (CUI: C0023764)
   - amylase (CUI: C0002712)
   - papain (CUI: C0030346, UNII: A236A06Y32)
   - cellulase (CUI: C0007641)
   - serrapeptase (CUI: C0074389, UNII: NL053ABE4J)
2. Prunes child aliases from digestive_enzymes in ingredient_quality_map.json
3. Restricts aliases of INGR_DIGESTIVE_ENZYMES in backed_clinical_studies.json
   (removes standalone lipase, protease, amylase, pancreatic enzymes)
4. Updates supplement_taxonomy.py _ENZYME_CANONICAL_IDS and natto-serra token mapping.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

def migrate():
    iqm_path = ROOT / "scripts" / "data" / "ingredient_quality_map.json"
    with open(iqm_path) as f:
        iqm = json.load(f)

    # 1. Update digestive_enzymes parent entry
    parent = iqm.get("digestive_enzymes")
    if not parent:
        raise RuntimeError("digestive_enzymes not found in IQM")

    # Prune child aliases from plant-based enzyme complex
    p_form = parent.get("forms", {}).get("plant-based enzyme complex", {})
    p_aliases = set(p_form.get("aliases", []))
    p_aliases -= {
        "DigeZyme", "Zygest Lactase enzyme", "Fungal Protease",
        "aspergillus protease", "protease (fungal)"
    }
    p_form["aliases"] = sorted(p_aliases)

    # Prune child aliases from pancreatic enzymes
    pan_form = parent.get("forms", {}).get("pancreatic enzymes (animal-derived)", {})
    pan_aliases = set(pan_form.get("aliases", []))
    pan_aliases -= {
        "pancreatic enzymes", "pancreatin", "animal enzymes", "porcine enzymes",
        "animal-derived enzymes", "pancreatic enzyme blend", "porcine pancreatin",
        "animal enzyme supplement", "pancreatin supplement", "pancreatic enzymes supplement",
        "animal enzymes supplement", "porcine enzymes supplement",
        "animal-derived enzymes supplement", "pancreatic enzyme blend supplement",
        "porcine pancreatin supplement", "pancreatin 4x", "pancreatin 8x",
        "pancreatin concentrate 4x", "pancreatin usp", "pancrelipase",
        "porcine pancreatic concentrate", "pancreatic concentrate", "pancreatin 10x",
        "pancreatic enzymes 11x", "full strength pancreatin", "Pancreatin 5X",
        "Porcine", "Sus scrofa Pancreas", "Bos taurus Pancreas", "porcine pancreas",
        "bovine pancreas", "pancreas, porcine", "pancreas, bovine"
    }
    pan_aliases.update([
        "pancreatic enzyme complex", "animal-derived pancreatic enzyme extract"
    ])
    pan_form["aliases"] = sorted(pan_aliases)

    # Prune child aliases from specific enzymes
    spec_form = parent.get("forms", {}).get("specific enzymes", {})
    spec_aliases = set(spec_form.get("aliases", []))
    spec_aliases -= {
        "protease", "acid protease", "neutral protease, bacterial", "neutral protease bacterial",
        "lipase", "amylase", "bromelain", "papain", "serrapeptase", "lactase",
        "cellulase", "hemicellulase", "invertase", "maltase", "alpha-galactosidase",
        "alpha galactosidase", "alpha-galactosidase enzyme", "alpha galactosidase enzyme",
        "aspergillopepsin", "aspergillopepsin enzyme", "aspergillus acid protease",
        "peptidase", "phytase", "trypsin", "chymotrypsin", "protein-digesting enzymes",
        "fat-digesting enzymes", "carbohydrate-digesting enzymes", "targeted digestive enzymes",
        "protease supplement", "lipase supplement", "amylase supplement",
        "bromelain supplement", "papain supplement", "serrapeptase supplement",
        "lactase supplement", "cellulase supplement", "hemicellulase supplement",
        "invertase supplement", "maltase supplement", "alpha-galactosidase supplement",
        "peptidase supplement", "phytase supplement", "trypsin supplement",
        "chymotrypsin supplement", "protein-digesting enzymes supplement",
        "fat-digesting enzymes supplement", "carbohydrate-digesting enzymes supplement",
        "Prohydrolase", "prohydrolase enzyme blend", "serratiopeptidase", "serratia peptidase",
        "protease 4.5", "protease 4.5 enzyme", "rennin", "sucrase", "protease, fungal",
        "tolerase g", "cellulase enzymes", "vegpeptase", "protease ii", "protease 2",
        "protease iii", "protease 3", "protease 1", "tolerase g prolyl endopeptidase",
        "serrazimes", "oxidase", "transglucosidase", "glucanase", "acid-stable protease",
        "acid stable protease", "Protease I", "ProteaseGL", "ProteaseCW", "cellulase enzyme"
    }
    spec_aliases.update([
        "targeted enzyme formula", "multi-enzyme formula"
    ])
    spec_form["aliases"] = sorted(spec_aliases)

    # 2. Add 9 discrete canonical entries
    new_entries = {
        "lactase": {
            "standard_name": "Lactase",
            "category": "enzymes",
            "cui": "C0083183",
            "forms": {
                "lactase": {
                    "bio_score": 10,
                    "natural": True,
                    "score": 13,
                    "absorption": "category_error (local action; activity-units metric)",
                    "consumer_note": "Lactase is a digestive enzyme that breaks down lactose, the sugar found in milk and dairy products. Its potency is measured in Acid Lactase Units (ALU).",
                    "consumer_note_review": {
                        "by": "Product owner approval",
                        "date": "2026-09-19"
                    },
                    "notes": "Beta-galactosidase enzyme that hydrolyzes lactose into glucose and galactose in the small intestine. Measured in Acid Lactase Units (ALU / FCC ALU).",
                    "aliases": [
                        "lactase", "lactase enzyme", "acid lactase", "beta-galactosidase",
                        "tilactase", "zygest lactase enzyme", "aspergillus oryzae lactase",
                        "dairy digestive enzymes", "dairy-digesting enzyme", "lactase supplement"
                    ],
                    "dosage_importance": 1.0,
                    "absorption_structured": {
                        "value": None,
                        "range_low": None,
                        "range_high": None,
                        "quality": "unknown"
                    },
                    "unii": "37515NWH9U"
                }
            }
        },
        "alpha_galactosidase": {
            "standard_name": "Alpha-Galactosidase",
            "category": "enzymes",
            "cui": "C0002268",
            "forms": {
                "alpha-galactosidase": {
                    "bio_score": 10,
                    "natural": True,
                    "score": 13,
                    "absorption": "category_error (local action; activity-units metric)",
                    "consumer_note": "Alpha-galactosidase is an enzyme that helps break down complex carbohydrates in beans, legumes, and cruciferous vegetables. Measured in GaLU units.",
                    "consumer_note_review": {
                        "by": "Product owner approval",
                        "date": "2026-09-19"
                    },
                    "notes": "Alpha-D-galactosidase enzyme derived from Aspergillus niger that hydrolyzes alpha-1,6-galactosyl bonds in oligosaccharides (raffinose, stachyose, verbascose) found in legumes and cruciferous vegetables. Measured in Galactosidase Activity Units (GaLU / GALU).",
                    "aliases": [
                        "alpha-galactosidase", "alpha galactosidase", "alpha-galactosidase enzyme",
                        "alpha galactosidase enzyme", "alpha-d-galactosidase",
                        "aspergillus niger alpha-galactosidase", "alpha-galactosidase supplement"
                    ],
                    "dosage_importance": 1.0,
                    "absorption_structured": {
                        "value": None,
                        "range_low": None,
                        "range_high": None,
                        "quality": "unknown"
                    }
                }
            }
        },
        "pancreatin": {
            "standard_name": "Pancreatin",
            "category": "enzymes",
            "cui": "C0030304",
            "forms": {
                "pancreatin (porcine/bovine)": {
                    "bio_score": 11,
                    "natural": True,
                    "score": 14,
                    "absorption": "category_error (local action; activity-units metric)",
                    "consumer_note": "Pancreatin is an animal-derived pancreatic enzyme extract containing natural protease, amylase, and lipase. Measured in USP units.",
                    "consumer_note_review": {
                        "by": "Product owner approval",
                        "date": "2026-09-19"
                    },
                    "notes": "Standardized porcine or bovine pancreatic enzyme mixture containing lipase, protease, and amylase. Standardized to USP activity units (e.g. 4X, 8X, 10X concentration). Animal-derived (non-vegetarian/vegan; non-halal/kosher unless certified).",
                    "aliases": [
                        "pancreatin", "pancrelipase", "porcine pancreatin", "bovine pancreatin",
                        "pancreatin 4x", "pancreatin 8x", "pancreatin 10x", "pancreatin usp",
                        "pancreatic enzymes", "pancreatin concentrate 4x", "full strength pancreatin",
                        "porcine pancreatic concentrate", "pancreatic concentrate", "pancreatin 5x",
                        "pancreatic enzymes 11x", "porcine pancreas", "bovine pancreas",
                        "sus scrofa pancreas", "bos taurus pancreas", "pancreas, porcine",
                        "pancreas, bovine", "pancreatin supplement", "pancreatic enzymes supplement"
                    ],
                    "dosage_importance": 1.0,
                    "absorption_structured": {
                        "value": None,
                        "range_low": None,
                        "range_high": None,
                        "quality": "unknown"
                    },
                    "unii": "040L83973U"
                }
            }
        },
        "protease": {
            "standard_name": "Protease",
            "category": "enzymes",
            "cui": "C5200997",
            "forms": {
                "protease (fungal/bacterial)": {
                    "bio_score": 10,
                    "natural": True,
                    "score": 13,
                    "absorption": "category_error (local action; activity-units metric)",
                    "consumer_note": "Protease is a digestive enzyme that helps break down dietary proteins into peptides and amino acids. Potency is measured in HUT activity units.",
                    "consumer_note_review": {
                        "by": "Product owner approval",
                        "date": "2026-09-19"
                    },
                    "notes": "Functional class of proteolytic enzymes (peptidases) from fungal (Aspergillus) or bacterial (Bacillus) sources that cleave peptide bonds. Measured in Hemoglobin Units on the Tyrosine basis (HUT) or SAPU. Functional class, not a single chemical substance.",
                    "aliases": [
                        "protease", "proteases", "fungal protease", "protease (fungal)",
                        "aspergillus protease", "acid protease", "neutral protease, bacterial",
                        "neutral protease bacterial", "peptidase", "protease 4.5", "protease 6.0",
                        "protease 6", "protease 3.0", "protease 3", "protease 4.5 enzyme",
                        "protease, bacterial", "protease ii", "protease 2", "protease iii",
                        "protease 1", "aspergillopepsin", "aspergillopepsin enzyme",
                        "aspergillus acid protease", "protein-digesting enzymes", "vegpeptase",
                        "acid-stable protease", "acid stable protease", "protease i",
                        "proteasegl", "proteasecw", "protease supplement", "peptidase supplement",
                        "protein-digesting enzymes supplement", "rennin", "trypsin",
                        "chymotrypsin", "trypsin supplement", "chymotrypsin supplement",
                        "prohydrolase", "prohydrolase enzyme blend", "tolerase g"
                    ],
                    "dosage_importance": 1.0,
                    "absorption_structured": {
                        "value": None,
                        "range_low": None,
                        "range_high": None,
                        "quality": "unknown"
                    }
                }
            }
        },
        "lipase": {
            "standard_name": "Lipase",
            "category": "enzymes",
            "cui": "C0023764",
            "forms": {
                "lipase": {
                    "bio_score": 10,
                    "natural": True,
                    "score": 13,
                    "absorption": "category_error (local action; activity-units metric)",
                    "consumer_note": "Lipase is a digestive enzyme that breaks down fats and triglycerides into fatty acids and glycerol. Potency is measured in FIP activity units.",
                    "consumer_note_review": {
                        "by": "Product owner approval",
                        "date": "2026-09-19"
                    },
                    "notes": "Functional class of lipid-hydrolyzing enzymes from fungal (Candida rugosa, Aspergillus niger, Rhizopus oryzae) or animal sources that hydrolyze dietary triglycerides into free fatty acids and glycerol. Measured in FIP or LU units. Functional class, not a single substance.",
                    "aliases": [
                        "lipase", "fungal lipase", "lipase enzyme", "fat-digesting enzymes",
                        "aspergillus lipase", "candida lipase", "rhizopus lipase",
                        "lipase supplement", "fat-digesting enzymes supplement"
                    ],
                    "dosage_importance": 1.0,
                    "absorption_structured": {
                        "value": None,
                        "range_low": None,
                        "range_high": None,
                        "quality": "unknown"
                    }
                }
            }
        },
        "amylase": {
            "standard_name": "Amylase",
            "category": "enzymes",
            "cui": "C0002712",
            "forms": {
                "amylase": {
                    "bio_score": 10,
                    "natural": True,
                    "score": 13,
                    "absorption": "category_error (local action; activity-units metric)",
                    "consumer_note": "Amylase is a digestive enzyme that breaks down starches and carbohydrates into simple sugars. Potency is measured in DU activity units.",
                    "consumer_note_review": {
                        "by": "Product owner approval",
                        "date": "2026-09-19"
                    },
                    "notes": "Functional class of carbohydrate-hydrolyzing enzymes (alpha-amylase, glucoamylase, diastase) from fungal (Aspergillus oryzae) or plant sources that hydrolyze starch into maltose and glucose. Measured in Dextrinizing Units (DU) or SKB. Functional class, not a single substance.",
                    "aliases": [
                        "amylase", "alpha-amylase", "alpha amylase", "fungal amylase",
                        "glucoamylase", "diastase", "carbohydrate-digesting enzymes",
                        "aspergillus amylase", "amylase supplement",
                        "carbohydrate-digesting enzymes supplement"
                    ],
                    "dosage_importance": 1.0,
                    "absorption_structured": {
                        "value": None,
                        "range_low": None,
                        "range_high": None,
                        "quality": "unknown"
                    }
                }
            }
        },
        "papain": {
            "standard_name": "Papain",
            "category": "enzymes",
            "cui": "C0030346",
            "forms": {
                "papain": {
                    "bio_score": 10,
                    "natural": True,
                    "score": 13,
                    "absorption": "category_error (local action; activity-units metric)",
                    "consumer_note": "Papain is a plant-derived digestive enzyme extracted from papaya fruit that helps break down proteins. Measured in PU or USP units.",
                    "consumer_note_review": {
                        "by": "Product owner approval",
                        "date": "2026-09-19"
                    },
                    "notes": "Cysteine endopeptidase isolated from the latex of Carica papaya (papaya). Hydrolyzes peptide bonds. Measured in Papain Units (PU) or USP units. Potential latex-fruit syndrome cross-reactivity in allergic individuals.",
                    "aliases": [
                        "papain", "papain enzyme", "papaya enzyme", "carica papaya enzyme",
                        "papaya peptidase", "papaya protease", "papain supplement"
                    ],
                    "dosage_importance": 1.0,
                    "absorption_structured": {
                        "value": None,
                        "range_low": None,
                        "range_high": None,
                        "quality": "unknown"
                    },
                    "unii": "A236A06Y32"
                }
            }
        },
        "cellulase": {
            "standard_name": "Cellulase",
            "category": "enzymes",
            "cui": "C0007641",
            "forms": {
                "cellulase": {
                    "bio_score": 10,
                    "natural": True,
                    "score": 13,
                    "absorption": "category_error (local action; activity-units metric)",
                    "consumer_note": "Cellulase is an enzyme that helps break down plant cellulose and dietary fibers. Measured in CU activity units.",
                    "consumer_note_review": {
                        "by": "Product owner approval",
                        "date": "2026-09-19"
                    },
                    "notes": "Functional class of fiber-cleaving enzymes (cellulase, hemicellulase, beta-glucanase, xylanase, pectinase) from Trichoderma or Aspergillus that hydrolyze beta-1,4-glycosidic bonds in plant fibers and cellulose. Measured in Cellulase Units (CU). Humans do not produce endogenous cellulase.",
                    "aliases": [
                        "cellulase", "cellulase enzymes", "cellulase enzyme", "hemicellulase",
                        "hemicellulase enzyme", "beta-glucanase", "pectinase", "xylanase",
                        "invertase", "maltase", "phytase", "cellulase supplement",
                        "hemicellulase supplement", "invertase supplement", "maltase supplement",
                        "phytase supplement", "sucrase"
                    ],
                    "dosage_importance": 1.0,
                    "absorption_structured": {
                        "value": None,
                        "range_low": None,
                        "range_high": None,
                        "quality": "unknown"
                    }
                }
            }
        },
        "serrapeptase": {
            "standard_name": "Serrapeptase",
            "category": "enzymes",
            "cui": "C0074389",
            "forms": {
                "serrapeptase": {
                    "bio_score": 10,
                    "natural": True,
                    "score": 13,
                    "absorption": "category_error (local action; activity-units metric)",
                    "consumer_note": "Serrapeptase (serratiopeptidase) is a systemic enzyme derived from Serratia bacteria, commonly taken on an empty stomach for joint and tissue support. It is not a digestive enzyme. Potency is measured in SPU.",
                    "consumer_note_review": {
                        "by": "Product owner approval",
                        "date": "2026-09-19"
                    },
                    "notes": "Systemic proteolytic/fibrinolytic metalloprotease isolated from the non-pathogenic enterobacterium Serratia marcescens (strain E-15). Cleaves non-living tissue and fibrin. Systemic action, NOT a digestive enzyme. Measured in Serrapeptase Units (SPU). Decoupled from digestive taxonomy.",
                    "aliases": [
                        "serrapeptase", "serratiopeptidase", "serratia peptidase",
                        "serrapeptase supplement", "serrazimes"
                    ],
                    "dosage_importance": 1.0,
                    "absorption_structured": {
                        "value": None,
                        "range_low": None,
                        "range_high": None,
                        "quality": "unknown"
                    },
                    "unii": "NL053ABE4J"
                }
            }
        }
    }

    for k, v in new_entries.items():
        iqm[k] = v

    # Update metadata count
    content_keys = [k for k in iqm.keys() if k != "_metadata"]
    iqm["_metadata"]["total_entries"] = len(content_keys)

    with open(iqm_path, "w", encoding="utf-8") as f:
        json.dump(iqm, f, indent=2, ensure_ascii=False)
    print(f"Updated IQM: added {len(new_entries)} entries; new total_entries={len(content_keys)}")

    # 3. Update backed_clinical_studies.json
    bcs_path = ROOT / "scripts" / "data" / "backed_clinical_studies.json"
    with open(bcs_path) as f:
        bcs = json.load(f)

    studies = bcs.get("backed_clinical_studies", [])
    for s in studies:
        if s.get("id") == "INGR_DIGESTIVE_ENZYMES":
            # Remove generic individual enzyme aliases
            s["aliases"] = [
                "digestive enzyme complex",
                "multi-enzyme blend",
                "fungal multi-enzyme complex"
            ]
            s["notes"] = (
                "Placebo-controlled functional dyspepsia trial (PMID 37976892) evaluated an "
                "unbranded five-enzyme fungal fermentation formulation (amylase, protease, cellulase, "
                "lactase, lipase; 200 mg BID). Does not transfer to standalone protease, lipase, "
                "amylase, cellulase, or animal pancreatin."
            )
            s["notable_studies"] = (
                "One placebo-controlled dyspepsia trial (PMID 37976892) evaluated an unbranded "
                "five-enzyme fungal formulation in functional dyspepsia. Applicability requires "
                "matching multi-enzyme fungal formulation facts; standalone discrete enzymes do not "
                "inherit this evidence."
            )
            print("Updated INGR_DIGESTIVE_ENZYMES in backed_clinical_studies.json")
            break

    with open(bcs_path, "w", encoding="utf-8") as f:
        json.dump(bcs, f, indent=2, ensure_ascii=False)

    # 4. Update supplement_taxonomy.py
    tax_path = ROOT / "scripts" / "supplement_taxonomy.py"
    tax_text = tax_path.read_text(encoding="utf-8")

    # Update _ENZYME_CANONICAL_IDS
    old_enzyme_ids = (
        '    "digestive_enzymes", "pepsin",\n'
        '    "protease", "amylase", "lipase", "bromelain", "papain",'
    )
    new_enzyme_ids = (
        '    "digestive_enzymes", "pepsin",\n'
        '    "protease", "amylase", "lipase", "bromelain", "papain",\n'
        '    "lactase", "alpha_galactosidase", "pancreatin", "cellulase",'
    )
    if old_enzyme_ids in tax_text:
        tax_text = tax_text.replace(old_enzyme_ids, new_enzyme_ids)
        print("Updated _ENZYME_CANONICAL_IDS in supplement_taxonomy.py")

    # Update natto-serra in enzyme_name_map
    old_natto_serra = '"natto-serra": "digestive_enzymes"'
    new_natto_serra = '"natto-serra": "serrapeptase"'
    if old_natto_serra in tax_text:
        tax_text = tax_text.replace(old_natto_serra, new_natto_serra)
        print("Updated natto-serra mapping in supplement_taxonomy.py")

    tax_path.write_text(tax_text, encoding="utf-8")
    print("Migration complete.")

if __name__ == "__main__":
    migrate()
