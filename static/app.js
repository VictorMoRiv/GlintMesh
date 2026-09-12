import { readSSE } from './sse.mjs';

// ─── i18n ─────────────────────────────────────────────────────────────────
const I18N = {
  es: {
    subtitle: 'A2UI over MCP Interface Mesh', tools: 'Tools', clear: 'Limpiar', export: 'Exportar',
    preview: 'Vista previa', a2ui: 'Superficie A2UI', code: 'Código', agent_status: 'Estado del agente',
    ready: 'Listo para generar interfaces', tool_empty: 'Las llamadas MCP aparecerán aquí mientras trabaja el agente',
    quick_prompts: 'Prompts rápidos', p1: 'Dashboard de portafolio', p2: 'Monitor de índices', p3: 'Analizador de riesgo',
    p4: 'Calculadora de inversión', p5: 'Tablero forex', p6: 'Noticias financieras',
    welcome_desc: 'Describe cualquier dashboard financiero en lenguaje natural. GlintMesh obtiene datos MCP y los renderiza como superficies A2UI en segundos.',
    f1t: 'Datos de mercado', f1d: 'Cotizaciones, índices e historial en tiempo real', f2d: 'Superficies UI tipadas vía MCP',
    f3d: 'Herramientas demo activadas (datos simulados)', f3d_off: 'MCP desactivado; Gemini genera con datos de ejemplo',
    welcome_hint: 'Escribe abajo o elige un prompt rápido del sidebar',
    a2ui_empty: 'Las superficies A2UI de las llamadas MCP se renderizarán aquí',
    generated_html: 'HTML generado', copy: 'Copiar', disclaimer: 'GlintMesh puede producir datos financieros simulados con fines demostrativos',
    placeholder: "Describe una interfaz financiera... ej. 'Dashboard de portafolio en tiempo real'",
    drawer_title: 'MCPs conectados', drawer_sub: 'Servidores y herramientas disponibles para el agente',
    data: 'Datos', datasets_title: 'Mis datasets', datasets_sub: 'Sube CSV o JSON (máx 2 MB). El agente construye la interfaz con tus datos.',
    upload: 'Subir', use: 'Usar', using: 'Usando', no_datasets: 'Aún no hay datasets. Sube tu primer CSV o JSON.',
    uploaded_ok: 'Dataset cargado', upload_fail: 'No se pudo cargar el dataset', rows: 'filas',
    session_cleared: 'Sesión limpiada', no_export: 'Aún no hay interfaz para exportar', exported: 'Interfaz exportada',
    copied: 'Código copiado', mcp_disabled: 'MCP desactivado. Gemini funciona sin herramientas.', mcp_error: 'No se pudieron obtener herramientas',
    waiting: 'Esperando a Gemini...', generating: 'Generando interfaz...', analyzing: 'Analizando solicitud...',
    done_ok: 'Interfaz generada correctamente', resp_ok: 'Respuesta recibida', failed: 'Generación fallida',
  },
  en: {
    subtitle: 'A2UI over MCP Interface Mesh', tools: 'Tools', clear: 'Clear', export: 'Export',
    preview: 'Preview', a2ui: 'A2UI Surface', code: 'Code', agent_status: 'Agent Status',
    ready: 'Ready to generate interfaces', tool_empty: 'MCP tool calls will appear here as the agent works',
    quick_prompts: 'Quick Prompts', p1: 'Portfolio dashboard', p2: 'Market indices monitor', p3: 'Credit risk analyzer',
    p4: 'Investment calculator', p5: 'Forex rates board', p6: 'Financial news feed',
    welcome_desc: 'Describe any financial dashboard in plain language. GlintMesh fetches MCP data and renders it as A2UI surfaces in seconds.',
    f1t: 'Live Market Data', f1d: 'Real-time quotes, indices, and price history', f2d: 'Typed UI surfaces streamed over MCP',
    f3d: 'Demo tools enabled (simulated data)', f3d_off: 'MCP disabled; Gemini generates with sample data',
    welcome_hint: 'Type a request below or choose a quick prompt from the sidebar',
    a2ui_empty: 'A2UI surfaces from MCP tool calls will render here',
    generated_html: 'Generated HTML', copy: 'Copy', disclaimer: 'GlintMesh may produce simulated financial data for demonstration purposes',
    placeholder: "Describe a financial interface... e.g. 'Build me a real-time stock portfolio dashboard'",
    drawer_title: 'Connected MCPs', drawer_sub: 'Servers and tools available to the agent',
    data: 'Data', datasets_title: 'My datasets', datasets_sub: 'Upload CSV or JSON (max 2 MB). The agent builds the interface from your data.',
    upload: 'Upload', use: 'Use', using: 'Using', no_datasets: 'No datasets yet. Upload your first CSV or JSON.',
    uploaded_ok: 'Dataset uploaded', upload_fail: 'Could not upload dataset', rows: 'rows',
    session_cleared: 'Session cleared', no_export: 'No interface to export yet', exported: 'Interface exported',
    copied: 'Code copied to clipboard', mcp_disabled: 'MCP is disabled. Gemini works without tools.', mcp_error: 'Could not fetch tools',
    waiting: 'Waiting for Gemini...', generating: 'Generating interface...', analyzing: 'Analyzing request...',
    done_ok: 'Interface generated successfully', resp_ok: 'Response received', failed: 'Generation failed',
  },
};
let lang = localStorage.getItem('glintmesh-lang') || 'es';
if (!I18N[lang]) lang = 'es';
const t = (k) => (I18N[lang] && I18N[lang][k]) || I18N.en[k] || k;

