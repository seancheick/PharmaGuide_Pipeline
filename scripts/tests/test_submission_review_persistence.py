"""Persistent reviewer corrections and attestations, executed against app.js.

The rule these defend: what the page shows about a review must be what the
server actually holds. A tick the database refused must not stay on screen, a
correction written against replaced photographs must not be silently adopted,
and the two sides must agree on the digest a tick is bound to.

These run the shipped asset in a sandbox, so what is asserted is the behaviour
that ships; only the browser and HTTP boundaries are simulated.
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
  open:false,hidden:false,type:'',title:'',
  classList:{add(){},remove(){},toggle(){},contains(){return false}},
  style:{setProperty(){}},dataset:{},listeners:{},
  set textContent(v){this.text=v;this.children=[]},
  get textContent(){return this.text||''},
  set className(v){this._c=v},get className(){return this._c||''},
  append(...items){this.children.push(...items)},
  addEventListener(kind,fn){this.listeners[kind]=fn},
  querySelector(){return this},showModal(){this.open=true},close(){this.open=false}}}
const nodes={},calls=[],out={};
const document={getElementById:id=>(nodes[id] ||= el(id)),createElement:()=>el(''),
 createTextNode:text=>({textContent:text}),querySelector:()=>null,addEventListener(){}};
// The reviewer's session exists; persistence is expected to engage.
const ctx=vm.createContext({document,console,out,calls,nodes,
 setTimeout,clearTimeout,queueMicrotask,
 fetch:async()=>({ok:true,json:async()=>({diagnostics:[]})}),
 structuredClone:v=>JSON.parse(JSON.stringify(v))});
vm.runInContext(fs.readFileSync(process.argv[1].replace('app.js','canonical.js'),'utf8'),ctx);
vm.runInContext(fs.readFileSync(process.argv[1],'utf8')+`
function boot(){} function setStatus(message){out.status=message;}
function renderRows(){} function renderStatements(){} function scheduleUrlRefresh(){}
function renderDetail(){} function renderQueue(){} function renderDraft(){}
function renderIdentityCheck(){} function renderProductPictureOptions(){}
function syncFieldsFromPayload(){}
sha256Hex=async(text)=>'a'.repeat(63)+(text.length%10).toString(16);
state.session={access_token:'fixture'};
state.selected={id:'s1',kind:'label_mismatch',review_status:'under_review',
 evidence_revision:2,evidence_manifest_sha256:'e'.repeat(64),photos:[
   {photo_id:'11111111-1111-1111-1111-111111111111',categories:['supplement_facts']}]};
state.payload={brandName:'Original'};
state.payloadCanonical=canonicalJson(state.payload);
`,ctx);
(async()=>{await vm.runInContext(process.argv[2],ctx);
  console.log(JSON.stringify(out));})()
.catch(e=>{console.error(e&&e.stack||String(e));process.exitCode=1});
"""


def _exercise(script):
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js required for console behavior")
    result = subprocess.run(
        [node, "-e", _HARNESS, str(ASSET), script],
        capture_output=True, text=True, check=True, timeout=20,
    )
    return json.loads(result.stdout)


def test_picture_url_refresh_preserves_unsaved_label_and_selection():
    out = _exercise("""(async()=>{
      state.reviewerImages=[{objectId:'image-1',previewUrl:'expired'}];
      state.productImage={kind:'reviewer',id:'image-1'};
      state.payload={brandName:'Unsaved edit'};
      edge=async()=>({review:{draft:{payload:{brandName:'Older saved label'}},
        reviewer_images:[{object_id:'image-1',signed_url:'renewed'}]}});
      await refreshReviewerPictureUrls();
      out.brand=state.payload.brandName;
      out.url=state.reviewerImages[0].previewUrl;
      out.picture=state.productImage.id;
    })()""")
    assert out == {'brand':'Unsaved edit','url':'renewed','picture':'image-1'}


def test_approved_controls_are_read_only_but_raw_json_remains_copyable():
    out = _exercise("""(()=>{
      const input=document.getElementById('brand');
      const raw=document.getElementById('raw-json');
      document.querySelectorAll=()=>[input,raw];
      state.selected.review_status='approved';
      setApprovedReadOnly();
      out.locked=input.disabled;out.rawReadOnly=raw.readOnly;out.rawDisabled=raw.disabled;
      state.selected.review_status='under_review';
      setApprovedReadOnly();out.editable=!input.disabled&&!raw.readOnly;
    })()""")
    assert out == {'locked':True,'rawReadOnly':True,'rawDisabled':False,'editable':True}


