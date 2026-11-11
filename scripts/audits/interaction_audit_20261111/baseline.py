"""Interaction audit Stage 1 baseline: pins plus a repeatable warning-volume sample.

Usage:
    python3 scripts/audits/interaction_audit_20261111/baseline.py \
        --blobs scripts/final_db_output --app "/Users/seancheick/PharmaGuide ai"

Writes baseline.json and sample_ids.json beside this file. The volume numbers
approximate the app's product-page gates. They rank rules for review and are
not a false-positive rate.
"""

from __future__ import annotations

import argparse
import collections
import json
import random
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
SAMPLE_SIZE = 4000
SEED = 1
RANK = {"monitor": 1, "caution": 2, "avoid": 3, "contraindicated": 4}
# One profile per id: a single saved condition or drug class (profile vocabulary).
PROFILES = [
    "anticoagulants",
    "antihypertensives",
    "pregnancy",
    "lactation",
    "diabetes",
    "kidney_disease",
    "heart_disease",
    "thyroid_medications",
]


def _sha(path: Path) -> str:
    return subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"], text=True).strip()


def _shown(warning: dict) -> bool:
    if warning.get("type") not in ("interaction", "drug_interaction"):
        return False
    severity = warning.get("severity")
    if severity not in RANK:
        return False
    if warning.get("dose_floor_status") in ("below", "form_mismatch") and severity not in (
        "avoid",
        "contraindicated",
    ):
        return False
    if (warning.get("dose_decision") or {}).get("consumer_disposition") == "suppress":
        return False
    return warning.get("direction") != "beneficial"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--blobs", type=Path, required=True, help="final_db_output directory")
    parser.add_argument("--app", type=Path, required=True, help="Flutter app checkout")
    args = parser.parse_args()

    export = json.loads((args.blobs / "export_manifest.json").read_text())
    interaction = json.loads((args.app / "assets/db/interaction_db_manifest.json").read_text())
    files = sorted((args.blobs / "detail_blobs").glob("*.json"))
    random.seed(SEED)
    sample = random.sample(files, SAMPLE_SIZE)

    worst = {p: collections.Counter() for p in PROFILES}
    drivers = {p: collections.Counter() for p in PROFILES}
    for path in sample:
        best: dict[str, tuple[int, str, str]] = {}
        for w in json.loads(path.read_text()).get("warnings") or []:
            if not _shown(w):
                continue
            ids = set(w.get("drug_class_ids") or []) | set(w.get("condition_ids") or [])
            subject = w.get("ingredient_canonical_id") or w.get("title") or "?"
            for p in PROFILES:
                rank = RANK[w["severity"]]
                if p in ids and (p not in best or rank > best[p][0]):
                    best[p] = (rank, w["severity"], subject)
        for p, (_, severity, subject) in best.items():
            worst[p][severity] += 1
            drivers[p][subject] += 1

    n = len(sample)
    baseline = {
        "pins": {
            "pipeline_sha": _sha(REPO),
            "app_sha": _sha(args.app),
            "interaction_db_version": interaction["interaction_db_version"],
            "interaction_db_checksum": interaction["checksum_sha256"],
            "profile_warning_rules_count": interaction["profile_warning_rules_count"],
            "blob_build": export["db_version"],
            "blob_build_checksum": export["checksum_sha256"],
            "blob_count": len(files),
        },
        "sample": {"size": n, "seed": SEED, "selection": "random.sample over sorted detail_blobs paths"},
        "profiles": {
            p: {
                "share_of_products_warned": round(sum(worst[p].values()) / n, 4),
                "worst_severity_share": {k: round(v / n, 4) for k, v in sorted(worst[p].items())},
                "top_subjects": drivers[p].most_common(8),
            }
            for p in PROFILES
        },
    }
    (HERE / "baseline.json").write_text(json.dumps(baseline, indent=2) + "\n")
    (HERE / "sample_ids.json").write_text(json.dumps(sorted(p.stem for p in sample)) + "\n")
    for p in PROFILES:
        row = baseline["profiles"][p]
        print(f"{p:20} {row['share_of_products_warned']:.1%}  {row['worst_severity_share']}")


if __name__ == "__main__":
    main()
