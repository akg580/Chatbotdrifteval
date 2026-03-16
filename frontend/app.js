/* ════════════════════════════════════════════════════════════
   SENTINEL 2.0 — app.js
   Reads API_BASE_URL from window.__ENV__ (injected at build time)
   so the same bundle works locally AND on Netlify/Render.
════════════════════════════════════════════════════════════ */

// ── Config ────────────────────────────────────────────────────────
// window.__ENV__ is injected by index.html <script> block.
// Locally it falls back to localhost:5000.
const _env        = (typeof window !== 'undefined' && window.__ENV__) || {};
const API_BASE_URL = _env.API_BASE_URL || 'http://localhost:5000';
const EVAL_API_KEY = _env.EVAL_API_KEY || '';

function apiHeaders(extra) {
  extra = extra || {};
  var h = Object.assign({ 'Content-Type': 'application/json' }, extra);
  if (EVAL_API_KEY) h['X-API-Key'] = EVAL_API_KEY;
  return h;
}

// ── State ─────────────────────────────────────────────────────────
var currentDataset  = null;
var currentResults  = null;
var complianceChart = null;
var empathyChart    = null;
var _activeJobId    = null;
var _pollTimer      = null;
var POLL_MS         = 3000;

// ── Boot ──────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', function() {
  initNav();
  initChatEvents();
  initDashboardEvents();
  probeApi();
  loadDashboardData();
  initCharts();
});

// ══════════════════════════════════════════════════════════════════
// NAVIGATION
// ══════════════════════════════════════════════════════════════════
function initNav() {
  document.querySelectorAll('.nav-item[data-tab]').forEach(function(btn) {
    btn.addEventListener('click', function() { switchTab(btn.dataset.tab); });
  });
}

function switchTab(name) {
  document.querySelectorAll('.nav-item[data-tab]').forEach(function(b) {
    b.classList.toggle('active', b.dataset.tab === name);
    b.setAttribute('aria-selected', String(b.dataset.tab === name));
  });
  document.querySelectorAll('.view-pane').forEach(function(p) {
    p.classList.toggle('active', p.id === name + '-tab');
  });
}

// ══════════════════════════════════════════════════════════════════
// API STATUS PROBE
// ══════════════════════════════════════════════════════════════════
async function probeApi() {
  var dot  = document.getElementById('apiStatus');
  var text = document.getElementById('apiStatusText');
  try {
    var r = await fetch(API_BASE_URL + '/', { headers: apiHeaders() });
    if (r.ok) {
      var d = await r.json();
      dot.classList.add('online');
      text.textContent = d.provider
        ? capitalize(d.provider) + ' · online'
        : 'API online';
      var badge = document.getElementById('providerBadge');
      if (badge && d.provider) {
        badge.querySelector('span:last-child').textContent =
          capitalize(d.provider) + ' · ' + modelLabel(d.provider);
      }
    } else { throw new Error('non-2xx'); }
  } catch (e) {
    dot.classList.add('offline');
    text.textContent = 'API offline';
  }
}

function capitalize(s) { return s.charAt(0).toUpperCase() + s.slice(1); }
function modelLabel(p) {
  var m = { groq: 'Llama 3.3', anthropic: 'Claude', openai: 'GPT-4o' };
  return m[p] || p;
}

// ══════════════════════════════════════════════════════════════════
// CHAT
// ══════════════════════════════════════════════════════════════════
function initChatEvents() {
  var input   = document.getElementById('chatInput');
  var send    = document.getElementById('sendMessage');
  var counter = document.getElementById('charCounter');

  if (send)  send.addEventListener('click', sendChat);
  if (input) {
    input.addEventListener('keypress', function(e) {
      if (e.key === 'Enter') sendChat();
    });
    input.addEventListener('input', function() {
      var n = input.value.length;
      if (counter) counter.textContent = n + ' / 2000';
      if (counter) counter.classList.toggle('warn', n > 1800);
    });
  }

  document.querySelectorAll('.chip').forEach(function(btn) {
    btn.addEventListener('click', function() {
      if (input) {
        input.value = btn.dataset.prompt || btn.textContent;
        input.focus();
        input.dispatchEvent(new Event('input'));
      }
    });
  });
}