function applyLang(next) {
  lang = I18N[next] ? next : 'es';
  localStorage.setItem('glintmesh-lang', lang);
  document.documentElement.lang = lang;
  document.querySelectorAll('[data-i18n]').forEach((el) => {
    const key = el.getAttribute('data-i18n');
    if (I18N[lang][key]) el.textContent = I18N[lang][key];
  });
  document.querySelectorAll('[data-i18n-ph]').forEach((el) => {
    el.placeholder = t(el.getAttribute('data-i18n-ph'));
  });
  document.getElementById('lang-es').classList.toggle('active', lang === 'es');
  document.getElementById('lang-en').classList.toggle('active', lang === 'en');
}

// ─── State ──────────────────────────────────────────────────────────────────
const state = { isGenerating: false, controller: null, generatedHTML: '', agentMessage: '', toolCalls: [], a2ui: [], charts: [], lastSummary: '' };
const SESSION_KEY = 'glintmesh-session-v1';

const $ = (id) => document.getElementById(id);
const chatTextarea = $('chat-textarea'), sendBtn = $('send-btn'), toolFeed = $('tool-feed'),
  statusText = $('status-text'), welcomeState = $('welcome-state'), generatedWrapper = $('generated-wrapper'),
  agentBubble = $('agent-bubble'), agentBubbleText = $('agent-bubble-text'),
  previewContainer = $('preview-frame-container'), previewIframe = $('preview-iframe'),
  codeOutput = $('code-output'), progressBar = $('progress-bar-container'), progressLabel = $('progress-label'),
  charCount = $('char-count'), codeBadge = $('code-badge'), btnCopyCode = $('btn-copy-code'),
  a2uiFeed = $('a2ui-feed'), a2uiBadge = $('a2ui-badge');

document.querySelectorAll('.tab-btn').forEach((btn) => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab-btn').forEach((b) => b.classList.remove('active'));
    document.querySelectorAll('.panel').forEach((p) => p.classList.remove('active'));
    btn.classList.add('active');
    $('panel-' + btn.dataset.tab).classList.add('active');
  });
});

chatTextarea.addEventListener('input', () => {
  chatTextarea.style.height = 'auto';
  chatTextarea.style.height = Math.min(chatTextarea.scrollHeight, 120) + 'px';
  const len = chatTextarea.value.length;
  charCount.textContent = len + ' / 500';
  charCount.style.color = len > 450 ? 'var(--accent-amber)' : 'var(--text-muted)';
});
chatTextarea.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSubmit(); }
});
sendBtn.addEventListener('click', handleSubmit);
$('lang-es').addEventListener('click', () => { applyLang('es'); refreshConfigLabels(); });
$('lang-en').addEventListener('click', () => { applyLang('en'); refreshConfigLabels(); });

document.querySelectorAll('.suggestion-chip').forEach((chip) => {
  chip.addEventListener('click', () => {
    chatTextarea.value = chip.dataset[lang === 'es' ? 'promptEs' : 'promptEn'] || chip.dataset.promptEn;
    chatTextarea.dispatchEvent(new Event('input'));
    chatTextarea.focus();
    handleSubmit();
  });
});

$('btn-clear').addEventListener('click', () => {
  state.controller?.abort(); state.controller = null; state.isGenerating = false; state.a2ui = [];
  destroyA2UICharts();
  sendBtn.disabled = false; progressBar.style.display = 'none'; previewIframe.srcdoc = '';
  state.generatedHTML = ''; state.agentMessage = ''; state.toolCalls = []; state.lastSummary = '';
  activeDataset = null; refreshDatasetChip();
  try { localStorage.removeItem(SESSION_KEY); } catch (e) {}
  welcomeState.style.display = 'flex'; generatedWrapper.classList.remove('visible');
  agentBubble.style.display = 'none'; previewContainer.style.display = 'none'; agentBubbleText.textContent = '';
  codeOutput.innerHTML = '<code style="color:var(--text-muted); font-size:12px;">// Generated code will appear here...</code>';
  codeBadge.style.display = 'none'; btnCopyCode.style.display = 'none'; a2uiBadge.style.display = 'none';
  toolFeed.innerHTML = '<div style="text-align:center; padding:30px 16px; color:var(--text-muted); font-size:12px;">' + t('tool_empty') + '</div>';
  a2uiFeed.innerHTML = '<div id="a2ui-empty" style="text-align:center; padding:60px 20px; color:var(--text-muted); font-size:13px;">' + t('a2ui_empty') + '</div>';
  setStatus(t('ready'), ''); chatTextarea.value = ''; charCount.textContent = '0 / 500';
  showToast(t('session_cleared'), 'info');
});

