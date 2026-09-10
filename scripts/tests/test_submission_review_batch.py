"""Per-item batch approval, executed against the shipped console asset.

The rule under test: a batch saves clicks, never reading. Selection comes from
the server's readiness answer for this reviewer, every item carries its own
evidence fence, the approved label is never sent from the page, and a lost
answer is never replayed.
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
function el(id){return {id,children:[],value:'',checked:false,disabled:false,
  hidden:false,type:'',title:'',open:false,dataset:{},listeners:{},
  classList:{_s:new Set(),add(c){this._s.add(c)},remove(c){this._s.delete(c)},
    toggle(c,on){on?this._s.add(c):this._s.delete(c)},contains(c){return this._s.has(c)}},
  style:{setProperty(){}},
  set textContent(v){this.text=v;this.children=[]},
  get textContent(){return this.text||''},
  set className(v){this._c=v},get className(){return this._c||''},
  append(...items){this.children.push(...items)},
  addEventListener(kind,fn){this.listeners[kind]=fn},
  querySelector(){return null},showModal(){},close(){}}}
const nodes={},calls=[],out={};
const document={getElementById:id=>(nodes[id] ||= el(id)),createElement:()=>el(''),
 createTextNode:t=>({textContent:t}),querySelector:()=>null,addEventListener(){}};
const ctx=vm.createContext({document,console,out,calls,nodes,
 setTimeout,clearTimeout,queueMicrotask,
 fetch:async()=>({ok:true,json:async()=>({diagnostics:[]})}),
 structuredClone:v=>JSON.parse(JSON.stringify(v))});
vm.runInContext(fs.readFileSync(process.argv[1].replace('app.js','canonical.js'),'utf8'),ctx);
vm.runInContext(fs.readFileSync(process.argv[1],'utf8')+`
function boot(){} function setStatus(m){out.status=m;} function renderDetail(){}
function scheduleUrlRefresh(){} function renderRows(){} function syncFieldsFromPayload(){}
async function loadQueue(){calls.push({action:'__reload'});}
state.session={access_token:'fixture'};
state.submissions=[
 {id:'s1',kind:'label_mismatch',review_status:'under_review'},
 {id:'s2',kind:'label_mismatch',review_status:'under_review'},
 {id:'s3',kind:'label_mismatch',review_status:'under_review'}];
`,ctx);
(async()=>{await vm.runInContext(process.argv[2],ctx);
  console.log(JSON.stringify(out));})()
.catch(e=>{console.error(e&&e.stack||String(e));process.exitCode=1});
"""

READY = {
    "fully_verified": True, "superseded": False,
    "evidence_revision": 2, "evidence_manifest_sha256": "e" * 64,
    "payload_sha256": "a" * 64, "review_status": "under_review",
}


def _states(*entries):
    return json.dumps([{**READY, **entry} for entry in entries])


def _exercise(script):
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js required for console behavior")
    result = subprocess.run(
        [node, "-e", _HARNESS, str(ASSET), script],
        capture_output=True, text=True, check=True, timeout=20,
    )
    return json.loads(result.stdout)


def test_only_items_the_server_calls_fully_read_can_be_selected() -> None:
    out = _exercise("""(async()=>{
      edge=async()=>({states:%s});
      await refreshBatchStates();
      selectAllEligible();
      out.selected=[...state.batchSelected].sort();
    })()""" % _states(
        {"submission_id": "s1"},
        {"submission_id": "s2", "fully_verified": False},
        {"submission_id": "s3", "superseded": True},
    ))

    # Partly read and superseded items are not offered at all.
    assert out["selected"] == ["s1"]


def test_each_item_carries_its_own_fence_and_no_label_text() -> None:
    out = _exercise("""(async()=>{
      edge=async(body)=>{calls.push(body);
        if(body.action==='review_states') return {states:%s};
        return {results:body.items.map(i=>({submission_id:i.submission_id,applied:true})),
                applied:body.items.length,total:body.items.length};};
      await refreshBatchStates();
      selectAllEligible();
      await approveBatch();
      out.items=calls.find(c=>c.action==='batch_transition').items;
    })()""" % _states(
        {"submission_id": "s1"},
        {"submission_id": "s2", "evidence_revision": 7,
         "evidence_manifest_sha256": "f" * 64},
    ))

    items = sorted(out["items"], key=lambda entry: entry["submission_id"])
    assert [entry["expected_evidence_revision"] for entry in items] == [2, 7]
    assert [entry["evidence_manifest_sha256"] for entry in items] == ["e" * 64, "f" * 64]
    # The label the batch approves is read server-side from the reviewer's own
    # saved draft. Sending it from here would let the page approve text the
    # attestations were never made against.
    assert all("approved_payload" not in entry for entry in items)
    assert all(entry["to_status"] == "approved" for entry in items)