def test_saved_corrections_are_restored_when_the_page_reopens() -> None:
    # The whole point of persistence: a reload must not cost the reviewer the
    # twenty ingredient rows they already corrected.
    out = _exercise("""(async()=>{
      edge=async(body)=>{calls.push(body); return {review:{
        draft:{payload:{brandName:'Corrected'},payload_sha256:'a'.repeat(63)+'2',
               superseded:false},
        verifications:[{field_path:'identity.brand',live:true}]}};};
      await updateShaPreview();
      await loadReview();
      out.brand=state.payload.brandName;
      out.checked=[...verifiedSet()];
    })()""")

    assert out["brand"] == "Corrected"
    assert out["checked"] == ["brand"]


def test_saved_product_picture_is_restored_with_fresh_preview() -> None:
    out = _exercise("""(async()=>{
      edge=async()=>({review:{draft:null,verifications:[],
        product_image:{kind:'reviewer',id:'image-1'},
        reviewer_images:[{object_id:'image-1',signed_url:'https://signed.example/fresh'}]}});
      await loadReview();
      out.picture=state.productImage;
      out.images=state.reviewerImages;
    })()""")
    assert out["picture"] == {"kind": "reviewer", "id": "image-1"}
    assert out["images"][0]["previewUrl"] == "https://signed.example/fresh"


def test_approved_label_reopens_from_the_approval_not_an_empty_personal_draft() -> None:
    out = _exercise("""(async()=>{
      state.selected.review_status='approved';
      edge=async(body)=>{calls.push(body.action);return {review:{draft:null,
        approved_label:{approved_payload:{brandName:'Approved brand',ingredientRows:[{name:'Calcium'}]}},
        verifications:[]}}};
      await loadReview();
      await saveReview();
      out.brand=state.payload.brandName;
      out.rows=state.payload.ingredientRows;
      out.saves=calls.filter(x=>x==='save_review').length;
    })()""")
    assert out["brand"] == "Approved brand"
    assert out["rows"] == [{"name": "Calcium"}]
    assert out["saves"] == 0


def test_a_superseded_draft_is_never_adopted_into_the_editor() -> None:
    out = _exercise("""(async()=>{
      edge=async()=>({review:{
        draft:{payload:{brandName:'FromOldPhotos'},payload_sha256:'x'.repeat(64),
               superseded:true},
        verifications:[{field_path:'identity.brand',live:false}]}});
      await updateShaPreview();
      await loadReview();
      out.brand=state.payload.brandName;
      out.checked=verifiedSet().size;
      out.banner=nodes['review-banner'].textContent;
      out.blockers=approvalBlockers().map(c=>c.todo);
    })()""")

    # The old reading is kept by the server but must not be presented as a
    # reading of the photographs now on screen.
    assert out["brand"] == "Original"
    assert out["checked"] == 0
    assert "New photographs arrived" in out["banner"]
    assert any("Reopen this submission" in todo for todo in out["blockers"])


def test_a_late_review_load_cannot_restore_work_from_an_older_revision() -> None:
    out = _exercise("""(async()=>{
      let release; const gate=new Promise(r=>{release=r;});
      edge=async()=>{await gate; return {review:{
        draft:{payload:{brandName:'Old revision'},payload_sha256:'a'.repeat(64),superseded:false},
        verifications:[]}};};
      await updateShaPreview();
      const pending=loadReview();
      // A retake keeps the submission id but changes the evidence revision.
      state.selected.evidence_revision=3;
      state.selected.evidence_manifest_sha256='f'.repeat(64);
      state.payload={brandName:'Current revision'};
      await updateShaPreview();
      state.reviewLoadRequest += 1;
      release(); await pending;
      out.brand=state.payload.brandName;
    })()""")

    assert out["brand"] == "Current revision"


def test_a_tick_the_server_refused_is_taken_back_on_screen() -> None:
    out = _exercise("""(async()=>{
      await updateShaPreview();
      edge=async()=>{throw new Error('refused');};
      toggleVerified('brand');
      out.optimistic=verifiedSet().size;
      await new Promise(queueMicrotask);
      await new Promise(queueMicrotask);
      out.after=verifiedSet().size;
      out.status=out.status;
    })()""")

    # Shown immediately, then withdrawn: a tick that never reached the database
    # must not be able to count toward an approval.
    assert out["optimistic"] == 1
    assert out["after"] == 0
    assert "could not be recorded" in out["status"]


