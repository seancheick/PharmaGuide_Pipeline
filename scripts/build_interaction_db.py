"""build_interaction_db.py — M2 SQLite builder.

Reads verified drafts (output of verify_interactions.py), research_pairs
(output of ingest_suppai.py), drug_classes.json, and an optional manual
override file, and emits:

    scripts/interaction_db_output/interaction_db.sqlite
    scripts/interaction_db_output/interaction_db_manifest.json
    scripts/interaction_db_output/interaction_audit_report.json

Build artifacts land in the working dir first and are promoted to
scripts/dist/ via release_interaction_artifact.py (T7). See
INTERACTION_DB_SPEC v2.2.0 §6.3 + §0.4 E1–E14 for the full contract.

Design notes:

- Pure stdlib. No new dependencies; sqlite3 is bundled with Python.
- Pure functions with injectable BuildContext for testability.
- Deterministic output:
    * --build-time locks last_updated + metadata timestamps.
    * Row insertion is done in sorted order so page layout is stable.
    * PRAGMA user_version, VACUUM, ANALYZE, integrity_check at the tail.
- Dedup + conflict resolution:
    * Curated drafts > supp.ai > raw imports (supp.ai stays in the
      research_pairs tier; it never enters the interactions table).
    * When two curated drafts collide on the same agent pair the
      more-cautious severity wins per §6.3.3 (severity rank:
      contraindicated > avoid > caution > monitor).
    * Overrides are applied last and beat everything.
- Provenance (§0.4 E3) is derived from the first allow-listed host in
  source_urls — forensically auditable per-entry authority.
- Tombstone columns (§0.4 E4): version_added + version_last_modified are
  stamped on insert; retired_at / retired_reason stay NULL for new rows
  and are populated by future release diffs.
- FTS5 virtual table (§0.4 E5) indexes agent1_name + agent2_name for
  medication autocomplete in M4.

Run:

    python3.13 scripts/build_interaction_db.py \\
        --normalized-drafts scripts/interaction_db_output/normalized.json \\
        --research-pairs   scripts/interaction_db_output/research_pairs.json \\
        --drug-classes     scripts/data/drug_classes.json \\
        --overrides        scripts/data/curated_interactions/interaction_overrides.json \\
        --output           scripts/interaction_db_output/interaction_db.sqlite \\
        --manifest         scripts/interaction_db_output/interaction_db_manifest.json \\
        --report           scripts/interaction_db_output/interaction_audit_report.json \\
        --build-time       "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \\
        --interaction-db-version "v$(date -u +%Y.%m.%d.%H%M%S)"
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

SCHEMA_VERSION = "1.0.0"
SCHEMA_USER_VERSION = 1

# Severity rank for the more-cautious-wins resolver. Higher = more cautious.
SEVERITY_RANK: dict[str, int] = {
    "monitor": 0,
    "caution": 1,
    "avoid": 2,
    "contraindicated": 3,
}

# Allow-listed provenance hosts, in priority order (first match wins).
# Keeps the §0.4 E3 column forensically useful.
PROVENANCE_HOSTS: list[tuple[str, str]] = [
    ("ods.od.nih.gov", "nih_ods"),
    ("nccih.nih.gov", "nccih"),
    ("dailymed.nlm.nih.gov", "dailymed"),
    ("ncbi.nlm.nih.gov/books/NBK", "livertox"),
    ("ncbi.nlm.nih.gov/books", "ncbi_bookshelf"),
    ("pubmed.ncbi.nlm.nih.gov", "pubmed"),
    ("ncbi.nlm.nih.gov", "ncbi"),
]


# --------------------------------------------------------------------------- #
# BuildContext
# --------------------------------------------------------------------------- #


@dataclass
class BuildContext:
    normalized_drafts_path: Path
    research_pairs_path: Path
    drug_classes_path: Path
    overrides_path: Path | None
    output_db: Path
    manifest_path: Path
    report_path: Path
    build_time: str
    interaction_db_version: str
    pipeline_version: str = "0.0.0"
    min_app_version: str = "1.0.0"
    dry_run: bool = False


# --------------------------------------------------------------------------- #
# Loaders
# --------------------------------------------------------------------------- #


def _load_json(path: Path) -> Any:
    with path.open() as fh:
        return json.load(fh)


def load_drafts(path: Path) -> list[dict[str, Any]]:
    payload = _load_json(path)
    if isinstance(payload, list):
        return payload
    return payload.get("interactions", [])


def load_research_pairs(path: Path) -> list[dict[str, Any]]:
    payload = _load_json(path)
    if isinstance(payload, list):
        return payload
    return payload.get("research_pairs", [])


def load_drug_classes(path: Path) -> dict[str, Any]:
    return _load_json(path)


def load_overrides(path: Path | None) -> list[dict[str, Any]]:
    if path is None or not path.exists():
        return []
    payload = _load_json(path)
    if isinstance(payload, list):
        return payload
    return payload.get("overrides", [])


# --------------------------------------------------------------------------- #
# Derivations
# --------------------------------------------------------------------------- #


def build_rxcui_to_class(drug_classes: dict[str, Any]) -> dict[str, str]:
    """Return {rxcui → class_id} from drug_classes.json."""
    out: dict[str, str] = {}
    for class_id, meta in drug_classes.get("classes", {}).items():
        for rxcui in meta.get("member_rxcuis", []):
            out[str(rxcui)] = class_id
    return out


def derive_provenance(source_urls: list[str]) -> str:
    """First allow-listed host match wins; else 'curated_manual'."""
    for url in source_urls:
        try:
            parsed = urlparse(url)
            host_plus_path = (parsed.netloc + parsed.path).lower()
        except Exception:
            host_plus_path = url.lower()
        for marker, tag in PROVENANCE_HOSTS:
            if marker in host_plus_path:
                return tag
    return "curated_manual"


def severity_rank(sev: str) -> int:
    return SEVERITY_RANK.get(sev, -1)


def pair_key(row: dict[str, Any]) -> tuple[str, str]:
    """Deterministic dedup key for two curated rows that describe the same pair."""
    a1, a2 = row["agent1_id"], row["agent2_id"]
    return tuple(sorted((a1, a2)))  # type: ignore[return-value]


def resolve_curated_conflicts(
    drafts: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Merge drafts sharing a pair_key under more-cautious-severity wins.

    Returns (deduped_rows, resolved_conflicts) where every resolved_conflicts
    entry records {pair_key, kept_id, dropped_id, kept_severity, dropped_severity}.
    """
    by_key: dict[tuple[str, str], dict[str, Any]] = {}
    conflicts: list[dict[str, Any]] = []
    for row in drafts:
        key = pair_key(row)
        existing = by_key.get(key)
        if existing is None:
            by_key[key] = row
            continue
        kept, dropped = (
            (row, existing)
            if severity_rank(row["severity"]) > severity_rank(existing["severity"])
            else (existing, row)
        )
        by_key[key] = kept
        conflicts.append(
            {
                "pair_key": list(key),
                "kept_id": kept["id"],
                "dropped_id": dropped["id"],
                "kept_severity": kept["severity"],
                "dropped_severity": dropped["severity"],
            }
        )
    return list(by_key.values()), conflicts


