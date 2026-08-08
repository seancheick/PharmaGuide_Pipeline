#!/usr/bin/env python3
"""Regenerate the drug-class consumer-copy review packet from the vocab file.

The packet embeds a content hash of scripts/data/drug_class_vocab.json; any edit
to the reviewed copy invalidates it. Regenerating by hand risks the packet and
the artifact drifting apart, which is exactly what a clinician signature must
not do -- so the entry sections are rendered from the JSON, never retyped.

    python3 scripts/audits/drug_class_consumer_copy_v1_1/regenerate_packet.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
VOCAB = REPO_ROOT / "scripts/data/drug_class_vocab.json"
OUTPUT = Path(__file__).resolve().parent / "pharmacist_review_packet.md"

# Dr Pham's dispositions, review round 1 (2026-08-08). Entries absent from this
# map were dispositioned `approved` as authored.
REVISED = {
    "hypoglycemics_high_risk": "insulin spans type 1 + type 2; sulfonylureas are type 2 drugs",
    "hypoglycemics_lower_risk": "GLP-1 agents are also used for weight management, not merely 'support'",
    "thyroid_medications": "examples are replacement hormones, not agents that 'balance' thyroid function",
    "antidepressants_ssri_snri": "separates the additional uses from the primary indication",
    "maois": "oral selegiline is a Parkinson's drug; transdermal is the antidepressant form",
    "serotonergic_medications": "interaction grouping, not a therapeutic class -- separates purpose from the shared serotonin property",
    "cardiac_glycosides": "rate control in AF + symptom improvement in HF; not 'a steady rhythm'",
    "anticholinergics": "names the shared anticholinergic property rather than implying one indication",
    "calcium_channel_blockers": "class also includes rate/rhythm-control agents",
    "cyp2d6_substrates": "'broken down by' is wrong: CYP2D6 can bioactivate (codeine); substrate exposure is the concept",
    "cyp3a4_substrates": "same substrate-vs-'broken down by' correction as CYP2D6",
    "potassium_sparing_diuretics": "finerenone is an MRA for CKD in type 2 diabetes -- 'water pills' misleads",
    "tetracycline_antibiotics": "avoids implying these clear any bacterial infection",
    "fluoroquinolones": "drops sinusitis, which implied first-line status",
}


def build(vocab: dict, digest: str) -> str:
    classes = vocab["drug_classes"]
    review = vocab["_metadata"]["consumer_copy_review"]
    revised_n = len(REVISED)
    approved_n = len(classes) - revised_n

    lines = [
        "# Drug-class consumer-copy review packet (vocab v1.1.0)",
        "",
        "Revision: **2 — clinician wording changes applied, awaiting sign-off on this revised copy**",
        "",
        f"Status: **{review['status']}** — the {revised_n} revised strings below are the wording Dr Pham "
        "specified in review round 1 (2026-08-08). Nothing ships to the app until this revision is signed "
        "and `_metadata.consumer_copy_review.status` is set to `approved`.",
        "",
        "Scope: **two sheet-facing fields on all 30 drug-class entries: `group_label` + `commonly_used_for`.** "
        "Existing `name`/`notes`/`examples` copy is NOT part of this review (unchanged, previously approved "
        "for the profile checklist).",
        "",
        f"Artifact: `scripts/data/drug_class_vocab.json`, schema `{vocab['_metadata']['schema_version']}`, "
        f"content hash `sha256:{digest}`. Regenerate this packet (`regenerate_packet.py`) if the file "
        "hash changes again before signing.",
        "",
        f"Round-1 outcome: **{approved_n} approved as authored, {revised_n} approved_with_wording_change "
        "(all applied), 0 requires_revision.**",
        "",
        "## Why these fields exist",
        "",
        "The Flutter medication details sheet (`lib/features/stack/v2/widgets/medication_details_sheet.dart`) "
        "renders no medication education today, because `name`/`notes` were authored for the onboarding "
        'checklist ("Metformin, Ozempic, etc. (rarely cause low blood sugar)") and read wrong as a '
        "classification shown back to the user. `group_label` is the clean classification noun; "
        "`commonly_used_for` is one sentence of consumer education. Both render **verbatim** in the app; "
        "content is bundled on-device (no runtime lookups, by privacy design).",
        "",
        "## Review contract",
        "",
        '- Phrasing is deliberately **"Commonly used …", never "treats"** — off-label reality (amitriptyline '
        "for migraine, propranolol for anxiety). A contract test enforces this.",
        "",
        "- Sentences must not box the user into a diagnosis; class-level purpose only.",
        "",
        "- `group_label` is deliberately not unique — related classes share a consumer bucket (all four "
        'anticoagulant-family classes read "Blood thinners", retained at review).',
        "",
        "- Entries marked **REVISED** below carry round-1 wording changes; the rationale is recorded inline. "
        "Entries marked *approved as authored* were signed off unchanged.",
        "",
        "## Entries",
        "",
    ]

    for i, entry in enumerate(classes, start=1):
        tier = (
            "user-selectable"
            if entry["user_selectable"]
            else "rule-only (assigned by classification, not picked by user)"
        )
        revised = entry["id"] in REVISED
        lines.append(f"### {i}. `{entry['id']}` — {tier}")
        lines.append("")
        lines.append(f"- Checklist name (existing, unchanged): {entry['name']}")
        lines.append(f"- **group_label:** {entry['group_label']}")
        lines.append(f"- **commonly_used_for:** {entry['commonly_used_for']}")
        lines.append(
            f"- Example drugs (for source lookup): {', '.join(entry['examples'][:3])}"
        )
        if revised:
            lines.append(
                f"- Disposition: **approved_with_wording_change — REVISED, applied.** "
                f"Rationale: {REVISED[entry['id']]}."
            )
        else:
            lines.append("- Disposition: approved as authored (round 1)")
        lines.append("")

    lines.extend(
        [
            "---",
            "",
            "## Sign-off",
            "",
            "Reviewer: ______________________  Date: ____________",
            "",
            "By signing, the `group_label` + `commonly_used_for` layer at the content hash above is approved "
            "to render verbatim in the app.",
            "",
            "After sign-off: set `_metadata.consumer_copy_review.status` to `approved` in "
            "`scripts/data/drug_class_vocab.json`, then repin the Flutter asset "
            "(`assets/data/drug_class_vocab.json`) and update the app drift-test metadata lock in the same "
            "commit. The app parser already tolerates the fields' absence, so the app render slot stays "
            "dormant until the repin.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--vocab", type=Path, default=VOCAB)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()

    raw = args.vocab.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    vocab = json.loads(raw.decode("utf-8"))

    missing = sorted(
        set(REVISED) - {d["id"] for d in vocab["drug_classes"]}
    )
    if missing:
        raise SystemExit(f"dispositioned ids absent from vocab: {missing}")

    args.output.write_text(build(vocab, digest), encoding="utf-8")
    print(f"Wrote {args.output}")
    print(f"sha256:{digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
