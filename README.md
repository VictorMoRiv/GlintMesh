# GlintMesh — A2UI over MCP Interface Mesh

Generador de interfaces financieras con UI web, FastAPI, Gemini y DeepSeek. Describes un dashboard en lenguaje natural, GlintMesh trae datos MCP (live Yahoo + ECB + demo + MongoDB) y los renderiza como superficies A2UI en segundos, sin costo por refresh.

**Pitch (30s):** los dashboards financieros tardan días y mezclan datos falsos con reales. GlintMesh genera la interfaz con Gemini o DeepSeek, etiqueta cada dato (LIVE / SIM / USER / MONGODB), refresca sin gastar cuota y te avisa cuando un precio cruza tu umbral. Todo corre local con FastAPI + MCP estándar.

## Proveedores de LLM y Fallback Automático

GlintMesh soporta **Google Gemini** y **DeepSeek** (a través de su API compatible con OpenAI en `https://api.deepseek.com`), con selección de proveedor y tolerancia a fallos automática:

- `LLM_PROVIDER=auto` (predeterminado): intenta Gemini primero. Si Gemini devuelve **429, 401, 403, 500, 502 o 503**, el backend conmuta automáticamente a DeepSeek sin interrumpir al usuario.
- `LLM_PROVIDER=gemini`: utiliza exclusivamente Google Gemini con rotación de claves y modelos.
- `LLM_PROVIDER=deepseek`: utiliza directamente DeepSeek.

También es posible seleccionar el proveedor por solicitud en `POST /api/generate` enviando `"provider": "gemini" | "deepseek" | "auto"`.

### Mensajes de Error en Español
El backend proporciona mensajes de error claros y sanitizados en español para las siguientes condiciones:
- **Clave ausente**: `"Clave de API ausente. Configura GEMINI_API_KEY o DEEPSEEK_API_KEY en el archivo .env."`
- **Autenticación fallida** (401, 403): `"Autenticación fallida. Revisa la clave de API y sus permisos en el archivo .env."`
- **Cuota agotada** (429): `"Cuota agotada o límite de uso alcanzado. Revisa tus límites y facturación."`
- **Modelo no disponible** (404): `"Modelo no disponible. Revisa la configuración del modelo en el archivo .env."`
- **Error temporal del servicio** (500, 502, 503, 504, timeouts): `"Error temporal del servicio. El proveedor no está disponible temporalmente. Inténtalo de nuevo más tarde."`

### Seguridad de Credenciales
- Las claves se leen **exclusivamente desde `.env`**.
- Ninguna clave se expone en el frontend, logs, respuestas HTTP ni en Git (`.env` está en `.gitignore`).
- Las respuestas de error sanitizan automáticamente cualquier rastro de claves antes de emitir eventos SSE o respuestas JSON.

## Ejecutar en Windows (PowerShell)

Requiere Python 3.11 o posterior.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edita `.env` y configura tus claves. Si ya tienes `.env`, conserva tu archivo en lugar de ejecutar `Copy-Item`.

```dotenv
# Selección de proveedor de LLM: gemini | deepseek | auto (por defecto: auto)
LLM_PROVIDER=auto

# Configuración de Google Gemini
GEMINI_API_KEY=tu_clave_de_google_ai_studio
GEMINI_MODEL=gemini-3.6-flash
# Opcional: varias keys separadas por comas (rota ante 429) y varios modelos (fallback en orden):
# GEMINI_API_KEYS=key1,key2
# GEMINI_MODELS=gemini-3.6-flash,gemini-3-flash-preview

# Configuración de DeepSeek (API compatible con OpenAI: https://api.deepseek.com)
DEEPSEEK_API_KEY=tu_clave_de_deepseek
DEEPSEEK_MODEL=deepseek-chat
# DEEPSEEK_BASE_URL=https://api.deepseek.com

# MCP opcional (servidores de mercado y MongoDB)
MCP_ENABLED=false
MONGODB_URI=mongodb+srv://cluster0.iqh0irh.mongodb.net/
MONGODB_DATABASE=Datos_de_empresa
```

Inicia el servidor:

