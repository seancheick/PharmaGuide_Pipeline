#!/usr/bin/env python3
"""release_interaction_artifact.py — stage the interaction DB release.

Mirrors `release_catalog_artifact.py` for the M2 interaction DB subsystem
(INTERACTION_DB_SPEC v2.2.0 §0.4 E1–E2 + §6.3 step 9). Reads the build
working directory at `scripts/interaction_db_output/` produced by
`build_interaction_db.py`, validates it, and stages a clean set of
artifacts into `scripts/dist/` without disturbing unrelated files that
other releases (catalog) own in the same directory.

    scripts/dist/
      interaction_db.sqlite              # bundled SQLite, schema v1
      interaction_db_manifest.json       # release-contract fields
      INTERACTION_RELEASE_NOTES.md       # human-readable summary

The interaction DB has its own release cadence distinct from the main
pipeline catalog (§0.4 E1) — this script is the boundary. Catalog
releases run `release_catalog_artifact.py`; interaction releases run
this script; both can exist in `scripts/dist/` simultaneously.

## Validation gates

Before staging anything, the script enforces:

1. `interaction_db.sqlite` exists, SQLite opens cleanly, and
   `PRAGMA integrity_check` returns `"ok"`.
2. `interactions` has at least `--min-interactions` rows (default: 15,
   matching the M2 done-gate in §6.5 — curated fixture floor).
3. `drug_class_map` has at least one row.
4. The in-SQLite `interaction_db_metadata` key-value table carries
   `schema_version`, `built_at`, `source_drafts_count`,
   `source_suppai_count`, `total_interactions`,
   `interaction_db_version`, `pipeline_version`, `min_app_version`.
   (`sha256_checksum` is deliberately NOT embedded — storing a file's own
   hash inside the file would invalidate the hash. The manifest is the
   sole source of truth for the DB checksum.)
5. `interaction_db_manifest.json` exists alongside the DB and carries
   the E2 shape: `checksum`, `db_version`, `schema_version`,
   `pipeline_version`, `min_app_version`, `integrity`,
   `interaction_db_version`.
6. The manifest's `interaction_db_version` matches the embedded metadata
   row.
7. The manifest's `total_interactions` matches
   `SELECT COUNT(*) FROM interactions` (when present).
8. The actual SHA-256 of the DB on disk matches the manifest's
   `checksum` field (sha256:<hex> or raw hex both accepted).

Any failure aborts with a non-zero exit code. `scripts/dist/` is left
untouched so a broken build never replaces a good release.

## Atomicity & coexistence

Staging writes into a temporary `<output_dir>/.interaction_staging/`
directory, then moves each file into place with an atomic rename. Any
files owned by other releases (e.g. `pharmaguide_core.db`,
`export_manifest.json`, `RELEASE_NOTES.md` from the catalog) are left
untouched. Only the interaction DB artifacts are replaced.

If the `--output-dir` does not exist, it is created. If staging fails
halfway, the temp directory is cleaned up and the destination is not
modified.

## Usage

    python3 scripts/release_interaction_artifact.py
    python3 scripts/release_interaction_artifact.py \\
        --input-dir  scripts/interaction_db_output \\
        --output-dir scripts/dist \\
        --min-interactions 15 \\
        --print-json

    # Publish the staged release and point the app's hydration pin at it
    # (release_full.sh runs this; see publish_flutter_pin):
    python3 scripts/release_interaction_artifact.py \\
        --output-dir scripts/dist \\
        --publish-flutter-pin "/Users/seancheick/PharmaGuide ai"

Exit codes:
    0   release staged (or published and pinned) successfully
    1   validation failed
    2   unexpected runtime error
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable


DB_FILENAME = "interaction_db.sqlite"
MANIFEST_FILENAME = "interaction_db_manifest.json"
RELEASE_NOTES_FILENAME = "INTERACTION_RELEASE_NOTES.md"
DEFAULT_MIN_INTERACTIONS = 15


class ReleaseValidationError(RuntimeError):
    """Raised when a release candidate fails a validation gate."""


# --------------------------------------------------------------------------- #
# Pure helpers (no side effects beyond reads)
# --------------------------------------------------------------------------- #


def compute_sha256(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def strip_sha256_prefix(value: str | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(f"checksum must be a string, got {type(value).__name__}")
    value = value.strip()
    if value.lower().startswith("sha256:"):
        return value.split(":", 1)[1].strip()
    return value


def ensure_sha256_prefix(value: str | None) -> str | None:
    stripped = strip_sha256_prefix(value)
    if stripped is None:
        return None
    return f"sha256:{stripped}"


def _open_ro(db_path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)


def read_embedded_metadata(db_path: Path) -> dict[str, str]:
    con = _open_ro(db_path)
    try:
        cur = con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='interaction_db_metadata'"
        )
        if cur.fetchone() is None:
            raise ReleaseValidationError(
                f"{db_path.name} is missing the interaction_db_metadata table. "
                "Re-run build_interaction_db.py."
            )
        rows = con.execute(
            "SELECT key, value FROM interaction_db_metadata"
        ).fetchall()
    finally:
        con.close()
    return {str(k): str(v) for k, v in rows}


def count_interactions(db_path: Path) -> int:
    con = _open_ro(db_path)
    try:
        row = con.execute("SELECT COUNT(*) FROM interactions").fetchone()
    finally:
        con.close()
    return int(row[0]) if row else 0


def count_drug_classes(db_path: Path) -> int:
    con = _open_ro(db_path)
    try:
        row = con.execute("SELECT COUNT(*) FROM drug_class_map").fetchone()
    finally:
        con.close()
    return int(row[0]) if row else 0


def count_profile_warning_rules(db_path: Path) -> int:
    con = _open_ro(db_path)
    try:
        row = con.execute("SELECT COUNT(*) FROM profile_warning_rules").fetchone()
    except sqlite3.OperationalError:
        return 0
    finally:
        con.close()
    return int(row[0]) if row else 0


def research_pair_counts(db_path: Path) -> dict[str, int]:
    con = _open_ro(db_path)
    try:
        row = con.execute(
            """
            SELECT
              COUNT(*) AS total,
              SUM(
                CASE
                  WHEN COALESCE(rxcui_a, '') != ''
                    OR COALESCE(rxcui_b, '') != ''
                  THEN 1 ELSE 0
                END
              ) AS bridged,
              SUM(
                CASE
                  WHEN (
                    COALESCE(rxcui_a, '') != ''
                    OR COALESCE(rxcui_b, '') != ''
                  )
                  AND (
                    COALESCE(canonical_id_a, '') != ''
                    OR COALESCE(canonical_id_b, '') != ''
                  )
                  THEN 1 ELSE 0
                END
              ) AS bridged_with_canonical
            FROM research_pairs
            """
        ).fetchone()
    finally:
        con.close()
    if row is None:
        return {"total": 0, "bridged": 0, "bridged_with_canonical": 0}
    return {
        "total": int(row[0] or 0),
        "bridged": int(row[1] or 0),
        "bridged_with_canonical": int(row[2] or 0),
    }


def run_integrity_check(db_path: Path) -> str:
    try:
        con = _open_ro(db_path)
    except sqlite3.DatabaseError as exc:
        return f"open_failed:{exc}"
    try:
        row = con.execute("PRAGMA integrity_check").fetchone()
    except sqlite3.DatabaseError as exc:
        return f"pragma_failed:{exc}"
    finally:
        con.close()
    return str(row[0]) if row else "unknown"


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ReleaseValidationError(message)


REQUIRED_EMBEDDED_KEYS = (
    "schema_version",
    "built_at",
    "source_drafts_count",
    "source_suppai_count",
    "total_interactions",
    "profile_warning_rules_count",
    "profile_warning_rules_version",
    "interaction_db_version",
    "pipeline_version",
    "min_app_version",
)
# NOTE: sha256_checksum is intentionally NOT embedded in interaction_db_metadata.
# Writing the file's own hash into the file would change the file's bytes and
# invalidate the hash. The manifest is the sole source of truth for the hash.

REQUIRED_MANIFEST_KEYS = (
    "checksum",
    "db_version",
    "schema_version",
    "pipeline_version",
    "min_app_version",
    "integrity",
    "interaction_db_version",
    "profile_warning_rules_count",
    "profile_warning_rules_version",
)


def validate_release_candidate(
    *, input_dir: Path, min_interactions: int
) -> dict[str, Any]:
    db_path = input_dir / DB_FILENAME
    manifest_path = input_dir / MANIFEST_FILENAME

    _require(
        db_path.is_file(),
        f"Release candidate missing {DB_FILENAME} at {db_path}. "
        "Run build_interaction_db.py first.",
    )
    _require(
        manifest_path.is_file(),
        f"Release candidate missing {MANIFEST_FILENAME} at {manifest_path}. "
        "Run build_interaction_db.py first.",
    )

    integrity = run_integrity_check(db_path)
    _require(
        integrity == "ok",
        f"SQLite PRAGMA integrity_check returned {integrity!r} for {db_path}. "
        "DB is corrupted or not a valid interaction DB.",
    )

    interactions_count = count_interactions(db_path)
    _require(
        interactions_count >= min_interactions,
        f"Release candidate has only {interactions_count} interactions, "
        f"minimum is {min_interactions}. Refusing to stage a partial release.",
    )

    class_count = count_drug_classes(db_path)
    _require(
        class_count > 0,
        "Release candidate has zero drug_class_map rows. "
        "M4 medication entry screen cannot resolve RXCUI → class without them.",
    )

    profile_warning_rules_count = count_profile_warning_rules(db_path)
    _require(
        profile_warning_rules_count > 0,
        "Release candidate has zero profile_warning_rules rows. Schema-3 "
        "catalog warning references would be unresolvable.",
    )

    embedded = read_embedded_metadata(db_path)
    missing_embedded = [k for k in REQUIRED_EMBEDDED_KEYS if k not in embedded]
    _require(
        not missing_embedded,
        f"Embedded interaction_db_metadata missing required keys: "
        f"{', '.join(missing_embedded)}. Re-run build_interaction_db.py.",
    )

    try:
        manifest = json.loads(manifest_path.read_text())
    except json.JSONDecodeError as exc:
        raise ReleaseValidationError(
            f"{MANIFEST_FILENAME} is not valid JSON: {exc}"
        ) from exc

    missing_manifest = [k for k in REQUIRED_MANIFEST_KEYS if k not in manifest]
    _require(
        not missing_manifest,
        f"{MANIFEST_FILENAME} is missing required keys: "
        f"{', '.join(missing_manifest)}. Re-run build_interaction_db.py.",
    )

    _require(
        manifest["interaction_db_version"] == embedded["interaction_db_version"],
        f"interaction_db_version mismatch: manifest="
        f"{manifest['interaction_db_version']!r}, embedded="
        f"{embedded['interaction_db_version']!r}. Release integrity broken.",
    )

    if "total_interactions" in manifest:
        _require(
            int(manifest["total_interactions"]) == interactions_count,
            f"total_interactions mismatch: manifest="
            f"{manifest['total_interactions']}, actual_rows={interactions_count}.",
        )
    _require(
        int(embedded["profile_warning_rules_count"])
        == profile_warning_rules_count,
        "profile_warning_rules row count disagrees with embedded metadata",
    )
    _require(
        int(manifest["profile_warning_rules_count"])
        == profile_warning_rules_count,
        "profile_warning_rules row count disagrees with manifest",
    )
    _require(
        manifest["profile_warning_rules_version"]
        == embedded["profile_warning_rules_version"],
        "profile_warning_rules version disagrees between manifest and metadata",
    )

    research_counts = research_pair_counts(db_path)
    source_suppai_count = int(embedded["source_suppai_count"])
    _require(
        research_counts["total"] == source_suppai_count,
        "research_pairs row count disagrees with embedded source_suppai_count: "
        f"research_pairs={research_counts['total']}, "
        f"source_suppai_count={source_suppai_count}.",
    )
    if source_suppai_count > 0:
        _require(
            research_counts["bridged_with_canonical"] > 0,
            "research_pairs are bundled but no row has both a supplement "
            "canonical_id and a bridged drug RxCUI. Tier 2 would be "
            "unreachable from medication-aware Flutter paths.",
        )

    actual_checksum = compute_sha256(db_path)
    manifest_checksum = strip_sha256_prefix(manifest["checksum"])
    _require(
        manifest_checksum == actual_checksum,
        f"SHA-256 mismatch: manifest says {manifest_checksum}, "
        f"actual is {actual_checksum}. DB modified after manifest written.",
    )

    return {
        "db_path": db_path,
        "manifest_path": manifest_path,
        "manifest": manifest,
        "embedded_metadata": embedded,
        "checksum_sha256": actual_checksum,
        "interactions_count": interactions_count,
        "drug_class_count": class_count,
        "profile_warning_rules_count": profile_warning_rules_count,
        "research_pair_counts": research_counts,
        "integrity": integrity,
    }


# --------------------------------------------------------------------------- #
# Staging
# --------------------------------------------------------------------------- #


def build_release_manifest(
    *, source_manifest: dict[str, Any], checksum_sha256: str
) -> dict[str, Any]:
    release = dict(source_manifest)
    release["checksum"] = ensure_sha256_prefix(checksum_sha256)
    release["checksum_sha256"] = strip_sha256_prefix(checksum_sha256)
    release["release_staged_at"] = datetime.now(timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    return release


def build_release_notes(
    *, manifest: dict[str, Any], embedded: dict[str, str], checksum_sha256: str
) -> str:
    return (
        "# PharmaGuide Interaction DB Release Notes\n"
        "\n"
        f"- interaction_db_version: `{manifest.get('interaction_db_version')}`\n"
        f"- schema_version:         `{manifest.get('schema_version')}`\n"
        f"- pipeline_version:       `{manifest.get('pipeline_version')}`\n"
        f"- min_app_version:        `{manifest.get('min_app_version')}`\n"
        f"- built_at:               `{embedded.get('built_at')}`\n"
        f"- total_interactions:     {embedded.get('total_interactions')}\n"
        f"- source_drafts_count:    {embedded.get('source_drafts_count')}\n"
        f"- source_suppai_count:    {embedded.get('source_suppai_count')}\n"
        f"- profile_warning_rules:  {embedded.get('profile_warning_rules_count')} "
        f"(v{embedded.get('profile_warning_rules_version')})\n"
        f"- checksum_sha256:        `{checksum_sha256}`\n"
        "\n"
        "This release is an independent asset from `pharmaguide_core.db`\n"
        "and ships on its own cadence. The Flutter repo imports it via\n"
        "the Drift interaction database binding (M3).\n"
    )


def stage_release(
    *, validation: dict[str, Any], output_dir: Path
) -> dict[str, Any]:
    """Write the validated release into output_dir without wiping siblings.

    Strategy: write each artifact into a sibling `.interaction_staging` dir,
    self-verify, then move the files into output_dir. Unrelated files in
    output_dir are left untouched — this is the key difference from the
    catalog release script, which owns its whole output dir.
    """
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    staging_dir = output_dir / ".interaction_staging"
    if staging_dir.exists():
        shutil.rmtree(staging_dir)
    staging_dir.mkdir()

    try:
        dest_db = staging_dir / DB_FILENAME
        dest_manifest = staging_dir / MANIFEST_FILENAME
        dest_notes = staging_dir / RELEASE_NOTES_FILENAME

        shutil.copy2(validation["db_path"], dest_db)

        release_manifest = build_release_manifest(
            source_manifest=validation["manifest"],
            checksum_sha256=validation["checksum_sha256"],
        )
        dest_manifest.write_text(
            json.dumps(release_manifest, indent=2, sort_keys=True) + "\n"
        )

        dest_notes.write_text(
            build_release_notes(
                manifest=release_manifest,
                embedded=validation["embedded_metadata"],
                checksum_sha256=validation["checksum_sha256"],
            )
        )

        staged_checksum = compute_sha256(dest_db)
        if staged_checksum != validation["checksum_sha256"]:
            raise ReleaseValidationError(
                f"Staged DB checksum {staged_checksum} does not match source "
                f"{validation['checksum_sha256']}. Copy corrupted."
            )

        # Atomic promotion: move each file into output_dir.
        final_db = output_dir / DB_FILENAME
        final_manifest = output_dir / MANIFEST_FILENAME
        final_notes = output_dir / RELEASE_NOTES_FILENAME

        for final in (final_db, final_manifest, final_notes):
            if final.exists():
                final.unlink()

        dest_db.rename(final_db)
        dest_manifest.rename(final_manifest)
        dest_notes.rename(final_notes)
    finally:
        if staging_dir.exists():
            shutil.rmtree(staging_dir, ignore_errors=True)

    return {
        "output_dir": output_dir,
        "db_path": output_dir / DB_FILENAME,
        "manifest_path": output_dir / MANIFEST_FILENAME,
        "release_notes_path": output_dir / RELEASE_NOTES_FILENAME,
        "checksum_sha256": validation["checksum_sha256"],
        "interactions_count": validation["interactions_count"],
        "drug_class_count": validation["drug_class_count"],
        "profile_warning_rules_count": validation[
            "profile_warning_rules_count"
        ],
        "interaction_db_version": validation["manifest"].get("interaction_db_version"),
        "schema_version": validation["manifest"].get("schema_version"),
    }


# --------------------------------------------------------------------------- #
# Publication: the release asset the Flutter app hydrates from
# --------------------------------------------------------------------------- #
#
# The app does not commit interaction_db.sqlite. Its tool/fetch_interaction_db.sh
# hydrates the file at build time from the GitHub Release asset named by the pin
# tool/interaction_db.release.json, and refuses when that pin disagrees with the
# staged manifest. The Flutter importer moves only the manifest, so a pin left
# behind fails every app build and CI run at hydration (1.0.11 on 2026-09-12,
# 1.0.12 on 2026-09-22). The release train publishes the staged asset and moves
# the pin with the bundle.

FLUTTER_PIN_RELPATH = Path("tool") / "interaction_db.release.json"
RELEASE_TAG_PREFIX = "clinical-db-"


def pin_names_manifest(pin: dict[str, Any], manifest: dict[str, Any]) -> bool:
    """The identity keys the app's hydration script compares, pin vs manifest."""
    return (
        pin.get("sha256") == strip_sha256_prefix(manifest.get("checksum_sha256"))
        and pin.get("interaction_db_version") == manifest.get("interaction_db_version")
        and pin.get("schema_version") == manifest.get("schema_version")
    )


