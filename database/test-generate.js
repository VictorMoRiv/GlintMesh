import { ObjectId } from 'mongodb';
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

const empresaId = new ObjectId();
const meses = ultimosMeses(12);

const empresa = generarEmpresa();
const cuentas = generarCuentas(empresaId);
const clientes = generarClientes(empresaId, 15).map((c) => ({ _id: new ObjectId(), ...c }));
const proveedores = generarProveedores(empresaId, 12).map((p) => ({ _id: new ObjectId(), ...p }));
const empleados = generarEmpleados(empresaId, 12).map((e) => ({ _id: new ObjectId(), ...e }));
const transacciones = generarTransacciones(empresaId, meses);
const facturas = generarFacturas(empresaId, clientes, proveedores, meses);
const nomina = generarNomina(empresaId, empleados, meses);
const perfilCredito = generarPerfilCredito(empresaId, meses);
const presupuestos = generarPresupuestos(empresaId, meses);

console.log('Empresa:', empresa.nombre, '-', empresa.giro);
console.log('Meses cubiertos:', meses.length, `(${meses[0].year}-${meses[0].month} a ${meses.at(-1).year}-${meses.at(-1).month})`);
console.log('Cuentas:', cuentas.length);
console.log('Clientes:', clientes.length);
console.log('Proveedores:', proveedores.length);
console.log('Empleados:', empleados.length, '(activos:', empleados.filter(e => e.activo).length, ')');
console.log('Transacciones:', transacciones.length,
  '(ingresos:', transacciones.filter(t => t.tipo === 'ingreso').length,
  ', gastos:', transacciones.filter(t => t.tipo === 'gasto').length, ')');
console.log('Facturas:', facturas.length,
  '(pendientes:', facturas.filter(f => f.estado === 'pendiente').length, ')');
console.log('Registros de nómina:', nomina.length);
console.log('Perfil de crédito, score:', perfilCredito.score_interno, '- deuda:', perfilCredito.deuda_total);
console.log('Renglones de presupuesto:', presupuestos.length);

// Validación básica: nada de montos negativos o NaN
const todosLosMontos = [
  ...transacciones.map(t => t.monto),
  ...facturas.map(f => f.monto),
];
const invalidos = todosLosMontos.filter(m => !(m > 0));
console.log('Montos inválidos encontrados:', invalidos.length);

console.log('\nEjemplo de transacción:', JSON.stringify(transacciones[0], null, 2));
console.log('\nEjemplo de factura:', JSON.stringify(facturas[0], null, 2));
