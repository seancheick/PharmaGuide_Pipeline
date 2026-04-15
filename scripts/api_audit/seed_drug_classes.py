#!/usr/bin/env python3
"""Seed scripts/data/drug_classes.json via the NLM RxClass API.

Produces the source-of-truth mapping from ``class:X`` logical IDs (used in
interaction records) to expanded RxCUI member lists. One-shot seeder per
INTERACTION_DB_SPEC.md §10.2.

Design notes
------------
* Stdlib ``urllib`` only — mirrors ``verify_cui.py`` so operators who know
  that tool don't need to re-learn anything.
* Offline by default: ``--dry-run`` prints the plan without network calls.
* ``--live`` actually calls RxClass and writes the JSON.
* Classes span multiple ATC codes when one code isn't a clean fit
  (e.g. ``antihypertensives`` = C03 + C07 + C08 + C09; ``benzodiazepines``
  = N05BA + N05CD).
* We filter to ingredient-level terms via ``ttys=IN`` so brand/formulated
  names are excluded — stable, clean, deterministic output.
* Rate-limited at ``RATE_LIMIT_DELAY`` between requests.
* Deterministic: member lists are sorted by name (case-insensitive).

Usage
-----
    # Dry run (no network, shows plan):
    python3 scripts/api_audit/seed_drug_classes.py --dry-run

    # Live seed (calls RxClass, writes drug_classes.json):
    python3 scripts/api_audit/seed_drug_classes.py --live

    # Custom output path:
    python3 scripts/api_audit/seed_drug_classes.py --live \\
        --output /tmp/drug_classes.json

Exit codes
----------
    0   Success (or dry-run completed)
    1   Network failure / any class returned 0 members
    2   Bad arguments
"""

from __future__ import annotations

import argparse
import json
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

# --------------------------------------------------------------------------- #
# HTTP plumbing (mirrors verify_cui.py)
# --------------------------------------------------------------------------- #

RXCLASS_BASE = "https://rxnav.nlm.nih.gov/REST/rxclass"
RATE_LIMIT_DELAY = 0.12  # ~8 req/s, well under NLM's posted ~20 req/s cap
REQUEST_TIMEOUT = 10.0


def _make_ssl_ctx() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    try:
        req = urllib.request.Request("https://rxnav.nlm.nih.gov", method="HEAD")
        urllib.request.urlopen(req, timeout=5, context=ctx)
        return ctx
    except (ssl.SSLCertVerificationError, urllib.error.URLError):
        return ssl._create_unverified_context()


_SSL_CTX: ssl.SSLContext | None = None


def _ssl_ctx() -> ssl.SSLContext:
    global _SSL_CTX
    if _SSL_CTX is None:
        _SSL_CTX = _make_ssl_ctx()
    return _SSL_CTX


def http_get_json(endpoint: str, params: dict[str, str]) -> dict | None:
    """GET an RxClass endpoint. Returns parsed JSON or None on error/empty."""
    query = urllib.parse.urlencode(params)
    url = f"{RXCLASS_BASE}{endpoint}?{query}"
    time.sleep(RATE_LIMIT_DELAY)
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT, context=_ssl_ctx()) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        print(f"  API error: HTTP {e.code} — {e.reason}", file=sys.stderr)
        return None
    except (urllib.error.URLError, TimeoutError) as e:
        print(f"  API error: {e}", file=sys.stderr)
        return None


def fetch_class_members(class_id: str, rela_source: str = "ATC") -> list[tuple[str, str]]:
    """Fetch ingredient-level members of an RxClass class.

    Returns a sorted list of ``(rxcui, lowercase_name)`` tuples. Empty list
    on failure or no members.
    """
    payload = http_get_json(
        "/classMembers.json",
        {"classId": class_id, "relaSource": rela_source, "ttys": "IN"},
    )
    if not payload:
        return []

    members = payload.get("drugMemberGroup", {}).get("drugMember", []) or []
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for m in members:
        concept = m.get("minConcept", {})
        rxcui = str(concept.get("rxcui", "")).strip()
        name = str(concept.get("name", "")).strip().lower()
        if not rxcui or not name or rxcui in seen:
            continue
        seen.add(rxcui)
        out.append((rxcui, name))

    # Deterministic ordering: by name, then rxcui
    out.sort(key=lambda t: (t[1], t[0]))
    return out