def apply_overrides(
    rows: list[dict[str, Any]], overrides: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], int]:
    """Overrides beat curated. Match by row.id.

    Returns (merged_rows, override_count).
    """
    by_id = {row["id"]: dict(row) for row in rows}
    applied = 0
    for ov in overrides:
        rid = ov.get("id")
        if rid not in by_id:
            # Overrides can inject brand-new rows too, but they need full shape.
            required = {
                "id",
                "type",
                "agent1_name",
                "agent1_id",
                "agent2_name",
                "agent2_id",
                "severity",
                "mechanism",
                "management",
            }
            if required.issubset(ov.keys()):
                by_id[rid] = dict(ov)
                by_id[rid].setdefault("source_urls", [])
                by_id[rid].setdefault("source_pmids", [])
                by_id[rid].setdefault("type_authored", ov.get("type"))
                by_id[rid].setdefault("agent1_type", ov.get("agent1_type", "drug"))
                by_id[rid].setdefault(
                    "agent2_type", ov.get("agent2_type", "supplement")
                )
                by_id[rid].setdefault("agent1_canonical_id", None)
                by_id[rid].setdefault("agent2_canonical_id", None)
                by_id[rid]["source"] = "override"
                applied += 1
            continue
        merged = by_id[rid]
        for key in (
            "severity",
            "mechanism",
            "management",
            "interaction_effect_type",
            "source_urls",
            "source_pmids",
        ):
            if key in ov:
                merged[key] = ov[key]
        merged["source"] = "override"
        by_id[rid] = merged
        applied += 1
    return list(by_id.values()), applied


