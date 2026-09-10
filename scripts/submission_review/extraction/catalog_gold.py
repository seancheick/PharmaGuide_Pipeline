"""Match a bottle you can hold to a label transcription nobody derived from it.

A gold label has to come from somewhere that never saw your photograph and
never saw a model's output. Two models reading one photograph do not qualify,
however good they are: they share the photograph, they share the preparation
step, and a row that preparation deleted is missing from both of them. Their
agreement then reads as confirmation of a product that has no magnesium in it.

NIH's DSLD transcriptions already in this catalog do qualify. They were
written from the physical label by someone else, before any of this existed,
so the two sources have no common cause of error. That is the property that
matters, not which source is more accurate.

What this module does is mechanical: it finds the candidate record for a
scanned barcode, says which of the protocol's required cases that record can
account for, and says which rows it disagrees with a draft about. It never
writes gold, never attests, and never decides that a record *is* the bottle.
Confirming the edition is a person's job, and the physical label always wins.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from normalization import canonicalize_mass_unit

from ..gtin import canonical_gtin14_candidates
from .adapters.ocr_adapter import _parse_amount
from .benchmark import REQUIRED_CASES, _draft_rows, _norm

#: Where each required case can come from. Three different answers, and
#: conflating them is how a set ends up believing it covers a case it never
#: photographed.
#:
#: ``catalog``  — the DSLD record can tell you, so this tool can.
#: ``capture``  — you decide it when you take the photograph.
#: ``sourcing`` — a property of the product itself that the record does not
#:                carry; you have to go and find such a label.
CASE_SOURCES: dict[str, str] = {
    "nested_blend": "catalog",
    "multiple_forms": "catalog",
    "unit_mg": "catalog",
    "unit_mcg": "catalog",
    "unit_g": "catalog",
    "unit_IU": "catalog",
    "unit_CFU": "catalog",
    "unit_AFU": "catalog",
    "glare": "capture",
    "curved_bottle": "capture",
    "tiny_print": "capture",
    "split_facts": "capture",
    "wrong_slot": "capture",
    "mismatched_bottle": "capture",
    "unreadable": "capture",
    "combined_facts_other": "sourcing",
    "ambiguous_serving": "sourcing",
    "serving_range": "sourcing",
    "dv_only": "sourcing",
    "foreign_language": "sourcing",
    "handwritten": "sourcing",
    "expired_date": "sourcing",
}
# A case the protocol requires and this table has never heard of would be
# silently uncovered, which is the one failure a coverage report must not have.
assert set(CASE_SOURCES) == set(REQUIRED_CASES), (
    "CASE_SOURCES and benchmark.REQUIRED_CASES have drifted: "
    f"{set(CASE_SOURCES) ^ set(REQUIRED_CASES)}"
)

CATALOG_CASES = frozenset(c for c, source in CASE_SOURCES.items() if source == "catalog")

#: Mass spelling is not this module's business. `canonicalize_mass_unit` is
#: the pipeline's one owner of every alias — DSLD's "Gram(s)", the enricher's
#: "Milligram(s)", "µg", "mgc" — and a second table here was measurably worse:
#: it missed "Milligram(s)" on 820 rows of the corpus while reading the enzyme
#: units GALU and GaIU as grams.
_MASS_CASES: dict[str, str] = {"mg": "unit_mg", "mcg": "unit_mcg", "g": "unit_g"}

#: Activity and count units are not masses and that owner does not claim them.
#: Matched on a whole word, because they arrive with a magnitude in front and
#: a dosage form behind — "Billion AFU", "12.5 Billion Probiotic CFU
#: Capsule(s)" — and because a prefix rule reads GaIU as international units.
_ACTIVITY_CASES: dict[str, str] = {"iu": "unit_IU", "cfu": "unit_CFU", "afu": "unit_AFU"}
_WORD_BOUNDARY = re.compile(r"[a-z]+")


def _record_path(dsld_id: str, blobs_dir: Path) -> Path:
    """Resolve a catalog record without allowing path traversal."""
    value = str(dsld_id)
    if not value or value in {".", ".."} or Path(value).name != value:
        raise ValueError(f"invalid catalog record id: {dsld_id!r}")
    root = blobs_dir.resolve()
    path = (root / f"{value}.json").resolve()
    if not path.is_relative_to(root):
        raise ValueError(f"invalid catalog record id: {dsld_id!r}")
    return path


def printed_rows(blob: Mapping[str, Any]) -> list[dict[str, Any]]:
    """The panel as the label prints it.

    `display_ingredients` is the printed ledger; `ingredients` is the scored
    actives subset and holds 36% of the printed rows across the catalog. A
    photograph shows the panel, so anything comparing a photograph to a record
    must read the panel — otherwise a perfect reading of a real label reports
    Calories, Total Fat, a blend header and the capsule shell as rows the
    extractor invented. Measured on record 1059: twelve such findings out of
    sixteen printed rows.

    Dose text is parsed by the adapter's parser, which already handles the
    thousands comma and leaves a pseudo-unit like "{Calories}" unparsed.
    """
    rows: list[dict[str, Any]] = []
    for row in blob.get("display_ingredients") or ():
        name = row.get("label_display_name") or row.get("display_name")
        if not name:
            continue
        parsed = _parse_amount(str(row.get("exact_dose_text") or ""))
        rows.append({
            "name": str(name),
            "amount": parsed[0] if parsed else None,
            "path": row.get("raw_source_path"),
        })
    return rows


@dataclass(frozen=True)
class CatalogCandidate:
    """One DSLD record proposed for a scanned barcode. Not a decision."""

    dsld_id: str
    brand_name: str
    product_name: str
    upc_sku: str
    #: Provenance, not something printed on the package. It identifies the
    #: record, and cannot be used to confirm the bottle in your hand.
    formula_fingerprint: str | None
    source_name: str | None
    source_date: str | None
    catalog_version: str | None
    serving: str | None
    active_rows: int
    cases: frozenset[str]

    def corroboration(self) -> dict[str, Any]:
        """The fields a person compares against the physical label."""
        return {
            "brand": self.brand_name,
            "product_name": self.product_name,
            "serving": self.serving,
            "active_rows": self.active_rows,
        }


@dataclass(frozen=True)
class ScanResult:
    barcode: str
    canonical: tuple[str, ...]
    candidates: tuple[CatalogCandidate, ...]
    note: str | None = None

    @property
    def matched(self) -> bool:
        return bool(self.candidates)


@dataclass(frozen=True)
class Disagreement:
    #: name_text        same dose, different wording — usually a glance
    #: amount / unit    the two readings contradict each other
    #: missing_from_draft / absent_from_record   one side has a row the other has not
    kind: str
    row: str
    record: str | None
    draft: str | None


def unit_case(unit_text: Any) -> str | None:
    """Which unit family a printed unit belongs to, or None.

    Mass first, through the pipeline's canonicaliser, taking the leading token
    so a qualified unit ("mcg DFE", "mg NE", "Grams Powder") keeps its family
    while a concentration ("mcg/g") and a unit nobody recognises keep none.
    """
    if not isinstance(unit_text, str) or not unit_text.strip():
        return None
    canonical = canonicalize_mass_unit(unit_text)
    if not isinstance(canonical, str) or not canonical:
        return None
    head = canonicalize_mass_unit(canonical.split(" ", 1)[0])
    case = _MASS_CASES.get(canonical) or _MASS_CASES.get(head)
    if case:
        return case
    for word in _WORD_BOUNDARY.findall(canonical):
        activity = _ACTIVITY_CASES.get(word)
        if activity:
            return activity
    return None


def label_cases(blob: Mapping[str, Any]) -> frozenset[str]:
    """Required cases this DSLD record can account for, and only those.

    Absence here means the record does not say, never that the label does not
    have it. `dv_only` in particular is invisible: DSLD carries a quantity for
    essentially every row, so a %DV-only row has to be found on the physical
    label.
    """
    found: set[str] = set()
    blend = blob.get("proprietary_blend_detail") or {}
    # The bare `proprietary_blend` flag means something else; the detail
    # object owns this question.
    if blend.get("has_proprietary_blends"):
        found.add("nested_blend")
    for row in blob.get("ingredients") or ():
        # Forms are an enrichment concept and live only on this layer.
        if len(row.get("forms") or ()) > 1:
            found.add("multiple_forms")
    for row in printed_rows(blob):
        # Units are a printed property, so they are counted from the printed
        # panel: reading them off the actives subset misses every unit that
        # only a blend child or a nutrition row carries.
        case = unit_case((row["amount"] or {}).get("unit_text"))
        if case:
            found.add(case)
    return frozenset(found & CATALOG_CASES)


def read_candidate(dsld_id: str, blobs_dir: Path, *, brand: str = "", name: str = "",
                   upc: str = "") -> CatalogCandidate | None:
    """Load one record, refusing a blob that is not the record asked for."""
    path = _record_path(dsld_id, blobs_dir)
    if not path.is_file():
        return None
    blob = json.loads(path.read_text(encoding="utf-8"))
    if str(blob.get("dsld_id") or "") != str(dsld_id):
        raise ValueError(f"{path} does not hold record {dsld_id}")
    record = blob.get("label_record") or {}
    serving = blob.get("serving_info") or {}
    count, unit = serving.get("basis_count"), serving.get("basis_unit")
    return CatalogCandidate(
        dsld_id=str(dsld_id),
        brand_name=str(blob.get("brand_name") or brand or ""),
        product_name=str(blob.get("product_name") or name or ""),
        upc_sku=upc,
        formula_fingerprint=record.get("formula_fingerprint"),
        source_name=record.get("source_name"),
        source_date=record.get("source_date"),
        catalog_version=record.get("catalog_version"),
        serving=f"{count:g} {unit}" if count is not None and unit else None,
        active_rows=len(blob.get("ingredients") or ()),
        cases=label_cases(blob),
    )


def scan(barcodes: Iterable[str], index, blobs_dir: Path) -> list[ScanResult]:
    """Look every scanned barcode up through the console's own identity index."""
    results: list[ScanResult] = []
    for barcode in barcodes:
        canonical = sorted(canonical_gtin14_candidates(barcode))
        if not canonical:
            results.append(ScanResult(barcode, (), (), "not a readable barcode"))
            continue
        seen: dict[str, CatalogCandidate] = {}
        for gtin14 in canonical:
            for hit in index.lookup(gtin14):
                if hit.dsld_id in seen:
                    continue
                candidate = read_candidate(
                    hit.dsld_id, blobs_dir,
                    brand=hit.brand_name, name=hit.product_name, upc=hit.upc_sku,
                )
                if candidate is not None:
                    seen[hit.dsld_id] = candidate
        note = None
        if len(seen) > 1:
            # Never resolved here. Two records on one barcode is exactly the
            # ambiguity a person has to settle against the package.
            note = f"{len(seen)} records share this barcode — confirm which edition you hold"
        results.append(ScanResult(barcode, tuple(canonical), tuple(seen.values()), note))
    return results