# --------------------------------------------------------------------------- #
# Class definitions — the one source of truth for the 24 classes
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ClassDef:
    class_id: str  # e.g. "class:statins"
    display_name: str
    description: str
    atc_codes: tuple[str, ...]  # ATC codes to union
    rxclass_id: str  # primary ATC for breadcrumb; use first of atc_codes
    notes: str = ""


CLASS_DEFINITIONS: tuple[ClassDef, ...] = (
    ClassDef(
        class_id="class:statins",
        display_name="Statins",
        description="HMG-CoA reductase inhibitors used for cholesterol management",
        atc_codes=("C10AA",),
        rxclass_id="C10AA",
    ),
    ClassDef(
        class_id="class:ssris",
        display_name="SSRIs",
        description="Selective serotonin reuptake inhibitors (antidepressants)",
        atc_codes=("N06AB",),
        rxclass_id="N06AB",
    ),
    ClassDef(
        class_id="class:beta_blockers",
        display_name="Beta blockers",
        description="Beta-adrenergic receptor antagonists used for hypertension, arrhythmia, heart failure",
        atc_codes=("C07A",),
        rxclass_id="C07A",
    ),
    ClassDef(
        class_id="class:ace_inhibitors",
        display_name="ACE inhibitors",
        description="Angiotensin-converting enzyme inhibitors used for hypertension and heart failure",
        atc_codes=("C09A",),
        rxclass_id="C09A",
    ),
    ClassDef(
        class_id="class:maois",
        display_name="MAOIs",
        description="Monoamine oxidase inhibitors (antidepressants and antiparkinsonians)",
        atc_codes=("N06AF", "N06AG"),
        rxclass_id="N06AF",
        notes="Union of N06AF (non-selective hydrazines) and N06AG (type A selective)",
    ),
    ClassDef(
        class_id="class:benzodiazepines",
        display_name="Benzodiazepines",
        description="GABA-A positive allosteric modulators (anxiolytics, hypnotics, anticonvulsants)",
        atc_codes=("N05BA", "N05CD"),
        rxclass_id="N05BA",
        notes="Union of N05BA (anxiolytic benzos) and N05CD (hypnotic benzos)",
    ),
    ClassDef(
        class_id="class:nsaids",
        display_name="NSAIDs",
        description="Non-steroidal anti-inflammatory drugs",
        atc_codes=("M01A",),
        rxclass_id="M01A",
    ),
    ClassDef(
        class_id="class:anticonvulsants",
        display_name="Anticonvulsants",
        description="Antiepileptic drugs used for seizure disorders and neuropathic pain",
        atc_codes=("N03A",),
        rxclass_id="N03A",
    ),
    ClassDef(
        class_id="class:diabetes_meds",
        display_name="Oral antidiabetic drugs",
        description="Non-insulin blood glucose lowering drugs (metformin, sulfonylureas, GLP-1 agonists, etc.)",
        atc_codes=("A10B",),
        rxclass_id="A10B",
    ),
    ClassDef(
        class_id="class:insulins",
        display_name="Insulins",
        description="Insulin and insulin analogues for diabetes",
        atc_codes=("A10A",),
        rxclass_id="A10A",
    ),
    ClassDef(
        class_id="class:corticosteroids",
        display_name="Systemic corticosteroids",
        description="Glucocorticoids for systemic use (prednisone, dexamethasone, etc.)",
        atc_codes=("H02AB",),
        rxclass_id="H02AB",
    ),
    ClassDef(
        class_id="class:immunosuppressants",
        display_name="Immunosuppressants",
        description="Drugs suppressing immune response (calcineurin inhibitors, mTOR, antimetabolites, mAbs)",
        atc_codes=("L04A",),
        rxclass_id="L04A",
    ),
    ClassDef(
        class_id="class:hiv_protease_inhibitors",
        display_name="HIV protease inhibitors",
        description="Antiretroviral protease inhibitors for HIV treatment",
        atc_codes=("J05AE",),
        rxclass_id="J05AE",
    ),
    ClassDef(
        class_id="class:antipsychotics",
        display_name="Antipsychotics",
        description="Typical and atypical antipsychotic agents",
        atc_codes=("N05A",),
        rxclass_id="N05A",
    ),
    ClassDef(
        class_id="class:triptans",
        display_name="Triptans",
        description="Selective serotonin 5-HT1 receptor agonists for migraine",
        atc_codes=("N02CC",),
        rxclass_id="N02CC",
    ),
    ClassDef(
        class_id="class:antacids",
        display_name="Antacids",
        description="Direct-acting acid neutralizers (calcium carbonate, aluminum/magnesium hydroxide)",
        atc_codes=("A02A",),
        rxclass_id="A02A",
        notes="PPIs (A02BC) and H2 blockers (A02BA) are tracked separately if needed",
    ),
    ClassDef(
        class_id="class:calcium_channel_blockers",
        display_name="Calcium channel blockers",
        description="Selective calcium channel antagonists for hypertension and arrhythmia",
        atc_codes=("C08",),
        rxclass_id="C08",
    ),
    ClassDef(
        class_id="class:diuretics",
        display_name="Diuretics",
        description="Thiazide, loop, and potassium-sparing diuretics",
        atc_codes=("C03",),
        rxclass_id="C03",
    ),
    ClassDef(
        class_id="class:oral_contraceptives",
        display_name="Hormonal contraceptives",
        description="Systemic hormonal contraceptives (estrogens, progestogens, combinations)",
        atc_codes=("G03A",),
        rxclass_id="G03A",
    ),
    ClassDef(
        class_id="class:sedatives",
        display_name="Hypnotics and sedatives",
        description="Non-benzodiazepine hypnotics and sedatives (zolpidem, zaleplon, melatonin agonists)",
        atc_codes=("N05C",),
        rxclass_id="N05C",
        notes="Superset of N05CD benzos; for benzo-only use class:benzodiazepines",
    ),
    ClassDef(
        class_id="class:stimulants",
        display_name="Centrally-acting sympathomimetics",
        description="Amphetamines, methylphenidate, and related CNS stimulants",
        atc_codes=("N06BA",),
        rxclass_id="N06BA",
    ),
    ClassDef(
        class_id="class:antihypertensives",
        display_name="Antihypertensives (union class)",
        description="Union of RAAS blockers, beta blockers, CCBs, and diuretics for broad BP-lowering matches",
        atc_codes=("C03", "C07A", "C08", "C09"),
        rxclass_id="C09",
        notes="Superset — overlaps with class:ace_inhibitors, class:beta_blockers, class:calcium_channel_blockers, class:diuretics",
    ),
    ClassDef(
        class_id="class:b_vitamins",
        display_name="B vitamins",
        description="B-complex vitamin preparations (plain and combinations)",
        atc_codes=("A11D", "A11H"),
        rxclass_id="A11D",
        notes="Used for matching OTC B-vitamin products; supplement-side lookup handled via ingredient_quality_map canonical_ids",
    ),
    ClassDef(
        class_id="class:anticoagulants",
        display_name="Anticoagulants",
        description="Vitamin K antagonists, direct thrombin inhibitors, and direct Factor Xa inhibitors",
        atc_codes=("B01AA", "B01AE", "B01AF"),
        rxclass_id="B01AA",
        notes="Critical for supplement interactions: warfarin vs vitamin K, ginkgo, fish oil, garlic",
    ),
)


