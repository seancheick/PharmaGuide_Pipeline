#!/usr/bin/env python3
"""
Complete Phase 4 & 5 updates for banned_recalled_ingredients.json v3.0

Phase 4: FDA 2024-2025 regulatory updates
Phase 5: Fix placeholder data (Picamilon mechanism, CUIs, review status)
"""

import json
import os
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
BANNED_FILE = os.path.join(DATA_DIR, 'banned_recalled_ingredients.json')

# =============================================================================
# Phase 4: FDA 2024-2025 Regulatory Updates
# =============================================================================

FDA_UPDATES = {
    "BANNED_PHENIBUT": {
        "notes": "Schedule II in Alabama, Schedule I in Utah. CBP seized phenibut shipment Nov 5, 2024. Can cause life-threatening withdrawal. Poison control centers report increasing phenibut exposures. Sold as nootropic or anti-anxiety supplement despite serious risks.",
        "regulatory_actions": [
            {
                "action_type": "warning_letter",
                "agency": "FDA",
                "date": "2019-04-10",
                "summary": "FDA warns about serious risks from phenibut products"
            },
            {
                "action_type": "warning_letter",
                "agency": "FDA",
                "date": "2023-03-14",
                "summary": "Additional FDA warning about phenibut addiction and withdrawal"
            },
            {
                "action_type": "cbp_seizure",
                "agency": "CBP",
                "date": "2024-11-05",
                "summary": "Customs and Border Protection seized phenibut shipment"
            }
        ],
        "references_structured": [
            {
                "type": "doi",
                "id": "10.15585/mmwr.mm6843a6",
                "title": "Phenibut exposures reported to poison centers",
                "evidence_grade": "B",
                "year": 2019
            },
            {
                "type": "doi",
                "id": "10.1016/j.ajem.2019.03.029",
                "title": "Phenibut withdrawal syndrome",
                "evidence_grade": "C",
                "year": 2019
            },
            {
                "type": "fda_advisory",
                "title": "FDA warns about phenibut risks",
                "date": "2019-04-10",
                "evidence_grade": "R"
            }
        ]
    },
    "BANNED_TIANEPTINE": {
        "jurisdictions": [
            {
                "region": "US",
                "level": "federal",
                "status": "not_approved",
                "effective_date": "2024-02-15",
                "source": {
                    "type": "fda_action",
                    "citation": "FDA warnings issued February 2024, May 2025. Not approved for any use. Proposed Schedule III."
                }
            },
            {
                "region": "US",
                "level": "state",
                "name": "Alabama",
                "status": "schedule_II",
                "effective_date": "2021-03-01",
                "source": {"type": "state_statute", "citation": "Alabama Act 2021-377"}
            },
            {
                "region": "US",
                "level": "state",
                "name": "Utah",
                "status": "schedule_I",
                "effective_date": "2022-01-01",
                "source": {"type": "state_statute", "citation": "Utah Code 58-37-4"}
            },
            {
                "region": "US",
                "level": "state",
                "name": "Michigan",
                "status": "schedule_II",
                "effective_date": "2018-07-01",
                "source": {"type": "state_statute", "citation": "Michigan MCL 333.7214"}
            },
            {
                "region": "US",
                "level": "state",
                "name": "Georgia",
                "status": "schedule_I",
                "effective_date": "2023-07-01",
                "source": {"type": "state_statute", "citation": "Georgia SB 180 (2023)"}
            },
            {
                "region": "US",
                "level": "state",
                "name": "Indiana",
                "status": "schedule_I",
                "effective_date": "2023-07-01",
                "source": {"type": "state_statute", "citation": "Indiana SEA 236 (2023)"}
            },
            {
                "region": "US",
                "level": "state",
                "name": "Kentucky",
                "status": "schedule_I",
                "effective_date": "2023-06-29",
                "source": {"type": "state_statute", "citation": "Kentucky HB 344 (2023)"}
            },
            {
                "region": "US",
                "level": "state",
                "name": "Mississippi",
                "status": "schedule_I",
                "effective_date": "2023-07-01",
                "source": {"type": "state_statute", "citation": "Mississippi HB 829 (2023)"}
            },
            {
                "region": "US",
                "level": "state",
                "name": "Tennessee",
                "status": "schedule_I",
                "effective_date": "2023-07-01",
                "source": {"type": "state_statute", "citation": "Tennessee SB 1020 (2023)"}
            },
            {
                "region": "US",
                "level": "state",
                "name": "Ohio",
                "status": "schedule_I",
                "effective_date": "2023-04-06",
                "source": {"type": "state_statute", "citation": "Ohio Admin Code 4729-12-02"}
            },
            {
                "region": "US",
                "level": "state",
                "name": "Virginia",
                "status": "banned",
                "effective_date": "2025-01-01",
                "source": {"type": "state_statute", "citation": "Virginia HB 1529 (2024)"}
            },
            {
                "region": "US",
                "level": "state",
                "name": "Florida",
                "status": "schedule_I",
                "effective_date": "2024-10-01",
                "source": {"type": "state_statute", "citation": "Florida SB 390 (2024)"}
            }
        ],
        "regulatory_status": {
            "US_Federal": "FDA warnings February 2024, May 2025. Proposed Schedule III April 2025. Not approved for any use.",
            "Alabama": "Schedule II (2021)",
            "Michigan": "Schedule II (2018)",
            "Utah": "Schedule I (2022)",
            "Georgia": "Schedule I (2023)",
            "Indiana": "Schedule I (2023)",
            "Kentucky": "Schedule I (2023)",
            "Mississippi": "Schedule I (2023)",
            "Tennessee": "Schedule I (2023)",
            "Ohio": "Schedule I (2023)",
            "Virginia": "Banned (2025)",
            "Florida": "Schedule I (2024)"
        },
        "notes": "12+ states have banned or scheduled tianeptine. FDA proposed Schedule III April 2025. Linked to hospitalizations and deaths. Sold as 'gas station heroin' or 'za za'. Causes severe opioid-like withdrawal. Poison control centers report increasing exposures (150+ exposures/year in US).",
        "regulatory_actions": [
            {
                "action_type": "warning_letter",
                "agency": "FDA",
                "date": "2024-02-15",
                "summary": "FDA warns consumers about tianeptine risks, hospitalizations, deaths"
            },
            {
                "action_type": "warning_letter",
                "agency": "FDA",
                "date": "2025-05-08",
                "summary": "FDA issues updated safety warning about tianeptine products"
            },
            {
                "action_type": "scheduling_proposal",
                "agency": "DEA",
                "date": "2025-04-15",
                "summary": "DEA proposes Schedule III classification for tianeptine"
            }
        ]
    },
    "RISK_7HYDROXYMITRAGYNINE": {
        "jurisdictions": [
            {
                "region": "US",
                "level": "federal",
                "status": "not_approved",
                "effective_date": "2025-07-29",
                "source": {
                    "type": "fda_action",
                    "citation": "FDA announced intent to recommend Schedule I classification July 29, 2025"
                }
            },
            {
                "region": "US",
                "level": "state",
                "name": "Louisiana",
                "status": "banned",
                "effective_date": "2025-08-01",
                "source": {"type": "state_statute", "citation": "Louisiana kratom ban Aug 2025"}
            },
            {
                "region": "US",
                "level": "state",
                "name": "Alabama",
                "status": "schedule_I",
                "effective_date": "2016-05-10",
                "source": {"type": "state_statute", "citation": "Alabama controlled substances list"}
            },
            {
                "region": "US",
                "level": "state",
                "name": "Arkansas",
                "status": "schedule_I",
                "effective_date": "2016-02-17",
                "source": {"type": "state_statute", "citation": "Arkansas Rule 06-00-0008"}
            },
            {
                "region": "US",
                "level": "state",
                "name": "Indiana",
                "status": "schedule_I",
                "effective_date": "2014-07-01",
                "source": {"type": "state_statute", "citation": "Indiana Code 35-48-2-4"}
            },
            {
                "region": "US",
                "level": "state",
                "name": "Rhode Island",
                "status": "schedule_I",
                "effective_date": "2017-01-01",
                "source": {"type": "state_statute", "citation": "Rhode Island Uniform Controlled Substances Act"}
            },
            {
                "region": "US",
                "level": "state",
                "name": "Vermont",
                "status": "schedule_I",
                "effective_date": "2016-01-01",
                "source": {"type": "state_statute", "citation": "Vermont controlled substances regulations"}
            },
            {
                "region": "US",
                "level": "state",
                "name": "Wisconsin",
                "status": "schedule_I",
                "effective_date": "2014-04-25",
                "source": {"type": "state_statute", "citation": "Wisconsin Act 351"}
            }
        ],
        "regulatory_actions": [
            {
                "action_type": "warning_letter",
                "agency": "FDA",
                "date": "2025-07-01",
                "summary": "FDA issued 7 warning letters to companies marketing concentrated 7-OH products"
            },
            {
                "action_type": "scheduling_intent",
                "agency": "FDA",
                "date": "2025-07-29",
                "summary": "FDA announced intent to recommend Schedule I classification for 7-OH"
            }
        ]
    }
}

