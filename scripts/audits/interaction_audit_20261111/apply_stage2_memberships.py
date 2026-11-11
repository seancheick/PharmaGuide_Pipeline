"""Stage 2 data batch: medication classes that entered medicines need to reach rule classes.

Run once from the repo root:
    $PG_PYTHON scripts/audits/interaction_audit_20261111/apply_stage2_memberships.py

Every RxCUI below was taken from live RxClass ATC membership or an exact RxNorm
name lookup, then content-verified on RxNorm (name, tty IN, status Active) on
2026-11-11. Receipts: research_stage2.md. Nothing here is fetched at run time.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scripts"))
import data_batch  # noqa: E402

CLASSES = REPO / "scripts/data/drug_classes.json"
RULES = REPO / "scripts/data/ingredient_interaction_rules.json"
TAXONOMY = REPO / "scripts/data/clinical_risk_taxonomy.json"
VERIFIED = "All rxcuis content-verified against RxNorm (ingredient, Active) 2026-11-11."

SNRIS = [("1433212", "levomilnacipran"), ("39786", "venlafaxine"), ("588250", "milnacipran"),
         ("72625", "duloxetine"), ("734064", "desvenlafaxine")]
SULFONYLUREAS_AND_MEGLITINIDES = [
    ("173", "acetohexamide"), ("2068", "carbutamide"), ("2404", "chlorpropamide"),
    ("102846", "glibornuride"), ("4816", "gliclazide"), ("25789", "glimepiride"), ("4821", "glipizide"),
    ("25793", "gliquidone"), ("4815", "glyburide"), ("10633", "tolazamide"), ("10635", "tolbutamide"),
    ("274332", "nateglinide"), ("73044", "repaglinide"),
]

# class id -> (display_name, description, atc_codes, members [(rxcui, name)], notes)
NEW_CLASSES = {
    "class:cardiac_glycosides": (
        "Cardiac glycosides (digoxin, digitoxin)",
        "Digitalis glycosides, the medicines the cardiac_glycosides rule class describes.",
        ["C01AA"],
        [("235219", "digitalis leaf extract"), ("132871", "acetyldigitoxin"), ("199", "acetyldigoxins"),
         ("3248", "deslanoside"), ("3403", "digitoxin"), ("3407", "digoxin"), ("27929", "lanatoside c"),
         ("6686", "medigoxin")],
        "Live RxClass ATC C01AA membership. Selects the existing cardiac_glycosides rule class "
        "(senna, cascara, aloe ferox, ginseng). " + VERIFIED,
    ),
    "class:thyroid_medications": (
        "Thyroid hormone medicines",
        "Thyroid hormone replacement (levothyroxine, liothyronine, desiccated thyroid).",
        ["H03AA"],
        [("10572", "thyroid (usp)"), ("10582", "levothyroxine"), ("10814", "liothyronine"),
         ("13982", "tiratricol")],
        "Thyroid hormones only. Every thyroid_medications sub-rule concerns levothyroxine absorption or "
        "thyroid-hormone action, so antithyroid drugs (methimazole, propylthiouracil; ATC H03B) are not "
        "members, although the profile vocabulary's examples list methimazole (open for PharmD review). "
        "RxClass returns only tiratricol for H03AA; the other three come from exact RxNorm lookups. " + VERIFIED,
    ),
    "class:antidepressants_ssri_snri": (
        "Antidepressants (SSRIs and SNRIs)",
        "Selective serotonin reuptake inhibitors and serotonin-norepinephrine reuptake inhibitors.",
        ["N06AB", "N06AX16", "N06AX17", "N06AX21", "N06AX23", "N06AX28"],
        "class:ssris+snris",
        "class:ssris members (ATC N06AB) plus the SNRIs venlafaxine, milnacipran, duloxetine, "
        "desvenlafaxine and levomilnacipran, matching the rule class the profile vocabulary defines. " + VERIFIED,
    ),
    "class:anticholinergics": (
        "Anticholinergic (antimuscarinic) medicines",
        "Medicines whose main action is muscarinic blockade: bladder antimuscarinics, anticholinergic "
        "antiparkinson agents, scopolamine and antimuscarinic antispasmodics.",
        ["G04BD", "N04AA", "N04AC01", "A04AD01", "A03AB02", "A03AA07", "A03BA03"],
        [("136198", "darifenacin"), ("3816", "emepronium"), ("797195", "fesoterodine"),
         ("32675", "oxybutynin"), ("55175", "propiverine"), ("322167", "solifenacin"),
         ("37815", "terodiline"), ("119565", "tolterodine"), ("236778", "trospium"),
         ("1589", "biperiden"), ("19610", "bornaprine"), ("3267", "dexetimide"), ("29682", "methixene"),
         ("8718", "procyclidine"), ("4134", "profenamine"), ("10811", "trihexyphenidyl"),
         ("38876", "tropatepine"), ("1424", "benztropine"), ("9601", "scopolamine"),
         ("1546438", "glycopyrronium"), ("3361", "dicyclomine"), ("153970", "hyoscyamine")],
        "Primary antimuscarinics only. Excluded: beta-3 agonists that share ATC G04BD (mirabegron, "
        "vibegron) and flavoxate (not a clear antimuscarinic). Medicines with secondary anticholinergic "
        "effects (diphenhydramine, tricyclics), which the profile vocabulary's examples include, are left "
        "for PharmD review. " + VERIFIED,
    ),
    "class:hypoglycemics_high_risk": (
        "Insulin, sulfonylureas and meglitinides",
        "Diabetes medicines the profile vocabulary places in the high hypoglycemia-risk tier.",
        ["A10A", "A10BB", "A10BX02", "A10BX03"],
        "class:insulins+oral",
        "Tier per the signed drug_class_vocab (insulin, sulfonylureas, repaglinide, nateglinide): "
        "class:insulins members plus ATC A10BB, repaglinide and nateglinide. " + VERIFIED,
    ),
    "class:hypoglycemics_lower_risk": (
        "Metformin, GLP-1 agonists, SGLT2 and DPP-4 inhibitors",
        "Diabetes medicines the profile vocabulary places in the lower hypoglycemia-risk tier.",
        ["A10BA", "A10BJ", "A10BK", "A10BH"],
        [("6809", "metformin"), ("8129", "phenformin"), ("1534763", "albiglutide"),
         ("1551291", "dulaglutide"), ("60548", "exenatide"), ("475968", "liraglutide"),
         ("1440051", "lixisenatide"), ("1991302", "semaglutide"), ("2627044", "bexagliflozin"),
         ("1373458", "canagliflozin"), ("1488564", "dapagliflozin"), ("1545653", "empagliflozin"),
         ("1992672", "ertugliflozin"), ("2638675", "sotagliflozin"), ("1368001", "alogliptin"),
         ("1100699", "linagliptin"), ("857974", "saxagliptin"), ("593411", "sitagliptin"),
         ("596554", "vildagliptin")],
        "Tier per the signed drug_class_vocab (metformin, GLP-1 receptor agonists, SGLT2 and DPP-4 "
        "inhibitors). " + VERIFIED,
    ),
    "class:hypoglycemics_unknown": (
        "Other diabetes medicines",
        "Diabetes medicines the profile vocabulary names in neither tier; they take the conservative tier.",
        ["A10BG", "A10BF", "A10BX05", "A10BX06", "A10BX16"],
        [("33738", "pioglitazone"), ("84108", "rosiglitazone"), ("72610", "troglitazone"),
         ("16681", "acarbose"), ("30009", "miglitol"), ("139953", "pramlintide"), ("18880", "benfluorex"),
         ("2601723", "tirzepatide")],
        "Unknown-tier sub-rules carry the high-risk severities, so this is the conservative placement. "
        "Guar gum (ATC A10BX01) is a dietary fiber and is excluded. The tier for tirzepatide and "
        "pramlintide is open for PharmD review. " + VERIFIED,
    ),
    "class:clobazam": (
        "Clobazam",
        "Clobazam, kept as its own class for the antiseizure-medicine warnings that name it.",
        ["N05BA09"],
        [("21241", "clobazam")],
        "Single-medicine class (precedent: class:lithium). The cannabidiol label names clobazam; adding it "
        "to class:anticonvulsants would also reach the enzyme-induction contraceptive pair. " + VERIFIED,
    ),
}


def _members(spec, classes: dict) -> list[tuple[str, str]]:
    if spec == "class:ssris+snris":
        base = classes["class:ssris"]
        return list(zip(base["member_rxcuis"], base["member_names"])) + SNRIS
    if spec == "class:insulins+oral":
        base = classes["class:insulins"]
        return list(zip(base["member_rxcuis"], base["member_names"])) + SULFONYLUREAS_AND_MEGLITINIDES
    return spec


def main() -> None:
    blob = data_batch.load(CLASSES)
    classes = blob["classes"]
    for class_id, (display, description, atc, spec, notes) in NEW_CLASSES.items():
        assert class_id not in classes, class_id
        members = sorted(dict(_members(spec, classes)).items(), key=lambda m: (m[1].lower(), m[0]))
        assert len({r for r, _ in members}) == len(members)
        classes[class_id] = {
            "display_name": display,
            "description": description,
            "member_rxcuis": [r for r, _ in members],
            "member_names": [n for _, n in members],
            "rxclass_id": atc[0],
            "atc_codes": atc,
            "notes": notes,
        }
    data_batch.save(CLASSES, blob)

    # The taxonomy is the profile-gate vocabulary, not the profile picker
    # (drug_class_vocab.json); ssris and lithium are listed the same way.
    tax = data_batch.load(TAXONOMY)
    have = {d["id"] for d in tax["drug_classes"]}
    for entry in (
        {"id": "valproate", "label": "Valproate", "category": "neurologic", "display_priority": 23},
        {"id": "clobazam", "label": "Clobazam", "category": "neurologic", "display_priority": 24},
    ):
        if entry["id"] not in have:
            tax["drug_classes"].append(entry)
    meta = tax["_metadata"]
    meta["drug_classes_count"] = len(tax["drug_classes"])
    meta["total_entries"] += sum(1 for e in ("valproate", "clobazam") if e not in have)
    meta["schema_version"] = "5.6.0"
    meta["last_updated"] = "2026-11-11"
    migrations = meta["migration"]["completed_migrations"]
    if migrations[0]["to"] != "5.6.0":
        migrations.insert(0, {
            "from": "5.5.0", "to": "5.6.0", "date": "2026-11-11",
            "summary": "Additive: drug classes valproate and clobazam, so the cannabidiol antiseizure-medicine "
                       "warning can name the two medicines its label names. Gate vocabulary only; the profile "
                       "picker (drug_class_vocab.json) is unchanged.",
        })
    data_batch.save(TAXONOMY, tax)

    rules = data_batch.load(RULES)
    cbd = next(r for r in rules["interaction_rules"] if r["id"] == "RULE_BANNED_CBD_INTERACTIONS")
    sub = next(d for d in cbd["drug_class_rules"] if d["drug_class_id"] == "anticonvulsants")
    gate = sub["profile_gate"]["requires"]["drug_classes_any"]
    for alias in ("clobazam", "valproate"):
        if alias not in gate:
            gate.append(alias)
    data_batch.save(RULES, rules)


if __name__ == "__main__":
    main()