```powershell
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

Abre **http://127.0.0.1:8000**. Usa el servidor Python para abrir la UI, ya que necesita los endpoints del backend.

### Ejecución con Docker

```powershell
docker build -t glintmesh .
docker run --rm -p 8000:8000 --env-file .env glintmesh
```

## Guía rápida de uso

1. Escribe `Hola` y comprueba la respuesta del LLM configurado.
2. Pide `Genera una tarjeta de utilidad neta de $482,300, variación +12%, con datos de ejemplo`.
3. Comprueba **Preview**, **Code** y **Export**. **Clear** cancela una generación en curso y limpia la interfaz.

## MCP (Model Context Protocol)

La UI funciona sin MCP con `MCP_ENABLED=false`. Para activar los servidores de `mcp_servers.json`, cambia a `MCP_ENABLED=true` y reinicia el backend. Se usa el SDK oficial MCP (`mcp>=1.20,<3`), compatible con FastMCP v1 y MCPServer v2.

Tanto **Gemini** como **DeepSeek** tienen acceso completo e idéntico a todas las herramientas MCP:
- `mcp_server.py`: Cotizaciones, carteras, índices, noticias y tipos de cambio simulados.
- `mcp_yahoo.py`: Cotizaciones e históricos reales en vivo desde Yahoo Finance.
- `mcp_ecb.py`: Tipos de cambio oficiales del Banco Central Europeo.
- `mcp_mongodb.py`: Consultas seguras de solo lectura a MongoDB Atlas (`mongo_ping`, `mongo_list_databases`, `mongo_list_collections`, `mongo_get_schema`, `mongo_find`, `mongo_count`, `mongo_aggregate`).

Con MCP activado, el backend entrega las definiciones de herramientas al proveedor activo (en formato Gemini o en formato function calling de OpenAI para DeepSeek), ejecuta las llamadas por stdio y devuelve los resultados al modelo para componer las superficies A2UI.

## MongoDB integration

MongoDB se consulta exclusivamente desde el servidor: **Frontend → FastAPI → LLM (Gemini o DeepSeek) → MCP (stdio) → `database/mongodb.py` → MongoDB**. El agente dispone de siete herramientas de solo lectura: `mongo_ping`, `mongo_list_databases`, `mongo_list_collections`, `mongo_get_schema`, `mongo_find`, `mongo_count` y `mongo_aggregate`. No hay operaciones destructivas ni comandos arbitrarios.

1. Configura `.env` con las credenciales de MongoDB:

   ```dotenv
   MCP_ENABLED=true
   MONGODB_URI=mongodb+srv://<username>:<password>@<cluster>.mongodb.net/?retryWrites=true&w=majority
   MONGODB_DATABASE=finance
   ```

2. Comprueba la conexión sin gastar cuota del LLM:

   ```powershell
   Invoke-RestMethod http://127.0.0.1:8000/api/tool-call -Method Post -ContentType 'application/json' -Body '{"tool":"mongo_ping","args":{}}'
   Invoke-RestMethod http://127.0.0.1:8000/api/tool-call -Method Post -ContentType 'application/json' -Body '{"tool":"mongo_list_collections","args":{}}'
   ```

## API

- `GET /`: interfaz web.

- `POST /api/generate`: genera interfaz en streaming SSE. Acepta:
  - `message`: texto del usuario (1-500 caracteres).
  - `lang`: `"es"` | `"en"`.
  - `provider`: `"gemini"` | `"deepseek"` | `"auto"` (opcional, sobreescribe `LLM_PROVIDER`).
  - `model`: modelo específico (ej. `"gemini-3.6-flash"`, `"deepseek-chat"`).
  - `temperature`: float entre 0.0 y 1.0.
  - `mode`: `"full"` | `"data"`.
  - `context`: resumen del turno anterior para continuidad.
  - `dataset_id`: ID de dataset cargado.
  - `images`: lista de hasta 3 imágenes adjuntas en base64.
- `GET /health`: estado del servicio, modelos configurados (`gemini_configured`, `deepseek_configured`, `llm_provider`, etc.) sin exponer claves privadas.
- `POST /api/tool-call`: re-ejecuta una herramienta MCP directamente sin pasar por el LLM (refresh gratis de superficies A2UI).
- `GET /api/tools`: herramientas MCP disponibles agrupadas por servidor.
- `POST /api/datasets` / `GET /api/datasets` / `DELETE /api/datasets/{id}`: gestión de datasets CSV/JSON.
- `POST /api/share` / `GET /share/{id}`: compartir interfaces generadas.
- `POST /api/auth/register`, `/api/auth/login`, `/api/auth/logout`, `GET /api/auth/me`, `PUT /api/auth/avatar`: autenticación local.
- `POST /api/pdf`: descarga directa del HTML generado como PDF A4 (`attachment; filename="glintmesh-interface-<timestamp>.pdf"`).
- `GET /api/prefs` / `PUT /api/prefs`: preferencias por usuario (modelo, dataset, idioma, alertas).
- `POST /api/datasets`: sube CSV o JSON propio (máx 2 MB) a `uploads/`; devuelve columnas, filas y muestra.
- `GET /api/datasets`: datasets subidos con muestra de filas.
- `DELETE /api/datasets/{id}`: borra un dataset.
- `POST /api/tool-call`: re-ejecuta un MCP sin Gemini (refresh gratis de superficies A2UI).
- `POST /api/share` + `GET /share/{id}`: link compartible de una interfaz generada.
- `POST /api/generate`: JSON `{"message":"...", "lang":"es"|"en", "context":"resumen opcional", "dataset_id":"opcional", "images":[{"mime":"image/png","data":"base64"}]}`; `message` 1-500 chars, `context` hasta 2000, máx 3 imágenes (cada una 1.5 MB, png/jpeg/webp/gif) que llegan a Gemini como `inline_data`. Regla: solo gráficas financieras (charts, tablas, dashboards); si mandas un meme/perro/foto random no se rompe — responde en 1-2 frases que solo trabaja con gráficas y no genera HTML.
- `POST /api/auth/register` + `POST /api/auth/login` + `GET /api/auth/me` (Bearer, devuelve `user` y `avatar`) + `PUT /api/auth/avatar` (data URL png/jpeg/webp/gif, máx ~300 KB) + `POST /api/auth/logout`: cuentas locales en `users.json` (hash sha256+salt, gitignored). Invitado: tu sesión vive solo en la pestaña y se pierde al salir; con login se guarda en el navegador.
- `GET /api/tools`: herramientas disponibles; lista vacía cuando MCP está desactivado.
- `GET /health`: modelo y presencia de configuración, sin exponer la clave. No realiza una llamada de validación a Gemini.

## Live channel (WebSocket)

Además del streaming SSE de `/api/generate`, hay un canal persistente `GET /ws/live` (nativo FastAPI, sin dependencias extra; `?token=` opcional para login):

- **Ticks**: suscríbete con `{"op":"subscribe","symbols":["AAPL"],"watches":{"AAPL":{"above":200,"below":null}}}` y el servidor emite `tick` cada 15 s. La UI actualiza las tarjetas A2UI de cotización solas, sin gastar cuota de Gemini.
- **Alertas**: cuando un precio cruza tu umbral recibes `alert` (toast ámbar + badge en la píldora LIVE). Configúralas con el botón **Alertas** del tab A2UI.
- **Progreso cross-tab**: si generas en una pestaña, tus otras pestañas ven el progreso en vivo; al reconectar reciben el último estado.
- **Sync**: `GET/PUT /api/prefs` guarda modelo, dataset, idioma y alertas por usuario (invitados usan `localStorage` + `BroadcastChannel` solo en ese navegador). Cambiar algo en una pestaña lo refleja en las demás.

Los errores de validación usan HTTP 422; una clave sin configurar usa HTTP 503. Los errores ocurridos durante la generación usan el evento SSE `error` y no emiten `done`. La UI muestra el error con botón **Retry** en 1 clic, y el backend rota keys/modelos ante 429/404/5xx antes de fallar.

## Demo 3 minutos (ver DEMO-3MIN.md)

1. `Hola` → respuesta de texto (0:30). Micrófono para dictar (Web Speech API, Chrome/Edge) y clip para adjuntar hasta 3 gráficas que ve Gemini (memes/perros se rechazan con mensaje, sin romperse).
2. `Dashboard de portafolio AAPL, MSFT, NVDA` → Preview + A2UI + **Compose dashboard** combina N superficies en 1 (1:30).
3. **Refresh data** sin cuota + **Retry** en 1 clic si falla Gemini + **Sign in** con foto (invitado pierde todo al salir, logueado lo guarda) (1:00).

Compatibilidad: voz e imágenes con degradado — si el navegador no soporta dictado, el botón avisa; sin login todo sigue funcionando (demo-friendly).



## Pruebas

Para ejecutar la suite completa de pruebas unitarias y de integración:

```powershell
# Pruebas de Python (Gemini, DeepSeek, MCP, MongoDB, autenticación y seguridad)
.\.venv\Scripts\python.exe -m unittest discover -s tests -v

# Pruebas de SSE en JavaScript
node --test tests/sse.test.mjs
```

Las pruebas verifican:
- Respuesta correcta de DeepSeek en formato compatible con OpenAI.
- Fallback automático de Gemini a DeepSeek ante 429, 401, 403, 500, 502 y 503.
- Protección estricta: las claves nunca aparecen en frontend, logs ni respuestas HTTP.
- Integración completa de MCP (incluyendo MongoDB) con DeepSeek.
- Mensajes de error claros en español para clave ausente, autenticación fallida, cuota agotada, modelo no disponible y errores temporales de servicio.
