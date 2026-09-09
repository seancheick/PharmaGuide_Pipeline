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
  $('add-row').addEventListener('click', () => {
    state.payload.ingredientRows.push(emptyRow());
    renderRows();
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
    item.addEventListener('click', () => select(submission));
    list.append(item);
  }
}

function select(submission) {
  state.selected = submission;
  state.reviewInvalidated = false;
  state.payload = defaultPayload();
  state.identityLookup = null;
  state.identityRecorded = null;
  state.reviewerImages = [];
  state.productImage = null;
  $('reviewer-image-attestation').checked = false;
  $('reviewer-image-file').value = '';
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
  if (!submission) return null;
  return `${submission.id}:${submission.evidence_revision}:${state.payloadSha ?? ''}`;
}

function verifiedSet() {
  const key = verificationKey();
  if (!key) return new Set();
  if (state.verifiedKey !== key) {
    // The label text or the evidence moved. A check of an older value is not
    // a check of this one, so the ticks go rather than quietly carrying over.
    state.verifiedKey = key;
    state.verified = new Set();
  }
  return state.verified;
}

function toggleVerified(field) {
  const verified = verifiedSet();
  if (verified.has(field)) verified.delete(field); else verified.add(field);
  renderVerifyChecklist();
  renderReadiness();
  setDecisionAvailability();
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
    box.addEventListener('change', () => toggleVerified(field));
    const text = document.createElement('span');
    text.textContent = label;
    wrap.append(box, text);
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
      done: submission.review_status === 'under_review',
      todo: 'Press Start review so this submission is assigned to you.',
      done_text: 'This submission is assigned to you.',
    },
    {
      done: missing.length === 0,
      todo: missing.length === 1
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

// ------------------------------------------------------------- help drawer

async function openHelp() {
  const drawer = $('help-drawer');
  const body = $('help-body');
  if (!state.help) {
    try {
      state.help = await (await fetch('/help.json')).json();
    } catch {
      state.help = { terms: [], rejections: [] };
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
    // The reviewer should see the sentence the submitter will read.
    plain.textContent = `${entry.use_when} The submitter sees: "${entry.user_sees}"`;
    rejections.append(term, plain);
  }
  const after = document.createElement('p');
  after.textContent = state.help.after_approve ?? '';
  body.append(terms, rejections, after);
  drawer.showModal();
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
  try {
    const digest = await sha256Hex(canonicalJson(state.payload));
    state.payloadSha = digest;
    $('payload-sha').textContent = digest.slice(0, 16) + '…';
  } catch {
    state.payloadSha = null;
    $('payload-sha').textContent = 'invalid payload';
  }
  // Editing a field is the reviewer withdrawing their own check of it.
  renderVerifyChecklist();
  renderReadiness();
  setDecisionAvailability();
}

// ---------------------------------------------------------------- product picture

function renderProductPictureOptions() {
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
  if (state.selected !== selection || state.reviewInvalidated) {
    return setStatus('The selected evidence changed. Review it before approving.', true);
  }
  syncScalarFields();
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
