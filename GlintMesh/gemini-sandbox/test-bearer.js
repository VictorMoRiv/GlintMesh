import { apiKey, modelName } from './config.js';

// Las claves API se envian en x-goog-api-key, incluido el formato AQ.
async function testToken() {
  const url = `https://generativelanguage.googleapis.com/v1beta/models/${modelName}:generateContent`;
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'x-goog-api-key': apiKey, 'Content-Type': 'application/json' },
    body: JSON.stringify({ contents: [{ parts: [{ text: 'Hola, responde brevemente.' }] }] }),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(`HTTP ${response.status}: ${data.error?.message}`);
  console.log('Conexion correcta:', data.candidates?.[0]?.content?.parts?.map(part => part.text ?? '').join(''));
}

testToken().catch(error => {
  console.error('Error de conexion:', error.message);
  process.exitCode = 1;
});