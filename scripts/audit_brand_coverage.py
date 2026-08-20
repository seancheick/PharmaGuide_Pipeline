#!/usr/bin/env python3
"""Compare downloaded brand datasets against live DSLD on-market counts.

Answers one question: "did we actually download every on-market label for the
brands we track, or did something get silently skipped?"

The count check is cheap (one API call per brand). The `--ids` check is the
honest one: matching COUNTS can hide drift, because one product going
off-market while another appears nets to zero. `--ids` pages the real DSLD
label IDs and diffs the sets.

Brand query derivation
----------------------
The DSLD `brand` filter matches by prefix, and a single brand folder usually
holds several sub-brand strings ("GNC", "GNC Mega Men", "GNC Beyond Raw"...).
So the query term is the longest common WORD prefix of every `brandName` in
the folder, case-insensitively.

That matters: a naive "shortest brandName" would pick "CVS Health" and miss
"CVS Pharmacy", or "Goli Bites" and miss "Goli Nutrition". The word-prefix
derivation returns "CVS" and "Goli" and finds all of them.

Use --brand-map to override a folder whose derivation is wrong; a non-zero
delta on a brand you believe is complete is usually a derivation problem, not
missing data, so check the derived query column first.

Examples
--------
    # Full check, all brands (fast, counts only)
    python3 scripts/audit_brand_coverage.py

    # Prove set membership, not just counts, on the brands most likely to drift
    python3 scripts/audit_brand_coverage.py --ids --targets GNC,BulkSupplements

    # Include off-market labels in the comparison
    python3 scripts/audit_brand_coverage.py --status 2

Freshness
---------
A brand can be 100% complete against DSLD and still fail in a store.

`entryDate` is DSLD's BATCH-LOAD date, not the manufacturer's filing date. DSLD
loads monthly (the 20th-25th); across the local corpus there are 156 distinct
entryDate values, one per month, and they stop at 2025-09-25. So:

  * A brand whose newest label predates the cutoff has not appeared in a recent
    DSLD batch. Its newer shelf SKUs are not obtainable from DSLD at any price.
    Example: CVS tops out at 2023-06-22 in EVERY status (on/off/all), so 2024+
    CVS bottles cannot be scanned however much we download.
  * This is NOT proof the manufacturer stopped filing. It only means DSLD has
    not published those labels. Do not infer manufacturer behaviour from it.
  * DSLD itself has published no batch since 2025-09-25, so EVERY brand is
    missing roughly the last year of product changes, not just the stale ones.

STALE therefore means "complete, but not shelf-current" — partial coverage, not
useless coverage. Older SKUs still on shelf continue to scan correctly.

Exit codes: 0 = every brand matches, 1 = at least one delta, 2 = bad usage.
Freshness never changes the exit code — it is advisory, not a completeness bug.
"""

from __future__ import annotations

import argparse
import collections
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dsld_api_client import DSLDApiClient  # noqa: E402
from dataset_paths import brand_dataset_root  # noqa: E402

DEFAULT_ROOT = brand_dataset_root()

# Mirrors the infrastructure blocklist in batch_run_all_datasets.sh so this
# audit sees exactly the folders the pipeline would process.
SKIP_DIRS = {
    "forms",
    "state",
    "delta",
    "reports",
    "staging",
    ".qodo",
    "__pycache__",
}

# Courtesy pause between DSLD calls. The public API is unauthenticated and
# rate limits aggressively; 3 req/s is the documented ceiling.
REQUEST_PAUSE_SECONDS = 0.35

# Labels loaded on or after this date count as "fresh". A brand whose newest
# label predates it has not appeared in a recent published DSLD batch. That is
# an availability warning, not evidence about manufacturer filing behavior.
DEFAULT_FRESH_SINCE = "2024-01-01"


def scan_folder(folder: Path) -> tuple[collections.Counter, list[str]]:
    """Return distinct `brandName` counts and every `entryDate` in the folder."""
    names: collections.Counter = collections.Counter()
    dates: list[str] = []
    for path in folder.glob("*.json"):
        try:
            label = json.loads(path.read_text())
        except (ValueError, OSError):
            continue
        name = label.get("brandName")
        if name:
            names[name] += 1
        entry = (label.get("entryDate") or "")[:10]
        if entry:
            dates.append(entry)
    return names, dates


def common_word_prefix(names: list[str]) -> str:
    """Longest shared leading word sequence, compared case-insensitively.

    Casing is taken from the first name so the query reads naturally.
    Returns an empty string when no safe shared prefix exists; callers must
    provide an explicit brand-map override instead of guessing.
    """
    if not names:
        return ""
    token_lists = [name.split() for name in names]
    shared: list[str] = []
    for index in range(min(len(tokens) for tokens in token_lists)):
        distinct = {tokens[index].lower() for tokens in token_lists}
        if len(distinct) != 1:
            break
        shared.append(token_lists[0][index])
    return " ".join(shared)


def live_count(client: DSLDApiClient, query: str, status: int) -> int | None:
    response = client.search_filter(size=0, brand=query, status=status)
    stats = response.get("stats") if isinstance(response, dict) else None
    return (stats or {}).get("count")


