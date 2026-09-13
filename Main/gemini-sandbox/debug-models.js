import { apiKey } from './config.js';

async function listModels() {
  let pageToken;
  do {
    const url = new URL('https://generativelanguage.googleapis.com/v1beta/models');
    if (pageToken) url.searchParams.set('pageToken', pageToken);
    const response = await fetch(url, { headers: { 'x-goog-api-key': apiKey } });
    const data = await response.json();
    if (!response.ok) throw new Error(`HTTP ${response.status}: ${data.error?.message}`);
    for (const model of data.models ?? []) {
      if (model.supportedGenerationMethods?.includes('generateContent')) console.log(model.name);
    }
    pageToken = data.nextPageToken;
  } while (pageToken);
}

listModels().catch(error => {
  console.error('Error al listar modelos:', error.message);
  process.exitCode = 1;
});