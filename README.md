# GlintMesh 💠 — Interfaces financieras generadas con IA

> Describe tu dashboard en lenguaje natural y GlintMesh lo construye en segundos: la IA entiende qué le pides, trae los datos en vivo vía MCP (Yahoo, BCE, MongoDB) y los renderiza como superficies A2UI listas para usar — sin escribir una sola línea de HTML.

---

## 📝 Descripción del Proyecto

Proyecto para el **HackMTY** enfocado en crear interfaces para el cliente usando **agentes de Inteligencia Artificial**, combinando **MCP** (Model Context Protocol), **A2UI** y **LLMs** para entender lo que el usuario le pide al servicio.

Aplicado al sector **financiero**, GlintMesh convierte un pedido en lenguaje natural en una interfaz comprensible en minutos: tarjetas, tablas, gráficas y dashboards completos con datos reales etiquetados — de forma fácil, cómoda y en menor tiempo.

## ⭐ Características principales

- **Creación de Interfaces**: el agente genera interfaces completas a partir de un prompt (Preview + Código + Export).
- **Vista de Código**: visualiza lo generado en formato HTML/CSS/JS para copiarlo o integrarlo.
- **Integración con Datos**: 4 servidores MCP conectan datos simulados, live de Yahoo Finance, tasas oficiales del BCE y MongoDB Atlas; también acepta CSV/JSON propios del usuario.
- **Datos etiquetados**: cada cifra se marca `LIVE` (Yahoo), `SIM` (demo), `USER` (CSV) o `MONGODB`, para nunca confundir realidad con ejemplo.
- **Refresh sin cuota**: vuelve a ejecutar una herramienta MCP sin pasar por el LLM, gratis.
- **Fallback automático**: si Gemini se queda sin cuota (429/401/403/5xx), conmuta a Groq/DeepSeek sin interrumpir.
- **Live channel (WebSocket)**: ticks cada 15 s, alertas por umbral de precio y sync entre pestañas.
- **Voz e imágenes**: dictado por micrófono y hasta 3 gráficas adjuntas que la IA analiza.
- **Login con foto**: cuentas locales con avatar; invitados pierden su sesión al salir.
- **PDF**: exporta la interfaz generada a PDF A4 directo, sin navegador externo.
- **Desplegable en Vercel**: listo para serverless (usa `/tmp` para datos efímeros).

## 🏗️ Arquitectura

```
                 ┌──────────────────────────────────────────────────────┐
  Navegador      │                        Backend                       │
 ┌────────────┐  │ ┌──────────────────────────────────────────────────┐ │
 │ index.html │  │ │                    FastAPI                       │ │
 │ app.js     │──┼▶│  main.py (routers + agent) + socket_events.py    │ │
 │ live.js    │◀─┼─│  socket_app  (Socket.io ASGI)                    │ │
 │ themes.json│  │ │ └──────────────┬─────────────────────────────────┘ │
 └────────────┘  │        SSE/WS    │ stream + tool calls              │
                 │                  ▼                                  │
                 │ ┌─────────────────────────────────────────────────┐ │
                 │ │         LLM Provider (auto / fallback)          │ │
                 │ │   Gemini ── 429/5xx ──▶ Groq ──▶ DeepSeek        │ │
                 │ └───────────────────┬─────────────────────────────┘ │
                 │                     │ function calling             │
                 │                     ▼                              │
                 │ ┌─────────────────────────────────────────────────┐ │
                 │ │      MCP (Model Context Protocol) — stdio       │ │
                 │ │  mcp_server.py  ─ Demo (simulado)               │ │
                 │ │  mcp_yahoo.py    ─ LIVE mercado real             │ │
                 │ │  mcp_ecb.py      ─ Tasas oficiales BCE           │ │
                 │ │  mcp_mongodb.py  ─ MongoDB Atlas (solo lectura)  │ │
                 │ └───────────────────┬─────────────────────────────┘ │
                 │                     ▼ persistencia / almacenamiento │
                 │  mongo_store.py (Motor) · users.json · uploads/     │
                 └─────────────────────────────────────────────────────┘
```

### Flujo de generación
1. El usuario pide una interfaz en lenguaje natural (+ opcional: voz, imágenes, CSV propio).
2. FastAPI arma el agente con `SYSTEM_PROMPT` (reglas anti-alucinación y etiquetas de datos).
3. El LLM activo decide qué herramientas MCP llamar; el backend las ejecuta por stdio.
4. Con los resultados reales, el modelo compone la superficie A2UI y la transmite por **SSE**.
5. La UI renderiza Preview / Código / A2UI, y puede **Compose** N superficies en 1, **Refresh** datos sin cuota y **Export** a PDF.

## 🛠️ Stack

| Capa | Tecnología |
|---|---|
| Backend | Python · FastAPI · Uvicorn |
| IA | Google Gemini (`google-genai`) · Groq/DeepSeek (API OpenAI) |
| Datos | MCP stdio · Yahoo Finance · BCE · pymongo/motor |
| Tiempo real | SSE (streaming) · Socket.io WS |
| Persistencia | MongoDB Atlas + fallback a archivos |
| PDF | fpdf2 + Pillow |
| Deploy | Docker · Vercel (Python/ASGI) |

---

## 🚀 Empezar (Windows · PowerShell)

Requiere **Python 3.11+**.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env          # si no tienes .env todavía
```

Edita `.env`:

```dotenv
LLM_PROVIDER=auto                     # gemini | groq | deepseek | auto

GEMINI_API_KEY=tu_clave
GEMINI_MODEL=gemini-3.6-flash
# GEMINI_API_KEYS=key1,key2           # rotación ante 429
# GEMINI_MODELS=modelo1,modelo2       # fallback en orden

