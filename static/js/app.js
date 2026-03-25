/* ============================================================
   ModelBench AI — App / Benchmark Page JavaScript
   ============================================================ */

// ── Nav scroll ─────────────────────────────────────────────
const nav = document.querySelector('.nav');
window.addEventListener('scroll', () => {
  nav.classList.toggle('scrolled', window.scrollY > 4);
});

// ── State ──────────────────────────────────────────────────
let currentResultId = null;
let compareIds = new Set();
const charts = {};

// ── Chart.js theme ─────────────────────────────────────────
Chart.defaults.color = '#4a6080';
Chart.defaults.borderColor = 'rgba(255,255,255,0.05)';
const C = {
  cyan:      '#00d97e',
  cyanDim:   'rgba(0,217,126,0.08)',
  amber:     '#ffaa00',
  green:     '#00ff88',
  red:       '#ff4466',
  purple:    '#b06cff',
  text:      '#8ca0c0',
};
const PALETTE = [C.cyan, C.amber, C.green, C.purple, C.red];

// ── Tabs ───────────────────────────────────────────────────
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('tab-' + btn.dataset.tab).classList.add('active');
    if (btn.dataset.tab === 'history') loadHistory();
    if (btn.dataset.tab === 'system')  loadSystemInfo();
    if (btn.dataset.tab === 'compare') updateCompareBar();
  });
});

// ── Drop Zones ─────────────────────────────────────────────
function initDropZone(zoneId, inputId, nameId, onFile) {
  const zone  = document.getElementById(zoneId);
  const input = document.getElementById(inputId);
  const nameEl= document.getElementById(nameId);
  if (!zone || !input) return;

  zone.addEventListener('click', () => input.click());
  zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('dragover'); });
  zone.addEventListener('dragleave', () => zone.classList.remove('dragover'));
  zone.addEventListener('drop', e => {
    e.preventDefault(); zone.classList.remove('dragover');
    if (e.dataTransfer.files[0]) {
      input.files = e.dataTransfer.files;
      setZoneFile(zone, nameEl, e.dataTransfer.files[0].name);
      if (onFile) onFile(e.dataTransfer.files[0].name);
    }
  });
  input.addEventListener('change', () => {
    if (input.files[0]) {
      setZoneFile(zone, nameEl, input.files[0].name);
      if (onFile) onFile(input.files[0].name);
    }
  });
}
function setZoneFile(zone, nameEl, name) {
  zone.classList.add('has-file');
  nameEl.textContent = name;
}
function pickleCheck(filename) {
  const warn = document.getElementById('pickleWarning');
  if (warn) warn.classList.toggle('visible', filename.endsWith('.pkl'));
}

initDropZone('modelDropZone',  'modelFile',  'modelFileName', pickleCheck);
initDropZone('dataDropZone',   'dataFile',   'dataFileName');
initDropZone('labelsDropZone', 'labelsFile', 'labelsFileName');
initDropZone('sweepModelDropZone', 'sweepModelFile', 'sweepModelFileName', pickleCheck);
initDropZone('sweepDataDropZone',  'sweepDataFile',  'sweepDataFileName');

// ── Run Benchmark ───────────────────────────────────────────
async function runBenchmark() {
  const modelFile  = document.getElementById('modelFile').files[0];
  const dataFile   = document.getElementById('dataFile').files[0];
  const labelsFile = document.getElementById('labelsFile').files[0];
  const asyncMode  = document.getElementById('asyncMode').checked;

  if (!modelFile || !dataFile) {
    showAlert('Please select both a model file and a test data file.', 'error'); return;
  }

  const fd = new FormData();
  fd.append('model', modelFile);
  fd.append('data', dataFile);
  if (labelsFile) fd.append('labels', labelsFile);
  fd.append('batch_size',     document.getElementById('batchSize').value);
  fd.append('num_iterations', document.getElementById('numIterations').value);
  fd.append('warmup_runs',    document.getElementById('warmupRuns').value);

  const btn    = document.getElementById('runBtn');
  const loader = document.getElementById('loadingBar');
  const fill   = document.getElementById('loadingFill');
  const msg    = document.getElementById('loadingMsg');
  const pct    = document.getElementById('loadingPct');

  btn.disabled = true;
  loader.classList.add('active');
  fill.classList.remove('indeterminate');
  fill.style.width = '0%';
  clearAlert();
  document.getElementById('resultsSection').classList.remove('visible');

  try {
    if (asyncMode) {
      msg.textContent = 'Submitting async job…';
      pct.textContent = '';
      const res  = await fetch('/api/benchmark/async', { method: 'POST', body: fd });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Failed to start job');
      await pollJob(data.job_id, fill, pct, msg);
    } else {
      fill.classList.add('indeterminate');
      msg.textContent = 'Running benchmark — profiling inference latency…';
      pct.textContent = '';
      const res  = await fetch('/api/benchmark', { method: 'POST', body: fd });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Benchmark failed');
      fill.classList.remove('indeterminate');
      fill.style.width = '100%';
      onDone(data);
    }
  } catch (err) {
    showAlert('Error: ' + err.message, 'error');
  } finally {
    btn.disabled = false;
    loader.classList.remove('active');
    fill.classList.remove('indeterminate');
  }
}

