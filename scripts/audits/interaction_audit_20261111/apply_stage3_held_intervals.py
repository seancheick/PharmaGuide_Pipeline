"""Stage 3 batch 1: published text stops stating intervals no source supports.

Run once from the repo root:
    $PG_PYTHON scripts/audits/interaction_audit_20261111/apply_stage3_held_intervals.py

Each interval below is held in timing_rules.json as unsupported by its cited
source, or (psyllium) is stated by no source at all. The separation advice
stays where a source supports separating; only the number goes. Magnesium +
levothyroxine keeps "at least 4 hours": Sean approved that interval on
2026-10-01 (D27). Receipts:
research_stage3.md. Nothing here is fetched at run time.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scripts"))
import data_batch  # noqa: E402

CURATED = REPO / "scripts/data/curated_interactions/curated_interactions_v1.json"
RULES = REPO / "scripts/data/ingredient_interaction_rules.json"

CURATED_MANAGEMENT = {
    # ODS Iron and Calcium fact sheets: "at different times of the day"; no hours.
    "SSI_IRON_CALCIUM": (
        "at least 2 hours apart",
        "Take iron and calcium supplements at different times of the day. Iron is best absorbed on an "
        "empty stomach in the morning. Calcium can be taken with meals or at bedtime.",
    ),
    # Messina & Redmond 2006 (PMID 16571087) supports the interaction; states no interval.
    "DSI_LEVOTHYROXINE_SOY": (
        "at least 4 hours",
        "Take levothyroxine at a different time from soy-rich foods or supplements, and ask your prescriber "
        "how far apart. Patients with hypothyroidism on stable levothyroxine should have TSH re-checked if "
        "starting high-dose soy isoflavone supplements.",
    ),
}
DEAD_URLS = {"DSI_LEVOTHYROXINE_SOY": "https://ods.od.nih.gov/factsheets/Soy-HealthProfessional/"}

PSYLLIUM_CLASS_ACTION = (
    "Talk to your prescriber before adding psyllium, and monitor your glucose more closely at first."
)
RULE_ACTIONS = {
    ("RULE_IQM_PSYLLIUM_DIABETES", "condition_rules", 0): (
        "at least 2 hours",
        "Talk to your clinician before adding psyllium, and monitor glucose, especially in the first weeks.",
    ),
    ("RULE_IQM_PSYLLIUM_DIABETES", "drug_class_rules", 0): ("at least 2 hours", PSYLLIUM_CLASS_ACTION),
    ("RULE_IQM_PSYLLIUM_DIABETES", "drug_class_rules", 1): ("at least 2 hours", PSYLLIUM_CLASS_ACTION),
    ("RULE_IQM_PSYLLIUM_DIABETES", "drug_class_rules", 3): ("at least 2 hours", PSYLLIUM_CLASS_ACTION),
}


def main() -> None:
    curated = data_batch.load(CURATED)
    by_id = {item["id"]: item for item in curated["interactions"]}
    for pair_id, (old_phrase, management) in CURATED_MANAGEMENT.items():
        item = by_id[pair_id]
        assert old_phrase in item["management"], pair_id
        item["management"] = management
    for pair_id, url in DEAD_URLS.items():
        item = by_id[pair_id]
        assert url in item["source_urls"], pair_id
        item["source_urls"].remove(url)
    data_batch.save(CURATED, curated)

    rules = data_batch.load(RULES)
    by_rule = {rule["id"]: rule for rule in rules["interaction_rules"]}
    for (rule_id, kind, index), (old_phrase, action) in RULE_ACTIONS.items():
        sub = by_rule[rule_id][kind][index]
        assert old_phrase in sub["action"], (rule_id, kind, index)
        sub["action"] = action
    data_batch.save(RULES, rules)


if __name__ == "__main__":
    main()