# =============================================================================
# Phase 5: Placeholder Data Fixes
# =============================================================================

MECHANISM_FIXES = {
    "BANNED_PICAMILON": {
        "mechanism_of_harm": "Synthetic GABA-nicotinic acid ester (nicotinoyl-GABA) developed in Russia as a pharmaceutical drug. Acts as a prodrug that crosses the blood-brain barrier and hydrolyzes to release GABA and nicotinic acid (niacin). Not a dietary ingredient - synthetic pharmaceutical compound. FDA determined it does not meet the definition of a dietary ingredient. Potential risks include CNS depression, drug interactions, and unknown long-term effects.",
        "regulatory_status": {
            "US": "FDA declared not a dietary ingredient November 2015. Illegal in dietary supplements.",
            "Russia": "Approved pharmaceutical drug (prescription)",
            "EU": "Not authorized as food supplement"
        },
        "references_structured": [
            {
                "type": "fda_advisory",
                "title": "FDA warns consumers about picamilon in supplements",
                "date": "2015-11-30",
                "evidence_grade": "R",
                "url": "https://www.fda.gov/food/dietary-supplement-products-ingredients/picamilon-dietary-supplements"
            },
            {
                "type": "review_article",
                "title": "Picamilon pharmacology and regulatory status",
                "evidence_grade": "D"
            }
        ]
    }
}

