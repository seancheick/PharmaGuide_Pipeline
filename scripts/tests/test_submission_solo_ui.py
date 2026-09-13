"""Execute the solo workflow against the shipped JS, without a browser service."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ASSET = Path(__file__).parents[1] / "submission_review/static/solo.js"
HARNESS = r'''
const fs=require('node:fs'), vm=require('node:vm');
const controls={}, output={}, time={now:1000};
const node=id=>controls[id]??=( {hidden:false,checked:true,value:'',textContent:'',classList:{},dataset:{},
 getContext:()=>({drawImage:(...args)=>{output.draw=args.slice(1);}}),showModal(){output.modal=id;},close(){}} );
const row=(name,amount,order)=>({name,quantity:[{quantity:amount,unit:'mg'}],forms:[],nestedRows:[],order});
const payload={brandName:'B',fullName:'P',ingredientRows:[row('C',500,1),row('Zinc',10,2)]};
const docEvents={},winEvents={};
const ctx=vm.createContext({console,structuredClone,time,docEvents,winEvents,performance:{now:()=>time.now},
 createImageBitmap:async()=>({width:1000,height:500,close(){}}),fetchReviewPhoto:async()=>({}),
 setStatus:message=>{output.error=message;},
 document:{getElementById:node,querySelectorAll:()=>[],hasFocus:()=>true,visibilityState:'visible',addEventListener:(e,f)=>{docEvents[e]=f;}},
 window:{prompt:()=> 'not on label',addEventListener:(e,f)=>{winEvents[e]=f;}},
 state:{selected:{id:'p',evidence_revision:1,evidence_manifest_sha256:'hash'},
        session:{user:{id:'sean'}},payload},
});
vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),ctx);
vm.runInContext(`SoloReview.start({version:1,draft_payload:{ingredient_rows:[]}},structuredClone(state.payload));`,ctx);
(async()=>{
 await vm.runInContext(`(async()=>{${process.argv[2]}})()`,ctx);
 const record=vm.runInContext('SoloReview.buildRecord()',ctx);
 process.stdout.write(JSON.stringify({...record,...output}));
})().catch(error=>{console.error(error);process.exitCode=1;});
'''


def run(code):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node required")
    result = subprocess.run([node, "-e", HARNESS, str(ASSET), code], capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


def test_confirm_correct_and_reorder_preserve_original_occurrences():
    result = run('''
      const rows=state.payload.ingredientRows;
      rows.forEach(SoloReview.confirm);
      rows[0].quantity[0].quantity=250;
      SoloReview.changed();
      rows.reverse();
    ''')
    assert result["original_machine_payload"]["ingredientRows"][0]["quantity"][0]["quantity"] == 500
    assert result["rows"] == [
        {"original_index": 1, "reviewed_index": 0, "confirmed": True},
        {"original_index": 0, "reviewed_index": 1, "confirmed": False},
    ]


def test_removed_and_added_rows_are_explicit():
    result = run('''
      SoloReview.remove(state.payload.ingredientRows[0]);
      state.payload.ingredientRows.shift();
      state.payload.ingredientRows.push({name:'Magnesium',quantity:[{quantity:100,unit:'mg'}]});
      state.payload.ingredientRows.forEach(SoloReview.confirm);
    ''')
    assert result["rows"][1]["original_index"] is None
    assert result["rows"][2] == {"original_index": 0, "reviewed_index": None, "confirmed": True, "reason": "not on label"}


def test_photo_revision_change_prevents_old_record_export():
    with pytest.raises(subprocess.CalledProcessError):
        run("state.selected.evidence_revision=2;")


def test_raw_json_reordering_rebinds_only_exact_unique_rows():
    result = run('''
      const prior=SoloReview.flatten(state.payload.ingredientRows);
      prior.forEach(SoloReview.confirm);
      state.payload=JSON.parse(JSON.stringify(state.payload));
      state.payload.ingredientRows.reverse();
      SoloReview.rawReplaced(prior);
    ''')
    assert [row["original_index"] for row in result["rows"]] == [1, 0]


def test_changing_blend_owner_clears_confirmation():
    result = run('''
      const rows=state.payload.ingredientRows;
      rows.forEach(SoloReview.confirm);
      const child=rows.pop(); rows[0].nestedRows.push(child);
      SoloReview.changed();
    ''')
    assert result["rows"][1]["confirmed"] is False


def test_raw_correction_keeps_explicit_order_identity_and_invalidates_mark():
    result = run('''
      const prior=SoloReview.flatten(state.payload.ingredientRows);
      prior.forEach(SoloReview.confirm);
      state.payload=JSON.parse(JSON.stringify(state.payload));
      state.payload.ingredientRows[0].quantity[0].quantity=250;
      SoloReview.rawReplaced(prior);
    ''')
    assert len(result["rows"]) == 2
    assert result["rows"][0]["original_index"] == 0
    assert result["rows"][0]["confirmed"] is False


def test_evidence_crop_uses_original_normalized_region_with_context():
    result = run('''
      state.selected.photos=[{photo_id:'p1',signed_url:'fixture'}];
      SoloReview.start({version:1,draft_payload:{ingredient_rows:[]},grounding:{
        region_coordinate_space:'orientation_corrected_original',
        rows:[{row_index:0,photo_id:'p1',status:'supported',region:{x:.1,y:.2,w:.5,h:.1}}]
      }},structuredClone(state.payload));
      await SoloReview.evidence(0);
    ''')
    assert result["draw"][:4] == pytest.approx([75, 87.5, 550, 75])
    assert result["modal"] == "solo-evidence"


def test_invalid_region_falls_back_to_full_photo():
    result = run('''
      state.selected.photos=[{photo_id:'p1',signed_url:'fixture'}];
      SoloReview.start({version:1,draft_payload:{ingredient_rows:[]},grounding:{
        region_coordinate_space:'orientation_corrected_original',
        rows:[{row_index:0,photo_id:'p1',region:{x:.9,y:0,w:.5,h:.1}}]
      }},structuredClone(state.payload));
      await SoloReview.evidence(0);
    ''')
    assert result["draw"][:4] == [0, 0, 1000, 500]


def test_active_time_excludes_hidden_window_and_idle_after_30_seconds():
    result = run('''
      SoloReview.init();
      time.now=11000; document.visibilityState='hidden'; docEvents.visibilitychange();
      time.now=51000; document.visibilityState='visible'; docEvents.visibilitychange();
      docEvents.pointerdown();
      time.now=111000; docEvents.pointerdown();
    ''')
    assert result["active_seconds"] == 40
