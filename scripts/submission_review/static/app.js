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
  payload: null,
  refreshTimer: null,
  nextAfter: null,
  totalOpenCount: 0,
  queueRequestId: 0,
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
  $('apply-raw').addEventListener('click', applyRawJson);
  $('t-under-review').addEventListener('click', () =>
    transition({ to_status: 'under_review' }),
  );
  $('t-approve').addEventListener('click', approve);
  $('t-reject').addEventListener('click', reject);
  $('t-duplicate').addEventListener('click', markDuplicate);
  $('catalog-go').addEventListener('click', catalogSearch);
  for (const id of ['p-brand', 'p-name', 'p-servings-count', 'p-serving-qty', 'p-serving-unit']) {
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
  state.payload = defaultPayload();
  renderQueue();
  renderDetail();
  scheduleUrlRefresh();
}

// Signed URLs live 300s; refresh this submission's row just before expiry.
function scheduleUrlRefresh() {
  clearTimeout(state.refreshTimer);
  state.refreshTimer = setTimeout(refreshSelected, 270 * 1000);
}

async function refreshSelected() {
  if (!state.selected) return;
  try {
    const { submissions } = await edge({
      action: 'list',
      submission_id: state.selected.id,
      limit: 1,
    });
    if (submissions.length === 1) {
      state.selected = submissions[0];
      renderDetail();
      scheduleUrlRefresh();
    }
  } catch {
    // Keep the stale view; the next manual action reloads.
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
    img.addEventListener('click', () => window.open(photo.signed_url, '_blank'));
    const caption = document.createElement('figcaption');
    caption.textContent =
      `#${photo.seq} · ${(photo.categories ?? []).join(', ')}`;
    figure.append(img, caption);
    grid.append(figure);
  }

  renderRows();
  syncFieldsFromPayload();
  updateShaPreview();
}

// ---------------------------------------------------------------- payload

function emptyRow() {
  return {
    name: '',
    quantity: [{ quantity: 0, unit: 'mg' }],
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
      minQuantity: 1,
      maxQuantity: 1,
      minDailyServings: 1,
      maxDailyServings: 1,
      unit: 'Capsule(s)',
    }],
    servingsPerContainer: 30,
    offMarket: 0,
  };
}

function renderRows() {
  const tbody = $('rows-table').querySelector('tbody');
  tbody.textContent = '';
  state.payload.ingredientRows.forEach((row, index) => {
    const tr = document.createElement('tr');
    const nameCell = document.createElement('td');
    const nameInput = document.createElement('input');
    nameInput.value = row.name ?? '';
    nameInput.addEventListener('input', () => {
      row.name = nameInput.value;
      updateShaPreview();
    });
    nameCell.append(nameInput);

    const qtyCell = document.createElement('td');
    const qtyInput = document.createElement('input');
    qtyInput.type = 'number';
    qtyInput.step = 'any';
    qtyInput.value = row.quantity?.[0]?.quantity ?? '';
    qtyInput.addEventListener('input', () => {
      row.quantity = [{
        quantity: Number(qtyInput.value || 0),
        unit: row.quantity?.[0]?.unit ?? 'mg',
      }];
      updateShaPreview();
    });
    qtyCell.append(qtyInput);

    const unitCell = document.createElement('td');
    const unitInput = document.createElement('input');
    unitInput.value = row.quantity?.[0]?.unit ?? 'mg';
    unitInput.addEventListener('input', () => {
      row.quantity = [{
        quantity: Number(qtyInput.value || 0),
        unit: unitInput.value,
      }];
      updateShaPreview();
    });
    unitCell.append(unitInput);

    const removeCell = document.createElement('td');
    const removeButton = document.createElement('button');
    removeButton.type = 'button';
    removeButton.className = 'ghost';
    removeButton.textContent = '✕';
    removeButton.addEventListener('click', () => {
      state.payload.ingredientRows.splice(index, 1);
      renderRows();
      updateShaPreview();
    });
    removeCell.append(removeButton);

    tr.append(nameCell, qtyCell, unitCell, removeCell);
    tbody.append(tr);
  });
  $('raw-json').value = JSON.stringify(state.payload, null, 2);
}

function syncFieldsFromPayload() {
  $('p-brand').value = state.payload.brandName ?? '';
  $('p-name').value = state.payload.fullName ?? '';
  $('p-servings-count').value = state.payload.servingsPerContainer ?? '';
  $('p-serving-qty').value = state.payload.servingSizes?.[0]?.maxQuantity ?? 1;
  $('p-serving-unit').value = state.payload.servingSizes?.[0]?.unit ?? '';
}

function syncScalarFields() {
  state.payload.brandName = $('p-brand').value;
  state.payload.fullName = $('p-name').value;
  const servings = Number($('p-servings-count').value || 0);
  if (servings > 0) state.payload.servingsPerContainer = servings;
  const quantity = Number($('p-serving-qty').value || 1);
  const unit = $('p-serving-unit').value || 'Capsule(s)';
  state.payload.servingSizes = [{
    minQuantity: quantity,
    maxQuantity: quantity,
    minDailyServings: 1,
    maxDailyServings: 1,
    unit,
  }];
  $('raw-json').value = JSON.stringify(state.payload, null, 2);
  updateShaPreview();
}

function applyRawJson() {
  try {
    state.payload = JSON.parse($('raw-json').value);
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
    $('payload-sha').textContent =
      (await sha256Hex(canonicalJson(state.payload))).slice(0, 16) + '…';
  } catch {
    $('payload-sha').textContent = 'invalid payload';
  }
}

// ---------------------------------------------------------------- decisions

async function transition(fields) {
  if (!state.selected) return;
  try {
    setStatus('Working…');
    const result = await edge({
      action: 'transition',
      submission_id: state.selected.id,
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

function approve() {
  syncScalarFields();
  return transition({
    to_status: 'approved',
    approved_schema_version: 'manual_label_v1',
    approved_payload: state.payload,
  });
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