$('btn-export').addEventListener('click', (e) => {
  e.preventDefault();
  if (!state.generatedHTML) { showToast(t('no_export'), 'error'); return; }
  const blob = new Blob([state.generatedHTML], { type: 'text/html' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = 'glintmesh-interface-' + Date.now() + '.html'; a.click();
  URL.revokeObjectURL(url); showToast(t('exported'), 'success');
});

// ─── Tools drawer: list connected MCPs, not just count ──────────────────────
const drawer = $('tools-drawer'), overlay = $('tools-overlay');
function openTools() { drawer.classList.add('open'); overlay.classList.add('open'); loadTools(); }
function closeTools() { drawer.classList.remove('open'); overlay.classList.remove('open'); }
$('btn-tools').addEventListener('click', openTools);
$('btn-close-tools').addEventListener('click', closeTools);
overlay.addEventListener('click', closeTools);

async function loadTools() {
  const list = $('tools-list');
  list.innerHTML = '<div style="font-size:12px;color:var(--text-secondary);padding:8px;">Loading…</div>';
  try {
    const [healthRes, toolsRes] = await Promise.all([fetch('/health'), fetch('/api/tools')]);
    const health = await healthRes.json().catch(() => ({}));
    const data = await toolsRes.json().catch(() => ({}));
    if (!toolsRes.ok) throw new Error('unavailable');
    const server = health.mcp_server || 'finflow-financial-tools';
    const protocol = health.protocol || 'A2UI over MCP';
    if (!data.enabled) {
      list.innerHTML = '<div class="mcp-tool"><div class="mcp-name"><span class="mcp-dot off"></span>' + server + '</div>'
        + '<div class="mcp-desc">' + t('mcp_disabled') + ' (' + protocol + ')</div></div>';
      return;
    }
    const tools = data.tools || [];
    const groups = data.servers && data.servers.length
      ? data.servers
      : [{ name: server, label: server, tools }];
    let html = '';
    groups.forEach((g) => {
      const gtools = g.tools || [];
      html += '<div class="mcp-server-row"><i class="bi bi-hdd-network"></i>' + escapeHtml(g.label || g.name) + ' &bull; ' + gtools.length + '</div>';
      html += gtools.map((tl) => '<div class="mcp-tool"><div class="mcp-name"><span class="mcp-dot"></span>' + escapeHtml(tl.name) + '</div>'
        + '<div class="mcp-desc">' + escapeHtml(tl.description || '') + '</div>'
        + '<details><summary>schema</summary><pre>' + escapeHtml(JSON.stringify(tl.parameters || {}, null, 2)) + '</pre></details></div>').join('');
    });
    list.innerHTML = html || '<div style="font-size:12px;">No tools</div>';
  } catch (e) { showToast(t('mcp_error'), 'error'); list.innerHTML = '<div style="font-size:12px;color:var(--accent-red);">MCP unreachable</div>'; }
}
function escapeHtml(s) { return String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])); }

// ─── User datasets ──────────────────────────────────────────────────────────
let activeDataset = null;
const dataModal = $('data-modal'), dataOverlay = $('data-overlay');
function openData() { dataModal.style.display = 'block'; dataOverlay.style.display = 'block'; loadDatasets(); }
function closeData() { dataModal.style.display = 'none'; dataOverlay.style.display = 'none'; }
$('btn-data').addEventListener('click', openData);
$('btn-close-data').addEventListener('click', closeData);
dataOverlay.addEventListener('click', closeData);

function refreshDatasetChip() {
  const chip = $('dataset-chip');
  if (activeDataset) {
    chip.style.display = 'flex';
    $('dataset-chip-name').textContent = t('using') + ': ' + activeDataset.name;
  } else chip.style.display = 'none';
}
$('dataset-chip-x').addEventListener('click', () => { activeDataset = null; refreshDatasetChip(); });

async function loadDatasets() {
  const list = $('data-list');
  list.innerHTML = '<div style="font-size:12px;color:var(--text-secondary);">…</div>';
  try {
    const res = await fetch('/api/datasets');
    const data = await res.json();
    const items = data.datasets || [];
    if (!items.length) { list.innerHTML = '<div style="font-size:12px;color:var(--text-muted);">' + t('no_datasets') + '</div>'; return; }
    list.innerHTML = items.map((d) => '<div class="mcp-tool"><div class="mcp-name"><span class="mcp-dot' + (activeDataset && activeDataset.id === d.id ? '' : ' off') + '"></span>' + escapeHtml(d.name) + '</div>'
      + '<div class="mcp-desc">' + d.n_rows + ' ' + t('rows') + ' · ' + d.columns.length + ' cols</div>'
      + '<button class="btn-glass btn-sm" data-ds-use="' + escapeHtml(d.id) + '" style="margin-top:8px;"><i class="bi bi-check"></i> ' + t('use') + '</button></div>').join('');
    list.querySelectorAll('[data-ds-use]').forEach((btn) => btn.addEventListener('click', () => {
      const found = items.find((d) => d.id === btn.dataset.dsUse);
      if (found) { activeDataset = found; refreshDatasetChip(); loadDatasets(); }
    }));
  } catch (e) { list.innerHTML = '<div style="font-size:12px;color:var(--accent-red);">MCP unreachable</div>'; }
}

