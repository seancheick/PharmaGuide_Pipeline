#!/usr/bin/env python3
"""Generate a pair-change journal from discovered enriched/scored outputs."""

import argparse
import json
from datetime import datetime, timezone

from build_all_final_dbs import (
    compute_pair_state,
    discover_pairs,
    load_state_file,
    save_state_file,
)


def build_journal_entries(current_state, previous_state, changed_at):
    entries = []
    all_prefixes = sorted(set(current_state.keys()) | set(previous_state.keys()))

    for prefix in all_prefixes:
        current = current_state.get(prefix)
        previous = previous_state.get(prefix)

        if current and not previous:
            change_type = "new"
            source = current
        elif previous and not current:
            change_type = "removed"
            source = previous
        elif current and previous and (
            current.get("combined_fingerprint") != previous.get("combined_fingerprint")
        ):
            change_type = "changed"
            source = current
        else:
            continue

        entries.append(
            {
                "prefix": prefix,
                "change_type": change_type,
                "changed_at": changed_at,
                "enriched_dir": source.get("enriched_dir"),
                "scored_dir": source.get("scored_dir"),
                "combined_fingerprint": source.get("combined_fingerprint"),
            }
        )

    return entries


def write_change_journal_and_state(journal_path, state_path, entries, current_state, scan_dir):
    journal_payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scan_dir": scan_dir,
        "entry_count": len(entries),
        "entries": entries,
    }
    with open(journal_path, "w", encoding="utf-8") as f:
        json.dump(journal_payload, f, indent=2, sort_keys=True)

    save_state_file(state_path, current_state)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Generate pair_change_journal.json from discovered enriched/scored outputs."
    )
    parser.add_argument(
        "--scan-dir",
        default="scripts",
        help="Directory to scan for output_*_enriched/scored folders",
    )
    parser.add_argument(
        "--journal-path",
        default=None,
        help="Where to write the generated pair-change journal JSON",
    )
    parser.add_argument(
        "--state-file",
        default=None,
        help="Fingerprint state file used to detect changed/new/removed pairs",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    journal_path = args.journal_path or f"{args.scan_dir}/pair_change_journal.json"
    state_file = args.state_file or f"{args.scan_dir}/pair_source_state.json"

    enriched_dirs, scored_dirs, paired, _, _ = discover_pairs(args.scan_dir)
    current_state = compute_pair_state(enriched_dirs, scored_dirs, paired)
    previous_state = load_state_file(state_file)
    changed_at = datetime.now(timezone.utc).isoformat()
    entries = build_journal_entries(current_state, previous_state, changed_at)

    write_change_journal_and_state(
        journal_path,
        state_file,
        entries,
        current_state,
        scan_dir=args.scan_dir,
    )

    print(
        json.dumps(
            {
                "journal_path": journal_path,
                "state_file": state_file,
                "entry_count": len(entries),
                "changed_prefixes": [entry["prefix"] for entry in entries],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
