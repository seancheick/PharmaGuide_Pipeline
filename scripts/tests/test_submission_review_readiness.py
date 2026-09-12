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
vm.runInContext(fs.readFileSync(asset.replace('app.js','canonical.js'),'utf8'),ctx);
vm.runInContext(fs.readFileSync(asset,'utf8')+`
function boot(){} function renderRows(){} function syncFieldsFromPayload(){}
function setStatus(){} function renderDraft(){} function renderQueue(){}
function scheduleUrlRefresh(){} function renderIdentityCheck(){}
function renderProductPictureOptions(){} function updateShaPreview(){}
`,ctx);
vm.runInContext(`
state.selected = ${JSON.stringify(setup.submission)};
state.payload = {brandName:'Example'};
state.payloadCanonical = canonicalJson(state.payload);
state.payloadSha = ${JSON.stringify(setup.payload_sha)};
state.identityRecorded = ${JSON.stringify(setup.identity)};
state.productImage = ${setup.product_image ? "{id:'p'}" : 'null'};
state.reviewInvalidated = ${setup.invalidated ? 'true' : 'false'};
state.diagnostics = ${JSON.stringify(setup.diagnostics)};
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


def _exercise(script):
    """Run real state transitions; only browser/HTTP boundaries are simulated."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js required for console behavior")
    harness = r"""
const fs=require('node:fs'),vm=require('node:vm');
function el(id){return {id,children:[],value:'',checked:false,disabled:false,open:false,
  classList:{add(){},remove(){},toggle(){}},style:{setProperty(){}},listeners:{},
  set textContent(v){this.text=v;this.children=[]},get textContent(){return this.text||''},
  append(...items){this.children.push(...items)},
  addEventListener(kind,fn){this.listeners[kind]=fn},
  querySelector(){return this},showModal(){this.open=true},close(){this.open=false}}}
const nodes={},pending=[],calls=[],out={};
const document={getElementById:id=>(nodes[id] ||= el(id)),createElement:()=>el(''),
 createTextNode:text=>({textContent:text}),querySelector:()=>Object.values(nodes).find(n=>n.open),
 addEventListener(){}};
const ctx=vm.createContext({document,console,out,pending,calls,
 structuredClone:v=>JSON.parse(JSON.stringify(v))});
vm.runInContext(fs.readFileSync(process.argv[1].replace('app.js','canonical.js'),'utf8'),ctx);
vm.runInContext(fs.readFileSync(process.argv[1],'utf8')+`
function boot(){} function setStatus(message){out.status=message;}
function renderRows(){} function renderStatements(){} function scheduleUrlRefresh(){}
function renderDetail(){} function renderQueue(){}
sha256Hex=(text)=>new Promise(resolve=>pending.push({text,resolve}));
edge=async body=>{calls.push(body);return {};};
state.selected={id:'s1',kind:'label_mismatch',review_status:'under_review',evidence_revision:2,
 evidence_manifest_sha256:'a'.repeat(64)};
state.payload={brandName:'Original'};
state.payloadSha='a'.repeat(64);
state.payloadCanonical=canonicalJson(state.payload);
state.diagnostics=[];
for(const [field] of CRITICAL_FIELDS) toggleVerified(field);
`,ctx);
(async()=>{await vm.runInContext(process.argv[2],ctx);console.log(JSON.stringify(out));})()
.catch(e=>{console.error(e);process.exitCode=1});
"""
    result = subprocess.run([node, "-e", harness, str(ASSET), script],
                            capture_output=True, text=True, check=True, timeout=15)
    return json.loads(result.stdout)


def test_real_edit_revokes_checks_before_the_hash_finishes():
    out = _exercise("""(async()=>{
      state.payload.brandName='Edited';
      const hashing=updateShaPreview();
      out.disabled=document.getElementById('t-approve').disabled;
      out.checked=verifiedSet().size;
      pending[0].resolve('b'.repeat(64)); await hashing;
      out.after=verifiedSet().size;
    })()""")
    assert out == {"disabled": True, "checked": 0, "after": 0}


def test_older_hash_completion_cannot_rebind_newer_payload():
    out = _exercise("""(async()=>{
      state.payload.brandName='First'; const first=updateShaPreview();
      state.payload.brandName='Second'; const second=updateShaPreview();
      pending[1].resolve('c'.repeat(64)); await second;
      for(const [field] of CRITICAL_FIELDS) toggleVerified(field);
      pending[0].resolve('b'.repeat(64)); await first;
      out.sha=state.payloadSha; out.checked=verifiedSet().size;
    })()""")
    assert out == {"sha": "c" * 64, "checked": 5}


def test_approve_action_itself_refuses_unchecked_fields():
    out = _exercise("""(async()=>{
      toggleVerified('rows'); await approve(); out.calls=calls.length;
    })()""")
    assert out["calls"] == 0
    assert "ingredient" in out["status"].lower()


def test_selecting_last_required_image_refreshes_approval_after_save():
    out = _exercise("""(async()=>{
      state.selected.kind='missing_product'; state.identityRecorded='no_match_verified';
      state.selected.photos=[{photo_id:'p1',categories:['front_identity'],signed_url:'fixture'}];
      renderProductPictureOptions(); setDecisionAvailability();
      out.before=document.getElementById('t-approve').disabled;
      document.getElementById('product-picture-options').children[0].children[0].listeners.change();
      out.during=document.getElementById('t-approve').disabled;
      await state.pictureSavePromise;
      out.after=document.getElementById('t-approve').disabled;
      out.saved=calls.some(call=>call.action==='set_review_image');
    })()""")
    assert out == {"before": True, "during": True, "after": False, "saved": True}


def test_keyboard_does_not_approve_under_an_open_dialog():
    out = _exercise("""(async()=>{
      document.getElementById('help-drawer').showModal();
      approve=()=>calls.push('approved');
      handleShortcut({key:'a',target:{tagName:'BUTTON'},preventDefault(){}});
      out.calls=calls.length;
    })()""")
    assert out == {"calls": 0}


def test_help_blocks_shortcuts_while_its_content_is_still_loading():
    out = _exercise("""(async()=>{
      let resolve;
      globalThis.fetch=()=>new Promise(done=>resolve=done);
      const loading=openHelp();
      approve=()=>calls.push('approved');
      handleShortcut({key:'a',target:{tagName:'BUTTON'},preventDefault(){}});
      out.calls=calls.length;
      resolve({json:async()=>({})});await loading;
    })()""")
    assert out == {"calls": 0}


def test_help_does_not_author_a_second_copy_of_consumer_resolution_text():
    help_data = json.loads((ASSET.parent / 'help.json').read_text())
    assert all('user_sees' not in entry for entry in help_data['rejections'])
    assert 'The submitter sees:' not in ASSET.read_text()


def test_approval_rechecks_payload_after_waiting_for_identity():
    out = _exercise("""(async()=>{
      state.selected.kind='missing_product';state.selected.normalized_upc='012345678905';
      state.identityRecorded='no_match_verified';state.productImage={kind:'photo',id:'p1'};
      state.identityLookup={canonical_gtin14:'00012345678905',index_revision:'source',freshness:'fresh'};
      let finish;
      globalThis.fetch=()=>new Promise(resolve=>finish=resolve);
      const approval=approve();
      state.payload.brandName='Edited while identity was checked';
      finish({ok:true,json:async()=>state.identityLookup});await approval;
      out.calls=calls.length;
    })()""")
    assert out['calls'] == 0
    assert 'changed' in out['status'].lower()


def test_recording_identity_refreshes_readiness_immediately():
    out = _exercise("""(async()=>{
      state.selected.kind='missing_product';state.selected.normalized_upc='012345678905';
      state.identityRecorded=null;state.productImage={kind:'photo',id:'p1'};
      state.identityLookup={canonical_gtin14:'00012345678905',index_revision:'source',freshness:'fresh',matches:[]};
      globalThis.fetch=async()=>({ok:true,json:async()=>state.identityLookup});
      setDecisionAvailability();out.before=document.getElementById('t-approve').disabled;
      await recordMatch('no_match_verified');
      out.after=document.getElementById('t-approve').disabled;
    })()""")
    assert out == {'before': True, 'after': False}


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
        # The importer's validator has answered and found nothing. "Not yet
        # answered" is a separate state, and it blocks.
        "diagnostics": [],
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
    # Count the gates that exist rather than a number frozen at one moment:
    # adding a gate must not silently pass by leaving this assertion behind.
    done = len(out["items"])
    assert out["progress"].startswith(f"{done} of {done}")


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


def test_an_unanswered_label_check_is_not_treated_as_clean() -> None:
    out = _render(diagnostics=None)

    assert out["approveDisabled"] is True
    assert any("Waiting for the label check" in text for text in _blockers(out))


def test_importer_problems_block_approval_and_are_counted() -> None:
    out = _render(diagnostics=[
        {"path": "ingredientRows[2]", "message": "amount must be a number"},
        {"path": "servingSizes[0]", "message": "minQuantity required"},
    ])

    assert out["approveDisabled"] is True
    assert any("Fix the 2 problems" in text for text in _blockers(out))


def test_a_photo_request_names_the_ticked_panels_against_the_evidence_on_screen():
    out = _exercise("""(async()=>{
      state.selected.kind='missing_product';
      document.getElementById('retake-supplement_facts').checked=true;
      document.getElementById('retake-barcode').checked=true;
      document.getElementById('retake-reason').value='label_unreadable';
      await requestEvidence();
      out.first=calls[0];
    })()""")
    assert out["first"] == {
        "action": "request_evidence",
        "submission_id": "s1",
        "expected_evidence_revision": 2,
        "evidence_manifest_sha256": "a" * 64,
        "reason": "label_unreadable",
        "panels": ["supplement_facts", "barcode"],
    }


def test_a_photo_request_with_no_panel_ticked_sends_nothing():
    out = _exercise("""(async()=>{
      state.selected.kind='missing_product';
      await requestEvidence();
      out.calls=calls.length;
    })()""")
    assert out["calls"] == 0
    assert "Tick the panel" in out["status"]


def test_photo_requests_are_offered_only_for_open_missing_product_reviews():
    out = _exercise("""(async()=>{
      const button=document.getElementById('t-request-evidence');
      setDecisionAvailability(); out.correction=button.disabled;
      state.selected.kind='missing_product';
      setDecisionAvailability(); out.open=button.disabled;
      state.selected.review_status='rejected';
      setDecisionAvailability(); out.closed=button.disabled;
    })()""")
    assert out == {"correction": True, "open": False, "closed": True}


def test_an_open_request_reads_as_waiting_and_a_newer_revision_as_answered():
    out = _exercise("""(async()=>{
      const asked={evidence_requested_at:'t',evidence_requested_revision:2,
        evidence_revision:2,evidence_request_reason:'photo_quality',
        evidence_request_panels:['supplement_facts']};
      out.waiting=evidenceRequestNote(asked);
      out.answered=evidenceRequestNote({...asked,evidence_revision:3});
      out.none=evidenceRequestNote({evidence_revision:1});
    })()""")
    assert out["waiting"].startswith("waiting for new photos of: supplement_facts")
    assert out["answered"].startswith("new photos received")
    assert "revision 3" in out["answered"]
    assert out["none"] is None


# ---------------------------------------------------------------------------
# A barcode the catalog already uses: correction or separate edition
# ---------------------------------------------------------------------------


def _catalog_hit(script: str) -> dict:
    """A missing-product capture whose barcode names one catalog record."""
    return _exercise("""
      state.selected={id:'s2',kind:'missing_product',review_status:'under_review',
        normalized_upc:'016500558170',evidence_revision:1,
        evidence_manifest_sha256:'a'.repeat(64)};
      state.productImage={kind:'photo',id:'p1'};
      state.identityRecorded='catalog_match';
      state.identityLookup={canonical_gtin14:'00016500558170',index_revision:'r1',
        freshness:'fresh',index_built_at:'2026-09-10T08:45:34Z',matches:[
          {source:'catalog',dsld_id:'178392',brand_name:'One A Day',
           product_name:"Women's Prenatal 1"},
          {source:'corpus',dsld_id:'178392',brand_name:'One A Day',
           product_name:"Women's Prenatal 1",draft_payload:{
             brandName:'One A Day',fullName:"Women's Prenatal 1",
             servingsPerContainer:30,
             servingSizes:[{minQuantity:1,maxQuantity:1,unit:'Softgel(s)'}],
             ingredientRows:[
               {name:'Biotin',quantity:[{quantity:300,unit:'mcg'}]},
               {name:'Folic Acid',quantity:[{quantity:800,unit:'mcg'}]}]}}]};
      state.payload={brandName:'One A Day',fullName:'Prenatal',
        servingsPerContainer:30,
        servingSizes:[{minQuantity:1,maxQuantity:1,unit:'Softgel(s)'}],
        ingredientRows:[
          {name:'Biotin',quantity:[{quantity:35,unit:'mcg'}]},
          {name:'Folate',quantity:[{quantity:1330,unit:'mcg DFE'}]}]};
    """ + script)


def test_a_catalog_hit_alone_never_authorizes_an_approval():
    out = _catalog_hit("""
      renderReadiness();
      out.blocked=(document.getElementById('readiness-list').children||[])
        .filter(n=>n.className==='blocking').map(n=>n.textContent);
    """)
    assert any("corrects that record or is a separate edition" in text
               for text in out["blocked"]), out["blocked"]


def test_the_comparison_shows_what_actually_differs():
    out = _catalog_hit("""
      const rows=labelComparisonRows(state.payload,
        state.identityLookup.matches[1].draft_payload);
      out.rows=rows;
      out.differing=rows.filter(([,mine,theirs])=>mine!==theirs).map(r=>r[0]);
    """)
    # The product name, both biotin amounts, and each folate spelling differ.
    assert "Biotin" in out["differing"]
    assert "Product name" in out["differing"]
    assert ["Servings per container", "30", "30"] in out["rows"]
    assert ["Serving size", "1 Softgel(s)", "1 Softgel(s)"] in out["rows"]
    assert ["Biotin", "35 mcg", "300 mcg"] in out["rows"]
    assert ["Folate", "1330 mcg DFE", "not on that record"] in out["rows"]


def test_choosing_correction_or_edition_clears_the_blocker():
    for kind, expected in (
        ("correction", "corrects catalog record 178392"),
        ("edition", "separate edition beside catalog record 178392"),
    ):
        out = _catalog_hit(f"""
          chooseCatalogRelation({kind!r}, '178392');
          out.done=(document.getElementById('readiness-list').children||[])
            .filter(n=>n.className==='ready').map(n=>n.textContent);
        """)
        assert any(expected in text for text in out["done"]), out["done"]


def test_the_decision_travels_with_the_approval():
    for kind, field in (
        ("correction", "correction_target_dsld_id"),
        ("edition", "edition_of_dsld_id"),
    ):
        out = _catalog_hit(f"""(async()=>{{
          state.payloadSha='a'.repeat(64);
          state.payloadCanonical=canonicalJson(state.payload);
          state.diagnostics=[];
          for(const [field] of CRITICAL_FIELDS) toggleVerified(field);
          chooseCatalogRelation({kind!r}, '178392');
          requireCurrentIdentity=async()=>state.identityLookup;
          await approve();
          out.call=calls.filter(c=>c.to_status==='approved')[0]||null;
        }})()""")
        assert out["call"], "approval was refused"
        assert out["call"][field] == "178392"
        other = ({"correction_target_dsld_id", "edition_of_dsld_id"} - {field}).pop()
        assert other not in out["call"]


def test_a_verified_no_match_still_carries_no_catalog_relation():
    out = _exercise("""(async()=>{
      state.selected={id:'s3',kind:'missing_product',review_status:'under_review',
        normalized_upc:'0850051911561',evidence_revision:1,
        evidence_manifest_sha256:'a'.repeat(64)};
      state.productImage={kind:'photo',id:'p1'};
      state.identityRecorded='no_match_verified';
      state.identityLookup={canonical_gtin14:'00850051911561',index_revision:'r1',
        freshness:'fresh',matches:[]};
      state.diagnostics=[];
      for(const [field] of CRITICAL_FIELDS) toggleVerified(field);
      requireCurrentIdentity=async()=>state.identityLookup;
      await approve();
      out.call=calls.filter(c=>c.to_status==='approved')[0]||null;
    })()""")
    assert out["call"], "approval was refused"
    assert "correction_target_dsld_id" not in out["call"]
    assert "edition_of_dsld_id" not in out["call"]


def test_a_decision_dies_with_the_match_check_it_was_made_against():
    """A relation is only as good as the recorded check that supports it.

    Re-running the lookup after the catalog moved can retract the match the
    decision was made against. The decision must not outlive it and reach an
    approval, where the server would refuse it as a mismatch the reviewer
    cannot see.
    """
    out = _catalog_hit("""(async()=>{
      chooseCatalogRelation('edition', '178392');
      // The catalog moved: this barcode is nobody else's now.
      state.identityLookup={canonical_gtin14:'00016500558170',index_revision:'r2',
        freshness:'fresh',matches:[]};
      state.identityRecorded='no_match_verified';
      state.payloadSha='a'.repeat(64);
      state.payloadCanonical=canonicalJson(state.payload);
      state.diagnostics=[];
      for(const [field] of CRITICAL_FIELDS) toggleVerified(field);
      requireCurrentIdentity=async()=>state.identityLookup;
      await approve();
      out.call=calls.filter(c=>c.to_status==='approved')[0]||null;
    })()""")
    assert out["call"], "approval was refused"
    assert "edition_of_dsld_id" not in out["call"]
    assert "correction_target_dsld_id" not in out["call"]


def test_a_decision_for_another_record_never_rides_along():
    """The lookup now names a different catalog record than the one decided."""
    out = _catalog_hit("""
      chooseCatalogRelation('correction', '178392');
      state.identityLookup.matches=[{source:'catalog',dsld_id:'299239',
        brand_name:'Other',product_name:'Other'}];
      renderReadiness();
      out.blocked=(document.getElementById('readiness-list').children||[])
        .filter(n=>n.className==='blocking').map(n=>n.textContent);
    """)
    assert any("corrects that record or is a separate edition" in text
               for text in out["blocked"]), out["blocked"]