# --------------------------------------------------------------------------- #
# SQLite schema
# --------------------------------------------------------------------------- #


SCHEMA_SQL = """
CREATE TABLE interactions (
    id                      TEXT PRIMARY KEY,
    agent1_type             TEXT NOT NULL,
    agent1_name             TEXT NOT NULL,
    agent1_id               TEXT NOT NULL,
    agent1_canonical_id     TEXT,
    agent1_drug_class       TEXT,
    agent2_type             TEXT NOT NULL,
    agent2_name             TEXT NOT NULL,
    agent2_id               TEXT NOT NULL,
    agent2_canonical_id     TEXT,
    agent2_drug_class       TEXT,
    severity                TEXT NOT NULL,
    effect_type             TEXT,
    mechanism               TEXT NOT NULL,
    management              TEXT NOT NULL,
    evidence_level          TEXT,
    source_urls_json        TEXT NOT NULL,
    source_pmids_json       TEXT NOT NULL,
    bidirectional           INTEGER DEFAULT 1,
    dose_dependent          INTEGER DEFAULT 0,
    dose_threshold_text     TEXT,
    type_authored           TEXT NOT NULL,
    source                  TEXT NOT NULL,
    provenance              TEXT NOT NULL,
    version_added           TEXT NOT NULL,
    version_last_modified   TEXT NOT NULL,
    retired_at              TEXT,
    retired_reason          TEXT,
    last_updated            TEXT NOT NULL
);

CREATE INDEX idx_int_a1_canon ON interactions(agent1_canonical_id)
    WHERE agent1_canonical_id IS NOT NULL;
CREATE INDEX idx_int_a2_canon ON interactions(agent2_canonical_id)
    WHERE agent2_canonical_id IS NOT NULL;
CREATE INDEX idx_int_a1_id    ON interactions(agent1_type, agent1_id);
CREATE INDEX idx_int_a2_id    ON interactions(agent2_type, agent2_id);
CREATE INDEX idx_int_a1_class ON interactions(agent1_drug_class)
    WHERE agent1_drug_class IS NOT NULL;
CREATE INDEX idx_int_a2_class ON interactions(agent2_drug_class)
    WHERE agent2_drug_class IS NOT NULL;

CREATE VIRTUAL TABLE interactions_fts USING fts5(
    id UNINDEXED,
    agent1_name,
    agent2_name,
    tokenize = 'unicode61 remove_diacritics 2'
);

CREATE TABLE drug_class_map (
    class_id            TEXT PRIMARY KEY,
    class_name          TEXT NOT NULL,
    drug_rxcuis_json    TEXT NOT NULL,
    source              TEXT NOT NULL,
    last_updated        TEXT NOT NULL
);

CREATE TABLE research_pairs (
    pair_id                 TEXT PRIMARY KEY,
    cui_a                   TEXT NOT NULL,
    cui_b                   TEXT NOT NULL,
    entity_a_name           TEXT NOT NULL,
    entity_b_name           TEXT NOT NULL,
    entity_a_type           TEXT NOT NULL,
    entity_b_type           TEXT NOT NULL,
    canonical_id_a          TEXT,
    canonical_id_b          TEXT,
    rxcui_a                 TEXT,
    rxcui_b                 TEXT,
    paper_count             INTEGER NOT NULL,
    human_study_count       INTEGER NOT NULL,
    clinical_study_count    INTEGER NOT NULL,
    top_sentences_json      TEXT NOT NULL,
    top_pmids_json          TEXT NOT NULL,
    latest_paper_year       INTEGER,
    source                  TEXT NOT NULL DEFAULT 'suppai',
    last_updated            TEXT NOT NULL
);

CREATE INDEX idx_rp_canon_a ON research_pairs(canonical_id_a)
    WHERE canonical_id_a IS NOT NULL;
CREATE INDEX idx_rp_canon_b ON research_pairs(canonical_id_b)
    WHERE canonical_id_b IS NOT NULL;
CREATE INDEX idx_rp_cui_a   ON research_pairs(cui_a);
CREATE INDEX idx_rp_cui_b   ON research_pairs(cui_b);
CREATE INDEX idx_rp_rxcui_a ON research_pairs(rxcui_a) WHERE rxcui_a IS NOT NULL;
CREATE INDEX idx_rp_rxcui_b ON research_pairs(rxcui_b) WHERE rxcui_b IS NOT NULL;

CREATE TABLE interaction_db_metadata (
    key     TEXT PRIMARY KEY,
    value   TEXT NOT NULL
);
"""