async function pollJob(jobId, fill, pct, msg) {
  return new Promise((resolve, reject) => {
    const iv = setInterval(async () => {
      try {
        const res  = await fetch(`/api/jobs/${jobId}`);
        const data = await res.json();
        if (data.progress) { fill.style.width = data.progress + '%'; pct.textContent = data.progress + '%'; }
        if (data.status === 'done') {
          clearInterval(iv);
          fill.style.width = '100%';
          const rr = await fetch(`/api/jobs/${jobId}/result`);
          const rd = await rr.json();
          onDone(rd); resolve();
        } else if (data.status === 'error') {
          clearInterval(iv); reject(new Error(data.error || 'Job failed'));
        } else {
          msg.textContent = `Async job running… ${data.progress || 0}%`;
        }
      } catch (e) { clearInterval(iv); reject(e); }
    }, 800);
  });
}

function onDone(data) {
  currentResultId = data.result_id;
  renderResults(data);
  showAlert(`✓ Benchmark complete — ${data.metrics.avg_latency_ms}ms avg · ${data.metrics.total_predictions} predictions`, 'success');
}

// ── Render Results ──────────────────────────────────────────
function renderResults(data) {
  const m = data.metrics;

  // Perf tiles
  const tiles = [
    { label: 'Avg Latency',   value: m.avg_latency_ms,     unit: 'ms', hl: true },
    { label: 'Median',        value: m.median_latency_ms,  unit: 'ms' },
    { label: 'P90',           value: m.p90_latency_ms,     unit: 'ms' },
    { label: 'P95',           value: m.p95_latency_ms,     unit: 'ms' },
    { label: 'P99',           value: m.p99_latency_ms,     unit: 'ms' },
    { label: 'Min',           value: m.min_latency_ms,     unit: 'ms' },
    { label: 'Max',           value: m.max_latency_ms,     unit: 'ms' },
    { label: 'Std Dev',       value: m.std_latency_ms,     unit: 'ms' },
    { label: 'Throughput',    value: m.throughput_per_sec, unit: '/s', hl: true },
    { label: 'Total Time',    value: m.total_time_ms,      unit: 'ms' },
    { label: 'Total Preds',   value: m.total_predictions,  unit: '' },
  ];
  document.getElementById('metricsGrid').innerHTML = tiles.map(t => `
    <div class="metric-tile">
      <div class="metric-label">${t.label}</div>
      <div class="metric-value${t.hl ? ' highlight' : ''}">${fmt(t.value)}<span class="metric-unit">${t.unit}</span></div>
    </div>`).join('');

  // Memory / CPU
  let mcHtml = '';
  const hasMem = m.memory_peak_kb != null, hasCpu = m.cpu_avg_pct != null, hasRam = m.ram_rss_mb != null;
  if (hasMem || hasCpu || hasRam) {
    mcHtml = '<div class="section-divider">Memory &amp; CPU</div><div class="metrics-grid">';
    if (hasMem) {
      mcHtml += tile('Mem Peak', m.memory_peak_kb, 'KB', 'warn');
      mcHtml += tile('Mem Current', m.memory_current_kb, 'KB');
    }
    if (hasRam) mcHtml += tile('RAM RSS', m.ram_rss_mb, 'MB', 'warn');
    if (hasCpu) {
      mcHtml += tile('CPU Avg', m.cpu_avg_pct, '%', 'warn');
      mcHtml += tile('CPU Peak', m.cpu_max_pct, '%', 'warn');
    }
    mcHtml += '</div>';
  }
  document.getElementById('memCpuSection').innerHTML = mcHtml;

  // Charts
  renderBarChart(m);
  renderLineChart(data.latencies || []);
  renderHistChart(data.histogram);
  renderAccuracy(data.accuracy_metrics);
  renderIntrospection(data.introspection);

  document.getElementById('resultsSection').classList.add('visible');
  document.getElementById('resultsSection').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function tile(label, value, unit, cls = '') {
  return `<div class="metric-tile"><div class="metric-label">${label}</div><div class="metric-value ${cls}">${fmt(value)}<span class="metric-unit">${unit}</span></div></div>`;
}

function fmt(v) {
  if (v == null) return '—';
  const n = parseFloat(v);
  if (isNaN(n)) return String(v);
  return n >= 10000 ? n.toFixed(0) : n >= 100 ? n.toFixed(1) : n.toFixed(2);
}

function fmtTime(iso) {
  try { return new Date(iso).toLocaleString(); } catch { return iso; }
}

function escHtml(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// ── Charts ──────────────────────────────────────────────────
function destroyChart(key) { if (charts[key]) { charts[key].destroy(); charts[key] = null; } }

const CHART_OPTS = {
  responsive: true, maintainAspectRatio: false,
  plugins: { legend: { display: false } },
  scales: {
    y: { beginAtZero: true, grid: { color: 'rgba(255,255,255,0.04)' }, ticks: { font: { family: "'IBM Plex Mono'", size: 10 }, color: C.text } },
    x: { grid: { display: false },                                      ticks: { font: { family: "'IBM Plex Mono'", size: 10 }, color: C.text, maxTicksLimit: 8 } }
  }
};

function renderBarChart(m) {
  destroyChart('bar');
  const ctx = document.getElementById('barChart').getContext('2d');
  charts.bar = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: ['Min','Avg','Med','P90','P95','P99','Max'],
      datasets: [{ label: 'ms',
        data: [m.min_latency_ms, m.avg_latency_ms, m.median_latency_ms, m.p90_latency_ms, m.p95_latency_ms, m.p99_latency_ms, m.max_latency_ms],
        backgroundColor: [C.green, C.cyan, C.cyan, C.amber, C.amber, C.red, C.red].map(c => c + '99'),
        borderColor:     [C.green, C.cyan, C.cyan, C.amber, C.amber, C.red, C.red],
        borderWidth: 1, borderRadius: 4, borderSkipped: false,
      }]
    },
    options: { ...CHART_OPTS }
  });
}

