# GlintMesh — A2UI over MCP Interface Mesh

Generador de interfaces financieras con UI web, FastAPI y Gemini. Describes un dashboard en lenguaje natural, GlintMesh trae datos MCP (live Yahoo + ECB + demo) y los renderiza como superficies A2UI en segundos, sin costo por refresh.

**Pitch (30s):** los dashboards financieros tardan días y mezclan datos falsos con reales. GlintMesh genera la interfaz con Gemini, etiqueta cada dato (LIVE / SIM / USER), refresca sin gastar cuota y te avisa cuando un precio cruza tu umbral. Todo corre local con FastAPI + MCP estándar.

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

```powershell
docker build -t glintmesh .
docker run --rm -p 8000:8000 -e GEMINI_API_KEY=tu_clave -e MCP_ENABLED=true glintmesh
```

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

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
node --test tests/sse.test.mjs
```

Las pruebas del backend simulan Gemini y comprueban también el servidor MCP local por stdio. Las pruebas de JavaScript verifican que el streaming conserve eventos y caracteres UTF-8 cuando llegan fragmentados. No necesitan una clave real ni consumen cuota de Gemini.

`gemini-sandbox/` conserva el chat de consola y los cinco ejemplos independientes (`npm run chat`, `npm run step1` a `step5`). No es necesario ejecutar Node.js para usar la UI web.