# --------------------------------------------------------------------------- #
# Row builders
# --------------------------------------------------------------------------- #


def build_interaction_row(
    draft: dict[str, Any],
    *,
    rxcui_to_class: dict[str, str],
    build_time: str,
    interaction_db_version: str,
) -> dict[str, Any]:
    agent1_id = str(draft["agent1_id"])
    agent2_id = str(draft["agent2_id"])
    agent1_drug_class = rxcui_to_class.get(agent1_id)
    agent2_drug_class = rxcui_to_class.get(agent2_id)

    effect_type = draft.get("interaction_effect_type")
    if isinstance(effect_type, str):
        effect_type = effect_type.lower()

    return {
        "id": draft["id"],
        "agent1_type": draft.get("agent1_type") or "unknown",
        "agent1_name": draft["agent1_name"],
        "agent1_id": agent1_id,
        "agent1_canonical_id": draft.get("agent1_canonical_id"),
        "agent1_drug_class": agent1_drug_class,
        "agent2_type": draft.get("agent2_type") or "unknown",
        "agent2_name": draft["agent2_name"],
        "agent2_id": agent2_id,
        "agent2_canonical_id": draft.get("agent2_canonical_id"),
        "agent2_drug_class": agent2_drug_class,
        "severity": draft["severity"],
        "effect_type": effect_type,
        "mechanism": draft["mechanism"],
        "management": draft["management"],
        "evidence_level": draft.get("evidence_level"),
        "source_urls_json": json.dumps(
            draft.get("source_urls", []), sort_keys=True
        ),
        "source_pmids_json": json.dumps(
            draft.get("source_pmids", []), sort_keys=True
        ),
        "bidirectional": 1 if draft.get("bidirectional", True) else 0,
        "dose_dependent": 1 if draft.get("dose_dependent", False) else 0,
        "dose_threshold_text": draft.get("dose_threshold_text"),
        "type_authored": draft.get("type_authored") or draft.get("type"),
        "source": draft.get("source", "curated"),
        "provenance": derive_provenance(draft.get("source_urls", [])),
        "version_added": interaction_db_version,
        "version_last_modified": interaction_db_version,
        "retired_at": None,
        "retired_reason": None,
        "last_updated": build_time,
    }


