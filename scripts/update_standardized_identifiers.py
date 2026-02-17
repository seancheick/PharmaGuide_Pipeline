#!/usr/bin/env python3
"""
Update standardized identifiers (UMLS CUI, PubChem CID, CAS, UNII) in banned_recalled_ingredients.json.

These identifiers were researched from authoritative sources:
- UMLS Metathesaurus (NLM)
- PubChem (NCBI)
- FDA UNII database
- Chemical Abstract Service (CAS)

For recalled products (entity_type: "product"), CUI doesn't apply as these are
product names, not chemical substances.
"""

import json
import os
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
BANNED_FILE = os.path.join(DATA_DIR, 'banned_recalled_ingredients.json')

# Researched identifiers from authoritative sources
# Format: id -> {identifier_type: value}
IDENTIFIER_UPDATES = {
    # Delta-8-THC - Found CUI from NCI Thesaurus/UMLS
    # Source: https://ncit.nci.nih.gov/ncitbrowser/ConceptReport.jsp?dictionary=NCI+Thesaurus&code=C61312
    "BANNED_DELTA8_THC": {
        "CUI": "C0057341",
        "pubchem_cid": "638026",
        "cas_number": "5957-75-5",
        "nci_thesaurus_code": "C61312"
    },

    # Anatabine - Tobacco alkaloid
    # Source: https://pubchem.ncbi.nlm.nih.gov/compound/Anatabine
    "BANNED_ADD_ANATABINE": {
        "pubchem_cid": "11388",
        "cas_number": "581-49-7",
        "identifier_note": "No UMLS CUI found; minor tobacco alkaloid"
    },

    # IGF-1 LR3 - Synthetic peptide
    # Source: https://precision.fda.gov/uniisearch/srs/unii/M9L22Y19H9
    "BANNED_IGF1_LR3": {
        "cas_number": "946870-92-4",
        "unii": "M9L22Y19H9",
        "identifier_note": "Synthetic peptide; no UMLS CUI assigned"
    },

    # Citrus Red 2 - Food dye
    # Source: https://pubchem.ncbi.nlm.nih.gov/compound/Citrus-red-2
    "BANNED_ADD_CITRUS_RED_2": {
        "pubchem_cid": "22830",
        "cas_number": "6358-53-8",
        "identifier_note": "IARC Group 2B carcinogen; FDA phase-out planned"
    },

    # Orange B - Food dye
    # Source: https://en.wikipedia.org/wiki/Orange_B
    "BANNED_ADD_ORANGE_B": {
        "cas_number": "15139-76-1",
        "identifier_note": "Not certified since 1978; FDA revocation proposed"
    },

    # SARMs - Novel research chemicals without UMLS CUIs
    # Source: PubChem and chemical suppliers
    "BANNED_S23": {
        "pubchem_cid": "24892822",
        "cas_number": "1010396-29-8",
        "identifier_note": "Novel SARM; no UMLS CUI assigned"
    },
    "BANNED_SR9009": {
        "pubchem_cid": "57394020",
        "cas_number": "1379686-30-2",
        "identifier_note": "Rev-ErbA agonist (not actually a SARM); no UMLS CUI"
    },
    "BANNED_YK11": {
        "cas_number": "1370003-76-1",
        "identifier_note": "Myostatin inhibitor/SARM; no UMLS CUI assigned"
    },
    "BANNED_SUNIFIRAM": {
        "pubchem_cid": "4223713",
        "cas_number": "314728-85-3",
        "identifier_note": "Ampakine nootropic; no UMLS CUI assigned"
    },

    # Nootropics - Research chemicals
    "NOOTROPIC_9MEBC": {
        "pubchem_cid": "164979",
        "cas_number": "2521-07-5",
        "identifier_note": "9-Methyl-β-carboline; research compound, no UMLS CUI"
    },
    "NOOTROPIC_FLMODAFINIL": {
        "cas_number": "90280-13-0",
        "identifier_note": "Fluorinated modafinil analog; no UMLS CUI"
    },
    "NOOTROPIC_OMBERACETAM": {
        "pubchem_cid": "132441",
        "cas_number": "77472-70-9",
        "identifier_note": "Noopept; peptide nootropic, no UMLS CUI"
    },
    "BANNED_FASORACETAM": {
        "pubchem_cid": "198695",
        "cas_number": "110958-19-5",
        "drugbank_id": "DB16163",
        "identifier_note": "Failed Phase 3 trials; no marketed form"
    },
}

