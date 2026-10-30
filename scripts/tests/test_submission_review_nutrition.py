"""Nutrition Facts capture in the reviewer console, executed against app.js.

The rule these defend: nutritionalInfo is the exact raw shape DSLD ships and
enrich_supplements_v3.py's _collect_nutrition_summary already reads — one
brain for both catalog and submission products. A reviewer who leaves every
row blank (most supplements have no Nutrition Facts panel) must produce a
payload with no nutritionalInfo key at all, never a payload full of
fabricated zeros.

This runs the shipped asset in a sandbox, so what is asserted is the
behaviour that ships; only the browser and HTTP boundaries are simulated.
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
function renderVerifyChecklist(){} function renderReadiness(){}
function setDecisionAvailability(){} function scheduleReviewSave(){}
function refreshDiagnostics(){return Promise.resolve();}
sha256Hex=async(text)=>'a'.repeat(63)+(text.length%10).toString(16);
state.session={access_token:'fixture'};
state.selected={id:'s1',kind:'missing_product',review_status:'under_review',
 evidence_revision:1,evidence_manifest_sha256:'e'.repeat(64)};
state.payload=defaultPayload();
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


def test_blank_nutrition_fields_never_enter_the_payload():
    # Most supplements have no Nutrition Facts panel. A blank row must not
    # become a fabricated 0 in the payload the importer eventually ships.
    out = _exercise("""(()=>{
      syncNutritionFields();
      out.hasKey='nutritionalInfo' in state.payload;
    })()""")
    assert out["hasKey"] is False


def test_filled_rows_become_dslds_raw_amount_unit_shape():
    out = _exercise("""(()=>{
      document.getElementById('n-calories').value='10';
      document.getElementById('n-total-fat').value='1';
      document.getElementById('n-sodium').value='140';
      syncNutritionFields();
      out.info=state.payload.nutritionalInfo;
    })()""")
    assert out["info"] == {
        "calories": {"amount": 10, "unit": "kcal"},
        "totalFat": {"amount": 1, "unit": "g"},
        "sodium": {"amount": 140, "unit": "mg"},
    }


def test_a_row_left_blank_is_omitted_not_zeroed():
    out = _exercise("""(()=>{
      document.getElementById('n-calories').value='10';
      document.getElementById('n-total-carb').value='';
      syncNutritionFields();
      out.info=state.payload.nutritionalInfo;
    })()""")
    assert "totalCarbohydrates" not in out["info"]
    assert out["info"]["calories"] == {"amount": 10, "unit": "kcal"}


def test_clearing_every_row_removes_the_key_again():
    out = _exercise("""(()=>{
      document.getElementById('n-calories').value='10';
      syncNutritionFields();
      document.getElementById('n-calories').value='';
      syncNutritionFields();
      out.hasKey='nutritionalInfo' in state.payload;
    })()""")
    assert out["hasKey"] is False


def test_reopening_a_submission_repopulates_the_typed_amounts():
    # A reviewer who saves, reloads, and reopens this submission must see
    # exactly what they typed, not a blank Nutrition Facts panel.
    out = _exercise("""(()=>{
      state.payload.nutritionalInfo={
        calories:{amount:10,unit:'kcal'},
        totalFat:{amount:1,unit:'g'},
      };
      syncFieldsFromPayload();
      out.calories=document.getElementById('n-calories').value;
      out.fat=document.getElementById('n-total-fat').value;
      out.carb=document.getElementById('n-total-carb').value;
    })()""")
    assert out == {"calories": 10, "fat": 1, "carb": ""}


def test_a_printed_bound_is_typed_as_a_bound_not_an_exact_amount():
    # S19 ARMRA prints "Total Carbohydrates <1g"; that is not exactly 1 g.
    out = _exercise("""(()=>{
      document.getElementById('n-total-carb').value='<1';
      document.getElementById('n-protein').value='less than 1';
      document.getElementById('n-poly-fat').value='0.5';
      document.getElementById('n-sugars').value='<about';
      syncNutritionFields();
      out.info=state.payload.nutritionalInfo;
      syncFieldsFromPayload();
      out.carb=document.getElementById('n-total-carb').value;
    })()""")
    assert out["info"] == {
        "polyunsaturatedFat": {"amount": 0.5, "unit": "g"},
        "totalCarbohydrates": {"amount": 1, "unit": "g", "operator": "<"},
        "protein": {"amount": 1, "unit": "g", "operator": "<"},
    }
    assert out["carb"] == "<1"


def test_approximate_servings_per_container_keep_their_printed_wording():
    out = _exercise("""(()=>{
      const field=document.getElementById('p-servings-count');
      field.value='about 17'; syncScalarFields(); out.about=state.payload.servingsPerContainer;
      field.value='60'; syncScalarFields(); out.exact=state.payload.servingsPerContainer;
      field.value='17ish'; syncScalarFields(); out.bad=state.payload.servingsPerContainer;
      field.value='1,5'; syncScalarFields(); out.comma=state.payload.servingsPerContainer;
      field.value='1,000'; syncScalarFields(); out.grouped=state.payload.servingsPerContainer;
    })()""")
    assert out == {"about": "about 17", "exact": 60, "bad": None, "comma": None, "grouped": 1000}
