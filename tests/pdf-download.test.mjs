import assert from 'node:assert/strict';
import test from 'node:test';
import vm from 'node:vm';
import { readFileSync } from 'node:fs';

const source = readFileSync(new URL('../static/app.js', import.meta.url), 'utf8');

// ─── Static contract: actions are split, download never prints ────────────
test('print_pdf keeps printResponse; download_pdf routes to downloadPdf', () => {
  assert.ok(source.includes("data.action === 'print_pdf'"));
  assert.ok(source.includes("data.action === 'download_pdf'"));
  assert.ok(source.includes('async function downloadPdf()'));
  const handler = source.slice(source.indexOf('── A2UI feedback loop'), source.indexOf('/* ─── Real A2UI:'));
  assert.match(handler, /print_pdf.*printResponse\(\)/s);
  assert.match(handler, /download_pdf.*downloadPdf\(\)/s);
  assert.ok(!/download_pdf[\s\S]{0,200}printResponse\(\)/.test(handler),
    'download_pdf must not call printResponse');
});

test('downloadPdf posts to /api/pdf and never calls window.print', () => {
  const body = source.slice(source.indexOf('async function downloadPdf()'), source.indexOf('// ─── Tools drawer:'));
  assert.ok(body.includes('/api/pdf'));
  assert.ok(!body.includes('window.print'), 'download must not use window.print');
  assert.ok(body.includes('state.isGenerating'));
  assert.ok(body.includes('state.generatedHTML'));
  assert.ok(body.includes('response.ok'));
  assert.ok(body.includes('response.blob()'));
  assert.ok(body.includes('createObjectURL'));
  assert.ok(body.includes('revokeObjectURL'));
  assert.ok(body.includes('authHeaders()'));
  assert.ok(body.includes('pdf_downloaded'));
  assert.ok(body.includes('pdf_download_fail'));
});

test('es/en translations exist for the download flow', () => {
  for (const key of ['pdf_empty', 'pdf_busy', 'pdf_downloaded', 'pdf_download_fail']) {
    assert.ok(source.includes(key), `missing i18n key ${key}`);
  }
  assert.ok(source.includes('No se pudo descargar el PDF'));
  assert.ok(source.includes('Could not download the PDF'));
});

// ─── Behavioral harness: real printResponse/downloadPdf/handler sources ────
const printSrc = source.slice(
  source.indexOf('function printResponse()'),
  source.indexOf("$('btn-print-pdf').addEventListener"),
);
const downloadSrc = source.slice(
  source.indexOf('async function downloadPdf()'),
  source.indexOf('// ─── Tools drawer:'),
);
const handlerSrc = source.slice(
  source.indexOf('// ─── A2UI feedback loop'),
  source.indexOf('/* ─── Real A2UI:'),
);
const tick = () => new Promise((resolve) => setImmediate(resolve));

function harness({ fetchImpl, html = '<h1>Plan $1,220</h1>', generating = false } = {}) {
  const toasts = [];
  const calls = { printView: 0, fetch: [], windowPrint: 0, opened: [], revoked: [], clicked: [] };
  const anchors = [];
  const state = { isGenerating: generating, generatedHTML: html };
  let receive;
  const anchor = () => {
    const a = { href: '', download: '' };
    a.click = () => calls.clicked.push(a.download);
    a.remove = () => {};
    anchors.push(a);
    return a;
  };
  const ctx = vm.createContext({
    state, lang: 'es', Blob, Response,
    t: (k) => k,
    showToast: (...args) => toasts.push(args),
    authHeaders: () => ({ Authorization: 'Bearer test-token' }),
    openPrintView: () => { calls.printView += 1; return true; },
    fetch: fetchImpl || (async (url, options) => {
      calls.fetch.push({ url, ...options });
      return new Response('%PDF-1.4 fake', {
        status: 200,
        headers: {
          'content-type': 'application/pdf',
          'content-disposition': 'attachment; filename="glintmesh-interface-123.pdf"',
        },
      });
    }),
    URL: {
      createObjectURL: () => { calls.opened.push(1); return 'blob:mock'; },
      revokeObjectURL: () => { calls.revoked.push(1); },
    },
    document: { createElement: (tag) => (tag === 'a' ? anchor() : {}), body: { appendChild() {} } },
    window: {
      addEventListener(type, cb) { assert.equal(type, 'message'); receive = cb; },
      print: () => { calls.windowPrint += 1; },
    },
    previewIframe: { contentWindow: {} },
    agentBubble: { style: { display: 'flex' } },
    agentBubbleText: { textContent: 'Respuesta' },
    handleSubmit: () => { throw new Error('should not submit for pdf actions'); },
    $: () => ({ addEventListener() {} }),
  });
  ctx.previewIframe.contentWindow = {};
  vm.runInContext(`${printSrc}\n${downloadSrc}\n${handlerSrc}`, ctx);
  return {
    ctx, state, toasts, calls,
    send(data) { return receive({ source: ctx.previewIframe.contentWindow, data }); },
  };
}