$('btn-upload').addEventListener('click', async () => {
  const input = $('data-file');
  if (!input.files.length) return;
  const form = new FormData();
  form.append('file', input.files[0]);
  try {
    const res = await fetch('/api/datasets', { method: 'POST', body: form });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'upload failed');
    activeDataset = { id: data.id, name: data.name };
    refreshDatasetChip();
    addDatasetPreviewCard(data);
    input.value = '';
    loadDatasets();
    showToast(t('uploaded_ok'), 'success');
  } catch (e) { showToast(typeof e.message === 'string' ? e.message : t('upload_fail'), 'error'); }
});

function addDatasetPreviewCard(ds) {
  const empty = $('a2ui-empty'); if (empty) empty.remove();
  const cols = (ds.columns || []).slice(0, 6);
  const head = cols.map((c) => '<th>' + escapeHtml(c) + '</th>').join('');
  const rows = (ds.sample || []).slice(0, 5).map((r) => '<tr>' + cols.map((c) => '<td>' + escapeHtml(r[c] ?? '') + '</td>').join('') + '</tr>').join('');
  const card = document.createElement('div');
  card.className = 'a2ui-card';
  card.innerHTML = '<div class="a2ui-head"><span class="proto-badge">A2UI</span><span class="proto-badge">USER DATA</span><span>' + escapeHtml(ds.name || '') + '</span><span style="margin-left:auto;font-size:10px;color:var(--text-muted);">' + ds.n_rows + ' ' + t('rows') + '</span></div>'
    + '<div class="a2ui-body"><table class="a2ui-table"><thead><tr>' + head + '</tr></thead><tbody>' + rows + '</tbody></table></div>';
  a2uiFeed.appendChild(card);
  state.a2ui.push('user_dataset');
  a2uiBadge.style.display = 'inline-flex'; a2uiBadge.textContent = state.a2ui.length;
}

$('btn-reload-preview').addEventListener('click', () => { if (state.generatedHTML) renderPreview(state.generatedHTML); });
$('btn-fullscreen').addEventListener('click', () => {
  if (!state.generatedHTML) return;
  const frame = document.createElement('iframe');
  frame.setAttribute('sandbox', 'allow-scripts'); frame.style.cssText = 'border:0;width:100%;height:100vh'; frame.srcdoc = state.generatedHTML;
  const url = URL.createObjectURL(new Blob(['<!doctype html><html><head><title>GlintMesh Preview</title></head><body style="margin:0">' + frame.outerHTML + '</body></html>'], { type: 'text/html' }));
  window.open(url, '_blank', 'noopener,noreferrer'); setTimeout(() => URL.revokeObjectURL(url), 60000);
});
btnCopyCode.addEventListener('click', async () => {
  if (!state.generatedHTML) return;
  await navigator.clipboard.writeText(state.generatedHTML); showToast(t('copied'), 'success');
});

// ─── Submit ─────────────────────────────────────────────────────────────────
async function handleSubmit() {
  const message = chatTextarea.value.trim();
  if (!message || state.isGenerating) return;
  if (message.length > 500) return;
  const controller = new AbortController();
  state.controller = controller; state.isGenerating = true;
  state.generatedHTML = ''; state.agentMessage = ''; state.toolCalls = []; state.a2ui = [];
  destroyA2UICharts();
  chatTextarea.value = ''; chatTextarea.style.height = 'auto'; charCount.textContent = '0 / 500';
  sendBtn.disabled = true; progressBar.style.display = 'flex';
  welcomeState.style.display = 'none'; generatedWrapper.classList.add('visible');
  agentBubble.style.display = 'flex'; agentBubbleText.textContent = t('waiting');
  toolFeed.innerHTML = ''; codeOutput.textContent = ''; codeOutput.classList.add('streaming');
  codeBadge.style.display = 'none'; btnCopyCode.style.display = 'none'; a2uiBadge.style.display = 'none';
  a2uiFeed.innerHTML = ''; previewContainer.style.display = 'none'; previewIframe.srcdoc = '';
  setStatus(t('analyzing'), 'active');

  let fullText = '', completed = false;
  try {
    const payload = { message, lang };
    if (state.lastSummary) payload.context = state.lastSummary.slice(0, 800);
    if (activeDataset) payload.dataset_id = activeDataset.id;
    const response = await fetch('/api/generate', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload), signal: controller.signal,
    });
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(typeof body.detail === 'string' ? body.detail : 'request failed');
    }
    for await (const event of readSSE(response.body)) {
      if (controller.signal.aborted) return;
      if (event.type === 'error') throw new Error(event.content);
      handleSSEEvent(event);
      if (event.type === 'text_chunk') {
        fullText += event.content; codeOutput.textContent = fullText;
        const htmlStart = fullText.indexOf('```html');
        agentBubbleText.textContent = htmlStart === -1 ? fullText : (fullText.slice(0, htmlStart).trim() || t('generating'));
      } else if (event.type === 'done') { completed = true; finalize(fullText); break; }
    }
    if (!completed && !controller.signal.aborted) throw new Error('interrupted');
  } catch (error) {
    if (!controller.signal.aborted) {
      setStatus(t('failed'), 'error'); agentBubbleText.textContent = error.message; showToast(error.message, 'error');
      if (!chatTextarea.value) { chatTextarea.value = message; chatTextarea.dispatchEvent(new Event('input')); }
    }
  } finally {
    codeOutput.classList.remove('streaming');
    if (state.controller === controller) { state.controller = null; state.isGenerating = false; sendBtn.disabled = false; progressBar.style.display = 'none'; }
  }
}