function renderLineChart(latencies) {
  destroyChart('line');
  if (!latencies.length) return;
  const ctx = document.getElementById('lineChart').getContext('2d');
  charts.line = new Chart(ctx, {
    type: 'line',
    data: {
      labels: latencies.map((_,i) => i+1),
      datasets: [{ label: 'Latency (ms)', data: latencies,
        borderColor: C.cyan, backgroundColor: C.cyanDim,
        borderWidth: 1.5, fill: true, pointRadius: 0, tension: 0.35,
      }]
    },
    options: { ...CHART_OPTS }
  });
}

function renderHistChart(histogram) {
  destroyChart('hist');
  if (!histogram || !histogram.counts) return;
  const labels = histogram.edges.slice(0,-1).map((e,i) => `${e.toFixed(1)}`);
  const ctx = document.getElementById('histChart').getContext('2d');
  charts.hist = new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [{ label: 'Count', data: histogram.counts,
        backgroundColor: 'rgba(176,108,255,0.4)',
        borderColor: C.purple, borderWidth: 1, borderRadius: 3,
      }]
    },
    options: { ...CHART_OPTS }
  });
}

// ── Accuracy ────────────────────────────────────────────────
function renderAccuracy(acc) {
  const el = document.getElementById('accuracySection');
  if (!acc || !Object.keys(acc).length) { el.innerHTML = ''; return; }
  if (acc.error) {
    el.innerHTML = `<div class="section-divider">Accuracy</div><div style="font-family:var(--font-mono);font-size:11px;color:var(--red)">⚠ ${acc.error}</div>`;
    return;
  }
  const tiles = Object.entries(acc).filter(([k]) => k !== 'n_samples_evaluated').map(([k,v]) => {
    const label = k.replace(/_/g,' ').replace(/\b\w/g, c => c.toUpperCase());
    const val = k === 'accuracy' ? (v*100).toFixed(1) : fmt(v);
    const unit = k === 'accuracy' ? '%' : '';
    return `<div class="acc-tile"><div class="acc-label">${label}</div><div class="acc-value">${val}<span class="acc-unit">${unit}</span></div></div>`;
  }).join('');
  const n = acc.n_samples_evaluated ? ` (${acc.n_samples_evaluated} samples)` : '';
  el.innerHTML = `<div class="section-divider">Accuracy Metrics${n}</div><div class="accuracy-grid">${tiles}</div>`;
}