def build_research_pair_row(pair: dict[str, Any], build_time: str) -> dict[str, Any]:
    top_papers = pair.get("top_papers", [])
    cui_a = pair["cui_a"]
    cui_b = pair["cui_b"]
    # Accept both the normalized test-fixture shape and ingest_suppai's
    # current output (display_name_*, ent_type_*, no pair_id).
    pair_id = pair.get("pair_id") or f"{cui_a}-{cui_b}"
    entity_a_name = pair.get("entity_a_name") or pair.get("display_name_a", "")
    entity_b_name = pair.get("entity_b_name") or pair.get("display_name_b", "")
    entity_a_type = pair.get("entity_a_type") or pair.get("ent_type_a", "supplement")
    entity_b_type = pair.get("entity_b_type") or pair.get("ent_type_b", "supplement")

    # Derive summary counts from top_papers when ingest_suppai didn't pre-compute.
    human_count = pair.get(
        "human_study_count",
        sum(1 for p in top_papers if p.get("human_study")),
    )
    clinical_count = pair.get(
        "clinical_study_count",
        sum(1 for p in top_papers if p.get("clinical_study")),
    )
    latest_year = pair.get("latest_paper_year")
    if latest_year is None and top_papers:
        years = [p.get("year") for p in top_papers if isinstance(p.get("year"), int)]
        latest_year = max(years) if years else None

    # top_pmids may already be a flat list (ingest_suppai) or absent (tests).
    explicit_top_pmids = pair.get("top_pmids")
    if isinstance(explicit_top_pmids, list):
        top_pmids = [str(x) for x in explicit_top_pmids]
    else:
        top_pmids = [str(p["pmid"]) for p in top_papers if p.get("pmid") is not None]

    return {
        "pair_id": pair_id,
        "cui_a": cui_a,
        "cui_b": cui_b,
        "entity_a_name": entity_a_name,
        "entity_b_name": entity_b_name,
        "entity_a_type": entity_a_type,
        "entity_b_type": entity_b_type,
        "canonical_id_a": pair.get("canonical_id_a"),
        "canonical_id_b": pair.get("canonical_id_b"),
        "rxcui_a": pair.get("rxcui_a"),
        "rxcui_b": pair.get("rxcui_b"),
        "paper_count": int(pair.get("paper_count", len(top_papers))),
        "human_study_count": int(human_count),
        "clinical_study_count": int(clinical_count),
        "top_sentences_json": json.dumps(
            pair.get("top_sentences", []), sort_keys=True
        ),
        "top_pmids_json": json.dumps(top_pmids, sort_keys=True),
        "latest_paper_year": latest_year,
        "source": "suppai",
        "last_updated": build_time,
    }


# --------------------------------------------------------------------------- #
# Writer
# --------------------------------------------------------------------------- #


def _column_order(table: str) -> list[str]:
    """Fixed column order per table so INSERT statements are deterministic."""
    if table == "interactions":
        return [
            "id",
            "agent1_type",
            "agent1_name",
            "agent1_id",
            "agent1_canonical_id",
            "agent1_drug_class",
            "agent2_type",
            "agent2_name",
            "agent2_id",
            "agent2_canonical_id",
            "agent2_drug_class",
            "severity",
            "effect_type",
            "mechanism",
            "management",
            "evidence_level",
            "source_urls_json",
            "source_pmids_json",
            "bidirectional",
            "dose_dependent",
            "dose_threshold_text",
            "type_authored",
            "source",
            "provenance",
            "version_added",
            "version_last_modified",
            "retired_at",
            "retired_reason",
            "last_updated",
        ]
    if table == "research_pairs":
        return [
            "pair_id",
            "cui_a",
            "cui_b",
            "entity_a_name",
            "entity_b_name",
            "entity_a_type",
            "entity_b_type",
            "canonical_id_a",
            "canonical_id_b",
            "rxcui_a",
            "rxcui_b",
            "paper_count",
            "human_study_count",
            "clinical_study_count",
            "top_sentences_json",
            "top_pmids_json",
            "latest_paper_year",
            "source",
            "last_updated",
        ]
    if table == "drug_class_map":
        return [
            "class_id",
            "class_name",
            "drug_rxcuis_json",
            "source",
            "last_updated",
        ]
    raise KeyError(table)


def _insert_rows(
    con: sqlite3.Connection, table: str, rows: list[dict[str, Any]]
) -> None:
    if not rows:
        return
    cols = _column_order(table)
    placeholders = ",".join(["?"] * len(cols))
    sql = f"INSERT INTO {table} ({','.join(cols)}) VALUES ({placeholders})"
    con.executemany(sql, [[row.get(c) for c in cols] for row in rows])


def _insert_metadata(con: sqlite3.Connection, kv: dict[str, str]) -> None:
    con.executemany(
        "INSERT INTO interaction_db_metadata (key, value) VALUES (?, ?)",
        sorted(kv.items()),
    )


