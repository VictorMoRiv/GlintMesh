import { readSSE } from './sse.mjs';

// ─── i18n ─────────────────────────────────────────────────────────────────
const I18N = {
  es: {
    subtitle: 'A2UI over MCP Interface Mesh', tools: 'Tools', clear: 'Limpiar', export: 'Exportar',
    preview: 'Vista previa', a2ui: 'Superficie A2UI', code: 'Código', agent_status: 'Estado del agente',
    ready: 'Listo para generar interfaces', tool_empty: 'Las llamadas MCP aparecerán aquí mientras trabaja el agente',
    quick_prompts: 'Prompts rápidos', add_prompt: 'Nuevo prompt rápido', edit_prompt: 'Editar prompt', prompt_need: 'Escribe al menos un texto (ES o EN)', p1: 'Dashboard de portafolio', p2: 'Monitor de índices', p3: 'Analizador de riesgo',
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
    refresh_data: 'Actualizar datos', auto_60: 'Auto 60s', refreshed_ok: 'Datos actualizados sin gastar cuota', refresh_fail: 'No se pudo actualizar',
    link_copied: 'Link copiado al portapapeles', share_fail: 'No se pudo crear el link',
    settings: 'Configuración', options_menu: 'Opciones', style_title: 'Estilo de interfaces', style_sub: 'Describe cómo quieres que se vean todas tus interfaces. Vacío = minimalista empresarial (default).',
    style_ph: 'Ej.: modo oscuro con acentos verdes y números grandes...', save: 'Guardar', reset_default: 'Restablecer',
    s_min: 'Minimalista empresarial', s_glass: 'Glassmorphism', s_dark: 'Oscuro simple', s_corp: 'Corporativo clásico', s_custom: 'Personalizado', style_saved: 'Estilo guardado',
    model_label: 'Modelo', creativity: 'Creatividad', mode_label: 'Modo', mode_full: 'Interfaz completa', mode_data: 'Solo datos',
    data_mgmt: 'Datos guardados', saved_session: 'Sesión guardada', session_empty: 'Sin sesión guardada', delete: 'Borrar',
    app_look: 'Apariencia de la app', ui_dark: 'Oscuro', ui_light: 'Claro',
    css_ph: 'Un solo prompt de diseño: pega un snippet o escribe tu CSS...',
    css_hint: 'Se aplica en vivo solo a esta app. Nunca afecta las interfaces generadas.',
    reset_look: 'Restablecer apariencia', snip_blue: 'Header azul', snip_round: 'Todo redondeado', snip_compact: 'Compacto',
    del_all: 'Borrar todo', keep_imp: 'Conservar importantes', del_everything: 'Borrar todo', cancel: 'Cancelar',
    wipe_title: '¿Borrar datos guardados?', wipe_will_delete: 'Se borrará:', w_session: 'sesión', w_datasets: 'datasets', w_prefs: 'preferencias',
    imp_tag: 'importante', wiped_ok: 'Datos eliminados',
    session_cleared: 'Sesión limpiada', no_export: 'Aún no hay interfaz para exportar', exported: 'Interfaz exportada',
    copied: 'Código copiado', mcp_disabled: 'MCP desactivado. Gemini funciona sin herramientas.', mcp_error: 'No se pudieron obtener herramientas',
    waiting: 'Esperando a Gemini...', generating: 'Generando interfaz...', analyzing: 'Analizando solicitud...',
    done_ok: 'Interfaz generada correctamente', resp_ok: 'Respuesta recibida', failed: 'Generación fallida',
  },
  en: {
    subtitle: 'A2UI over MCP Interface Mesh', tools: 'Tools', clear: 'Clear', export: 'Export',
    preview: 'Preview', a2ui: 'A2UI Surface', code: 'Code', agent_status: 'Agent Status',
    ready: 'Ready to generate interfaces', tool_empty: 'MCP tool calls will appear here as the agent works',
    quick_prompts: 'Quick Prompts', add_prompt: 'New quick prompt', edit_prompt: 'Edit prompt', prompt_need: 'Type at least one text (ES or EN)', p1: 'Portfolio dashboard', p2: 'Market indices monitor', p3: 'Credit risk analyzer',
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
    refresh_data: 'Refresh data', auto_60: 'Auto 60s', refreshed_ok: 'Data refreshed with no quota used', refresh_fail: 'Could not refresh',
    link_copied: 'Link copied to clipboard', share_fail: 'Could not create link',
    settings: 'Settings', options_menu: 'Options', style_title: 'Interface style', style_sub: 'Describe how you want all your interfaces to look. Empty means minimalist enterprise (default).',
    style_ph: 'E.g.: dark mode with green accents and big numbers...', save: 'Save', reset_default: 'Reset',
    s_min: 'Minimalist enterprise', s_glass: 'Glassmorphism', s_dark: 'Simple dark', s_corp: 'Classic corporate', s_custom: 'Custom', style_saved: 'Style saved',
    model_label: 'Model', creativity: 'Creativity', mode_label: 'Mode', mode_full: 'Full interface', mode_data: 'Data only',
    data_mgmt: 'Saved data', saved_session: 'Saved session', session_empty: 'No saved session', delete: 'Delete',
    app_look: 'App appearance', ui_dark: 'Dark', ui_light: 'Light',
    css_ph: 'One design prompt: paste a snippet or write your CSS...',
    css_hint: 'Applies live to this app only. Never affects generated interfaces.',
    reset_look: 'Reset look', snip_blue: 'Blue header', snip_round: 'All rounded', snip_compact: 'Compact',
    del_all: 'Delete all', keep_imp: 'Keep important', del_everything: 'Delete everything', cancel: 'Cancel',
    wipe_title: 'Delete saved data?', wipe_will_delete: 'Will delete:', w_session: 'session', w_datasets: 'datasets', w_prefs: 'preferences',
    imp_tag: 'important', wiped_ok: 'Data deleted',
    session_cleared: 'Session cleared', no_export: 'No interface to export yet', exported: 'Interface exported',
    copied: 'Code copied to clipboard', mcp_disabled: 'MCP is disabled. Gemini works without tools.', mcp_error: 'Could not fetch tools',
    waiting: 'Waiting for Gemini...', generating: 'Generating interface...', analyzing: 'Analyzing request...',
    done_ok: 'Interface generated successfully', resp_ok: 'Response received', failed: 'Generation failed',
  },
};
let lang = localStorage.getItem('glintmesh-lang') || 'es';
if (!I18N[lang]) lang = 'es';
Object.assign(I18N.es, { retry: 'Reintentar', compose: 'Combinar', composed_ok: 'Dashboard combinado creado', need_2: 'Necesitas al menos 2 superficies A2UI para combinar', signin: 'Entrar', signup: 'Registro', signin_title: 'Iniciar sesión', session_saved: 'Sesión guardada mientras hay login', guest_note: 'Modo invitado: tu info se pierde al salir del chat. Inicia sesión para guardarla.', auth_short: 'Usuario 3+ letras y clave 4+ caracteres', auth_reg_fail: 'No se pudo registrar (¿usuario tomado?)', auth_enter_login: 'Registrado. Ahora pulsa Entrar', auth_empty: 'Escribe usuario y clave', auth_bad: 'Usuario o clave incorrectos', auth_login_fail: 'No se pudo entrar', auth_photo_ok: 'Foto actualizada', auth_photo_fail: 'No se pudo subir la foto (máx 300 KB)', auth_avatar_big: 'Foto muy pesada (máx 300 KB)', voice_on: 'Escuchando... habla ahora', voice_off: 'Voz no disponible en este navegador', voice_mic_denied: 'Permite el micrófono en el navegador y reintenta', voice_no_mic: 'No se encontró micrófono', voice_no_speech: 'No te escuché, habla más fuerte y reintenta', voice_network: 'Voz necesita internet (Chrome/Edge)', voice_lang: 'Idioma de voz no soportado', img_many: 'Máximo 3 imágenes', img_big: 'Imagen muy pesada (máx 1.5 MB)' });
Object.assign(I18N.en, { retry: 'Retry', compose: 'Compose dashboard', composed_ok: 'Composed dashboard created', need_2: 'Need at least 2 A2UI surfaces to compose', signin: 'Sign in', signup: 'Register', signin_title: 'Sign in', session_saved: 'Session saved while signed in', guest_note: 'Guest mode: your info is lost when you leave the chat. Sign in to keep it.', auth_short: 'User 3+ chars and password 4+ chars', auth_reg_fail: 'Could not register (name taken?)', auth_enter_login: 'Registered. Now press Sign in', auth_empty: 'Type user and password', auth_bad: 'Wrong user or password', auth_login_fail: 'Could not sign in', auth_photo_ok: 'Photo updated', auth_photo_fail: 'Could not upload photo (max 300 KB)', auth_avatar_big: 'Photo too large (max 300 KB)', voice_on: 'Listening... speak now', voice_off: 'Voice not available in this browser', voice_mic_denied: 'Allow the microphone in the browser and retry', voice_no_mic: 'No microphone found', voice_no_speech: 'Did not hear you, speak up and retry', voice_network: 'Voice needs internet (Chrome/Edge)', voice_lang: 'Voice language not supported', img_many: 'Max 3 images', img_big: 'Image too large (max 1.5 MB)' });
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
const state = { isGenerating: false, controller: null, generatedHTML: '', agentMessage: '', toolCalls: [], toolResults: {}, a2ui: [], charts: [], lastSummary: '', lastPayload: null, lastError: '' };
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

