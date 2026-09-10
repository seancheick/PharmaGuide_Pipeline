// PharmaGuide submission reviewer console.
//
// All privileged calls go browser -> local proxy (/api/edge) -> the deployed
// review-product-submissions Edge Function under the signed-in reviewer's
// JWT. Approval payloads are validated + canonicalized authoritatively
// server-side; this page only previews.
'use strict';

/* global canonicalJson, sha256Hex, supabase */

const state = {
  client: null,
  session: null,
  submissions: [],
  selected: null,
  reviewInvalidated: false,
  payload: null,
  payloadSha: null,
  payloadCanonical: null,
  payloadHashRequest: 0,
  refreshTimer: null,
  nextAfter: null,
  totalOpenCount: 0,
  queueRequestId: 0,
  identityLookup: null,
  identityRecorded: null,
  reviewerImages: [],
  productImage: null,
  lightboxImage: null,
  lightboxRotation: 0,
  // The reviewer's own saved corrections and attestations, as the server
  // reports them. The local tick set stays the fast path for rendering; this
  // is the durable record that survives a reload.
  review: null,
  reviewLoadedFor: null,
  reviewSaveTimer: null,
  reviewSaveRequest: 0,
  reviewLoadRequest: 0,
  reviewVerifyRequest: 0,
  batchStates: new Map(),
  batchSelected: new Set(),
  batchStateRequest: 0,
  batchRunning: false,
  batchResults: null,
  diagnostics: null,
  diagnosticsSha: null,
  diagnosticsRequest: 0,
  reviewSuperseded: false,
  reviewDigestMismatch: false,
};

const $ = (id) => document.getElementById(id);

function setStatus(message, isError = false) {
  const line = $('status-line');
  line.textContent = message;
  line.style.color = isError ? 'var(--bad)' : 'var(--fg-muted)';
}

// ---------------------------------------------------------------- auth

async function boot() {
  const config = await (await fetch('/api/config')).json();
  state.client = supabase.createClient(config.supabase_url, config.anon_key);
  const { data } = await state.client.auth.getSession();
  if (data.session) onSignedIn(data.session);

  $('signin-form').addEventListener('submit', async (event) => {
    event.preventDefault();
    const email = $('email').value.trim();
    const { error } = await state.client.auth.signInWithOtp({
      email,
      options: { shouldCreateUser: false },
    });
    if (error) return setStatus(`Sign-in failed: ${error.message}`, true);
    $('signin-form').classList.add('hidden');
    $('verify-form').classList.remove('hidden');
    setStatus(`Code sent to ${email}.`);
  });

  $('verify-form').addEventListener('submit', async (event) => {
    event.preventDefault();
    const { data: verified, error } = await state.client.auth.verifyOtp({
      email: $('email').value.trim(),
      token: $('otp').value.trim(),
      type: 'email',
    });
    if (error || !verified.session) {
      return setStatus(`Code rejected: ${error?.message ?? 'no session'}`, true);
    }
    onSignedIn(verified.session);
  });

  $('signout').addEventListener('click', async () => {
    await state.client.auth.signOut();
    window.location.reload();
  });

  $('reload').addEventListener('click', () => loadQueue());
  $('filter-status').addEventListener('change', () => loadQueue());
  $('filter-kind').addEventListener('change', () => loadQueue());
  $('load-more').addEventListener('click', () => loadQueue(true));
  $('batch-select-all').addEventListener('click', () => selectAllEligible());
  $('batch-approve').addEventListener('click', () => void approveBatch());
  $('add-row').addEventListener('click', () => {
    state.payload.ingredientRows.push(emptyRow());
    renderRows();
    updateShaPreview();
  });
  $('add-statement').addEventListener('click', addStatement);
  $('ai-draft-load').addEventListener('click', loadDraftIntoEditor);
  $('help-open').addEventListener('click', openHelp);
  $('help-close').addEventListener('click', () => $('help-drawer').close());
  document.addEventListener('keydown', handleShortcut);
  $('apply-raw').addEventListener('click', applyRawJson);
  $('t-under-review').addEventListener('click', () =>
    transition({ to_status: 'under_review' }),
  );
  $('t-approve').addEventListener('click', approve);
  $('t-reject').addEventListener('click', reject);
  $('t-duplicate').addEventListener('click', markDuplicate);
  $('catalog-go').addEventListener('click', catalogSearch);
  $('identity-run').addEventListener('click', checkIdentity);
  $('other-disclosure').addEventListener('change', syncDisclosureFields);
  $('other-ingredients').addEventListener('input', syncDisclosureFields);
  $('reviewer-image-upload').addEventListener('click', uploadReplacementImage);
  $('lightbox-close').addEventListener('click', closeLightbox);
  $('image-rotate').addEventListener('click', rotateLightbox);
  $('image-crop').addEventListener('click', cropLightbox);
  $('image-use-crop').addEventListener('click', useLightboxCrop);
  for (const id of [
    'p-brand',
    'p-name',
    'p-product-type',
    'p-physical-state',
    'p-servings-count',
    'p-serving-qty',
    'p-serving-unit',
  ]) {
    $(id).addEventListener('input', syncScalarFields);
  }
}

function onSignedIn(session) {
  state.session = session;
  $('signin-form').classList.add('hidden');
  $('verify-form').classList.add('hidden');
  $('signed-in').classList.remove('hidden');
  $('reviewer-email').textContent = session.user.email ?? session.user.id;
  loadQueue();
}

// ---------------------------------------------------------------- edge calls

async function edge(body) {
  const response = await fetch('/api/edge', {
    method: 'POST',
    headers: {
      'content-type': 'application/json',
      authorization: `Bearer ${state.session.access_token}`,
    },
    body: JSON.stringify(body),
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.error ?? `edge call failed (${response.status})`);
  }
  return payload;
}

// ---------------------------------------------------------------- queue

async function loadQueue(append = false) {
  if (append && !state.nextAfter) return;
  const requestId = ++state.queueRequestId;
  const loadMore = $('load-more');
  loadMore.disabled = true;
  try {
    const body = { action: 'list', limit: 100 };
    if ($('filter-status').value) body.status = $('filter-status').value;
    if ($('filter-kind').value) body.kind = $('filter-kind').value;
    if (append) body.after = state.nextAfter;
    const { submissions, total_open_count, next_after } = await edge(body);
    if (requestId !== state.queueRequestId) return;
    if (append) {
      state.submissions.push(...submissions);
    } else {
      state.submissions = submissions;
    }
    state.totalOpenCount = Number(total_open_count ?? 0);
    state.nextAfter = next_after ?? null;
    renderQueue();
    $('queue-count').textContent =
      `${state.totalOpenCount} open · ${state.submissions.length} loaded`;
    loadMore.classList.toggle('hidden', state.nextAfter === null);
    setStatus(`${state.submissions.length} submission(s) loaded.`);
    // Readiness is the server's answer, refreshed with the queue it describes.
    void refreshBatchStates();
  } catch (error) {
    if (requestId !== state.queueRequestId) return;
    setStatus(String(error.message ?? error), true);
  } finally {
    if (requestId === state.queueRequestId) loadMore.disabled = false;
  }
}

function renderQueue() {
  const list = $('queue');
  list.textContent = '';
  for (const submission of state.submissions) {
    const item = document.createElement('li');
    item.classList.toggle('active', submission.id === state.selected?.id);
    const badge = document.createElement('span');
    badge.className = `badge ${submission.review_status}`;
    badge.textContent = submission.review_status;
    const kind = document.createElement('span');
    kind.className = 'badge';
    kind.textContent = submission.kind === 'missing_product'
      ? `UPC ${submission.normalized_upc ?? '?'}`
      : `fix ${submission.product_submission_mismatch_details?.dsld_id ?? '?'}`;
    const id = document.createElement('div');
    id.className = 'id';
    id.textContent = submission.id;
    item.append(badge, kind, id);
    if (batchEligible(submission)) {
      const pick = document.createElement('input');
      pick.type = 'checkbox';
      pick.className = 'queue-pick';
      pick.checked = state.batchSelected.has(submission.id);
      pick.title = 'Include in the next batch approval';
      // Picking an item for a batch is not opening it.
      pick.addEventListener('click', (event) => event.stopPropagation?.());
      pick.addEventListener('change', () => toggleBatchSelection(submission.id));
      item.append(pick);
    }
    item.addEventListener('click', () => select(submission));
    list.append(item);
  }
}

function select(submission) {
  state.selected = submission;
  state.reviewInvalidated = false;
  state.payload = defaultPayload();
  state.payloadSha = null;
  state.payloadCanonical = null;
  state.verifiedKey = null;
  state.verified = new Set();
  state.review = null;
  state.diagnostics = null;
  state.diagnosticsSha = null;
  state.diagnosticsRequest += 1;
  state.reviewLoadRequest += 1;
  state.reviewLoadedFor = null;
  state.reviewSuperseded = false;
  state.reviewDigestMismatch = false;
  state.identityLookup = null;
  state.identityRecorded = null;
  state.reviewerImages = [];
  state.productImage = null;
  $('reviewer-image-attestation').checked = false;
  $('reviewer-image-file').value = '';
  // Last, and only if one is pending: cancelling a save is cleanup, and
  // cleanup must never be able to abort the reset above part-way through.
  if (state.reviewSaveTimer) clearTimeout(state.reviewSaveTimer);
  state.reviewSaveTimer = null;
  renderQueue();
  renderDetail();
  void refreshSelected();
}