test('print_pdf still opens the print view and never hits /api/pdf', async () => {
  const h = harness();
  h.send({ glintmesh: true, action: 'print_pdf', label: 'Imprimir', payload: {} });
  await tick();
  assert.equal(h.calls.printView, 1);
  assert.equal(h.calls.fetch.length, 0);
  assert.equal(h.calls.windowPrint, 0);
});

test('download_pdf posts HTML to /api/pdf and downloads a .pdf file', async () => {
  const h = harness({ html: '<h1>Hola</h1>' });
  h.send({ glintmesh: true, action: 'download_pdf', label: 'Guardar PDF', payload: {} });
  await tick(); await tick();
  assert.equal(h.calls.printView, 0);
  assert.equal(h.calls.windowPrint, 0);
  assert.equal(h.calls.fetch.length, 1);
  assert.equal(h.calls.fetch[0].url, '/api/pdf');
  assert.equal(h.calls.fetch[0].method, 'POST');
  assert.deepEqual(JSON.parse(h.calls.fetch[0].body), { html: '<h1>Hola</h1>' });
  assert.equal(h.calls.fetch[0].headers.Authorization, 'Bearer test-token');
  assert.ok(h.calls.clicked.length === 1);
  assert.ok(h.calls.clicked[0].endsWith('.pdf'));
  assert.equal(h.calls.opened.length, 1);
  assert.equal(h.calls.revoked.length, 1);
  assert.ok(h.toasts.some(([msg, kind]) => msg === 'pdf_downloaded' && kind === 'success'));
});

test('HTTP errors show an error toast and no file is downloaded', async () => {
  const seen = [];
  const h = harness({
    fetchImpl: async (url, options) => {
      seen.push({ url, ...options });
      return { ok: false, status: 500, headers: { get: () => null }, blob: async () => { throw new Error('no blob'); } };
    },
  });
  h.send({ glintmesh: true, action: 'download_pdf', label: 'Guardar PDF', payload: {} });
  await tick(); await tick();
  assert.equal(seen.length, 1);
  assert.equal(seen[0].url, '/api/pdf');
  assert.equal(h.calls.clicked.length, 0);
  assert.equal(h.calls.windowPrint, 0);
  assert.ok(h.toasts.some(([msg, kind]) => msg === 'pdf_download_fail' && kind === 'error'));
});

test('no download while generating (loop guard stays silent, as before)', async () => {
  const h = harness({ generating: true, html: '<h1>x</h1>' });
  h.send({ glintmesh: true, action: 'download_pdf', label: 'Guardar PDF', payload: {} });
  await tick(); await tick();
  assert.equal(h.calls.fetch.length, 0);
  assert.equal(h.calls.clicked.length, 0);
  assert.equal(h.calls.windowPrint, 0);
});

test('direct downloadPdf() call while generating toasts and skips fetch', async () => {
  const h = harness({ generating: true, html: '<h1>x</h1>' });
  await h.ctx.downloadPdf();
  assert.equal(h.calls.fetch.length, 0);
  assert.equal(h.calls.clicked.length, 0);
  assert.ok(h.toasts.some(([msg]) => msg === 'pdf_busy'));
});

test('no download without generated HTML', async () => {
  const h = harness({ html: '' });
  h.send({ glintmesh: true, action: 'download_pdf', label: 'Guardar PDF', payload: {} });
  await tick(); await tick();
  assert.equal(h.calls.fetch.length, 0);
  assert.equal(h.calls.clicked.length, 0);
  assert.ok(h.toasts.length > 0);
});
