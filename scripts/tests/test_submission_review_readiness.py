"""The approval page's readiness rules, executed against the shipped console.

A reviewer should never have to guess why Approve is refusing, and should never
be able to approve a field nobody has read off the photographs. These run
app.js in a sandbox, so what is asserted is the behaviour that ships.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ASSET = Path(__file__).parents[1] / "submission_review/static/app.js"

_HARNESS = r"""
const fs=require('node:fs'),vm=require('node:vm');
const [asset, setupJson] = process.argv.slice(1);
const setup = JSON.parse(setupJson);
const out={items:[],progress:'',approveDisabled:null,approveTitle:'',chips:[]};

function el(id){
  const node={id,children:[],classList:{_s:new Set(),add(c){this._s.add(c);},
      remove(c){this._s.delete(c);},contains(c){return this._s.has(c);}},
    dataset:{},style:{},disabled:false,title:'',checked:false,type:'',
    set textContent(v){this._t=v;this.children=[];},get textContent(){return this._t||'';},
    set className(v){this._c=v;},get className(){return this._c||'';},
    append(...k){this.children.push(...k);},addEventListener(){},showModal(){},close(){}};
  return node;
}
const nodes={};
const document={createElement:()=>el('new'),getElementById:(id)=>(nodes[id] ||= el(id)),
  addEventListener(){}};
const ctx=vm.createContext({out,console,document,fetch:async()=>({json:async()=>({})}),
  structuredClone:(v)=>JSON.parse(JSON.stringify(v))});
vm.runInContext(fs.readFileSync(asset,'utf8')+`
function boot(){} function renderRows(){} function syncFieldsFromPayload(){}
function setStatus(){} function renderDraft(){} function renderQueue(){}
function scheduleUrlRefresh(){} function renderIdentityCheck(){}
function renderProductPictureOptions(){} function updateShaPreview(){}
`,ctx);
vm.runInContext(`
state.selected = ${JSON.stringify(setup.submission)};
state.payloadSha = ${JSON.stringify(setup.payload_sha)};
state.identityRecorded = ${JSON.stringify(setup.identity)};
state.productImage = ${setup.product_image ? "{id:'p'}" : 'null'};
state.reviewInvalidated = ${setup.invalidated ? 'true' : 'false'};
renderVerifyChecklist();
for (const field of ${JSON.stringify(setup.verified)}) toggleVerified(field);
renderReadiness();
setDecisionAvailability();
out.items = (document.getElementById('readiness-list').children || []).map(
  (n) => ({text: n.textContent, blocking: n.className === 'blocking'}));
out.progress = document.getElementById('readiness-progress').textContent;
out.approveDisabled = document.getElementById('t-approve').disabled;
out.approveTitle = document.getElementById('t-approve').title;
out.chips = (document.getElementById('verify-checklist').children || []).map(
  (n) => n.className);
`,ctx);
process.stdout.write(JSON.stringify(out));
"""

ALL_FIELDS = ["brand", "name", "serving", "rows", "other"]


def _render(**overrides):
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js required for console behavior")
    setup = {
        "submission": {
            "id": "s1",
            "kind": "missing_product",
            "review_status": "under_review",
            "evidence_revision": 2,
        },
        "payload_sha": "a" * 64,
        "identity": "no_match_verified",
        "product_image": True,
        "invalidated": False,
        "verified": ALL_FIELDS,
    }
    setup.update(overrides)
    result = subprocess.run(
        [node, "-e", _HARNESS, str(ASSET), json.dumps(setup)],
        capture_output=True, text=True, check=True,
    )
    return json.loads(result.stdout)


def _blockers(out):
    return [item["text"] for item in out["items"] if item["blocking"]]


def test_a_fully_checked_submission_can_be_approved() -> None:
    out = _render()

    assert _blockers(out) == []
    assert out["approveDisabled"] is False
    assert out["progress"].startswith("5 of 5")


def test_approve_is_refused_until_every_field_has_been_read() -> None:
    out = _render(verified=["brand", "name"])

    assert out["approveDisabled"] is True
    # The message says what to do next, not merely that something is wrong.
    assert "Read and tick 3 more fields." in _blockers(out)


def test_one_remaining_field_is_named_rather_than_counted() -> None:
    out = _render(verified=["brand", "name", "serving", "rows"])

    assert "Read other ingredients off the photographs and tick it." in _blockers(out)


def test_a_disabled_approve_button_always_explains_itself() -> None:
    out = _render(verified=[])

    assert out["approveDisabled"] is True
    # A dead-end button is the thing this page exists to avoid.
    assert out["approveTitle"] != ""
    assert out["approveTitle"] == _blockers(out)[0]


def test_missing_identity_check_blocks_a_missing_product() -> None:
    out = _render(identity=None)

    assert out["approveDisabled"] is True
    assert any("not already in the catalog" in text for text in _blockers(out))


def test_missing_catalog_picture_blocks_a_missing_product() -> None:
    out = _render(product_image=False)

    assert any("catalog picture" in text for text in _blockers(out))


def test_a_correction_needs_no_picture_or_barcode_check() -> None:
    out = _render(
        submission={
            "id": "s1",
            "kind": "label_mismatch",
            "review_status": "under_review",
            "evidence_revision": 1,
        },
        identity=None,
        product_image=False,
    )

    # Those two gates belong to new products, not to corrections.
    assert _blockers(out) == []
    assert out["approveDisabled"] is False


def test_changed_photos_block_the_decision_outright() -> None:
    out = _render(invalidated=True)

    assert out["approveDisabled"] is True
    assert any("photos changed" in text.lower() for text in _blockers(out))


def test_editing_the_label_clears_the_ticks() -> None:
    # A check of an older value is not a check of this one. The ticks are bound
    # to the exact payload digest, so one edit withdraws them.
    edited = _render(payload_sha="b" * 64, verified=[])

    assert edited["approveDisabled"] is True
    assert all("verified" not in chip for chip in edited["chips"])


def test_a_submission_not_yet_started_cannot_be_approved() -> None:
    out = _render(
        submission={
            "id": "s1",
            "kind": "missing_product",
            "review_status": "submitted",
            "evidence_revision": 2,
        }
    )

    assert out["approveDisabled"] is True
    assert any("Start review" in text for text in _blockers(out))


def test_every_critical_field_gets_its_own_tick() -> None:
    out = _render(verified=[])

    assert len(out["chips"]) == len(ALL_FIELDS)
