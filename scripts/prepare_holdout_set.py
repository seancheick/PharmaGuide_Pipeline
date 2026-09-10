#!/usr/bin/env python3
"""Assemble the frozen photo benchmark set, one real product at a time.

The protocol is `scripts/submission_review/HOLDOUT.md` and the scorer is
`extraction/benchmark.py`. Both already existed; what did not was any way for a
person to build the set they describe without writing Python. This is that way,
and nothing more: it hashes photographs, writes manifest rows, and leaves a
blank gold record for a human to fill in.

Three things it will not do, because each one would quietly destroy the value
of the benchmark:

*It never fills a gold label.* Every value has to come off the photograph by
eye, twice, by two people who have not seen a model's answer. A prefilled
template is the fastest way to turn a check into a rubber stamp.

*It never reads a model.* No provider is called here, and no draft is imported.

*It never edits a product already in the manifest.* The set is frozen once
scoring begins; correcting a mistake is a deliberate act with a dated
amendment, not a silent overwrite.

    python3 scripts/prepare_holdout_set.py init  reports/submission_holdout
    python3 scripts/prepare_holdout_set.py add   reports/submission_holdout \
        --key northwind-magnesium --family "Northwind/magnesium" \
        --split development --case unit_mg --case nested_blend \
        --photo ~/captures/front.jpg --photo ~/captures/facts.jpg
    python3 scripts/prepare_holdout_set.py status reports/submission_holdout
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from submission_review.extraction.benchmark import (  # noqa: E402
    MANIFEST_SCHEMA,
    REQUIRED_CASES,
    SPLITS,
)
from submission_review.extraction.development import (  # noqa: E402
    gold_template,
    intake_manifest_entry,
)

#: What a qualifying set contains, from the frozen protocol.
REQUIRED_COUNTS = {"development": 20, "holdout": 40}


class HoldoutSetError(RuntimeError):
    """The requested change would violate the protocol."""


def _manifest_path(root: Path) -> Path:
    return root / "manifest.json"


def _load(root: Path) -> dict:
    path = _manifest_path(root)
    if not path.exists():
        raise HoldoutSetError(f"no manifest at {path}; run `init` first")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != MANIFEST_SCHEMA:
        raise HoldoutSetError(f"manifest schema must be {MANIFEST_SCHEMA}")
    return manifest


def _save(root: Path, manifest: dict) -> None:
    _manifest_path(root).write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def init(root: Path) -> int:
    if _manifest_path(root).exists():
        raise HoldoutSetError(f"{_manifest_path(root)} already exists")
    (root / "photos").mkdir(parents=True, exist_ok=True)
    (root / "gold").mkdir(parents=True, exist_ok=True)
    _save(root, {"schema_version": MANIFEST_SCHEMA, "products": []})
    print(f"Created {root}/ with photos/ and gold/.")
    print("This directory holds real product photographs: keep it out of git.")
    return 0


def add(root: Path, key: str, family: str, split: str,
        cases: list[str], photos: list[Path]) -> int:
    manifest = _load(root)
    if split not in SPLITS:
        raise HoldoutSetError(f"split must be one of {', '.join(SPLITS)}")
    unknown = sorted(set(cases) - REQUIRED_CASES)
    if unknown:
        raise HoldoutSetError(f"unknown case label(s): {', '.join(unknown)}")
    if any(entry["product_key"] == key for entry in manifest["products"]):
        # Correcting a product is a dated amendment, never a silent overwrite.
        raise HoldoutSetError(f"{key} is already in the manifest")
    for photo in photos:
        if not photo.is_file():
            raise HoldoutSetError(f"no such photograph: {photo}")

    # Everything is checked against the source bytes before a single file is
    # written. An add that fails half way leaves photographs on disk that no
    # manifest row mentions, and the next `status` cannot see them to say so.
    seen = {photo["sha256"]: entry["product_key"]
            for entry in manifest["products"] for photo in entry["photos"]}
    digests = []
    for photo in photos:
        digest = hashlib.sha256(photo.read_bytes()).hexdigest()
        if digest in seen:
            raise HoldoutSetError(
                f"that photograph is already used by {seen[digest]}")
        if digest in digests:
            raise HoldoutSetError(f"{photo} was given twice")
        digests.append(digest)

    gold_path = root / "gold" / f"{key}.json"
    if gold_path.exists():
        raise HoldoutSetError(f"{gold_path} already exists")
    destination = root / "photos" / key
    if destination.exists():
        raise HoldoutSetError(f"{destination} already exists")

    destination.mkdir(parents=True)
    stored = []
    for index, photo in enumerate(photos):
        target = destination / f"{index:02d}{photo.suffix.lower()}"
        target.write_bytes(photo.read_bytes())
        stored.append(target)

    entry = intake_manifest_entry(key, family, split, stored, root)
    entry["cases"] = sorted(set(cases))
    gold_path.write_text(
        json.dumps(gold_template(key), indent=2) + "\n", encoding="utf-8")

    manifest["products"].append(entry)
    _save(root, manifest)
    print(f"Added {key} to {split} with {len(stored)} photograph(s).")
    print(f"Now fill in {gold_path} by eye, twice, independently.")
    return 0


def status(root: Path) -> int:
    manifest = _load(root)
    products = manifest["products"]
    print(f"{len(products)} product(s) in {root}")
    for split in SPLITS:
        have = sum(1 for e in products if e["split"] == split)
        need = REQUIRED_COUNTS[split]
        mark = "ok" if have == need else f"needs {need - have} more" if have < need else "OVER"
        print(f"  {split:<12} {have:>3} / {need:<3} {mark}")

    incomplete = [e["product_key"] for e in products if not _gold_is_filled(root, e)]
    print(f"  gold filled  {len(products) - len(incomplete):>3} / {len(products)}")

    covered = {c for e in products if e["split"] == "holdout" for c in e["cases"]}
    thin = sorted(
        case for case in REQUIRED_CASES
        if sum(1 for e in products if e["split"] == "holdout" and case in e["cases"]) < 2
    )
    print(f"  case cover   {len(covered):>3} / {len(REQUIRED_CASES)} seen in holdout")
    if thin:
        # Two holdout products per case, including the expected abstentions.
        print(f"\nCases still needing two holdout products:\n  {', '.join(thin)}")
    if incomplete:
        print(f"\nGold labels still blank ({len(incomplete)}):\n  "
              + ", ".join(incomplete[:12])
              + (" …" if len(incomplete) > 12 else ""))
    if not thin and not incomplete and all(
        sum(1 for e in products if e["split"] == s) == REQUIRED_COUNTS[s] for s in SPLITS
    ):
        print("\nThe set is complete. Freeze it, then score a candidate with "
              "extraction/benchmark.py.")
    return 0


def _gold_is_filled(root: Path, entry: dict) -> bool:
    """A gold record still holding its placeholders is not a reading."""
    path = root / entry["gold"]
    if not path.exists():
        return False
    try:
        gold = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return False
    checkers = gold.get("checked_by") or []
    if len(checkers) != 2:
        return False
    initials = [str(c.get("checker", "")) for c in checkers]
    if any(not i or i.startswith("<") for i in initials):
        return False
    # Two people, not one person twice: the whole point of the second read.
    if initials[0].strip().lower() == initials[1].strip().lower():
        return False
    if any(c.get("model_output_seen") for c in checkers):
        return False
    return bool((gold.get("identity") or {}).get("brand"))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("init", "status"):
        node = sub.add_parser(name)
        node.add_argument("root", type=Path)
    node = sub.add_parser("add")
    node.add_argument("root", type=Path)
    node.add_argument("--key", required=True)
    node.add_argument("--family", required=True,
                      help="brand/family, e.g. \"Northwind/magnesium\"")
    node.add_argument("--split", required=True, choices=SPLITS)
    node.add_argument("--case", action="append", default=[], dest="cases",
                      help=f"repeatable; one of: {', '.join(sorted(REQUIRED_CASES))}")
    node.add_argument("--photo", action="append", default=[], dest="photos",
                      type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "init":
            return init(args.root)
        if args.command == "status":
            return status(args.root)
        return add(args.root, args.key, args.family, args.split,
                   args.cases, args.photos)
    except HoldoutSetError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
