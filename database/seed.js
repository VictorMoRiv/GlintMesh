// seed.js
// Corre con: npm run seed
// Agrega una empresa con datos sintéticos sin borrar datos existentes.

import { ObjectId } from 'mongodb';
import { getDb, closeDb } from './db.js';
import {
  ultimosMeses,
  generarEmpresa,
  generarCuentas,
  generarClientes,
  generarProveedores,
  generarEmpleados,
  generarTransacciones,
  generarFacturas,
  generarNomina,
  generarPerfilCredito,
  generarPresupuestos,
} from './generate.js';

const MESES_HISTORIA = 12;

async function seed() {
  const db = await getDb();

  console.log('Conectado a Mongo. Base de datos:', db.databaseName);

  const empresaId = new ObjectId();
  const meses = ultimosMeses(MESES_HISTORIA);

  console.log('Generando datos en memoria...');
  const empresa = { _id: empresaId, ...generarEmpresa() };
  const cuentas = generarCuentas(empresaId);
  const clientes = generarClientes(empresaId, 15).map((c) => ({ _id: new ObjectId(), ...c }));
  const proveedores = generarProveedores(empresaId, 12).map((p) => ({ _id: new ObjectId(), ...p }));
  const empleados = generarEmpleados(empresaId, 12).map((e) => ({ _id: new ObjectId(), ...e }));
  const transacciones = generarTransacciones(empresaId, meses);
  const facturas = generarFacturas(empresaId, clientes, proveedores, meses);
  const nomina = generarNomina(empresaId, empleados, meses);
  const perfilCredito = generarPerfilCredito(empresaId, meses);
  const presupuestos = generarPresupuestos(empresaId, meses);

  console.log('Insertando en Mongo...');
  await db.collection('companies').insertOne(empresa);
  await db.collection('accounts').insertMany(cuentas);
  await db.collection('clients').insertMany(clientes);
  await db.collection('providers').insertMany(proveedores);
  await db.collection('employees').insertMany(empleados);
  await db.collection('transactions').insertMany(transacciones);
  await db.collection('invoices').insertMany(facturas);
  if (nomina.length) await db.collection('payroll').insertMany(nomina);
  await db.collection('credit_profile').insertOne(perfilCredito);
  await db.collection('budgets').insertMany(presupuestos);

  console.log('Creando índices...');
  await db.collection('transactions').createIndex({ empresa_id: 1, fecha: 1 });
  await db.collection('transactions').createIndex({ empresa_id: 1, categoria: 1 });
  await db.collection('invoices').createIndex({ empresa_id: 1, estado: 1 });
  await db.collection('payroll').createIndex({ empresa_id: 1, periodo: 1 });

  console.log('\nListo. Resumen:');
  console.log('  empresa_id a usar en tus MCP:', empresaId.toString());
  console.log('  companies:', 1);
  console.log('  accounts:', cuentas.length);
  console.log('  clients:', clientes.length);
  console.log('  providers:', proveedores.length);
  console.log('  employees:', empleados.length);
  console.log('  transactions:', transacciones.length);
  console.log('  invoices:', facturas.length);
  console.log('  payroll:', nomina.length);
  console.log('  credit_profile:', 1);
  console.log('  budgets:', presupuestos.length);
  console.log('\nGuarda el empresa_id de arriba: tus MCP lo van a necesitar como parámetro fijo.');

  await closeDb();
}

seed().catch((err) => {
  console.error('Error corriendo el seed:', err);
  process.exit(1);
});
