import dotenv from 'dotenv';
import { fileURLToPath } from 'node:url';
import { GoogleGenerativeAI } from '@google/generative-ai';

dotenv.config({ path: fileURLToPath(new URL('./.env', import.meta.url)), quiet: true });

export const apiKey = process.env.GEMINI_API_KEY?.trim();
if (!apiKey) {
  throw new Error('Configura GEMINI_API_KEY en gemini-sandbox/.env.');
}

export const modelName = process.env.GEMINI_MODEL?.trim() || 'gemini-3.6-flash';
export const genAI = new GoogleGenerativeAI(apiKey);
