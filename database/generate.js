// generate.js
// Funciones puras: no tocan la base de datos, solo generan objetos en
// memoria. Así se pueden probar con `npm run test:generate` sin
// necesitar Mongo corriendo.

import { fakerES_MX as faker } from '@faker-js/faker';
import {
  MONEDA_BASE,
  CUENTAS,
  CATEGORIAS_GASTO,
  CATEGORIAS_INGRESO,
  PUESTOS,
  DESCRIPCIONES_GASTO,
  DESCRIPCIONES_INGRESO,
} from './config.js';

function randomInt(min, max) {
  return Math.floor(Math.random() * (max - min + 1)) + min;
}

function pick(arr) {
  return arr[randomInt(0, arr.length - 1)];
}

// Genera los últimos `months` meses como [{ year, month, start, end }],
// terminando en el mes actual.
export function ultimosMeses(months, referencia = new Date()) {
  const meses = [];
  for (let i = months - 1; i >= 0; i--) {
    const d = new Date(referencia.getFullYear(), referencia.getMonth() - i, 1);
    const start = new Date(d.getFullYear(), d.getMonth(), 1);
    const end = new Date(d.getFullYear(), d.getMonth() + 1, 0, 23, 59, 59);
    meses.push({ year: d.getFullYear(), month: d.getMonth() + 1, start, end });
  }
  return meses;
}

export function generarEmpresa() {
  return {
    nombre: faker.company.name(),
    rfc: faker.string.alphanumeric({ length: 12, casing: 'upper' }),
    moneda_base: MONEDA_BASE,
    giro: pick(['Comercio al por menor', 'Servicios profesionales', 'Manufactura ligera', 'Tecnología']),
    fecha_creacion: faker.date.past({ years: 5 }).toISOString(),
  };
}

export function generarCuentas(empresaId) {
  return CUENTAS.map((c) => ({ empresa_id: empresaId, ...c }));
}

export function generarClientes(empresaId, n = 15) {
  return Array.from({ length: n }, () => ({
    empresa_id: empresaId,
    nombre: faker.company.name(),
    rfc: faker.string.alphanumeric({ length: 12, casing: 'upper' }),
    contacto: faker.person.fullName(),
    email: faker.internet.email(),
    telefono: faker.phone.number(),
    ciudad: faker.location.city(),
    fecha_alta: faker.date.past({ years: 3 }).toISOString(),
  }));
}

export function generarProveedores(empresaId, n = 12) {
  return Array.from({ length: n }, () => ({
    empresa_id: empresaId,
    nombre: faker.company.name(),
    rfc: faker.string.alphanumeric({ length: 12, casing: 'upper' }),
    categoria: pick(['tecnologia', 'renta', 'marketing', 'mantenimiento', 'servicios', 'otros']),
    contacto: faker.person.fullName(),
    email: faker.internet.email(),
    fecha_alta: faker.date.past({ years: 4 }).toISOString(),
  }));
}

export function generarEmpleados(empresaId, n = 12) {
  return Array.from({ length: n }, () => {
    const p = pick(PUESTOS);
    return {
      empresa_id: empresaId,
      nombre: faker.person.fullName(),
      puesto: p.puesto,
      salario_mensual: randomInt(p.rango[0], p.rango[1]),
      fecha_ingreso: faker.date.past({ years: 4 }).toISOString(),
      activo: Math.random() > 0.05, // ~95% activos, un par de bajas realistas
    };
  });
}

// Transacciones: la colección más grande, la que alimenta
// get_financial_summary y get_expenses_breakdown.
export function generarTransacciones(empresaId, meses, opciones = {}) {
  const { gastosPorMes = [25, 45], ingresosPorMes = [15, 30] } = opciones;
  const transacciones = [];

  for (const mes of meses) {
    const nGastos = randomInt(...gastosPorMes);
    const nIngresos = randomInt(...ingresosPorMes);

    for (let i = 0; i < nGastos; i++) {
      const cat = pick(CATEGORIAS_GASTO);
      const fecha = faker.date.between({ from: mes.start, to: mes.end });
      transacciones.push({
        empresa_id: empresaId,
        tipo: 'gasto',
        categoria: cat.categoria,
        cuenta_codigo: cat.cuenta,
        monto: Number(faker.finance.amount({ min: 500, max: 60000, dec: 0 })),
        moneda: MONEDA_BASE,
        fecha: fecha.toISOString(),
        descripcion: pick(DESCRIPCIONES_GASTO[cat.categoria]),
      });
    }

    for (let i = 0; i < nIngresos; i++) {
      const cat = pick(CATEGORIAS_INGRESO);
      const fecha = faker.date.between({ from: mes.start, to: mes.end });
      transacciones.push({
        empresa_id: empresaId,
        tipo: 'ingreso',
        categoria: cat.categoria,
        cuenta_codigo: cat.cuenta,
        monto: Number(faker.finance.amount({ min: 2000, max: 120000, dec: 0 })),
        moneda: MONEDA_BASE,
        fecha: fecha.toISOString(),
        descripcion: pick(DESCRIPCIONES_INGRESO[cat.categoria]),
      });
    }
  }

  return transacciones.sort((a, b) => new Date(a.fecha) - new Date(b.fecha));
}

