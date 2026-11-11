"""Stage 3 batch 2: replace DailyMed label citations that do not exist.

Run once from the repo root:
    $PG_PYTHON scripts/audits/interaction_audit_20261111/apply_stage3_label_citations.py

Every old setid returned 404 from the DailyMed v2 SPL service on 2026-11-11
(the service returned 200 for a known label in the same run); six follow a
sequential-hex pattern and look fabricated. Each replacement is the current
label whose interaction text was read and quoted in research_stage3.md. Only
citations change: severity, mechanism and management are untouched.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scripts"))
import data_batch  # noqa: E402

CURATED_DIR = REPO / "scripts/data/curated_interactions"
RULES = REPO / "scripts/data/ingredient_interaction_rules.json"


def label(setid: str) -> str:
    return f"https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid={setid}"


LANOXIN_TABLETS = label("d91e3646-4c63-4512-ab22-db39c085c4dc")
CIPRO = label("888dc7f9-ad9c-4c00-8d50-8ddfd9bd27c0")
TEGRETOL = label("8d409411-aa9f-4f3a-a52c-fbcb0c3ec053")
DEPAKOTE = label("08a65cf4-7749-4ceb-6895-8f4805e2b01f")
VERAPAMIL_ER = label("af1249b0-e889-4f02-bdc2-54862de0545e")
GEMFIBROZIL = label("cf32b795-bf42-4861-b273-06d27de3f21d")

DEAD = {
    "c2d3e4f5-a6b7-4c8d-9e0f-1a2b3c4d5e6f": VERAPAMIL_ER,
    "0e83dd12-eaf9-4764-8039-eae5d6a9bd87": LANOXIN_TABLETS,
    "d3e4f5a6-b7c8-4d9e-0f1a-2b3c4d5e6f7a": LANOXIN_TABLETS,
    "0de62b3e-de08-4fbb-afcb-3b7dae3b4ca7": CIPRO,
    "e4f5a6b7-c8d9-4e0f-1a2b-3c4d5e6f7a8b": CIPRO,
    "d5b3c5ca-6064-4bc4-b46f-f45a41f0a4f6": TEGRETOL,
    "f5a6b7c8-d9e0-4f1a-2b3c-4d5e6f7a8b9c": TEGRETOL,
    "a6b7c8d9-e0f1-4a2b-3c4d-5e6f7a8b9c0d": DEPAKOTE,
    "b7c8d9e0-f1a2-4b3c-4d5e-6f7a8b9c0d1e": LANOXIN_TABLETS,
    "09b2febc-cc26-40c4-aeda-5a04a5e2a93c": GEMFIBROZIL,
    "1496ea0f-1419-c809-e063-6294a90a0b43": CIPRO,
}

CURATED_EXPECTED = {
    "med_med_pairs_v1.json": {
        "DDI_BETABLOCKER_VERAPAMIL", "DDI_DIGOXIN_AMIODARONE", "DDI_THEOPHYLLINE_CIPRO", "DDI_ANTICONV_OCP",
        "DDI_PHENYTOIN_VALPROATE", "DDI_DIGOXIN_DIURETICS", "DDI_STATIN_GEMFIBROZIL",
    },
    "batch_critical_2026_05.json": {"DSI_FLUOROQUINOLONES_IRON", "DSI_FLUOROQUINOLONES_MAGNESIUM"},
}
RULES_EXPECTED = {
    ("RULE_IQM_IRON_HYPERTENSION", 2), ("RULE_IQM_MAGNESIUM_HYPERTENSION", 2),
    ("RULE_IQM_CALCIUM", 1), ("RULE_IQM_ZINC", 1),
}


def _replace(urls: list[str]) -> tuple[list[str], bool]:
    out, changed = [], False
    for url in urls:
        dead = next((s for s in DEAD if s in url), None)
        new = DEAD[dead] if dead else url
        changed |= dead is not None
        if new not in out:
            out.append(new)
    return out, changed


def main() -> None:
    for name, expected in CURATED_EXPECTED.items():
        path = CURATED_DIR / name
        doc = data_batch.load(path)
        touched = set()
        for item in doc["interactions"]:
            urls, changed = _replace(item.get("source_urls") or [])
            if changed:
                item["source_urls"] = urls
                touched.add(item["id"])
        assert touched == expected, (name, touched ^ expected)
        data_batch.save(path, doc)

    rules = data_batch.load(RULES)
    touched = set()
    for rule in rules["interaction_rules"]:
        for i, sub in enumerate(rule.get("drug_class_rules") or []):
            urls, changed = _replace(sub.get("sources") or [])
            if changed:
                sub["sources"] = urls
                touched.add((rule["id"], i))
    assert touched == RULES_EXPECTED, touched ^ RULES_EXPECTED
    data_batch.save(RULES, rules)


if __name__ == "__main__":
    main()