// Signed URLs live 300s; refresh this submission's row just before expiry.
function scheduleUrlRefresh() {
  clearTimeout(state.refreshTimer);
  state.refreshTimer = setTimeout(refreshSelected, 270 * 1000);
}

async function refreshSelected() {
  const selection = state.selected;
  if (!selection) return;
  try {
    const { submissions } = await edge({
      action: 'list',
      submission_id: selection.id,
      limit: 1,
    });
    if (state.selected !== selection) return;
    if (submissions.length === 1 && submissions[0].id === selection.id) {
      const fresh = submissions[0];
      if (fresh.evidence_revision !== selection.evidence_revision ||
          fresh.evidence_manifest_sha256 !== selection.evidence_manifest_sha256) {
        state.submissions = state.submissions.map((row) => row.id === fresh.id ? fresh : row);
        select(fresh);
        state.reviewInvalidated = true;
        setDecisionAvailability();
        setStatus('Photos changed. Select this submission again and review the new evidence before deciding.', true);
        return;
      }
      state.selected = fresh;
      renderDetail();
    }
  } catch {
    // Keep the edited payload; retry metadata without inventing a fresh binding.
  } finally {
    if (state.selected?.id === selection.id) scheduleUrlRefresh();
  }
}

// ---------------------------------------------------------------- detail

function renderDetail() {
  const submission = state.selected;
  $('detail-panel').classList.remove('hidden');
  const head = $('detail-head');
  head.textContent = '';
  const title = document.createElement('h2');
  title.textContent = submission.kind === 'missing_product'
    ? `Missing product — UPC ${submission.normalized_upc ?? '?'}`
    : `Catalog correction — dsld ${submission.product_submission_mismatch_details?.dsld_id ?? '?'}`;
  const meta = document.createElement('p');
  meta.className = 'mono';
  meta.textContent = `${submission.id} · ${submission.review_status}` +
    ` · submitted ${submission.submitted_at ?? '?'}` +
    (submission.declared_no_separate_ingredient_panel
      ? ' · declared: no separate ingredient panel'
      : '');
  head.append(title, meta);
  if (submission.resolution_code) {
    const resolution = document.createElement('p');
    resolution.className = 'muted';
    resolution.textContent =
      `resolution: ${submission.resolution_code}` +
      (submission.resolution_detail ? ` — ${submission.resolution_detail}` : '') +
      (submission.resolved_dsld_id ? ` → ${submission.resolved_dsld_id}` : '');
    head.append(resolution);
  }

  const grid = $('photos');
  grid.textContent = '';
  for (const photo of submission.photos ?? []) {
    const figure = document.createElement('figure');
    figure.dataset.photoId = photo.photo_id;
    const img = document.createElement('img');
    img.src = photo.signed_url;
    img.alt = `photo seq ${photo.seq}`;
    img.addEventListener('click', () => openLightbox(photo));
    const caption = document.createElement('figcaption');
    caption.textContent =
      `#${photo.seq} · ${(photo.categories ?? []).join(', ')}`;
    figure.append(img, caption);
    grid.append(figure);
  }

  renderDraft();
  renderVerifyChecklist();
  renderReadiness();
  renderRows();
  syncFieldsFromPayload();
  updateShaPreview();
  renderIdentityCheck();
  renderProductPictureOptions();
  setDecisionAvailability();
  renderReviewBanner();
  renderDiagnostics();
  // Restore this reviewer's saved corrections and ticks, once per revision.
  void loadReview();
}

// ---------------------------------------------------------------- identity

function canonicalSubmissionGtin14() {
  const digits = String(state.selected?.normalized_upc ?? '');
  return /^(?:\d{8}|\d{12}|\d{13}|\d{14})$/.test(digits)
    ? digits.padStart(14, '0')
    : null;
}

async function checkIdentity() {
  if (state.selected?.kind !== 'missing_product') return;
  const gtin14 = canonicalSubmissionGtin14();
  if (!gtin14) return setStatus('This submission has no valid barcode identity.', true);
  try {
    setStatus('Checking the released catalog and full DSLD corpus…');
    const response = await fetch(
      `/api/identity_lookup?gtin14=${encodeURIComponent(gtin14)}`,
    );
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error ?? 'identity lookup failed');
    state.identityLookup = payload;
    state.identityRecorded = null;
    renderIdentityCheck();
    setStatus('Identity check complete.');
  } catch (error) {
    setStatus(String(error.message ?? error), true);
  }
}

async function requireCurrentIdentity() {
  const lookup = state.identityLookup;
  if (!lookup) throw new Error('Run the identity check first.');
  const submissionId = state.selected?.id;
  let current = null;
  try {
    const response = await fetch(
      `/api/identity_lookup?gtin14=${encodeURIComponent(lookup.canonical_gtin14)}`,
      { cache: 'no-store' },
    );
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error ?? 'Identity check unavailable.');
    if (state.selected?.id !== submissionId) {
      throw new Error('The selected submission changed. Run its identity check.');
    }
    current = payload;
    if (
      !lookup.index_revision || current.index_revision !== lookup.index_revision ||
      current.canonical_gtin14 !== canonicalSubmissionGtin14() ||
      current.freshness === 'blocked'
    ) {
      throw new Error('Identity sources changed or expired. Review the current matches and record a new check.');
    }
    return current;
  } catch (error) {
    if (state.selected?.id === submissionId) {
      state.identityLookup = current;
      state.identityRecorded = null;
      renderIdentityCheck();
    }
    throw error;
  }
}

function selectedEvidenceBinding() {
  const selected = state.selected;
  if (!selected || !Number.isSafeInteger(selected.evidence_revision) || selected.evidence_revision < 1 ||
      !/^[0-9a-f]{64}$/.test(selected.evidence_manifest_sha256 ?? '')) {
    throw new Error('Refresh this submission before reviewing its evidence.');
  }
  return {expected_evidence_revision:selected.evidence_revision,
    evidence_manifest_sha256:selected.evidence_manifest_sha256};
}

async function recordMatch(outcome, options = {}) {
  const selectedId = state.selected?.id;
  const binding = selectedEvidenceBinding();
  const lookup = await requireCurrentIdentity();
  const result = await edge({
    action: 'record_match',
    submission_id: selectedId,
    ...binding,
    outcome,
    canonical_gtin14: lookup.canonical_gtin14,
    index_built_at: lookup.index_built_at,
    ...options,
  });
  if (state.selected?.id !== selectedId || state.selected.evidence_revision !== binding.expected_evidence_revision) {
    throw new Error('The selected submission changed. Review its current evidence.');
  }
  state.identityRecorded = outcome;
  renderIdentityCheck();
  return result;
}

function identityButton(label, action, className = 'ghost') {
  const button = document.createElement('button');
  button.type = 'button';
  button.className = className;
  button.textContent = label;
  button.addEventListener('click', async () => {
    button.disabled = true;
    try {
      await action();
    } catch (error) {
      setStatus(String(error.message ?? error), true);
    } finally {
      button.disabled = false;
    }
  });
  return button;
}

