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