// ─── Quick prompts: editable, deletable, pinnable, addable ──────────────────
const PROMPT_KEY = 'glintmesh-prompts-v1';
const DEFAULT_PROMPTS = [
  { id: 'p1', es: "Muéstrame un dashboard de portafolio en tiempo real para acciones AAPL, MSFT, NVDA y TSLA", en: "Show me a real-time portfolio dashboard for AAPL, MSFT, NVDA and TSLA stocks", icon: 'bi-pie-chart-fill', pinned: false },
  { id: 'p2', es: "Genera un monitor de índices S&P 500, NASDAQ, Dow Jones e IPC México", en: "Generate a market indices monitor showing S&P 500, NASDAQ, Dow Jones and IPC Mexico with live data", icon: 'bi-graph-up-arrow', pinned: false },
  { id: 'p3', es: "Crea un dashboard de análisis de riesgo crediticio para una hipoteca de $250,000 con ingreso de $75,000", en: "Create a credit risk analysis dashboard for a $250,000 mortgage application with income $75,000", icon: 'bi-shield-check', pinned: false },
  { id: 'p4', es: "Construye una calculadora de interés compuesto para $10,000 a 30 años al 8% anual", en: "Build a compound interest calculator showing growth projections for $10,000 over 30 years at 8% annual rate", icon: 'bi-calculator', pinned: false },
  { id: 'p5', es: "Muéstrame un tablero de tipos de cambio con USD como base y gráfico histórico de BTC", en: "Show me a forex exchange rates dashboard with USD as base currency and historical BTC price chart", icon: 'bi-currency-exchange', pinned: false },
  { id: 'p6', es: "Genera un feed de noticias financieras con sentimiento de mercado y titulares", en: "Generate a financial news feed dashboard with market sentiment indicators and latest headlines", icon: 'bi-newspaper', pinned: false },
];
let prompts = [];
try {
  const saved = JSON.parse(localStorage.getItem(PROMPT_KEY) || 'null');
  prompts = Array.isArray(saved) && saved.length ? saved : DEFAULT_PROMPTS.map((p) => ({ ...p }));
} catch (e) { prompts = DEFAULT_PROMPTS.map((p) => ({ ...p })); }
function savePrompts() { try { localStorage.setItem(PROMPT_KEY, JSON.stringify(prompts)); } catch (e) {} }
function promptText(p) { const l = lang === 'es' ? p.es : p.en; return l || p.es || p.en || ''; }
function renderPrompts() {
  const list = $('prompt-list');
  if (!list) return;
  const sorted = [...prompts].sort((a, b) => (b.pinned ? 1 : 0) - (a.pinned ? 1 : 0));
  if (!sorted.length) {
    list.innerHTML = '<div style="font-size:12px; color:var(--text-muted); padding:6px 2px;">No prompts. Pulsa + para añadir uno.</div>';
    return;
  }
  list.innerHTML = sorted.map((p) => {
    const label = promptText(p);
    return '<div class="prompt-row" data-id="' + escapeHtml(p.id) + '">'
      + '<button class="suggestion-chip" title="' + escapeHtml(label) + '"><i class="bi ' + escapeHtml(p.icon || 'bi-lightning-charge') + '"></i><span>' + escapeHtml(label) + '</span></button>'
      + '<button class="prompt-act ' + (p.pinned ? 'pinned' : '') + '" data-act="pin" title="Pin / unpin">' + (p.pinned ? '<i class="bi bi-pin-angle-fill"></i>' : '<i class="bi bi-pin-angle"></i>') + '</button>'
      + '<button class="prompt-act" data-act="edit" title="Edit"><i class="bi bi-pencil"></i></button>'
      + '<button class="prompt-act" data-act="del" title="Delete"><i class="bi bi-x-lg"></i></button>'
      + '</div>';
  }).join('');
}
const promptListEl = $('prompt-list');
promptListEl.addEventListener('click', (e) => {
  const row = e.target.closest('.prompt-row');
  if (!row) return;
  const p = prompts.find((x) => x.id === row.dataset.id);
  if (!p) return;
  const actBtn = e.target.closest('[data-act]');
  if (actBtn) {
    const act = actBtn.dataset.act;
    if (act === 'pin') p.pinned = !p.pinned;
    else if (act === 'del') prompts = prompts.filter((x) => x.id !== p.id);
    else if (act === 'edit') { openPromptEditor(p); return; }
    savePrompts();
    renderPrompts();
    return;
  }
  const txt = lang === 'es' ? p.es : p.en;
  if (!txt) return;
  chatTextarea.value = txt;
  chatTextarea.dispatchEvent(new Event('input'));
  chatTextarea.focus();
  handleSubmit();
});
let editingPromptId = null;
function openPromptEditor(p) {
  editingPromptId = p ? p.id : null;
  $('prompt-modal-title').textContent = p ? t('edit_prompt') : t('add_prompt');
  $('prompt-es').value = p ? (p.es || '') : '';
  $('prompt-en').value = p ? (p.en || '') : '';
  $('prompt-overlay').style.display = 'block';
  $('prompt-modal').style.display = 'block';
  $('prompt-es').focus();
}
function closePromptEditor() {
  $('prompt-overlay').style.display = 'none';
  $('prompt-modal').style.display = 'none';
  editingPromptId = null;
}
$('btn-add-prompt').addEventListener('click', () => openPromptEditor(null));
$('btn-close-prompt').addEventListener('click', closePromptEditor);
$('btn-prompt-cancel').addEventListener('click', closePromptEditor);
$('prompt-overlay').addEventListener('click', closePromptEditor);
$('btn-prompt-save').addEventListener('click', () => {
  const es = $('prompt-es').value.trim().slice(0, 500);
  const en = $('prompt-en').value.trim().slice(0, 500);
  if (!es && !en) { showToast(t('prompt_need'), 'error'); return; }
  if (editingPromptId) {
    const p = prompts.find((x) => x.id === editingPromptId);
    if (p) { p.es = es; p.en = en || es; }
  } else {
    prompts.push({ id: 'cp_' + Date.now().toString(36), es, en: en || es, icon: 'bi-lightning-charge', pinned: false });
  }
  savePrompts();
  renderPrompts();
  closePromptEditor();
});
renderPrompts();