function renderIdentityCheck() {
  renderReadiness();
  setDecisionAvailability();
  const section = $('identity-check');
  const status = $('identity-index-status');
  const results = $('identity-results');
  const actions = $('identity-actions');
  results.textContent = '';
  actions.textContent = '';

  if (state.selected?.kind !== 'missing_product') {
    section.classList.add('hidden');
    return;
  }
  section.classList.remove('hidden');
  const lookup = state.identityLookup;
  if (!lookup) {
    status.textContent = 'Required before approval. Exact matches only; no fuzzy lookup.';
    return;
  }
  const built = new Date(lookup.index_built_at).toLocaleString();
  status.textContent = `Index ${lookup.freshness} · source snapshot ${built}` +
    (state.identityRecorded ? ` · recorded ${state.identityRecorded}` : '');
  for (const match of lookup.matches) {
    const item = document.createElement('li');
    item.textContent = `${match.source} · ${match.dsld_id} · ` +
      `${match.brand_name} ${match.product_name}`;
    results.append(item);
  }

  const ids = [...new Set(lookup.matches.map((match) => match.dsld_id))];
  const catalogIds = [...new Set(
    lookup.matches.filter((match) => match.source === 'catalog')
      .map((match) => match.dsld_id),
  )];
  if (ids.length === 0) {
    if (lookup.freshness === 'blocked') {
      status.textContent += ' · blocked: rebuild the corpus before approving';
      return;
    }
    actions.append(identityButton('Record verified no match', async () => {
      await recordMatch('no_match_verified');
      setStatus('Verified no match recorded. Transcription may proceed.');
    }, 'primary'));
    return;
  }

  if (catalogIds.length === 1 && ids.length === 1) {
    actions.append(identityButton('Record and mark catalog duplicate', async () => {
      await recordMatch('catalog_match', { matched_dsld_id: catalogIds[0] });
      $('dup-code').value = 'already_in_catalog';
      $('dup-target').value = catalogIds[0];
      await markDuplicate();
    }, 'primary'));
  } else if (catalogIds.length === 0 && ids.length === 1) {
    const draftMatch = lookup.matches.find(
      (match) => match.source === 'corpus' && match.dsld_id === ids[0],
    );
    if (draftMatch?.draft_payload) {
      actions.append(identityButton('Use as draft for label comparison', async () => {
        state.payload = structuredClone(draftMatch.draft_payload);
        renderRows();
        syncFieldsFromPayload();
        updateShaPreview();
        setStatus('DSLD label loaded as an editable draft. Human comparison is still required.');
      }));
    }
    actions.append(identityButton('Import DSLD match and mark duplicate', async () => {
      await recordMatch('dsld_match', { matched_dsld_id: ids[0] });
      const response = await fetch('/api/dsld_refresh', {
        method: 'POST',
        headers: {
          'content-type': 'application/json',
          authorization: `Bearer ${state.session.access_token}`,
        },
        body: JSON.stringify({ dsld_id: ids[0] }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error ?? 'DSLD import failed');
      $('dup-code').value = 'already_in_catalog';
      $('dup-target').value = ids[0];
      await markDuplicate();
    }, 'primary'));
  } else {
    actions.append(identityButton('Record ambiguous identity', async () => {
      await recordMatch('identity_ambiguous', { candidate_dsld_ids: ids });
      setStatus('Ambiguous exact matches recorded. Select the correct identity before closing.');
    }));
  }

  actions.append(identityButton('None of these is this product', async () => {
    const reason = window.prompt('Why are the exact barcode hits not this product?');
    if (!reason?.trim()) throw new Error('An audited reason is required.');
    for (const dsldId of ids) {
      await recordMatch('not_this_product', {
        matched_dsld_id: dsldId,
        reason: reason.trim(),
      });
    }
    if (lookup.freshness === 'blocked') {
      throw new Error('Overrides recorded, but the index is stale. Rebuild before approval.');
    }
    await recordMatch('no_match_verified');
    setStatus('Wrong hits retained in history; verified no match recorded.');
  }));
}

// ---------------------------------------------------------------- payload

// ------------------------------------------------- reviewer readiness
//
// The console's job is to make the next action obvious. A reviewer should
// never have to guess why Approve is refusing, and should never be able to
// approve a field nobody has actually read off the photographs.
//
// These checks are a reviewer aid on top of the server's own gates, not a
// replacement for them: the database still refuses a stale revision, a missing
// identity check and an unverified payload whatever this page believes.

const CRITICAL_FIELDS = [
  ['brand', 'Brand'],
  ['name', 'Product name'],
  ['serving', 'Serving size and count'],
  ['rows', 'Every ingredient row'],
  ['other', 'Other Ingredients'],
];

/** Ticks belong to one exact payload and one exact evidence revision. */
function verificationKey() {
  const submission = state.selected;
  if (!submission || !state.payloadSha) return null;
  try {
    if (canonicalJson(state.payload) !== state.payloadCanonical) return null;
  } catch { return null; }
  return `${submission.id}:${submission.evidence_revision}:${submission.evidence_manifest_sha256}:${state.payloadSha}`;
}

function verifiedSet() {
  const key = verificationKey();
  if (!key) {
    state.verifiedKey = null;
    state.verified = new Set();
    return state.verified;
  }
  if (state.verifiedKey !== key) {
    // The label text or the evidence moved. A check of an older value is not
    // a check of this one, so the ticks go rather than quietly carrying over.
    state.verifiedKey = key;
    state.verified = new Set();
  }
  return state.verified;
}

function toggleVerified(field) {
  if (!verificationKey() || !CRITICAL_FIELDS.some(([key]) => key === field)) return;
  const verified = verifiedSet();
  if (verified.has(field)) verified.delete(field); else verified.add(field);
  renderVerifyChecklist();
  renderReadiness();
  setDecisionAvailability();
  void persistVerification(field, verified.has(field));
}

function renderVerifyChecklist() {
  const host = $('verify-checklist');
  if (!host) return;
  host.textContent = '';
  const verified = verifiedSet();
  for (const [field, label] of CRITICAL_FIELDS) {
    const wrap = document.createElement('label');
    wrap.className = verified.has(field) ? 'verify-chip verified' : 'verify-chip';
    const box = document.createElement('input');
    box.type = 'checkbox';
    box.id = `verify-${field}`;
    box.checked = verified.has(field);
    box.disabled = !verificationKey();
    box.addEventListener('change', () => toggleVerified(field));
    const text = document.createElement('span');
    text.textContent = label;
    wrap.append(box, text);
    // A tick means "I read this off the photograph". Where the draft says
    // which photograph that was, make it one click away rather than a hunt.
    const photoId = sourcePhotoForField(field);
    if (photoId) {
      const source = document.createElement('button');
      source.type = 'button';
      source.className = 'verify-source';
      source.textContent = 'source';
      source.title = 'Show the photograph this reading came from';
      source.addEventListener('click', () => focusSourcePhoto(photoId));
      wrap.append(source);
    }
    host.append(wrap);
  }
}

/** Everything standing between the reviewer and Approve, in plain sentences. */
function readinessChecks() {
  const submission = state.selected;
  if (!submission) return [];
  const verified = verifiedSet();
  const missing = CRITICAL_FIELDS.filter(([field]) => !verified.has(field));
  const checks = [
    {
      done: !state.reviewInvalidated,
      todo: 'The photos changed while you were reading. Open this submission again.',
      done_text: 'You are looking at the current photos.',
    },
    {
      // Saved work that describes other photographs, or text the server reads
      // differently, cannot authorize this decision.
      done: !state.reviewSuperseded && !state.reviewDigestMismatch,
      todo: state.reviewDigestMismatch
        ? 'This page and the server disagree about the label text. Reopen this submission.'
        : 'New photographs arrived after you started. Reopen this submission to read them.',
      done_text: 'Your saved review matches this evidence.',
    },
    {
      // Not yet checked is not the same as clean. An unanswered validator
      // must not read as permission: approving a label the importer will
      // refuse produces a broken catalog entry nobody is watching for.
      done: Array.isArray(state.diagnostics) && state.diagnostics.length === 0,
      todo: state.diagnostics === null
        ? 'Waiting for the label check. If it does not arrive, reopen this submission.'
        : `Fix ${state.diagnostics.length} problem(s) the catalog importer will refuse.`,
      done_text: 'The catalog importer accepts this label.',
    },
    {
      done: submission.review_status === 'under_review',
      todo: 'Press Start review before making an approval decision.',
      done_text: 'This submission is under review.',
    },
    {
      done: Boolean(verificationKey()) && missing.length === 0,
      todo: !verificationKey() ? 'Wait for the current payload check; correct invalid JSON if it fails.' : missing.length === 1
        ? `Read ${missing[0][1].toLowerCase()} off the photographs and tick it.`
        : `Read and tick ${missing.length} more fields.`,
      done_text: 'Every field has been read off the photographs.',
    },
  ];
  if (submission.kind === 'missing_product') {
    checks.push({
      done: state.identityRecorded === 'no_match_verified',
      todo: 'Run the barcode check to confirm this product is not already in the catalog.',
      done_text: 'Checked: this barcode is not already in the catalog.',
    });
    checks.push({
      done: Boolean(state.productImage),
      todo: 'Choose the one photo that becomes the catalog picture.',
      done_text: 'Catalog picture chosen.',
    });
  }
  return checks;
}

function renderReadiness() {
  const list = $('readiness-list');
  const progress = $('readiness-progress');
  if (!list) return;
  list.textContent = '';
  const checks = readinessChecks();
  const done = checks.filter((check) => check.done).length;
  progress.textContent = checks.length ? `${done} of ${checks.length} done` : '';
  for (const check of checks) {
    const item = document.createElement('li');
    item.className = check.done ? 'ready' : 'blocking';
    // Say what to do, not what is wrong: a reviewer needs the next action.
    item.textContent = check.done ? check.done_text : check.todo;
    list.append(item);
  }
}

function approvalBlockers() {
  return readinessChecks().filter((check) => !check.done);
}

// ------------------------------------------------- persistent reviewer review
//
// A reviewer who reloads the page must find their corrections and their ticks
// exactly as they left them, and must never find a tick standing against text
// or photographs that have since moved. The server owns both facts; this layer
// keeps the page and the server saying the same thing.
//
// The local tick set remains the rendering fast path. It is hydrated from the
// server on open and confirmed against the server on every change, so an
// optimistic tick the server refuses is taken back rather than left showing.

/** Where each console field lives in the label contract, for both sides. */
const FIELD_PATHS = new Map([
  ['brand', 'identity.brand'],
  ['name', 'identity.product_name'],
  ['serving', 'serving.size'],
  ['rows', 'ingredient_rows'],
  ['other', 'other_ingredients'],
]);

/** The photograph the model says a field was read off, when it says one. */
function sourcePhotoForField(field) {
  const draft = state.draft?.draft_payload;
  if (!draft) return null;
  const lookup = {
    brand: draft.identity?.brand,
    name: draft.identity?.product_name,
    serving: draft.serving?.size,
    other: draft.other_ingredients,
    rows: Array.isArray(draft.ingredient_rows) ? draft.ingredient_rows[0] : null,
  }[field];
  const source = lookup?.sources?.[0] ?? lookup?.display_name?.sources?.[0];
  const photoId = source?.photo_id ?? null;
  // Only offer a photograph that is actually part of this evidence revision.
  return (state.selected?.photos ?? []).some((p) => p.photo_id === photoId)
    ? photoId
    : null;
}

function hydrateReview(review) {
  state.review = review ?? null;
  const draft = review?.draft ?? null;
  state.reviewSuperseded = Boolean(draft?.superseded);
  // The server's digest is authoritative. If the two sides canonicalize the
  // same label differently an attestation would bind to text the reviewer
  // never saw, so it becomes a blocker rather than a silent disagreement.
  state.reviewDigestMismatch = Boolean(
    draft && !draft.superseded && state.payloadSha &&
    draft.payload_sha256 !== state.payloadSha,
  );
  const key = verificationKey();
  if (!key) return;
  const live = (review?.verifications ?? [])
    .filter((entry) => entry.live)
    .map((entry) => entry.field_path);
  const fields = new Set();
  for (const [field, path] of FIELD_PATHS) {
    if (live.includes(path)) fields.add(field);
  }
  state.verifiedKey = key;
  state.verified = fields;
}

async function loadReview() {
  const submission = state.selected;
  if (!submission || !state.session) return;
  const key = `${submission.id}:${submission.evidence_revision}`;
  const requestId = state.reviewLoadRequest;
  if (state.reviewLoadedFor === key) return;
  state.reviewLoadedFor = key;
  let review;
  try {
    ({ review } = await edge({ action: 'load_review', submission_id: submission.id }));
  } catch {
    state.reviewLoadedFor = null;
    setStatus('Saved review could not be loaded; your edits will not persist.', true);
    return;
  }
  // The same submission id survives a retake. Bind the response to the
  // revision as well as the id, otherwise a slow old response can restore
  // corrections made against photographs that are no longer current.
  if (state.reviewLoadRequest !== requestId ||
      state.selected?.id !== submission.id ||
      `${state.selected?.id}:${state.selected?.evidence_revision}` !== key) return;
  const draft = review?.draft;
  // Restore the reviewer's own work. A superseded draft is never adopted into
  // the editor: it describes photographs that are no longer the evidence.
  if (draft && !draft.superseded && draft.payload) {
    state.payload = draft.payload;
    syncFieldsFromPayload();
    renderRows();
    await updateShaPreview();
  }
  hydrateReview(review);
  renderVerifyChecklist();
  renderReadiness();
  renderReviewBanner();
  setDecisionAvailability();
}

function scheduleReviewSave() {
  if (!state.session) return;
  clearTimeout(state.reviewSaveTimer);
  state.reviewSaveTimer = setTimeout(() => void saveReview(), 800);
}

async function saveReview() {
  const submission = state.selected;
  if (!submission || !state.session) return;
  if (!state.payloadSha || state.reviewInvalidated) return;
  if (!submission.evidence_manifest_sha256) return;
  const requestId = ++state.reviewSaveRequest;
  const boundSha = state.payloadSha;
  const boundRevision = submission.evidence_revision;
  const boundManifest = submission.evidence_manifest_sha256;
  let review;
  try {
    ({ review } = await edge({
      action: 'save_review',
      submission_id: submission.id,
      payload: state.payload,
      expected_evidence_revision: submission.evidence_revision,
      evidence_manifest_sha256: submission.evidence_manifest_sha256,
    }));
  } catch {
    setStatus('Your corrections are not being saved. Reopen this submission.', true);
    return;
  }
  // A save that finished after a newer edit must not describe the screen.
  if (requestId !== state.reviewSaveRequest) return;
  if (state.selected?.id !== submission.id ||
      state.selected?.evidence_revision !== boundRevision ||
      state.selected?.evidence_manifest_sha256 !== boundManifest ||
      state.payloadSha !== boundSha) return;
  hydrateReview(review);
  renderReviewBanner();
  setDecisionAvailability();
}

/** Persist one tick, and take it back if the server refuses. */
async function persistVerification(field, verified) {
  const submission = state.selected;
  const path = FIELD_PATHS.get(field);
  if (!submission || !state.session) return;
  if (!path || !state.payloadSha) return;
  const boundSha = state.payloadSha;
  const boundRevision = submission.evidence_revision;
  const boundManifest = submission.evidence_manifest_sha256;
  // Ticks are made in quick succession. An earlier reply describes fewer of
  // them, so letting a late arrival repaint the list would silently drop a
  // check the database has already accepted.
  const requestId = ++state.reviewVerifyRequest;
  let review;
  try {
    ({ review } = await edge({
      action: 'set_field_verification',
      submission_id: submission.id,
      field_path: path,
      payload_sha256: boundSha,
      verified,
      photo_id: verified ? sourcePhotoForField(field) : null,
    }));
  } catch {
    if (state.selected?.id === submission.id && state.payloadSha === boundSha) {
      // The tick did not reach the database, so the page must stop showing it.
      state.verified.delete(field);
      renderVerifyChecklist();
      renderReadiness();
      setDecisionAvailability();
    }
    setStatus('That check could not be recorded. Read the field again.', true);
    return;
  }
  if (requestId !== state.reviewVerifyRequest) return;
  if (state.selected?.id !== submission.id ||
      state.selected?.evidence_revision !== boundRevision ||
      state.selected?.evidence_manifest_sha256 !== boundManifest ||
      state.payloadSha !== boundSha) return;
  hydrateReview(review);
  renderVerifyChecklist();
  renderReadiness();
  setDecisionAvailability();
}

/** Say plainly when saved work no longer applies to what is on screen. */
function renderReviewBanner() {
  const banner = $('review-banner');
  if (!banner) return;
  let message = '';
  if (state.reviewDigestMismatch) {
    message = 'This page and the server disagree about the label text. ' +
      'Reopen this submission before approving.';
  } else if (state.reviewSuperseded) {
    message = 'New photographs arrived after you started. Your earlier ' +
      'corrections were kept but no longer apply to this evidence.';
  }
  banner.textContent = message;
  banner.hidden = message === '';
}


// ------------------------------------------------- server-owned diagnostics
//
// The console has no label rules of its own. It asks the Edge Function for the
// verdict of the very validator that will refuse the approval, so a reviewer
// can never be told a label is acceptable by one implementation and refused by
// another with nobody able to say which was right. The catalog importer keeps
// its own validator for its own gate; a pinned fixture proves the two agree.

async function refreshDiagnostics() {
  const submission = state.selected;
  if (!submission || !state.session || !state.payloadSha) return;
  if (state.diagnosticsSha === state.payloadSha) return;
  const requestId = ++state.diagnosticsRequest;
  const boundSha = state.payloadSha;
  let diagnostics;
  try {
    ({ diagnostics } = await edge({
      action: 'validate_label', payload: state.payload,
    }));
  } catch {
    // Unknown is not clean. Leaving the previous answer standing would let a
    // reviewer approve against a check that never actually ran.
    if (requestId !== state.diagnosticsRequest) return;
    state.diagnostics = null;
    state.diagnosticsSha = null;
    renderDiagnostics();
    setDecisionAvailability();
    return;
  }
  if (requestId !== state.diagnosticsRequest) return;
  if (state.selected?.id !== submission.id || state.payloadSha !== boundSha) return;
  state.diagnostics = Array.isArray(diagnostics) ? diagnostics : null;
  state.diagnosticsSha = state.diagnostics ? boundSha : null;
  renderDiagnostics();
  renderReadiness();
  setDecisionAvailability();
}

function renderDiagnostics() {
  const host = $('label-diagnostics');
  if (!host) return;
  host.textContent = '';
  const diagnostics = state.diagnostics;
  if (!diagnostics || diagnostics.length === 0) {
    host.hidden = true;
    return;
  }
  host.hidden = false;
  const heading = document.createElement('p');
  heading.className = 'diagnostics-heading';
  heading.textContent = diagnostics.length === 1
    ? 'The catalog importer will refuse this label:'
    : `The catalog importer will refuse this label (${diagnostics.length} problems):`;
  host.append(heading);
  const list = document.createElement('ul');
  for (const entry of diagnostics) {
    const item = document.createElement('li');
    const path = document.createElement('code');
    path.textContent = entry.path ?? '$';
    const message = document.createTextNode(` ${entry.message ?? ''}`);
    item.append(path, message);
    list.append(item);
  }
  host.append(list);
}

/** Bring the photograph a field was read off into view, and mark it. */
function focusSourcePhoto(photoId) {
  const grid = $('photos');
  if (!grid || !photoId) return false;
  let found = false;
  for (const figure of grid.children ?? []) {
    const matches = figure.dataset?.photoId === photoId;
    figure.classList?.[matches ? 'add' : 'remove']('source-photo');
    if (matches) {
      found = true;
      figure.scrollIntoView?.({ block: 'nearest' });
    }
  }
  return found;
}

// ------------------------------------------------------------ batch actions
//
// A batch is a convenience for one person at one screen: it saves the clicks,
// never the reading. Each item is applied through the ordinary human
// transition with its own evidence fence, its own payload and its own
// attestations, and the server sources the approved label from that
// reviewer's saved draft rather than from this page. A ticked neighbour, a
// model's confidence and a stale screen all authorize exactly nothing.

/** Server-reported readiness per submission, for this reviewer only. */
function batchState(submissionId) {
  return state.batchStates?.get(submissionId) ?? null;
}

function batchEligible(submission) {
  const readiness = batchState(submission.id);
  // A new product also needs its barcode check and its catalog picture, and
  // neither is knowable from the queue. Offering it here would only produce a
  // refusal the reviewer cannot act on from this screen, so new products are
  // approved from their own page. The server supports either kind; this is a
  // limit of what the queue knows, and it is stated rather than hidden.
  if (submission.kind !== 'label_mismatch') return false;
  return Boolean(
    readiness && readiness.fully_verified && !readiness.superseded &&
    submission.review_status === 'under_review',
  );
}

async function refreshBatchStates() {
  if (!state.session) return;
  const ids = state.submissions
    .filter((submission) => submission.review_status === 'under_review')
    .map((submission) => submission.id)
    .slice(0, 100);
  const requestId = ++state.batchStateRequest;
  if (ids.length === 0) {
    state.batchStates = new Map();
    renderQueue();
    renderBatchBar();
    return;
  }
  let states;
  try {
    ({ states } = await edge({ action: 'review_states', submission_ids: ids }));
  } catch {
    // Unknown readiness offers nothing to select, which is the safe direction.
    if (requestId !== state.batchStateRequest) return;
    state.batchStates = new Map();
    renderQueue();
    renderBatchBar();
    return;
  }
  if (requestId !== state.batchStateRequest) return;
  state.batchStates = new Map(
    (states ?? []).map((entry) => [entry.submission_id, entry]),
  );
  // Anything that stopped being eligible while we asked stops being selected.
  for (const id of [...state.batchSelected]) {
    const submission = state.submissions.find((entry) => entry.id === id);
    if (!submission || !batchEligible(submission)) state.batchSelected.delete(id);
  }
  renderQueue();
  renderBatchBar();
}

function toggleBatchSelection(submissionId) {
  const submission = state.submissions.find((entry) => entry.id === submissionId);
  if (!submission || !batchEligible(submission)) return;
  if (state.batchSelected.has(submissionId)) {
    state.batchSelected.delete(submissionId);
  } else {
    state.batchSelected.add(submissionId);
  }
  renderBatchBar();
}

function selectAllEligible() {
  for (const submission of state.submissions) {
    if (batchEligible(submission)) state.batchSelected.add(submission.id);
  }
  renderQueue();
  renderBatchBar();
}

function renderBatchBar() {
  const bar = $('batch-bar');
  if (!bar) return;
  const count = state.batchSelected.size;
  const button = $('batch-approve');
  const summary = $('batch-summary');
  if (button) {
    button.disabled = count === 0 || state.batchRunning;
    button.textContent = count === 1
      ? 'Approve 1 verified submission'
      : `Approve ${count} verified submissions`;
  }
  if (summary && !state.batchResults) {
    const eligible = state.submissions.filter(batchEligible).length;
    summary.textContent = eligible === 0
      ? 'Nothing is fully read yet.'
      : `${eligible} fully read and ready.`;
  }
  bar.hidden = false;
}

function renderBatchResults() {
  const host = $('batch-results');
  if (!host) return;
  host.textContent = '';
  const results = state.batchResults;
  if (!results) {
    host.hidden = true;
    return;
  }
  host.hidden = false;
  for (const entry of results) {
    const line = document.createElement('li');
    line.className = entry.applied ? 'ready' : 'blocking';
    line.textContent = entry.applied
      ? `${entry.submission_id}: approved`
      : `${entry.submission_id}: not approved — open it to see why`;
    host.append(line);
  }
}

async function approveBatch() {
  if (state.batchRunning || state.batchSelected.size === 0) return;
  const items = [...state.batchSelected].map((id) => {
    const readiness = batchState(id);
    const submission = state.submissions.find((entry) => entry.id === id);
    return {
      submission_id: id,
      to_status: 'approved',
      // Each item carries its own fence. The approved label itself is read
      // server-side from this reviewer's saved draft, never sent from here.
      expected_evidence_revision: readiness.evidence_revision,
      evidence_manifest_sha256: readiness.evidence_manifest_sha256,
      ...(submission?.kind === 'missing_product' && submission.product_image_photo_id
        ? { product_image_photo_id: submission.product_image_photo_id }
        : {}),
    };
  });
  state.batchRunning = true;
  state.batchResults = null;
  renderBatchBar();
  let response;
  try {
    response = await edge({ action: 'batch_transition', items });
  } catch {
    // The request may have applied some items before the answer was lost.
    // Re-running it blind would be a second attempt at work that may already
    // be done, so refresh and make the reviewer look instead.
    state.batchRunning = false;
    state.batchSelected.clear();
    setStatus(
      'The batch answer was lost. Some submissions may already be approved; ' +
      'the queue has been refreshed — check before trying again.', true);
    await loadQueue();
    return;
  }
  state.batchRunning = false;
  state.batchResults = response.results ?? [];
  // Only the ones that actually applied leave the selection; a refusal stays
  // visible so the reviewer can open it.
  for (const entry of state.batchResults) {
    if (entry.applied) state.batchSelected.delete(entry.submission_id);
  }
  setStatus(`${response.applied ?? 0} of ${response.total ?? items.length} approved.`);
  renderBatchResults();
  await loadQueue();
}

// ------------------------------------------------------------- help drawer

async function openHelp() {
  const drawer = $('help-drawer');
  const body = $('help-body');
  // Make the page inert immediately, not after the help fetch. Otherwise an
  // approval shortcut can fire in the interval between click and response.
  if (!drawer.open) drawer.showModal();
  body.textContent = 'Loading reviewer help…';
  if (!state.help) {
    try {
      const response = await fetch('/help.json');
      if (response.ok === false) throw new Error('Help unavailable');
      state.help = await response.json();
    } catch {
      body.textContent = 'Reviewer help could not be loaded. Close and reopen to retry.';
      return;
    }
  }
  body.textContent = '';
  const terms = document.createElement('dl');
  for (const entry of state.help.terms ?? []) {
    const term = document.createElement('dt');
    term.textContent = entry.term;
    const plain = document.createElement('dd');
    plain.textContent = entry.plain;
    terms.append(term, plain);
  }
  const rejections = document.createElement('dl');
  for (const entry of state.help.rejections ?? []) {
    const term = document.createElement('dt');
    term.textContent = `Reject: ${entry.code}`;
    const plain = document.createElement('dd');
    // Operator guidance, not a second translation of consumer resolution copy.
    // The app's productSubmissionResolutionGuidance owns that wording.
    plain.textContent = entry.use_when;
    rejections.append(term, plain);
  }
  const after = document.createElement('p');
  after.textContent = state.help.after_approve ?? '';
  body.append(terms, rejections, after);
}

// -------------------------------------------------------------- shortcuts
//
// One key per decision, and never while the reviewer is typing into a field.

function isTyping(target) {
  const tag = (target?.tagName ?? '').toLowerCase();
  return tag === 'input' || tag === 'textarea' || tag === 'select'
    || target?.isContentEditable === true;
}

function handleShortcut(event) {
  if (event.repeat || event.isComposing || document.querySelector('dialog[open]')) return;
  if (event.metaKey || event.ctrlKey || event.altKey) return;
  if (isTyping(event.target)) return;
  const keys = {
    j: () => moveSelection(1),
    k: () => moveSelection(-1),
    a: () => $('t-approve').disabled || approve(),
    s: () => $('t-under-review').disabled || transition({ to_status: 'under_review' }),
    '?': () => openHelp(),
  };
  const action = keys[event.key];
  if (!action) return;
  event.preventDefault();
  action();
}

function moveSelection(step) {
  const items = state.submissions ?? [];
  if (!items.length) return;
  const current = items.findIndex((item) => item.id === state.selected?.id);
  const next = items[Math.min(items.length - 1, Math.max(0, current + step))];
  if (next && next.id !== state.selected?.id) select(next);
}

// ------------------------------------------------------------------ AI draft
//
// Shown beside the photographs, never instead of them. A draft is a starting
// point a reviewer checks against the label; the fields most often wrong when
// a machine reads a supplement panel — dose, unit, and which blend a row
// belongs to — are the ones surfaced hardest here.

function draftFieldValue(field) {
  if (!field || typeof field !== 'object') return null;
  return field.status === 'read' || field.status === 'partial' ? field.value : null;
}

function draftFieldRow(label, field) {
  const row = document.createElement('div');
  row.className = 'draft-field';
  const status = field && typeof field === 'object' ? field.status : 'not_present';
  const value = draftFieldValue(field);
  const name = document.createElement('span');
  name.className = 'draft-label';
  name.textContent = label;
  const shown = document.createElement('span');
  // An unreadable field says so. It must never render as blank, which reads
  // as "nothing on the label" rather than "the model could not read it".
  shown.className = value === null ? 'draft-unknown' : 'draft-value';
  shown.textContent = value === null ? `— ${status}` : String(value);
  const provenance = document.createElement('span');
  provenance.className = 'mono muted';
  const sources = (field && field.sources) || [];
  provenance.textContent = sources.length
    ? `from ${sources.map((source) => source.input_id).join(', ')}`
    : 'no source cited';
  row.append(name, shown, provenance);
  return row;
}

function renderDraft() {
  const section = $('ai-draft');
  const body = $('ai-draft-body');
  const meta = $('ai-draft-meta');
  body.textContent = '';
  meta.textContent = '';
  const extraction = (state.selected?.extractions ?? []).find((entry) =>
    entry.draft_payload?.schema_version === 'label_draft_v1' &&
    entry.draft_payload?.draft_origin === 'model' &&
    entry.evidence_revision === state.selected.evidence_revision &&
    entry.draft_payload.evidence_revision === state.selected.evidence_revision);
  state.draft = extraction ?? null;
  if (!extraction || !extraction.draft_payload) {
    section.classList.add('hidden');
    return;
  }
  section.classList.remove('hidden');
  const payload = extraction.draft_payload;
  meta.textContent =
    `v${extraction.version} · ${extraction.actor_kind} · ${extraction.provider}` +
    ` ${extraction.model} · prompt ${extraction.prompt_version}` +
    ` · revision ${extraction.evidence_revision}`;

  if (payload.abstained) {
    const abstained = document.createElement('p');
    abstained.className = 'draft-unknown';
    abstained.textContent =
      `The model did not read this label: ${payload.abstain_reason ?? 'no reason given'}.` +
      ' Transcribe it by hand.';
    body.append(abstained);
  }

  const identity = payload.identity ?? {};
  const serving = payload.serving ?? {};
  body.append(
    draftFieldRow('Brand', identity.brand),
    draftFieldRow('Product name', identity.product_name),
    draftFieldRow('Serving size', serving.size),
    draftFieldRow('Servings per container', serving.servings_per_container),
    draftFieldRow('Serving basis', serving.basis_text),
    draftFieldRow('Other ingredients', (payload.other_ingredients ?? {}).text),
  );

  for (const finding of payload.discrepancies ?? []) {
    const warning = document.createElement('p');
    warning.className = 'draft-unknown';
    warning.textContent = `${finding.severity}: ${finding.code} — ${finding.detail ?? ''}`;
    body.append(warning);
  }
  for (const role of payload.photo_roles ?? []) {
    const finding = document.createElement('p');
    finding.textContent = `Photo ${role.photo_id}: ${role.readability}; ${(role.issues ?? []).join(', ')}; detected ${(role.inferred ?? []).map(r => r.role).join(', ')}`;
    body.append(finding);
  }
  const rows = payload.ingredient_rows ?? [];
  const table = document.createElement('table');
  table.className = 'draft-rows';
  const header = document.createElement('tr');
  for (const column of ['Ingredient', 'Amount', 'Unit', 'Form', '%DV', 'Belongs to', 'From']) {
    const cell = document.createElement('th');
    cell.textContent = column;
    header.append(cell);
  }
  table.append(header);
  rows.forEach((row, index) => {
    const line = document.createElement('tr');
    const amount = draftFieldValue(row.amount);
    const parent = row.parent_index === null || row.parent_index === undefined
      ? (row.is_blend_header ? 'blend header' : '')
      : draftFieldValue((rows[row.parent_index] ?? {}).display_name) ?? '?';
    const sources = [row.display_name, row.amount, row.form_text, row.percent_dv]
      .flatMap(field => field?.sources ?? []).map(s => s.input_id);
    const sourceText = [...new Set(sources)].join(', ');
    for (const [text, unknown] of [
      [draftFieldValue(row.display_name) ?? '—', draftFieldValue(row.display_name) === null],
      [amount ? String(amount.value) : '—', !amount],
      [amount ? amount.unit_text : '—', !amount],
      [draftFieldValue(row.form_text) ?? '—', !draftFieldValue(row.form_text)],
      [String(draftFieldValue(row.percent_dv) ?? '—'), false],
      [parent || '—', false],
      [sourceText || 'no source', !sourceText],
    ]) {
      const cell = document.createElement('td');
      cell.className = unknown ? 'draft-unknown' : '';
      cell.textContent = text;
      line.append(cell);
    }
    line.dataset.rowIndex = String(index);
    table.append(line);
  });
  if (rows.length) body.append(table);
}

/** Fill the editor from the draft, keeping only what the model claims to have
 * actually read. Nothing unreadable is carried across as a value, because a
 * blank a reviewer must fill is safer than a guess they might accept. */
function loadDraftIntoEditor() {
  const payload = state.draft?.draft_payload;
  if (!payload) return;
  const next = defaultPayload();
  next.brandName = String(draftFieldValue(payload.identity?.brand) ?? '');
  next.fullName = String(draftFieldValue(payload.identity?.product_name) ?? '');
  next.servingsPerContainer = draftFieldValue(payload.serving?.servings_per_container);
  const serving = draftFieldValue(payload.serving?.amount);
  next.servingSizes = [{
    minQuantity: serving?.value ?? null, maxQuantity: serving?.value ?? null,
    unit: serving?.unit_text ?? '',
    minDailyServings: null, maxDailyServings: null,
  }];
  const other = draftFieldValue(payload.other_ingredients?.text);
  // An observed list cannot be hidden behind a declared-none default.
  next.otherIngredients = String(other ?? '');
  next.otherIngredientsDisclosure = other !== null ? 'present'
    : payload.other_ingredients?.disclosure_hint === 'declared_none' ? 'declared_none' : '';
  const flat = (payload.ingredient_rows ?? []).map((row) => {
    const amount = draftFieldValue(row.amount);
    const form = draftFieldValue(row.form_text);
    const dv = draftFieldValue(row.percent_dv);
    return {
      ...emptyRow(), name: String(draftFieldValue(row.display_name) ?? ''),
      quantity: amount ? [{quantity: amount.value, unit: amount.unit_text}] : [],
      forms: form ? [{name: String(form)}] : [],
      // manual_label_v1 has no scalar %DV field. Preserve its printed value as
      // label notes, never confuse it with a compound/form percentage.
      ...(dv === null ? {} : {notes: `Printed %DV: ${dv}`}),
    };
  });
  next.ingredientRows = [];
  (payload.ingredient_rows ?? []).forEach((row, index) => {
    if (Number.isInteger(row.parent_index) && row.parent_index >= 0 &&
        row.parent_index < index && payload.ingredient_rows[row.parent_index].is_blend_header) {
      flat[row.parent_index].nestedRows.push(flat[index]);
    } else {
      next.ingredientRows.push(flat[index]);
    }
  });
  next.statements = (payload.statements ?? []).map(draftFieldValue)
    .filter(value => value !== null).map(value => ({type: 'Label statement', notes: String(value)}));
  state.payload = next;
  renderRows();
  syncFieldsFromPayload();
  updateShaPreview();
  setStatus(
    'Draft loaded. Every field is unverified until you have read it off the photographs.',
  );
}

function emptyRow() {
  return {
    name: '',
    ingredientGroup: 'Dietary Ingredient',
    quantity: [],
    forms: [],
    nestedRows: [],
  };
}

function defaultPayload() {
  return {
    brandName: '',
    fullName: '',
    ingredientRows: [emptyRow()],
    servingSizes: [{
      minQuantity: null,
      maxQuantity: null,
      minDailyServings: null,
      maxDailyServings: null,
      unit: '',
    }],
    servingsPerContainer: null,
    offMarket: 0,
    otherIngredientsDisclosure: '',
    otherIngredients: '',
    statements: [],
  };
}

function renderRows() {
  const tbody = $('rows-table').querySelector('tbody');
  tbody.textContent = '';
  state.payload.ingredientRows.forEach((row, index) => {
    renderIngredientRow(row, state.payload.ingredientRows, index, 0, tbody);
  });
  $('raw-json').value = JSON.stringify(state.payload, null, 2);
}

function renderIngredientRow(row, owner, index, depth, tbody) {
    const tr = document.createElement('tr');
    tr.style.setProperty('--ingredient-depth', depth);
    const nameCell = document.createElement('td');
    const nameInput = document.createElement('input');
    nameInput.value = row.name ?? '';
    nameInput.addEventListener('input', () => {
      row.name = nameInput.value;
      updateShaPreview();
    });
    const groupInput = document.createElement('input');
    groupInput.value = row.ingredientGroup ?? '';
    groupInput.placeholder = 'Ingredient group';
    groupInput.addEventListener('input', () => {
      row.ingredientGroup = groupInput.value;
      updateShaPreview();
    });
    nameCell.append(nameInput, groupInput);

    const qtyCell = document.createElement('td');
    const qtyInput = document.createElement('input');
    qtyInput.type = 'number';
    qtyInput.step = 'any';
    qtyInput.value = row.quantity?.[0]?.quantity ?? '';
    qtyInput.addEventListener('input', () => {
      row.quantity = [{
        quantity: qtyInput.value.trim() === '' ? null : Number(qtyInput.value),
        unit: row.quantity?.[0]?.unit ?? '',
      }];
      updateShaPreview();
    });
    qtyCell.append(qtyInput);

    const unitCell = document.createElement('td');
    const unitInput = document.createElement('input');
    unitInput.value = row.quantity?.[0]?.unit ?? '';
    unitInput.addEventListener('input', () => {
      row.quantity = [{
        quantity: qtyInput.value.trim() === '' ? null : Number(qtyInput.value),
        unit: unitInput.value,
      }];
      updateShaPreview();
    });
    unitCell.append(unitInput);

    const structureCell = document.createElement('td');
    const formSummary = document.createElement('div');
    formSummary.className = 'muted';
    formSummary.textContent = (row.forms ?? []).length
      ? `forms: ${row.forms.map((form) => form.name).join(', ')}`
      : 'no forms';
    const formButton = document.createElement('button');
    formButton.type = 'button';
    formButton.className = 'ghost compact';
    formButton.textContent = '+ form';
    formButton.addEventListener('click', () => addIngredientForm(row));
    const nestedButton = document.createElement('button');
    nestedButton.type = 'button';
    nestedButton.className = 'ghost compact';
    nestedButton.textContent = '+ child';
    nestedButton.addEventListener('click', () => addNestedRow(row));
    structureCell.append(formSummary, formButton, nestedButton);

    const removeCell = document.createElement('td');
    const removeButton = document.createElement('button');
    removeButton.type = 'button';
    removeButton.className = 'ghost';
    removeButton.textContent = '✕';
    removeButton.addEventListener('click', () => {
      owner.splice(index, 1);
      renderRows();
      updateShaPreview();
    });
    removeCell.append(removeButton);

    tr.append(nameCell, qtyCell, unitCell, structureCell, removeCell);
    tbody.append(tr);
    (row.nestedRows ?? []).forEach((nested, nestedIndex) => {
      renderIngredientRow(
        nested,
        row.nestedRows,
        nestedIndex,
        depth + 1,
        tbody,
      );
    });
}

function addIngredientForm(row) {
  const name = window.prompt('Form name shown on the label');
  if (!name?.trim()) return;
  row.forms ??= [];
  row.forms.push({ name: name.trim() });
  renderRows();
  updateShaPreview();
}

function addNestedRow(row) {
  row.nestedRows ??= [];
  row.nestedRows.push(emptyRow());
  renderRows();
  updateShaPreview();
}

function addStatement() {
  state.payload.statements ??= [];
  state.payload.statements.push({ type: 'Label statement', notes: '' });
  renderStatements();
  updateShaPreview();
}

function renderStatements() {
  const list = $('statements-list');
  list.textContent = '';
  (state.payload.statements ?? []).forEach((statement, index) => {
    const row = document.createElement('div');
    row.className = 'row';
    const type = document.createElement('input');
    type.placeholder = 'Statement type';
    type.value = statement.type ?? '';
    const notes = document.createElement('input');
    notes.className = 'grow';
    notes.placeholder = 'Exact label statement';
    notes.value = statement.notes ?? '';
    const remove = document.createElement('button');
    remove.type = 'button';
    remove.className = 'ghost';
    remove.textContent = '✕';
    type.addEventListener('input', () => {
      statement.type = type.value;
      updateShaPreview();
    });
    notes.addEventListener('input', () => {
      statement.notes = notes.value;
      updateShaPreview();
    });
    remove.addEventListener('click', () => {
      state.payload.statements.splice(index, 1);
      renderStatements();
      updateShaPreview();
    });
    row.append(type, notes, remove);
    list.append(row);
  });
}

function syncFieldsFromPayload() {
  $('p-brand').value = state.payload.brandName ?? '';
  $('p-name').value = state.payload.fullName ?? '';
  $('p-product-type').value = state.payload.productType?.name ?? '';
  $('p-physical-state').value = state.payload.physicalState?.name ?? '';
  $('p-servings-count').value = state.payload.servingsPerContainer ?? '';
  $('p-serving-qty').value = state.payload.servingSizes?.[0]?.maxQuantity ?? '';
  $('p-serving-unit').value = state.payload.servingSizes?.[0]?.unit ?? '';
  $('other-disclosure').value =
    state.payload.otherIngredientsDisclosure ?? '';
  $('other-ingredients').value = state.payload.otherIngredients ?? '';
  $('other-ingredients').disabled =
    $('other-disclosure').value !== 'present';
  renderStatements();
}

function syncScalarFields() {
  state.payload.brandName = $('p-brand').value;
  state.payload.fullName = $('p-name').value;
  const productType = $('p-product-type').value.trim();
  const physicalState = $('p-physical-state').value.trim();
  if (productType) state.payload.productType = { name: productType };
  else delete state.payload.productType;
  if (physicalState) state.payload.physicalState = { name: physicalState };
  else delete state.payload.physicalState;
  const servings = Number($('p-servings-count').value || 0);
  state.payload.servingsPerContainer = servings > 0 ? servings : null;
  const quantity = $('p-serving-qty').value.trim() === '' ? null : Number($('p-serving-qty').value);
  const unit = $('p-serving-unit').value;
  const existingServingSizes = Array.isArray(state.payload.servingSizes)
    ? state.payload.servingSizes
    : [];
  state.payload.servingSizes = [{
    ...(existingServingSizes[0] ?? {}),
    minQuantity: quantity,
    maxQuantity: quantity,
    minDailyServings: existingServingSizes[0]?.minDailyServings ?? null,
    maxDailyServings: existingServingSizes[0]?.maxDailyServings ?? null,
    unit,
  }, ...existingServingSizes.slice(1)];
  $('raw-json').value = JSON.stringify(state.payload, null, 2);
  updateShaPreview();
}

function syncDisclosureFields() {
  state.payload.otherIngredientsDisclosure = $('other-disclosure').value;
  if (state.payload.otherIngredientsDisclosure === 'present') {
    state.payload.otherIngredients = $('other-ingredients').value;
    $('other-ingredients').disabled = false;
  } else {
    state.payload.otherIngredients = '';
    $('other-ingredients').value = '';
    $('other-ingredients').disabled = true;
  }
  $('raw-json').value = JSON.stringify(state.payload, null, 2);
  updateShaPreview();
}

function applyRawJson() {
  try {
    const parsed = JSON.parse($('raw-json').value);
    state.payload = parsed;
    renderRows();
    syncFieldsFromPayload();
    updateShaPreview();
    setStatus('Raw payload applied.');
  } catch (error) {
    setStatus(`Raw JSON invalid: ${error.message}`, true);
  }
}

async function updateShaPreview() {
  const requestId = ++state.payloadHashRequest;
  let canonical;
  try {
    canonical = canonicalJson(state.payload);
    // Unchanged refreshes preserve checks. Edits revoke them synchronously,
    // before WebCrypto yields, and old promises cannot restore stale hashes.
    if (canonical === state.payloadCanonical && state.payloadSha) return;
    state.payloadCanonical = canonical;
    state.payloadSha = null;
    renderVerifyChecklist();
    renderReadiness();
    setDecisionAvailability();
    $('payload-sha').textContent = 'checking…';
    const digest = await sha256Hex(canonical);
    if (requestId !== state.payloadHashRequest) return;
    state.payloadSha = digest;
    $('payload-sha').textContent = digest.slice(0, 16) + '…';
  } catch {
    if (requestId !== state.payloadHashRequest) return;
    state.payloadSha = null;
    $('payload-sha').textContent = 'invalid payload';
  }
  // Deliberately outside the try above: a failure to save is not the label
  // being invalid, and must never be reported to the reviewer as one.
  if (state.payloadSha) {
    scheduleReviewSave();
    void refreshDiagnostics();
  }
  // Editing a field is the reviewer withdrawing their own check of it.
  renderVerifyChecklist();
  renderReadiness();
  setDecisionAvailability();
}

// ---------------------------------------------------------------- product picture

function renderProductPictureOptions() {
  renderReadiness();
  setDecisionAvailability();
  const container = $('product-picture-options');
  container.textContent = '';
  const missingProduct = state.selected?.kind === 'missing_product';
  $('reviewer-image-upload').disabled = !missingProduct;
  if (!missingProduct) {
    container.textContent = 'Catalog corrections keep the existing product picture.';
    return;
  }

  for (const photo of state.selected.photos ?? []) {
    if (!(photo.categories ?? []).includes('front_identity')) continue;
    const label = document.createElement('label');
    label.className = 'picture-option';
    const radio = document.createElement('input');
    radio.type = 'radio';
    radio.name = 'product-picture';
    radio.checked = state.productImage?.kind === 'photo' &&
      state.productImage.id === photo.photo_id;
    radio.addEventListener('change', () => {
      state.productImage = { kind: 'photo', id: photo.photo_id };
      renderReadiness();
      setDecisionAvailability();
    });
    const image = document.createElement('img');
    image.src = photo.signed_url;
    image.alt = 'Front-label product picture option';
    image.addEventListener('click', (event) => {
      event.preventDefault();
      openLightbox(photo);
    });
    label.append(radio, image, document.createTextNode('Use original front photo'));
    container.append(label);
  }

  for (const imageRecord of state.reviewerImages) {
    const label = document.createElement('label');
    label.className = 'picture-option';
    const radio = document.createElement('input');
    radio.type = 'radio';
    radio.name = 'product-picture';
    radio.checked = state.productImage?.kind === 'reviewer' &&
      state.productImage.id === imageRecord.objectId;
    radio.addEventListener('change', () => {
      state.productImage = { kind: 'reviewer', id: imageRecord.objectId };
      renderReadiness();
      setDecisionAvailability();
    });
    const image = document.createElement('img');
    image.src = imageRecord.previewUrl;
    image.alt = 'Reviewer-prepared product picture option';
    label.append(radio, image, document.createTextNode(imageRecord.label));
    container.append(label);
  }
}

async function uploadReviewerBlob(
  blob,
  sourceRights,
  rightsAttested,
  label,
  sourcePhotoId = null,
) {
  const objectId = crypto.randomUUID();
  const selectedId = state.selected?.id;
  const binding = selectedEvidenceBinding();
  const upload = await edge({
    action: 'create_reviewer_image_upload',
    submission_id: selectedId,
    ...binding,
    object_id: objectId,
    source_rights: sourceRights,
    rights_attested: rightsAttested,
    source_photo_id: sourcePhotoId,
  });
  const { error } = await state.client.storage
    .from('product-submission-reviewer-images')
    .uploadToSignedUrl(upload.object_path, upload.token, blob, {
      contentType: blob.type,
      upsert: false,
    });
  if (error) throw error;
  if (state.selected?.id !== selectedId || state.selected.evidence_revision !== binding.expected_evidence_revision) {
    throw new Error('The selected submission changed. Refresh before choosing its picture.');
  }
  const previewUrl = URL.createObjectURL(blob);
  state.reviewerImages.push({ objectId, previewUrl, label });
  state.productImage = { kind: 'reviewer', id: objectId };
  renderProductPictureOptions();
}

async function uploadReplacementImage() {
  const file = $('reviewer-image-file').files?.[0];
  const sourceRights = $('reviewer-image-rights').value;
  const attested = $('reviewer-image-attestation').checked;
  if (!file) return setStatus('Choose a replacement image first.', true);
  if (!attested) return setStatus('Confirm the publication rights first.', true);
  try {
    $('reviewer-image-upload').disabled = true;
    setStatus('Uploading the verified replacement…');
    await uploadReviewerBlob(file, sourceRights, true, 'Reviewer replacement');
    setStatus('Replacement uploaded and selected.');
  } catch (error) {
    setStatus(String(error.message ?? error), true);
  } finally {
    $('reviewer-image-upload').disabled = false;
  }
}

async function fetchReviewPhoto(signedUrl) {
  const response = await fetch('/api/photo', {
    method: 'POST',
    headers: {
      'content-type': 'application/json',
      authorization: `Bearer ${state.session.access_token}`,
    },
    body: JSON.stringify({ signed_url: signedUrl }),
  });
  if (!response.ok) throw new Error('Photo could not be opened.');
  return response.blob();
}

async function openLightbox(photo) {
  try {
    state.lightboxImage = await createImageBitmap(
      await fetchReviewPhoto(photo.signed_url),
    );
    state.lightboxPhoto = photo;
    state.lightboxRotation = 0;
    drawLightbox();
    $('image-use-crop').disabled =
      !(photo.categories ?? []).includes('front_identity');
    $('photo-lightbox').showModal();
  } catch (error) {
    setStatus(String(error.message ?? error), true);
  }
}

function drawLightbox() {
  const image = state.lightboxImage;
  if (!image) return;
  const canvas = $('image-canvas');
  const rotated = state.lightboxRotation % 180 !== 0;
  const naturalWidth = rotated ? image.height : image.width;
  const naturalHeight = rotated ? image.width : image.height;
  const scale = Math.min(1000 / naturalWidth, 800 / naturalHeight, 1);
  canvas.width = Math.max(1, Math.round(naturalWidth * scale));
  canvas.height = Math.max(1, Math.round(naturalHeight * scale));
  const context = canvas.getContext('2d');
  context.clearRect(0, 0, canvas.width, canvas.height);
  context.save();
  context.translate(canvas.width / 2, canvas.height / 2);
  context.rotate(state.lightboxRotation * Math.PI / 180);
  context.drawImage(
    image,
    -image.width * scale / 2,
    -image.height * scale / 2,
    image.width * scale,
    image.height * scale,
  );
  context.restore();
}

function rotateLightbox() {
  state.lightboxRotation = (state.lightboxRotation + 90) % 360;
  drawLightbox();
}

async function cropLightbox() {
  const source = $('image-canvas');
  const size = Math.min(source.width, source.height);
  const crop = document.createElement('canvas');
  crop.width = size;
  crop.height = size;
  crop.getContext('2d').drawImage(
    source,
    (source.width - size) / 2,
    (source.height - size) / 2,
    size,
    size,
    0,
    0,
    size,
    size,
  );
  const blob = await canvasBlob(crop);
  state.lightboxImage.close?.();
  state.lightboxImage = await createImageBitmap(blob);
  state.lightboxRotation = 0;
  drawLightbox();
}

function canvasBlob(canvas) {
  return new Promise((resolve, reject) => {
    canvas.toBlob(
      (blob) => blob ? resolve(blob) : reject(new Error('Image export failed.')),
      'image/jpeg',
      0.92,
    );
  });
}

async function useLightboxCrop() {
  if (!state.lightboxPhoto) return;
  try {
    const blob = await canvasBlob($('image-canvas'));
    await uploadReviewerBlob(
      blob,
      'user_evidence_crop',
      false,
      'Front-photo crop',
      state.lightboxPhoto.photo_id,
    );
    closeLightbox();
    setStatus('Crop uploaded and selected.');
  } catch (error) {
    setStatus(String(error.message ?? error), true);
  }
}

function closeLightbox() {
  const dialog = $('photo-lightbox');
  if (dialog.open) dialog.close();
  state.lightboxImage?.close?.();
  state.lightboxImage = null;
  state.lightboxPhoto = null;
}

// ---------------------------------------------------------------- decisions

function setDecisionAvailability() {
  const status = state.selected?.review_status;
  const terminal = state.reviewInvalidated || ['approved', 'rejected', 'duplicate'].includes(status);
  $('t-under-review').disabled = terminal || status !== 'submitted';
  const blockers = approvalBlockers();
  const approveButton = $('t-approve');
  approveButton.disabled = terminal || status !== 'under_review' || blockers.length > 0;
  // A disabled button with no reason is a dead end. Say the next action.
  approveButton.title = blockers.length ? blockers[0].todo : 'Approve this label.';
  $('t-reject').disabled = terminal || !['submitted', 'under_review'].includes(status);
  $('t-duplicate').disabled = terminal || !['submitted', 'under_review'].includes(status);
}

async function transition(fields) {
  if (!state.selected) return;
  if (state.reviewInvalidated) return setStatus('Review the updated evidence before deciding.', true);
  try {
    setStatus('Working…');
    const result = await edge({
      action: 'transition',
      submission_id: state.selected.id,
      ...selectedEvidenceBinding(),
      ...fields,
    });
    setStatus(
      `Done.${result.payload_sha256 ? ` payload sha256 ${result.payload_sha256}` : ''}`,
    );
    await loadQueue();
    await refreshSelected();
  } catch (error) {
    setStatus(String(error.message ?? error), true);
  }
}

async function approve() {
  const selection = state.selected;
  if (!selection) return;
  const blocker = approvalBlockers()[0];
  if (blocker) return setStatus(blocker.todo, true);
  const reviewedKey = verificationKey();
  if (state.reviewInvalidated) return setStatus('Review the updated evidence before deciding.', true);
  if (
    state.selected?.kind === 'missing_product' &&
    state.identityRecorded !== 'no_match_verified'
  ) {
    return setStatus('Record a fresh verified no-match identity check first.', true);
  }
  if (state.selected?.kind === 'missing_product' && !state.productImage) {
    return setStatus('Choose exactly one catalog product picture first.', true);
  }
  if (state.selected?.kind === 'missing_product') {
    try {
      await requireCurrentIdentity();
    } catch (error) {
      return setStatus(String(error.message ?? error), true);
    }
  }
  if (state.selected !== selection || state.reviewInvalidated ||
      reviewedKey !== verificationKey() || approvalBlockers().length) {
    return setStatus('The selected evidence changed. Review it before approving.', true);
  }
  // Input handlers already own the editor payload. Do not re-normalize it
  // after the reviewer attests to its exact digest (e.g. serving ranges).
  const fields = {
    to_status: 'approved',
    approved_schema_version: 'manual_label_v1',
    approved_payload: state.payload,
  };
  if (state.productImage?.kind === 'photo') {
    fields.product_image_photo_id = state.productImage.id;
  } else if (state.productImage?.kind === 'reviewer') {
    fields.product_image_reviewer_object_id = state.productImage.id;
  }
  return transition(fields);
}

function reject() {
  const code = $('reject-code').value;
  const detail = $('reject-detail').value.trim();
  const fields = { to_status: 'rejected', resolution_code: code };
  if (detail) fields.resolution_detail = detail;
  return transition(fields);
}

function markDuplicate() {
  const code = $('dup-code').value;
  const target = $('dup-target').value.trim();
  if (!target) return setStatus('Duplicate needs a target id.', true);
  const fields = { to_status: 'duplicate', resolution_code: code };
  if (code === 'already_in_catalog') {
    fields.resolved_dsld_id = target;
  } else {
    fields.duplicate_of = target;
  }
  return transition(fields);
}

async function catalogSearch() {
  const query = $('catalog-q').value.trim();
  const list = $('catalog-results');
  list.textContent = '';
  if (!query) return;
  const { results, error } = await (
    await fetch(`/api/catalog_search?q=${encodeURIComponent(query)}`)
  ).json();
  if (error) return setStatus(error, true);
  for (const product of results) {
    const item = document.createElement('li');
    item.textContent =
      `${product.dsld_id} · ${product.brand_name} ${product.product_name}` +
      (product.upc_sku ? ` · UPC ${product.upc_sku}` : '');
    item.addEventListener('click', () => {
      $('dup-target').value = product.dsld_id;
      $('dup-code').value = 'already_in_catalog';
    });
    list.append(item);
  }
}

boot();
