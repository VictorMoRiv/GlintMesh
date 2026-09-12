import { readSSE } from './sse.mjs';

// ─── State ──────────────────────────────────────────────────────────────────
const state = {
  isGenerating: false,
  controller: null,
  generatedHTML: '',
  agentMessage: '',
  toolCalls: [],
};

// ─── DOM References ──────────────────────────────────────────────────────────
const chatTextarea     = document.getElementById('chat-textarea');
const sendBtn          = document.getElementById('send-btn');
const toolFeed         = document.getElementById('tool-feed');
const statusText       = document.getElementById('status-text');
const welcomeState     = document.getElementById('welcome-state');
const generatedWrapper = document.getElementById('generated-wrapper');
const agentBubble      = document.getElementById('agent-bubble');
const agentBubbleText  = document.getElementById('agent-bubble-text');
const previewContainer = document.getElementById('preview-frame-container');
const previewIframe    = document.getElementById('preview-iframe');
const codeOutput       = document.getElementById('code-output');
const progressBar      = document.getElementById('progress-bar-container');
const progressLabel    = document.getElementById('progress-label');
const charCount        = document.getElementById('char-count');
const codeBadge        = document.getElementById('code-badge');
const btnCopyCode      = document.getElementById('btn-copy-code');

// ─── Tab Navigation ──────────────────────────────────────────────────────────
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const tab = btn.dataset.tab;
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById(`panel-${tab}`).classList.add('active');
  });
});

// ─── Textarea Auto-resize ────────────────────────────────────────────────────
chatTextarea.addEventListener('input', () => {
  chatTextarea.style.height = 'auto';
  chatTextarea.style.height = Math.min(chatTextarea.scrollHeight, 120) + 'px';
  const len = chatTextarea.value.length;
  charCount.textContent = `${len} / 500`;
  if (len > 450) charCount.style.color = 'var(--accent-amber)';
  else charCount.style.color = 'var(--text-muted)';
});

chatTextarea.addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    handleSubmit();
  }
});

sendBtn.addEventListener('click', handleSubmit);

// ─── Suggestion Chips ────────────────────────────────────────────────────────
document.querySelectorAll('.suggestion-chip').forEach(chip => {
  chip.addEventListener('click', () => {
    chatTextarea.value = chip.dataset.prompt;
    chatTextarea.dispatchEvent(new Event('input'));
    chatTextarea.focus();
    handleSubmit();
  });
});

// ─── Clear Button ────────────────────────────────────────────────────────────
document.getElementById('btn-clear').addEventListener('click', () => {
  state.controller?.abort();
  state.controller = null;
  state.isGenerating = false;
  sendBtn.disabled = false;
  progressBar.style.display = 'none';
  previewIframe.srcdoc = '';
  state.generatedHTML = '';
  state.agentMessage = '';
  state.toolCalls = [];
  welcomeState.style.display = 'flex';
  generatedWrapper.classList.remove('visible');
  agentBubble.style.display = 'none';
  previewContainer.style.display = 'none';
  agentBubbleText.textContent = '';
  codeOutput.innerHTML = '<code style="color:var(--text-muted); font-size:12px;">// Generated code will appear here...</code>';
  codeBadge.style.display = 'none';
  btnCopyCode.style.display = 'none';
  toolFeed.innerHTML = `<div style="text-align:center; padding:30px 16px; color:var(--text-muted); font-size:12px; line-height:1.6;">
    <i class="bi bi-diagram-3" style="font-size:24px; display:block; margin-bottom:10px; color:var(--text-muted);"></i>
    MCP tool calls will appear here as the agent works
  </div>`;
  setStatus('Ready to generate interfaces', '');
  chatTextarea.value = '';
  charCount.textContent = '0 / 500';
  showToast('Session cleared', 'info');
});