async function sendChat() {
  var input   = document.getElementById('chatInput');
  var message = input ? input.value.trim() : '';
  if (!message) return;

  input.value = '';
  document.getElementById('charCounter').textContent = '0 / 2000';
  document.querySelector('.welcome-block') && document.querySelector('.welcome-block').remove();

  appendMsg(message, 'user');
  var typingId = appendTyping();

  var pulse = document.getElementById('evalPulse');
  if (pulse) pulse.classList.add('active');

  try {
    var r = await fetch(API_BASE_URL + '/api/chat', {
      method: 'POST',
      headers: apiHeaders(),
      body: JSON.stringify({ message: message }),
    });
    removeMsg(typingId);

    if (!r.ok) {
      var err = await r.json().catch(function() { return { error: r.statusText }; });
      appendMsg('Error ' + r.status + ': ' + (err.error || r.statusText), 'bot', true);
      showToast('API error: ' + (err.error || r.statusText), 'error');
      return;
    }

    var d = await r.json();
    if (d.success) {
      appendMsg(d.response, 'bot');
      renderEval(d.evaluation);
    } else {
      appendMsg('Something went wrong. Try again.', 'bot', true);
      showToast(d.error, 'error');
    }
  } catch (e) {
    removeMsg(typingId);
    appendMsg("Can't reach the backend. Is it running?", 'bot', true);
  } finally {
    if (pulse) pulse.classList.remove('active');
  }
}

function appendMsg(text, sender, isErr) {
  var feed = document.getElementById('chatMessages');
  var id   = 'msg-' + Date.now() + '-' + Math.random().toString(36).slice(2);

  var wrap   = document.createElement('div');
  wrap.className = 'message ' + sender;
  wrap.id = id;

  var av = document.createElement('div');
  av.className = 'message-av';
  av.setAttribute('aria-hidden', 'true');
  av.textContent = sender === 'user' ? 'YOU' : '🛡';

  var body   = document.createElement('div');
  body.className = 'message-body';
  var bubble = document.createElement('div');
  bubble.className = 'message-bubble';
  bubble.textContent = text;
  if (isErr) bubble.style.opacity = '0.55';

  var time = document.createElement('div');
  time.className = 'message-time';
  time.textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

  body.appendChild(bubble);
  body.appendChild(time);
  wrap.appendChild(av);
  wrap.appendChild(body);
  feed.appendChild(wrap);
  feed.scrollTop = feed.scrollHeight;
  return id;
}

function appendTyping() {
  var feed = document.getElementById('chatMessages');
  var id   = 'typing-' + Date.now();
  var wrap = document.createElement('div');
  wrap.className = 'message bot';
  wrap.id = id;

  var av = document.createElement('div');
  av.className = 'message-av';
  av.setAttribute('aria-hidden', 'true');
  av.textContent = '🛡';

  var body   = document.createElement('div');
  body.className = 'message-body';
  var bubble = document.createElement('div');
  bubble.className = 'message-bubble';
  bubble.innerHTML = '<div class="typing-bubble"><span></span><span></span><span></span></div>';

  body.appendChild(bubble);
  wrap.appendChild(av);
  wrap.appendChild(body);
  feed.appendChild(wrap);
  feed.scrollTop = feed.scrollHeight;
  return id;
}

function removeMsg(id) {
  var el = document.getElementById(id);
  if (el) el.remove();
}

