import { genAI, modelName } from './config.js';

const model = genAI.getGenerativeModel({ model: modelName });

async function run() {
  try {
    const prompt = "Hola, ¿estás funcionando?";
    const result = await model.generateContent(prompt);
    const response = await result.response;
    console.log(response.text());
  } catch (error) {
    console.error("Error in step 1:", error);
    process.exit(1);
  }
}

run();
