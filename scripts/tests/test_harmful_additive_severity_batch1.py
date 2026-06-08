"""Harmful-additive severity recalibration — Batch 1 (colorants + BHA/BHT).

Slice 1: severity_level recalibration of EXISTING entries + the ADD_BHA gsrs CFR
data-bug fix, all content-verified against EFSA / FDA / IARC / NTP / Prop 65 /
EU Reg (EC) 1333-2008. Research cached at
scripts/audits/batch_harmful_additives_01/research.md.

- Green 3 (Fast Green FCF): moderate -> high — NOT on the EU positive colour list
  (the EU green is E142 Green S); a non-permitted food colour in the EU.
- Blue 1, Blue 2: moderate -> low — authorized in both the US and EU with no major
  safety signal (clean-label preference, not a safety penalty).
- BHT: moderate -> low — IARC Group 3 (not classifiable), NOT NTP-listed, NOT on
  Prop 65 — a sharply lower carcinogen profile than BHA (which stays high: IARC 2B
  + NTP RoC + Prop 65).
- ADD_BHA gsrs.cfr_sections: "21 CFR 171.110" (171 = petition procedure, wrong)
  -> "21 CFR 172.110" (the entry's own regulatory_status.US already says 172.110).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA = REPO_ROOT / "scripts" / "data" / "harmful_additives.json"


def _entries() -> dict:
    return {e["id"]: e for e in json.loads(DATA.read_text())["harmful_additives"]}


def test_green3_escalated_to_high() -> None:
    assert _entries()["ADD_GREEN3"]["severity_level"] == "high"


def test_blue1_deescalated_to_low() -> None:
    assert _entries()["ADD_BLUE1"]["severity_level"] == "low"


def test_blue2_deescalated_to_low() -> None:
    assert _entries()["ADD_BLUE2"]["severity_level"] == "low"


def test_bht_deescalated_to_low() -> None:
    assert _entries()["ADD_BHT"]["severity_level"] == "low"


def test_bha_gsrs_cfr_section_corrected_171_to_172() -> None:
    bha = _entries()["ADD_BHA"]
    cfr = (bha.get("gsrs") or {}).get("cfr_sections") or []
    assert "21 CFR 171.110" not in cfr, "171.110 is the petition-procedure part, not a listing"
    assert "21 CFR 172.110" in cfr, "BHA is permitted under 21 CFR 172.110"


def test_unchanged_severities_hold() -> None:
    e = _entries()
    # BHA stays high (IARC 2B + NTP + Prop 65); the EU-warning azo dyes stay moderate.
    assert e["ADD_BHA"]["severity_level"] == "high"
    assert e["ADD_YELLOW5"]["severity_level"] == "moderate"
    assert e["ADD_YELLOW6"]["severity_level"] == "moderate"
    assert e["ADD_RED40"]["severity_level"] == "moderate"
