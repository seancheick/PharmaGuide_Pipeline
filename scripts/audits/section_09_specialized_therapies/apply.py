#!/usr/bin/env python3
"""Finalize Section 9 specialty-therapy record dispositions."""
import json
from pathlib import Path

DATA = Path(__file__).resolve().parents[2] / "data" / "medication_depletions.json"
REVIEWER = "medication_depletion_section_09_specialized_therapies_audit"
VERIFIED = {
    "DEP_ORLISTAT_VITAMINA", "DEP_ORLISTAT_VITAMIND", "DEP_ORLISTAT_VITAMINE", "DEP_ORLISTAT_VITAMINK",
    "DEP_CHOLESTYRAMINE_VITAMINA", "DEP_CHOLESTYRAMINE_VITAMIND", "DEP_CHOLESTYRAMINE_VITAMINE", "DEP_CHOLESTYRAMINE_VITAMINK",
}
SUPPRESSED = {
    "DEP_IMMUNOSUPPRESSANTS_MAGNESIUM": "Suppressed: PMID 16641596 is a content mismatch; calcineurin-specific magnesium evidence needs a verified replacement and narrow scope.",
    "DEP_IMMUNOSUPPRESSANTS_VITAMIND": "Suppressed: PMID 19528952 is a content mismatch; transplant-associated vitamin-D status does not establish a class-wide immunosuppressant depletion claim.",
    "DEP_HIVPI_VITAMIND": "Suppressed: PMID 21694637 is a content mismatch and the record conflates HIV disease with protease-inhibitor effects.",
    "DEP_HIVPI_ZINC": "Suppressed: PMID 12591569 is a content mismatch and the record conflates HIV disease with protease-inhibitor effects.",
}
NEUTRAL = {
    "evidence_level": "possible", "mechanism": "No consumer depletion mechanism is asserted pending exact supporting evidence.",
    "clinical_impact": "No consumer depletion warning is emitted.", "recommendation": "Do not supplement solely because of this medication or condition.",
    "onset_timeline": "not established", "monitoring_note": "No medication-specific nutrient monitoring recommendation is emitted.",
    "alert_headline": "No medication-specific depletion alert", "alert_body": "No medication-caused nutrient depletion has been established over time; no consumer warning is emitted.",
    "acknowledgement_note": "No medication-specific nutrient coverage acknowledgement is emitted.",
    "monitoring_tip_short": "Discuss individual monitoring needs with your treating clinician.", "food_sources_short": "Maintain dietary intake appropriate to your individual needs.",
}
def main() -> None:
    document=json.loads(DATA.read_text()); entries={e['id']:e for e in document['depletions']}
    for entry_id in VERIFIED:
        entries[entry_id].update(citation_review_status='verified', reviewed_at='2026-07-26', reviewer=REVIEWER)
    for entry_id, note in SUPPRESSED.items():
        entry=entries[entry_id]; entry.update(citation_review_status='needs_revision', citation_review_note=note, reviewed_at='2026-07-26', reviewer=REVIEWER, **NEUTRAL)
        entry.pop('adequacy_threshold_mcg', None); entry.pop('adequacy_threshold_mg', None)
    DATA.write_text(json.dumps(document, indent=2) + '\n')
if __name__ == '__main__': main()