// Facturas emitidas (a clientes) y recibidas (de proveedores).
// No todas están pagadas: eso alimenta accounts_receivable / accounts_payable.
export function generarFacturas(empresaId, clientes, proveedores, meses) {
  const facturas = [];

  for (const mes of meses) {
    const nEmitidas = randomInt(4, 10);
    for (let i = 0; i < nEmitidas; i++) {
      const cliente = pick(clientes);
      const fechaEmision = faker.date.between({ from: mes.start, to: mes.end });
      const pagada = Math.random() > 0.2; // ~20% pendientes, realista para una PyME
      facturas.push({
        empresa_id: empresaId,
        tipo: 'emitida',
        folio: `A-${faker.string.numeric(6)}`,
        cliente_id: cliente._id,
        monto: Number(faker.finance.amount({ min: 3000, max: 90000, dec: 0 })),
        moneda: MONEDA_BASE,
        fecha_emision: fechaEmision.toISOString(),
        fecha_vencimiento: new Date(fechaEmision.getTime() + 30 * 86400000).toISOString(),
        estado: pagada ? 'pagada' : 'pendiente',
        fecha_pago: pagada
          ? new Date(fechaEmision.getTime() + randomInt(1, 25) * 86400000).toISOString()
          : null,
      });
    }

    const nRecibidas = randomInt(3, 8);
    for (let i = 0; i < nRecibidas; i++) {
      const proveedor = pick(proveedores);
      const fechaEmision = faker.date.between({ from: mes.start, to: mes.end });
      const pagada = Math.random() > 0.15;
      facturas.push({
        empresa_id: empresaId,
        tipo: 'recibida',
        folio: `P-${faker.string.numeric(6)}`,
        proveedor_id: proveedor._id,
        monto: Number(faker.finance.amount({ min: 1000, max: 60000, dec: 0 })),
        moneda: MONEDA_BASE,
        fecha_emision: fechaEmision.toISOString(),
        fecha_vencimiento: new Date(fechaEmision.getTime() + 30 * 86400000).toISOString(),
        estado: pagada ? 'pagada' : 'pendiente',
        fecha_pago: pagada
          ? new Date(fechaEmision.getTime() + randomInt(1, 25) * 86400000).toISOString()
          : null,
      });
    }
  }

  return facturas;
}

// Nómina mensual por empleado activo.
export function generarNomina(empresaId, empleados, meses) {
  const nomina = [];
  for (const mes of meses) {
    for (const emp of empleados) {
      if (!emp.activo) continue;
      const bono = Math.random() > 0.85 ? randomInt(500, 5000) : 0;
      nomina.push({
        empresa_id: empresaId,
        empleado_id: emp._id,
        periodo: `${mes.year}-${String(mes.month).padStart(2, '0')}`,
        salario_bruto: emp.salario_mensual,
        bono,
        salario_neto: Math.round(emp.salario_mensual * 0.82) + bono, // ISR/IMSS aproximado
        fecha_pago: new Date(mes.year, mes.month - 1, 28).toISOString(),
      });
    }
  }
  return nomina;
}

// Perfil de crédito, usado por analyze_credit_risk.
export function generarPerfilCredito(empresaId, meses) {
  const historial = meses.map((mes) => ({
    fecha: new Date(mes.year, mes.month - 1, randomInt(1, 28)).toISOString(),
    monto: randomInt(8000, 25000),
    atraso_dias: Math.random() > 0.85 ? randomInt(1, 15) : 0,
  }));

  const atrasos = historial.filter((h) => h.atraso_dias > 0).length;
  const scoreBase = 780 - atrasos * 25;

  return {
    empresa_id: empresaId,
    deuda_total: randomInt(150000, 600000),
    score_interno: Math.max(500, scoreBase),
    historial_pagos: historial,
    fecha_actualizacion: new Date().toISOString(),
  };
}

// Presupuesto mensual por categoría de gasto, para comparar contra
// lo real (útil para un futuro componente tipo "vas arriba/abajo del presupuesto").
export function generarPresupuestos(empresaId, meses) {
  const presupuestos = [];
  for (const mes of meses) {
    for (const cat of CATEGORIAS_GASTO) {
      presupuestos.push({
        empresa_id: empresaId,
        periodo: `${mes.year}-${String(mes.month).padStart(2, '0')}`,
        categoria: cat.categoria,
        monto_presupuestado: randomInt(3000, 50000),
      });
    }
  }
  return presupuestos;
}