def thin_cases(covered_counts: Mapping[str, int], *, minimum: int = 2) -> list[str]:
    """Required cases without `minimum` products behind them."""
    return sorted(case for case in REQUIRED_CASES if covered_counts.get(case, 0) < minimum)


def case_counts(case_sets: Iterable[Iterable[str]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for cases in case_sets:
        for case in cases:
            counts[case] = counts.get(case, 0) + 1
    return counts


def disagreements(blob: Mapping[str, Any], draft: Mapping[str, Any]) -> list[Disagreement]:
    """Rows where the record and a draft of the photograph do not agree.

    This is the only list a person needs to adjudicate. It is deliberately
    one-sided in nothing: a row the draft invented and a row it dropped are
    both reported, because either can be the reformulation that makes the
    record the wrong gold for this bottle.
    """
    record_rows = printed_rows(blob)
    draft_rows = [r for r in _draft_rows(dict(draft)) if _norm(r["name"])]

    # Pass 1: the same printed name. Pass 2: the same printed name once a
    # trailing form parenthetical is removed, because DSLD keeps the form in
    # its own field and a label prints it inline ("Niacin" vs "Niacin (as
    # niacinamide)"). Measured on a real 21-row prenatal record, matching on
    # the exact name alone reported 12 of 21 rows as disagreements purely on
    # wording — which would send a person to adjudicate more than half the
    # label and destroy the only reason this list exists.
    taken: set[int] = set()
    pairs: list[tuple[int, dict, bool]] = []
    unpaired_draft: list[dict] = []
    for row in draft_rows:
        index = _find_record(record_rows, taken, _norm(row["name"]))
        renamed = False
        if index is None:
            index = _find_record(record_rows, taken, _norm(_without_parenthetical(row["name"])))
            renamed = index is not None
        if index is None:
            unpaired_draft.append(row)
            continue
        taken.add(index)
        pairs.append((index, row, renamed))

    # Pass 3: whatever is left over pairs by an identical printed amount, but
    # only when that amount is unique on both sides. A guess here would hide a
    # real disagreement, so an ambiguous leftover stays a disagreement.
    leftover_record = [i for i in range(len(record_rows)) if i not in taken]
    for row in list(unpaired_draft):
        amount = _amount_text(row["amount"] or {})
        if amount is None:
            continue
        same = [i for i in leftover_record if _record_amount(record_rows[i]) == amount]
        twins = [r for r in unpaired_draft if _amount_text(r["amount"] or {}) == amount]
        if len(same) == 1 and len(twins) == 1:
            taken.add(same[0])
            leftover_record.remove(same[0])
            unpaired_draft.remove(row)
            pairs.append((same[0], row, True))

    found: list[Disagreement] = []
    for index, row, renamed in pairs:
        record = record_rows[index]
        drafted = row["amount"] or {}
        printed = str(record.get("name") or "")
        record_amount = record["amount"] or {}
        if unit_case(record_amount.get("unit_text")) != unit_case(drafted.get("unit_text")):
            found.append(Disagreement("unit", row["name"],
                                      _record_amount(record), _amount_text(drafted)))
        elif record_amount.get("value") != drafted.get("value"):
            found.append(Disagreement("amount", row["name"],
                                      _record_amount(record), _amount_text(drafted)))
        elif renamed:
            # Reported, never corrected. Both names are printed so a person
            # can see at a glance whether these are one row or two.
            found.append(Disagreement(
                "name_text", row["name"],
                f"{printed} · {_record_amount(record)}",
                f"{row['name']} · {_amount_text(drafted) or '—'}",
            ))
    for row in unpaired_draft:
        found.append(Disagreement("absent_from_record", row["name"], None,
                                  _amount_text(row["amount"] or {})))
    for index in leftover_record:
        record = record_rows[index]
        found.append(Disagreement(
            "missing_from_draft", str(record["name"]),
            _record_amount(record), None,
        ))
    return found


def _without_parenthetical(name: str) -> str:
    """Drop one trailing "(as ...)" so a printed row can meet a stored one."""
    head, _, _ = str(name).partition("(")
    return head.strip() or str(name)


def _find_record(rows: Sequence[Mapping[str, Any]], taken: set[int], key: str) -> int | None:
    if not key:
        return None
    for index, row in enumerate(rows):
        if index in taken:
            continue
        if _norm(row.get("name")) == key:
            return index
    return None


def _record_amount(row: Mapping[str, Any]) -> str:
    return _amount_text(row.get("amount")) or ""


def _amount_text(amount: Any) -> str | None:
    if not isinstance(amount, Mapping) or amount.get("value") is None:
        return None
    return f"{amount['value']:g} {amount.get('unit_text') or ''}".strip()
