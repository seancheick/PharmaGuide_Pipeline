"""Batch 3b part 2: fixes from the independent review of PR #449.

Run once from the repo root:
    $PG_PYTHON scripts/audits/clinical_review_20261111/apply_batch3b_part2_review_fixes.py

Agent dispositions (label and identity review, not Dr. Pham's decisions):
- Licorice identity. The cleaner left "Glycyrrhiza uralensis root" and "... root extract" unmapped, so the
  Chinese-licorice twin added in this batch never reached them; both are G. uralensis root, which the EU liquorice
  monograph (EMA/HMPC/108399/2024 Rev. 1) covers. "Licorice Root Extract, DGL" stayed unmapped, as did two DGL
  names on current labels ("GutGard Deglycyrrhizinated Licorice (DGL) root extract", "standardized Deglycyrrhized
  Licorice extract"). Each name states deglycyrrhizination, so each joins the DGL entry. Not fixed here:
  "Licorice root extract (deglycyrrhizinated)" still maps to whole licorice, because the cleaner resolves the name
  before its parenthetical, so an alias cannot reach it (over-warning; no current label uses it). No label in the
  current corpus names G. inflata; no alias is added for it.
- DSI_LEVODOPA_IRON. The SINEMET label (setid 9b17b028) names "iron salts or multivitamins containing iron salts";
  the pair said the label "applies to iron supplements". The text now says what the label names and that the pair
  covers every iron form as a precaution.
- CBD + immunosuppressants. The headline and body still said "transplant drugs" and "your transplant prescriber";
  everolimus, which the EPIDIOLEX finding concerns, is also used for tuberous sclerosis and cancer. Severity, gate
  and evidence unchanged.
- Licorice review_owner. The earlier owner (pharmaguide_clinical_team) wrote the original rule, not this batch's
  text; the field now says so.

Recorded for the 12 stored-id mismatches: four rows were not changed because their stored and shipped ids normalize
to the same supplement (DSI_STATINS_RYR: BANNED_RED_YEAST_RICE vs RISK_RED_YEAST_RICE -> red_yeast_rice;
DSI_ANTICOAG_CBD, DSI_ANTIHYP_CBD, DSI_STATINS_CBD: cbd vs BANNED_CBD_US -> cbd). Also recorded:
RULE_BOTANICAL_LICORICE_ROOT dropped PMID 31605160 in this batch; it is a glycyrrhizin-metabolite biomarker study,
not an interaction study.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scripts"))
import data_batch  # noqa: E402

DATA = REPO / "scripts/data"
RULES = DATA / "ingredient_interaction_rules.json"
PAIRS = DATA / "curated_interactions/curated_interactions_v1.json"
BOTANICALS = DATA / "botanical_ingredients.json"

URALENSIS_ALIASES = ["glycyrrhiza uralensis root", "glycyrrhiza uralensis root extract"]
DGL_ALIASES = [
    "licorice root extract, dgl",
    "gutgard deglycyrrhizinated licorice (dgl) root extract",
    "gutgard deglycyrrhizinated licorice (dgl) extract",
    "standardized deglycyrrhized licorice extract",
]

OLD_OWNER_TAIL = "read by agent; pharmaguide_clinical_team"
NEW_OWNER_TAIL = "read by agent; original rule by pharmaguide_clinical_team"


def rules(blob: dict) -> None:
    by_id = {r["id"]: r for r in blob["interaction_rules"]}
    cbd = by_id["RULE_BANNED_CBD_INTERACTIONS"]
    [sub] = [s for s in cbd["drug_class_rules"] if s["drug_class_id"] == "immunosuppressants"]
    assert sub["alert_headline"] == "May increase exposure to some transplant drugs"
    assert sub["alert_body"].startswith("CBD can increase exposure to certain transplant drugs.")
    sub["alert_headline"] = "May raise levels of some immunosuppressant medicines"
    sub["alert_body"] = (
        "CBD can raise levels of certain immunosuppressant medicines, such as everolimus, tacrolimus or "
        "sirolimus. Talk to the prescriber of that medicine before use; drug-level monitoring or a prescribed "
        "dose adjustment may be needed."
    )
    for rule_id in ("RULE_IQM_LICORICE_HYPERTENSION", "RULE_BOTANICAL_LICORICE_ROOT"):
        owner = by_id[rule_id]["review_owner"]
        assert owner.endswith(OLD_OWNER_TAIL), rule_id
        by_id[rule_id]["review_owner"] = owner[: -len(OLD_OWNER_TAIL)] + NEW_OWNER_TAIL


def pairs(blob: dict) -> None:
    pair = next(r for r in blob["interactions"] if r["id"] == "DSI_LEVODOPA_IRON")
    assert "says this applies to iron supplements" in pair["mechanism"]
    pair["mechanism"] = (
        "Iron salts can form chelates with levodopa and carbidopa and so reduce how much of the medicine is "
        "available to the body. The carbidopa/levodopa (SINEMET) label names iron salts, including multivitamins "
        "that contain them; this finding covers every iron supplement as a precaution."
    )


def botanicals(blob: dict) -> None:
    by_id = {b["id"]: b for b in blob["botanical_ingredients"]}
    for entry_id, new in (("chinese_licorice", URALENSIS_ALIASES), ("dgl_deglycyrrhizinated_licorice", DGL_ALIASES)):
        aliases = by_id[entry_id]["aliases"]
        assert not set(new) & set(aliases), entry_id
        aliases.extend(new)


if __name__ == "__main__":
    for path, patch in ((RULES, rules), (PAIRS, pairs), (BOTANICALS, botanicals)):
        blob = data_batch.load(path)
        patch(blob)
        data_batch.save(path, blob)