# Entries that don't need CUI (products, categories, threats)
# These get a note explaining why no CUI applies
NO_CUI_APPLICABLE = {
    # Recalled products - product names, not chemicals
    "RECALLED_GE_LABS_YKARINE": "Product recall - not a chemical substance",
    "RECALLED_HYDROXYCUT": "Product recall - multi-ingredient product",
    "RECALLED_JACK3D": "Product recall - multi-ingredient product",
    "RECALLED_MR7_SUPER_700000": "Product recall - not a chemical substance",
    "RECALLED_OXYELITE_PRO": "Product recall - multi-ingredient product",
    "RECALLED_RHEUMACARE_CAPSULES": "Product recall - not a chemical substance",
    "RECALLED_TITAN_SARMS_LLC": "Manufacturer recall - not a chemical substance",
    "RECALLED_LIVE_IT_UP_SUPER_GREENS": "Product recall - not a chemical substance",
    "RECALLED_SILINTAN": "Product recall - not a chemical substance",
    "RECALLED_MODERN_WARRIOR": "Product recall - multi-ingredient product",
    "RECALLED_GOLD_STAR_DISTRIBUTION": "Manufacturer recall - not a chemical substance",
    "RECALLED_REBOOST_CLEARLIFE_NASAL_SPRAY": "Product recall - not a chemical substance",
    "RECALLED_PURITY_PRODUCTS_MY_BLADDER": "Product recall - not a chemical substance",
    "RECALLED_GREEN_LUMBER": "Product recall - not a chemical substance",
    "RECALLED_B_BRAUN_IV_SOLUTIONS": "Product recall - not a dietary supplement",

    # Category entries - represent classes, not single chemicals
    "BANNED_ADD_ARTIFICIAL_COLORS": "Category - represents multiple substances",
    "BANNED_ADD_QUATERNARY_AMMONIUM_COMPOUNDS": "Category - represents multiple substances",
    "BANNED_ADD_SYNTHETIC_AMINO_ACIDS": "Category - represents multiple substances",
    "BANNED_ADD_SYNTHETIC_ANTIOXIDANTS": "Category - represents multiple substances",
    "BANNED_ADD_SYNTHETIC_ESTROGENS": "Category - represents multiple substances",
    "BANNED_ADD_SYNTHETIC_FOOD_ACIDS": "Category - represents multiple substances",
    "BANNED_ADD_SYNTHETIC_IRON_OXIDES": "Category - represents multiple substances",

    # Threat/spike entries - categories or analogs
    "BANNED_CONTAMINATED_GLP1": "Contamination category - not a specific chemical",
    "BANNED_METAL_FIBERS": "Contaminant category - not a specific chemical",
    "RC_CARDARINE_ANALOGS": "Analog category - represents multiple substances",
    "SPIKE_ANABOLIC_STEROIDS": "Category - represents multiple substances",
    "SPIKE_CHLOROPRETADALAFIL": "Novel analog - no CUI assigned yet",
    "SPIKE_METHYL7K": "Novel compound - no CUI assigned",
    "SPIKE_PROPOXYPHENYLSILDENAFIL": "Novel analog - no CUI assigned yet",
    "SPIKE_TIANEPTINE_ANALOGUES": "Analog category - represents multiple substances",
    "STIM_ALPHA_PHP": "Novel stimulant - limited registry data",
    "STIM_METHYLHEXANAMINE_ANALOGS": "Analog category - represents multiple substances",
    "SYNTH_CUMYL_PICA": "Synthetic cannabinoid - limited registry data",
    "THREAT_AI_SYNTHETIC_COMPOUNDS": "Threat category - not a specific chemical",
    "THREAT_BACOPA_ADULTERANTS": "Adulterant category - not a specific chemical",
    "THREAT_CONTAMINATED_BOTANICAL_SUBSTITUTION": "Threat category - not a specific chemical",
    "THREAT_MISLABELED_MUSHROOMS": "Threat category - not a specific chemical",
    "THREAT_NOVEL_PEPTIDES": "Threat category - represents multiple substances",
}