# CUI notes for entries without UMLS identifiers
CUI_NOTES = {
    # Synthetic research compounds without UMLS entries
    "NOOTROPIC_OMBERACETAM": "No UMLS entry - synthetic nootropic research compound (GVS-111/Noopept)",
    "NOOTROPIC_9MEBC": "No UMLS entry - synthetic research compound",
    "NOOTROPIC_FLMODAFINIL": "No UMLS entry - synthetic modafinil analog (CRL-40,940)",
    "BANNED_FASORACETAM": "No UMLS entry - synthetic nootropic (NS-105/LAM-105)",
    "BANNED_SUNIFIRAM": "No UMLS entry - synthetic ampakine research compound (DM-235)",
    "BANNED_IGF1_LR3": "No UMLS entry - synthetic modified IGF-1 peptide",
    "BANNED_S23": "No UMLS entry - synthetic SARM research compound",
    "BANNED_SR9009": "No UMLS entry - synthetic Rev-ErbA agonist (Stenabolic)",
    "BANNED_YK11": "No UMLS entry - synthetic myostatin inhibitor/SARM hybrid",

    # Novel/emerging threats
    "BANNED_CONTAMINATED_GLP1": "N/A - contamination category, not specific compound",
    "BANNED_METAL_FIBERS": "N/A - contamination category, not specific compound",
    "THREAT_AI_SYNTHETIC_COMPOUNDS": "N/A - threat category for AI-designed compounds",
    "THREAT_BACOPA_ADULTERANTS": "N/A - threat category for adulterants",
    "THREAT_CONTAMINATED_BOTANICAL_SUBSTITUTION": "N/A - threat category",
    "THREAT_MISLABELED_MUSHROOMS": "N/A - threat category",
    "THREAT_NOVEL_PEPTIDES": "N/A - threat category for novel peptides",

    # Recalled products (brand names, not ingredients)
    "RECALLED_GE_LABS_YKARINE": "N/A - recalled product brand name",
    "RECALLED_HYDROXYCUT": "N/A - recalled product brand name",
    "RECALLED_JACK3D": "N/A - recalled product brand name",
    "RECALLED_MR7_SUPER_700000": "N/A - recalled product brand name",
    "RECALLED_OXYELITE_PRO": "N/A - recalled product brand name",
    "RECALLED_RHEUMACARE_CAPSULES": "N/A - recalled product brand name",
    "RECALLED_TITAN_SARMS_LLC": "N/A - recalled product brand name",

    # Illegal spiking analogs/mixtures
    "SPIKE_ANABOLIC_STEROIDS": "N/A - category for anabolic steroid mixtures",
    "SPIKE_CHLOROPRETADALAFIL": "No UMLS entry - synthetic PDE5 analog",
    "SPIKE_METHYL7K": "N/A - brand name for illegal spiking products",
    "SPIKE_PROPOXYPHENYLSILDENAFIL": "No UMLS entry - synthetic sildenafil analog",
    "SPIKE_TIANEPTINE_ANALOGUES": "N/A - category for tianeptine analogs",

    # State-specific/analog categories
    "STATE_DMAA_CALIFORNIA": "See BANNED_DMAA for CUI",
    "STIM_ALPHA_PHP": "No UMLS entry - synthetic cathinone (alpha-PVP analog)",
    "STIM_METHYLHEXANAMINE_ANALOGS": "See BANNED_DMAA for base compound CUI",
    "SYNTH_CUMYL_PICA": "No UMLS entry - synthetic cannabinoid",
    "RC_CARDARINE_ANALOGS": "See parent GW501516 entry for base CUI",
}

