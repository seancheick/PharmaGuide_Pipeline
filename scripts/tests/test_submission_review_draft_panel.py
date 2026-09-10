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
const mapped = process.argv[3] ? JSON.parse(process.argv[3]) : {payload:{}, unresolved:[]};
const ctx=vm.createContext({
  out, console,
  document:{createElement:()=>el(), createTextNode:(t)=>({textContent:t}),
            getElementById:(id)=>nodes[id]||el()},
  structuredClone:(v)=>JSON.parse(JSON.stringify(v)),
  // Stands in for /api/draft_to_label. The mapping itself is Python's, and is
  // tested there; what matters here is that the console asks and adopts.
  fetch:async(url,init)=>{ out.mapperUrl=url; out.sentDraft=JSON.parse(init.body).draft;
    return {ok:true, json:async()=>mapped}; },
});
vm.runInContext(fs.readFileSync(asset,'utf8')+`
function boot(){} function renderRows(){} function syncFieldsFromPayload(){}
function updateShaPreview(){} function setStatus(s){ out.status=s; }
`,ctx);
vm.runInContext(`
state.session={access_token:'fixture'};
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
(async()=>{
  await vm.runInContext(`loadDraftIntoEditor()`,ctx);
  out.payload = vm.runInContext('state.payload',ctx);
  out.unresolved = vm.runInContext('state.unresolvedFromDraft',ctx);
  process.stdout.write(JSON.stringify(out));
})().catch(e=>{console.error(e);process.exitCode=1});
"""


def _render(payload, mapped=None, **extraction):
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
    argv = [node, "-e", _HARNESS, str(ASSET), json.dumps(record)]
    argv.append(json.dumps(mapped if mapped is not None
                           else {"payload": {}, "unresolved": []}))
    result = subprocess.run(argv, capture_output=True, text=True, check=True)
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


def test_the_console_sends_the_draft_to_the_one_mapper() -> None:
    out = _render(_payload())

    # The browser used to map this itself and had already drifted from the
    # Python mapper. There is one mapper now, and this is how it is reached.
    assert out["mapperUrl"] == "/api/draft_to_label"
    assert out["sentDraft"]["identity"]["brand"]["value"] == "Northwind Labs"


def test_the_console_adopts_the_mapping_exactly_as_returned() -> None:
    mapped = {
        "payload": {"brandName": "From The Mapper", "ingredientRows": []},
        "unresolved": [{"path": "servingSizes", "reason": "printed as text",
                        "printed": "2 capsules"}],
    }

    out = _render(_payload(), mapped=mapped)

    assert out["payload"]["brandName"] == "From The Mapper"
    assert out["unresolved"] == mapped["unresolved"]


def test_what_the_model_could_not_supply_is_shown_to_the_reviewer() -> None:
    out = _render(_payload(), mapped={
        "payload": {},
        "unresolved": [{"path": "servingSizes", "reason": "printed as text",
                        "printed": "2 capsules"}],
    })

    assert "1 field(s)" in out["status"]


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


def test_a_conflict_the_model_found_is_shown_beside_the_draft() -> None:
    out = _render(_payload(discrepancies=[{
        "code": "multiple_products", "severity": "warning",
        "detail": "Two different bottles appear across these photographs.",
        "photo_ids": ["p1"],
    }]))

    # Display of findings belongs to this panel; the mapping does not.
    assert "Two different bottles" in " ".join(out["fields"])


def test_stale_or_noncanonical_drafts_are_not_loaded():
    for payload in [_payload(schema_version="manual_label_v1"), _payload(evidence_revision=1)]:
        out = _render(payload)
        assert out["hidden"] is True
