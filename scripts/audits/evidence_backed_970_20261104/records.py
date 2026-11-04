"""Agent-reviewed rejection records for the 970-label Evidence review (November 4, 2026).

Each record is rejected on every label it reaches: no record here may earn credit.
Written by agent review (Claude). Nothing here is a clinician's approval.
"""

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
]
