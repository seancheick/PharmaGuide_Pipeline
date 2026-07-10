"""Release gate for active interaction rules that mention high-dose use."""

from __future__ import annotations

import json
import re
from pathlib import Path


DATA_DIR = Path(__file__).parent.parent / "data"
PAIR_DIR = DATA_DIR / "curated_interactions"
PAIR_FILES = (
    "curated_interactions_v1.json",
    "med_med_pairs_v1.json",
    "batch_critical_2026_05.json",
)
HIGH_DOSE = re.compile(r"high[ -]dose", re.IGNORECASE)


def _pairs() -> list[dict]:
    return [
        pair
        for filename in PAIR_FILES
        for pair in json.loads((PAIR_DIR / filename).read_text())["interactions"]
    ]


def test_every_active_high_dose_pair_is_thresholded_or_explicitly_exempt() -> None:
    exemptions = json.loads((DATA_DIR / "high_dose_rule_exemptions.json").read_text())
    reviewed = exemptions["pairwise_interaction_ids"]
    ids = set()
    for pair in _pairs():
        text = " ".join(
            str(pair.get(field, "") or "")
            for field in ("agent1_name", "agent2_name", "mechanism", "management")
        )
        if not HIGH_DOSE.search(text):
            continue
        ids.add(pair["id"])
        threshold = pair.get("dose_threshold")
        if threshold is not None:
            assert pair.get("materiality") == "dose_dependent", pair["id"]
            assert threshold.get("agent_canonical_id"), pair["id"]
            assert threshold.get("value") is not None, pair["id"]
            assert threshold.get("unit"), pair["id"]
            continue
        rationale = reviewed.get(pair["id"])
        assert isinstance(rationale, str) and len(rationale.strip()) >= 20, (
            f"{pair['id']} mentions high-dose use but has neither a structured "
            "threshold nor a reviewed exemption with rationale"
        )

    assert set(reviewed) <= ids, "exemption allowlist contains an inactive or non-high-dose rule"