def test_a_partial_failure_keeps_the_refusals_visible() -> None:
    out = _exercise("""(async()=>{
      edge=async(body)=>{
        if(body.action==='review_states') return {states:%s};
        return {results:[{submission_id:'s1',applied:true},
                         {submission_id:'s2',applied:false}],applied:1,total:2};};
      await refreshBatchStates();
      selectAllEligible();
      await approveBatch();
      out.stillSelected=[...state.batchSelected];
      out.results=state.batchResults;
      out.status=out.status;
    })()""" % _states({"submission_id": "s1"}, {"submission_id": "s2"}))

    # The one that applied is done; the refusal stays selected so the reviewer
    # can open it and find out why.
    assert out["stillSelected"] == ["s2"]
    assert out["results"] == [
        {"submission_id": "s1", "applied": True},
        {"submission_id": "s2", "applied": False},
    ]
    assert "1 of 2 approved" in out["status"]


def test_a_lost_answer_is_never_replayed() -> None:
    out = _exercise("""(async()=>{
      let asked=0;
      edge=async(body)=>{
        if(body.action==='review_states') return {states:%s};
        asked+=1; throw new Error('connection lost');};
      await refreshBatchStates();
      selectAllEligible();
      await approveBatch();
      out.attempts=asked;
      out.selected=[...state.batchSelected];
      out.reloaded=calls.some(c=>c.action==='__reload');
      out.status=out.status;
    })()""" % _states({"submission_id": "s1"}, {"submission_id": "s2"}))

    # Some items may already be approved. Retrying blind would be a second
    # attempt at work that may be done, so the console refreshes and stops.
    assert out["attempts"] == 1
    assert out["selected"] == []
    assert out["reloaded"] is True
    assert "may already be approved" in out["status"]


def test_readiness_lost_underneath_drops_the_selection() -> None:
    out = _exercise("""(async()=>{
      edge=async()=>({states:%s});
      await refreshBatchStates();
      selectAllEligible();
      out.before=[...state.batchSelected].sort();
      // A retake lands between selecting and approving.
      edge=async()=>({states:%s});
      await refreshBatchStates();
      out.after=[...state.batchSelected];
    })()""" % (
        _states({"submission_id": "s1"}, {"submission_id": "s2"}),
        _states({"submission_id": "s1", "superseded": True},
                {"submission_id": "s2", "fully_verified": False}),
    ))

    assert out["before"] == ["s1", "s2"]
    assert out["after"] == []


def test_an_unavailable_readiness_answer_offers_nothing() -> None:
    out = _exercise("""(async()=>{
      edge=async()=>{throw new Error('down');};
      await refreshBatchStates();
      selectAllEligible();
      out.selected=[...state.batchSelected];
      out.eligible=state.submissions.filter(batchEligible).length;
    })()""")

    # Unknown readiness must not become "select everything".
    assert out["selected"] == []
    assert out["eligible"] == 0


def test_a_new_product_is_not_offered_for_batch_approval() -> None:
    out = _exercise("""(async()=>{
      state.submissions=[{id:'s1',kind:'missing_product',review_status:'under_review'},
                         {id:'s2',kind:'label_mismatch',review_status:'under_review'}];
      edge=async()=>({states:%s});
      await refreshBatchStates();
      selectAllEligible();
      out.selected=[...state.batchSelected];
    })()""" % _states({"submission_id": "s1"}, {"submission_id": "s2"}))

    # A new product needs its barcode check and catalog picture, neither of
    # which the queue knows. Offering it would only produce a refusal the
    # reviewer cannot act on from this screen.
    assert out["selected"] == ["s2"]