def update_identifiers():
    """Update banned_recalled_ingredients.json with standardized identifiers."""

    with open(BANNED_FILE, 'r') as f:
        data = json.load(f)

    ingredients = data.get('ingredients', [])

    stats = {
        'cui_added': 0,
        'pubchem_added': 0,
        'cas_added': 0,
        'unii_added': 0,
        'notes_added': 0,
        'no_cui_applicable': 0
    }

    for item in ingredients:
        item_id = item.get('id', '')

        # Check if we have identifier updates for this item
        if item_id in IDENTIFIER_UPDATES:
            updates = IDENTIFIER_UPDATES[item_id]

            for key, value in updates.items():
                if key == 'CUI' and not item.get('CUI'):
                    item['CUI'] = value
                    stats['cui_added'] += 1
                elif key == 'pubchem_cid' and not item.get('pubchem_cid'):
                    item['pubchem_cid'] = value
                    stats['pubchem_added'] += 1
                elif key == 'cas_number' and not item.get('cas_number'):
                    item['cas_number'] = value
                    stats['cas_added'] += 1
                elif key == 'unii' and not item.get('unii'):
                    item['unii'] = value
                    stats['unii_added'] += 1
                elif key == 'identifier_note' and not item.get('identifier_note'):
                    item['identifier_note'] = value
                    stats['notes_added'] += 1
                elif key not in ['CUI', 'pubchem_cid', 'cas_number', 'unii', 'identifier_note']:
                    # Other identifiers like drugbank_id, nci_thesaurus_code
                    if not item.get(key):
                        item[key] = value

        # Add note for entries where CUI doesn't apply
        elif item_id in NO_CUI_APPLICABLE and not item.get('identifier_note'):
            item['identifier_note'] = NO_CUI_APPLICABLE[item_id]
            stats['no_cui_applicable'] += 1

    # Update metadata (schema v4 layout)
    metadata = data.setdefault('_metadata', {})
    metadata['last_updated'] = datetime.now().strftime('%Y-%m-%d')
    governance = metadata.setdefault('governance', {})
    governance.setdefault('change_log', [])
    governance['change_log'].append({
        'version': metadata.get('schema_version', '4.0.0'),
        'date': datetime.now().strftime('%Y-%m-%d'),
        'changes': [
            f"Added {stats['cui_added']} UMLS CUI identifiers",
            f"Added {stats['pubchem_added']} PubChem CID identifiers",
            f"Added {stats['cas_added']} CAS numbers",
            f"Added {stats['unii_added']} FDA UNII identifiers",
            f"Added identifier notes for {stats['no_cui_applicable']} product/category entries"
        ]
    })

    with open(BANNED_FILE, 'w') as f:
        json.dump(data, f, indent=2)

    return stats


def print_summary(stats):
    """Print summary of updates."""
    print("\n" + "=" * 60)
    print("Standardized Identifier Update Summary")
    print("=" * 60)
    print(f"UMLS CUI added: {stats['cui_added']}")
    print(f"PubChem CID added: {stats['pubchem_added']}")
    print(f"CAS numbers added: {stats['cas_added']}")
    print(f"FDA UNII added: {stats['unii_added']}")
    print(f"Identifier notes added: {stats['notes_added']}")
    print(f"No-CUI-applicable notes: {stats['no_cui_applicable']}")
    print("=" * 60)

    # Verify current state
    with open(BANNED_FILE, 'r') as f:
        data = json.load(f)

    ingredients = data.get('ingredients', [])
    has_cui = sum(1 for i in ingredients if i.get('CUI'))
    has_pubchem = sum(1 for i in ingredients if i.get('pubchem_cid'))
    has_cas = sum(1 for i in ingredients if i.get('cas_number'))
    has_any_id = sum(1 for i in ingredients if i.get('CUI') or i.get('pubchem_cid') or i.get('cas_number') or i.get('unii'))

    print(f"\nCurrent coverage:")
    print(f"  With UMLS CUI: {has_cui}/{len(ingredients)} ({has_cui/len(ingredients)*100:.1f}%)")
    print(f"  With PubChem CID: {has_pubchem}/{len(ingredients)} ({has_pubchem/len(ingredients)*100:.1f}%)")
    print(f"  With CAS number: {has_cas}/{len(ingredients)} ({has_cas/len(ingredients)*100:.1f}%)")
    print(f"  With any standardized ID: {has_any_id}/{len(ingredients)} ({has_any_id/len(ingredients)*100:.1f}%)")


if __name__ == '__main__':
    print("Updating standardized identifiers in banned_recalled_ingredients.json...")
    stats = update_identifiers()
    print_summary(stats)
    print("\nDone!")
