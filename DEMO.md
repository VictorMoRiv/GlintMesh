# GlintMesh — Guion demo 3 minutos

Previo: server arriba (`http://127.0.0.1:8000`), MCP activado, sesión limpia (Clear).

## 0:00–0:50 — El problema y el flujo agentic
1. Di: “Las IAs te dan texto o código con datos inventados. GlintMesh ejecuta herramientas reales y renderiza UI nativa.”
2. Escribe: `cotización de AAPL`.
3. Señala el sidebar: `tool_call → tool_result` (`get_live_quote`, `get_live_history`).
4. Abre la tab **A2UI Surface**: tarjeta + gráfica Chart.js con badge **LIVE**. “Cero código del modelo ejecutándose aquí.”

## 0:50–1:30 — Composición
5. Fija (pin) la cotización y la gráfica. Abre la tab **Dashboard**: “Varias superficies, un tablero.”
6. Clic en una columna para ordenar; rueda sobre la gráfica para zoom; clic en un símbolo (drill-down gratis, sin cuota).

## 1:30–2:10 — Tus datos
7. Botón **Data** → sube un CSV (ej. `mes,ingreso,gasto`) → queda como chip activo.
8. Pide: `haz un dashboard con mis datos`. Muestra la tarjeta USER DATA + el Preview generado con tus números.

## 2:10–2:45 — Alertas y estilo
9. Engrane → **Alertas**: crea `AAPL debajo de 300`. Explica el checker cada 60s.
10. Cambia el preset de estilo a **Oscuro simple** y el tema de la app a **Claro**: “El usuario controla todo.”

## 2:45–3:00 — Cierre
11. Botón **Refresh** en A2UI: “Datos frescos sin gastar cuota de Gemini.”
12. **Export/Share**: link compartible de la interfaz. Frase final: “Usuario → Agente → MCP → A2UI → Componentes. Sin datos falsos: lo simulado solo existe en modo simulación.”