assert len(CLASS_DEFINITIONS) == 24, f"Expected 24 classes, got {len(CLASS_DEFINITIONS)}"


# --------------------------------------------------------------------------- #
# Seed build
# --------------------------------------------------------------------------- #


@dataclass
class SeedResult:
    class_id: str
    display_name: str
    description: str
    member_rxcuis: list[str] = field(default_factory=list)
    member_names: list[str] = field(default_factory=list)
    rxclass_id: str = ""
    atc_codes: list[str] = field(default_factory=list)
    notes: str = ""

    def to_dict(self) -> dict:
        out: dict = {
            "display_name": self.display_name,
            "description": self.description,
            "member_rxcuis": self.member_rxcuis,
            "member_names": self.member_names,
            "rxclass_id": self.rxclass_id,
            "atc_codes": self.atc_codes,
        }
        if self.notes:
            out["notes"] = self.notes
        return out


def seed_one(defn: ClassDef) -> SeedResult:
    """Fetch all ATC member lists for one class and merge them."""
    merged: dict[str, str] = {}  # rxcui -> name
    for atc in defn.atc_codes:
        members = fetch_class_members(atc, rela_source="ATC")
        for rxcui, name in members:
            # First name wins for a rxcui (they're identical across ATC codes)
            merged.setdefault(rxcui, name)

    # Sort deterministically by name, then rxcui
    ordered = sorted(merged.items(), key=lambda kv: (kv[1], kv[0]))
    return SeedResult(
        class_id=defn.class_id,
        display_name=defn.display_name,
        description=defn.description,
        member_rxcuis=[rxcui for rxcui, _ in ordered],
        member_names=[name for _, name in ordered],
        rxclass_id=defn.rxclass_id,
        atc_codes=list(defn.atc_codes),
        notes=defn.notes,
    )


