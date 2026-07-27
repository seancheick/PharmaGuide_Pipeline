#!/usr/bin/env python3
"""Fail-closed content gate for reviewed medication-depletion citations.

Existence checks prove that a PMID resolves.  They do *not* prove that the
paper is about the medication--nutrient relationship for which it is cited.
This gate evaluates an explicitly reviewed expectation contract against the
live PubMed title and abstract.  It deliberately never promotes a source to
``verified``: keyword matching is a regression detector, not clinical review.

Only citations explicitly present in the contract are evaluated.  A reviewed
section can therefore be protected immediately without pretending that legacy
unreviewed citations have been content audited.  ``--require-coverage`` is
available for the eventual whole-corpus gate and fails for every cited PMID
that lacks a reviewed expectation.

Exit codes with ``--live``:
  0  every evaluated citation content-matched and the contract was valid
  1  content mismatch, missing expectation, or abstract unavailable
  2  PubMed was transiently unavailable after the client's retries
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any, Callable

SCRIPT_DIR = Path(__file__).resolve().parent
SCRIPTS_ROOT = SCRIPT_DIR.parent
DATA_DIR = SCRIPTS_ROOT / "data"
DEFAULT_CONTRACT = DATA_DIR / "medication_depletion_citation_expectations.json"
DEFAULT_DEPLETIONS = DATA_DIR / "medication_depletions.json"
PMID_RE = re.compile(r"pubmed\.ncbi\.nlm\.nih\.gov/(\d+)")
SUPPRESSED_STATUSES = {"needs_revision", "rejected"}


def normalize_text(value: str | None) -> str:
    """Normalize punctuation, hyphens, and Unicode before concept matching."""
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(char for char in value if not unicodedata.combining(char))
    value = value.lower().replace("β", "beta")
    value = re.sub(r"[‐‑‒–—―-]", " ", value)
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


def _contains(text: str, term: str) -> bool:
    normalized = normalize_text(term)
    return bool(normalized) and f" {normalized} " in f" {text} "


def _matches_any(text: str, terms: list[str]) -> bool:
    return any(_contains(text, term) for term in terms)


def _matches_all(text: str, terms: list[str]) -> bool:
    return all(_contains(text, term) for term in terms)


def classify_article(article: dict[str, Any] | None, expectation: dict[str, Any]) -> dict[str, Any]:
    """Classify one fetched article without changing any clinical data.

    A title is useful diagnostic context but is not enough to content-verify a
    claim.  A missing abstract is therefore explicitly ``abstract_unavailable``
    and keeps the release gate red rather than silently accepting title overlap.
    """
    if not article or not str(article.get("abstract") or "").strip():
        return {
            "status": "abstract_unavailable",
            "reason": "PubMed record has no usable abstract",
        }

    expected = expectation.get("expected") or {}
    text = normalize_text(
        f"{article.get('title') or ''} {article.get('abstract') or ''} "
        f"{' '.join(article.get('mesh_terms') or [])}"
    )
    missing: list[str] = []
    if not _matches_any(text, list(expected.get("drug_terms_any") or [])):
        missing.append("drug_terms_any")
    if not _matches_any(text, list(expected.get("nutrient_terms_any") or [])):
        missing.append("nutrient_terms_any")
    if not _matches_all(text, list(expected.get("required_terms_all") or [])):
        missing.append("required_terms_all")
    context_terms = list(expected.get("context_terms_any") or [])
    if context_terms and not _matches_any(text, context_terms):
        missing.append("context_terms_any")
    disqualifying = [term for term in expected.get("disqualifying_terms_any") or [] if _contains(text, term)]
    if disqualifying:
        missing.append("disqualifying_terms_any=" + ", ".join(disqualifying))

    if missing:
        return {"status": "content_mismatch", "reason": "; ".join(missing)}
    return {"status": "content_match", "reason": "all reviewed concepts matched"}


def _pmids_for_entry(entry: dict[str, Any]) -> set[str]:
    return {
        match.group(1)
        for source in entry.get("sources", [])
        if (match := PMID_RE.search(str(source.get("url") or "")))
    }


def validate_contract(
    expectations: list[dict[str, Any]], entries: list[dict[str, Any]], *, require_coverage: bool = False
) -> list[str]:
    """Validate authored review expectations against the canonical data file."""
    by_id = {str(entry.get("id")): entry for entry in entries}
    errors: list[str] = []
    covered: set[tuple[str, str]] = set()
    for item in expectations:
        entry_id, pmid = str(item.get("entry_id") or ""), str(item.get("pmid") or "")
        expected = item.get("expected") or {}
        if not entry_id or not pmid.isdigit():
            errors.append(f"malformed expectation: entry_id={entry_id!r}, pmid={pmid!r}")
            continue
        if item.get("reviewer_disposition") != "verified_for_claim":
            errors.append(f"{entry_id}/{pmid}: reviewer_disposition must be verified_for_claim")
        if not expected.get("drug_terms_any") or not expected.get("nutrient_terms_any"):
            errors.append(f"{entry_id}/{pmid}: medication and nutrient expectations are required")
        entry = by_id.get(entry_id)
        if not entry:
            errors.append(f"{entry_id}/{pmid}: referenced entry is absent")
            continue
        if entry.get("citation_review_status") != "verified":
            errors.append(f"{entry_id}/{pmid}: entry is not citation_review_status=verified")
        if pmid not in _pmids_for_entry(entry):
            errors.append(f"{entry_id}/{pmid}: PMID is not an authored source on the entry")
        covered.add((entry_id, pmid))

    if require_coverage:
        for entry in entries:
            if entry.get("citation_review_status") != "verified":
                continue
            entry_id = str(entry.get("id") or "")
            for pmid in _pmids_for_entry(entry):
                if (entry_id, pmid) not in covered:
                    errors.append(f"{entry_id}/{pmid}: verified citation has no reviewed expectation")
    return errors


def audit_expectations(
    expectations: list[dict[str, Any]], fetch_article: Callable[[str], dict[str, Any] | None]
) -> list[dict[str, Any]]:
    """Fetch and evaluate contracts; transient fetch exceptions remain distinct."""
    results: list[dict[str, Any]] = []
    for expectation in expectations:
        pmid = str(expectation["pmid"])
        try:
            article = fetch_article(pmid)
            outcome = classify_article(article, expectation)
        except Exception as exc:  # the client already retries; this is unresolved
            outcome = {"status": "transient_api_failure", "reason": str(exc)}
        results.append({
            "entry_id": expectation["entry_id"],
            "pmid": pmid,
            "title": (article or {}).get("title", "") if "article" in locals() else "",
            **outcome,
        })
    return results


def decide_exit(contract_errors: list[str], results: list[dict[str, Any]]) -> int:
    if contract_errors:
        return 1
    if any(result["status"] == "transient_api_failure" for result in results):
        return 2
    if any(result["status"] != "content_match" for result in results):
        return 1
    return 0


def _load_article_fixture(path: Path) -> dict[str, dict[str, Any]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {str(pmid): article for pmid, article in raw.items()}


def _live_fetcher() -> Callable[[str], dict[str, Any] | None]:
    sys.path.insert(0, str(SCRIPT_DIR))
    from pubmed_client import PubMedClient, parse_pubmed_article_xml

    client = PubMedClient()

    def fetch(pmid: str) -> dict[str, Any] | None:
        articles = parse_pubmed_article_xml(client.efetch([pmid]))
        return next((article for article in articles if article.get("pmid") == pmid), None)

    return fetch


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--depletions", type=Path, default=DEFAULT_DEPLETIONS)
    parser.add_argument("--live", action="store_true", help="fetch title/abstracts from PubMed")
    parser.add_argument("--fixture", type=Path, help="offline PMID-to-article JSON fixture (test use)")
    parser.add_argument("--require-coverage", action="store_true", help="fail if a verified PubMed citation lacks a contract")
    parser.add_argument("--entry-id", action="append", dest="entry_ids", help="evaluate only one reviewed entry (repeatable)")
    args = parser.parse_args(argv)
    if args.live and args.fixture:
        parser.error("--live and --fixture are mutually exclusive")

    contract = json.loads(args.contract.read_text(encoding="utf-8"))
    expectations = list(contract.get("expectations") or [])
    if args.entry_ids:
        selected = set(args.entry_ids)
        expectations = [item for item in expectations if item.get("entry_id") in selected]
        if not expectations:
            print("No contract expectations match --entry-id.", file=sys.stderr)
            return 1
    entries = json.loads(args.depletions.read_text(encoding="utf-8")).get("depletions") or []
    contract_errors = validate_contract(expectations, entries, require_coverage=args.require_coverage)
    if contract_errors:
        print("CONTRACT ERRORS:", file=sys.stderr)
        for error in contract_errors:
            print(f"  - {error}", file=sys.stderr)
    if not (args.live or args.fixture):
        print(f"Validated {len(expectations)} reviewed citation expectations (dry run).")
        return 1 if contract_errors else 0

    fixture = _load_article_fixture(args.fixture) if args.fixture else None
    fetch = (lambda pmid: fixture.get(pmid)) if fixture is not None else _live_fetcher()
    results = audit_expectations(expectations, fetch)
    for result in results:
        print(f"{result['status']:24} {result['entry_id']} PMID {result['pmid']} — {result['reason']}")
    return decide_exit(contract_errors, results)


if __name__ == "__main__":
    raise SystemExit(run())