$('btn-clear').addEventListener('click', () => {
  state.controller?.abort(); state.controller = null; state.isGenerating = false; state.a2ui = [];
  destroyA2UICharts();
  sendBtn.disabled = false; progressBar.style.display = 'none'; previewIframe.srcdoc = '';
  state.generatedHTML = ''; state.agentMessage = ''; state.toolCalls = []; state.lastSummary = '';
  if (refreshTimer) { clearInterval(refreshTimer); refreshTimer = null; }
  const autoBox = $('auto-refresh');
  if (autoBox) autoBox.checked = false;
  activeDataset = null; refreshDatasetChip();
  try { localStorage.removeItem(SESSION_KEY); sessionStorage.removeItem(SESSION_KEY); } catch (e) {}
  welcomeState.style.display = 'flex'; generatedWrapper.classList.remove('visible');
  agentBubble.style.display = 'none'; previewContainer.style.display = 'none'; agentBubbleText.textContent = '';
  $('user-bubble').style.display = 'none'; $('user-bubble-text').textContent = ''; $('user-bubble-imgs').innerHTML = '';
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

// ─── Generation settings (interface style prompt) ───────────────────────────
const STYLE_KEY = 'glintmesh-style-v1';
const STYLE_PRESETS = {
  minimalist: 'Minimalist enterprise style: clean layouts with generous whitespace, slate grays with one emerald accent, simple bordered cards, professional typography, clear data tables, no gradients or decoration.',
  glass: 'True glassmorphism style: transparent frosted-crystal cards with backdrop blur you can see through, thin translucent white borders, subtle light refraction and soft shadows, airy and clean.',
  dark: 'Simple dark style: flat near-black background, light gray text, one subtle accent color, minimal borders, maximum readability, no gradients or effects.',
  corporate: 'Classic corporate banking style: white background, navy blue headers, conservative tables, dense and formal, maximum readability.',
  custom: '',
};
let stylePrompt = '', stylePreset = 'minimalist';
let genModel = '', genTemp = 0.7, genMode = 'full';
try {
  const saved = JSON.parse(localStorage.getItem(STYLE_KEY) || 'null');
  if (saved) {
    stylePrompt = saved.prompt || ''; stylePreset = saved.preset || 'minimalist';
    genModel = saved.model || ''; genTemp = (typeof saved.temp === 'number') ? saved.temp : 0.7;
    genMode = saved.mode === 'data' ? 'data' : 'full';
  }
} catch (e) {}
function persistSettings() {
  try { localStorage.setItem(STYLE_KEY, JSON.stringify({ prompt: stylePrompt, preset: stylePreset, model: genModel, temp: genTemp, mode: genMode })); } catch (e) {}
}
function refreshSettingsDot() {
  $('settings-dot').style.display = (stylePrompt && stylePreset !== 'minimalist') ? 'block' : 'none';
}
function syncSettingsUI() {
  const ta = $('style-textarea');
  ta.value = stylePrompt;
  $('style-count').textContent = ta.value.length + ' / 1000';
  document.querySelectorAll('#style-presets [data-preset]').forEach((b) => {
    b.style.borderColor = b.dataset.preset === stylePreset ? cv('--ok-active-bd') : '';
  });
  const sel = $('gen-model');
  const geminiModels = (cachedHealth && cachedHealth.models) || [];
  const groqModels = (cachedHealth && (cachedHealth.groq_models || (cachedHealth.groq_model ? [cachedHealth.groq_model] : []))) || [];
  let optsHtml = '<option value="">default</option>';
  if (geminiModels.length) {
    optsHtml += '<optgroup label="Gemini">' + geminiModels.map((m) => '<option value="' + escapeHtml(m) + '"' + (m === genModel ? ' selected' : '') + '>' + escapeHtml(m) + '</option>').join('') + '</optgroup>';
  }
  if (groqModels.length) {
    optsHtml += '<optgroup label="Groq (fallback)">' + groqModels.map((m) => '<option value="' + escapeHtml(m) + '"' + (m === genModel ? ' selected' : '') + '>' + escapeHtml(m) + '</option>').join('') + '</optgroup>';
  }
  sel.innerHTML = optsHtml;
  if (genModel && ![...sel.options].some((o) => o.value === genModel)) {
    const opt = document.createElement('option'); opt.value = genModel; opt.textContent = genModel; opt.selected = true; sel.appendChild(opt);
  }
  $('gen-temp').value = Math.round(genTemp * 100);
  $('gen-temp-val').textContent = Number(genTemp).toFixed(1);
  $('mode-full').style.borderColor = genMode === 'full' ? cv('--ok-active-bd') : '';
  $('mode-data').style.borderColor = genMode === 'data' ? cv('--ok-active-bd') : '';
  refreshSettingsSession();
}
function openSettings() {
  syncSettingsUI();
  refreshSettingsDatasets();
  $('settings-modal').style.display = 'block';
  $('settings-overlay').style.display = 'block';
}
function closeSettings() { $('settings-modal').style.display = 'none'; $('settings-overlay').style.display = 'none'; }
$('btn-settings').addEventListener('click', openSettings);
$('btn-close-settings').addEventListener('click', closeSettings);
$('settings-overlay').addEventListener('click', closeSettings);
document.querySelectorAll('#style-presets [data-preset]').forEach((b) => b.addEventListener('click', () => {
  stylePreset = b.dataset.preset;
  $('style-textarea').value = stylePreset === 'custom' ? '' : STYLE_PRESETS[stylePreset];
  $('style-count').textContent = $('style-textarea').value.length + ' / 1000';
  if (stylePreset === 'custom') $('style-textarea').focus();
  openSettingsRefresh();
}));
function openSettingsRefresh() {
  document.querySelectorAll('#style-presets [data-preset]').forEach((x) => { x.style.borderColor = x.dataset.preset === stylePreset ? cv('--ok-active-bd') : ''; });
}
$('style-textarea').addEventListener('input', (e) => {
  $('style-count').textContent = e.target.value.length + ' / 1000';
  if (e.target.value !== (STYLE_PRESETS[stylePreset] || '')) stylePreset = 'custom';
  openSettingsRefresh();
});
$('gen-model').addEventListener('change', (e) => { genModel = e.target.value; persistSettings(); refreshSettingsDot(); });
$('gen-temp').addEventListener('input', (e) => {
  genTemp = Math.round(Number(e.target.value)) / 100;
  $('gen-temp-val').textContent = genTemp.toFixed(1);
  persistSettings(); refreshSettingsDot();
});
$('mode-full').addEventListener('click', () => { genMode = 'full'; persistSettings(); syncSettingsUI(); });
$('mode-data').addEventListener('click', () => { genMode = 'data'; persistSettings(); syncSettingsUI(); });
$('btn-style-save').addEventListener('click', () => {
  stylePrompt = $('style-textarea').value.trim().slice(0, 1000);
  if (!stylePrompt) stylePreset = 'minimalist';
  persistSettings();
  refreshSettingsDot();
  closeSettings();
  showToast(t('style_saved'), 'success');
});
$('btn-style-reset').addEventListener('click', () => {
  stylePrompt = ''; stylePreset = 'minimalist'; genModel = ''; genTemp = 0.7; genMode = 'full';
  try { localStorage.removeItem(STYLE_KEY); } catch (e) {}
  refreshSettingsDot();
  closeSettings();
});
function refreshSettingsSession() {
  let session = null;
  try { session = JSON.parse(localStorage.getItem(SESSION_KEY) || sessionStorage.getItem(SESSION_KEY) || 'null'); } catch (e) {}
  const el = $('settings-session');
  if (session && (session.generatedHTML || session.agentMessage)) {
    const imp = getImportant();
    const when = session.ts ? new Date(session.ts).toLocaleString() : '';
    el.innerHTML = '<span></span><span class="star-wrap"></span> <button class="btn-glass btn-sm" id="btn-wipe-session" style="margin-left:8px;"></button>';
    el.querySelector('span').textContent = t('saved_session') + (when ? ' · ' + when : '');
    const wrap = el.querySelector('.star-wrap');
    wrap.innerHTML = starBtn(imp.session);
    wrap.querySelector('[data-star]').addEventListener('click', () => {
      const v = getImportant(); v.session = !v.session; saveImportant(v); refreshSettingsSession();
    });
    el.querySelector('#btn-wipe-session').textContent = t('delete');
    el.querySelector('#btn-wipe-session').addEventListener('click', () => {
      try { localStorage.removeItem(SESSION_KEY); sessionStorage.removeItem(SESSION_KEY); } catch (e) {}
      refreshSettingsSession();
    });
  } else {
    el.textContent = t('session_empty');
  }
}
async function refreshSettingsDatasets() {
  const box = $('settings-datasets');
  box.innerHTML = '';
  try {
    const res = await fetch('/api/datasets');
    const data = await res.json();
    (data.datasets || []).forEach((d) => {
      const row = document.createElement('div');
      row.style.cssText = 'display:flex; align-items:center; gap:8px; font-size:12px; color:var(--text-secondary);';
      const imp = getImportant().datasets.includes(d.id);
      row.innerHTML = '<i class="bi bi-database" style="color:var(--ok-color);"></i><span style="flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;"></span>' + starBtn(imp) + '<button class="btn-glass btn-sm"></button>';
      row.querySelector('span').textContent = d.name + ' (' + d.n_rows + ')';
      row.querySelector('[data-star]').addEventListener('click', () => {
        const v = getImportant();
        v.datasets = v.datasets.includes(d.id) ? v.datasets.filter((x) => x !== d.id) : [...v.datasets, d.id];
        saveImportant(v); refreshSettingsDatasets();
      });
      const btn = row.querySelector('.btn-glass:not([data-star])');
      btn.textContent = t('delete');
      btn.addEventListener('click', async () => {
        await fetch('/api/datasets/' + encodeURIComponent(d.id), { method: 'DELETE' });
        if (activeDataset && activeDataset.id === d.id) { activeDataset = null; refreshDatasetChip(); }
        refreshSettingsDatasets();
      });
      box.appendChild(row);
    });
    if (!box.children.length) box.innerHTML = '<div style="font-size:12px;color:var(--text-muted);">' + t('no_datasets') + '</div>';
  } catch (e) {}
}
$('btn-wipe-all').addEventListener('click', async () => {
  let nDatasets = 0, hasSession = false;
  try {
    const res = await fetch('/api/datasets');
    nDatasets = ((await res.json()).datasets || []).length;
  } catch (e) {}
  try { hasSession = !!JSON.parse(localStorage.getItem(SESSION_KEY) || sessionStorage.getItem(SESSION_KEY) || 'null'); } catch (e) {}
  const imp = getImportant();
  const parts = [];
  if (hasSession) parts.push('1 ' + t('w_session') + (imp.session ? ' (' + t('imp_tag') + ')' : ''));
  if (nDatasets) parts.push(nDatasets + ' ' + t('w_datasets') + (imp.datasets.length ? ' (' + imp.datasets.length + ' ' + t('imp_tag') + ')' : ''));
  parts.push(t('w_prefs'));
  $('wipe-text').textContent = t('wipe_will_delete') + ' ' + parts.join(', ') + '.';
  $('wipe-overlay').style.display = 'block';
  $('wipe-modal').style.display = 'block';
});
function closeWipe() { $('wipe-overlay').style.display = 'none'; $('wipe-modal').style.display = 'none'; }
$('btn-wipe-cancel').addEventListener('click', closeWipe);
$('wipe-overlay').addEventListener('click', closeWipe);
async function wipeAll(keepImportant) {
  const imp = keepImportant ? getImportant() : { datasets: [], session: false };
  try {
    const res = await fetch('/api/datasets');
    const items = ((await res.json()).datasets || []);
    for (const d of items) {
      if (keepImportant && imp.datasets.includes(d.id)) continue;
      await fetch('/api/datasets/' + encodeURIComponent(d.id), { method: 'DELETE' });
    }
  } catch (e) {}
  if (!keepImportant || !imp.session) {
    try { localStorage.removeItem(SESSION_KEY); sessionStorage.removeItem(SESSION_KEY); } catch (e) {}
  }
  if (!keepImportant) {
    try { localStorage.removeItem(STYLE_KEY); localStorage.removeItem(UI_KEY); localStorage.removeItem(IMPORTANT_KEY); } catch (e) {}
    stylePrompt = ''; stylePreset = 'minimalist'; genModel = ''; genTemp = 0.7; genMode = 'full';
    themeId = 'red-white'; userCss = '';
    applyTheme(); refreshSettingsDot();
  }
  if (activeDataset && !(keepImportant && imp.datasets.includes(activeDataset.id))) {
  activeDataset = null; refreshDatasetChip();
  attachedImages = []; renderImgStrip();
  }
  closeWipe(); closeSettings();
  refreshSettingsSession(); refreshSettingsDatasets();
  showToast(t('wiped_ok'), 'success');
}
$('btn-wipe-keep').addEventListener('click', () => wipeAll(true));
$('btn-wipe-all2').addEventListener('click', () => wipeAll(false));
refreshSettingsDot();

// ─── App appearance: themes (JSON) + custom CSS (app shell only) ────────────
const UI_KEY = 'glintmesh-ui-v3';
let THEMES = [];
let themeId = 'red-white', userCss = '';
try {
  const savedUI = JSON.parse(localStorage.getItem(UI_KEY) || 'null');
  if (savedUI) {
    if (typeof savedUI.theme === 'string' && savedUI.theme) themeId = savedUI.theme;
    userCss = (savedUI.css || '').slice(0, 3000);
  }
} catch (e) {}
function cv(name, fallback = '') {
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return v || fallback;
}
function getTheme(id) { return THEMES.find((t) => t.id === id) || null; }
function applyTheme() {
  document.body.dataset.theme = themeId;
  const root = document.documentElement;
  for (const p of Array.from(root.style)) { if (p.startsWith('--')) root.style.removeProperty(p); }
  const theme = getTheme(themeId);
  if (theme && theme.vars) {
    Object.entries(theme.vars).forEach(([k, v]) => { if (v !== '' && v != null) root.style.setProperty(k, v); });
  }
  const tag = $('theme-css');
  if (tag) tag.textContent = (theme && theme.css) || '';
  const u = $('user-css');
  if (u) u.textContent = userCss;
  document.querySelectorAll('#theme-grid [data-theme]').forEach((b) => {
    b.style.borderColor = b.dataset.theme === themeId ? cv('--ok-active-bd') : '';
  });
  if ($('ui-dark')) $('ui-dark').style.borderColor = themeId === 'dark' ? cv('--ok-active-bd') : '';
  if ($('ui-light')) $('ui-light').style.borderColor = themeId === 'light' ? cv('--ok-active-bd') : '';
  const ta = $('user-css-textarea');
  if (ta && document.activeElement !== ta) ta.value = userCss;
}
function persistUI() {
  try { localStorage.setItem(UI_KEY, JSON.stringify({ theme: themeId, css: userCss })); } catch (e) {}
}
function buildThemeGrid() {
  const grid = $('theme-grid');
  if (!grid) return;
  grid.innerHTML = THEMES.map((t) => '<button class="btn-glass btn-sm" data-theme="' + escapeHtml(t.id) + '" style="flex:1 0 40%;">' + escapeHtml(t.name) + '</button>').join('');
  grid.querySelectorAll('[data-theme]').forEach((b) => b.addEventListener('click', () => {
    themeId = b.dataset.theme; persistUI(); applyTheme();
  }));
}
$('ui-dark').addEventListener('click', () => { themeId = getTheme('dark') ? 'dark' : (THEMES[0]?.id || 'red-white'); persistUI(); applyTheme(); });
$('ui-light').addEventListener('click', () => { themeId = getTheme('light') ? 'light' : (THEMES[0]?.id || 'red-white'); persistUI(); applyTheme(); });
$('user-css-textarea').addEventListener('input', (e) => {
  userCss = e.target.value.slice(0, 3000);
  const tag = $('user-css');
  if (tag) tag.textContent = userCss;
  persistUI();
});
const CSS_SNIPS = {
  blue: '#header { background:linear-gradient(135deg,#1e3a8a,#1e40af) !important; }',
  round: '#sidebar, #content-area, .tool-card, .feature-card, #input-wrapper, .a2ui-card { border-radius:20px !important; }',
  compact: '#header { height:52px !important; } #main-body { padding:8px !important; gap:8px !important; } .feature-card { padding:10px 8px !important; }',
};
document.querySelectorAll('[data-snip]').forEach((b) => b.addEventListener('click', () => {
  const snip = CSS_SNIPS[b.dataset.snip];
  if (!snip) return;
  const ta = $('user-css-textarea');
  ta.value = (ta.value.trim() ? ta.value.trim() + '\n' : '') + snip;
  userCss = ta.value.slice(0, 3000);
  const tag = $('user-css');
  if (tag) tag.textContent = userCss;
  persistUI();
}));
$('btn-reset-look').addEventListener('click', () => {
  themeId = 'red-white'; userCss = '';
  persistUI(); applyTheme();
  showToast(t('style_saved'), 'success');
});
applyTheme();
async function loadThemes() {
  try {
    const res = await fetch('/static/themes.json');
    const data = await res.json();
    if (Array.isArray(data.themes)) THEMES = data.themes;
  } catch (e) { THEMES = []; }
  if (!THEMES.some((t) => t.id === themeId)) themeId = THEMES[0]?.id || 'red-white';
  buildThemeGrid();
  applyTheme();
}
loadThemes();

// ─── Important flags + wipe-all with warning ────────────────────────────────
const IMPORTANT_KEY = 'glintmesh-important-v1';
function getImportant() {
  try {
    const v = JSON.parse(localStorage.getItem(IMPORTANT_KEY) || 'null');
    if (v && Array.isArray(v.datasets)) return { datasets: v.datasets, session: !!v.session };
  } catch (e) {}
  return { datasets: [], session: false };
}
function saveImportant(v) {
  try { localStorage.setItem(IMPORTANT_KEY, JSON.stringify(v)); } catch (e) {}
}
function starBtn(on) {
  return '<button class="btn-glass btn-sm" data-star="1" title="important" style="padding:3px 7px; color:' + (on ? '#fbbf24' : 'var(--text-muted)') + ';">'
    + '<svg viewBox="0 0 16 16" width="12" height="12" fill="currentColor" aria-hidden="true"><path d="M8 1l2.2 4.7 5.1.6-3.8 3.5 1 5-4.5-2.5-4.5 2.5 1-5L.7 6.3l5.1-.6z"/></svg></button>';
}

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

// ─── A2UI refresh without Gemini (replays stored MCP tool calls) ─────────────
let refreshTimer = null;
function latestA2UICard(tool) {
  const cards = a2uiFeed.querySelectorAll('.a2ui-card');
  for (let i = cards.length - 1; i >= 0; i--) {
    if (cards[i].dataset.tool === tool && !cards[i].dataset.pending) return cards[i];
  }
  return null;
}
async function refreshA2UIData() {
  if (!state.toolCalls.length) return;
  const seen = new Set();
  let ok = 0, fail = 0;
  for (const call of state.toolCalls) {
    if (seen.has(call.tool)) continue;
    seen.add(call.tool);
    try {
      const res = await fetch('/api/tool-call', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tool: call.tool, args: call.args || {} }),
      });
      if (!res.ok) throw new Error('tool failed');
      const data = await res.json();
      const card = latestA2UICard(call.tool);
      if (card) { fillA2UICard(card, call.tool, data.data, false); ok++; }
    } catch (e) { fail++; }
  }
  const note = $('refresh-note');
  if (note) {
    note.textContent = new Date().toLocaleTimeString() + ' · ' + (fail ? t('refresh_fail') : t('refreshed_ok'));
    setTimeout(() => { if (note) note.textContent = ''; }, 4000);
  }
  if (ok && !fail) showToast(t('refreshed_ok'), 'success');
  else if (fail) showToast(t('refresh_fail'), 'error');
}
$('btn-refresh-data').addEventListener('click', refreshA2UIData);
$('auto-refresh').addEventListener('change', (e) => {
  if (refreshTimer) { clearInterval(refreshTimer); refreshTimer = null; }
  if (e.target.checked) refreshTimer = setInterval(refreshA2UIData, 60000);
});

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
$('btn-share').addEventListener('click', async () => {
  if (!state.generatedHTML) return;
  try {
    const res = await fetch('/api/share', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ html: state.generatedHTML }),
    });
    if (!res.ok) throw new Error('share failed');
    const data = await res.json();
    await navigator.clipboard.writeText(window.location.origin + data.url);
    showToast(t('link_copied'), 'success');
  } catch (e) { showToast(t('share_fail'), 'error'); }
});