def test_a_digest_disagreement_blocks_the_decision() -> None:
    out = _exercise("""(async()=>{
      edge=async()=>({review:{
        draft:{payload:{brandName:'Original'},payload_sha256:'f'.repeat(64),
               superseded:false},
        verifications:[]}});
      await updateShaPreview();
      await loadReview();
      out.mismatch=state.reviewDigestMismatch;
      out.banner=nodes['review-banner'].textContent;
      out.blockers=approvalBlockers().map(c=>c.todo);
    })()""")

    # If the two sides canonicalize differently, a tick would bind to text the
    # reviewer never read. That is a stop, not a warning.
    assert out["mismatch"] is True
    assert "disagree about the label text" in out["banner"]
    assert any("disagree about the label text" in todo for todo in out["blockers"])


def test_a_late_save_response_cannot_describe_a_newer_payload() -> None:
    out = _exercise("""(async()=>{
      let release; const gate=new Promise(r=>{release=r;});
      let first=true;
      edge=async(body)=>{calls.push(body);
        if(first){first=false; await gate;
          return {review:{draft:{payload:{brandName:'First'},
            payload_sha256:'f'.repeat(64),superseded:true},verifications:[]}};}
        return {review:{draft:{payload:{brandName:'Second'},
          payload_sha256:state.payloadSha,superseded:false},verifications:[]}};};
      await updateShaPreview();
      const slow=saveReview();
      state.payload={brandName:'Second'};
      await updateShaPreview();
      await saveReview();
      release(); await slow;
      out.superseded=state.reviewSuperseded;
    })()""")

    # The stale reply claimed the draft was superseded. It describes a payload
    # nobody is looking at any more and must not repaint the current one.
    assert out["superseded"] is False


def test_persistence_sends_the_source_photograph_it_was_read_from() -> None:
    out = _exercise("""(async()=>{
      state.draft={draft_payload:{identity:{brand:{sources:[
        {photo_id:'11111111-1111-1111-1111-111111111111'}]}}}};
      await updateShaPreview();
      edge=async(body)=>{calls.push(body); return {review:{draft:null,verifications:[]}};};
      toggleVerified('brand');
      await new Promise(queueMicrotask);
      await new Promise(queueMicrotask);
      out.sent=calls.filter(c=>c.action==='set_field_verification');
    })()""")

    assert len(out["sent"]) == 1
    assert out["sent"][0]["field_path"] == "identity.brand"
    assert out["sent"][0]["photo_id"] == "11111111-1111-1111-1111-111111111111"


def test_an_older_verification_reply_cannot_drop_a_newer_tick() -> None:
    out = _exercise("""(async()=>{
      await updateShaPreview();
      let release; const gate=new Promise(r=>{release=r;});
      let first=true;
      edge=async(body)=>{
        if(first){first=false; await gate;
          // The reply to the first tick knows about only that one.
          return {review:{draft:{payload:state.payload,
            payload_sha256:state.payloadSha,superseded:false},
            verifications:[{field_path:'identity.brand',live:true}]}};}
        return {review:{draft:{payload:state.payload,
          payload_sha256:state.payloadSha,superseded:false},
          verifications:[{field_path:'identity.brand',live:true},
                         {field_path:'serving.size',live:true}]}};};
      toggleVerified('brand');
      toggleVerified('serving');
      await new Promise(queueMicrotask);
      await new Promise(queueMicrotask);
      release();
      await new Promise(queueMicrotask);
      await new Promise(queueMicrotask);
      out.checked=[...verifiedSet()].sort();
    })()""")

    # The stale reply lists one tick. Repainting from it would discard a check
    # the database has already accepted.
    assert out["checked"] == ["brand", "serving"]


def test_the_console_asks_the_importer_rather_than_judging_the_label() -> None:
    out = _exercise("""(async()=>{
      edge=async(body)=>{calls.push(body);
        return {diagnostics:[
          {path:'ingredientRows[1]',message:'amount must be a number'}]};};
      await updateShaPreview();
      await refreshDiagnostics();
      out.action=calls[0].action;
      out.sentPayload=calls[0].payload;
      out.diagnostics=state.diagnostics;
      out.blockers=approvalBlockers().map(c=>c.todo);
    })()""")

    assert out["action"] == "validate_label"
    assert out["sentPayload"] == {"brandName": "Original"}
    assert out["diagnostics"] == [
        {"path": "ingredientRows[1]", "message": "amount must be a number"}
    ]
    assert any("Fix the 1 problem" in todo for todo in out["blockers"])


