"""Execute real reviewer actions against synthetic asynchronous list responses."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest


def test_select_loads_details_immediately_without_resetting_edited_payload():
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js required for console behavior")
    asset = Path(__file__).parents[1] / "submission_review/static/app.js"
    harness = r"""
const fs=require('node:fs'),vm=require('node:vm'),calls=[];
const ctx=vm.createContext({calls,document:{getElementById(){return {value:'',checked:false};}}});
vm.runInContext(fs.readFileSync(process.argv[1],'utf8')+`
function boot(){} function renderQueue(){} function renderDetail(){}
function scheduleUrlRefresh(){calls.push('scheduled');}
`,ctx);
(async()=>{
await vm.runInContext(`(async()=>{
let resolve;
edge=(body)=>{calls.push(body.action);return new Promise(r=>resolve=r);};
select({id:'a',evidence_revision:2,evidence_manifest_sha256:'same'});
state.payload.fullName='Reviewer edit';
resolve({submissions:[{id:'a',evidence_revision:2,evidence_manifest_sha256:'same',extractions:[{version:1}]}]});
await Promise.resolve();
calls.push(state.payload.fullName);
calls.push(state.selected.extractions[0].version);
})()`,ctx);
console.log(JSON.stringify(calls));
})().catch(e=>{console.error(e);process.exitCode=1;});
"""
    run = subprocess.run([node, "-e", harness, str(asset)], capture_output=True, text=True, timeout=10, check=True)
    assert json.loads(run.stdout) == ["list", "scheduled", "Reviewer edit", 1]


@pytest.mark.parametrize("change", ["revision", "digest", "selection", "unchanged"])
def test_refresh_never_rebinds_old_human_review_to_new_evidence(change):
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js required for console behavior")
    asset = Path(__file__).parents[1] / "submission_review/static/app.js"
    harness = r"""
const fs=require('node:fs'),vm=require('node:vm');
const [asset,change]=process.argv.slice(1), calls=[];
const ctx=vm.createContext({calls,change,document:{getElementById(){return {value:'',checked:false};}}});
vm.runInContext(fs.readFileSync(asset.replace('app.js','canonical.js'),'utf8'),ctx);
vm.runInContext(fs.readFileSync(asset,'utf8')+`
function boot(){} function renderDetail(){} function renderQueue(){}
function scheduleUrlRefresh(){} function syncScalarFields(){} function setStatus(){}
function setDecisionAvailability(){} async function loadQueue(){}
`,ctx);
(async()=>{
await vm.runInContext(`(async()=>{
state.selected={id:'a',kind:'label_mismatch',review_status:'under_review',evidence_revision:1,evidence_manifest_sha256:'a'.repeat(64)};
state.payload={fullName:'Old draft'};state.identityRecorded='no_match_verified';state.productImage={id:'old'};
state.payloadCanonical=canonicalJson(state.payload);state.payloadSha='c'.repeat(64);
state.diagnostics=[];  // the importer's validator has answered: nothing wrong

state.verifiedKey=verificationKey();state.verified=new Set(CRITICAL_FIELDS.map(([key])=>key));
edge=async(body)=>{
  if(body.action!=='list'){calls.push(body);return {};}
  if(change==='selection'){state.selected={id:'b'};state.payload={fullName:'Selected B'};}
  return {submissions:[{id:'a',kind:'label_mismatch',review_status:'under_review',evidence_revision:change==='revision'?2:1,
    evidence_manifest_sha256:change==='digest'?'b'.repeat(64):'a'.repeat(64)}]};
};
await refreshSelected();
if(change!=='selection') await approve();
})()`,ctx);
console.log(JSON.stringify({calls,...vm.runInContext('({selected:state.selected,payload:state.payload,identity:state.identityRecorded,image:state.productImage})',ctx)}));
})().catch(e=>{console.error(e);process.exitCode=1});
"""
    completed = subprocess.run([node, "-e", harness, str(asset), change], capture_output=True, text=True, timeout=15, check=True)
    result = json.loads(completed.stdout)
    if change == "unchanged":
        assert len(result["calls"]) == 1
        assert result["calls"][0]["approved_payload"]["fullName"] == "Old draft"
    elif change == "selection":
        assert result["selected"]["id"] == "b"
        assert result["payload"]["fullName"] == "Selected B"
    else:
        assert result["calls"] == []
        assert result["payload"].get("fullName") != "Old draft"
        assert result["identity"] is None and result["image"] is None


def test_a_decision_reloads_the_review_so_the_approved_label_shows():
    """After Approve the console refreshed the status but kept the review it had
    loaded before the decision, so the approved label was missing and the page
    said it 'could not be loaded' (S03, 2026-10-22). A status change reloads it."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js required for console behavior")
    asset = Path(__file__).parents[1] / "submission_review/static/app.js"
    harness = r"""
const fs=require('node:fs'),vm=require('node:vm');
const [asset]=process.argv.slice(1), calls=[];
const ctx=vm.createContext({calls,document:{getElementById(){return {value:'',checked:false,hidden:true,textContent:''};}}});
vm.runInContext(fs.readFileSync(asset.replace('app.js','canonical.js'),'utf8'),ctx);
vm.runInContext(fs.readFileSync(asset,'utf8')+`
function boot(){} function renderDetail(){} function renderQueue(){} function scheduleUrlRefresh(){}
function setStatus(){} function setDecisionAvailability(){} async function loadQueue(){}
function syncFieldsFromPayload(){} function renderRows(){} async function updateShaPreview(){}
function renderProductPictureOptions(){} function renderVerifyChecklist(){} function renderReadiness(){}
function renderBarcodePanel(){} function setApprovedReadOnly(){} async function autoPrepare(){} async function checkIdentity(){}
`,ctx);
(async()=>{
await vm.runInContext(`(async()=>{
state.session={access_token:'t'};
state.selected={id:'a',kind:'missing_product',review_status:'under_review',evidence_revision:1,evidence_manifest_sha256:'a'.repeat(64)};
state.reviewLoadedFor='a:1';
state.review={draft:{payload:{fullName:'Draft'}},approved_label:null};
edge=async(body)=>{
  calls.push(body.action);
  if(body.action==='list') return {submissions:[{id:'a',kind:'missing_product',review_status:'approved',evidence_revision:1,evidence_manifest_sha256:'a'.repeat(64)}]};
  if(body.action==='load_review') return {review:{approved_label:{approved_payload:{fullName:'Approved'}},draft:null,verifications:[],reviewer_images:[]}};
  return {};
};
await refreshSelected();
})()`,ctx);
console.log(JSON.stringify({calls,...vm.runInContext('({approved:state.review?.approved_label?.approved_payload?.fullName ?? null,payload:state.payload?.fullName ?? null})',ctx)}));
})().catch(e=>{console.error(e);process.exitCode=1});
"""
    completed = subprocess.run([node, "-e", harness, str(asset)], capture_output=True, text=True, timeout=15, check=True)
    result = json.loads(completed.stdout)
    assert "load_review" in result["calls"]
    assert result["approved"] == "Approved"
    assert result["payload"] == "Approved"


