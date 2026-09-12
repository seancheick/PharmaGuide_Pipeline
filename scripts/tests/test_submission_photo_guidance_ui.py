"""Exercise the real reviewer JS: hints must never become approval state."""
from test_submission_review_readiness import _exercise
from pathlib import Path
from html.parser import HTMLParser


def test_queue_errors_are_visible_before_a_submission_is_selected():
    class StatusLocation(HTMLParser):
        hidden_detail = False
        visible_status = False

        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if attrs.get('id') == 'detail-panel':
                self.hidden_detail = True
            if attrs.get('id') == 'status-line':
                self.visible_status = not self.hidden_detail

    parser = StatusLocation()
    parser.feed((Path(__file__).parents[1] / 'submission_review/static/index.html').read_text())
    assert parser.visible_status


SETUP = """
state.session = {access_token:'reviewer'};
state.selected.photos = [{photo_id:'p1', seq:1, content_sha256:'b'.repeat(64), categories:['front_identity']}];
const photo = state.selected.photos[0];
const report = {submission_id:'s1', photo_id:'p1', evidence_revision:2,
 evidence_manifest_sha256:'a'.repeat(64), photo_sha256:'b'.repeat(64),
 status:'suggestions', possible_role_mismatch:true, declared:['front_identity'],
 suggestions:[{role:'supplement_facts',text:'Supplement Facts',box:{left:1,top:2,right:3,bottom:4}}]};
function flatten(n){return [n.textContent,...(n.children||[]).map(flatten)].join(' ');}
"""


def test_photo_guidance_uses_only_evidence_ids_and_keeps_approval_untouched():
    out = _exercise(SETUP + """
(async()=>{
 const before=JSON.stringify({payload:state.payload,verified:[...state.verified]});
 fetch=async(url,options)=>{out.url=url;out.request=JSON.parse(options.body);
   return {ok:true,json:async()=>report};};
 await checkPhotoGuidance(photo);
 out.text=flatten(document.getElementById('photo-guidance'));
 out.unchanged=before===JSON.stringify({payload:state.payload,verified:[...state.verified]});
})()
""")
    assert out["url"] == "/api/photo_guidance"
    assert set(out["request"]) == {"submission_id", "photo_id", "evidence_revision", "evidence_manifest_sha256"}
    assert "Selected by submitter: Product identity" in out["text"]
    assert "Supplement Facts" in out["text"]
    assert "Please confirm" in out["text"]
    assert out["unchanged"] is True


def test_guidance_finishing_after_selection_change_is_discarded():
    out = _exercise(SETUP + """
(async()=>{
 let finish; fetch=()=>new Promise(resolve=>finish=resolve);
 const task=checkPhotoGuidance(photo);
 state.selected={...state.selected,id:'s2'};
 finish({ok:true,json:async()=>report}); await task;
 out.report=state.photoGuidanceReport;
})()
""")
    assert out["report"] is None


def test_signout_immediately_invalidates_pending_guidance():
    out = _exercise(SETUP + """
(async()=>{
 let finish; fetch=()=>new Promise(resolve=>finish=resolve);
 const task=checkPhotoGuidance(photo);
 let finishSignout; state.client={auth:{signOut:()=>new Promise(resolve=>finishSignout=resolve)}};
 window={location:{reload(){out.reloaded=true;}}};
 const signingOut=signOut();
 out.sessionCleared=state.session===null;
 finish({ok:true,json:async()=>report}); await task;
 out.report=state.photoGuidanceReport;out.pending=state.photoGuidancePending;
 finishSignout();await signingOut;
})()
""")
    assert out["sessionCleared"] is True
    assert out["report"] is None
    assert out["pending"] is False
    assert out["reloaded"] is True


def test_guidance_failure_leaves_a_useful_message_and_does_not_touch_label():
    out = _exercise(SETUP + """
(async()=>{
 fetch=async()=>({ok:false,json:async()=>({error:'unavailable'})});
 await checkPhotoGuidance(photo);
 out.text=flatten(document.getElementById('photo-guidance'));
 out.brand=state.payload.brandName;out.pending=state.photoGuidancePending;
})()
""")
    assert "review the photos manually" in out["text"]
    assert out["brand"] == "Original"
    assert out["pending"] is False


def test_refreshed_session_updates_requests_without_discarding_review():
    out = _exercise(SETUP + """
state.session={access_token:'old',user:{id:'reviewer'}};
state.photoGuidancePending=true;
const before=JSON.stringify({payload:state.payload,verified:[...state.verified]});
updateAuthSession('TOKEN_REFRESHED',{access_token:'new',user:{id:'reviewer'}});
out.token=state.session.access_token;out.pending=state.photoGuidancePending;
out.unchanged=before===JSON.stringify({payload:state.payload,verified:[...state.verified]});
""")
    assert out['token'] == 'new'
    assert out['pending'] is False
    assert out['unchanged'] is True


def test_expired_session_guidance_asks_for_signin_not_connection_retry():
    out = _exercise(SETUP + """
(async()=>{
 fetch=async()=>({ok:false,status:401,json:async()=>({error:'expired'})});
 await checkPhotoGuidance(photo);
 out.text=flatten(document.getElementById('photo-guidance'));
})()
""")
    assert 'Sign in again' in out['text']


def test_auth_signout_invalidates_work_without_initial_session_reload_loop():
    out = _exercise("""
window={location:{reload(){out.reloads=(out.reloads||0)+1;}}};
state.session=null;
updateAuthSession('INITIAL_SESSION',null);
out.initialReloads=out.reloads||0;
state.session={access_token:'old',user:{id:'reviewer'}};
state.photoGuidancePending=true;
updateAuthSession('SIGNED_OUT',null);
out.session=state.session;out.pending=state.photoGuidancePending;
""")
    assert out['initialReloads'] == 0
    assert out['reloads'] == 1
    assert out['session'] is None
    assert out['pending'] is False


def test_identity_copy_explains_catalog_match_without_asserting_label_equivalence():
    out = _exercise("""
state.selected.kind='missing_product';
state.identityLookup={freshness:'fresh',index_built_at:'2026-09-12T09:55:59Z',
 matches:[{source:'catalog',dsld_id:'299239',brand_name:'Ritual',product_name:'Synbiotic+'}]};
renderIdentityCheck();
out.actions=document.getElementById('identity-actions').children.map(n=>n.textContent);
out.result=document.getElementById('identity-results').children[0].textContent;
out.status=document.getElementById('identity-index-status').textContent;
""")
    assert "Same product and label — already in catalog" in out["actions"]
    assert "These are different products" in out["actions"]
    assert any("changed formula" in text and "Label differs — compare" in text
               for text in out["actions"])
    assert out["result"].startswith("Ritual Synbiotic+")
    assert "Compare the label" in out["status"]
