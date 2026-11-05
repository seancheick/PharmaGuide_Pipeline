"""Agent-reviewed rejection records for the 970-label Evidence review (November 4, 2026).

Each record is rejected on every label it reaches: no record here may earn credit.
Written by agent review (Claude). Nothing here is a clinician's approval.
"""
import json
from pathlib import Path

AGENT_NOTE = "Agent review (Claude), 2026-11-04; not clinician reviewed."

RECORDS = [
    {
        "id": "INGR_N_ACETYL_L_TYROSINE",
        "standard_name": "N-Acetyl-L-Tyrosine",
        "aliases": ["N-Acetyl L-Tyrosine", "N-Acetyl Tyrosine", "N-Acetyltyrosine", "NALT"],
        "category": "cognitive_neurological",
        "evidence_level": "ingredient-human",
        "study_type": "rct_multiple",
        "published_studies": ["25598314", "24433977", "14621123", "2507878", "7705801"],
        "score_contribution": "tier_3",
        "effect_direction": "null",
        "effect_direction_confidence": "low",
        "effect_direction_rationale": (
            "No oral efficacy trial of N-acetyl-L-tyrosine alone was found. The small placebo-controlled "
            "cognition trials read here gave free L-tyrosine, so they do not establish this preparation. "
            "The human N-acetyl-L-tyrosine reports found are parenteral or intravenous utilization studies. "
            "Null records that no affirmative finding exists for this preparation, not that it was tested "
            "and failed. " + AGENT_NOTE
        ),
        "key_endpoints": ["No efficacy endpoint tested for oral N-acetyl-L-tyrosine alone"],
        "endpoint_relevance_tags": ["cognitive"],
        "health_goals_supported": [],
        "notes": (
            "Preparation rejection only: this record says nothing about free L-tyrosine, whose separate "
            "review is in scripts/audits/evidence_backed_970_20261104/packet. PMIDs 25598314 and 24433977 "
            "tested tyrosine in healthy adults. PMIDs 14621123, 2507878 and 7705801 report intravenous or "
            "parenteral utilization of N-acetyl-L-tyrosine, with considerable unchanged urinary excretion. "
            "PubMed title and abstract search on November 4, 2026: 225 records retrieved, 42 in a human-use "
            "or supplement context read as excerpts, none an oral efficacy trial of this ingredient alone; "
            "PMIDs 28096758 and 28096757 tested a pre-workout blend containing 300 mg. " + AGENT_NOTE
        ),
        "last_updated": "2026-11-04",
        "applicability": {
            "scope": "ingredient",
            "excluded_form_terms": ["n-acetyl", "n acetyl", "acetyl-l-tyrosine", "acetyl l-tyrosine", "acetyl tyrosine", "acetyltyrosine", "nalt"],
            "source_pmids": ["25598314", "24433977"],
            "studied_population": "Healthy adults given free L-tyrosine in single-session placebo-controlled cognitive task trials.",
            "supported_outcomes": ["Focus & Mental Clarity"],
            "reviewed_at": "2026-11-04",
            "reason": (
                "The reviewed human studies gave free L-tyrosine. Oral N-acetyl-L-tyrosine alone has no "
                "efficacy trial found, so these studies do not qualify for this preparation. " + AGENT_NOTE
            ),
        },
    },
    {
        "id": "INGR_BUTTERBUR_WHOLE_HERB",
        "standard_name": "Butterbur Whole Herb Extract",
        "aliases": ["Butterbur Whole Herb Extract"],
        "category": "general_herbs",
        "evidence_level": "ingredient-human",
        "study_type": "rct_multiple",
        "published_studies": ["15623680", "14752215"],
        "score_contribution": "tier_3",
        "effect_direction": "null",
        "effect_direction_confidence": "low",
        "effect_direction_rationale": (
            "The placebo-controlled migraine trials read here gave a standardized Petasites hybridus root "
            "extract, so they do not establish a whole herb extract. No whole-herb efficacy trial was found. "
            "Null records that no affirmative finding exists for this preparation, not that it was tested "
            "and failed. " + AGENT_NOTE
        ),
        "key_endpoints": ["No efficacy endpoint tested for a butterbur whole herb extract"],
        "endpoint_relevance_tags": [],
        "health_goals_supported": [],
        "notes": (
            "Preparation rejection only: this record says nothing about butterbur root extract, whose separate "
            "review is in scripts/audits/evidence_backed_970_20261104/packet. PubMed search on November 4, 2026: "
            "butterbur, petasites, petadolex or Ze 339 with trial, review or guideline publication types, 97 "
            "records, titles scanned; butterbur with liver, pyrrolizidine, whole herb or aerial part, 52 records, "
            "the 30 most recent titles scanned. No title or abstract read names a whole-herb trial. Not every "
            "abstract was opened. " + AGENT_NOTE
        ),
        "last_updated": "2026-11-04",
        "applicability": {
            "scope": "ingredient",
            "excluded_form_terms": ["whole herb"],
            "source_pmids": ["15623680", "14752215"],
            "studied_population": "Adults with migraine given a standardized Petasites hybridus root extract.",
            "supported_outcomes": ["Migraine attack frequency"],
            "reviewed_at": "2026-11-04",
            "reason": (
                "The reviewed human studies gave a standardized butterbur root extract. No efficacy trial of a "
                "whole herb extract was found, so these studies do not qualify for this preparation. " + AGENT_NOTE
            ),
        },
    },
    {
        "id": "INGR_L_ORNITHINE_L_ASPARTATE",
        "standard_name": "L-Ornithine L-Aspartate",
        "aliases": ["L-Ornithine L-Aspartate"],
        "category": "liver_detox",
        "evidence_level": "ingredient-human",
        "study_type": "rct_multiple",
        "published_studies": ["29762873", "38403493", "9625322"],
        "score_contribution": "tier_3",
        "effect_direction": "null",
        "effect_direction_confidence": "low",
        "effect_direction_rationale": (
            "The human research read here enrolled people with cirrhosis and hepatic encephalopathy, including "
            "a trial at 18 g per day (PMID 9625322). The 2018 Cochrane review rates much of that evidence very "
            "low quality (PMID 29762873). No trial of this ingredient alone outside liver disease was found, so "
            "these studies do not establish a benefit for a general supplement label. Null records that no "
            "affirmative finding exists for that use, not that it was tested and failed. " + AGENT_NOTE
        ),
        "key_endpoints": ["No efficacy endpoint tested for this ingredient alone outside liver disease"],
        "endpoint_relevance_tags": [],
        "health_goals_supported": [],
        "notes": (
            "Preparation and purpose rejection only: this record says nothing about L-ornithine hydrochloride, "
            "whose separate review is in scripts/audits/evidence_backed_970_20261104/packet. PubMed search for "
            "trials outside cirrhosis on November 4, 2026 returned 2 records: PMID 41653037, a narrative review "
            "in metabolic fatty liver disease that asks for further research, and PMID 26785372, which gave it "
            "with branched chain amino acids in 11 trained men. Labels print 3 g per serving. " + AGENT_NOTE
        ),
        "last_updated": "2026-11-04",
        "applicability": {
            "scope": "ingredient",
            "excluded_form_terms": ["aspartate", "lola"],
            "source_pmids": ["29762873", "38403493", "9625322"],
            "studied_population": "People with cirrhosis and overt or minimal hepatic encephalopathy.",
            "supported_outcomes": ["Hepatic encephalopathy"],
            "reviewed_at": "2026-11-04",
            "reason": (
                "The reviewed human studies enrolled people with cirrhosis and hepatic encephalopathy. No trial "
                "of this ingredient alone outside liver disease was found, so these studies do not qualify for "
                "the purpose of this product. " + AGENT_NOTE
            ),
        },
    },
]

