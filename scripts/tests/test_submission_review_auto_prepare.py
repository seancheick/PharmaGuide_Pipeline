"""Open, inspect, confirm, approve: what opening a prepared submission does.

Runs the shipped app.js in a sandbox. Opening a submitted product that has a
reading does the mechanical steps (adopt the draft, record a clean barcode
check, preselect the front photo, start the review) and never a field tick or
a decision.
"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ASSET = Path(__file__).parents[1] / "submission_review/static/app.js"

_HARNESS = r"""
const fs=require('node:fs'),vm=require('node:vm');
const [asset, scenarioJson] = process.argv.slice(1);
const scenario = JSON.parse(scenarioJson);
const out={calls:[]};
function el(){ return {children:[],classList:{add(){},remove(){},contains(){return false;}},
  dataset:{},style:{},append(...k){this.children.push(...k);},addEventListener(){},
  set textContent(v){this._t=v;}, get textContent(){return this._t||'';}}; }
const ctx=vm.createContext({out,console,
  document:{createElement:()=>el(),createTextNode:(t)=>({textContent:t}),getElementById:()=>el()}});
vm.runInContext(fs.readFileSync(asset,'utf8')+`
function boot(){}
async function loadDraftIntoEditor(){ out.calls.push('load_draft'); return globalThis.draftLoads; }
async function saveReview(){ out.calls.push('save_review'); }
async function checkIdentity(o){ out.calls.push('identity:'+Boolean(o&&o.record)); }
async function chooseProductImage(p){ out.calls.push('image:'+p.id); }
async function transition(f){ out.calls.push('transition:'+f.to_status); }
async function persistVerification(){ out.calls.push('VERIFY'); }
async function approve(){ out.calls.push('APPROVE'); }
async function approveBatch(){ out.calls.push('APPROVE'); }
function renderProductPictureOptions(){}
`,ctx);
(async()=>{
  vm.runInContext(`
    const s = ${JSON.stringify(scenario)};
    state.selected = s.selected;
    state.reviewReadyFor = s.selected.id + ':' + s.selected.evidence_revision;
    state.review = s.review ?? null;
    state.draft = s.draft ?? null;
    state.identityRecorded = s.identityRecorded ?? null;
    state.productImage = s.productImage ?? null;
    globalThis.draftLoads = s.draftLoads ?? true;
  `, ctx);
  await vm.runInContext('autoPrepare()', ctx);
  await vm.runInContext('autoPrepare()', ctx);
  out.prepared = vm.runInContext('state.autoPreparedFor ?? null', ctx);
  if (scenario.evidenceField) {
    out.evidence = vm.runInContext(`draftEvidence(${JSON.stringify(scenario.evidenceField)})`, ctx);
  }
  process.stdout.write(JSON.stringify(out));
})().catch(e=>{console.error(e);process.exitCode=1});
"""

FRONT = "22222222-2222-4222-8222-222222222222"


def _run(**scenario):
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js required for console behavior")
    selected = {
        "id": "11111111-1111-4111-8111-111111111111", "evidence_revision": 1,
        "kind": "missing_product", "review_status": "submitted",
        "photos": [
            {"photo_id": "33333333-3333-4333-8333-333333333333", "categories": ["supplement_facts"]},
            {"photo_id": FRONT, "categories": ["front_identity"]},
        ],
    }
    selected.update(scenario.pop("selected", {}))
    result = subprocess.run(
        [node, "-e", _HARNESS, str(ASSET), json.dumps({"selected": selected, **scenario})],
        capture_output=True, text=True, timeout=30, check=False)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


DRAFT = {"draft_payload": {"schema_version": "label_draft_v1"}}


def test_a_fresh_reading_is_prepared_up_to_the_reviewer_s_clicks() -> None:
    out = _run(draft=DRAFT)

    assert out["calls"] == [
        "load_draft", "save_review", "identity:true", f"image:{FRONT}",
        "transition:under_review",
    ]
    # Once per revision, however many times the page re-renders.
    assert out["prepared"].endswith(":1")


def test_a_draft_that_fails_to_load_is_not_saved_as_a_blank_review() -> None:
    """A mapper failure leaves the editor blank; saving it would make the blank
    label the review, and the draft would never be adopted again."""
    out = _run(draft=DRAFT, draftLoads=False)

    assert out["calls"] == ["load_draft"]


def test_a_saved_review_is_kept_rather_than_overwritten_by_the_draft() -> None:
    out = _run(draft=DRAFT, review={"draft": {"payload": {"brandName": "Acme"}}})

    assert "load_draft" not in out["calls"]
    assert out["calls"][-1] == "transition:under_review"


def test_steps_already_done_are_not_repeated() -> None:
    out = _run(
        selected={"review_status": "under_review"}, draft=DRAFT,
        review={"draft": {"payload": {"brandName": "Acme"}}},
        identityRecorded="no_match_verified", productImage={"kind": "photo", "id": FRONT},
    )

    assert out["calls"] == []


@pytest.mark.parametrize("status", ["approved", "rejected", "duplicate"])
def test_a_decided_submission_is_left_alone(status) -> None:
    out = _run(selected={"review_status": status}, draft=DRAFT)

    assert out["calls"] == [] and out["prepared"] is None


def test_without_a_reading_it_waits_for_one() -> None:
    out = _run()

    # Drafts arrive with the one-submission read; opening must try again then.
    assert out["calls"] == [] and out["prepared"] is None


def test_nothing_is_ever_ticked_or_approved_for_the_reviewer() -> None:
    for scenario in ({"draft": DRAFT}, {"review": {"draft": {"payload": {}}}}):
        assert not {"VERIFY", "APPROVE"} & set(_run(**scenario)["calls"])


def test_the_evidence_beside_a_tick_is_the_draft_s_quote_and_region() -> None:
    photo = "33333333-3333-4333-8333-333333333333"

    def field(text, region):
        return {"value": text, "status": "read", "confidence": None,
                "sources": [{"photo_id": photo, "input_id": "i0",
                             "supporting_text": text, "region": region}]}

    draft = {"draft_payload": {"ingredient_rows": [
        {"display_name": field("Vitamin C", {"x": 0.2, "y": 0.4, "w": 0.2, "h": 0.05}),
         "amount": field("1000 mg", {"x": 0.6, "y": 0.4, "w": 0.1, "h": 0.05})},
    ]}}
    out = _run(selected={"review_status": "approved"}, draft=draft, evidenceField="rows")

    evidence = out["evidence"]
    assert evidence["quotes"] == ["Vitamin C", "1000 mg"]
    assert evidence["photoId"] == photo
    region = evidence["region"]
    # The union of both readings, with a small margin.
    assert region["x"] == pytest.approx(0.19) and region["y"] == pytest.approx(0.39)
    assert region["x"] + region["w"] == pytest.approx(0.71)
    assert region["y"] + region["h"] == pytest.approx(0.46)


# S19, 2026-09-28: opening it before any draft existed saved the editor's empty
# form, and that blank review then blocked both auto-prep and the agent's save.
BLANK_FORM = {
    "fullName": "", "brandName": "", "offMarket": 0, "statements": [],
    "servingSizes": [{"unit": "", "maxQuantity": None, "minQuantity": None,
                      "maxDailyServings": None, "minDailyServings": None}],
    "ingredientRows": [{"name": "", "forms": [], "quantity": [], "nestedRows": [],
                        "ingredientGroup": ""}],
    "otherIngredients": "", "servingsPerContainer": None, "otherIngredientsDisclosure": "",
}


def test_a_blank_saved_form_is_replaced_by_the_draft() -> None:
    out = _run(draft=DRAFT, review={"draft": {"payload": BLANK_FORM}})

    assert out["calls"][:2] == ["load_draft", "save_review"]


_SAVE_HARNESS = r"""
const fs=require('node:fs'),vm=require('node:vm');
const [asset, payloadJson] = process.argv.slice(1);
const out={edge:[]};
function el(){ return {children:[],classList:{add(){},remove(){},contains(){return false;}},
  dataset:{},style:{},append(){},addEventListener(){},textContent:''}; }