def _populate_fts(con: sqlite3.Connection, rows: list[dict[str, Any]]) -> None:
    con.executemany(
        "INSERT INTO interactions_fts (id, agent1_name, agent2_name) VALUES (?, ?, ?)",
        [(r["id"], r["agent1_name"], r["agent2_name"]) for r in rows],
    )


def _sqlite_bytes_hash(db: Path) -> str:
    return hashlib.sha256(db.read_bytes()).hexdigest()


# --------------------------------------------------------------------------- #
# Main driver
# --------------------------------------------------------------------------- #


@dataclass
class BuildResult:
    total_interactions: int
    source_drafts_count: int
    source_suppai_count: int
    resolved_conflicts: list[dict[str, Any]] = field(default_factory=list)
    dropped_entries: list[dict[str, Any]] = field(default_factory=list)
    override_count: int = 0
    sha256: str = ""


def run_build(ctx: BuildContext) -> BuildResult:
    drafts = load_drafts(ctx.normalized_drafts_path)
    research_pairs = load_research_pairs(ctx.research_pairs_path)
    drug_classes = load_drug_classes(ctx.drug_classes_path)
    overrides = load_overrides(ctx.overrides_path)

    source_drafts_count = len(drafts)
    source_suppai_count = len(research_pairs)

    deduped, resolved_conflicts = resolve_curated_conflicts(drafts)
    merged, override_count = apply_overrides(deduped, overrides)

    # Deterministic insert order. Research pairs may lack a pre-computed
    # pair_id (ingest_suppai output), so derive the key on-the-fly.
    merged.sort(key=lambda r: r["id"])
    research_pairs_sorted = sorted(
        research_pairs,
        key=lambda r: r.get("pair_id") or f"{r['cui_a']}-{r['cui_b']}",
    )

    rxcui_to_class = build_rxcui_to_class(drug_classes)

    interaction_rows = [
        build_interaction_row(
            draft,
            rxcui_to_class=rxcui_to_class,
            build_time=ctx.build_time,
            interaction_db_version=ctx.interaction_db_version,
        )
        for draft in merged
    ]
    research_rows = [
        build_research_pair_row(pair, build_time=ctx.build_time)
        for pair in research_pairs_sorted
    ]
    class_rows = sorted(
        (
            {
                "class_id": cid,
                "class_name": meta.get("class_name", cid),
                "drug_rxcuis_json": json.dumps(meta.get("member_rxcuis", [])),
                "source": meta.get("source", "rxclass"),
                "last_updated": ctx.build_time,
            }
            for cid, meta in drug_classes.get("classes", {}).items()
        ),
        key=lambda r: r["class_id"],
    )

    result = BuildResult(
        total_interactions=len(interaction_rows),
        source_drafts_count=source_drafts_count,
        source_suppai_count=source_suppai_count,
        resolved_conflicts=resolved_conflicts,
        override_count=override_count,
    )

    if ctx.dry_run:
        _emit_dry_run_summary(ctx, result)
        return result

    ctx.output_db.parent.mkdir(parents=True, exist_ok=True)
    if ctx.output_db.exists():
        ctx.output_db.unlink()

    con = sqlite3.connect(str(ctx.output_db))
    try:
        con.executescript(SCHEMA_SQL)

        _insert_rows(con, "interactions", interaction_rows)
        _populate_fts(con, interaction_rows)
        _insert_rows(con, "research_pairs", research_rows)
        _insert_rows(con, "drug_class_map", class_rows)

        metadata = {
            "schema_version": SCHEMA_VERSION,
            "built_at": ctx.build_time,
            "source_drafts_count": str(source_drafts_count),
            "source_suppai_count": str(source_suppai_count),
            "total_interactions": str(len(interaction_rows)),
            "override_count": str(override_count),
            "resolved_conflict_count": str(len(resolved_conflicts)),
            "interaction_db_version": ctx.interaction_db_version,
            "pipeline_version": ctx.pipeline_version,
            "min_app_version": ctx.min_app_version,
            "sha256_checksum": "pending",
        }
        _insert_metadata(con, metadata)

        con.commit()
        con.execute(f"PRAGMA user_version = {SCHEMA_USER_VERSION}")
        con.execute("VACUUM")
        con.execute("ANALYZE")

        integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise RuntimeError(
                f"sqlite integrity_check failed after build: {integrity!r}"
            )
    finally:
        con.close()

    # Patch sha256_checksum in a separate short-lived connection.
    sha256 = _sqlite_bytes_hash(ctx.output_db)
    con = sqlite3.connect(str(ctx.output_db))
    try:
        con.execute(
            "UPDATE interaction_db_metadata SET value = ? WHERE key = ?",
            (sha256, "sha256_checksum"),
        )
        con.commit()
    finally:
        con.close()
    result.sha256 = sha256

    _write_manifest(ctx, result, integrity="ok")
    _write_report(ctx, result)
    return result


