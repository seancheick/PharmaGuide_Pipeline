#!/usr/bin/env python3
"""Add standardization-marker canonical identities to the IQM (2026-09-19).

Canonical-owner repair for the Phase-3 clinical review's reject decisions
(PM Phytogen 216948, Longevity A.I. 232718): standardization constituents of
dosed botanical extracts were promoted as standalone actives with no canonical
identity. Per the clinical team's reviewed model, the extract/botanical keeps
the dose-bearing identity and the constituent is a standardization MARKER:

- miroestrol: estrogenic constituent standardizing Solgar's PM Phytogen
  (Pueraria mirifica) root extract (16 mcg per 80 mg extract). Conservative
  marker entry — resolves the row canonically without authoring an efficacy
  claim. The product-level estrogenic/endocrine caution is a product concern,
  not an ingredient identity question.
- withaferin_a: steroidal-lactone withanolide and normal low-level constituent
  of ashwagandha (Withania somnifera); the marker standardized by Life
  Extension's ashwagandha extract (12 mg at 3%). Carries the existing
  WATCH_WITHAFERIN_A dose-dependent consumer caution.

The marker identities make the nested rows resolve canonically, so the enrich
stage can never fall into safety_recognition_without_primary_identity for them.
Follows the Phase 1a Nickel/Tin canonical-entry template exactly (no-RDA-style
conservative form, provenance notes, GSRS/external identifiers).

Idempotent: re-running verifies existing values instead of rewriting.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
IQM_PATH = REPO_ROOT / "scripts" / "data" / "ingredient_quality_map.json"

REVIEWER = "Quarantine remediation 2026-09-19 (clinical sign-off review packet)"
REVIEW_DATE = "2026-09-19"

ENTRIES: dict[str, dict] = {
    "miroestrol": {
        "standard_name": "Miroestrol",
        "category": "herbs",
        # C0056493 (crisnatol) until 2026-09-26; see the IQM entry's cui_note.
        "cui": "C3491692",
        "forms": {
            "miroestrol (unspecified)": {
                "bio_score": 3.0,
                "natural": True,
                "score": 6.0,
                "absorption": "low",
                "absorption_structured": {
                    "quality": "low",
                    "value": 0.3,
                    "range_low": 0.2,
                    "range_high": 0.4,
                },
                "consumer_note": (
                    "Miroestrol is an estrogenic constituent used to standardize "
                    "Pueraria mirifica (kwao krua) extracts. It is measured as a "
                    "standardization marker, not as a standalone nutrient."
                ),
                "consumer_note_review": {
                    "by": REVIEWER,
                    "date": REVIEW_DATE,
                },
                "notes": (
                    "Standardization marker of standardized Pueraria mirifica root "
                    "extract (Solgar PM Phytogen: 16 mcg miroestrol per 80 mg "
                    "extract). Long-term human safety data are insufficient; this "
                    "entry exists so the marker row resolves canonically under its "
                    "dosed extract parent instead of quarantining the product as "
                    "an unresolved standalone identity. No efficacy claim is "
                    "authored. Product-level estrogenic/endocrine caution is "
                    "handled by the product safety layer."
                ),
                "dosage_importance": 0.3,
                "aliases": ["Miroestrol", "deoxymiroestrol marker"],
            }
        },
        "match_rules": {"priority": 1, "match_mode": "exact", "exclusions": []},
        "category_enum": "herbs",
        "rxcui": None,
        "rxcui_note": (
            "No RxNorm concept exists for this standardization constituent; "
            "identified via PubChem CID 165001 and UMLS C3491692 instead (GSRS "
            "has no miroestrol record, so there is no UNII)."
        ),
        "data_quality": {
            "review_status": "validated",
            "completeness": 0.6,
            "last_reviewed_at": REVIEW_DATE,
            "research_status": "validated",
        },
        "external_ids": {
            # 5318042 ((E)-hex-2-en-1-ol) until 2026-09-26.
            "pubchem_cid": 165001,
        },
        "gsrs": {
            "substance_name": "Miroestrol",
            "substance_class": "phytochemical",
            "cfr_sections": [],
            "dsld_count": 1,
            "dsld_info_raw": (
                "Standardization constituent of Pueraria mirifica extract "
                "(DSLD 216948); no standalone DSLD ingredient row"
            ),
            "active_moiety": None,
            "salt_parents": [],
            "metabolic_relationships": [],
            "metabolites": [],
        },
        "aliases": ["Miroestrol"],
        "description": (
            "Estrogenic coumestan constituent of Pueraria mirifica, used as a "
            "standardization marker for kwao krua root extracts."
        ),
        "dosage_importance": 0.3,
        "source": "quarantine_remediation_2026_09_19_clinical_signoff",
        "priority": 1,
    },
    "withaferin_a": {
        "standard_name": "Withaferin A",
        "category": "herbs",
        "cui": "C0078503",
        "forms": {
            "withaferin a (unspecified)": {
                "bio_score": 3.0,
                "natural": True,
                "score": 6.0,
                "absorption": "low",
                "absorption_structured": {
                    "quality": "low",
                    "value": 0.3,
                    "range_low": 0.2,
                    "range_high": 0.4,
                },
                "consumer_note": (
                    "Withaferin A is a normal ashwagandha compound, but cytotoxic "
                    "in concentrated, high-withanolide extracts — a dose-dependent "
                    "risk. Talk to your doctor about high-potency ashwagandha."
                ),
                "consumer_note_review": {
                    "by": REVIEWER + "; consumer caution text inherited from WATCH_WITHAFERIN_A",
                    "date": REVIEW_DATE,
                },
                "notes": (
                    "Standardization marker of ashwagandha (Withania somnifera) "
                    "extract standardized to withaferin A content (Life Extension "
                    "Longevity A.I.: 12 mg at 3% of extract). A phase-I oncology "
                    "study (72-216 mg/day) reported no grade 3/4 toxicities but "
                    "mild liver-enzyme elevations in 5/13 patients and poor oral "
                    "bioavailability; long-term healthy-consumer safety at 12 mg "
                    "is not established. This identity resolves the marker row "
                    "under its botanical extract provenance instead of "
                    "quarantining the product; the dose-dependent WATCH_WITHAFERIN_A "
                    "safety signal is retained by the safety layer."
                ),
                "dosage_importance": 0.4,
                "aliases": ["Withaferin A", "withaferin-a"],
            }
        },
        "match_rules": {"priority": 1, "match_mode": "exact", "exclusions": []},
        "category_enum": "herbs",
        "rxcui": None,
        "rxcui_note": (
            "No RxNorm concept exists for this standardization constituent; "
            "identified via UNII/CAS instead."
        ),
        "data_quality": {
            "review_status": "validated",
            "completeness": 0.6,
            "last_reviewed_at": REVIEW_DATE,
            "research_status": "validated",
        },
        "external_ids": {
            "unii": "L6DO3QW4K5",
            "cas": "5119-48-2",
            "pubchem_cid": 265237,
        },
        "gsrs": {
            "substance_name": "Withaferin A",
            "substance_class": "withanolide",
            "cfr_sections": [],
            "dsld_count": 1,
            "dsld_info_raw": (
                "Withanolide constituent standardizing ashwagandha extract "
                "(DSLD 232718); watchlist dose-dependent safety class"
            ),
            "active_moiety": None,
            "salt_parents": [],
            "metabolic_relationships": [],
            "metabolites": [],
        },
        "aliases": ["Withaferin A", "withaferin-a"],
        "description": (
            "Steroidal-lactone withanolide and normal low-level constituent of "
            "ashwagandha; used as a standardization marker for high-withanolide "
            "extracts."
        ),
        "dosage_importance": 0.4,
        "source": "quarantine_remediation_2026_09_19_clinical_signoff",
        "priority": 1,
    },
}


def main() -> int:
    raw = IQM_PATH.read_text()
    iqm = json.loads(raw)

    changed = []
    for key, entry in ENTRIES.items():
        existing = iqm.get(key)
        if isinstance(existing, dict):
            # Idempotency: verify the essentials and top up any schema fields
            # added after the entry first landed (e.g. absorption_structured,
            # rxcui_note) without rewriting content another session may have
            # edited concurrently.
            form_key = f"{entry['standard_name'].lower()} (unspecified)"
            forms = existing.get("forms") or {}
            form = forms.get(form_key) or next(iter(forms.values()), {})
            assert existing.get("standard_name") == entry["standard_name"], key
            assert form.get("bio_score") == entry["forms"][form_key]["bio_score"], key
            ref_form = entry["forms"][form_key]
            for field in ("absorption_structured", "score"):
                if form.get(field) != ref_form.get(field):
                    form[field] = ref_form[field]
                    changed.append(f"{key}.forms.{field}")
            for field in ("rxcui", "rxcui_note"):
                if existing.get(field) != entry.get(field):
                    existing[field] = entry.get(field)
                    changed.append(f"{key}.{field}")
            print(f"  ok (already present): {key}")
            continue
        # Insert adjacent to the related botanical for readable diffs.
        anchor = "ashwagandha" if key == "withaferin_a" else "isoflavones"
        if anchor in iqm:
            items = list(iqm.items())
            out = {}
            for k, v in items:
                out[k] = v
                if k == anchor:
                    out[key] = entry
            iqm.clear()
            iqm.update(out)
        else:
            iqm[key] = entry
        changed.append(key)

    if changed:
        print(f"added: {changed}")

    # Declared statistics must equal actual counts (schema-test contract).
    # Computed FROM THE DATA on every run (never incremented) so the file
    # stays self-consistent even when concurrent sessions add or remove
    # entries in the same working tree. Note: the shared IQM is a live
    # concurrent-edit surface — read, modify, verify, and hand back quickly;
    # never cache a long-lived copy across a write.
    entries = {k: v for k, v in iqm.items() if k not in ("_metadata", "relationships")}
    meta = iqm.get("_metadata")
    if not isinstance(meta, dict):
        meta = {}
        iqm["_metadata"] = meta
    metadata_fixed = False
    if isinstance(meta, dict):
        stats = meta.get("statistics")
        if not isinstance(stats, dict):
            stats = {}
            meta["statistics"] = stats
        if "total_entries" in stats or "total_aliases" in stats:
            metadata_fixed = True  # spurious keys from an earlier draft
        stats.pop("total_entries", None)
        stats.pop("total_aliases", None)
        # EXACT replication of TestStatisticsReconciliation._compute so the
        # declared statistics always satisfy the schema contract.
        total_parents = total_forms = total_form_aliases = 0
        parents_parent = parents_contains = parents_pattern = 0
        for entry in entries.values():
            if not isinstance(entry, dict):
                continue
            total_parents += 1
            if entry.get("aliases"):
                parents_parent += 1
            if entry.get("contains_aliases"):
                parents_contains += 1
            if entry.get("pattern_aliases"):
                parents_pattern += 1
            forms = entry.get("forms", {})
            if isinstance(forms, dict):
                for fdata in forms.values():
                    total_forms += 1
                    if isinstance(fdata, dict):
                        total_form_aliases += len(fdata.get("aliases", []))
        stats["total_parents"] = total_parents
        stats["total_forms"] = total_forms
        stats["total_form_aliases"] = total_form_aliases
        stats["parents_with_parent_aliases"] = parents_parent
        stats["parents_with_contains_aliases"] = parents_contains
        stats["parents_with_pattern_aliases"] = parents_pattern
        meta["total_entries"] = len(entries)

    if changed or metadata_fixed:
        IQM_PATH.write_text(json.dumps(iqm, indent=2, ensure_ascii=False) + "\n")
        if metadata_fixed:
            print("metadata statistics reconciled")

    # Verify every new key resolves through the cleaner's canonical lookup.
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from enhanced_normalizer import EnhancedDSLDNormalizer  # noqa: E402

    norm = EnhancedDSLDNormalizer()
    for key, entry in ENTRIES.items():
        std = entry["standard_name"]
        hit = norm._resolve_canonical_identity(std, std)
        assert hit[0] == key, f"{key} does not resolve: {hit}"
        print(f"  resolves: {std} -> {hit}")

    digest = hashlib.sha256(IQM_PATH.read_bytes()).hexdigest()
    print(f"iqm sha256: {digest[:16]}…")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
