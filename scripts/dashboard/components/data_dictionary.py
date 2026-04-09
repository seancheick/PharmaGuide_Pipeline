import streamlit as st

def field_help(field_name: str) -> str:
    """
    Returns the tooltip string for a given field name.
    """
    dictionary = {
        "bio_score": "Bioavailability score (0-100%) based on ingredient form and clinical data.",
        "grade": "Letter grade based on the Final Score (A+, A, B, C, D, F).",
        "verdict": "Overall product safety verdict (SAFE, CAUTION, POOR, UNSAFE, BLOCKED).",
        "score_100_equivalent": "Final score normalized to a 0-100 scale.",
        "mapped_coverage": "The percentage of product ingredients mapped to our internal clinical database.",
        "has_banned_substance": "Indicates if any ingredient is on a banned or recalled substance list.",
        "has_harmful_additives": "Indicates if any inactive ingredients are classified as harmful.",
        "has_allergen_risks": "Indicates if any ingredient is a known common allergen.",
        "safety_verdict": "Specific verdict focused only on safety and purity criteria.",
        "ingredient_quality": "Pillar 1: Quality and form of the active ingredients.",
        "safety_purity": "Pillar 2: Presence of contaminants or harmful additives.",
        "evidence_research": "Pillar 3: Strength of clinical evidence for the ingredients.",
        "brand_trust": "Pillar 4: Brand reputation and third-party certifications."
    }
    
    return dictionary.get(field_name.lower(), "Description not available.")

def help_icon(field_name: str):
    """
    Renders a help icon with a tooltip for a field.
    """
    st.help(field_help(field_name))
