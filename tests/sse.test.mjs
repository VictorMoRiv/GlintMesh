import test from 'node:test';
import assert from 'node:assert/strict';
import { readSSE } from '../static/sse.mjs';

const encoder = new TextEncoder();
function stream(chunks) {
  return new ReadableStream({ start(controller) {
    chunks.forEach(chunk => controller.enqueue(chunk));
    controller.close();
  }});
}
async function collect(body) {
  const events = [];
  for await (const event of readSSE(body)) events.push(event);
  return events;
}

test('preserves JSON and UTF-8 split at every byte', async () => {
  const events = [{ type: 'text_chunk', content: '¡Hola! Utilidad: $482,300' }, { type: 'done' }];
  const bytes = encoder.encode(events.map(e => `data: ${JSON.stringify(e)}\n\n`).join(''));
  assert.deepEqual(await collect(stream(Array.from(bytes, byte => Uint8Array.of(byte)))), events);
});

test('handles CRLF, comments and multiple events in one read', async () => {
  const data = ': ping\r\n\r\ndata: {"type":"status","content":"Ready"}\r\n\r\ndata:{"type":"done"}\r\n\r\n';
  assert.deepEqual(await collect(stream([encoder.encode(data)])), [{ type: 'status', content: 'Ready' }, { type: 'done' }]);
});

test('reads final event without trailing blank line', async () => {
  assert.deepEqual(await collect(stream([encoder.encode('data: {"type":"done"}')])), [{ type: 'done' }]);
});

test('rejects malformed/truncated JSON instead of silently losing output', async () => {
  await assert.rejects(collect(stream([encoder.encode('data: {"type":"text_chunk"')])), SyntaxError);
});

test('cancels the reader when the consumer stops at done', async () => {
  let cancelled = false;
  const body = new ReadableStream({
    start(controller) { controller.enqueue(encoder.encode('data: {"type":"done"}\n\n')); },
    cancel() { cancelled = true; },
  });
  for await (const event of readSSE(body)) { assert.equal(event.type, 'done'); break; }
  assert.equal(cancelled, true);
});