def test_a_validator_outage_is_unknown_not_clean() -> None:
    out = _exercise("""(async()=>{
      edge=async()=>({diagnostics:[]});
      await updateShaPreview();
      await refreshDiagnostics();
      out.beforeOutage=approvalBlockers().map(c=>c.todo);
      // The outage starts before the edit, because diagnostics now travel the
      // same channel as every other reviewer call.
      edge=async()=>{throw new Error('down');};
      state.payload={brandName:'Edited'};
      await updateShaPreview();
      await refreshDiagnostics();
      out.diagnostics=state.diagnostics;
      out.blockers=approvalBlockers().map(c=>c.todo);
    })()""")

    # A previous clean answer must not survive an outage: it would let the
    # reviewer approve against a check that never ran for this text.
    assert not any("label check" in todo for todo in out["beforeOutage"])
    assert out["diagnostics"] is None
    assert any("Waiting for the label check" in todo for todo in out["blockers"])


def test_a_stale_diagnostics_reply_cannot_clear_a_newer_payload() -> None:
    out = _exercise("""(async()=>{
      let release; const gate=new Promise(r=>{release=r;});
      let first=true;
      edge=async()=>{
        if(first){first=false; await gate; return {diagnostics:[]};}
        return {diagnostics:[{path:'$',message:'brandName required'}]};};
      await updateShaPreview();
      const slow=refreshDiagnostics();
      state.payload={brandName:'Edited'};
      await updateShaPreview();
      await refreshDiagnostics();
      release(); await slow;
      out.diagnostics=state.diagnostics;
    })()""")

    # The stale reply said "clean" about text nobody is looking at any more.
    assert out["diagnostics"] == [{"path": "$", "message": "brandName required"}]


def test_a_field_points_at_the_photograph_it_was_read_from() -> None:
    out = _exercise("""(async()=>{
      state.draft={draft_payload:{identity:{brand:{sources:[
        {photo_id:'11111111-1111-1111-1111-111111111111'}]}}}};
      const grid=document.getElementById('photos');
      const match={dataset:{photoId:'11111111-1111-1111-1111-111111111111'},
        classList:{_s:new Set(),add(c){this._s.add(c)},remove(c){this._s.delete(c)}},
        scrollIntoView(){}};
      const other={dataset:{photoId:'22222222-2222-2222-2222-222222222222'},
        classList:{_s:new Set(),add(c){this._s.add(c)},remove(c){this._s.delete(c)}},
        scrollIntoView(){}};
      grid.children=[match,other];
      out.found=focusSourcePhoto('11111111-1111-1111-1111-111111111111');
      out.marked=[...match.classList._s];
      out.otherMarked=[...other.classList._s];
    })()""")

    assert out["found"] is True
    assert out["marked"] == ["source-photo"]
    assert out["otherMarked"] == []


def test_opening_a_submission_never_saves_over_its_draft_before_it_loads() -> None:
    # Production lost a reviewed Adrenal Complex draft this way: opening the
    # submission hashed the blank page and the debounced save fired before the
    # slower load_review answered, writing the blank default over the work.
    out = _exercise("""(async()=>{
      let finishLoad;
      edge=async(body)=>{calls.push(body.action);
        if(body.action==='load_review') return new Promise(done=>finishLoad=done);
        return {review:{}};};
      state.payload=defaultPayload();state.payloadCanonical=null;state.payloadSha=null;
      await updateShaPreview();
      const loading=loadReview();
      await new Promise(done=>setTimeout(done,900));
      out.savedBeforeLoad=calls.filter(action=>action==='save_review').length;
      finishLoad({review:{draft:{payload:{brandName:'Reviewed work'},superseded:false}}});
      await loading;
      await new Promise(done=>setTimeout(done,900));
      out.brand=state.payload.brandName;
    })()""")

    assert out["savedBeforeLoad"] == 0
    assert out["brand"] == "Reviewed work"


def test_a_failed_draft_load_never_saves_over_the_server_copy() -> None:
    out = _exercise("""(async()=>{
      edge=async(body)=>{calls.push(body.action);
        if(body.action==='load_review') throw new Error('offline');
        return {review:{}};};
      await loadReview();
      state.payload={brandName:'Typed while offline'};
      await updateShaPreview();
      await new Promise(done=>setTimeout(done,900));
      out.saves=calls.filter(action=>action==='save_review').length;
    })()""")

    assert out["saves"] == 0