// ── Introspection ────────────────────────────────────────────
function renderIntrospection(intro) {
  const el = document.getElementById('introspectionSection');
  if (!intro || Object.keys(intro).length === 0) { el.innerHTML = ''; return; }

  const skip = new Set(['framework','params','feature_importances_top10','introspection_error','inputs','outputs','classes']);
  const items = Object.entries(intro).filter(([k]) => !skip.has(k)).map(([k,v]) => {
    const label = k.replace(/_/g,' ').replace(/\b\w/g, c => c.toUpperCase());
    const cls = (k === 'is_classifier' || k === 'is_regressor') && v ? 'accent' : '';
    return `<div class="intro-item"><div class="intro-key">${label}</div><div class="intro-val ${cls}">${String(v)}</div></div>`;
  }).join('');

  let paramsHtml = '';
  if (intro.params) {
    paramsHtml = `<div class="section-divider" style="margin-top:16px;">Parameters</div>
      <table class="params-table">${Object.entries(intro.params).map(([k,v]) =>
        `<tr><td>${k}</td><td>${v}</td></tr>`).join('')}</table>`;
  }

  let fiHtml = '';
  if (intro.feature_importances_top10) {
    fiHtml = `<div class="section-divider" style="margin-top:16px;">Feature Importances (Top ${intro.feature_importances_top10.length})</div>
      <div style="background:var(--bg-raised);border:1px solid var(--border-faint);border-radius:var(--radius);padding:16px">
      ${intro.feature_importances_top10.map((v,i) => `
        <div class="fi-bar-row">
          <span class="fi-label">feat ${i}</span>
          <div class="fi-track"><div class="fi-fill" style="width:${Math.min(100,v*100*5)}%"></div></div>
          <span class="fi-pct">${(v*100).toFixed(1)}%</span>
        </div>`).join('')}
      </div>`;
  }

  if (intro.introspection_error) {
    el.innerHTML = `<div class="section-divider">Introspection</div><div style="font-family:var(--font-mono);font-size:11px;color:var(--red)">⚠ ${intro.introspection_error}</div>`;
    return;
  }

  el.innerHTML = `<div class="section-divider">Model Introspection</div>
    <div class="intro-grid">${items}</div>${paramsHtml}${fiHtml}`;
}

// ── History ─────────────────────────────────────────────────
async function loadHistory() {
  try {
    const res = await fetch('/api/results');
    const list = await res.json();
    renderHistory(list);
    renderTrendChart(list);
  } catch (e) { console.error(e); }
}