// ─── Submit ─────────────────────────────────────────────────────────────────
async function handleSubmit() {
  const message = chatTextarea.value.trim();
  if (!message || state.isGenerating) return;
  if (message.length > 500) return;
  try { recog && listening && recog.stop(); } catch (e) {}
  const controller = new AbortController();
  state.controller = controller; state.isGenerating = true;
  state.generatedHTML = ''; state.agentMessage = ''; state.toolCalls = []; state.toolResults = {}; state.a2ui = [];
  destroyA2UICharts();
  $('btn-retry').style.display = 'none'; state.lastError = '';
  const sentImages = attachedImages.slice(0, 3);
  chatTextarea.value = ''; chatTextarea.style.height = 'auto'; charCount.textContent = '0 / 500';
  attachedImages = []; renderImgStrip();
  sendBtn.disabled = true; progressBar.style.display = 'flex';
  welcomeState.style.display = 'none'; generatedWrapper.classList.add('visible');
  // user bubble: show what was sent (text + images, Gemini style)
  const userBubble = $('user-bubble'), userBubbleText = $('user-bubble-text'), userBubbleImgs = $('user-bubble-imgs');
  userBubble.style.display = 'flex'; userBubbleText.textContent = message;
  userBubbleImgs.innerHTML = '';
  sentImages.forEach((im) => {
    const img = document.createElement('img');
    img.src = im.url; img.style.cssText = 'width:72px; height:72px; object-fit:cover; border-radius:10px; border:1px solid var(--glass-border);';
    userBubbleImgs.appendChild(img);
  });
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
    if (stylePrompt) payload.style_prompt = stylePrompt.slice(0, 1000);
    if (genModel) payload.model = genModel;
    if (genTemp !== 0.7) payload.temperature = genTemp;
    if (genMode === 'data') payload.mode = 'data';
    if (sentImages.length) payload.images = sentImages.map(({ mime, data }) => ({ mime, data }));
    state.lastPayload = { ...payload };
    const response = await fetch('/api/generate', {
      method: 'POST', headers: { 'Content-Type': 'application/json', ...authHeaders() },
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
      state.lastError = error.message || '';
      $('btn-retry').style.display = 'inline-flex';
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
  if (/portfolio|forex|_fx|indices|news|ecb/i.test(tool)) return 'table';
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
    if (tool === 'get_forex_rates' || tool === 'get_live_fx' || tool === 'get_ecb_rates') return a2uiForex(data);
    return '<pre class="a2ui-raw">' + esc(JSON.stringify(data, null, 2)).slice(0, 4000) + '</pre>';
  } catch (e) {
    return '<div class="a2ui-mlabel">Could not render this surface</div>';
  }
}

function mountA2UIChart(tool, data, cid) {
  if (!window.Chart) return;
  try {
    const okChart = cv('--ok-chart'), okFill = cv('--ok-chart-fill'), grid = cv('--grid-line'), sec = cv('--chart-secondary', '#64748b');
    Chart.defaults.color = cv('--text-muted', '#8a94a8');
    Chart.defaults.font.family = 'Inter, sans-serif';
    const el = document.getElementById(cid);
    if (!el) return;
    let cfg = null;
    if (tool === 'get_historical_prices' || tool === 'get_live_history') {
      const pts = data.data || [];
      const step = Math.max(1, Math.ceil(pts.length / 14));
      cfg = { type: 'line', data: { labels: pts.filter((_, i) => i % step === 0).map((p) => p.date), datasets: [{ data: pts.filter((_, i) => i % step === 0).map((p) => p.close), borderColor: okChart, backgroundColor: okFill, fill: true, tension: .3, pointRadius: 0 }] }, options: { plugins: { legend: { display: false } }, scales: { x: { grid: { color: grid } }, y: { grid: { color: grid } } } } };
    } else if (tool === 'calculate_compound_interest') {
      const yrs = data.yearly_breakdown || [];
      cfg = { type: 'line', data: { labels: yrs.map((y) => 'Y' + y.year), datasets: [{ label: 'Balance', data: yrs.map((y) => y.balance), borderColor: okChart, backgroundColor: okFill, fill: true, tension: .3 }, { label: 'Contributions', data: yrs.map((y) => y.contributions), borderColor: sec, borderDash: [5, 4], fill: false, tension: .3, pointRadius: 0 }] }, options: { plugins: { legend: { labels: { boxWidth: 12 } } }, scales: { x: { grid: { display: false } }, y: { grid: { color: grid } } } } };
    }
    if (cfg) state.charts.push(new Chart(el, cfg));
  } catch (e) {}
}

function handleSSEEvent(event) {
  switch (event.type) {
    case 'status': setStatus(event.content, 'active'); progressLabel.textContent = event.content; break;
    case 'tool_call': {
      setStatus(event.content, 'active'); progressLabel.textContent = event.content;
      const name = event.tool || event.content.replace('Fetching ', '').replace('...', '');
      const args = (event.args && typeof event.args === 'object') ? event.args : {};
      state.toolCalls.push({ tool: name, args });
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
      if (event.tool) state.toolResults[event.tool] = { data: event.data, failed: !!event.failed };
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
  const live = !!(data && typeof data.source === 'string' && data.source.indexOf('live') === 0);
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
  if (genMode === 'data') {
    const a2uiTab = document.querySelector('.tab-btn[data-tab="a2ui"]');
    if (a2uiTab) a2uiTab.click();
  }
  state.lastSummary = (agentBubble.style.display === 'none' ? fullText : agentBubbleText.textContent).slice(0, 800);
  saveSession();
}

function isAuthed() {
  try { return !!(JSON.parse(localStorage.getItem(AUTH_KEY) || 'null') || {}).token; } catch (e) { return false; }
}

function saveSession() {
  try {
    if (!state.generatedHTML && !state.agentMessage) return;
    const data = JSON.stringify({
      lang, agentMessage: agentBubbleText.textContent || '', generatedHTML: state.generatedHTML || '',
      dataset: activeDataset, ts: Date.now(),
    });
    if (isAuthed()) localStorage.setItem(SESSION_KEY, data);
    else sessionStorage.setItem(SESSION_KEY, data);
  } catch (e) {}
}

function restoreSession() {
  let saved = null;
  try { saved = JSON.parse(localStorage.getItem(SESSION_KEY) || sessionStorage.getItem(SESSION_KEY) || 'null'); } catch (e) {}
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
// ─── Voz: dictado Web Speech API (degradado si no hay soporte) ─────────────
let recog = null, listening = false, voiceBase = '', voiceInterim = '';
(function initVoice() {
  const btn = $('mic-btn');
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) { btn.style.opacity = '0.35'; btn.title = t('voice_off'); btn.addEventListener('click', () => showToast(t('voice_off'), 'error')); return; }
  const r = new SR();
  r.interimResults = true; r.maxAlternatives = 1; r.continuous = false;
  const setRec = (on) => {
    listening = on;
    btn.innerHTML = on ? '<i class="bi bi-record-circle-fill"></i>' : '<i class="bi bi-mic"></i>';
    btn.style.color = on ? 'var(--accent-red)' : '';
    btn.style.animation = on ? 'micPulse 1s ease-in-out infinite' : '';
    if (!document.getElementById('mic-pulse-style')) {
      const s = document.createElement('style'); s.id = 'mic-pulse-style';
      s.textContent = '@keyframes micPulse { 0%,100%{opacity:1;} 50%{opacity:0.35;} }';
      document.head.appendChild(s);
    }
    setStatus(on ? t('voice_on') : t('ready'), on ? 'active' : '');
  };
  r.onresult = (e) => {
    let finalTxt = '', interimTxt = '';
    for (let i = e.resultIndex; i < e.results.length; i++) {
      const res = e.results[i];
      if (res.isFinal) finalTxt += res[0].transcript;
      else interimTxt += res[0].transcript;
    }
    voiceInterim = interimTxt.trim();
    const base = voiceBase ? voiceBase + ' ' : '';
    chatTextarea.value = (base + finalTxt.trim() + (voiceInterim ? ' ' + voiceInterim : '')).slice(0, 500);
    chatTextarea.dispatchEvent(new Event('input'));
    if (finalTxt.trim()) voiceBase = (base + finalTxt.trim()).trim();
  };
  r.onend = () => {
    voiceInterim = '';
    if (voiceBase) { chatTextarea.value = voiceBase.slice(0, 500); chatTextarea.dispatchEvent(new Event('input')); chatTextarea.focus(); }
    setRec(false);
  };
  r.onerror = (e) => {
    const err = (e && e.error) || 'error';
    setRec(false);
    const msgs = { 'not-allowed': 'voice_mic_denied', 'service-not-allowed': 'voice_mic_denied', 'audio-capture': 'voice_no_mic', 'no-speech': 'voice_no_speech', 'network': 'voice_network', 'aborted': '', 'language-not-supported': 'voice_lang' };
    const key = msgs[err];
    if (key) showToast(t(key), 'error');
    else if (err) showToast('Voz: ' + err, 'error');
  };
  recog = r;
  btn.addEventListener('click', () => {
    if (listening) { try { r.stop(); } catch (err) {} return; }
    voiceBase = chatTextarea.value.trim();
    voiceInterim = '';
    try {
      r.lang = lang === 'es' ? 'es-ES' : 'en-US';
      r.start();
      setRec(true);
      showToast(t('voice_on'), 'info');
    } catch (err) { showToast(t('voice_off'), 'error'); }
  });
})();

// ─── Imágenes al prompt (base64, máx 3 x 1.5MB) ─────────────────────────────
let attachedImages = [];
$('img-btn').addEventListener('click', () => $('img-input').click());
$('img-input').addEventListener('change', (e) => {
  const files = [...(e.target.files || [])];
  for (const f of files) {
    if (attachedImages.length >= 3) { showToast(t('img_many'), 'error'); break; }
    if (f.size > 1500000) { showToast(t('img_big'), 'error'); continue; }
    const rd = new FileReader();
    rd.onload = () => {
      const url = String(rd.result || '');
      const b64 = url.split(',')[1] || '';
      if (!b64) return;
      attachedImages.push({ mime: f.type || 'image/png', data: b64, url });
      renderImgStrip();
    };
    rd.readAsDataURL(f);
  }
  e.target.value = '';
});
function renderImgStrip() {
  const strip = $('img-strip');
  strip.innerHTML = '';
  if (!attachedImages.length) { strip.style.display = 'none'; return; }
  strip.style.display = 'flex';
  attachedImages.forEach((im, i) => {
    const box = document.createElement('div');
    box.style.cssText = 'position:relative; width:64px; height:64px; border-radius:10px; overflow:hidden; border:1px solid var(--glass-border);';
    box.innerHTML = '<img style="width:100%;height:100%;object-fit:cover;" /><button style="position:absolute;top:2px;right:2px;background:rgba(0,0,0,0.6);border:none;color:#fff;border-radius:50%;width:20px;height:20px;cursor:pointer;font-size:12px;">×</button>';
    box.querySelector('img').src = im.url;
    box.querySelector('button').addEventListener('click', () => { attachedImages.splice(i, 1); renderImgStrip(); });
    strip.appendChild(box);
  });
}

// ─── Login local opcional ───────────────────────────────────────────────────
const AUTH_KEY = 'glintmesh-auth-v1';
function authHeaders() {
  try {
    const s = JSON.parse(localStorage.getItem(AUTH_KEY) || 'null');
    if (s && s.token) return { 'Authorization': 'Bearer ' + s.token };
  } catch (e) {}
  return {};
}
function currentAuth() {
  try { return JSON.parse(localStorage.getItem(AUTH_KEY) || 'null') || {}; } catch (e) { return {}; }
}
function refreshAuthLabel() {
  const s = currentAuth();
  const user = s.user || null, avatar = s.avatar || null;
  $('auth-label').textContent = user || t('signin');
  $('auth-avatar').style.display = avatar ? 'inline-block' : 'none';
  $('auth-icon').style.display = avatar ? 'none' : '';
  if (avatar) $('auth-avatar-img').src = avatar;
  $('btn-logout').style.display = user ? 'block' : 'none';
  $('auth-profile').style.display = user ? 'flex' : 'none';
  $('auth-guest-note').style.display = user ? 'none' : 'block';
  $('auth-user').style.display = user ? 'none' : 'block';
  $('auth-pass').style.display = user ? 'none' : 'block';
  $('btn-login').style.display = user ? 'none' : 'block';
  $('btn-register').style.display = user ? 'none' : 'block';
  if (user) {
    $('auth-profile-name').textContent = user;
    $('auth-profile-img').style.display = avatar ? 'block' : 'none';
    $('auth-profile-icon').style.display = avatar ? 'none' : 'block';
    if (avatar) $('auth-profile-img').src = avatar;
  }
}
$('btn-auth').addEventListener('click', () => { refreshAuthLabel(); $('auth-modal').style.display = 'block'; $('auth-overlay').style.display = 'block'; });
$('btn-close-auth').addEventListener('click', () => { $('auth-modal').style.display = 'none'; $('auth-overlay').style.display = 'none'; });
$('auth-overlay').addEventListener('click', () => { $('auth-modal').style.display = 'none'; $('auth-overlay').style.display = 'none'; });
$('btn-register').addEventListener('click', async () => {
  const user = $('auth-user').value.trim(), password = $('auth-pass').value;
  if (user.length < 3 || password.length < 4) { $('auth-note').textContent = t('auth_short'); return; }
  const res = await fetch('/api/auth/register', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ user, password }) });
  if (!res.ok) { $('auth-note').textContent = t('auth_reg_fail') + ' (' + res.status + ')'; return; }
  // auto-login: registra y entra directo, sin paso extra
  const login = await fetch('/api/auth/login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ user, password }) });
  if (!login.ok) { $('auth-note').textContent = t('auth_enter_login'); return; }
  await applyAuthSession(await login.json());
});
async function applyAuthSession(data) {
  try { localStorage.setItem(AUTH_KEY, JSON.stringify(data)); } catch (e) {}
  // la sesion de invitado pasa a ser persistente al entrar
  try {
    const guest = sessionStorage.getItem(SESSION_KEY);
    if (guest && !localStorage.getItem(SESSION_KEY)) localStorage.setItem(SESSION_KEY, guest);
    sessionStorage.removeItem(SESSION_KEY);
  } catch (e) {}
  refreshAuthLabel();
  $('auth-modal').style.display = 'none'; $('auth-overlay').style.display = 'none';
  showToast((data && data.user) || '', 'success');
}
$('btn-login').addEventListener('click', async () => {
  const user = $('auth-user').value.trim(), password = $('auth-pass').value;
  if (!user || !password) { $('auth-note').textContent = t('auth_empty'); return; }
  const res = await fetch('/api/auth/login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ user, password }) });
  if (!res.ok) { $('auth-note').textContent = (res.status === 401 ? t('auth_bad') : t('auth_login_fail')) + ' (' + res.status + ')'; return; }
  await applyAuthSession(await res.json());
});
// Enter en usuario/clave = entrar
[$('auth-user'), $('auth-pass')].forEach((el) => el.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') { e.preventDefault(); $('btn-login').click(); }
}));
$('btn-logout').addEventListener('click', async () => {
  try {
    const s = JSON.parse(localStorage.getItem(AUTH_KEY) || 'null');
    if (s && s.token) await fetch('/api/auth/logout', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ token: s.token }) });
  } catch (e) {}
  try { localStorage.removeItem(AUTH_KEY); localStorage.removeItem(SESSION_KEY); sessionStorage.removeItem(SESSION_KEY); } catch (e) {}
  refreshAuthLabel();
});
// Guest mode: info lives only in this tab; never persist guests to disk.
window.addEventListener('beforeunload', () => {
  if (!isAuthed()) { try { localStorage.removeItem(SESSION_KEY); } catch (e) {} }
});
// ─── Avatar: foto de perfil (max ~300 KB) ──────────────────────────────────
$('btn-avatar-pick').addEventListener('click', () => $('auth-avatar-input').click());
$('auth-avatar-input').addEventListener('change', (e) => {
  const f = (e.target.files || [])[0];
  e.target.value = '';
  if (!f) return;
  if (f.size > 300000) { $('auth-note').textContent = t('auth_avatar_big'); return; }
  const rd = new FileReader();
  rd.onload = async () => {
    const url = String(rd.result || '');
    if (!/^data:image\/(png|jpeg|webp|gif);base64,/.test(url)) return;
    // preview local inmediato (aunque el upload tarde)
    $('auth-profile-img').style.display = 'block';
    $('auth-profile-icon').style.display = 'none';
    $('auth-profile-img').src = url;
    $('auth-avatar').style.display = 'inline-block';
    $('auth-icon').style.display = 'none';
    $('auth-avatar-img').src = url;
    try {
      const res = await fetch('/api/auth/avatar', { method: 'PUT', headers: { 'Content-Type': 'application/json', ...authHeaders() }, body: JSON.stringify({ avatar: url.slice(0, 400000) }) });
      if (!res.ok) throw new Error('upload failed');
      const data = await res.json();
      const s = currentAuth(); s.avatar = data.avatar;
      try { localStorage.setItem(AUTH_KEY, JSON.stringify(s)); } catch (err) {}
      refreshAuthLabel();
      $('auth-note').textContent = t('auth_photo_ok');
    } catch (err) { $('auth-note').textContent = t('auth_photo_fail'); }
  };
  rd.readAsDataURL(f);
});
refreshAuthLabel();
// ─── 3. Retry 1-clic ────────────────────────────────────────────────────────
$('btn-retry').addEventListener('click', () => {
  if (state.isGenerating) return;
  $('btn-retry').style.display = 'none';
  const p = state.lastPayload;
  if (p && p.message) {
    chatTextarea.value = p.message;
    chatTextarea.dispatchEvent(new Event('input'));
  }
  handleSubmit(true);
});