def live_ids(client: DSLDApiClient, query: str, status: int) -> set[str]:
    """Page every label id for a brand. Slower, but proves set membership."""
    ids: set[str] = set()
    offset = 0
    total: int | None = None
    while True:
        response = client.search_filter(
            size=1000, from_=offset, brand=query, status=status
        )
        hits = response.get("hits") or []
        if total is None:
            total = (response.get("stats") or {}).get("count") or 0
        if not hits:
            break
        for hit in hits:
            ids.add(str(hit.get("_id")))
        offset += len(hits)
        time.sleep(REQUEST_PAUSE_SECONDS)
        if offset >= total:
            break
    return ids


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--root", default=str(DEFAULT_ROOT), help="Dataset root")
    parser.add_argument(
        "--targets", default="", help="Comma-separated folder substrings to limit to"
    )
    parser.add_argument(
        "--status",
        type=int,
        choices=[0, 1, 2],
        default=1,
        help="DSLD market status (1=on market, 0=off market, 2=all). Default 1.",
    )
    parser.add_argument(
        "--ids",
        action="store_true",
        help="Diff real label IDs instead of counts. Slower; proves set membership.",
    )
    parser.add_argument(
        "--fresh-since",
        default=DEFAULT_FRESH_SINCE,
        help=f"Date a label counts as fresh from (default {DEFAULT_FRESH_SINCE})",
    )
    parser.add_argument(
        "--brand-map",
        default=None,
        help='JSON file of {"folder_name": "DSLD brand query"} overrides',
    )
    args = parser.parse_args()

    root = Path(args.root)
    if not root.is_dir():
        print(f"ERROR: dataset root not found: {root}", file=sys.stderr)
        return 2

    overrides: dict[str, str] = {}
    if args.brand_map:
        overrides = json.loads(Path(args.brand_map).read_text())

    targets = [t.strip() for t in args.targets.split(",") if t.strip()]

    folders = sorted(
        p
        for p in root.iterdir()
        if p.is_dir() and p.name not in SKIP_DIRS and not p.name.startswith("xOld")
    )
    if targets:
        folders = [p for p in folders if any(t in p.name for t in targets)]
    if not folders:
        print("ERROR: no brand folders matched", file=sys.stderr)
        return 2

    client = DSLDApiClient()
    status_label = {0: "off-mkt", 1: "on-mkt", 2: "all"}[args.status]

    counts_cols = f"{'delta':>7}" if not args.ids else f"{'missing':>8} {'gone':>6}"
    header = (
        f"{'brand':26} {'on disk':>8} {'LIVE ' + status_label:>13} {counts_cols} "
        f"{'newest':>12} {'%fresh':>7}"
    )
    print(header)
    print("-" * len(header))

    total_disk = 0
    total_live = 0
    problems: list[str] = []
    stale_brands: list[str] = []

    for folder in folders:
        on_disk_ids = {p.stem for p in folder.glob("*.json")}
        on_disk = len(on_disk_ids)
        if on_disk == 0:
            print(f"{folder.name:26} {'0':>8} {'-':>13}   (empty folder)")
            continue

        names, dates = scan_folder(folder)
        query = overrides.get(folder.name) or common_word_prefix(list(names))
        if not query:
            # The folder is an operator-reviewed brand boundary. Its slug is a
            # safer fallback than choosing one arbitrary raw sub-brand.
            query = folder.name.replace("_", " ").replace("-", " ")
        if not query:
            print(
                f"{folder.name:26} {on_disk:>8} {'ERROR':>13}   "
                "no safe brand query; add --brand-map override"
            )
            problems.append(f"{folder.name}: no safe derived brand query")
            continue

        newest = max(dates) if dates else "-"
        fresh_pct = (
            100.0 * sum(1 for d in dates if d >= args.fresh_since) / len(dates)
            if dates
            else 0.0
        )
        fresh_col = f"{newest:>12} {fresh_pct:>6.0f}%"
        if newest != "-" and newest < args.fresh_since:
            stale_brands.append(f"{folder.name}: newest label {newest}")

        try:
            if args.ids:
                remote = live_ids(client, query, args.status)
                missing = len(remote - on_disk_ids)
                stale = len(on_disk_ids - remote)
                live = len(remote)
                flag = "  <<<" if (missing or stale) else ""
                print(
                    f"{folder.name:26} {on_disk:>8} {live:>13} "
                    f"{missing:>8} {stale:>6} {fresh_col}{flag}"
                )
                if missing or stale:
                    problems.append(
                        f"{folder.name}: {missing} missing locally, "
                        f"{stale} no longer live (query={query!r})"
                    )
            else:
                live = live_count(client, query, args.status)
                if live is None:
                    print(f"{folder.name:26} {on_disk:>8} {'ERROR':>13} {'?':>7}")
                    problems.append(f"{folder.name}: no count returned")
                    continue
                delta = live - on_disk
                flag = "  <<<" if delta else ""
                print(
                    f"{folder.name:26} {on_disk:>8} {live:>13} {delta:>+7} "
                    f"{fresh_col}{flag}"
                )
                if delta:
                    problems.append(
                        f"{folder.name}: delta {delta:+d} (query={query!r})"
                    )
        except Exception as exc:  # noqa: BLE001 - operator tool, report and continue
            print(f"{folder.name:26} {on_disk:>8} {'ERROR':>13}   {exc}")
            problems.append(f"{folder.name}: {exc}")
            continue

        total_disk += on_disk
        total_live += live
        time.sleep(REQUEST_PAUSE_SECONDS)

    print("-" * len(header))
    print(
        f"TOTALS  on disk={total_disk:,}  live {status_label}={total_live:,}  "
        f"delta={total_live - total_disk:+,}"
    )
    print(f"brands with any delta: {len(problems)}")
    for problem in problems:
        print(f"  - {problem}")

    if stale_brands:
        print(
            f"\nSTALE — complete, but no label appeared in a published DSLD "
            f"batch since {args.fresh_since}. Newer shelf products may be missing:"
        )
        for stale_brand in stale_brands:
            print(f"  - {stale_brand}")

    if problems:
        print(
            "\nA non-zero delta is usually one of: new labels published since the "
            "last download, labels that left the market, or a wrong derived "
            "query. Check the derived query before assuming missing data.",
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
