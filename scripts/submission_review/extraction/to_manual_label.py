"""Turn a ``label_draft_v1`` reading into a ``manual_label_v1`` skeleton.

The reviewer console loads the result into its editor. Two rules shape all of
it, and both exist because a draft is a *reading* of photographs, not a label.

*Nothing is invented.* A field the model could not read is absent from the
skeleton and named in ``unresolved`` instead, with whatever text was printed so
the reviewer can resolve it from the photograph. Guessing here would be the
worst possible place to guess: the reviewer's job is to confirm, and a
plausible invented value is exactly what a confirmation pass fails to catch.

*The strict validator runs at approval, not here.* A skeleton is expected to be
incomplete; ``manual_label_v1`` will refuse it until a human finishes it. This
module therefore never calls that validator and never tries to satisfy it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

#: Reasons a value could not be carried across, in the reviewer's words.
UNREADABLE = "the photograph could not be read here"
NOT_PRESENT = "the label does not print this"
NO_TARGET_FIELD = "the catalog has nowhere to record this; decide from the photograph"
FREE_TEXT_ONLY = "printed as text; enter the numbers the catalog needs"


@dataclass
class ManualLabelSkeleton:
    """A partly filled label plus an explicit account of what is missing."""

    payload: dict[str, Any]
    unresolved: list[dict[str, str]] = field(default_factory=list)

    def as_payload(self) -> dict[str, Any]:
        return self.payload


def _field_value(entry: object) -> Any:
    """The value of a draft field, or None when it was not read."""
    if not isinstance(entry, Mapping):
        return None
    if entry.get("status") not in {"read", "partial"}:
        return None
    return entry.get("value")


def _field_note(entry: object) -> str:
    status = entry.get("status") if isinstance(entry, Mapping) else None
    return NOT_PRESENT if status == "not_present" else UNREADABLE


def _text(entry: object) -> str | None:
    value = _field_value(entry)
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _printed_source(entry: object) -> str | None:
    """Keep attributed partial text visible; never parse it into a quantity."""
    if not isinstance(entry, Mapping):
        return None
    texts = []
    for source in entry.get("sources") or []:
        text = source.get("supporting_text") if isinstance(source, Mapping) else None
        if isinstance(text, str) and text.strip() and text not in texts:
            texts.append(text)
    return "\n".join(texts) or None


def _amount(entry: object) -> dict[str, Any] | None:
    """An amount field: {value: number, unit_text: string}, both required.

    Printed units cross unchanged. "mcg DFE", "billion CFU" and "IU" are what
    the label says, and normalising them here would quietly discard the only
    record of it.
    """
    value = _field_value(entry)
    if not isinstance(value, Mapping):
        return None
    quantity = value.get("value")
    unit = value.get("unit_text")
    if not isinstance(quantity, (int, float)) or isinstance(quantity, bool):
        return None
    if not isinstance(unit, str) or not unit.strip():
        return None
    return {"quantity": float(quantity), "unit": unit.strip()}


def to_manual_label(draft: Mapping[str, Any]) -> ManualLabelSkeleton:
    """Map a validated draft onto the approval schema, losing nothing silently."""
    if not isinstance(draft, Mapping):
        raise TypeError("a label_draft_v1 mapping is required")

    payload: dict[str, Any] = {}
    unresolved: list[dict[str, str]] = []

    def missing(path: str, reason: str, printed: str | None = None) -> None:
        entry = {"path": path, "reason": reason}
        if printed:
            entry["printed"] = printed
        unresolved.append(entry)

    identity = draft.get("identity") or {}
    for source, target in (("brand", "brandName"), ("product_name", "fullName")):
        text = _text(identity.get(source))
        if text is None:
            missing(target, _field_note(identity.get(source)))
        else:
            payload[target] = text

    # The draft carries two things about the serving: a structured amount and
    # the phrase as printed. Using the structured amount is transcription, not
    # inference, so it crosses. Parsing the phrase would be a reading decision
    # about the photograph, so that stays with the reviewer.
    serving = draft.get("serving") or {}
    serving_text = _text(serving.get("size"))
    amount = _amount(serving.get("amount"))
    if amount is not None:
        payload["servingSizes"] = [{
            "minQuantity": amount["quantity"],
            "maxQuantity": amount["quantity"],
            "unit": amount["unit"],
            "order": 1,
        }]
    else:
        missing("servingSizes", FREE_TEXT_ONLY if serving_text else
                _field_note(serving.get("size")), serving_text)
    per_container = _text(serving.get("servings_per_container"))
    if per_container:
        payload["servingsPerContainer"] = per_container

    payload["ingredientRows"] = _rows(draft.get("ingredient_rows") or [], missing)

    other = draft.get("other_ingredients") or {}
    hint = other.get("disclosure_hint")
    text = _text(other.get("text"))
    if hint in {"present", "declared_none", "on_facts_panel"}:
        # The catalog's vocabulary differs from the draft's hint for one value.
        payload["otherIngredientsDisclosure"] = (
            "included_on_facts_panel" if hint == "on_facts_panel" else hint
        )
        if hint == "present":
            if text:
                payload["otherIngredients"] = text
            else:
                missing("otherIngredients", UNREADABLE)
    else:
        missing("otherIngredientsDisclosure", UNREADABLE, text)

    statements = [
        {"type": value}
        for value in (_text(entry) for entry in draft.get("statements") or [])
        if value
    ]
    if statements:
        payload["statements"] = statements

    return ManualLabelSkeleton(payload=payload, unresolved=unresolved)


def _rows(rows: Sequence[Any], missing) -> list[dict[str, Any]]:
    """Rebuild the printed rows, including blend parentage and unknowns.

    A row nobody could read is kept rather than dropped. A panel with a row
    missing is a different label from the one photographed, and the reviewer
    has to be able to see that the row was there at all.
    """
    built: list[dict[str, Any]] = []
    by_index: dict[int, dict[str, Any]] = {}

    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            continue
        path = f"ingredientRows[{index}]"
        name = _text(row.get("display_name"))
        entry: dict[str, Any] = {
            "name": name or "",
            "order": index + 1,
            "quantity": [],
            "forms": [],
            "nestedRows": [],
        }
        if name is None:
            missing(f"{path}.name", UNREADABLE)

        amount = _amount(row.get("amount"))
        printed_amount = _printed_source(row.get("amount"))
        if amount is not None:
            entry["quantity"] = [amount]
        elif _field_value(row.get("percent_dv")) is not None:
            # A %DV-only row prints no weight, and manual_label_v1 has no
            # numeric field for the percentage. Keep the printed value in the
            # row's notes so it is not lost, and still tell the reviewer that
            # the catalog cannot record it as a quantity.
            printed = _field_value(row.get("percent_dv"))
            entry["notes"] = f"Printed %DV: {printed}"
            missing(f"{path}.quantity", FREE_TEXT_ONLY if printed_amount else NO_TARGET_FIELD,
                    printed_amount or f"%DV {printed}")
        elif printed_amount or row.get("is_blend_header") is not True:
            missing(f"{path}.quantity", FREE_TEXT_ONLY if printed_amount else
                    _field_note(row.get("amount")), printed_amount)

        form = _text(row.get("form_text"))
        if form:
            entry["forms"] = [{"name": form}]

        by_index[index] = entry
        parent = row.get("parent_index")
        has_parent = (
            isinstance(parent, int) and not isinstance(parent, bool)
            and 0 <= parent < index and parent in by_index
        )
        if has_parent:
            by_index[parent]["nestedRows"].append(entry)
            continue
        if parent is not None:
            # A forward or self reference cannot describe a printed panel, so
            # the row is kept at the top level and the conflict is reported.
            missing(f"{path}.nestedRows", NO_TARGET_FIELD, f"parent {parent}")
        built.append(entry)
    return built
