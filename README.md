# FinFlow AI - Financial Interface Generator

## Descripcion

FinFlow AI es un agente de inteligencia artificial que genera interfaces web financieras en tiempo real. El usuario describe en lenguaje natural la interfaz que necesita (dashboard de portafolio, monitor de mercado, analizador de riesgo, etc.) y el agente utiliza herramientas MCP para obtener datos financieros reales y generar HTML/CSS/JS completo e interactivo.

## Arquitectura

```
[Frontend Bootstrap 5 + Glassmorphism]
        |  SSE Streaming
        v
[FastAPI Backend - main.py]
        |  Tool calls
        v
[MCP Server - mcp_server.py]  <-->  [Google Gemini 2.0 Flash]
```

## Herramientas MCP disponibles

| Herramienta | Descripcion |
|---|---|
| `get_stock_quote` | Cotizacion en tiempo real de acciones (precio, cambio, volumen) |
| `get_portfolio_summary` | Resumen de portafolio de inversiones con P&L |
| `get_market_indices` | Indices principales: S&P 500, NASDAQ, Dow Jones, IPC Mexico |
| `analyze_credit_risk` | Analisis de riesgo crediticio con score y recomendacion |
| `get_historical_prices` | Datos historicos OHLCV para graficas |
| `get_financial_news` | Titulares financieros con sentimiento de mercado |
| `calculate_compound_interest` | Calculadora de interes compuesto con proyecciones |
| `get_forex_rates` | Tipos de cambio FX con multiples monedas |

## Instalacion

```bash
# 1. Clonar/descargar el proyecto
cd HackMTY

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Configurar API Key de Gemini
# Editar .env y agregar tu clave:
GEMINI_API_KEY=tu_clave_aqui

# 4. Iniciar el servidor
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# 5. Abrir en el navegador
# http://localhost:8000
```

## Obtencion de Gemini API Key

1. Ir a https://aistudio.google.com/app/apikey
2. Crear una nueva API key
3. Copiarla en el archivo `.env`

## Uso

1. Abre http://localhost:8000 en tu navegador
2. Usa los **Quick Prompts** del sidebar o escribe tu propia solicitud
3. El agente procesara la solicitud, llamara a las herramientas MCP necesarias y generara la interfaz
4. Ve el resultado en la pestana **Preview** o el codigo en **Code**
5. Exporta la interfaz generada con el boton **Export**

## Ejemplos de prompts

- "Show me a real-time portfolio dashboard for AAPL, MSFT, NVDA and TSLA stocks"
- "Generate a market indices monitor showing S&P 500, NASDAQ and Dow Jones"
- "Create a credit risk analysis dashboard for a $250,000 mortgage"
- "Build a compound interest calculator for $10,000 over 30 years at 8%"
- "Show me a forex exchange rates board with USD as base currency"
- "Generate a financial news feed with market sentiment indicators"

## Estructura del proyecto

```
HackMTY/
   main.py          # FastAPI backend + agente Gemini
   mcp_server.py    # MCP Server con herramientas financieras
   requirements.txt # Dependencias Python
   .env             # Configuracion (API keys)
   static/
      index.html   # Frontend con glassmorfismo + Bootstrap 5
```