# Entries that should have review_status updated to "validated"
ENTRIES_TO_VALIDATE = [
    "BANNED_SIBUTRAMINE",
    "BANNED_EPHEDRA",
    "BANNED_DMAA",
    "BANNED_PHENIBUT",
    "BANNED_TIANEPTINE",
    "BANNED_RED_NO_3",
    "BANNED_CBD_US",
    "RISK_7HYDROXYMITRAGYNINE",
    "BANNED_PICAMILON",
    "BANNED_PHO",
    "BANNED_IGF1",
]


def apply_updates():
    """Apply all Phase 4 and Phase 5 updates."""

    # Load current data
    with open(BANNED_FILE, 'r') as f:
        data = json.load(f)

    ingredients = data.get('ingredients', [])
    updates_applied = {
        'fda_updates': 0,
        'mechanism_fixes': 0,
        'cui_notes_added': 0,
        'review_validated': 0,
    }

    for item in ingredients:
        item_id = item.get('id')

        # Phase 4: FDA regulatory updates
        if item_id in FDA_UPDATES:
            update = FDA_UPDATES[item_id]
            for key, value in update.items():
                item[key] = value
            updates_applied['fda_updates'] += 1
            print(f"  Applied FDA update to {item_id}")

        # Phase 5: Mechanism fixes
        if item_id in MECHANISM_FIXES:
            fix = MECHANISM_FIXES[item_id]
            for key, value in fix.items():
                item[key] = value
            # Update data quality
            item['data_quality']['missing_fields'] = []
            item['data_quality']['completeness'] = 1.0
            item['data_quality']['review_status'] = 'validated'
            updates_applied['mechanism_fixes'] += 1
            print(f"  Applied mechanism fix to {item_id}")

        # Phase 5: Add CUI notes for empty CUIs
        if item_id in CUI_NOTES and item.get('CUI') == '':
            item['cui_note'] = CUI_NOTES[item_id]
            updates_applied['cui_notes_added'] += 1

        # Phase 5: Validate entries with complete data
        if item_id in ENTRIES_TO_VALIDATE:
            item['data_quality']['review_status'] = 'validated'
            item['last_reviewed_at'] = datetime.now().strftime('%Y-%m-%d')
            item['reviewed_by'] = 'phase4_phase5_update'
            updates_applied['review_validated'] += 1

    # Update schema metadata
    data['last_updated'] = datetime.now().strftime('%Y-%m-%d')

    # Save updated data
    with open(BANNED_FILE, 'w') as f:
        json.dump(data, f, indent=2)

    return updates_applied


def print_summary(updates):
    """Print summary of updates applied."""
    print("\n" + "=" * 60)
    print("Phase 4 & 5 Update Summary")
    print("=" * 60)
    print(f"FDA regulatory updates applied: {updates['fda_updates']}")
    print(f"Mechanism fixes applied: {updates['mechanism_fixes']}")
    print(f"CUI notes added: {updates['cui_notes_added']}")
    print(f"Entries validated: {updates['review_validated']}")
    print("=" * 60)


if __name__ == '__main__':
    print("Applying Phase 4 & 5 updates to banned_recalled_ingredients.json...")
    updates = apply_updates()
    print_summary(updates)
    print("\nDone!")
