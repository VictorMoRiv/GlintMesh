import { genAI, modelName } from './config.js';

async function testModel(modelName) {
  try {
    const model = genAI.getGenerativeModel({ model: modelName });
    const result = await model.generateContent("Hi");
    console.log(`${modelName} works!`);
  } catch (e) {
    console.error(`${modelName} failed: ${e.message}`);
    process.exitCode = 1;
  }
}

async function run() {
  await testModel(modelName);
}

run();