function renderHistory(list) {
  const el = document.getElementById('historyList');
  if (!list.length) {
    el.innerHTML = `<div class="empty-state"><span class="empty-icon">◇</span>No benchmarks yet. Run one to get started.</div>`;
    return;
  }
  el.innerHTML = list.map(r => {
    const sel = compareIds.has(r.result_id);
    const tag = r.tag ? `<span class="history-tag-badge">🏷 ${escHtml(r.tag)}</span>` : '';
    return `
    <div class="history-item${sel ? ' selected' : ''}" id="hi-${r.result_id}">
      <div class="history-main">
        <div class="history-row1" onclick="viewResult('${r.result_id}')">
          <span class="history-type-badge">${r.model_type}</span>
          <span class="history-metric-text">
            <strong>${fmt(r.metrics.avg_latency_ms)}ms</strong> avg ·
            ${fmt(r.metrics.throughput_per_sec)}/s ·
            bs=${r.batch_size} · ${r.num_iterations}it
            ${tag}
          </span>
          <span class="history-time">${fmtTime(r.timestamp)}</span>
        </div>
        <div class="tag-editor" id="te-${r.result_id}">
          <div class="field" style="margin-bottom:8px;"><label>Tag</label>
            <input type="text" id="ti-${r.result_id}" value="${escHtml(r.tag||'')}" placeholder="e.g. after-optimization">
          </div>
          <textarea id="ni-${r.result_id}" placeholder="Notes…">${escHtml(r.notes||'')}</textarea>
          <div class="tag-editor-actions">
            <button class="btn-sm active" onclick="saveTag('${r.result_id}')">Save</button>
            <button class="btn-sm" onclick="closeTagEditor('${r.result_id}')">Cancel</button>
            ${r.tag ? `<button class="btn-sm danger" onclick="removeTag('${r.result_id}')">Remove</button>` : ''}
          </div>
        </div>
      </div>
      <div class="history-actions">
        <button class="btn-sm${sel?' active':''}" onclick="toggleCompare('${r.result_id}')">${sel?'✓ Sel':'+ Cmp'}</button>
        <button class="btn-sm" onclick="openTagEditor('${r.result_id}')">🏷</button>
        <button class="btn-sm" onclick="window.location.href='/api/export/${r.result_id}'">↓</button>
        <button class="btn-sm danger" onclick="deleteResult('${r.result_id}')">✕</button>
      </div>
    </div>`;
  }).join('');
}

function renderTrendChart(list) {
  destroyChart('trend');
  const ctx = document.getElementById('trendChart')?.getContext('2d');
  if (!ctx || !list.length) return;
  const sorted = [...list].sort((a,b) => a.timestamp.localeCompare(b.timestamp));
  const byType = {};
  sorted.forEach(r => {
    const t = r.model_type || 'unknown';
    (byType[t] = byType[t] || []).push(r);
  });
  const datasets = Object.entries(byType).map(([type, rows], i) => ({
    label: type,
    data: rows.map(r => r.metrics.avg_latency_ms),
    labels: rows.map(r => fmtTime(r.timestamp)),
    borderColor: PALETTE[i % PALETTE.length],
    backgroundColor: 'transparent',
    borderWidth: 2, pointRadius: 5, tension: 0.3,
  }));
  charts.trend = new Chart(ctx, {
    type: 'line',
    data: { labels: sorted.map(r => fmtTime(r.timestamp)), datasets },
    options: {
      ...CHART_OPTS,
      plugins: {
        legend: { display: true, labels: { font: { family: "'IBM Plex Mono'", size: 10 }, color: C.text, boxWidth: 10 } }
      },
      scales: {
        ...CHART_OPTS.scales,
        y: { ...CHART_OPTS.scales.y, title: { display: true, text: 'Avg Latency (ms)', font: { family: "'IBM Plex Mono'", size: 10 }, color: C.text } }
      }
    }
  });
}

async function viewResult(id) {
  try {
    const res = await fetch(`/api/results/${id}`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.error);
    currentResultId = id;
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
    document.querySelector('[data-tab="benchmark"]').classList.add('active');
    document.getElementById('tab-benchmark').classList.add('active');
    renderResults(data);
  } catch (e) { showAlert('Failed to load result', 'error'); }
}

async function deleteResult(id) {
  if (!confirm('Delete this result?')) return;
  await fetch(`/api/results/${id}`, { method: 'DELETE' });
  compareIds.delete(id);
  updateCompareBar();
  loadHistory();
  showAlert('Result deleted.', 'success');
}

function openTagEditor(id)  { document.getElementById('te-' + id)?.classList.add('open'); }
function closeTagEditor(id) { document.getElementById('te-' + id)?.classList.remove('open'); }

async function saveTag(id) {
  const tag   = document.getElementById('ti-' + id)?.value;
  const notes = document.getElementById('ni-' + id)?.value;
  await fetch(`/api/results/${id}/tag`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ tag, notes }),
  });
  closeTagEditor(id);
  loadHistory();
  showAlert('Tag saved.', 'success');
}

async function removeTag(id) {
  await fetch(`/api/results/${id}/tag`, { method: 'DELETE' });
  closeTagEditor(id);
  loadHistory();
}

