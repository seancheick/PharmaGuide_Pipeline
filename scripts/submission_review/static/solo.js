// Development convenience only. Existing server-side approval remains authoritative.
'use strict';
globalThis.SoloReview = (() => {
  let run = null;
  const flatten = (rows, out = []) => {
    for (const row of rows ?? []) { out.push(row); flatten(row.nestedRows, out); }
    return out;
  };
  const snapshot = row => JSON.stringify({...row, nestedRows: undefined, order: undefined});
  const binding = () => `${state.selected?.id}:${state.selected?.evidence_revision}:${state.selected?.evidence_manifest_sha256}`;
  const current = () => run && run.binding === binding();
  function reset() {
    run = null;
    const host = document.getElementById('solo-review');
    if (host) host.hidden = true;
  }
  function start(extraction, machinePayload) {
    const originals = flatten(machinePayload.ingredientRows);
    const edited = flatten(state.payload.ingredientRows);
    const rawGrounding = extraction.grounding ?? extraction.usage?.grounding ?? {};
    run = {
      binding: binding(), extraction: structuredClone(extraction),
      machine: structuredClone(machinePayload), refs: new WeakMap(), marks: new Map(), removed: new Map(),
      originals: structuredClone(originals), next: originals.length, active: 0,
      last: performance.now(), activity: performance.now(), paused: false,
      activeWindow: document.visibilityState !== 'hidden' && document.hasFocus(),
      grounding: {...rawGrounding, rows: originals.map((row, index) => ({
        ...(rawGrounding.rows ?? []).find(r => r.row_index === row.order - 1), row_index: index,
      }))},
    };
    edited.forEach((row, index) => run.refs.set(row, index));
    const host = document.getElementById('solo-review');
    if (host) {
      host.hidden = false;
      document.getElementById('solo-complete').checked = false;
      document.getElementById('solo-causes').value = '';
      document.getElementById('solo-report').textContent = '';
      document.getElementById('solo-csv').hidden = true;
      document.getElementById('solo-text').hidden = true;
      document.getElementById('solo-pause').textContent = 'Pause timer';
      document.getElementById('solo-status').textContent = 'Check each row, then check the complete label and save your development report.';
    }
  }
  function idFor(row) {
    if (!current()) return null;
    if (!run.refs.has(row)) run.refs.set(row, run.next++);
    return run.refs.get(row);
  }
  function rowSnapshot(row) {
    let owner = null;
    function walk(rows, parent) {
      for (const item of rows ?? []) {
        if (item === row) owner = parent === null ? null : idFor(parent);
        walk(item.nestedRows, item);
      }
    }
    walk(state.payload.ingredientRows, null);
    return JSON.stringify([snapshot(row), owner]);
  }
  function tick() {
    if (!current()) return;
    const now = performance.now();
    const stop = Math.min(now, run.activity + 30000);
    if (!run.paused && run.activeWindow) {
      run.active += Math.max(0, stop - run.last) / 1000;
    }
    run.last = now;
    run.activeWindow = document.visibilityState !== 'hidden' && document.hasFocus();
  }
  function activity() { tick(); if (current()) run.activity = performance.now(); }
  function changed() {
    if (!current()) return;
    const all = flatten(state.payload.ingredientRows);
    for (const row of all) {
      const id = idFor(row);
      if (run.marks.get(id) !== rowSnapshot(row)) run.marks.delete(id);
    }
    const checkbox = document.getElementById('solo-complete');
    if (checkbox) checkbox.checked = false;
    // Clear visible marks immediately, without rebuilding focused inputs.
    document.querySelectorAll('[data-solo-confirm]').forEach(button => {
      const id = Number(button.dataset.soloConfirm);
      button.textContent = run.marks.has(id) ? 'Confirmed' : 'Confirm';
    });
  }
  function confirm(row) { const id = idFor(row); if (id !== null) run.marks.set(id, rowSnapshot(row)); }
  function remove(row) {
    if (!current()) return true;
    const reason = window.prompt('Why remove this row? For example: not on label, or duplicate.');
    if (!reason?.trim()) return false;
    for (const item of flatten([row])) {
      const id = idFor(item);
      run.removed.set(id, reason.trim()); run.marks.delete(id);
    }
    return true;
  }
  function button(label, action) {
    const b = document.createElement('button'); b.type = 'button'; b.className = 'ghost compact';
    b.textContent = label; b.addEventListener('click', action); return b;
  }
  function attach(row, cell, nameInput) {
    if (!current()) return;
    const id = idFor(row);
    const report = run.grounding.rows.find(r => r.row_index === id);
    const status = document.createElement('span');
    status.className = 'solo-evidence-status';
    status.textContent = ({supported: 'Original: supported', check_this: 'Original: check this'})[report?.status] ?? 'Original: not checked';
    status.title = report?.reason ?? 'No spatial verification is available. Read this row from the photo.';
    const source = button('Evidence', () => void evidence(id)); source.dataset.soloReadOnly = 'true';
    const check = button(run.marks.get(id) === rowSnapshot(row) ? 'Confirmed' : 'Confirm', () => {
      confirm(row); check.textContent = 'Confirmed';
    });
    check.dataset.soloConfirm = String(id); check.dataset.soloReadOnly = 'true';
    const correct = button('Correct', () => {
      nameInput.focus(); nameInput.select();
      setStatus('Edit this row, then Confirm after checking the photograph. The original reading is preserved.');
    });
    cell.append(status, source, check, correct);
  }
  function rawReplaced(previousRows) {
    if (!current()) return;
    const next = flatten(state.payload.ingredientRows);
    const used = new Set(), resolved = new Map();
    // Prefer unchanged values, then the mapper's explicit occurrence order.
    // This keeps genuine reordering distinct from changed field values.
    for (const row of next) {
      const candidates = previousRows.filter(old => snapshot(old) === snapshot(row));
      const duplicates = next.filter(other => snapshot(other) === snapshot(row));
      if (candidates.length === 1 && duplicates.length === 1) {
        resolved.set(row, candidates[0]); used.add(candidates[0]);
      }
    }
    for (const row of next.filter(row => !resolved.has(row))) {
      const candidates = previousRows.filter(old => !used.has(old) && Number.isInteger(row.order) && old.order === row.order);
      if (candidates.length === 1 && next.filter(other => other.order === row.order).length === 1) {
        resolved.set(row, candidates[0]); used.add(candidates[0]);
      }
    }
    if (previousRows.some(row => !used.has(row))) {
      throw new Error('Cannot preserve row identity for these JSON edits. Use the row controls to correct or remove rows.');
    }
    for (const [row, previous] of resolved) run.refs.set(row, idFor(previous));
    changed();
  }
  async function evidence(id) {
    const selectedRun = run;
    if (!current()) return;
    const report = run.grounding.rows.find(r => r.row_index === id);
    const sourceIndex = run.originals[id]?.order - 1;
    const raw = run.extraction.draft_payload?.ingredient_rows?.[sourceIndex];
    const photoId = report?.photo_id ?? raw?.amount?.sources?.[0]?.photo_id ?? raw?.display_name?.sources?.[0]?.photo_id;
    const photo = state.selected.photos?.find(p => p.photo_id === photoId);
    if (!photo) { setStatus('No current source photo is linked. Use the photographs above.', true); return; }
    try {
      const bitmap = await createImageBitmap(await fetchReviewPhoto(photo.signed_url));
      if (run !== selectedRun || !current()) { bitmap.close(); return; }
      const region = report?.region;
      const valid = run.grounding.region_coordinate_space === 'orientation_corrected_original' && region &&
        ['x','y','w','h'].every(k => Number.isFinite(region[k])) && region.x >= 0 && region.y >= 0 &&
        region.w > 0 && region.h > 0 && region.x + region.w <= 1 && region.y + region.h <= 1;
      const canvas = document.getElementById('solo-evidence-canvas');
      let x = 0, y = 0, w = bitmap.width, h = bitmap.height;
      if (valid) {
        x = Math.max(0, (region.x - .025) * bitmap.width);
        y = Math.max(0, (region.y - .025) * bitmap.height);
        w = Math.min(bitmap.width - x, (region.w + .05) * bitmap.width);
        h = Math.min(bitmap.height - y, (region.h + .05) * bitmap.height);
      }
      const scale = Math.min(1, 1600 / w);
      canvas.width = Math.max(1, Math.round(w * scale)); canvas.height = Math.max(1, Math.round(h * scale));
      canvas.getContext('2d').drawImage(bitmap, x, y, w, h, 0, 0, canvas.width, canvas.height);
      bitmap.close();
      document.getElementById('solo-evidence-note').textContent = valid
        ? 'Supporting region with surrounding context. Check ingredient, amount, unit and serving basis.'
        : 'Exact region unavailable. Showing the full photograph.';
      document.getElementById('solo-full-photo').onclick = () => {
        document.getElementById('solo-evidence').close(); void openLightbox(photo);
      };
      document.getElementById('solo-evidence').showModal();
    } catch (error) { setStatus(error.message, true); }
  }
  function buildRecord() {
    if (!current()) throw new Error('Load the machine draft to start a development review.');
    const edited = flatten(state.payload.ingredientRows);
    const rows = edited.map((row, reviewed_index) => {
      const id = idFor(row);
      return {original_index: id < run.originals.length ? id : null, reviewed_index,
              confirmed: run.marks.get(id) === rowSnapshot(row)};
    });
    const present = new Set(edited.map(idFor));
    run.originals.forEach((_, id) => {
      if (!present.has(id)) rows.push({original_index: id, reviewed_index: null,
        confirmed: run.removed.has(id), reason: run.removed.get(id) ?? ''});
    });
    return {
      schema_version: 'solo_review_v1', submission_id: state.selected.id,
      evidence_revision: state.selected.evidence_revision, extraction_version: run.extraction.version,
      evidence_manifest_sha256: state.selected.evidence_manifest_sha256,
      reviewer: state.session.user?.id ?? 'local-reviewer', active_seconds: run.active,
      original_machine_draft: run.extraction.draft_payload, original_machine_payload: run.machine,
      reviewed_payload: structuredClone(state.payload), rows, grounding: run.grounding,
      photo_causes: document.getElementById('solo-causes').value.split(',').map(s => s.trim()).filter(Boolean),
      review_complete: document.getElementById('solo-complete').checked,
    };
  }
  function download(name, text, mime) {
    const url = URL.createObjectURL(new Blob([text], {type: mime}));
    const a = document.createElement('a'); a.href = url; a.download = name; a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  async function save() {
    tick();
    const selectedRun = run;
    try {
      if (hasUnappliedRawJson()) throw new Error('Apply your JSON edits first.');
      const record = buildRecord();
      const response = await fetch('/api/solo_review', {method: 'POST',
        headers: {'content-type':'application/json', authorization:`Bearer ${state.session.access_token}`},
        body: JSON.stringify(record)});
      const result = await response.json();
      if (!response.ok) throw new Error(result.error ?? 'Development report could not be saved.');
      if (run !== selectedRun) return;
      document.getElementById('solo-report').textContent = result.text;
      document.getElementById('solo-status').textContent = 'Saved privately. These are development results, not qualification.';
      const csvButton = document.getElementById('solo-csv'); csvButton.hidden = false;
      csvButton.onclick = () => download('pharmaguide-development.csv', result.csv, 'text/csv');
      const textButton = document.getElementById('solo-text'); textButton.hidden = false;
      textButton.onclick = () => download('pharmaguide-development.txt', result.text, 'text/plain');
    } catch (error) { setStatus(error.message, true); }
  }
  function init() {
    document.getElementById('solo-save').onclick = () => void save();
    document.getElementById('solo-pause').onclick = () => {
      tick(); if (!current()) return; run.paused = !run.paused; run.activity = performance.now();
      document.getElementById('solo-pause').textContent = run.paused ? 'Resume timer' : 'Pause timer';
    };
    document.getElementById('solo-evidence-close').onclick = () => document.getElementById('solo-evidence').close();
    for (const event of ['pointerdown','keydown','pointermove','scroll']) document.addEventListener(event, activity, {passive:true});
    document.addEventListener('visibilitychange', () => { tick(); if (current()) run.last = performance.now(); });
    window.addEventListener('blur', tick);
    window.addEventListener('focus', () => { tick(); if (current()) run.last = run.activity = performance.now(); });
  }
  return {start, reset, changed, confirm, remove, attach, rawReplaced, flatten, buildRecord, evidence, init};
})();