const ctx=vm.createContext({out,console,
  document:{createElement:()=>el(),createTextNode:(t)=>({textContent:t}),getElementById:()=>el()}});
vm.runInContext(fs.readFileSync(asset,'utf8')+`
function boot(){} function renderReviewBanner(){} function setDecisionAvailability(){}
async function edge(body){ out.edge.push(body.action); return {review:{}}; }
`,ctx);
(async()=>{
  vm.runInContext(`
    state.session = {access_token:'t'};
    state.selected = {id:'s', evidence_revision:1, evidence_manifest_sha256:'m', review_status:'submitted'};
    state.reviewReadyFor = 's:1';
    state.payloadSha = 'x';
    state.payload = ${payloadJson};
  `, ctx);
  await vm.runInContext('saveReview()', ctx);
  process.stdout.write(JSON.stringify(out));
})().catch(e=>{console.error(e);process.exitCode=1});
"""


def test_the_console_never_saves_an_untouched_blank_form() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js required for console behavior")

    def saves(payload):
        result = subprocess.run([node, "-e", _SAVE_HARNESS, str(ASSET), json.dumps(payload)],
                                capture_output=True, text=True, timeout=30, check=False)
        assert result.returncode == 0, result.stderr
        return json.loads(result.stdout)["edge"]

    assert saves(BLANK_FORM) == []
    assert saves({**BLANK_FORM, "brandName": "Acme"}) == ["save_review"]