async function exportAllResults() { window.location.href = '/api/export/all'; }

// ── Compare ─────────────────────────────────────────────────
function toggleCompare(id) {
  if (compareIds.has(id)) compareIds.delete(id);
  else compareIds.add(id);
  updateCompareBar();
  loadHistory();
}

function updateCompareBar() {
  const bar  = document.getElementById('compareBar');
  const text = document.getElementById('compareBarText');
  if (compareIds.size > 0) { bar.classList.add('active'); text.textContent = `${compareIds.size} selected`; }
  else bar.classList.remove('active');
}

function addCurrentToCompare() {
  if (!currentResultId) { showAlert('Run a benchmark first.', 'error'); return; }
  compareIds.add(currentResultId);
  updateCompareBar();
  showAlert('Added to compare.', 'success');
}

function clearCompare() {
  compareIds.clear();
  updateCompareBar();
  document.getElementById('compareResults').innerHTML = '';
  loadHistory();
}

async function runCompare() {
  if (compareIds.size < 2) { showAlert('Select at least 2 results.', 'error'); return; }
  const res  = await fetch('/api/compare', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ result_ids: [...compareIds] }),
  });
  const data = await res.json();
  if (!res.ok) { showAlert(data.error, 'error'); return; }
  renderCompare(data.comparison);
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
  document.querySelector('[data-tab="compare"]').classList.add('active');
  document.getElementById('tab-compare').classList.add('active');
}

function renderCompare(items) {
  const METRICS = [
    ['avg_latency_ms','Avg Latency','ms',false],['median_latency_ms','Median','ms',false],
    ['p90_latency_ms','P90','ms',false],['p95_latency_ms','P95','ms',false],
    ['p99_latency_ms','P99','ms',false],['min_latency_ms','Min','ms',false],
    ['max_latency_ms','Max','ms',false],['std_latency_ms','Std Dev','ms',false],
    ['throughput_per_sec','Throughput','/s',true],['total_time_ms','Total Time','ms',false],
    ['memory_peak_kb','Mem Peak','KB',false],['ram_rss_mb','RAM RSS','MB',false],
    ['cpu_avg_pct','CPU Avg','%',false],
  ];
  const bests = {};
  METRICS.forEach(([k,,, hi]) => {
    const vals = items.map(it => it.metrics[k]).filter(v => v != null);
    if (vals.length) bests[k] = hi ? Math.max(...vals) : Math.min(...vals);
  });

  let html = `<div class="compare-table-wrap"><table class="compare-table"><thead><tr><th>Metric</th>`;
  items.forEach((it,i) => {
    const tag = it.tag ? ` · ${escHtml(it.tag)}` : '';
    html += `<th>${it.model_type} #${i+1}<br><small style="opacity:.5">${it.batch_size}bs · ${it.num_iterations}it${tag}</small></th>`;
  });
  html += `</tr></thead><tbody>`;
  METRICS.forEach(([k, label, unit, hi]) => {
    const vals = items.map(it => it.metrics[k]);
    if (!vals.some(v => v != null)) return;
    html += `<tr><td style="color:var(--text-muted)">${label}</td>`;
    vals.forEach(v => {
      if (v == null) { html += `<td>—</td>`; return; }
      const best  = v === bests[k];
      const worst = !best && vals.filter(x => x!=null).length > 1 &&
                    v === (hi ? Math.min(...vals.filter(x=>x!=null)) : Math.max(...vals.filter(x=>x!=null)));
      let badge = '';
      if (!best && bests[k] != null && bests[k] !== 0) {
        const pct = Math.abs((v - bests[k]) / bests[k] * 100).toFixed(1);
        badge = `<span class="diff-worse">+${pct}%</span>`;
      }
      html += `<td class="${best?'compare-best':worst?'compare-worst':''}">${fmt(v)}<span style="font-size:9px;opacity:.5">${unit}</span>${badge}</td>`;
    });
    html += `</tr>`;
  });
  html += `</tbody></table></div>`;

  // Compare bar charts
  html += `<div class="charts-row" style="margin-top:20px;">
    <div class="chart-box"><div class="chart-box-title">Avg Latency</div><canvas id="cmpLatChart"></canvas></div>
    <div class="chart-box"><div class="chart-box-title">Throughput</div><canvas id="cmpTpChart"></canvas></div>
  </div>`;
  document.getElementById('compareResults').innerHTML = html;

  const labels = items.map((it,i) => `${it.model_type}#${i+1}`);
  const bgColors = items.map((_,i) => PALETTE[i % PALETTE.length] + '99');
  const bdColors = items.map((_,i) => PALETTE[i % PALETTE.length]);

  destroyChart('cmpLat'); destroyChart('cmpTp');
  const latCtx = document.getElementById('cmpLatChart').getContext('2d');
  charts.cmpLat = new Chart(latCtx, {
    type:'bar', data:{ labels, datasets:[{ data: items.map(it=>it.metrics.avg_latency_ms), backgroundColor:bgColors, borderColor:bdColors, borderWidth:1, borderRadius:4 }] },
    options:{...CHART_OPTS}
  });
  const tpCtx = document.getElementById('cmpTpChart').getContext('2d');
  charts.cmpTp = new Chart(tpCtx, {
    type:'bar', data:{ labels, datasets:[{ data: items.map(it=>it.metrics.throughput_per_sec), backgroundColor:bgColors, borderColor:bdColors, borderWidth:1, borderRadius:4 }] },
    options:{...CHART_OPTS}
  });
}

