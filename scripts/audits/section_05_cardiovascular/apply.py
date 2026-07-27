#!/usr/bin/env python3
"""Fail-close Section 5 cardiovascular depletion claims pending exact scope."""
import json
from pathlib import Path

PATH = Path(__file__).resolve().parents[2] / "data" / "medication_depletions.json"
UPDATES = {
 "DEP_ACEINHIBITORS_ZINC": ("needs_revision", "possible", "Captopril-specific studies report altered zinc measures, particularly with long-term high-dose treatment; that does not justify a class-wide ACE-inhibitor supplement recommendation.", "No ACE-inhibitor zinc-depletion warning is emitted pending a drug-specific, clinically actionable review.", "Do not start zinc solely because of ACE-inhibitor use.", "Suppressed (needs_revision): live studies support a captopril-specific signal, not the displayed broad ACE-inhibitor claim or routine zinc supplementation."),
 "DEP_BETABLOCKERS_COQ10": ("needs_revision", "possible", "No consumer mechanism is asserted: the inherited PMID is not evidence that beta blockers deplete coenzyme Q10.", "No beta-blocker CoQ10 depletion warning is emitted pending exact supporting evidence.", "Do not start CoQ10 solely because of beta-blocker use.", "Suppressed (needs_revision): PMID 12392188 is a content mismatch for the displayed beta-blocker CoQ10 claim; it must not support consumer supplementation."),
 "DEP_BETABLOCKERS_MELATONIN": ("needs_revision", "possible", "Some beta blockers reduce nocturnal melatonin, but effects vary by agent and study; this is not a class-wide nutrient-depletion indication.", "No beta-blocker melatonin depletion warning is emitted pending agent-specific scope and consumer-safety review.", "Discuss persistent sleep symptoms with the prescriber rather than self-treating them as a universal beta-blocker depletion.", "Suppressed (needs_revision): PMIDs 10335905 and 23024438 support selected beta-blocker melatonin effects, not the displayed broad class claim or a universal supplementation recommendation."),
 "DEP_CALCIUMCHANNELBLOCKERS_POTASSIUM": ("rejected", "possible", "No reliable evidence establishes calcium-channel blockers as potassium-wasting medicines.", "No calcium-channel-blocker potassium depletion warning is emitted.", "Follow ordinary dietary potassium guidance; do not supplement solely because of calcium-channel-blocker use.", "Rejected: inherited textbook assertion lacks claim-matched evidence for potassium depletion or supplementation."),
 "DEP_ANTIHYPERTENSIVES_ZINC": ("rejected", "possible", "Antihypertensive classes have heterogeneous zinc effects; a broad class cannot support a single depletion mechanism.", "No broad-antihypertensive zinc depletion warning is emitted.", "Do not start zinc solely because of antihypertensive use.", "Rejected: broad class conflates ACE inhibitors, diuretics, beta blockers, and other agents with different evidence and mechanisms."),
 "DEP_ANTIHYPERTENSIVES_COQ10": ("rejected", "possible", "No reliable evidence establishes a hydralazine/clonidine coenzyme Q10 depletion claim.", "No hydralazine/clonidine CoQ10 depletion warning is emitted.", "Do not start CoQ10 solely because of hydralazine or clonidine use.", "Rejected: inherited textbook assertion lacks claim-matched clinical evidence for depletion or supplementation."),
}
def main():
 d=json.loads(PATH.read_text()); entries={e['id']:e for e in d['depletions']}
 for eid,(status,level,mechanism,impact,recommendation,note) in UPDATES.items():
  entries[eid].update(citation_review_status=status,evidence_level=level,mechanism=mechanism,clinical_impact=impact,recommendation=recommendation,citation_review_note=note,reviewed_at='2026-07-26',reviewer='medication_depletion_section_05_cardiovascular_audit')
 PATH.write_text(json.dumps(d,indent=2)+'\n')
if __name__ == '__main__': main()
