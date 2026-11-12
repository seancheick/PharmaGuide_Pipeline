"""Batch 3b part 2: second review of PR #449, levodopa + iron source (agent label review).

Run once from the repo root:
    $PG_PYTHON scripts/audits/clinical_review_20261111/apply_batch3b_part2_inbrija_source.py

DSI_LEVODOPA_IRON is keyed on levodopa's ingredient RxCUI 6375, so inhaled levodopa (INBRIJA) matches it too. The
pair cited only the oral carbidopa/levodopa (SINEMET) label and its "take together with caution" wording. The
INBRIJA label (DailyMed setid 077c0f39, effective 2026-07-20, read by an agent 2026-11-11) section 7.3 says iron
salts or multivitamins containing iron salts can form chelates with levodopa and reduce its bioavailability, and
its patient counselling text says to tell the prescriber about them. It gives no interval either. The text now
cites both labels and states what each says. Severity (Moderate) and the no-interval scope stay as Dr. Pham decided
(F2); this is a source addition, not a new clinical decision.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scripts"))
import data_batch  # noqa: E402

PAIRS = REPO / "scripts/data/curated_interactions/curated_interactions_v1.json"
INBRIJA = "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=077c0f39-a3a2-4b2b-a184-09131889dcfb"
INBRIJA_PASSAGE = (
    "INBRIJA (levodopa inhalation powder) label (setid 077c0f39, effective 2026-07-20) section 7.3: iron salts or "
    "multivitamins containing iron salts can form chelates with levodopa and reduce its bioavailability; no "
    "interval given."
)


def pairs(blob: dict) -> None:
    pair = next(r for r in blob["interactions"] if r["id"] == "DSI_LEVODOPA_IRON")
    assert INBRIJA not in pair["source_urls"] and "with caution" in pair["management"]
    pair["mechanism"] = (
        "Iron salts can form chelates with levodopa (and with carbidopa in combination tablets) and so reduce how "
        "much of the medicine is available to the body. The carbidopa/levodopa (SINEMET) and inhaled levodopa "
        "(INBRIJA) labels name iron salts, including multivitamins that contain them; this finding covers every "
        "iron supplement as a precaution."
    )
    pair["management"] = (
        "If you take levodopa, talk to your prescriber or pharmacist before starting an iron supplement or a "
        "multivitamin with iron. The carbidopa/levodopa label says to take them together with caution, and the "
        "inhaled levodopa (INBRIJA) label says iron can reduce how much levodopa is available to the body. Neither "
        "label gives a spacing interval, so ask how to time them."
    )
    pair["source_urls"].append(INBRIJA)
    pair["evidence_notes"] = pair["evidence_notes"] + " " + INBRIJA_PASSAGE
    pair["verification"]["notes"] = pair["verification"]["notes"] + " " + INBRIJA_PASSAGE + " Read by agent 2026-11-11."


if __name__ == "__main__":
    blob = data_batch.load(PAIRS)
    pairs(blob)
    data_batch.save(PAIRS, blob)