// ── Sweep ────────────────────────────────────────────────────
async function runSweep() {
  const modelFile = document.getElementById('sweepModelFile').files[0];
  const dataFile  = document.getElementById('sweepDataFile').files[0];
  if (!modelFile || !dataFile) { showAlert('Select model and data files.', 'error'); return; }

  const fd = new FormData();
  fd.append('model', modelFile);
  fd.append('data', dataFile);
  fd.append('batch_sizes',    document.getElementById('sweepBatchSizes').value);
  fd.append('num_iterations', document.getElementById('sweepIterations').value);
  fd.append('warmup_runs',    document.getElementById('sweepWarmup').value);

  const btn    = document.getElementById('sweepBtn');
  const loader = document.getElementById('sweepLoadingBar');
  btn.disabled = true;
  loader.classList.add('active');
  document.getElementById('sweepResults').style.display = 'none';
  clearAlert();

  try {
    const res  = await fetch('/api/sweep', { method: 'POST', body: fd });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error);
    renderSweep(data);
    showAlert(`✓ Sweep complete across ${data.sweep.length} batch sizes`, 'success');
  } catch (e) {
    showAlert('Sweep failed: ' + e.message, 'error');
  } finally {
    btn.disabled = false;
    loader.classList.remove('active');
  }
}

function renderSweep(data) {
  const valid  = data.sweep.filter(r => !r.error);
  const bestTp = data.best_throughput_batch_size;
  const bestLt = data.best_latency_batch_size;

  document.getElementById('sweepRecommendation').innerHTML = `
    <div class="recommendation-box">
      <div class="rec-item"><div class="rec-label">🚀 Best Throughput</div><div class="rec-value">bs=${bestTp||'—'}</div></div>
      <div class="rec-item"><div class="rec-label">⚡ Best Latency</div><div class="rec-value">bs=${bestLt||'—'}</div></div>
      <div class="rec-item"><div class="rec-label">Framework</div><div class="rec-value">${data.model_type||'—'}</div></div>
    </div>`;

  document.getElementById('sweepTable').innerHTML = `
    <thead><tr><th>Batch</th><th>Avg Lat.</th><th>P99</th><th>Throughput</th><th>Mem Peak</th></tr></thead>
    <tbody>${data.sweep.map(r => r.error
      ? `<tr><td>${r.batch_size}</td><td colspan="4" style="color:var(--red)">${r.error}</td></tr>`
      : `<tr class="${r.batch_size===bestTp||r.batch_size===bestLt?'best-row':''}">
           <td>${r.batch_size}${r.batch_size===bestTp?' 🚀':''}${r.batch_size===bestLt?' ⚡':''}</td>
           <td>${fmt(r.avg_latency_ms)} ms</td>
           <td>${fmt(r.p99_latency_ms)} ms</td>
           <td>${fmt(r.throughput_per_sec)} /s</td>
           <td>${fmt(r.memory_peak_kb)} KB</td>
         </tr>`).join('')}</tbody>`;

  const labels = valid.map(r => 'bs='+r.batch_size);
  const bestTpBg = valid.map(r => r.batch_size===bestTp ? C.cyan+99 : C.cyan+33);
  const bestLtColor = valid.map(r => r.batch_size===bestLt ? C.amber : C.amber+66);

  destroyChart('swTp'); destroyChart('swLt');
  const tpCtx = document.getElementById('sweepTpChart').getContext('2d');
  charts.swTp = new Chart(tpCtx, {
    type:'bar', data:{ labels, datasets:[{ data: valid.map(r=>r.throughput_per_sec), backgroundColor:bestTpBg, borderColor: C.cyan, borderWidth:1, borderRadius:3 }] },
    options:{...CHART_OPTS}
  });
  const ltCtx = document.getElementById('sweepLatChart').getContext('2d');
  charts.swLt = new Chart(ltCtx, {
    type:'line', data:{ labels, datasets:[{ data: valid.map(r=>r.avg_latency_ms),
      borderColor: C.amber, backgroundColor: 'rgba(255,170,0,0.08)',
      borderWidth: 2, fill: true, pointRadius: 5,
      pointBackgroundColor: bestLtColor, tension: 0.3,
    }] },
    options:{...CHART_OPTS}
  });

  document.getElementById('sweepResults').style.display = 'block';
}