function renderEval(ev) {
  var body = document.getElementById('realtimeEval');
  if (!ev || !body) return;

  var isOk   = ev.compliance_score === 1;
  var emp    = ev.empathy_score || 0;
  var empCls = emp >= 4 ? 'good' : emp >= 3 ? 'mid' : 'bad';

  function san(s) {
    return String(s == null ? '' : s)
      .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  }

  var flagsHtml = '';
  if (ev.flags && ev.flags.length) {
    flagsHtml = '<div class="flags-block">'
      + '<div class="flags-label">⚑ FLAGGED PHRASES</div>'
      + ev.flags.map(function(f) {
          return '<span class="flag-pill">' + san(f) + '</span>';
        }).join('')
      + '</div>';
  }

  body.innerHTML = '<div class="eval-result">'
    + '<div class="verdict-banner ' + (isOk ? 'ok' : 'fail') + '">'
    + '<span class="verdict-icon">' + (isOk ? '✓' : '✗') + '</span>'
    + (isOk ? 'Policy Compliant' : 'Policy Violation')
    + '</div>'
    + '<div class="score-row">'
    + '<div class="score-chip"><div class="score-chip-label">COMPLIANCE</div>'
    + '<div class="score-chip-value ' + (isOk ? 'good' : 'bad') + '">' + (isOk ? '1.0' : '0.0') + '</div></div>'
    + '<div class="score-chip"><div class="score-chip-label">EMPATHY</div>'
    + '<div class="score-chip-value ' + empCls + '">' + emp + '/5</div></div>'
    + '</div>'
    + '<div class="reasoning-block"><div class="reasoning-label">COMPLIANCE ANALYSIS</div>'
    + '<div class="reasoning-text">' + san(ev.compliance_reasoning) + '</div></div>'
    + '<div class="reasoning-block"><div class="reasoning-label">EMPATHY ANALYSIS</div>'
    + '<div class="reasoning-text">' + san(ev.empathy_reasoning) + '</div></div>'
    + flagsHtml
    + '</div>';
}

// ══════════════════════════════════════════════════════════════════
// DASHBOARD ACTIONS
// ══════════════════════════════════════════════════════════════════
function initDashboardEvents() {
  var gen     = document.getElementById('generateDataset');
  var run     = document.getElementById('runEval');
  var refresh = document.getElementById('refreshResults');
  if (gen)     gen.addEventListener('click', generateDataset);
  if (run)     run.addEventListener('click', runEvaluation);
  if (refresh) refresh.addEventListener('click', function() {
    loadDashboardData();
    showToast('Dashboard refreshed', 'success');
  });
}

async function generateDataset() {
  showLoading('Generating adversarial dataset…');
  try {
    var r = await fetch(API_BASE_URL + '/api/generate-dataset?count=50', {
      headers: apiHeaders(),
    });
    if (!r.ok) {
      var e = await r.json().catch(function() { return { error: r.statusText }; });
      showToast('Error ' + r.status + ': ' + e.error, 'error');
      return;
    }
    var d = await r.json();
    if (d.success) {
      currentDataset = d.questions;
      renderDataset(d.questions);
      switchTab('dashboard');
      showToast('Generated ' + d.count + ' adversarial questions', 'success');
    } else { showToast(d.error, 'error'); }
  } catch (e) { showToast('Could not connect to API', 'error'); }
  finally { hideLoading(); }
}

// ── Async job eval ────────────────────────────────────────────────
async function runEvaluation() {
  if (!currentDataset || !currentDataset.length) {
    showToast('Generate a dataset first', 'warning');
    return;
  }
  _stopPoll();
  showJobBar('Submitting evaluation job…', 0);

  try {
    var r = await fetch(API_BASE_URL + '/api/run-eval', {
      method: 'POST',
      headers: apiHeaders(),
      body: JSON.stringify({ dataset: currentDataset }),
    });
    if (!r.ok) {
      var e = await r.json().catch(function() { return { error: r.statusText }; });
      hideJobBar();
      showToast('Error ' + r.status + ': ' + e.error, 'error');
      return;
    }
    var d = await r.json();
    if (!d.success || !d.job_id) {
      hideJobBar();
      showToast(d.error || 'Failed to submit job', 'error');
      return;
    }
    _activeJobId = d.job_id;
    showJobBar('Job queued — starting…', 0, d.job_id);
    _pollTimer = setInterval(function() { _pollJob(_activeJobId); }, POLL_MS);
  } catch (e) {
    hideJobBar();
    showToast('Could not connect to API', 'error');
  }
}