def build_manifest(results: list[SeedResult], *, fetched_at: str) -> dict:
    """Assemble the final drug_classes.json payload."""
    classes: dict[str, dict] = {}
    for r in results:
        classes[r.class_id] = r.to_dict()

    total_members = sum(len(r.member_rxcuis) for r in results)

    return {
        "_metadata": {
            "schema_version": "1.0.0",
            "description": "Drug class expansion map for interaction matching (class:X → RxCUIs)",
            "purpose": "interaction_db_class_expansion",
            "last_updated": fetched_at.split("T")[0],
            "total_classes": len(results),
            "total_members": total_members,
            "data_source_metadata": {
                "sources": ["NLM RxClass (ATC)"],
                "fetched_at": fetched_at,
                "relaSource": "ATC",
                "ttys_filter": "IN",
                "api_base": RXCLASS_BASE,
                "update_frequency": "annual_or_on_demand",
            },
            "seed_runbook": {
                "summary": "Regenerate via: python3 scripts/api_audit/seed_drug_classes.py --live",
                "dry_run_command": "python3 scripts/api_audit/seed_drug_classes.py --dry-run",
                "live_command": "python3 scripts/api_audit/seed_drug_classes.py --live",
            },
            "usage": "Referenced by build_interaction_db.py when expanding class:X agents at build time. Missing class → blocks build.",
        },
        "classes": classes,
    }


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Seed drug_classes.json via the NLM RxClass API")
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--live", action="store_true", help="Call RxClass and write output file")
    mode.add_argument("--dry-run", action="store_true", help="Print plan without making network calls")
    p.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data" / "drug_classes.json",
        help="Output JSON path (default: scripts/data/drug_classes.json)",
    )
    p.add_argument(
        "--min-members",
        type=int,
        default=1,
        help="Fail if any class returns fewer than this many members (default 1)",
    )
    return p.parse_args(argv)


def _print_plan() -> None:
    print("RxClass seed plan — 24 drug classes")
    print("-" * 70)
    for defn in CLASS_DEFINITIONS:
        codes = "+".join(defn.atc_codes)
        print(f"  {defn.class_id:<38} ATC={codes}")
    print("-" * 70)
    print(f"Total classes: {len(CLASS_DEFINITIONS)}")
    print("Run with --live to fetch from https://rxnav.nlm.nih.gov/REST/rxclass")


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    if args.dry_run:
        _print_plan()
        return 0

    # Live mode
    fetched_at = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    print(f"Seeding {len(CLASS_DEFINITIONS)} classes from RxClass…", file=sys.stderr)

    results: list[SeedResult] = []
    failures: list[str] = []

    for defn in CLASS_DEFINITIONS:
        print(f"  [{defn.class_id}] ", end="", file=sys.stderr, flush=True)
        result = seed_one(defn)
        count = len(result.member_rxcuis)
        print(f"{count} members", file=sys.stderr)
        if count < args.min_members:
            failures.append(f"{defn.class_id}: only {count} members (required ≥{args.min_members})")
        results.append(result)

    if failures:
        print("\nFAILURES:", file=sys.stderr)
        for f in failures:
            print(f"  ✗ {f}", file=sys.stderr)
        return 1

    manifest = build_manifest(results, fetched_at=fetched_at)

    # Write with trailing newline and deterministic formatting
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    total_members = manifest["_metadata"]["total_members"]
    print(
        f"\n✓ Wrote {args.output} — {len(results)} classes, {total_members} total members",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
