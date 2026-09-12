// db.js
import { MongoClient } from 'mongodb';
import 'dotenv/config';

if (!process.env.MONGODB_URI) {
  throw new Error('Falta MONGODB_URI en tu .env (ver .env.example)');
}
if (process.env.MONGODB_URI.includes('<db_password>')) {
  throw new Error('Reemplaza <db_password> en .env por tu contraseña de MongoDB Atlas codificada para URL.');
}

const client = new MongoClient(process.env.MONGODB_URI);
let dbInstance = null;

export async function getDb() {
  if (!dbInstance) {
    await client.connect();
    dbInstance = client.db(process.env.MONGODB_DB_NAME || 'finapp');
  }
  return dbInstance;
}

export async function closeDb() {
  await client.close();
}
