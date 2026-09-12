# Seed de datos: PyME sintética

Genera una empresa ficticia completa (12 meses de historia) en MongoDB:
cuentas, clientes, proveedores, empleados, transacciones, facturas,
nómina, perfil de crédito y presupuestos.

## Uso

Desde la raíz del repositorio, entra a `database/`. Requiere Node.js 22.13 o posterior.

```bash
cd database
npm ci
cp .env.example .env
# Edita .env con tu conexión y contraseña de MongoDB Atlas.
npm run seed
```

El seed agrega una nueva empresa en `finapp` y conserva los datos existentes.
Cada ejecución agrega otra empresa. La contraseña en la URI debe estar
codificada para URL si contiene caracteres especiales.

Al terminar imprime el `empresa_id` generado — guárdalo, es el que tus
funciones MCP van a usar como parámetro fijo mientras solo tengan una
empresa de prueba.

## Empresa ya creada y conexión con la app

La base `finapp` en Atlas ya contiene la empresa de prueba
`6aa5a3120cdf772a8940bf84`. No necesitas ejecutar el seed otra vez para
consultar esos datos. Configura `MONGODB_URI`, `MONGODB_DB_NAME=finapp` y
`EMPRESA_ID=6aa5a3120cdf772a8940bf84` en el `.env` privado del backend.
En Windows puedes copiar el ejemplo con `Copy-Item .env.example .env`.
Nunca publiques el `.env` ni envíes la conexión al frontend.

Los documentos de las colecciones relacionadas guardan `empresa_id` como
`ObjectId`, no como texto. En `companies`, ese mismo identificador es `_id`.

```js
import { ObjectId } from 'mongodb';
import { getDb, closeDb } from './db.js';

try {
  const db = await getDb();
  const empresaId = new ObjectId(process.env.EMPRESA_ID);
  const transacciones = await db.collection('transactions')
    .find({ empresa_id: empresaId }).toArray();
  console.log(transacciones);
} finally {
  await closeDb();
}
```

Este módulo incluye la conexión y el generador en Node.js. La app Python
de esta rama todavía usa herramientas con datos simulados; no lee estas
variables ni consulta MongoDB. Para integrarla, su backend necesita un
cliente MongoDB y consultas filtradas por `ObjectId(EMPRESA_ID)`.
La tabla siguiente describe el uso previsto de las colecciones, no una
integración ya implementada en `mcp_server.py`.

## Probar la generación sin tocar Mongo

```bash
npm run test:generate
```

Corre las mismas funciones de generación pero solo imprime en consola,
sin conectarse a nada. Útil para ajustar cantidades o categorías antes
de insertar datos reales.

## Qué cubre cada colección

| Colección         | Para qué sirve                                              | ¿La usa algún MCP ya? |
|--------------------|--------------------------------------------------------------|------------------------|
| `companies`        | Datos generales de la empresa                                | Indirecto (empresa_id) |
| `accounts`         | Catálogo de cuentas contables                                | No                      |
| `clients`          | Clientes de la empresa                                       | No                      |
| `providers`        | Proveedores de la empresa                                    | No                      |
| `employees`        | Plantilla de empleados                                       | No                      |
| `transactions`     | Ingresos y gastos, mes a mes                                 | Sí — `get_financial_summary`, `get_expenses_breakdown` |
| `invoices`         | Facturas emitidas y recibidas, pagadas o pendientes          | No (útil para un futuro MCP de cuentas por cobrar/pagar) |
| `payroll`          | Nómina mensual por empleado                                  | No                      |
| `credit_profile`   | Historial de pagos y score interno                           | Sí — `analyze_credit_risk` |
| `budgets`          | Presupuesto mensual por categoría de gasto                   | No (útil para comparar real vs. presupuestado) |

Las colecciones marcadas "No" existen para que los datos de la empresa
se sientan completos y reales en la demo, aunque hoy ningún MCP las
consuma todavía. Si alguien quiere construir una tool nueva
(`get_pending_invoices`, `get_payroll_summary`, `compare_budget`, etc.),
los datos ya están ahí.

## Ajustar el volumen de datos

En `seed.js`, cambia `MESES_HISTORIA` (por defecto 12). En
`generate.js`, la función `generarTransacciones` acepta un tercer
argumento `opciones` para controlar cuántas transacciones se generan
por mes (`gastosPorMes`, `ingresosPorMes`).

## Nota sobre categorías

`CATEGORIAS_GASTO` en `config.js` incluye más categorías (`renta`,
`servicios`, `impuestos`, etc.) de las que hoy validan tus MCP
(`marketing`, `nomina`, `operacion`, `otros`). Esto es intencional —
pediste datos realistas aunque no encajen 100% con los MCP actuales.
Si tu `get_expenses_breakdown` valida contra un enum cerrado, vas a
necesitar ampliarlo o filtrar/agrupar estas categorías antes de
devolverlas al agente.
