// config.js
// Catálogo de cuentas y categorías de una PyME mexicana típica.
// Las categorías marcadas con [MCP] son las que ya usan tus MCP actuales
// (analyze_credit_risk, get_expenses_breakdown, etc.). Las demás son para
// que los datos se vean completos y realistas aunque hoy ningún MCP las
// consuma todavía.

export const MONEDA_BASE = 'MXN';

export const CUENTAS = [
  { codigo: '4000', nombre: 'Ventas de productos', tipo: 'ingreso' },
  { codigo: '4100', nombre: 'Ventas de servicios', tipo: 'ingreso' },
  { codigo: '4200', nombre: 'Ingresos financieros', tipo: 'ingreso' },
  { codigo: '5000', nombre: 'Nómina', tipo: 'gasto' },
  { codigo: '5100', nombre: 'Renta', tipo: 'gasto' },
  { codigo: '5200', nombre: 'Marketing y publicidad', tipo: 'gasto' },
  { codigo: '5300', nombre: 'Servicios (luz, agua, internet)', tipo: 'gasto' },
  { codigo: '5400', nombre: 'Impuestos y derechos', tipo: 'gasto' },
  { codigo: '5500', nombre: 'Mantenimiento y suministros', tipo: 'gasto' },
  { codigo: '5600', nombre: 'Viáticos y viajes', tipo: 'gasto' },
  { codigo: '5700', nombre: 'Tecnología y software', tipo: 'gasto' },
  { codigo: '5800', nombre: 'Seguros', tipo: 'gasto' },
  { codigo: '5900', nombre: 'Capacitación', tipo: 'gasto' },
  { codigo: '5999', nombre: 'Otros gastos operativos', tipo: 'gasto' },
  { codigo: '1000', nombre: 'Caja y bancos', tipo: 'activo' },
  { codigo: '1100', nombre: 'Cuentas por cobrar', tipo: 'activo' },
  { codigo: '1200', nombre: 'Inventario', tipo: 'activo' },
  { codigo: '2000', nombre: 'Cuentas por pagar', tipo: 'pasivo' },
  { codigo: '2100', nombre: 'Préstamos bancarios', tipo: 'pasivo' },
  { codigo: '3000', nombre: 'Capital social', tipo: 'capital' },
];

// Mapeo categoría (usada en transactions.categoria) -> código de cuenta.
// [MCP] = ya cubierta por get_expenses_breakdown en el contrato actual.
export const CATEGORIAS_GASTO = [
  { categoria: 'nomina', cuenta: '5000', mcp: true },
  { categoria: 'renta', cuenta: '5100', mcp: false },
  { categoria: 'marketing', cuenta: '5200', mcp: true },
  { categoria: 'servicios', cuenta: '5300', mcp: false },
  { categoria: 'impuestos', cuenta: '5400', mcp: false },
  { categoria: 'mantenimiento', cuenta: '5500', mcp: false },
  { categoria: 'viaticos', cuenta: '5600', mcp: false },
  { categoria: 'tecnologia', cuenta: '5700', mcp: false },
  { categoria: 'seguros', cuenta: '5800', mcp: false },
  { categoria: 'capacitacion', cuenta: '5900', mcp: false },
  { categoria: 'operacion', cuenta: '5999', mcp: true }, // catch-all que ya espera tu MCP
  { categoria: 'otros', cuenta: '5999', mcp: true },
];

export const CATEGORIAS_INGRESO = [
  { categoria: 'venta_producto', cuenta: '4000' },
  { categoria: 'venta_servicio', cuenta: '4100' },
  { categoria: 'ingreso_financiero', cuenta: '4200' },
];

// Descripciones realistas en español por categoría, para no depender del
// módulo `commerce` de faker (no está bien localizado a es_MX).
export const DESCRIPCIONES_GASTO = {
  nomina: ['Pago de nómina quincenal', 'Pago de nómina y prestaciones', 'Liquidación de aguinaldo parcial'],
  renta: ['Renta de oficina', 'Renta de bodega', 'Renta de local comercial'],
  marketing: ['Campaña en redes sociales', 'Diseño de material publicitario', 'Pauta en Google Ads', 'Impresión de material promocional'],
  servicios: ['Recibo de luz', 'Recibo de agua', 'Servicio de internet y telefonía', 'Recolección de basura'],
  impuestos: ['Pago provisional de ISR', 'Pago de IVA', 'Cuotas IMSS', 'Derechos municipales'],
  mantenimiento: ['Mantenimiento de equipo de cómputo', 'Reparación de aire acondicionado', 'Compra de papelería', 'Mantenimiento de vehículo'],
  viaticos: ['Viáticos visita a cliente', 'Boletos de avión viaje de negocios', 'Hospedaje congreso del sector'],
  tecnologia: ['Licencia de software mensual', 'Renovación de hosting', 'Suscripción a herramienta SaaS', 'Compra de equipo de cómputo'],
  seguros: ['Póliza de seguro de responsabilidad civil', 'Seguro de flotilla vehicular', 'Seguro de gastos médicos colectivo'],
  capacitacion: ['Curso de capacitación al equipo', 'Certificación técnica empleado', 'Taller de ventas'],
  operacion: ['Compra de insumos de operación', 'Servicio de mensajería', 'Renta de equipo temporal'],
  otros: ['Gasto operativo diverso', 'Gasto menor de caja chica', 'Ajuste contable menor'],
};

export const DESCRIPCIONES_INGRESO = {
  venta_producto: ['Venta de producto a cliente', 'Pedido mayorista', 'Venta en punto de venta'],
  venta_servicio: ['Servicio de consultoría prestado', 'Proyecto entregado a cliente', 'Servicio mensual recurrente'],
  ingreso_financiero: ['Rendimiento de inversión', 'Interés bancario generado'],
};

export const PUESTOS = [
  { puesto: 'Gerente General', rango: [35000, 55000] },
  { puesto: 'Contador', rango: [18000, 28000] },
  { puesto: 'Ejecutivo de Ventas', rango: [12000, 22000] },
  { puesto: 'Desarrollador', rango: [20000, 38000] },
  { puesto: 'Diseñador', rango: [15000, 25000] },
  { puesto: 'Atención a Cliente', rango: [10000, 16000] },
  { puesto: 'Almacén / Logística', rango: [9000, 14000] },
  { puesto: 'Marketing', rango: [14000, 24000] },
];