// ─── Export Button ───────────────────────────────────────────────────────────
document.getElementById('btn-export').addEventListener('click', e => {
  e.preventDefault();
  if (!state.generatedHTML) { showToast('No interface to export yet', 'error'); return; }
  const blob = new Blob([state.generatedHTML], { type: 'text/html' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `finflow-interface-${Date.now()}.html`;
  a.click();
  URL.revokeObjectURL(url);
  showToast('Interface exported', 'success');
});

// ─── Tools Button ────────────────────────────────────────────────────────────
document.getElementById('btn-tools').addEventListener('click', async () => {
  try {
    const res = await fetch('/api/tools');
    const data = await res.json();
    if (!res.ok) throw new Error('Tools unavailable');
    if (!data.enabled) {
      showToast('MCP is disabled. Gemini works without tools.', 'info');
    } else if (data.tools) {
      showToast(`${data.tools.length} MCP tools available`, 'info');
    }
  } catch(e) {
    showToast('Could not fetch tools', 'error');
  }
});

// ─── Preview Actions ─────────────────────────────────────────────────────────
document.getElementById('btn-reload-preview').addEventListener('click', () => {
  if (state.generatedHTML) renderPreview(state.generatedHTML);
});

document.getElementById('btn-fullscreen').addEventListener('click', () => {
  if (!state.generatedHTML) return;
  const frame = document.createElement('iframe');
  frame.setAttribute('sandbox', 'allow-scripts');
  frame.setAttribute('title', 'Generated Financial Interface');
  frame.style.cssText = 'border:0;width:100%;height:100vh';
  frame.srcdoc = state.generatedHTML;
  const wrapper = '<!doctype html><html><head><title>FinFlow Preview</title></head><body style="margin:0">' + frame.outerHTML + '</body></html>';
  const url = URL.createObjectURL(new Blob([wrapper], { type: 'text/html' }));
  window.open(url, '_blank', 'noopener,noreferrer');
  setTimeout(() => URL.revokeObjectURL(url), 60000);
});

// ─── Copy Code ───────────────────────────────────────────────────────────────
btnCopyCode.addEventListener('click', async () => {
  if (!state.generatedHTML) return;
  await navigator.clipboard.writeText(state.generatedHTML);
  showToast('Code copied to clipboard', 'success');
});

// ─── Main Submit Handler ─────────────────────────────────────────────────────
async function handleSubmit() {
  const message = chatTextarea.value.trim();
  if (!message || state.isGenerating) return;
  if (message.length > 500) {
    showToast('Use at most 500 characters per request.', 'error');
    return;
  }

  const controller = new AbortController();
  state.controller = controller;
  state.isGenerating = true;
  state.generatedHTML = '';
  state.agentMessage = '';
  state.toolCalls = [];
  chatTextarea.value = '';
  chatTextarea.style.height = 'auto';
  charCount.textContent = '0 / 500';
  sendBtn.disabled = true;
  progressBar.style.display = 'flex';
  welcomeState.style.display = 'none';
  generatedWrapper.classList.add('visible');
  agentBubble.style.display = 'flex';
  agentBubbleText.textContent = 'Waiting for Gemini...';
  toolFeed.innerHTML = '';
  codeOutput.textContent = '';
  codeBadge.style.display = 'none';
  btnCopyCode.style.display = 'none';
  previewContainer.style.display = 'none';
  previewIframe.srcdoc = '';
  setStatus('Analyzing request...', 'active');

  let fullText = '';
  let completed = false;
  try {
    const response = await fetch('/api/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message }),
      signal: controller.signal,
    });
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(typeof body.detail === 'string' ? body.detail : 'The request could not be processed. Check your message and try again.');
    }
    for await (const event of readSSE(response.body)) {
      if (controller.signal.aborted) return;
      if (event.type === 'error') throw new Error(event.content);
      handleSSEEvent(event);
      if (event.type === 'text_chunk') {
        fullText += event.content;
        codeOutput.textContent = fullText;
        const htmlStart = fullText.indexOf('```html');
        agentBubbleText.textContent = htmlStart === -1
          ? fullText
          : fullText.slice(0, htmlStart).trim() || 'Generating interface...';
      } else if (event.type === 'done') {
        completed = true;
        finalize(fullText);
        break;
      }
    }
    if (!completed && !controller.signal.aborted) throw new Error('The response was interrupted. Please try again.');
  } catch (error) {
    if (!controller.signal.aborted) {
      setStatus('Generation failed', 'error');
      agentBubbleText.textContent = error.message;
      showToast(error.message, 'error');
      if (!chatTextarea.value) {
        chatTextarea.value = message;
        chatTextarea.dispatchEvent(new Event('input'));
      }
    }
  } finally {
    if (state.controller === controller) {
      state.controller = null;
      state.isGenerating = false;
      sendBtn.disabled = false;
      progressBar.style.display = 'none';
    }
  }
}
function handleSSEEvent(event) {
  switch(event.type) {
    case 'status':
      setStatus(event.content, 'active');
      progressLabel.textContent = event.content;
      break;

    case 'tool_call':
      setStatus(event.content, 'active');
      progressLabel.textContent = event.content;
      addToolCard(event.content.replace('Fetching ', '').replace('...', ''), 'calling');
      break;

    case 'tool_result': {
      // Update last tool card to done
      const cards = toolFeed.querySelectorAll('.tool-card');
      if (cards.length > 0) {
        const last = cards[cards.length - 1];
        const icon = last.querySelector('.tool-status-icon');
        if (icon) {
          icon.className = 'tool-status-icon ' + (event.failed ? 'error' : 'done');
          icon.innerHTML = event.failed ? '<i class="bi bi-x"></i>' : '<i class="bi bi-check"></i>';
        }
        // Show brief data summary
        const dataDiv = last.querySelector('.tool-data');
        if (dataDiv && event.data) {
          const snippet = JSON.stringify(event.data).slice(0, 120) + '...';
          dataDiv.textContent = snippet;
        }
      }
      break;
    }

    case 'error':
      setStatus(event.content, 'error');
      agentBubbleText.textContent = 'Error: ' + event.content;
      showToast(event.content, 'error');
      break;
  }
}

