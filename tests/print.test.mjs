import assert from 'node:assert/strict';
import test from 'node:test';
import { renderPrintTree, openPrintView } from '../static/print.mjs';

function documentStub() {
  const node = (tag) => ({tag, children:[], appendChild(child) {this.children.push(child);}});
  return {
    createDocumentFragment: () => node('fragment'),
    createElement: node,
    createTextNode: text => ({text}),
  };
}
test('print tree preserves financial values, headings and table spans', () => {
  const tree = renderPrintTree(documentStub(), [{tag:'h1', children:[{text:'Plan de 18 meses'}]}, {tag:'table', children:[{tag:'tr', children:[{tag:'td', colSpan:2, children:[{text:'$1,220 | CAT 35.1% | Saldo $18,400'}]}]}]}]);
  assert.equal(tree.children[0].children[0].text, 'Plan de 18 meses');
  assert.equal(tree.children[1].children[0].children[0].colSpan, 2);
});
test('untrusted text is a text node, never interpreted as HTML', () => {
  const text = '<img src=x onerror=alert(1)><script>alert(1)</script>';
  assert.deepEqual(renderPrintTree(documentStub(), [{text}]).children[0], {text});
});
test('scripts, frames, forms and unknown elements are rejected', () => {
  for (const tag of ['script','iframe','form','object','embed','meta','link','svg','a','input','SCRIPT']) {
    assert.throws(() => renderPrintTree(documentStub(), [{tag, children:[]}]));
  }
});
test('all arbitrary attributes and styles are ignored', () => {
  const tree = renderPrintTree(documentStub(), [{tag:'p', onclick:'alert(1)', style:'position:fixed', id:'print-controls', src:'javascript:alert(1)', children:[{text:'safe'}]}]);
  assert.deepEqual(Object.keys(tree.children[0]).sort(), ['appendChild','children','tag']);
});
test('only embedded PNGs are permitted, no SVG or external URLs', () => {
  for (const png of ['https://example.com/x.png','javascript:alert(1)','data:image/svg+xml,<svg/>','data:image/png;base64,"><img src=x>']) {
    assert.throws(() => renderPrintTree(documentStub(), [{tag:'img',png}]));
  }
  const image = renderPrintTree(documentStub(), [{tag:'img',png:'data:image/png;base64,iVBORw0KGgo=',alt:'Gráfico'}]).children[0];
  assert.equal(image.src, 'data:image/png;base64,iVBORw0KGgo=');
});
test('invalid, oversized and deeply nested payloads are rejected', () => {
  for (const nodes of [null, {}, [null], [{tag:'p'}], [{text:'x'.repeat(2000001)}]]) assert.throws(() => renderPrintTree(documentStub(), nodes));
  let deep = {text:'leaf'};
  for (let i=0;i<55;i++) deep = {tag:'div',children:[deep]};
  assert.throws(() => renderPrintTree(documentStub(), [deep]));
  const cycle = {tag:'div',children:[]}; cycle.children.push(cycle);
  assert.throws(() => renderPrintTree(documentStub(), [cycle]));
  assert.throws(() => renderPrintTree(documentStub(), Array(20001).fill({text:'x'})));
});
test('invalid table spans are ignored', () => {
  for (const colSpan of [0, -1, 101, '2', 1.5]) {
    const cell = renderPrintTree(documentStub(), [{tag:'td',colSpan,children:[]}]).children[0];
    assert.equal(cell.colSpan, undefined);
  }
});
test('popup blocking returns false for app to show actionable feedback', () => {
  globalThis.window = {open: () => null};
  try { assert.equal(openPrintView({text:'response'}), false); }
  finally { delete globalThis.window; }
});
