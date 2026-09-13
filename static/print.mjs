// The printable window is owned by GlintMesh. Generated code only runs in its opaque iframe.
const PRINT_TAGS = new Set(['div', 'section', 'article', 'main', 'header', 'footer', 'p', 'span', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'ul', 'ol', 'li', 'table', 'thead', 'tbody', 'tfoot', 'tr', 'td', 'th', 'caption', 'strong', 'b', 'em', 'i', 'small', 'dl', 'dt', 'dd', 'hr', 'br', 'pre', 'code', 'blockquote', 'figure', 'figcaption']);

// Rebuild an allowlisted tree with DOM APIs: never accept HTML, attributes, URLs or scripts.
export function renderPrintTree(doc, nodes) {
  let count = 0, characters = 0;
  function render(node, depth) {
    if (++count > 20000 || depth > 50 || !node || typeof node !== 'object') throw new Error('Invalid print content');
    if (typeof node.text === 'string') {
      characters += node.text.length;
      if (characters > 2000000) throw new Error('Print content too large');
      return doc.createTextNode(node.text);
    }
    if (node.tag === 'img') {
      if (typeof node.png !== 'string' || !/^data:image\/png;base64,[A-Za-z0-9+/]+=*$/.test(node.png) || node.png.length > 12000000) throw new Error('Invalid print image');
      characters += node.png.length;
      if (characters > 16000000) throw new Error('Print content too large');
      const img = doc.createElement('img');
      img.src = node.png;
      img.alt = typeof node.alt === 'string' ? node.alt.slice(0, 200) : '';
      return img;
    }
    if (!PRINT_TAGS.has(node.tag) || !Array.isArray(node.children)) throw new Error('Invalid print element');
    const el = doc.createElement(node.tag);
    for (const key of ['colSpan', 'rowSpan']) {
      if (['td', 'th'].includes(node.tag) && Number.isInteger(node[key]) && node[key] > 0 && node[key] <= 100) el[key] = node[key];
    }
    for (const child of node.children) el.appendChild(render(child, depth + 1));
    return el;
  }
  if (!Array.isArray(nodes)) throw new Error('Invalid print document');
  const fragment = doc.createDocumentFragment();
  for (const node of nodes) fragment.appendChild(render(node, 0));
  return fragment;
}

export function openPrintView({ html = '', text = '', lang = 'es' }) {
  const es = lang !== 'en';
  const popup = window.open('about:blank', '_blank');
  if (!popup) return false;
  popup.opener = null;
  const doc = popup.document;
  doc.documentElement.lang = es ? 'es' : 'en';
  doc.title = 'GlintMesh - ' + (es ? 'Respuesta' : 'Response');
  const style = doc.createElement('style');
  style.textContent = [
    '@page { size: A4; margin: 14mm; }',
    '* { box-sizing: border-box; }',
    'body { margin: 0; background: #e9edf2; color: #172033; font: 14px/1.5 system-ui, sans-serif; }',
    '.print-controls { padding: 16px; text-align: center; }',
    'button { padding: 10px 20px; border: 0; border-radius: 6px; background: #146c55; color: white; cursor: pointer; font: inherit; }',
    'button:disabled { opacity: .5; cursor: wait; }',
    '#print-content { width: 182mm; margin: 0 auto 24px; padding: 20px; background: white; overflow-wrap: anywhere; }',
    'h1, h2, h3, h4, h5, h6 { color: #146c55; line-height: 1.25; break-after: avoid; }',
    'p, li { orphans: 3; widows: 3; }',
    'table { width: 100%; border-collapse: collapse; margin: 16px 0; table-layout: fixed; }',
    'th, td { border: 1px solid #d5dde5; padding: 8px; text-align: left; vertical-align: top; }',
    'th { background: #edf5f2; }',
    'tr, figure, img { break-inside: avoid; }',
    'thead { display: table-header-group; }',
    'img { display: block; max-width: 100%; max-height: 240mm; object-fit: contain; margin: 12px auto; }',
    'pre { white-space: pre-wrap; overflow-wrap: anywhere; font: inherit; }',
    '@media print { body { background: white; } .print-controls { display: none; } #print-content { width: auto; margin: 0; padding: 0; } * { -webkit-print-color-adjust: exact; print-color-adjust: exact; } }',
  ].join('\n');
  doc.head.appendChild(style);
  const controls = doc.createElement('div');
  controls.className = 'print-controls';
  const button = doc.createElement('button');
  button.type = 'button';
  button.disabled = true;
  button.textContent = es ? 'Imprimir / Guardar PDF' : 'Print / Save PDF';
  const note = doc.createElement('p');
  note.textContent = es ? 'Preparando la respuesta…' : 'Preparing the response…';
  controls.append(button, note);
  const main = doc.createElement('main');
  main.id = 'print-content';
  doc.body.replaceChildren(controls, main);
  button.addEventListener('click', () => { popup.focus(); popup.print(); });

  async function ready() {
    await Promise.all(Array.from(main.querySelectorAll('img'), img => img.decode().catch(() => {})));
    await doc.fonts.ready;
    if (popup.closed) return;
    button.disabled = false;
    note.textContent = es
      ? 'Elige una impresora o selecciona "Guardar como PDF" como destino y pulsa Guardar.'
      : 'Choose a printer or select "Save as PDF" as the destination, then Save.';
    popup.setTimeout(() => { if (!popup.closed) { popup.focus(); popup.print(); } }, 150);
  }
  if (!html) {
    const content = doc.createElement('pre');
    content.textContent = text;
    main.appendChild(content);
    void ready();
    return true;
  }

  const frame = doc.createElement('iframe');
  frame.title = es ? 'Preparando respuesta' : 'Preparing response';
  frame.setAttribute('sandbox', 'allow-scripts');
  frame.style.cssText = 'position:absolute;left:-10000px;width:182mm;height:600px;border:0';
  const parsed = new DOMParser().parseFromString(html, 'text/html');
  const snapshot = parsed.createElement('script');
  snapshot.textContent = '(' + collectPrintContent.toString() + ')(' + JSON.stringify([...PRINT_TAGS]) + ',' + JSON.stringify(es) + ');';
  parsed.body.appendChild(snapshot);
  let completed = false;
  function fail() {
    if (completed) return;
    completed = true;
    frame.remove();
    popup.removeEventListener('message', receive);
    note.textContent = es ? 'No se pudo preparar la respuesta. Cierra esta vista y vuelve a intentar.' : 'Could not prepare the response. Close this view and try again.';
  }
  const timeout = popup.setTimeout(fail, 20000);
  function receive(event) {
    if (completed || event.source !== frame.contentWindow) return;
    const data = event.data;
    if (!data || data.glintmeshPrint !== true || !Array.isArray(data.nodes)) return;
    try {
      const content = renderPrintTree(doc, data.nodes);
      completed = true;
      popup.clearTimeout(timeout);
      popup.removeEventListener('message', receive);
      frame.remove();
      main.replaceChildren(content);
      void ready();
    } catch (e) { fail(); }
  }
  popup.addEventListener('message', receive);
  frame.srcdoc = '<!doctype html>\n' + parsed.documentElement.outerHTML;
  doc.body.appendChild(frame);
  return true;
}