function addToolCard(name, status = 'calling') {
  const card = document.createElement('div');
  card.className = 'tool-card';

  const iconClass = status === 'calling' ? 'calling' : 'done';
  const iconContent = status === 'calling'
    ? '<i class="bi bi-arrow-repeat" style="animation:spin 1s linear infinite;"></i>'
    : '<i class="bi bi-check"></i>';

  card.innerHTML = `
    <div class="tool-name">
      <div class="tool-status-icon ${iconClass}">${iconContent}</div>
      ${name.replace(/_/g, ' ')}
    </div>
    <div class="tool-data">Calling MCP tool...</div>
  `;

  // Style for spin animation
  const styleEl = document.getElementById('spin-style');
  if (!styleEl) {
    const s = document.createElement('style');
    s.id = 'spin-style';
    s.textContent = '@keyframes spin { from{transform:rotate(0)} to{transform:rotate(360deg)} }';
    document.head.appendChild(s);
  }

  // Remove empty state if present
  const emptyState = toolFeed.querySelector('div[style*="text-align"]');
  if (emptyState) emptyState.remove();

  toolFeed.appendChild(card);
  toolFeed.scrollTop = toolFeed.scrollHeight;
  return card;
}

function finalize(fullText) {
  // Extract agent message (before ```html)
  const htmlStart = fullText.indexOf('```html');
  if (htmlStart !== -1) {
    const preText = fullText.slice(0, htmlStart).trim();
    if (preText) {
      agentBubbleText.textContent = preText;
    } else {
      agentBubble.style.display = 'none';
    }

    // Extract HTML
    const extractStart = htmlStart + 7;
    const htmlEnd = fullText.lastIndexOf('```');
    if (htmlEnd > extractStart) {
      state.generatedHTML = fullText.slice(extractStart, htmlEnd).trim();
    } else {
      state.generatedHTML = fullText.slice(extractStart).trim();
    }

    // Render preview
    if (state.generatedHTML) {
      renderPreview(state.generatedHTML);
      codeBadge.style.display = 'inline-flex';
      btnCopyCode.style.display = 'flex';
      showToast('Interface generated successfully', 'success');
    }
  } else {
    // No HTML block, just show text
    agentBubbleText.textContent = fullText;
    showToast('Response received', 'info');
  }

  // Final code display with syntax highlighting
  if (state.generatedHTML) {
    try {
      const highlighted = hljs.highlight(state.generatedHTML, { language: 'html' }).value;
      codeOutput.innerHTML = highlighted;
    } catch(e) {
      codeOutput.textContent = state.generatedHTML;
    }
  }

  setStatus(state.generatedHTML ? 'Interface generated successfully' : 'Response received', 'success');
  progressBar.style.display = 'none';
}

function renderPreview(html) {
  previewContainer.style.display = 'block';
  const iframe = previewIframe;
  iframe.srcdoc = html;

  // Adjust iframe height after load
  iframe.onload = () => {
    try {
      const body = iframe.contentDocument.body;
      const h = Math.max(body.scrollHeight, 500);
      iframe.style.height = Math.min(h, 800) + 'px';
    } catch(e) {
      iframe.style.height = '600px';
    }
  };
}

function setStatus(text, type = '') {
  statusText.textContent = text;
  statusText.className = type ? `active ${type}` : '';
}

// ─── Toast ───────────────────────────────────────────────────────────────────
function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  const icons = { success: 'bi-check-circle-fill', error: 'bi-x-circle-fill', info: 'bi-info-circle-fill' };
  const colors = { success: 'var(--accent-green)', error: 'var(--accent-red)', info: 'var(--accent-blue)' };

  const toast = document.createElement('div');
  toast.className = `toast-item ${type}`;
  toast.innerHTML = `
    <i class="bi ${icons[type] || icons.info}" style="color:${colors[type] || colors.info}; font-size:16px; flex-shrink:0;"></i>
    <span></span>
  `;
  toast.querySelector('span').textContent = message;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(10px)';
    toast.style.transition = 'all 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}

async function loadConfiguration() {
  const badge = document.getElementById('connection-status');
  try {
    const response = await fetch('/health');
    if (!response.ok) throw new Error('Backend unavailable');
    const config = await response.json();
    badge.textContent = config.gemini_configured ? 'Gemini configured' : 'Gemini key required';
    document.getElementById('model-description').textContent = `Model: ${config.model}`;
    document.getElementById('mcp-description').textContent = config.mcp_enabled
      ? 'MCP demo tools enabled (simulated data)'
      : 'MCP disabled; Gemini can generate with sample data';
    if (!config.gemini_configured && !state.isGenerating) setStatus('Configure GEMINI_API_KEY on the server', 'error');
  } catch {
    badge.textContent = 'Backend unavailable';
    if (!state.isGenerating) setStatus('Start the Python server to use Gemini', 'error');
  }
}
loadConfiguration();