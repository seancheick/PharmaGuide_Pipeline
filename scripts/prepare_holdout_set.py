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

*It never lets a model's reading become a value.* No provider is called here.
`diff` will compare an existing draft against a catalog record, because a list
of disputed rows is what makes a human check finish in minutes instead of
hours — but it only ever prints rows for a person to settle. Nothing a model
read is written anywhere near a gold label.

*It never edits a product already in the manifest.* The set is frozen once
scoring begins; correcting a mistake is a deliberate act with a dated
amendment, not a silent overwrite.

    python3 scripts/prepare_holdout_set.py init  reports/submission_holdout
    python3 scripts/prepare_holdout_set.py add   reports/submission_holdout \
        --key northwind-magnesium --family "Northwind/magnesium" \
        --split development --case unit_mg --case nested_blend \
        --photo ~/captures/front.jpg --photo ~/captures/facts.jpg
    python3 scripts/prepare_holdout_set.py status reports/submission_holdout
    python3 scripts/prepare_holdout_set.py scan --barcode 048107092900
    python3 scripts/prepare_holdout_set.py diff --dsld-id 1059 --draft run/d-1.json
"""
from __future__ import annotations

import argparse
import hashlib
from datetime import datetime, timezone
import json
import os
import sys
import tempfile
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from submission_review.extraction.benchmark import (  # noqa: E402
    MANIFEST_SCHEMA,
    _inside,
    _statement_present,
    _norm,
    _sha,
    REQUIRED_CASES,
    SPLITS,
    BenchmarkError,
    _TOKEN,
    load_gold,
)
from submission_review.extraction.catalog_gold import (  # noqa: E402
    CASE_SOURCES,
    Disagreement,
    printed_rows,
    gold_rows,
    other_ingredients_text,
    verify_fingerprint,
    case_counts,
    disagreements,
    _record_path,
    scan as scan_barcodes,
    thin_cases,
)
from submission_review.gtin import canonical_gtin14_candidates  # noqa: E402
from submission_review.extraction.envelope import (  # noqa: E402
    DISCLOSURE_HINTS,
    LabelDraftError,
    validate_label_draft_v1,
)
from submission_review.extraction.development import (  # noqa: E402
    gold_template,
    intake_manifest_entry,
)

#: Defaults shared with the reviewer console, which owns identity lookup.
CATALOG_DB = Path("scripts/dist/pharmaguide_core.db")
PRODUCTS_DIR = Path("scripts/products")
BLOBS_DIR = Path("scripts/dist/detail_blobs")

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


def _atomic_write_json(target: Path, payload: dict, *, prefix: str) -> None:
    # A laptop sleep, disk-full error, or interrupted process must not leave a
    # truncated file that hides an otherwise valid frozen set. Replace the
    # completed file atomically in the same directory.
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    fd, temporary = tempfile.mkstemp(prefix=prefix, dir=target.parent, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    except BaseException:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def _save(root: Path, manifest: dict) -> None:
    _atomic_write_json(_manifest_path(root), manifest, prefix=".manifest.")


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
    if not _TOKEN.fullmatch(key):
        raise HoldoutSetError(
            "key must be a path-safe token (letters, digits, '.', '_' or '-')"
        )
    if not family.strip() or "/" not in family:
        raise HoldoutSetError("family must be a nonempty 'brand/line' value")
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

    stored = []
    try:
        destination.mkdir(parents=True)
        for index, photo in enumerate(photos):
            target = destination / f"{index:02d}{photo.suffix.lower()}"
            target.write_bytes(photo.read_bytes())
            stored.append(target)

        entry = intake_manifest_entry(key, family, split, stored, root)
        entry["cases"] = sorted(set(cases))
        gold_path.write_text(
            json.dumps(gold_template(key), indent=2) + "\n", encoding="utf-8"
        )

        manifest["products"].append(entry)
        _save(root, manifest)
    except BaseException:
        # The directory and gold file were created only by this invocation, so
        # clean them on any failed write and leave the set self-consistent.
        for path in stored:
            try:
                path.unlink()
            except OSError:
                pass
        try:
            destination.rmdir()
        except OSError:
            pass
        try:
            gold_path.unlink()
        except OSError:
            pass
        raise
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

    counts = case_counts(e["cases"] for e in products if e["split"] == "holdout")
    covered = set(counts)
    thin = thin_cases(counts)
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
    """Whether the gold record is valid enough for the benchmark loader.

    ``status`` is an operator-facing preview before the manifest is frozen, so
    it deliberately validates the current gold bytes rather than requiring
    the template-time ``gold_sha256`` in the manifest.  All semantic checks
    still come from ``benchmark.load_gold``; maintaining a smaller predicate
    here had allowed status to disagree with the actual scorer.
    """
    path = root / entry["gold"]
    if not path.exists():
        return False
    try:
        current = dict(entry)
        current["gold_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        load_gold(root, current)
    except (OSError, ValueError, BenchmarkError):
        return False
    return True


def _by_source(cases) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {"catalog": [], "capture": [], "sourcing": []}
    for case in sorted(cases):
        grouped[CASE_SOURCES[case]].append(case)
    return grouped


def scan(barcodes: list[str], catalog_db: Path, products_dir: Path,
         blobs_dir: Path, *, as_json: bool = False) -> int:
    """Report what the catalog already knows about bottles you can hold."""
    from submission_review.serve import build_identity_index

    if not barcodes:
        raise HoldoutSetError("give at least one --barcode, or --barcodes-file")
    if not as_json:
        print(f"Building the identity index from {catalog_db} and {products_dir} "
              "(this takes about a minute)…", file=sys.stderr)
    index = build_identity_index(catalog_db, products_dir)
    results = scan_barcodes(barcodes, index, blobs_dir)

    # Counted once per barcode, and only where one record matched. A barcode
    # with two candidate editions covers nothing until a person says which
    # edition is in their hand.
    counts = case_counts(r.candidates[0].cases for r in results if len(r.candidates) == 1)
    if as_json:
        json.dump({
            "scanned": [
                {"barcode": r.barcode, "canonical": list(r.canonical), "note": r.note,
                 "candidates": [
                     {"dsld_id": c.dsld_id, "brand": c.brand_name, "product_name": c.product_name,
                      "serving": c.serving, "active_rows": c.active_rows,
                      "formula_fingerprint": c.formula_fingerprint,
                      "source_name": c.source_name, "source_date": c.source_date,
                      "catalog_version": c.catalog_version, "cases": sorted(c.cases)}
                     for c in r.candidates]}
                for r in results],
            "case_counts": counts,
            "thin": thin_cases(counts),
            "case_sources": CASE_SOURCES,
        }, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0

    matched = [r for r in results if r.matched]
    print(f"\n{len(matched)} of {len(results)} barcode(s) matched a catalog record.\n")
    for result in results:
        if not result.matched:
            if not result.canonical:
                # Not a product without a record: not a barcode at all.
                print(f"  {result.barcode:<16} unreadable — {result.note}")
                print("  " + " " * 16 + "  rescan it; nothing was looked up\n")
                continue
            print(f"  {result.barcode:<16} no match — not in the catalog")
            print("  " + " " * 16 + "  this one needs the two-person transcription route\n")
            continue
        for candidate in result.candidates:
            print(f"  {result.barcode:<16} candidate  dsld:{candidate.dsld_id}")
            print(f"  {'':<16}   {candidate.brand_name} — {candidate.product_name}")
            print(f"  {'':<16}   serving {candidate.serving or 'unknown'}"
                  f" · {candidate.active_rows} active row(s)")
            print(f"  {'':<16}   covers: "
                  + (", ".join(sorted(candidate.cases)) or "no required case"))
            print(f"  {'':<16}   source: {candidate.source_name or 'unknown'}"
                  f" {candidate.source_date or ''}".rstrip())
        if result.note:
            print(f"  {'':<16}   NOTE: {result.note}")
        print(f"  {'':<16}   confirm against the bottle before using it: brand, product")
        print(f"  {'':<16}   name, serving size and row count. The record's version and")
        print(f"  {'':<16}   date identify the record, not the package — they cannot")
        print(f"  {'':<16}   confirm the edition you are holding.\n")

    grouped = _by_source(REQUIRED_CASES)
    thin = set(thin_cases(counts))
    print("Required cases, two products each:\n")
    have = [c for c in grouped["catalog"] if c not in thin]
    need = [c for c in grouped["catalog"] if c in thin]
    print("  covered by these records   "
          + (", ".join(f"{c} ({counts[c]})" for c in have) or "none yet"))
    print("  still short                "
          + (", ".join(f"{c} ({counts.get(c, 0)})" for c in need) or "none"))
    print("\n  the record cannot say — you decide these when you photograph:")
    print("    " + ", ".join(grouped["capture"]))
    print("\n  the record cannot say — you have to find such a label:")
    print("    " + ", ".join(grouped["sourcing"]))
    ambiguous = [r.barcode for r in results if len(r.candidates) > 1]
    if ambiguous:
        print("\n  not counted, edition unresolved: " + ", ".join(ambiguous))
    print("\nA match is a candidate, never a decision. The physical label wins.")
    return 0


def diff(dsld_id: str, draft_path: Path, blobs_dir: Path, *, as_json: bool = False) -> int:
    """List only the rows a person has to settle between record and photograph."""
    try:
        blob_path = _record_path(dsld_id, blobs_dir)
    except ValueError as error:
        raise HoldoutSetError(str(error)) from error
    if not blob_path.is_file():
        raise HoldoutSetError(f"no catalog record {dsld_id} under {blobs_dir}")
    if not draft_path.is_file():
        raise HoldoutSetError(f"no draft at {draft_path}")
    blob = json.loads(blob_path.read_text(encoding="utf-8"))
    # Validated through the one draft contract before it is read at all: an
    # arbitrary file is not a draft, and a malformed one must fail as a
    # message rather than a traceback.
    try:
        draft = validate_label_draft_v1(json.loads(draft_path.read_text(encoding="utf-8")))
    except LabelDraftError as error:
        raise HoldoutSetError(f"{draft_path} is not a valid label_draft_v1: {error}") from error
    found = disagreements(blob, draft)
    if as_json:
        json.dump([vars(d) for d in found], sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0
    if not found:
        print(f"dsld:{dsld_id} and {draft_path.name} agree on every row.")
        print("That is not proof either is right — it is two independent readings")
        print("that did not diverge. Confirm the edition against the bottle.")
        return 0
    print(f"\n{len(found)} row(s) to settle against the photograph:\n")
    for item in found:
        print(f"  {item.kind:<20} {item.row}")
        print(f"  {'':<20}   record: {item.record if item.record is not None else '—'}")
        print(f"  {'':<20}   draft:  {item.draft if item.draft is not None else '—'}")
    print("\nSettle each one by reading the label. Neither side is authoritative.")
    return 0


def _statement_disagreements(statements: list[str], draft: dict) -> list[Disagreement]:
    """Where the typed statements and the photograph's statements differ.

    The operator types what the package prints; the draft read the same
    package. Either side holding a statement the other lacks means one of
    them is wrong, and a warning is not a field to settle by default.
    """
    typed = [_norm(text) for text in statements]
    read = [_norm(item.get("value")) for item in (draft.get("statements") or ())
            if isinstance(item, dict) and item.get("status") == "read" and item.get("value")]
    found = [Disagreement("statement", "typed statement not on the photograph", None, None)
             for text in typed if not _statement_present(text, read)]
    found += [Disagreement("statement", "photographed statement not typed", None, None)
              for text in read if not _statement_present(text, typed)]
    found += [Disagreement("statement", "statement needs a complete reading", None, None)
              for item in (draft.get("statements") or ())
              if isinstance(item, dict) and item.get("status") in ("partial", "unreadable")]
    return found


def import_reference(root: Path, key: str, dsld_id: str, draft_path: Path,
                     reviewer: str, *, confirmed: bool, blobs_dir: Path,
                     barcode: str | None, serving_size: str | None,
                     servings_per_container: str | None,
                     disclosure_hint: str | None,
                     statements: list[str] | None) -> int:
    """Propose a gold record from a catalog transcription a person confirmed.

    The rule that makes this safe is that it refuses every disagreement.
    Where the record and the photographed label agree on every row, no model
    value has entered the gold record and the confirming person never had one
    to be anchored by: they compared a transcription written by someone else
    against the bottle in their hand. Where anything disagrees, that is no
    longer true, and the product goes to the two-person route.
    """
    if not str(reviewer).strip() or str(reviewer).startswith("<"):
        raise HoldoutSetError("--reviewer needs the initials of a real person")
    if not confirmed:
        raise HoldoutSetError(
            "refusing: pass --confirmed-physical-label only after comparing the "
            "record to the package itself. No record can make that judgement.")
    if barcode is not None:
        barcode = str(barcode).strip()
        if not canonical_gtin14_candidates(barcode):
            raise HoldoutSetError(
                "refusing: --barcode must be a valid UPC/EAN/GTIN with a "
                "valid check digit, or be omitted when no barcode is visible")
    for flag, value in (("--serving-size", serving_size),
                        ("--servings-per-container", servings_per_container),
                        *(("--statement", text) for text in (statements or ()))):
        if value is not None and not str(value).strip():
            raise HoldoutSetError(f"refusing: {flag} was given an empty value")
    if statements is None:
        raise HoldoutSetError(
            "refusing: a catalog record does not carry printed directions or "
            "warnings. Pass --statement for each one printed, or --no-statements "
            "if the label prints none. An empty list assumed is a claim nobody made.")
    if (root / "freeze.json").exists():
        raise HoldoutSetError(
            "refusing: this set is frozen. Writing gold now would invalidate "
            "every result scored against it.")

    manifest = _load(root)
    entry = next((e for e in manifest["products"] if e["product_key"] == key), None)
    if entry is None:
        raise HoldoutSetError(f"{key} is not in the manifest; run `add` first")
    if _gold_is_filled(root, entry):
        raise HoldoutSetError(
            f"{key} already has a complete gold record; correcting one is a "
            "dated amendment, never a silent overwrite")
    existing = _inside(root, entry["gold"])
    if existing.exists():
        try:
            current = json.loads(existing.read_text(encoding="utf-8"))
        except ValueError:
            current = None
        if current != gold_template(key):
            raise HoldoutSetError(
                f"refusing: {existing} already holds a transcription someone "
                "started. Only a blank template is replaced; finish or remove "
                "that reading deliberately first.")

    try:
        blob_path = _record_path(dsld_id, blobs_dir)
    except ValueError as error:
        raise HoldoutSetError(str(error)) from error
    if not blob_path.is_file():
        raise HoldoutSetError(f"no catalog record {dsld_id} under {blobs_dir}")
    blob = json.loads(blob_path.read_text(encoding="utf-8"))
    if str(blob.get("dsld_id") or "") != str(dsld_id):
        raise HoldoutSetError(f"{blob_path} does not hold record {dsld_id}")
    try:
        fingerprint = verify_fingerprint(blob)
    except ValueError as error:
        raise HoldoutSetError(f"refusing: {error}") from error

    if not draft_path.is_file():
        raise HoldoutSetError(f"no draft at {draft_path}")
    try:
        draft = validate_label_draft_v1(json.loads(draft_path.read_text(encoding="utf-8")))
    except LabelDraftError as error:
        raise HoldoutSetError(f"{draft_path} is not a valid label_draft_v1: {error}") from error
    # Content is identity. "No disagreements" only means something if the
    # draft read the photographs this product was added with; a draft of
    # another bottle, or a reading of the record itself, would confirm nothing.
    photographed = set()
    for photo in entry.get("photos") or ():
        actual = _sha(_inside(root, photo["path"]))
        if actual != photo["sha256"]:
            raise HoldoutSetError("refusing: a product photograph changed after it was added")
        photographed.add(actual)
    read = set((draft.get("evidence_snapshot") or {}).values())
    if not read or not read <= photographed:
        raise HoldoutSetError(
            f"refusing: {draft_path} is not a reading of this product's "
            "photographs. Its evidence hashes do not match the photographs "
            f"{key} was added with.")

    differences = disagreements(blob, draft) + _statement_disagreements(
        statements, draft)
    if differences:
        # The model's reading is deliberately withheld. The person who
        # settles these is the one about to attest that they compared the
        # record to the package; showing them the model's answer first would
        # make that attestation false.
        record_names = {_norm(row["name"]): row["name"] for row in printed_rows(blob)}
        lines = "\n".join(
            f"    {d.kind:<20} {record_names.get(_norm(d.row), 'label field')}\n"
            f"      record: {d.record or '—'}"
            for d in differences[:12])
        raise HoldoutSetError(
            f"refusing: {len(differences)} row(s) disagree between the record and "
            f"the photographed label.\n{lines}\n"
            "  Settle these by reading the package. If the record is stale, "
            "reformulated, or its edition is ambiguous, this product takes the "
            "two-person transcription route instead.")

    brand = str(blob.get("brand_name") or "")
    if _norm(brand) and _norm(brand) != _norm(entry.get("brand")):
        # Caught here rather than at freeze, where it would surface as an
        # unfreezable set long after the operator has moved on.
        raise HoldoutSetError(
            f"refusing: the record's brand ({brand}) is not the manifest's "
            f"({entry.get('brand')}). Add the product under the brand the "
            "package prints, or this set can never be frozen.")

    record = blob.get("label_record") or {}
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    gold = {
        "schema_version": "gold_label_v1",
        "product_key": key,
        "sourced_from": {
            "source_name": str(record.get("source_name") or "unknown"),
            "source_record_id": str(record.get("source_record_id") or dsld_id),
            "formula_fingerprint": fingerprint,
            "imported_at": stamp,
            # Zero by construction: an import with anything unsettled is refused
            # above, so this can never be a number somebody typed.
            "disagreements_resolved": 0,
        },
        "checked_by": [{
            "checker": reviewer,
            "checked_at": stamp,
            "human": True,
            "independent": True,
            "model_output_seen": False,
            "confirmed_physical_label": True,
        }],
        "expected": "draft",
        "identity": {
            "brand": str(blob.get("brand_name") or "") or None,
            "product_name": str(blob.get("product_name") or "") or None,
            # Digits a person read off the package. A record's barcode would
            # identify the record, which is not the same claim.
            "barcode_digits_seen": barcode,
        },
        "serving": {
            # The printed serving phrase is not in a catalog record: what the
            # record holds is a derived basis. Left null unless a person typed
            # what the panel says.
            "size": serving_size,
            "amount": None,
            "basis_text": None,
            "servings_per_container": servings_per_container,
        },
        "other_ingredients": {
            "text": other_ingredients_text(blob),
            # Scored against the draft, so it must be a reading. A record
            # lists inactive ingredients; it does not say whether the panel
            # printed an "Other Ingredients" line, so nothing is claimed here.
            "disclosure_hint": disclosure_hint,
        },
        "statements": list(statements),
        "rows": gold_rows(blob),
    }

    gold_path = existing
    previous = gold_path.read_bytes() if gold_path.exists() else None
    try:
        _atomic_write_json(gold_path, gold, prefix=f".{key}.")
        entry["gold_sha256"] = _sha(gold_path)
        # The writer's acceptance test is the scorer's own loader, so this
        # command cannot drift from what the benchmark will later accept.
        load_gold(root, entry)
        _save(root, manifest)
    except BaseException:
        if previous is None:
            gold_path.unlink(missing_ok=True)
        else:
            gold_path.write_bytes(previous)
        entry.pop("gold_sha256", None)
        raise

    print(f"Imported dsld:{dsld_id} into {key}: {len(gold['rows'])} printed row(s), "
          f"{len(gold['statements'])} statement(s).")
    print(f"  source      {gold['sourced_from']['source_name']} "
          f"{record.get('source_date') or ''}".rstrip())
    print(f"  fingerprint {fingerprint[:16]}… (recomputed from the record's own panel)")
    print(f"  confirmed   {reviewer} compared the record to the package")
    print("\nThis is a proposed reference, not a verdict. The physical label wins.")
    return 0


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

    node = sub.add_parser("scan", help="match scanned barcodes to catalog records")
    node.add_argument("--barcode", action="append", default=[], dest="barcodes")
    node.add_argument("--barcodes-file", type=Path,
                      help="one barcode per line; blank lines and # comments ignored")
    node.add_argument("--catalog-db", type=Path, default=CATALOG_DB)
    node.add_argument("--products-dir", type=Path, default=PRODUCTS_DIR)
    node.add_argument("--blobs-dir", type=Path, default=BLOBS_DIR)
    node.add_argument("--json", action="store_true", dest="as_json")

    node = sub.add_parser("import-reference",
                          help="propose gold from a confirmed catalog record")
    node.add_argument("root", type=Path)
    node.add_argument("--key", required=True)
    node.add_argument("--dsld-id", required=True)
    node.add_argument("--draft", type=Path, required=True)
    node.add_argument("--reviewer", required=True,
                      help="initials of the person who compared record to package")
    node.add_argument("--confirmed-physical-label", action="store_true", dest="confirmed")
    node.add_argument("--barcode", default=None,
                      help="digits read off the package, not from the record")
    node.add_argument("--serving-size", default=None,
                      help="the serving phrase as the panel prints it")
    node.add_argument("--servings-per-container", default=None)
    node.add_argument("--other-ingredients-disclosure", default=None,
                      choices=sorted(DISCLOSURE_HINTS), dest="disclosure_hint",
                      help="what the panel prints; omitted means no claim")
    node.add_argument("--statement", action="append", default=None, dest="statements",
                      help="repeatable; a printed direction or warning, verbatim")
    node.add_argument("--no-statements", action="store_true",
                      help="the label prints no directions or warnings")
    node.add_argument("--blobs-dir", type=Path, default=BLOBS_DIR)

    node = sub.add_parser("diff", help="rows where a record and a draft disagree")
    node.add_argument("--dsld-id", required=True)
    node.add_argument("--draft", type=Path, required=True)
    node.add_argument("--blobs-dir", type=Path, default=BLOBS_DIR)
    node.add_argument("--json", action="store_true", dest="as_json")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "init":
            return init(args.root)
        if args.command == "status":
            return status(args.root)
        if args.command == "scan":
            barcodes = list(args.barcodes)
            if args.barcodes_file:
                if not args.barcodes_file.is_file():
                    raise HoldoutSetError(f"no barcode list at {args.barcodes_file}")
                barcodes += [
                    line.split("#", 1)[0].strip()
                    for line in args.barcodes_file.read_text(encoding="utf-8").splitlines()
                    if line.split("#", 1)[0].strip()
                ]
            return scan(barcodes, args.catalog_db, args.products_dir,
                        args.blobs_dir, as_json=args.as_json)
        if args.command == "import-reference":
            if args.statements and args.no_statements:
                raise HoldoutSetError("pass --statement or --no-statements, not both")
            statements = [] if args.no_statements else args.statements
            return import_reference(
                args.root, args.key, args.dsld_id, args.draft, args.reviewer,
                confirmed=args.confirmed, blobs_dir=args.blobs_dir,
                barcode=args.barcode, serving_size=args.serving_size,
                servings_per_container=args.servings_per_container,
                disclosure_hint=args.disclosure_hint,
                statements=statements)
        if args.command == "diff":
            return diff(args.dsld_id, args.draft, args.blobs_dir, as_json=args.as_json)
        return add(args.root, args.key, args.family, args.split,
                   args.cases, args.photos)
    except (HoldoutSetError, BenchmarkError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