async function _pollJob(jobId) {
  try {
    var r = await fetch(API_BASE_URL + '/api/jobs/' + jobId, { headers: apiHeaders() });
    if (!r.ok) { _stopPoll(); hideJobBar(); showToast('Poll error: ' + r.statusText, 'error'); return; }
    var d = await r.json();
    if (!d.success) { _stopPoll(); hideJobBar(); showToast(d.error, 'error'); return; }

    var job = d.job;
    showJobBar(_jobMsg(job), job.progress || 0, jobId);

    if (job.state === 'done') {
      _stopPoll();
      await _grabResult(jobId);
    } else if (job.state === 'failed') {
      _stopPoll(); hideJobBar();
      showToast('Evaluation failed: ' + (job.error || 'unknown'), 'error');
    } else if (job.state === 'cancelled') {
      _stopPoll(); hideJobBar();
      showToast('Evaluation cancelled', 'warning');
    }
  } catch (e) { /* network blip — keep polling */ }
}

async function _grabResult(jobId) {
  try {
    var r = await fetch(API_BASE_URL + '/api/jobs/' + jobId + '/result', { headers: apiHeaders() });
    var d = await r.json();
    hideJobBar();
    if (d.success && d.results) {
      currentResults = d.results;
      renderResults(d.results);
      updateKPIs(d.results.metrics);
      loadDashboardData();
      switchTab('dashboard');
      showToast('Evaluation complete!', 'success');
    } else { showToast(d.error || 'Could not retrieve results', 'error'); }
  } catch (e) { hideJobBar(); showToast('Could not retrieve results', 'error'); }
}

function _stopPoll() {
  if (_pollTimer) { clearInterval(_pollTimer); _pollTimer = null; }
  _activeJobId = null;
}

function _jobMsg(job) {
  if (job.state === 'pending') return 'Job queued — waiting for worker…';
  if (job.state === 'running') return job.total_items > 0
    ? 'Evaluating ' + job.done_items + '/' + job.total_items + ' responses…'
    : 'Evaluation running…';
  if (job.state === 'done') return 'Fetching results…';
  return 'State: ' + job.state;
}

// ── Job progress bar ──────────────────────────────────────────────
function showJobBar(msg, pct, jobId) {
  var bar = document.getElementById('_jobBar');
  if (!bar) {
    bar = document.createElement('div');
    bar.id = '_jobBar';
    bar.style.cssText = [
      'position:fixed;bottom:24px;right:24px;z-index:8000;width:310px',
      'background:rgba(10,10,35,0.92);backdrop-filter:blur(20px)',
      'border:1px solid rgba(224,64,251,0.25);border-radius:18px',
      'padding:16px 18px',
      'box-shadow:0 8px 40px rgba(0,0,0,0.5),0 0 40px rgba(224,64,251,0.08)',
      'animation:toast-slide 0.35s cubic-bezier(0.16,1,0.3,1)',
    ].join(';');
    document.body.appendChild(bar);
  }

  var p = Math.max(0, Math.min(100, pct || 0));
  var fillStyle = p > 0
    ? 'background:linear-gradient(90deg,#e040fb,#00e5ff);width:' + p + '%'
    : 'background:rgba(255,255,255,0.06);width:100%';

  bar.innerHTML = '<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px">'
    + '<span style="font-family:\'Space Mono\',monospace;font-size:11px;color:#9898c8;flex:1">' + san(msg) + '</span>'
    + '<button onclick="window._cancelJob()" style="background:none;border:none;color:#5050a0;cursor:pointer;font-size:14px;padding:0 0 0 10px">✕</button>'
    + '</div>'
    + '<div style="background:rgba(255,255,255,0.06);border-radius:3px;height:4px;overflow:hidden;margin-bottom:9px">'
    + '<div style="' + fillStyle + ';height:100%;border-radius:3px;transition:width .7s"></div>'
    + '</div>'
    + '<div style="display:flex;justify-content:space-between;align-items:center">'
    + (jobId ? '<span style="font-family:\'Space Mono\',monospace;font-size:9px;color:#5050a0">job: ' + san(jobId) + '</span>' : '<span></span>')
    + '<span style="font-family:\'Space Mono\',monospace;font-size:11px;color:#e040fb">' + p + '%</span>'
    + '</div>';
}