/* ─── Real A2UI: native components rendered from MCP data (no model code runs) ─── */
function esc(v) {
  return String(v ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}
function fmtMoney(v) {
  const n = Number(v);
  return Number.isFinite(n) ? '$' + n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : esc(v);
}
function fmtNum(v) {
  const n = Number(v);
  return Number.isFinite(n) ? n.toLocaleString('en-US') : esc(v);
}
function deltaBadge(pct) {
  const n = Number(pct);
  const up = !(n < 0);
  return '<span class="a2ui-delta ' + (up ? 'up' : 'down') + '">' + (up ? '▲' : '▼') + ' ' + esc(Math.abs(Number.isFinite(n) ? n : 0).toFixed(2)) + '%</span>';
}
function destroyA2UICharts() {
  (state.charts || []).forEach((c) => { try { c.destroy(); } catch (e) {} });
  state.charts = [];
}

function a2uiKind(tool) {
  if (/historical|history|prices/i.test(tool)) return 'chart';
  if (/compound/i.test(tool)) return 'chart';
  if (/portfolio|forex|_fx|indices|news/i.test(tool)) return 'table';
  if (/credit/i.test(tool)) return 'gauge';
  return 'card';
}

function a2uiQuote(d) {
  return '<div class="a2ui-hero"><div><div class="a2ui-sym">' + esc(d.symbol) + '</div>'
    + '<div class="a2ui-price">' + fmtMoney(d.price) + ' ' + deltaBadge(d.change_percent) + '</div></div></div>'
    + '<div class="a2ui-grid">'
    + '<div class="a2ui-metric"><div class="a2ui-mlabel">Change</div><div class="a2ui-mval">' + fmtMoney(d.change) + '</div></div>'
    + '<div class="a2ui-metric"><div class="a2ui-mlabel">Volume</div><div class="a2ui-mval">' + fmtNum(d.volume) + '</div></div>'
    + '<div class="a2ui-metric"><div class="a2ui-mlabel">Mkt Cap</div><div class="a2ui-mval">' + esc(d.market_cap) + '</div></div>'
    + '<div class="a2ui-metric"><div class="a2ui-mlabel">52w Range</div><div class="a2ui-mval">' + fmtMoney(d.low_52w) + ' – ' + fmtMoney(d.high_52w) + '</div></div>'
    + '</div>';
}

function a2uiPortfolio(d) {
  const rows = (d.positions || []).map((p) => '<tr><td><strong>' + esc(p.symbol) + '</strong></td><td>' + fmtNum(p.shares) + '</td>'
    + '<td>' + fmtMoney(p.current_price) + '</td><td>' + fmtMoney(p.market_value) + '</td><td>' + deltaBadge(p.gain_percent) + '</td></tr>').join('');
  return '<div class="a2ui-grid">'
    + '<div class="a2ui-metric"><div class="a2ui-mlabel">Total Value</div><div class="a2ui-mval">' + fmtMoney(d.total_market_value) + '</div></div>'
    + '<div class="a2ui-metric"><div class="a2ui-mlabel">Unrealized Gain</div><div class="a2ui-mval">' + fmtMoney(d.total_unrealized_gain) + '</div></div>'
    + '<div class="a2ui-metric"><div class="a2ui-mlabel">Return</div><div class="a2ui-mval">' + deltaBadge(d.total_return_percent) + '</div></div>'
    + '</div><table class="a2ui-table"><thead><tr><th>Symbol</th><th>Shares</th><th>Price</th><th>Value</th><th>Gain</th></tr></thead><tbody>' + rows + '</tbody></table>';
}

function a2uiIndices(d) {
  const tiles = Object.entries(d || {}).filter(([, v]) => v && typeof v === 'object').map(([k, v]) => '<div class="a2ui-metric"><div class="a2ui-mlabel">' + esc(v.name || k) + '</div>'
    + '<div class="a2ui-mval">' + fmtNum(v.value) + '</div>' + deltaBadge(v.change_percent) + '</div>').join('');
  return '<div class="a2ui-grid">' + tiles + '</div>';
}

function a2uiHistory(d, cid) {
  return '<div class="a2ui-head-row"><strong>' + esc(d.symbol) + '</strong><span class="a2ui-mlabel">' + esc(d.period_days) + 'd</span>'
    + deltaBadge(d.total_return) + '</div><div class="a2ui-canvas-wrap"><canvas id="' + cid + '"></canvas></div>';
}

function a2uiNews(d) {
  const items = Array.isArray(d) ? d : (d.items || d.articles || []);
  const rows = items.map((n) => {
    const s = String(n.sentiment || 'neutral').toLowerCase();
    const cls = s.includes('pos') ? 'pos' : (s.includes('neg') ? 'neg' : 'neu');
    return '<div class="a2ui-news"><div><div class="a2ui-news-title">' + esc(n.title) + '</div>'
      + '<div class="a2ui-mlabel">' + esc(n.source) + ' · ' + esc(n.published_at || '') + '</div></div>'
      + '<span class="a2ui-sent ' + cls + '">' + esc(n.sentiment || 'neutral') + '</span></div>';
  }).join('');
  return rows || '<div class="a2ui-mlabel">No headlines</div>';
}

function a2uiCredit(d) {
  const score = Math.max(0, Math.min(100, Number(d.risk_score) || 0));
  const rec = String(d.recommendation || '');
  const rc = rec.includes('APPROVE') && !rec.includes('CONDITIONAL') ? 'pos' : (rec.includes('DECLINE') ? 'neg' : 'neu');
  const factors = (d.risk_factors || []).map((f) => '<li><strong>' + esc(f.factor) + '</strong> <span class="a2ui-mlabel">[' + esc(f.impact) + ']</span> — ' + esc(f.note) + '</li>').join('');
  return '<div class="a2ui-grid">'
    + '<div class="a2ui-metric"><div class="a2ui-mlabel">Risk Score</div><div class="a2ui-mval">' + esc(score) + '/100</div></div>'
    + '<div class="a2ui-metric"><div class="a2ui-mlabel">Decision</div><div><span class="a2ui-sent ' + rc + '">' + esc(rec.replace(/_/g, ' ')) + '</span></div></div>'
    + '<div class="a2ui-metric"><div class="a2ui-mlabel">Sugg. Rate</div><div class="a2ui-mval">' + esc(d.suggested_interest_rate) + '%</div></div>'
    + '</div><div class="a2ui-riskbar"><div style="width:' + score + '%"></div></div>'
    + (factors ? '<ul class="a2ui-factors">' + factors + '</ul>' : '<div class="a2ui-mlabel">No risk factors flagged</div>');
}

function a2uiCompound(d, cid) {
  const yrs = d.yearly_breakdown || [];
  const last = yrs.length ? yrs[yrs.length - 1] : null;
  return '<div class="a2ui-grid">'
    + '<div class="a2ui-metric"><div class="a2ui-mlabel">Final Balance</div><div class="a2ui-mval">' + fmtMoney(d.final_balance) + '</div></div>'
    + '<div class="a2ui-metric"><div class="a2ui-mlabel">Contributed</div><div class="a2ui-mval">' + fmtMoney(d.total_contributions) + '</div></div>'
    + '<div class="a2ui-metric"><div class="a2ui-mlabel">Interest</div><div class="a2ui-mval">' + fmtMoney(d.total_interest_earned) + '</div></div>'
    + '</div><div class="a2ui-canvas-wrap"><canvas id="' + cid + '"></canvas></div>'
    + (last ? '<div class="a2ui-mlabel">ROI ' + esc(d.return_on_investment) + '% over ' + yrs.length + ' years</div>' : '');
}

function a2uiForex(d) {
  const rows = Object.entries(d.rates || {}).map(([c, r]) => '<tr><td><strong>' + esc(c) + '</strong></td><td>' + esc(r) + '</td></tr>').join('');
  return '<div class="a2ui-head-row"><span class="a2ui-mlabel">Base</span><strong>' + esc(d.base) + '</strong></div>'
    + '<table class="a2ui-table"><thead><tr><th>Currency</th><th>Rate</th></tr></thead><tbody>' + rows + '</tbody></table>';
}

function renderA2UIBody(tool, data, cid) {
  try {
    if (!data || typeof data !== 'object') return '<pre class="a2ui-raw">' + esc(JSON.stringify(data)) + '</pre>';
    if (tool === 'get_stock_quote' || tool === 'get_live_quote') return a2uiQuote(data);
    if (tool === 'get_portfolio_summary') return a2uiPortfolio(data);
    if (tool === 'get_market_indices' || tool === 'get_live_indices') return a2uiIndices(data);
    if (tool === 'get_historical_prices' || tool === 'get_live_history') return a2uiHistory(data, cid);
    if (tool === 'get_financial_news') return a2uiNews(data);
    if (tool === 'analyze_credit_risk') return a2uiCredit(data);
    if (tool === 'calculate_compound_interest') return a2uiCompound(data, cid);
    if (tool === 'get_forex_rates' || tool === 'get_live_fx') return a2uiForex(data);
    return '<pre class="a2ui-raw">' + esc(JSON.stringify(data, null, 2)).slice(0, 4000) + '</pre>';
  } catch (e) {
    return '<div class="a2ui-mlabel">Could not render this surface</div>';
  }
}

function mountA2UIChart(tool, data, cid) {
  if (!window.Chart) return;
  try {
    Chart.defaults.color = '#8a94a8';
    Chart.defaults.font.family = 'Inter, sans-serif';
    const el = document.getElementById(cid);
    if (!el) return;
    let cfg = null;
    if (tool === 'get_historical_prices' || tool === 'get_live_history') {
      const pts = data.data || [];
      const step = Math.max(1, Math.ceil(pts.length / 14));
      cfg = { type: 'line', data: { labels: pts.filter((_, i) => i % step === 0).map((p) => p.date), datasets: [{ data: pts.filter((_, i) => i % step === 0).map((p) => p.close), borderColor: '#34d399', backgroundColor: 'rgba(52,211,153,.15)', fill: true, tension: .3, pointRadius: 0 }] }, options: { plugins: { legend: { display: false } }, scales: { x: { grid: { color: 'rgba(255,255,255,.05)' } }, y: { grid: { color: 'rgba(255,255,255,.05)' } } } } };
    } else if (tool === 'calculate_compound_interest') {
      const yrs = data.yearly_breakdown || [];
      cfg = { type: 'line', data: { labels: yrs.map((y) => 'Y' + y.year), datasets: [{ label: 'Balance', data: yrs.map((y) => y.balance), borderColor: '#34d399', backgroundColor: 'rgba(52,211,153,.15)', fill: true, tension: .3 }, { label: 'Contributions', data: yrs.map((y) => y.contributions), borderColor: '#64748b', borderDash: [5, 4], fill: false, tension: .3, pointRadius: 0 }] }, options: { plugins: { legend: { labels: { boxWidth: 12 } } }, scales: { x: { grid: { display: false } }, y: { grid: { color: 'rgba(255,255,255,.05)' } } } } };
    }
    if (cfg) state.charts.push(new Chart(el, cfg));
  } catch (e) {}
}

function handleSSEEvent(event) {
  switch (event.type) {
    case 'status': setStatus(event.content, 'active'); progressLabel.textContent = event.content; break;
    case 'tool_call': {
      setStatus(event.content, 'active'); progressLabel.textContent = event.content;
      const name = event.content.replace('Fetching ', '').replace('...', '');
      addToolCard(name, 'calling');
      addA2UICard(name, null, true);
      break;
    }
    case 'tool_result': {
      const cards = toolFeed.querySelectorAll('.tool-card');
      if (cards.length > 0) {
        const last = cards[cards.length - 1];
        const icon = last.querySelector('.tool-status-icon');
        if (icon) { icon.className = 'tool-status-icon ' + (event.failed ? 'error' : 'done'); icon.innerHTML = event.failed ? '<i class="bi bi-x"></i>' : '<i class="bi bi-check"></i>'; }
        const dataDiv = last.querySelector('.tool-data');
        if (dataDiv && event.data) dataDiv.textContent = JSON.stringify(event.data).slice(0, 140) + '...';
      }
      updateA2UICard(event.tool, event.data, event.failed);
      break;
    }
    case 'error': setStatus(event.content, 'error'); agentBubbleText.textContent = 'Error: ' + event.content; showToast(event.content, 'error'); break;
  }
}

function addToolCard(name, status = 'calling') {
  const card = document.createElement('div'); card.className = 'tool-card';
  const iconContent = status === 'calling' ? '<i class="bi bi-arrow-repeat" style="animation:spin 1s linear infinite;"></i>' : '<i class="bi bi-check"></i>';
  card.innerHTML = '<div class="tool-name"><div class="tool-status-icon ' + status + '">' + iconContent + '</div><span></span><span class="proto-badge mcp">MCP</span></div><div class="tool-data">Calling MCP tool...</div>';
  card.querySelector('.tool-name span').textContent = name.replace(/_/g, ' ');
  if (!document.getElementById('spin-style')) {
    const s = document.createElement('style'); s.id = 'spin-style';
    s.textContent = '@keyframes spin { from{transform:rotate(0)} to{transform:rotate(360deg)} }';
    document.head.appendChild(s);
  }
  toolFeed.appendChild(card); toolFeed.scrollTop = toolFeed.scrollHeight;
  return card;
}

function addA2UICard(tool, data, pending) {
  const empty = $('a2ui-empty'); if (empty) empty.remove();
  const card = document.createElement('div'); card.className = 'a2ui-card'; card.dataset.tool = tool;
  const kind = a2uiKind(tool);
  const cid = 'a2ui-chart-' + Date.now() + '-' + state.a2ui.length;
  card.dataset.cid = cid;
  card.innerHTML = '<div class="a2ui-head"><span class="proto-badge">A2UI</span><span class="proto-badge mcp">MCP</span><span></span><span style="margin-left:auto;font-size:10px;color:var(--text-muted);"></span></div><div class="a2ui-body"><div class="skeleton" style="height:64px;"></div></div>';
  card.querySelector('.a2ui-head span:nth-child(3)').textContent = tool;
  card.querySelector('.a2ui-head span:last-child').textContent = kind;
  if (!pending) fillA2UICard(card, tool, data, false);
  else card.dataset.pending = '1';
  a2uiFeed.appendChild(card);
  state.a2ui.push(tool);
  a2uiBadge.style.display = 'inline-flex'; a2uiBadge.textContent = state.a2ui.length;
}
function fillA2UICard(card, tool, data, failed) {
  const body = card.querySelector('.a2ui-body');
  if (failed) {
    body.innerHTML = '<div class="a2ui-mlabel">MCP tool failed</div>';
    card.style.borderLeftColor = 'var(--accent-red)';
    return;
  }
  body.innerHTML = renderA2UIBody(tool, data, card.dataset.cid);
  card.style.borderLeftColor = 'var(--accent-green)';
  const live = data && data.source === 'live';
  card.querySelector('.a2ui-head').insertAdjacentHTML('beforeend',
    live ? '<span class="proto-badge live">LIVE</span>' : '<span class="proto-badge mcp">SIM</span>');
  mountA2UIChart(tool, data, card.dataset.cid);
}
function updateA2UICard(tool, data, failed) {
  const cards = a2uiFeed.querySelectorAll('.a2ui-card');
  for (let i = cards.length - 1; i >= 0; i--) {
    if (cards[i].dataset.tool === tool && cards[i].dataset.pending === '1') {
      delete cards[i].dataset.pending;
      fillA2UICard(cards[i], tool, data, failed);
      return;
    }
  }
}

function finalize(fullText) {
  const htmlStart = fullText.indexOf('```html');
  if (htmlStart !== -1) {
    const preText = fullText.slice(0, htmlStart).trim();
    if (preText) agentBubbleText.textContent = preText; else agentBubble.style.display = 'none';
    const extractStart = htmlStart + 7;
    const htmlEnd = fullText.lastIndexOf('```');
    state.generatedHTML = (htmlEnd > extractStart ? fullText.slice(extractStart, htmlEnd) : fullText.slice(extractStart)).trim();
    if (state.generatedHTML) {
      renderPreview(state.generatedHTML); codeBadge.style.display = 'inline-flex'; btnCopyCode.style.display = 'flex';
      showToast(t('done_ok'), 'success');
    }
  } else { agentBubbleText.textContent = fullText; showToast(t('resp_ok'), 'info'); }
  if (state.generatedHTML) {
    try { codeOutput.innerHTML = hljs.highlight(state.generatedHTML, { language: 'html' }).value; }
    catch (e) { codeOutput.textContent = state.generatedHTML; }
  }
  setStatus(state.generatedHTML ? t('done_ok') : t('resp_ok'), 'success');
  progressBar.style.display = 'none';
  state.lastSummary = (agentBubble.style.display === 'none' ? fullText : agentBubbleText.textContent).slice(0, 800);
  saveSession();
}

function saveSession() {
  try {
    if (!state.generatedHTML && !state.agentMessage) return;
    localStorage.setItem(SESSION_KEY, JSON.stringify({
      lang, agentMessage: agentBubbleText.textContent || '', generatedHTML: state.generatedHTML || '',
      dataset: activeDataset, ts: Date.now(),
    }));
  } catch (e) {}
}

function restoreSession() {
  let saved = null;
  try { saved = JSON.parse(localStorage.getItem(SESSION_KEY) || 'null'); } catch (e) {}
  if (!saved || (!saved.generatedHTML && !saved.agentMessage)) return;
  if (saved.lang && I18N[saved.lang]) applyLang(saved.lang);
  welcomeState.style.display = 'none';
  generatedWrapper.classList.add('visible');
  state.generatedHTML = saved.generatedHTML || '';
  if (saved.dataset && saved.dataset.id) { activeDataset = saved.dataset; refreshDatasetChip(); }
  state.lastSummary = (saved.agentMessage || '').slice(0, 800);
  if (saved.agentMessage) { agentBubble.style.display = 'flex'; agentBubbleText.textContent = saved.agentMessage; }
  if (state.generatedHTML) {
    renderPreview(state.generatedHTML);
    try { codeOutput.innerHTML = hljs.highlight(state.generatedHTML, { language: 'html' }).value; }
    catch (e) { codeOutput.textContent = state.generatedHTML; }
    codeBadge.style.display = 'inline-flex'; btnCopyCode.style.display = 'flex';
  }
  setStatus(t('resp_ok'), 'success');
}

function renderPreview(html) {
  previewContainer.style.display = 'block';
  previewIframe.srcdoc = html;
  previewIframe.onload = () => {
    try {
      const h = Math.max(previewIframe.contentDocument.body.scrollHeight, 500);
      previewIframe.style.height = Math.min(h, 800) + 'px';
    } catch (e) { previewIframe.style.height = '600px'; }
  };
}

function setStatus(text, type = '') { statusText.textContent = text; statusText.className = type ? 'active ' + type : ''; }
function showToast(message, type = 'info') {
  const container = $('toast-container');
  const icons = { success: 'bi-check-circle-fill', error: 'bi-x-circle-fill', info: 'bi-info-circle-fill' };
  const colors = { success: 'var(--accent-green)', error: 'var(--accent-red)', info: 'var(--accent-cyan)' };
  const el = document.createElement('div'); el.className = 'toast-item ' + type;
  el.innerHTML = '<i class="bi ' + (icons[type] || icons.info) + '" style="color:' + (colors[type] || colors.info) + '; font-size:16px;"></i><span></span>';
  el.querySelector('span').textContent = message; container.appendChild(el);
  setTimeout(() => { el.style.opacity = '0'; el.style.transition = 'all .3s ease'; setTimeout(() => el.remove(), 300); }, 3500);
}

let cachedHealth = null;
async function loadConfiguration() {
  try {
    const res = await fetch('/health');
    if (!res.ok) throw new Error('down');
    cachedHealth = await res.json();
    refreshConfigLabels();
    if (!cachedHealth.gemini_configured && !state.isGenerating) setStatus('GEMINI_API_KEY missing', 'error');
  } catch { if (!state.isGenerating) setStatus('Start the Python server', 'error'); }
}
function refreshConfigLabels() {
  if (!cachedHealth) return;
  $('model-description').textContent = 'Model: ' + cachedHealth.model + ' • A2UI over MCP • v' + (cachedHealth.version || '2.0.0');
  const mcpEl = $('mcp-description');
  if (mcpEl) mcpEl.textContent = cachedHealth.mcp_enabled ? t('f3d') : t('f3d_off');
  const v = $('version-label');
  if (v) v.textContent = 'GlintMesh • v' + (cachedHealth.version || '2.0.0');
}
applyLang(lang);
restoreSession();
loadConfiguration();
