// A network read can contain half an event or several events, including split UTF-8 characters.
export async function* readSSE(body) {
  if (!body) throw new Error('The server returned no response stream.');
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  const parse = frame => {
    const data = frame.split(/\r?\n/)
      .filter(line => line.startsWith('data:'))
      .map(line => line.slice(5).replace(/^ /, ''))
      .join('\n');
    return data ? JSON.parse(data) : null;
  };
  try {
    while (true) {
      const { value, done } = await reader.read();
      buffer += done ? decoder.decode() : decoder.decode(value, { stream: true });
      let boundary;
      while ((boundary = /\r?\n\r?\n/.exec(buffer))) {
        const frame = buffer.slice(0, boundary.index);
        buffer = buffer.slice(boundary.index + boundary[0].length);
        const event = parse(frame);
        if (event) yield event;
      }
      if (done) {
        if (buffer.trim()) {
          const event = parse(buffer);
          if (event) yield event;
        }
        break;
      }
    }
  } finally {
    await reader.cancel().catch(() => {});
    reader.releaseLock();
  }
}