window._cancelJob = async function() {
  if (!_activeJobId) { hideJobBar(); return; }
  _stopPoll();
  try {
    await fetch(API_BASE_URL + '/api/jobs/' + _activeJobId,
                { method: 'DELETE', headers: apiHeaders() });
  } catch (e) { /* best-effort */ }
  hideJobBar();
  showToast('Evaluation cancelled', 'warning');
};

function hideJobBar() {
  var el = document.getElementById('_jobBar');
  if (el) el.remove();
}

// ══════════════════════════════════════════════════════════════════
// DASHBOARD DATA
// ══════════════════════════════════════════════════════════════════
async function loadDashboardData() {
  try {
    var r = await fetch(API_BASE_URL + '/api/dashboard-data', { headers: apiHeaders() });
    if (!r.ok) { await loadMockDrift(); return; }
    var d = await r.json();
    if (d.success && d.data.latest_metrics) {
      updateKPIs(d.data.latest_metrics);
      updateCharts(d.data.drift_data);
    } else { await loadMockDrift(); }
  } catch (e) { await loadMockDrift(); }
}

async function loadMockDrift() {
  try {
    var r = await fetch(API_BASE_URL + '/api/mock-drift-data');
    var d = await r.json();
    if (d.success) updateCharts(d.data);
  } catch (e) { /* silent */ }
}

// ── KPIs ──────────────────────────────────────────────────────────
function updateKPIs(m) {
  if (!m) return;

  var cr = m.compliance_rate || 0;
  countUp('complianceRate', cr * 100, 1, '%');
  setTimeout(function() {
    var b = document.getElementById('complianceBar');
    if (b) b.style.width = (cr * 100) + '%';
  }, 80);

  var em = m.avg_empathy_score || 0;
  countUp('empathyScore', em, 1, '');
  setTimeout(function() {
    var b = document.getElementById('empathyBar');
    if (b) b.style.width = ((em/5)*100) + '%';
  }, 80);

  countUp('totalFlags', m.total_flags || 0, 0, '');
  countUp('totalEvals', m.total_evaluations || 0, 0, '');

  renderSpark('flagSparkline', mockSpark(8, 0, m.total_flags || 10));
  renderSpark('evalSparkline', mockSpark(8, 10, m.total_evaluations || 50));
}

function countUp(id, target, dec, suffix) {
  var el = document.getElementById(id);
  if (!el) return;
  var from = parseFloat(el.textContent) || 0;
  var dur = 900;
  var t0  = performance.now();
  function step(ts) {
    var prog = Math.min((ts - t0) / dur, 1);
    var ease = 1 - Math.pow(1 - prog, 3);
    el.textContent = (from + (target - from) * ease).toFixed(dec) + suffix;
    if (prog < 1) requestAnimationFrame(step);
  }
  requestAnimationFrame(step);
}

function mockSpark(n, min, max) {
  var vals = [];
  for (var i = 0; i < n; i++) vals.push(min + Math.random() * (max - min));
  return vals;
}

