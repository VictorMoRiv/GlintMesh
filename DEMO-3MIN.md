# DEMO-3MIN — guion HackMTY

Total 3:00. Servidor ya corriendo en http://127.0.0.1:8000 con MCP_ENABLED=true.

## 0:00-0:30 — Hola + etiquetas de datos
1. Escribe `Hola`.
2. Di: "Todo dato va etiquetado: LIVE (Yahoo), SIM (demo), USER (mi CSV)".
3. Muestra drawer Tools: live 4 + ecb 1.

## 0:30-2:00 — Dashboard + Compose
1. Prompt: `Dashboard de portafolio en tiempo real para AAPL, MSFT, NVDA y TSLA`.
2. Muestra Preview, Code, pestaña A2UI Surface (cards por tool).
3. Clic **Compose dashboard**: "N superficies combinadas en 1, sin otra llamada a Gemini".
4. Clic **Refresh data**: "Actualiza todo sin gastar cuota".

## 2:00-2:45 — Alertas + Retry
1. Header **Alerts** → crea `AAPL below 150` → **Check now**.
2. Badge rojo = triggered con last_price y hora.
3. "El servidor revisa cada 5 min (alerts.json, sin Gemini)".
4. Si falla Gemini: "Error visible con Retry en 1 clic; el backend rota 3 keys x 7 modelos".

## 2:45-3:00 — Cierre
1. Export / Share link.
2. "28+ tests, `python -m unittest discover -s tests -v`, sin emojis, datos live etiquetados".

## Screenshots (tomar antes de presentar)
- `docs/shot-dashboard.png`: Preview con dashboard.
- `docs/shot-a2ui.png`: A2UI + tarjeta COMPOSED.
- `docs/shot-alerts.png`: modal de alertas con 1 triggered.