// ─── 4. Compose: combina N superficies A2UI en 1 dashboard (sin cuota) ──────
$('btn-compose').addEventListener('click', () => {
  const entries = Object.entries(state.toolResults || {}).filter(([, v]) => v && !v.failed);
  if (entries.length < 2) { showToast(t('need_2'), 'error'); return; }
  const empty = $('a2ui-empty'); if (empty) empty.remove();
  const tiles = entries.slice(0, 8).map(([tool, v]) => {
    const d = v.data || {};
    const sym = d.symbol || d.base || tool.replace(/_/g, ' ');
    const price = d.price ?? d.total_market_value ?? d.value ?? '';
    return '<div class="a2ui-metric"><div class="a2ui-mlabel">' + esc(sym) + '</div>'
      + '<div class="a2ui-mval">' + (price === '' ? esc(tool) : esc(String(price))) + '</div>'
      + '<div class="a2ui-mlabel">' + esc(tool) + '</div></div>';
  }).join('');
  const card = document.createElement('div');
  card.className = 'a2ui-card'; card.dataset.tool = 'composed_dashboard';
  card.style.borderLeftColor = 'var(--accent-purple)';
  card.innerHTML = '<div class="a2ui-head"><span class="proto-badge">A2UI</span>'
    + '<span class="proto-badge mcp">COMPOSED</span><span>Dashboard · ' + entries.length + ' sources</span></div>'
    + '<div class="a2ui-body"><div class="a2ui-grid">' + tiles + '</div>'
    + '<div class="a2ui-mlabel">Combined from: ' + esc(entries.map(([k]) => k).join(', ')) + '</div></div>';
  a2uiFeed.prepend(card);
  state.a2ui.push('composed_dashboard');
  a2uiBadge.style.display = 'inline-flex'; a2uiBadge.textContent = state.a2ui.length;
  showToast(t('composed_ok'), 'success');
});
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
