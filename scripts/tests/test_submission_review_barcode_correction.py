"""The console lets a reviewer correct the barcode an owner filed.

The barcode lives in product_submissions.normalized_upc and nowhere else; the
console sends the correction, then takes the row back from the server. These
run the real app.js against a fake DOM and a fake edge function.
"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

REVIEW_DIR = Path(__file__).resolve().parents[1] / "submission_review"

HARNESS = r"""
const fs = require('node:fs');
const vm = require('node:vm');
const [asset, scenario] = process.argv.slice(1);
const calls = [];
const statuses = [];
const elements = new Map();
function element() {
  return {value: '', textContent: '', hidden: false, open: false, disabled: false,
    style: {}, classList: {add() {}, remove() {}}, append() {}, addEventListener() {}};
}
const filed = {id: 'submission', kind: 'missing_product', review_status: 'under_review',
  normalized_upc: '00671477', evidence_revision: 2, evidence_manifest_sha256: 'a'.repeat(64)};
// What the server holds after a correction: the one barcode, rewritten.
const fresh = {...filed, normalized_upc: '00671422'};
const context = vm.createContext({
  calls, statuses, filed, fresh, scenario,
  document: {createElement: element, getElementById(id) {
    if (!elements.has(id)) elements.set(id, element());
    return elements.get(id);
  }},
  fetch: async (url, options) => {
    const body = options?.body ? JSON.parse(options.body) : null;
    calls.push({url, body});
    if (body?.action === 'correct_barcode') {
      if (scenario === 'refused') {
        return {ok: false, status: 409, json: async () => ({
          error: 'That is not a valid barcode: the check digit does not match.'})};
      }
      return {ok: true, json: async () => ({corrected: {from_upc: '00671477', to_upc: '00671422'}})};
    }
    if (body?.action === 'list') return {ok: true, json: async () => ({submissions: [fresh]})};
    if (body?.action === 'load_review') return {ok: true, json: async () => ({review: {barcode_corrections: []}})};
    return {ok: true, json: async () => ({})};
  },
});
vm.runInContext(fs.readFileSync(asset.replace('app.js', 'canonical.js'), 'utf8'), context);
vm.runInContext(fs.readFileSync(asset, 'utf8') + `
function boot() {}
async function loadQueue() {}
async function refreshSelected() {}
let reloads = 0, hydrates = 0, lookups = 0, queueRenders = 0, detailRenders = 0;
async function loadReview() { reloads += 1; }
function hydrateReview() { hydrates += 1; }
async function checkIdentity() { lookups += 1; }
function renderQueue() { queueRenders += 1; }
function renderDetail() { detailRenders += 1; }
function setStatus(message, isError) { statuses.push([message, Boolean(isError)]); }
`, context);
(async () => {
  await vm.runInContext(`(async () => {
    state.selected = filed;
    state.submissions = [filed];
    state.session = {access_token: 'reviewer-test-session'};
    state.identityLookup = {canonical_gtin14: '00000000671477', matches: []};
    state.identityRecorded = 'no_match_verified';
    state.payload = {brandName: 'unsaved edit'};  // typed, not yet saved
    const requestBefore = state.identityCheckRequest;
    if (scenario !== 'empty') {
      $('barcode-new').value = '  0067 1422 ';
      $('barcode-reason').value = ' Bottle prints 0067 1422 ';
    } else {
      $('barcode-new').value = '0067 1422';
    }
    await correctBarcode();
    globalThis.requestBefore = requestBefore;
  })()`, context);
  process.stdout.write(JSON.stringify({
    calls, statuses,
    selectedUpc: vm.runInContext('state.selected.normalized_upc', context),
    selectedIsServerRow: vm.runInContext('state.selected === fresh && state.submissions[0] === fresh', context),
    listedUpc: vm.runInContext('state.submissions[0].normalized_upc', context),
    identityLookup: vm.runInContext('state.identityLookup', context),
    identityRecorded: vm.runInContext('state.identityRecorded', context),
    requestMoved: vm.runInContext('state.identityCheckRequest', context) !==
      vm.runInContext('requestBefore', context),
    reloads: vm.runInContext('reloads', context),
    hydrates: vm.runInContext('hydrates', context),
    lookups: vm.runInContext('lookups', context),
    payload: vm.runInContext('state.payload', context),
    newInput: context.document.getElementById('barcode-new').value,
    buttonDisabled: context.document.getElementById('barcode-save').disabled,
  }));
})().catch(error => {console.error(error); process.exitCode = 1;});
"""


def run(scenario):
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for reviewer interaction tests")
    result = subprocess.run(
        [node, "-e", HARNESS, str(REVIEW_DIR / "static" / "app.js"), scenario],
        capture_output=True, text=True, check=True, timeout=15,
    )
    return json.loads(result.stdout)


def edge_calls(observed):
    return [row["body"] for row in observed["calls"] if row["url"] == "/api/edge"]


def test_a_correction_is_bound_to_the_evidence_and_taken_back_from_the_server():
    observed = run("corrected")
    correction, listing, review = edge_calls(observed)
    assert correction == {
        "action": "correct_barcode",
        "submission_id": "submission",
        "new_upc": "0067 1422",
        "reason": "Bottle prints 0067 1422",
        "expected_evidence_revision": 2,
        "evidence_manifest_sha256": "a" * 64,
    }
    assert listing["action"] == "list" and listing["submission_id"] == "submission"
    # The page shows the server's row, in the selection and in the queue.
    assert observed["selectedUpc"] == observed["listedUpc"] == "00671422"
    assert observed["selectedIsServerRow"] is True  # not a locally patched copy
    assert review["action"] == "load_review" and review["submission_id"] == "submission"
    # The review state is refreshed and the new barcode is looked up once, but
    # the saved draft is not re-adopted over what the reviewer is typing.
    assert observed["reloads"] == 0
    assert observed["hydrates"] == 1 and observed["lookups"] == 1
    assert observed["payload"] == {"brandName": "unsaved edit"}
    assert observed["newInput"] == ""
    assert observed["buttonDisabled"] is False
    assert observed["statuses"][-1][1] is False
    assert "00671477" in observed["statuses"][-1][0] and "00671422" in observed["statuses"][-1][0]


def test_a_correction_discards_the_barcode_check_made_for_the_old_barcode():
    observed = run("corrected")
    assert observed["identityLookup"] is None
    assert observed["identityRecorded"] is None
    assert observed["requestMoved"] is True  # an in-flight lookup is ignored


def test_a_refused_correction_says_why_and_changes_nothing():
    observed = run("refused")
    assert [body["action"] for body in edge_calls(observed)] == ["correct_barcode"]
    assert observed["selectedUpc"] == observed["listedUpc"] == "00671477"
    assert observed["identityRecorded"] == "no_match_verified"
    assert observed["statuses"][-1] == [
        "That is not a valid barcode: the check digit does not match.", True]
    assert observed["buttonDisabled"] is False


def test_a_correction_needs_both_the_barcode_and_the_reason():
    observed = run("empty")
    assert edge_calls(observed) == []
    assert observed["statuses"][-1][1] is True


def test_the_barcode_panel_is_part_of_the_identity_step():
    html = (REVIEW_DIR / "static" / "index.html").read_text()
    for element_id in ("barcode-panel", "barcode-current", "barcode-history",
                       "barcode-correct", "barcode-new", "barcode-reason", "barcode-save"):
        assert f'id="{element_id}"' in html
    step = html[html.index('id="identity-check"'):html.index('id="identity-status-card"')]
    assert 'id="barcode-panel"' in step


def test_label_review_requires_explicit_complete_evidence_bound_decision():
    node = shutil.which('node')
    assert node
    program = r"""