// Runs only in the sandboxed copy. Return plain text, structural tags and PNGs, never HTML.
function collectPrintContent(tags, es) {
  const allowed = new Set(tags);
  const skip = new Set(['SCRIPT', 'STYLE', 'LINK', 'META', 'BASE', 'NOSCRIPT', 'TEMPLATE', 'BUTTON', 'IFRAME', 'OBJECT', 'EMBED']);
  let count = 0;
  function collect(node, depth = 0) {
    if (++count > 20000 || depth > 50) throw new Error('Print content too large');
    if (node.nodeType === Node.TEXT_NODE) return node.textContent ? [{text: node.textContent}] : [];
    if (node.nodeType !== Node.ELEMENT_NODE || skip.has(node.tagName) || node.getAttribute('role') === 'button') return [];
    const style = getComputedStyle(node);
    if (style.display === 'none' || style.visibility === 'hidden') return [];
    if (node.tagName === 'INPUT') return ['hidden', 'password', 'button', 'submit', 'reset'].includes(node.type) ? [] : [{tag:'span', children:[{text: ['checkbox', 'radio'].includes(node.type) ? (node.checked ? '☑' : '☐') : node.value}]}];
    if (node.tagName === 'SELECT' || node.tagName === 'TEXTAREA') return [{tag:'span', children:[{text: node.tagName === 'SELECT' ? Array.from(node.selectedOptions, o => o.text).join(', ') : node.value}]}];
    if (node.tagName === 'CANVAS' || node.tagName === 'IMG') {
      try {
        let canvas = node;
        if (node.tagName === 'IMG') {
          canvas = document.createElement('canvas');
          canvas.width = node.naturalWidth; canvas.height = node.naturalHeight;
          canvas.getContext('2d').drawImage(node, 0, 0);
        }
        const png = canvas.toDataURL('image/png');
        if (!png.startsWith('data:image/png;base64,')) throw new Error('Empty image');
        return [{tag:'img', png, alt: node.getAttribute('aria-label') || node.alt || ''}];
      } catch (e) {
        return [{tag:'p', children:[{text: es ? '[Imagen no disponible para imprimir]' : '[Image unavailable for printing]'}]}];
      }
    }
    const children = Array.from(node.childNodes).flatMap(child => collect(child, depth + 1));
    const tag = node.tagName.toLowerCase();
    if (!allowed.has(tag)) return children;
    if (!children.length && !['hr', 'br'].includes(tag)) return [];
    return [{tag, children, ...(['td', 'th'].includes(tag) ? {colSpan:node.colSpan, rowSpan:node.rowSpan} : {})}];
  }
  window.addEventListener('load', async () => {
    await Promise.race([document.fonts.ready, new Promise(resolve => setTimeout(resolve, 3000))]);
    await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    try {
      for (const chart of Object.values(window.Chart?.instances || {})) chart.update('none');
      const nodes = collect(document.body);
      window.parent.postMessage({glintmeshPrint:true, nodes}, '*');
    } catch (e) { window.parent.postMessage({glintmeshPrint:true, nodes:[null]}, '*'); }
  }, {once:true});
}
