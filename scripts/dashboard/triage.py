"""Local triage state for dashboard findings (review annotations only, no scoring data).

Lives outside the index builds (``scripts/.cache/dashboard_review/triage.sqlite``) so a
rebuild never wipes it. An "Accepted exception" is scoped to the rule version and an
optional config-fingerprint scope and expiry; outside that scope it reads as Open.
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import closing
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

from scripts.dashboard.score_index import SCRIPTS_ROOT

STATUSES = ["Open", "Expected", "Investigating", "Fixed in candidate", "Resolved", "Accepted exception"]
RESOLVED_BY_RUN = "Resolved by run"
_SCHEMA = """
CREATE TABLE IF NOT EXISTS triage (
    finding_id TEXT PRIMARY KEY,
    rule_id TEXT NOT NULL,
    rule_version INTEGER NOT NULL,
    status TEXT NOT NULL,
    owner TEXT,
    notes TEXT,
    config_scope TEXT,
    review_by TEXT,
    updated_at TEXT NOT NULL
)
"""


def default_path() -> Path:
    root = os.environ.get("PG_DASHBOARD_REVIEW") or SCRIPTS_ROOT / ".cache" / "dashboard_review"
    return Path(root) / "triage.sqlite"


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute(_SCHEMA)
    return conn


def set_status(finding_id: str, rule_id: str, rule_version: int, status: str, *, owner: str | None = None,
               notes: str | None = None, config_scope: str | None = None, review_by: str | None = None,
               path: Path | None = None) -> None:
    if status not in STATUSES:
        raise ValueError(f"unknown triage status {status!r}")
    with closing(_connect(path or default_path())) as conn, conn:
        conn.execute(
            "INSERT INTO triage VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(finding_id) DO UPDATE SET "
            "rule_id=excluded.rule_id, rule_version=excluded.rule_version, status=excluded.status, "
            "owner=excluded.owner, notes=excluded.notes, config_scope=excluded.config_scope, "
            "review_by=excluded.review_by, updated_at=excluded.updated_at",
            (finding_id, rule_id, int(rule_version), status, owner, notes, config_scope, review_by,
             datetime.now(timezone.utc).isoformat(timespec="seconds")),
        )


def load(path: Path | None = None) -> pd.DataFrame:
    with closing(_connect(path or default_path())) as conn:
        return pd.read_sql_query("SELECT * FROM triage", conn)


def effective_status(row: dict, *, config_versions: list[str], today: date | None = None) -> str:
    """Triage status as it applies to the current finding (``row`` has triage + finding fields)."""
    status = row.get("status")
    if not isinstance(status, str) or not status:
        return "Open"
    if status == "Accepted exception":
        if int(row.get("rule_version") or -1) != int(row.get("finding_rule_version") or -2):
            return "Open"
        scope = row.get("config_scope")
        if not isinstance(scope, str) or not scope or scope not in config_versions:
            return "Open"
        review_by = row.get("review_by")
        if isinstance(review_by, str) and review_by:
            try:
                if (today or date.today()) > date.fromisoformat(review_by[:10]):
                    return "Open"
            except ValueError:
                return "Open"  # an unreadable review date cannot keep an exception closed
    return status


def merge(findings: pd.DataFrame, *, config_versions: list[str], path: Path | None = None,
          run_configs: dict[str, list[str]] | None = None) -> pd.DataFrame:
    """Current findings plus triage, plus triaged findings absent from the newest run."""
    triage = load(path)
    if findings.empty and triage.empty:
        return findings
    out = findings.merge(triage.drop(columns=["rule_id"]).rename(columns={"rule_version": "triage_rule_version"}),
                         on="finding_id", how="left") if not findings.empty else findings.copy()
    if not out.empty:
        out["triage_status"] = [
            effective_status({**row, "rule_version": row.get("triage_rule_version"),
                              "finding_rule_version": row.get("rule_version")}, config_versions=([row["config_fingerprint"]] if row.get("config_fingerprint")
                                               else [] if pd.notna(row.get("dsld_id"))
                                               else (run_configs or {}).get(row.get("run_key"), config_versions)))
            for row in out.to_dict("records")
        ]
    gone = triage[~triage["finding_id"].isin(findings["finding_id"] if not findings.empty else [])]
    if not gone.empty:
        resolved = gone.assign(
            triage_status=[RESOLVED_BY_RUN if status != "Accepted exception" else "Accepted exception"
                           for status in gone["status"]],
            message="(not present in the newest run)")
        out = pd.concat([out, resolved], ignore_index=True)
    return out
