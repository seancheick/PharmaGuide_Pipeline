#!/usr/bin/env python3
"""Classify every enricher identity rewrite in a replay capture and measure its impact (read-only).

A rewrite is an ingredient_quality_data row whose canonical_id_before (the cleaner's identity)
differs from canonical_id_after (the enricher's). For each one this records which decision path
produced it, how the two identities relate in the enricher's own registries, whether the printed
label text literally names either identity, and what the rewrite changes downstream:
interaction rules matched, score participation and the displayed name.

    $PG_PYTHON reports/identity_line_20261019/measure_rewrites.py RECORDS_DIR OUT_JSON

RECORDS_DIR is a `replay.py snapshot --full --blob` records directory.
"""
from __future__ import annotations

import collections
import gzip
import json
import re
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from enrich_supplements_v3 import SupplementEnricherV3  # noqa: E402
from identity.interaction import interaction_subject_refs  # noqa: E402
from identity_integrity import normalize_label_display  # noqa: E402


def template(text):
    return re.sub(r"'[^']*'", "X", str(text or ""))


def main():
    records, out = Path(sys.argv[1]), Path(sys.argv[2])
    enricher = SupplementEnricherV3()
    quality_map = enricher.databases["ingredient_quality_map"]
    registry = enricher._current_canonical_identity_registry()
    parent_of = enricher._identity_parent_predicate(quality_map)
    registry_ids = enricher._interaction_registry_ids()
    rules = enricher.databases.get("ingredient_interaction_rules", {}).get("interaction_rules") or []
    rule_index = collections.defaultdict(set)
    for rule in rules:
        ref = rule.get("subject_ref") or {}
        rule_index[(enricher._normalize_interaction_db_key(ref.get("db")), str(ref.get("canonical_id")))].add(rule["id"])

    def db_of(canonical_id, hint=None):
        hint = enricher._normalize_interaction_db_key(hint)
        if hint in registry_ids and canonical_id in registry_ids[hint]:
            return hint
        return next((db for db, ids in registry_ids.items() if canonical_id in ids), hint or "ingredient_quality_map")

    def rules_for(canonical_id, hint=None):
        hits = set()
        for ref in interaction_subject_refs(db_of(canonical_id, hint), canonical_id):
            hits |= rule_index.get(ref, set())
        return hits

    def relation(before, after):
        if parent_of(after, before):
            return "after_is_registered_parent"
        if parent_of(before, after):
            return "after_is_registered_child"
        for db in ("ingredient_quality_map", "botanical_ingredients", "other_ingredients", "standardized_botanicals"):
            try:
                if registry.canonicalize(before, db)[0] == registry.canonicalize(after, db)[0] and before != after:
                    if registry.canonicalize(before, db)[0] != before or registry.canonicalize(after, db)[0] != after:
                        return "registered_equivalent"
            except ValueError:
                pass
        return "unrelated_in_registries"

    resolver = enricher._identity_candidate_resolver(quality_map)
    rows = []
    for path in sorted(records.glob("*.json.gz")):
        pid = path.name[:-8]
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            stages = json.load(handle)
        enriched = stages.get("enriched") or {}
        cleaned_by_path = {
            r.get("raw_source_path"): r
            for r in (stages.get("cleaned") or {}).get("activeIngredients") or []
            if isinstance(r, dict)
        }
        blob_by_path = collections.defaultdict(list)
        for key in ("ingredients", "display_ingredients"):
            for r in (stages.get("blob") or {}).get(key) or []:
                if isinstance(r, dict) and r.get("raw_source_path"):
                    blob_by_path[r["raw_source_path"]].append(r)
        for row in (enriched.get("ingredient_quality_data") or {}).get("ingredients") or []:
            if not isinstance(row, dict):
                continue
            before = row.get("canonical_id_before")
            after = row.get("canonical_id_after", row.get("canonical_id"))
            if not before or before == after:
                continue
            literal = row.get("raw_source_text") or row.get("name") or ""
            cleaned = cleaned_by_path.get(row.get("raw_source_path")) or {}
            structured = [e.get("value") for e in json.loads(row.get("identity_evidence") or "[]")
                          if e.get("kind") == "structured_identity"]
            # Subjects exactly as the enricher derives them (recognition fallback included),
            # for the shipped row and for the same row carrying the cleaner's identity.
            actual = enricher._derive_interaction_subject_ref(row)
            rules_after = rules_for(actual["canonical_id"], actual["db"]) if actual else set()
            rules_before = rules_for(before, cleaned.get("canonical_source_db"))
            shown = [b.get("display_name") or b.get("ingredient_group") or b.get("name") for b in blob_by_path.get(row.get("raw_source_path"), [])]
            rows.append({
                "id": pid,
                "path": row.get("raw_source_path"),
                "label": literal,
                "structured": structured[:1],
                "before": before,
                "after": after,
                "reason": row.get("identity_decision_reason") or row.get("fallback_reason") or "none_recorded",
                "disposition": row.get("identity_disposition"),
                "rationale": template(row.get("identity_resolution_rationale")),
                "relation": relation(before, after) if after else "after_unresolved",
                "literal_names_before": registry.literal_identity_matches(literal, before),
                "literal_names_after": bool(after) and registry.literal_identity_matches(literal, after),
                "resolver_on_literal": resolver(literal),
                "interaction_subject": actual,
                "blend_child": "nestedRows" in str(row.get("raw_source_path")),
                "scoreable": bool(row.get("scoreable_identity")),
                "role": row.get("role_classification"),
                "interaction_rules_lost": sorted(rules_before - rules_after),
                "interaction_rules_gained": sorted(rules_after - rules_before),
                "display_name": row.get("label_display_name"),
                "display_differs_from_label": normalize_label_display(literal).casefold()
                != normalize_label_display(row.get("label_display_name")).casefold(),
                "blob_shown_as": shown[:2],
            })

    by = collections.defaultdict(lambda: collections.Counter())
    for r in rows:
        key = (r["rationale"], r["relation"])
        c = by[key]
        c["rows"] += 1
        c["blend_child"] += r["blend_child"]
        c["scoreable"] += r["scoreable"]
        c["interaction_changed"] += bool(r["interaction_rules_lost"] or r["interaction_rules_gained"])
        c["literal_names_before_not_after"] += r["literal_names_before"] and not r["literal_names_after"]
        c["display_differs_from_label"] += r["display_differs_from_label"]
    summary = sorted(([k[0], k[1], dict(v)] for k, v in by.items()), key=lambda x: -x[2]["rows"])
    out.write_text(json.dumps({"rewrites": len(rows), "by_rationale_and_relation": summary, "rows": rows}, indent=1, default=str) + "\n")
    for rationale, rel, counts in summary:
        print(counts["rows"], rel, "|", rationale[:110], "|", {k: v for k, v in counts.items() if k != "rows"})


if __name__ == "__main__":
    main()