def _write_manifest(
    ctx: BuildContext, result: BuildResult, *, integrity: str
) -> None:
    manifest = {
        "checksum": f"sha256:{result.sha256}",
        "db_version": ctx.interaction_db_version,
        "interaction_db_version": ctx.interaction_db_version,
        "schema_version": SCHEMA_VERSION,
        "pipeline_version": ctx.pipeline_version,
        "min_app_version": ctx.min_app_version,
        "built_at": ctx.build_time,
        "source_drafts_count": result.source_drafts_count,
        "source_suppai_count": result.source_suppai_count,
        "total_interactions": result.total_interactions,
        "integrity": {
            "integrity_check": integrity,
            "user_version": SCHEMA_USER_VERSION,
        },
    }
    ctx.manifest_path.parent.mkdir(parents=True, exist_ok=True)
    ctx.manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    )


def _write_report(ctx: BuildContext, result: BuildResult) -> None:
    report = {
        "build_time": ctx.build_time,
        "total_interactions": result.total_interactions,
        "source_drafts_count": result.source_drafts_count,
        "source_suppai_count": result.source_suppai_count,
        "override_count": result.override_count,
        "resolved_conflicts": result.resolved_conflicts,
        "dropped_entries": result.dropped_entries,
        "sha256": result.sha256,
    }
    ctx.report_path.parent.mkdir(parents=True, exist_ok=True)
    ctx.report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")


def _emit_dry_run_summary(ctx: BuildContext, result: BuildResult) -> None:
    print(
        f"[dry-run] interactions={result.total_interactions} "
        f"drafts={result.source_drafts_count} "
        f"suppai={result.source_suppai_count} "
        f"overrides={result.override_count} "
        f"conflicts={len(result.resolved_conflicts)}",
        file=sys.stderr,
    )


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build interaction_db.sqlite from verified drafts + research_pairs"
    )
    parser.add_argument("--normalized-drafts", type=Path, required=True)
    parser.add_argument("--research-pairs", type=Path, required=True)
    parser.add_argument("--drug-classes", type=Path, required=True)
    parser.add_argument("--overrides", type=Path, default=None)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument(
        "--build-time",
        type=str,
        default=None,
        help="ISO 8601 build timestamp (omit = now UTC). "
        "Required for deterministic byte-identical builds.",
    )
    parser.add_argument(
        "--interaction-db-version",
        type=str,
        required=True,
        help="Human-readable release version string.",
    )
    parser.add_argument("--pipeline-version", type=str, default="0.0.0")
    parser.add_argument("--min-app-version", type=str, default="1.0.0")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    build_time = args.build_time or datetime.now(timezone.utc).isoformat(
        timespec="seconds"
    ).replace("+00:00", "Z")

    ctx = BuildContext(
        normalized_drafts_path=args.normalized_drafts,
        research_pairs_path=args.research_pairs,
        drug_classes_path=args.drug_classes,
        overrides_path=args.overrides,
        output_db=args.output,
        manifest_path=args.manifest,
        report_path=args.report,
        build_time=build_time,
        interaction_db_version=args.interaction_db_version,
        pipeline_version=args.pipeline_version,
        min_app_version=args.min_app_version,
        dry_run=args.dry_run,
    )
    run_build(ctx)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