# Literature records corrected to the existing no-credit path, where the read supports it directly.
LITERATURE_CORRECTIONS = {
    "l_lysine": {
        "effect_direction": "null",
        "applicability_decision": (
            "Conflicting human evidence with no clear benefit, so this review completes with no Evidence credit. "
            "An older placebo-controlled trial reported fewer recurrent herpes simplex infections at 3 g/day for "
            "6 months in 52 completers (PMID 3115841). A crossover trial in 41 patients reported fewer recurrences "
            "at 1,248 mg/day but not at 624 mg/day (PMID 6435961), and a trial in 21 patients found no substantial "
            "benefit at 1,200 mg/day (PMID 6419679). The 2015 Cochrane prevention review states: 'We failed to find "
            "any evidence of efficacy for lysine' (PMID 26252373). These sources support no established 1 g/day "
            "threshold or universal continuous efficacy range. " + AGENT_NOTE
        ),
        "studies": [
            {"pmid": "6435961", "study_type": "rct", "sample_size": 41,
             "primary_endpoint": "herpes simplex recurrence rate, severity and healing time",
             "effect_direction": "mixed",
             "quote": "A dose of 624 mg a day was not effective."},
            {"pmid": "6419679", "study_type": "rct", "sample_size": 21,
             "primary_endpoint": "herpes simplex episode frequency, duration and severity",
             "effect_direction": "null",
             "quote": "we were unable to detect any substantial benefit of lysine therapy"},
        ],
        "receipt": "PubMed abstracts read November 4, 2026; packet/INGR_L_LYSINE.json",
    },
}

LITERATURE_CORRECTIONS.update(json.loads((Path(__file__).parent / "literature_corrections.json").read_text()))
