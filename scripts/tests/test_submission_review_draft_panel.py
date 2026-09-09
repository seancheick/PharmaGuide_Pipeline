"""The reviewer's view of an AI draft, executed against the real console asset.

A draft is a starting point beside the photographs, never a finding. These run
app.js in a sandbox so what is asserted is the shipped behaviour, not a
description of it.
"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ASSET = Path(__file__).parents[1] / "submission_review/static/app.js"

_HARNESS = r"""
const fs=require('node:fs'),vm=require('node:vm');
const [asset, payloadJson] = process.argv.slice(1);
const out={fields:[],rows:[],meta:'',hidden:null,status:'',payload:null};

function el(){
  const node={children:[],classList:{_s:new Set(),add(c){this._s.add(c);},remove(c){this._s.delete(c);},contains(c){return this._s.has(c);}},
    dataset:{},style:{},set textContent(v){this._t=v;},get textContent(){return this._t||'';},
    append(...kids){this.children.push(...kids);},addEventListener(){}};
  return node;
}
const nodes={'ai-draft':el(),'ai-draft-body':el(),'ai-draft-meta':el()};
const ctx=vm.createContext({
  out, console,
  document:{createElement:()=>el(), getElementById:(id)=>nodes[id]||el()},
  structuredClone:(v)=>JSON.parse(JSON.stringify(v)),
});
vm.runInContext(fs.readFileSync(asset,'utf8')+`
function boot(){} function renderRows(){} function syncFieldsFromPayload(){}
function updateShaPreview(){} function setStatus(s){ out.status=s; }
`,ctx);
vm.runInContext(`
state.selected={evidence_revision:2,extractions:[JSON.parse(${JSON.stringify(payloadJson)})]};
renderDraft();
out.hidden = document.getElementById('ai-draft').classList.contains('hidden');
`,ctx);
// Walk the rendered tree for text, so assertions see what a reviewer sees.
vm.runInContext(`
function walk(n,acc){ if(!n) return acc; if(n.textContent) acc.push(n.textContent);
  for(const k of n.children||[]) walk(k,acc); return acc; }
out.fields = walk(document.getElementById('ai-draft-body'),[]);
out.meta = document.getElementById('ai-draft-meta').textContent;
`,ctx);
vm.runInContext(`
try{ loadDraftIntoEditor(); out.payload = state.payload; }catch(e){ out.payload={error:String(e)}; }
`,ctx);
process.stdout.write(JSON.stringify(out));
"""


def _render(payload, **extraction):
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js required for console behavior")
    record = {
        "version": 1,
        "actor_kind": "worker",
        "provider": "ollama",
        "model": "gemma4:latest",
        "prompt_version": "p1",
        "evidence_revision": 2,
        "draft_payload": payload,
    }
    record.update(extraction)
    result = subprocess.run(
        [node, "-e", _HARNESS, str(ASSET), json.dumps(record)],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


def _field(value, status="read", input_id="i0"):
    if status != "read":
        return {"value": None, "status": status, "confidence": None, "sources": []}
    return {
        "value": value,
        "status": status,
        "confidence": None,
        "sources": [{"input_id": input_id, "photo_id": "p1"}],
    }


def _payload(**overrides):
    payload = {
        "schema_version": "label_draft_v1", "draft_origin": "model",
        "evidence_revision": 2,
        "abstained": False,
        "abstain_reason": None,
        "identity": {
            "brand": _field("Northwind Labs"),
            "product_name": _field("Magnesium Glycinate"),
        },
        "serving": {
            "size": _field("2 capsules"),
            "servings_per_container": _field("60"),
            "basis_text": _field("Amount Per Serving"),
            "amount": _field({"value": 2, "unit_text": "capsules"}),
        },
        "other_ingredients": {"text": _field("Vegetable cellulose"), "disclosure_hint": "present"},
        "ingredient_rows": [
            {
                "display_name": _field("Magnesium"),
                "amount": {
                    "value": {"value": 200, "unit_text": "mg"},
                    "status": "read",
                    "confidence": None,
                    "sources": [{"input_id": "i0", "photo_id": "p1"}],
                },
                "parent_index": None,
                "is_blend_header": False,
            }
        ],
    }
    payload.update(overrides)
    return payload


def test_a_draft_shows_its_values_and_where_they_came_from() -> None:
    out = _render(_payload())

    text = " ".join(out["fields"])
    assert "Northwind Labs" in text and "Magnesium Glycinate" in text
    # Provenance is on screen: a reviewer can see which transmitted image a
    # value is claimed to come from.
    assert "from i0" in text
    assert "worker" in out["meta"] and "gemma4:latest" in out["meta"]
    assert out["hidden"] is False


def test_an_unreadable_field_says_so_rather_than_rendering_blank() -> None:
    payload = _payload(
        identity={"brand": _field(None, "unreadable"), "product_name": _field("X")}
    )

    out = _render(payload)

    text = " ".join(out["fields"])
    # A blank would read as "nothing on the label" instead of "not read".
    assert "unreadable" in text
    assert "no source cited" in text


def test_dose_and_unit_are_shown_as_separate_columns() -> None:
    out = _render(_payload())

    text = " ".join(out["fields"])
    for column in ("Ingredient", "Amount", "Unit", "Belongs to"):
        assert column in text
    assert "200" in text and "mg" in text


def test_a_nested_row_names_the_blend_it_belongs_to() -> None:
    payload = _payload(
        ingredient_rows=[
            {
                "display_name": _field("Proprietary Blend"),
                "amount": None,
                "parent_index": None,
                "is_blend_header": True,
            },
            {
                "display_name": _field("Ashwagandha"),
                "amount": None,
                "parent_index": 0,
                "is_blend_header": False,
            },
        ]
    )

    out = _render(payload)

    text = " ".join(out["fields"])
    assert "blend header" in text
    assert "Proprietary Blend" in text


def test_an_abstention_tells_the_reviewer_to_transcribe_by_hand() -> None:
    out = _render(_payload(abstained=True, abstain_reason="glare"))

    text = " ".join(out["fields"])
    assert "did not read this label" in text and "glare" in text
    assert "by hand" in text


def test_loading_the_draft_never_carries_an_unreadable_value_across() -> None:
    payload = _payload(
        identity={"brand": _field(None, "unreadable"), "product_name": _field("Mag")},
        ingredient_rows=[
            {
                "display_name": _field(None, "unreadable"),
                "amount": None,
                "parent_index": None,
                "is_blend_header": False,
            },
            {
                "display_name": _field("Zinc"),
                "amount": None,
                "parent_index": None,
                "is_blend_header": False,
            },
        ],
    )

    out = _render(payload)

    editor = out["payload"]
    # A blank the reviewer must fill is safer than a guess they might accept.
    assert editor["brandName"] == ""
    assert editor["fullName"] == "Mag"
    assert [row["name"] for row in editor["ingredientRows"]] == ["", "Zinc"]
    assert editor["ingredientRows"][0]["quantity"] == []


def test_loading_says_plainly_that_nothing_is_verified_yet() -> None:
    out = _render(_payload())

    assert "unverified" in out["status"]


def test_no_draft_hides_the_panel_entirely() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js required for console behavior")
    harness = _HARNESS.replace(
        "state.selected={evidence_revision:2,extractions:[JSON.parse(${JSON.stringify(payloadJson)})]};",
        "state.selected={extractions:[]};",
    )
    result = subprocess.run(
        [node, "-e", harness, str(ASSET), "{}"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(result.stdout)["hidden"] is True


def test_loader_preserves_label_serving_disclosure_and_unknown_daily_frequency():
    editor = _render(_payload())["payload"]
    assert editor["servingSizes"][0]["minQuantity"] == 2
    assert editor["servingSizes"][0]["unit"] == "capsules"
    assert editor["servingSizes"][0].get("minDailyServings") is None
    assert editor["servingsPerContainer"] == "60"
    assert editor["otherIngredientsDisclosure"] == "present"
    assert editor["otherIngredients"] == "Vegetable cellulose"


def test_loader_preserves_nested_rows_forms_and_displays_conflicts():
    row = _payload()["ingredient_rows"][0]
    header = {**row, "display_name": _field("Blend"), "is_blend_header": True}
    child = {**row, "parent_index": 0, "form_text": _field("glycinate")}
    out = _render(_payload(ingredient_rows=[header, child], discrepancies=[
        {"severity": "critical", "code": "multiple_products", "detail": "Two different bottles", "photo_ids": ["p1"]}]))
    assert len(out["payload"]["ingredientRows"]) == 1
    assert out["payload"]["ingredientRows"][0]["nestedRows"][0]["forms"] == [{"name": "glycinate"}]
    assert "Two different bottles" in " ".join(out["fields"])


def test_stale_or_noncanonical_drafts_are_not_loaded():
    for payload in [_payload(schema_version="manual_label_v1"), _payload(evidence_revision=1)]:
        out = _render(payload)
        assert out["hidden"] is True
