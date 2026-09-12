# GlintMesh / FinFlow AI

Generador de interfaces financieras con una UI web, FastAPI y Gemini. El usuario escribe en la interfaz y recibe la respuesta progresivamente. Las solicitudes de dashboards generan HTML que se muestra en Preview, Code y Export; los saludos reciben una respuesta de texto.

## Ejecutar en Windows (PowerShell)

Requiere Python 3.11 o posterior.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edita `.env` y configura tu clave de Google AI Studio. Si ya tienes `.env`, conserva tu archivo en lugar de ejecutar `Copy-Item`.

```dotenv
GEMINI_API_KEY=tu_clave_de_google_ai_studio
GEMINI_MODEL=gemini-3.6-flash
MCP_ENABLED=false
# GEMINI_API_KEYS=key1,key2
# GEMINI_MODELS=gemini-3.6-flash,gemini-3-flash-preview
```

Ante límite de cuota (429) el backend rota keys y prueba los modelos en orden antes de fallar.

El modelo predeterminado es el que se verificó con el sandbox. Puedes cambiarlo usando `GEMINI_MODEL`. La clave se lee exclusivamente en el backend; `.env` está excluido de Git. No pongas claves en `static/`.

```powershell
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

Abre **http://127.0.0.1:8000**. Usa el servidor Python para abrir la UI, ya que necesita los endpoints del backend.

1. Escribe `Hola` y comprueba la respuesta de Gemini.
2. Pide `Genera una tarjeta de utilidad neta de $482,300, variación +12%, con datos de ejemplo`.
3. Comprueba Preview, Code y Export. Clear cancela una generación en curso y limpia la interfaz.

Las solicitudes son independientes; la UI todavía no guarda historial entre generaciones. El chat de consola del sandbox conserva su propia conversación mientras está abierto.

## MCP opcional

La UI funciona sin MCP con `MCP_ENABLED=false`. Para probar las ocho herramientas locales de demostración, cambia a `MCP_ENABLED=true` y reinicia el backend. Se usa el SDK oficial MCP v1 (`mcp>=1.20,<2`) y su servidor FastMCP.

Las cotizaciones, carteras, índices, noticias y tipos de cambio de `mcp_server.py` son **simulados**, no datos financieros en vivo. Gemini recibe esta indicación y debe etiquetar los ejemplos. No se incluyen conexiones a proveedores reales pendientes de implementación.

Con MCP activado, el backend obtiene los esquemas, entrega las herramientas a Gemini, ejecuta las llamadas por MCP y devuelve sus resultados a Gemini. La UI muestra las llamadas y los resultados. Si el MCP habilitado no está disponible, se muestra un error; puedes desactivarlo para seguir usando Gemini.

## API

- `GET /`: interfaz web.
- `POST /api/generate`: JSON `{"message":"...", "lang":"es"|"en", "context":"optional prior-turn summary"}`; `message` 1-500 chars, `context` hasta 2000. Respuesta SSE con eventos `status`, `text_chunk`, `tool_call`, `tool_result`, `error` y `done`. La UI guarda la última sesión en localStorage y reenvía su resumen como `context` para continuidad.
- `GET /api/tools`: herramientas disponibles; lista vacía cuando MCP está desactivado.
- `GET /health`: modelo y presencia de configuración, sin exponer la clave. No realiza una llamada de validación a Gemini.

Los errores de validación usan HTTP 422; una clave sin configurar usa HTTP 503. Los errores ocurridos durante la generación usan el evento SSE `error` y no emiten `done`.

## Pruebas

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
node --test tests/sse.test.mjs
```

Las pruebas del backend simulan Gemini y comprueban también el servidor MCP local por stdio. Las pruebas de JavaScript verifican que el streaming conserve eventos y caracteres UTF-8 cuando llegan fragmentados. No necesitan una clave real ni consumen cuota de Gemini.

`gemini-sandbox/` conserva el chat de consola y los cinco ejemplos independientes (`npm run chat`, `npm run step1` a `step5`). No es necesario ejecutar Node.js para usar la UI web.