function renderSpark(id, vals) {
  var el = document.getElementById(id);
  if (!el) return;
  var maxV = Math.max.apply(null, vals.concat([1]));
  el.innerHTML = vals.map(function(v) {
    var h = Math.max(4, (v / maxV) * 28);
    return '<div class="kpi-spark-bar" style="height:' + h + 'px" title="' + v.toFixed(0) + '"></div>';
  }).join('');
}

// ── Charts ────────────────────────────────────────────────────────
function initCharts() {
  var base = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: 'index', intersect: false },
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: 'rgba(10,10,35,0.95)',
        borderColor: 'rgba(224,64,251,0.25)',
        borderWidth: 1,
        titleColor: '#9898c8',
        bodyColor: '#f0f0ff',
        padding: 10,
        cornerRadius: 10,
      },
    },
    scales: {
      x: {
        grid: { color: 'rgba(255,255,255,0.04)' },
        ticks: { color: '#5050a0', font: { family: "'Space Mono'", size: 10 } },
      },
      y: {
        grid: { color: 'rgba(255,255,255,0.04)' },
        ticks: { color: '#5050a0', font: { family: "'Space Mono'", size: 10 } },
      },
    },
  };

  var cCtx = document.getElementById('complianceChart');
  var eCtx = document.getElementById('empathyChart');
  if (!cCtx || !eCtx) return;

  complianceChart = new Chart(cCtx.getContext('2d'), {
    type: 'line',
    data: {
      labels: [],
      datasets: [{
        label: 'Compliance', data: [],
        borderColor: '#00e5ff',
        backgroundColor: 'rgba(0,229,255,0.06)',
        borderWidth: 2, tension: 0.45, fill: true,
        pointBackgroundColor: '#00e5ff',
        pointRadius: 3, pointHoverRadius: 7,
        pointHoverBackgroundColor: '#00e5ff',
        pointHoverBorderColor: '#fff',
        pointHoverBorderWidth: 2,
      }],
    },
    options: Object.assign({}, base, {
      scales: Object.assign({}, base.scales, {
        y: Object.assign({}, base.scales.y, {
          min: 0, max: 1,
          ticks: Object.assign({}, base.scales.y.ticks, {
            callback: function(v) { return (v*100).toFixed(0)+'%'; },
          }),
        }),
      }),
    }),
  });

  empathyChart = new Chart(eCtx.getContext('2d'), {
    type: 'line',
    data: {
      labels: [],
      datasets: [{
        label: 'Empathy', data: [],
        borderColor: '#e040fb',
        backgroundColor: 'rgba(224,64,251,0.06)',
        borderWidth: 2, tension: 0.45, fill: true,
        pointBackgroundColor: '#e040fb',
        pointRadius: 3, pointHoverRadius: 7,
        pointHoverBackgroundColor: '#e040fb',
        pointHoverBorderColor: '#fff',
        pointHoverBorderWidth: 2,
      }],
    },
    options: Object.assign({}, base, {
      scales: Object.assign({}, base.scales, {
        y: Object.assign({}, base.scales.y, {
          min: 0, max: 5,
          ticks: Object.assign({}, base.scales.y.ticks, { stepSize: 1 }),
        }),
      }),
    }),
  });
}

function updateCharts(drift) {
  if (!drift || !drift.length) return;
  var labels = drift.map(function(d) {
    return new Date(d.timestamp).toLocaleDateString('en-GB', { month: 'short', day: 'numeric' });
  });
  if (complianceChart) {
    complianceChart.data.labels = labels;
    complianceChart.data.datasets[0].data = drift.map(function(d) { return d.compliance_rate; });
    complianceChart.update('active');
  }
  if (empathyChart) {
    empathyChart.data.labels = labels;
    empathyChart.data.datasets[0].data = drift.map(function(d) { return d.avg_empathy; });
    empathyChart.update('active');
  }
}