def test_starting_a_review_does_not_reload_over_unsaved_edits():
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js required for console behavior")
    asset = Path(__file__).parents[1] / "submission_review/static/app.js"
    harness = r"""
const fs=require('node:fs'),vm=require('node:vm');
const [asset]=process.argv.slice(1), calls=[];
const ctx=vm.createContext({calls,document:{getElementById(){return {value:'',checked:false,hidden:true,textContent:''};}}});
vm.runInContext(fs.readFileSync(asset.replace('app.js','canonical.js'),'utf8'),ctx);
vm.runInContext(fs.readFileSync(asset,'utf8')+`
function boot(){} function renderDetail(){} function renderQueue(){} function scheduleUrlRefresh(){}
function setStatus(){} function setDecisionAvailability(){} async function loadQueue(){} async function autoPrepare(){}
`,ctx);
(async()=>{
await vm.runInContext(`(async()=>{
state.session={access_token:'t'};
state.selected={id:'a',kind:'missing_product',review_status:'submitted',evidence_revision:1,evidence_manifest_sha256:'a'.repeat(64)};
state.reviewLoadedFor='a:1'; state.payload={fullName:'Unsaved edit'};
edge=async(body)=>{ calls.push(body.action);
  if(body.action==='list') return {submissions:[{id:'a',kind:'missing_product',review_status:'under_review',evidence_revision:1,evidence_manifest_sha256:'a'.repeat(64)}]};
  return {review:{draft:{payload:{fullName:'Older saved draft'}},verifications:[],reviewer_images:[]}}; };
await refreshSelected();
})()`,ctx);
console.log(JSON.stringify({calls,payload:vm.runInContext('state.payload.fullName',ctx)}));
})().catch(e=>{console.error(e);process.exitCode=1});
"""
    completed = subprocess.run([node, "-e", harness, str(asset)], capture_output=True, text=True, timeout=15, check=True)
    result = json.loads(completed.stdout)
    assert "load_review" not in result["calls"]
    assert result["payload"] == "Unsaved edit"
