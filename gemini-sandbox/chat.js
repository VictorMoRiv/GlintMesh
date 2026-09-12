import { createInterface } from 'node:readline/promises';
import { stdin, stdout } from 'node:process';
import { genAI, modelName } from './config.js';

async function run() {
  const chat = genAI.getGenerativeModel({ model: modelName }).startChat();
  const terminal = createInterface({ input: stdin, output: stdout });
  const shutdown = new AbortController();

  terminal.once('close', () => {
    shutdown.abort();
    console.log('\nChat cerrado.');
  });

  const exit = () => {
    terminal.close();
    process.exit(0);
  };
  terminal.on('SIGINT', exit);
  process.on('SIGINT', exit);

  console.log('Chat con Gemini. Escribe tu mensaje y presiona Enter.');
  console.log('Usa /salir o Ctrl+C para terminar. La memoria dura esta sesión.\n');

  try {
    while (!shutdown.signal.aborted) {
      const message = (await terminal.question('Tú: ', { signal: shutdown.signal })).trim();
      if (message.toLowerCase() === '/salir') break;
      if (!message) continue;

      try {
        const result = await chat.sendMessage(message, { signal: AbortSignal.timeout(60000) });
        if (!shutdown.signal.aborted) console.log(`Gemini: ${result.response.text()}\n`);
      } catch (error) {
        if (shutdown.signal.aborted) break;
        // No imprimir el error original: puede contener datos de la petición.
        const hint = error.status === 429
          ? 'Se alcanzó el límite de uso. Espera un momento e inténtalo otra vez.'
          : 'No se pudo obtener una respuesta. Revisa tu conexión y la configuración de Gemini e inténtalo otra vez.';
        console.error(`Gemini: ${hint}\n`);
      }
    }
  } catch (error) {
    if (!shutdown.signal.aborted) throw error;
  } finally {
    terminal.close();
    process.removeListener('SIGINT', exit);
  }
}

run().catch(() => {
  console.error('No se pudo iniciar o continuar el chat. Revisa la configuración y vuelve a ejecutar npm run chat.');
  process.exitCode = 1;
});