def next_release_tag(existing_tags: list[str], day: str) -> str:
    base = f"{RELEASE_TAG_PREFIX}{day}"
    taken = [
        int(tag[len(base) + 1 :])
        for tag in existing_tags
        if tag.startswith(base + ".") and tag[len(base) + 1 :].isdigit()
    ]
    return f"{base}.{max(taken, default=0) + 1}"


def _gh(args: list[str]) -> str:
    result = subprocess.run(["gh", *args], capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args[:2])} failed: {result.stderr.strip()}")
    return result.stdout


def _download_sha256(url: str) -> str:
    h = hashlib.sha256()
    with urllib.request.urlopen(url, timeout=300) as response:
        for chunk in iter(lambda: response.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _pipeline_head() -> tuple[str, bool]:
    """HEAD of this checkout, and whether a remote-tracking branch contains it."""

    def git(*args: str) -> str:
        return subprocess.run(
            ["git", *args],
            check=True,
            capture_output=True,
            text=True,
            cwd=Path(__file__).resolve().parent,
        ).stdout.strip()

    head = git("rev-parse", "HEAD")
    return head, bool(git("branch", "-r", "--contains", head))


def publish_flutter_pin(
    *,
    dist_dir: Path,
    flutter_repo: Path,
    gh: Callable[[list[str]], str] = _gh,
    download_sha256: Callable[[str], str] = _download_sha256,
    pipeline_head: Callable[[], tuple[str, bool]] = _pipeline_head,
    today: str | None = None,
) -> dict[str, str]:
    """Make the app's hydration pin name the staged interaction DB.

    A no-op without network access when it already does. Otherwise reuse the
    clinical-db release whose asset carries the staged digest, or publish the
    next clinical-db-YYYY.MM.DD.N; download the asset and check its sha256; then
    rewrite only the pin's artifact-identity fields. Any failure leaves the pin
    untouched.
    """
    pin_path = flutter_repo / FLUTTER_PIN_RELPATH
    pin = json.loads(pin_path.read_text(encoding="utf-8"))
    manifest_path = dist_dir / MANIFEST_FILENAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    checksum = strip_sha256_prefix(manifest.get("checksum_sha256"))
    _require(
        bool(checksum and re.fullmatch(r"[0-9a-f]{64}", checksum)),
        f"{manifest_path} carries no checksum_sha256",
    )
    if pin_names_manifest(pin, manifest):
        return {"action": "current", "tag": str(pin.get("tag"))}

    db_path = dist_dir / DB_FILENAME
    _require(
        compute_sha256(db_path) == checksum,
        f"{db_path} does not match its manifest checksum {checksum}",
    )
    repo = pin["repo"]
    releases = [
        release
        for release in json.loads(gh(["api", f"repos/{repo}/releases?per_page=100"]))
        if release["tag_name"].startswith(RELEASE_TAG_PREFIX)
    ]
    carrying = next(
        (
            release
            for release in releases
            # A draft's assets are not publicly downloadable.
            if not release.get("draft")
            and any(
                asset.get("name") == DB_FILENAME
                and asset.get("digest") == f"sha256:{checksum}"
                for asset in release.get("assets", [])
            )
        ),
        None,
    )
    if carrying is not None:
        tag = carrying["tag_name"]
        target = str(carrying.get("target_commitish", ""))
        commit = target if re.fullmatch(r"[0-9a-f]{40}", target) else pipeline_head()[0]
        action = "reused"
    else:
        commit, pushed = pipeline_head()
        tag = next_release_tag(
            [release["tag_name"] for release in releases],
            today or date.today().strftime("%Y.%m.%d"),
        )
        create = [
            "release", "create", tag,
            "--repo", repo,
            "--title", f"Clinical interaction DB {tag[len(RELEASE_TAG_PREFIX):]}",
            "--notes-file", str(dist_dir / RELEASE_NOTES_FILENAME),
        ]
        if pushed:
            create += ["--target", commit]
        gh([*create, str(db_path), str(manifest_path)])
        action = "published"

    url = f"https://github.com/{repo}/releases/download/{tag}/{DB_FILENAME}"
    downloaded = download_sha256(url)
    _require(
        downloaded == checksum,
        f"downloaded {url} hashes to {downloaded}, not the staged {checksum}",
    )

    pin.update(
        tag=tag,
        url=url,
        sha256=checksum,
        size_bytes=db_path.stat().st_size,
        pipeline_commit=commit,
        interaction_db_version=manifest.get("interaction_db_version"),
        schema_version=manifest.get("schema_version"),
    )
    tmp_path = pin_path.with_name(pin_path.name + ".tmp")
    tmp_path.write_text(json.dumps(pin, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp_path, pin_path)
    return {"action": action, "tag": tag}


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Stage the interaction DB release artifact."
    )
    p.add_argument(
        "--input-dir",
        default="scripts/interaction_db_output",
        help="Build working directory (default: scripts/interaction_db_output).",
    )
    p.add_argument(
        "--output-dir",
        default="scripts/dist",
        help="Release staging directory (default: scripts/dist).",
    )
    p.add_argument(
        "--min-interactions",
        type=int,
        default=DEFAULT_MIN_INTERACTIONS,
        help=(
            f"Minimum interactions row count required in interactions table "
            f"(default: {DEFAULT_MIN_INTERACTIONS})."
        ),
    )
    p.add_argument(
        "--print-json",
        action="store_true",
        help="Print the staging result as JSON on stdout.",
    )
    p.add_argument(
        "--publish-flutter-pin",
        metavar="FLUTTER_REPO",
        help=(
            "Instead of staging: publish the release in --output-dir as a "
            "clinical-db GitHub Release asset (reused when one already carries "
            "it) and point FLUTTER_REPO's tool/interaction_db.release.json at it."
        ),
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    input_dir = Path(args.input_dir).resolve()
    output_dir = Path(args.output_dir).resolve()

    if args.publish_flutter_pin:
        flutter_repo = Path(args.publish_flutter_pin).resolve()
        try:
            result = publish_flutter_pin(dist_dir=output_dir, flutter_repo=flutter_repo)
        except ReleaseValidationError as exc:
            print(f"[interaction-release] PUBLICATION REFUSED: {exc}", file=sys.stderr)
            return 1
        except Exception as exc:  # noqa: BLE001
            print(
                f"[interaction-release] UNEXPECTED ERROR during publication: {exc}",
                file=sys.stderr,
            )
            return 2
        if result["action"] == "current":
            print(
                "[interaction-release] hydration pin already names the staged "
                f"interaction DB ({result['tag']})"
            )
        else:
            print(
                f"[interaction-release] {result['action']} {result['tag']}; "
                f"hydration pin → {flutter_repo / FLUTTER_PIN_RELPATH}"
            )
        return 0

    try:
        validation = validate_release_candidate(
            input_dir=input_dir, min_interactions=args.min_interactions
        )
    except ReleaseValidationError as exc:
        print(f"[interaction-release] VALIDATION FAILED: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001
        print(
            f"[interaction-release] UNEXPECTED ERROR during validation: {exc}",
            file=sys.stderr,
        )
        return 2

    try:
        result = stage_release(validation=validation, output_dir=output_dir)
    except ReleaseValidationError as exc:
        print(f"[interaction-release] STAGING FAILED: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001
        print(
            f"[interaction-release] UNEXPECTED ERROR during staging: {exc}",
            file=sys.stderr,
        )
        return 2

    if args.print_json:
        printable = {
            k: (str(v) if isinstance(v, Path) else v) for k, v in result.items()
        }
        print(json.dumps(printable, indent=2, sort_keys=True))
    else:
        print(f"[interaction-release] staged → {result['output_dir']}")
        print(
            f"[interaction-release]   interaction_db_version = "
            f"{result['interaction_db_version']}"
        )
        print(
            f"[interaction-release]   schema_version         = "
            f"{result['schema_version']}"
        )
        print(
            f"[interaction-release]   total_interactions     = "
            f"{result['interactions_count']}"
        )
        print(
            f"[interaction-release]   drug_class_count       = "
            f"{result['drug_class_count']}"
        )
        print(
            f"[interaction-release]   checksum_sha256        = "
            f"{result['checksum_sha256']}"
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