GROQ_API_KEY=tu_clave_groq
GROQ_MODEL=openai/gpt-oss-120b
# DEEPSEEK_API_KEY=tu_clave          # legacy si no hay Groq

MCP_ENABLED=false                     # true para activar los 4 servers
# MONGODB_URI=mongodb+srv://<user>:<pass>@cluster.mongodb.net/
# MONGODB_DATABASE=tu_bd
```

Inicia el servidor:

```powershell
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

Abre **http://127.0.0.1:8000** (usa el servidor Python, no el archivo directo).

### 🐳 Con Docker

```powershell
docker build -t glintmesh .
docker run --rm -p 8000:8000 --env-file .env glintmesh
```

## ⌨️ Guía rápida

1. Escribe `Hola` → el agente responde y muestra el canal (Gemini o Groq).
2. Pide un dashboard, p. ej.: `Dashboard de portafolio en tiempo real para AAPL, MSFT, NVDA y TSLA`.
3. Usa **Preview**, **Code**, tab **A2UI Surface**, **Compose dashboard**, **Refresh data** y **Clear**.

## 🔌 MCP (Model Context Protocol)

Servidores configurados en `mcp_servers.json` (`MCP_ENABLED=true` para activarlos):

| Server | Archivo | Datos |
|---|---|---|
| Demo | `mcp_server.py` | Cotizaciones, carteras, índices, noticias y FX simulados |
| Live | `mcp_yahoo.py` | Cotizaciones e históricos **reales** de Yahoo Finance |
| ECB | `mcp_ecb.py` | Tipos de cambio oficiales del Banco Central Europeo |
| MongoDB | `mcp_mongodb.py` | Consultas de **solo lectura** a MongoDB Atlas |

Gemini y Groq/DeepSeek tienen acceso **idéntico** a todas las herramientas: el backend entrega las definiciones en formato nativo de cada proveedor, ejecuta las llamadas por stdio y devuelve los resultados al modelo.

## 🍃 MongoDB

Cadena de consulta servidor-side: **Frontend → FastAPI → LLM → MCP (stdio) → `database/mongodb.py` → MongoDB**. Todo es de solo lectura (`mongo_ping`, `list_collections`, `get_schema`, `find`, `count`, `aggregate`), sin operaciones destructivas.

Prueba la conexión sin gastar cuota de IA:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/tool-call -Method Post -ContentType 'application/json' -Body '{"tool":"mongo_ping","args":{}}'
```

## 📡 Live channel (WebSocket)

`GET /ws/live` (FastAPI nativo; Socket.io en `socket_events.py` con motor + fallback a archivos):

- **Ticks**: suscripción a símbolos con emisión cada 15 s; las tarjetas se actualizan solas.
- **Alertas**: te avisa cuando un precio cruza un umbral (`above` / `below`).
- **Cross-tab**: el progreso de generación se ve en vivo en todas tus pestañas.
- **Sync de prefs**: modelo, dataset, idioma y alertas por usuario (`/api/prefs`).

## 📖 API (resumen)

- `GET /` → UI web
- `POST /api/generate` → streaming SSE (message, lang, provider, model, temperature, mode, context, dataset_id, images)
- `POST /api/tool-call` → re-ejecuta una herramienta MCP sin LLM (refresh gratis)
- `GET /api/tools` · `GET /health` → herramientas MCP y estado del servicio
- `POST|GET|DELETE /api/datasets` → datasets CSV/JSON (máx 2 MB)
- `POST /api/share` · `GET /share/{id}` → enlaces compartibles
- `POST /api/auth/*`, `PUT /api/auth/avatar` → login local con foto
- `POST /api/pdf` → descarga el HTML generado como PDF A4
- `GET|PUT /api/prefs` → preferencias por usuario

## ☁️ Deploy en Vercel

Vercel detecta **FastAPI** automáticamente (instancia `app` en `main.py`). El código es **serverless-safe**: los directorios escribibles (`uploads`, `shares`, `users.json`) usan `/tmp`.

1. Importa el repo en Vercel.
2. En **Settings → Environment Variables** agrega: `GEMINI_API_KEY`, `GROQ_API_KEY`, `MONGODB_URI`, `MONGODB_DATABASE` (si usas Mongo).
3. Push a `main` (o Redeploy) y listo.

> ⚠️ En Vercel no funcionan WebSocket/Socket.io ni subprocesos MCP persistentes; el código ya degrada con gracia (`SOCKETIO_AVAILABLE=False`). Para el canal live y MCP completo usa Docker/local.

## 🧪 Pruebas

```powershell
# Python: Gemini, Groq/DeepSeek, MCP, MongoDB, auth y seguridad
.\.venv\Scripts\python.exe -m unittest discover -s tests -v

# SSE / PDF / print en JavaScript
node --test tests/sse.test.mjs
```

Verifican: fallback por 429/401/403/5xx, claves nunca expuestas (sanitización), integración MCP+MongoDB y mensajes de error claros en español.

## 📹 Demo 3 minutos → [DEMO-3MIN.md](DEMO-3MIN.md)

1. **0:00–0:30** `Hola` + etiquetas LIVE/SIM/USER + drawer de Tools.
2. **0:30–2:00** Dashboard real AAPL/MSFT/NVDA + A2UI + Compose dashboard.
3. **2:00–3:00** Refresh gratis + Retry 1-clic + Sign in con foto.

## 🙌 Agradecimientos

Hecho para **HackMTY** con FastAPI, Google Gemini, MCP estándar y mucho café. 🚀