const fs=require('fs'),vm=require('vm');const elements=new Map(),calls=[],candidateState={complete:true,pending:[],conflicts:[]};
function el(){return {value:'',textContent:'',hidden:false,disabled:false,style:{},classList:{add(){},remove(){}},append(){},setAttribute(){},addEventListener(){}}}
const ctx=vm.createContext({URLSearchParams,Date,Set,Number,encodeURIComponent,clearTimeout,
 document:{getElementById(id){if(!elements.has(id))elements.set(id,el());return elements.get(id)},createElement:el},
 fetch:async(url,options)=>{if(options?.method==='POST'){const body=JSON.parse(options.body);if(body.action==='save_review'){ctx.savedPayload=body.payload;if(ctx.deferSave)return new Promise(resolve=>ctx.resolveSave=resolve);return {ok:true,json:async()=>({review:{draft:{payload_sha256:'test-label-sha'}}})}};if(body.action==='load_review')return {ok:true,json:async()=>({review:{identity_candidates:candidateState}})};calls.push(body);if(ctx.deferMatch)return new Promise(resolve=>ctx.resolveMatch=resolve);return {ok:true,json:async()=>({})}}
 return {ok:true,json:async()=>lookup}}});
const lookup={identity_method:'label_review',canonical_gtin14:null,brandName:'Example Labs',fullName:'Vitamin D3',index_built_at:new Date().toISOString(),index_revision:'current',freshness:'fresh',complete:true,matches:[]};
ctx.lookup=lookup;ctx.calls=calls;
vm.runInContext(fs.readFileSync(process.argv[1],'utf8')+`\nfunction boot(){} function renderIdentityCheck(){} function setStatus(){} function hydrateReview(review){state.review=review} function renderReviewBanner(){} function setDecisionAvailability(){}\n`,ctx);
(async()=>{
vm.runInContext(`state.session={access_token:'test'};state.selected={id:'submission',kind:'missing_product',normalized_upc:null,identifier:{brandName:'Example Labs',fullName:'Vitamin D3'},evidence_revision:2,evidence_manifest_sha256:'a'.repeat(64)};state.payload={brandName:'Example Labs',fullName:'Vitamin D3'};state.payloadSha='test-label-sha';state.reviewReadyFor='submission:2';state.identityLookup=lookup`,ctx);
elements.set('identifier-type',{value:'amazon_fnsku'});elements.set('identifier-issuer',{value:'Amazon'});elements.set('identifier-package',{value:'60 capsules'});elements.set('identifier-reason',{value:'Verified package and complete candidate list'});
await vm.runInContext('checkIdentity({record:true})',ctx);
if(calls.length)throw Error('empty search auto-verified a new product');
await vm.runInContext("recordMatch('new_product_verified')",ctx);
if(!ctx.savedPayload)throw Error('identity decision not preceded by saved label draft');
const body=calls[0];if(body.identity_method!=='label_review'||body.candidate_review_complete!==true||body.canonical_gtin14!==null||body.identifier_decision.package!=='60 capsules')throw Error(JSON.stringify(body));
ctx.deferMatch=true;
const waiting=vm.runInContext("recordMatch('new_product_verified')",ctx);
while(!ctx.resolveMatch)await new Promise(setImmediate);
elements.get('identifier-reason').value='A changed reviewer rationale';
vm.runInContext('state.identityRecorded=null',ctx);
ctx.resolveMatch({ok:true,json:async()=>({})});
let staleDecision=false;try{await waiting}catch{staleDecision=true}
if(!staleDecision||vm.runInContext('state.identityRecorded',ctx)!==null)throw Error('late match response restored edited decision');
if(!vm.runInContext("approvalBlockers().some(check=>check.todo.includes('Run the barcode check'))",ctx))throw Error('edited decision did not block approval');
ctx.deferMatch=false;
ctx.deferSave=true;
const saving=vm.runInContext("recordMatch('new_product_verified')",ctx);
while(!ctx.resolveSave)await new Promise(setImmediate);
vm.runInContext("state.payload.fullName='Changed label while saving';state.identityRecorded=null",ctx);
ctx.resolveSave({ok:true,json:async()=>({review:{draft:{payload_sha256:'test-label-sha'}}})});
let staleSave=false;try{await saving}catch{staleSave=true}
if(!staleSave||calls.length!==2)throw Error('stale saved draft authorized match RPC');
ctx.deferSave=false;
vm.runInContext("state.payload.fullName='Vitamin D3'",ctx);
candidateState.conflicts.push({source:'pending',id:'other',revision:1});let stale=false;try{await vm.runInContext('requireCurrentIdentity()',ctx)}catch{stale=true}if(!stale)throw Error('new pending approval did not invalidate receipt');
vm.runInContext('state.identityLookup=lookup',ctx);lookup.complete=false;let refused=false;try{await vm.runInContext("recordMatch('new_product_verified')",ctx)}catch{refused=true}if(!refused||calls.length!==2)throw Error('incomplete candidate set accepted');
lookup.identity_method='gtin';lookup.canonical_gtin14='00050428381397';lookup.complete=true;
vm.runInContext("state.selected.normalized_upc='050428381397';state.identityLookup=lookup",ctx);
await vm.runInContext('checkIdentity({record:true})',ctx);
if(calls.length!==2)throw Error('v2 GTIN automatically invented reviewer decision');
elements.get('identifier-reason').value='';let noReason=false;
try{await vm.runInContext("recordMatch('no_match_verified')",ctx)}catch{noReason=true}
if(!noReason||calls.length!==2)throw Error('v2 GTIN accepted missing reviewer rationale');
console.log('ok');
})().catch(e=>{console.error(e);process.exitCode=1});
"""
    result = subprocess.run([node, '-e', program, str(REVIEW_DIR / 'static/app.js')], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == 'ok'