// ── Render helpers ────────────────────────────────────────────────
function san(s) {
  return String(s == null ? '' : s)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

function renderResults(results) {
  var el    = document.getElementById('resultsContainer');
  var badge = document.getElementById('resultsCount');
  var items = ((results && results.results) || []).slice(0, 20);
  if (badge) badge.textContent = items.length;
  if (!items.length) {
    el.innerHTML = '<div class="empty-placeholder"><p>No results</p></div>';
    return;
  }
  el.innerHTML = items.map(function(r) {
    var ev = r.evaluation || {};
    var ok = ev.compliance_score === 1;
    var flags = (ev.flags && ev.flags.length)
      ? '<div style="margin-top:6px">'
        + ev.flags.map(function(f) {
            return '<span class="flag-pill" style="font-size:9px">' + san(f) + '</span>';
          }).join('')
        + '</div>'
      : '';
    return '<div class="result-item ' + (ok ? 'compliant' : 'fail') + '">'
      + '<div class="result-top">'
      + '<div class="result-q">' + san(r.question) + '</div>'
      + '<div class="result-badges">'
      + '<span class="result-badge ' + (ok ? 'rb-ok' : 'rb-fail') + '">' + (ok ? '✓ OK' : '✗ FAIL') + '</span>'
      + '<span class="result-badge rb-emp">E:' + (ev.empathy_score || '-') + '/5</span>'
      + '</div></div>'
      + '<div class="result-resp">' + san(r.bot_response) + '</div>'
      + flags
      + '</div>';
  }).join('');
}

function renderDataset(qs) {
  var el    = document.getElementById('datasetContainer');
  var badge = document.getElementById('datasetCount');
  if (badge) badge.textContent = qs.length;
  if (!qs.length) {
    el.innerHTML = '<div class="empty-placeholder"><p>No dataset</p></div>';
    return;
  }
  el.innerHTML = qs.slice(0, 30).map(function(q) {
    var rl = san(q.risk_level || 'medium');
    return '<div class="ds-item ' + rl + '">'
      + '<div class="ds-top">'
      + '<span class="ds-id">#' + san(String(q.id || '').padStart(3, '0')) + '</span>'
      + '<div class="ds-tags">'
      + '<span class="ds-tag tag-cat">' + san(q.category) + '</span>'
      + '<span class="ds-tag tag-risk-' + rl + '">' + rl + '</span>'
      + '<span class="ds-tag tag-type">' + san(q.adversarial_type) + '</span>'
      + '</div></div>'
      + '<div class="ds-q">' + san(q.question) + '</div>'
      + '</div>';
  }).join('');
}

// ══════════════════════════════════════════════════════════════════
// TOAST
// ══════════════════════════════════════════════════════════════════
function showToast(msg, type) {
  type = type || 'success';
  var icons = { success: '✓', error: '✗', warning: '⚠' };
  var cont  = document.getElementById('toastContainer');
  if (!cont) return;

  var t = document.createElement('div');
  t.className = 'toast ' + type;
  t.innerHTML = '<span class="toast-ico">' + (icons[type] || '·') + '</span>'
    + '<span class="toast-msg">' + san(msg) + '</span>'
    + '<button class="toast-x" aria-label="Dismiss">✕</button>';

  t.querySelector('.toast-x').addEventListener('click', function() { dismissToast(t); });
  cont.appendChild(t);
  setTimeout(function() { dismissToast(t); }, 5000);
}

function dismissToast(t) {
  t.classList.add('leaving');
  t.addEventListener('animationend', function() { t.remove(); }, { once: true });
}

// ══════════════════════════════════════════════════════════════════
// LOADING
// ══════════════════════════════════════════════════════════════════
function showLoading(msg) {
  var lt = document.getElementById('loadingText');
  var lo = document.getElementById('loadingOverlay');
  if (lt) lt.textContent = msg || 'Processing…';
  if (lo) lo.classList.remove('hidden');
}

function hideLoading() {
  var lo = document.getElementById('loadingOverlay');
  if (lo) lo.classList.add('hidden');
}