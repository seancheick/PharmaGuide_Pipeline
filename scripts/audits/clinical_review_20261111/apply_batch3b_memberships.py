"""Batch 3b, part 1: medication-class membership decisions D1-D3 of Dr. Pham's 2026-11-11 review.

Run once from the repo root:
    $PG_PYTHON scripts/audits/clinical_review_20261111/apply_batch3b_memberships.py

D1  Methimazole inhibits thyroid hormone synthesis (METHIMAZOLE label, setid 141a91d5); it is not a thyroid replacement.
    The vocabulary example and the "modulate" wording go; class:thyroid_medications already excludes antithyroid drugs.
    The tap-to-learn note applied a 4-hour spacing to iodine, kelp, soy isoflavones and biotin. The SYNTHROID label
    (setid 1e11ad30) gives 4 hours for binders such as calcium carbonate and ferrous sulfate, and says to stop biotin
    2 days before TSH/T4 tests; the note now says that and nothing more.
D2  Diphenhydramine joins class:anticholinergics (its label: "anticholinergic (drying) and sedative effects", setid
    f808ee14). Tricyclics were reviewed one by one against their own current DailyMed labels (read 2026-11-11); each
    of the nine below states anticholinergic properties or atropine-like action. Maprotiline has no current DailyMed
    label and is not added. Membership is by ingredient: RxNorm combination sleep aids resolve to diphenhydramine
    (3498), so they are reached; other antihistamines and antidepressants are not.
D3  Tirzepatide moves to the lower-risk tier: per MOUNJARO 5.3, use with an insulin secretagogue or insulin may
    increase the risk of hypoglycemia, including severe hypoglycemia, and those medicines carry the high-risk tier
    themselves. Pramlintide stays in the
    conservative unknown tier: SYMLIN 5.2 says it does not cause hypoglycemia alone but is indicated with mealtime
    insulin, where severe hypoglycemia risk rises; without insulin entered the regimen is incomplete, not low risk.

The two rules gated on anticholinergics now reach medicines whose anticholinergic effect is a side effect. Their
text is scoped to fit (an independent review found it did not): alpha-GPC's "reduced therapeutic efficacy" applies
to medicines taken for their anticholinergic action, and huperzine A's "these effects cancel" overstated the donepezil
label's "potential to interfere". Severities are unchanged; whether both rules should reach the new members is ask 6.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scripts"))
import data_batch  # noqa: E402

CLASSES = REPO / "scripts/data/drug_classes.json"
RULES = REPO / "scripts/data/ingredient_interaction_rules.json"
VOCAB = REPO / "scripts/data/drug_class_vocab.json"

# RxCUI (ingredient, Active, checked on RxNav 2026-11-11) -> (name, DailyMed setid of the label read).
ANTICHOLINERGIC_ADDITIONS = {
    "3498": ("diphenhydramine", "f808ee14-fccf-4abe-b53a-a40b0b3bba03"),
    "704": ("amitriptyline", "00d11130-c9ae-4258-9746-9763bc5deb84"),
    "722": ("amoxapine", "a16297df-3158-48db-85e5-5cd506885556"),
    "2597": ("clomipramine", "b1809cb2-c6a8-451a-b692-506456c4efc3"),
    "3247": ("desipramine", "a3b4b25d-0ddb-4531-badb-f1ba3168ac07"),
    "3638": ("doxepin", "1496dfc1-de50-471c-be87-1f1e2b70ab5a"),
    "5691": ("imipramine", "20af582f-08ba-4281-a2df-0bcf68c58594"),
    "7531": ("nortriptyline", "dbb3cc4d-c36d-495d-b9fc-e5513b2f6b93"),
    "8886": ("protriptyline", "c6c7c39e-e510-4f4a-bf7a-926f0e075d3a"),
    "10834": ("trimipramine", "4f31df66-7dc2-1f04-e054-00144ff88e88"),
}
TIRZEPATIDE = "2601723"

THYROID_NOTES = (
    "Thyroid hormone replacement. The levothyroxine label says to take it at least 4 hours apart from calcium "
    "carbonate or ferrous sulfate, and to stop biotin at least 2 days before thyroid blood tests."
)


def _set_members(cls: dict, pairs: list[tuple[str, str]]) -> None:
    pairs = sorted(pairs, key=lambda p: p[1])
    cls["member_rxcuis"] = [rxcui for rxcui, _ in pairs]
    cls["member_names"] = [name for _, name in pairs]


def _pairs(cls: dict) -> list[tuple[str, str]]:
    assert len(cls["member_rxcuis"]) == len(cls["member_names"])
    return list(zip(cls["member_rxcuis"], cls["member_names"]))


def anticholinergics(cls: dict) -> None:
    pairs = _pairs(cls)
    assert len(pairs) == 22 and not set(ANTICHOLINERGIC_ADDITIONS) & set(cls["member_rxcuis"])
    _set_members(cls, pairs + [(rxcui, name) for rxcui, (name, _) in ANTICHOLINERGIC_ADDITIONS.items()])
    cls["display_name"] = "Anticholinergic medicines"
    cls["description"] = (
        "Primary antimuscarinics (bladder antimuscarinics, anticholinergic antiparkinson agents, scopolamine, "
        "antimuscarinic antispasmodics), plus diphenhydramine and the tricyclic antidepressants whose own labels "
        "identify anticholinergic effects."
    )
    cls["atc_codes"] = [*cls["atc_codes"], "R06AA02", "N06AA"]
    cls["notes"] = (
        "Dr. Pham D2 (2026-11-11): add diphenhydramine and review the tricyclics individually; membership does not "
        "extend to all antihistamines or antidepressants. Each added medicine's current DailyMed label (read "
        "2026-11-11) states anticholinergic effects: diphenhydramine f808ee14; amitriptyline 00d11130; amoxapine "
        "a16297df; clomipramine b1809cb2; desipramine a3b4b25d; doxepin 1496dfc1; imipramine 20af582f; "
        "nortriptyline dbb3cc4d; protriptyline c6c7c39e; trimipramine 4f31df66. Membership is by ingredient, so "
        "combination sleep and cold products reach it and route is not distinguished (topical products included); "
        "low-dose doxepin (SILENOR, 3-6 mg) lists anticholinergic effects only above 6 mg (ask 4). N06AA is listed "
        "as the group the tricyclics belong to; membership is the explicit list. Maprotiline has no current DailyMed label and is not "
        "included. Excluded: beta-3 agonists that share ATC G04BD (mirabegron, vibegron) and flavoxate. All rxcuis "
        "content-verified against RxNorm (ingredient, Active) 2026-11-11."
    )


def lower_risk(cls: dict) -> None:
    assert TIRZEPATIDE not in cls["member_rxcuis"]
    _set_members(cls, _pairs(cls) + [(TIRZEPATIDE, "tirzepatide")])
    cls["atc_codes"] = [*cls["atc_codes"], "A10BX16"]
    cls["notes"] = (
        "Tier per the signed drug_class_vocab (metformin, GLP-1 receptor agonists, SGLT2 and DPP-4 inhibitors). "
        "Tirzepatide added per Dr. Pham D3 (2026-11-11): lower intrinsic risk alone; per MOUNJARO 5.3, use with an "
        "insulin secretagogue or insulin may increase the risk of hypoglycemia, including severe hypoglycemia, and "
        "those medicines carry the high-risk tier themselves. All rxcuis content-verified against RxNorm "
        "(ingredient, Active) 2026-11-11."
    )


def unknown(cls: dict) -> None:
    pairs = _pairs(cls)
    assert (TIRZEPATIDE, "tirzepatide") in pairs and "A10BX16" in cls["atc_codes"]
    _set_members(cls, [p for p in pairs if p[0] != TIRZEPATIDE])
    cls["atc_codes"] = [code for code in cls["atc_codes"] if code != "A10BX16"]
    cls["notes"] = (
        "Unknown-tier sub-rules carry the high-risk severities, so this is the conservative placement. Guar gum "
        "(ATC A10BX01) is a dietary fiber and is excluded. Pramlintide stays here per Dr. Pham D3 (2026-11-11): "
        "SYMLIN does not cause hypoglycemia alone but is indicated with mealtime insulin, where severe hypoglycemia "
        "risk rises, so without insulin entered the regimen is incomplete rather than low risk; entered insulin "
        "reaches the high-risk tier. All rxcuis content-verified against RxNorm (ingredient, Active) 2026-11-11."
    )


def thyroid(cls: dict) -> None:
    assert "open for PharmD review" in cls["notes"]
    cls["notes"] = (
        "Thyroid hormones only. Every thyroid_medications sub-rule concerns levothyroxine absorption or "
        "thyroid-hormone action, so antithyroid drugs (methimazole, propylthiouracil; ATC H03B) are not members; "
        "the profile vocabulary's methimazole example was removed per Dr. Pham D1 (2026-11-11). RxClass returns "
        "only tiratricol for H03AA; the other three come from exact RxNorm lookups. All rxcuis content-verified "
        "against RxNorm (ingredient, Active) 2026-11-11."
    )


def classes(blob: dict) -> None:
    c = blob["classes"]
    anticholinergics(c["class:anticholinergics"])
    lower_risk(c["class:hypoglycemics_lower_risk"])
    unknown(c["class:hypoglycemics_unknown"])
    thyroid(c["class:thyroid_medications"])


def vocab(blob: dict) -> None:
    entry = next(e for e in blob["drug_classes"] if e["id"] == "thyroid_medications")
    assert entry["examples"][-1] == "methimazole" and entry["notes"].startswith("Replace or modulate")
    entry["examples"] = entry["examples"][:-1]
    assert len(THYROID_NOTES) <= 200
    entry["notes"] = THYROID_NOTES


ALPHA_GPC_OLD = (
    "Alpha-GPC antagonises this pharmacological effect, potentially reducing the therapeutic efficacy of "
    "anticholinergics (e.g., overactive bladder treatment with oxybutynin) or creating unpredictable CNS effects."
)
ALPHA_GPC_NEW = (
    "Alpha-GPC antagonises this pharmacological effect. For medicines taken for their anticholinergic action (e.g., "
    "oxybutynin for overactive bladder), that could reduce their therapeutic effect; for medicines whose "
    "anticholinergic effect is a side effect (e.g., diphenhydramine, tricyclic antidepressants), the practical effect "
    "of the combination is not established."
)


def _anticholinergic_sub(blob: dict, rule_id: str) -> dict:
    rule = next(r for r in blob["interaction_rules"] if r["id"] == rule_id)
    return next(d for d in rule["drug_class_rules"] if d["drug_class_id"] == "anticholinergics")


def rules(blob: dict) -> None:
    gpc = _anticholinergic_sub(blob, "RULE_IQM_ALPHA_GPC_ANTICHOLINERGICS")
    assert gpc["mechanism"].endswith(ALPHA_GPC_OLD) and gpc["action"].endswith("Monitor for loss of efficacy.")
    gpc["mechanism"] = gpc["mechanism"].replace(ALPHA_GPC_OLD, ALPHA_GPC_NEW)
    gpc["action"] = (
        "Inform prescriber of alpha-GPC use if taking anticholinergic medications. If the medicine is taken for its "
        "anticholinergic action (for example, oxybutynin for overactive bladder), watch for it working less well."
    )
    hup = _anticholinergic_sub(blob, "RULE_IQM_HUPERZINE_A_ANTICHOLINERGICS")
    assert "these effects cancel" in hup["alert_body"]
    hup["alert_body"] = (
        "Huperzine A boosts acetylcholine while anticholinergics block it, so the two can work against each other. "
        "If you take an anticholinergic medication, talk to your prescriber before use."
    )


def edit(path: Path, fn) -> None:
    blob = data_batch.load(path)
    fn(blob)
    data_batch.save(path, blob)


if __name__ == "__main__":
    edit(CLASSES, classes)
    edit(VOCAB, vocab)
    edit(RULES, rules)