// ── System Info ──────────────────────────────────────────────
async function loadSystemInfo() {
  try {
    const res  = await fetch('/api/system');
    const info = await res.json();
    const c    = document.getElementById('systemInfo');

    const fwHtml = Object.entries(info.frameworks||{}).map(([name, fw]) =>
      `<span class="fw-tag ${fw.available?'ok':'no'}">${fw.available?'●':'○'} ${name} ${fw.version||'—'}</span>`
    ).join('');

    let hw = '';
    if (info.total_ram_gb)     hw += `<div class="sys-tile"><div class="sys-label">Total RAM</div><div class="sys-value">${info.total_ram_gb} GB</div></div>`;
    if (info.available_ram_gb) hw += `<div class="sys-tile"><div class="sys-label">Available RAM</div><div class="sys-value">${info.available_ram_gb} GB</div></div>`;
    if (info.cpu_count_logical)hw += `<div class="sys-tile"><div class="sys-label">CPU Cores (logical)</div><div class="sys-value">${info.cpu_count_logical}</div></div>`;
    if (info.cpu_freq_mhz)     hw += `<div class="sys-tile"><div class="sys-label">CPU Freq</div><div class="sys-value">${info.cpu_freq_mhz} MHz</div></div>`;
    if (info.gpu)              hw += `<div class="sys-tile"><div class="sys-label">GPU</div><div class="sys-value">${info.gpu}</div></div>`;

    c.innerHTML = `
      <div class="sys-grid">
        <div class="sys-tile"><div class="sys-label">Platform</div><div class="sys-value">${info.platform}</div></div>
        <div class="sys-tile"><div class="sys-label">Python</div><div class="sys-value">${info.python}</div></div>
        <div class="sys-tile"><div class="sys-label">Processor</div><div class="sys-value">${info.processor||'Unknown'}</div></div>
        ${hw}
        <div class="sys-tile" style="grid-column:1/-1"><div class="sys-label">ML Frameworks</div><div class="sys-value" style="margin-top:6px">${fwHtml}</div></div>
      </div>`;
  } catch {
    document.getElementById('systemInfo').innerHTML = `<div class="empty-state"><span class="empty-icon">⚙</span>Failed to load system info.</div>`;
  }
}

// ── Alerts ───────────────────────────────────────────────────
let alertTimer;
function showAlert(msg, type = 'info') {
  clearTimeout(alertTimer);
  const c = document.getElementById('alertContainer');
  if (c) { c.innerHTML = `<div class="alert alert-${type}">${msg}</div>`; }
  alertTimer = setTimeout(clearAlert, 5000);
}
function clearAlert() {
  const c = document.getElementById('alertContainer');
  if (c) c.innerHTML = '';
}

function exportCurrent() {
  if (currentResultId) window.location.href = `/api/export/${currentResultId}`;
  else showAlert('No result to export.', 'error');
}

// ── Init ─────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  loadSystemInfo();
});
