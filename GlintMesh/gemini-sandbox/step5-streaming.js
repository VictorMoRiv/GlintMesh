import { genAI, modelName } from './config.js';

const model = genAI.getGenerativeModel({ model: modelName });

async function run() {
  try {
    const prompt = "Hola, ¿estás funcionando?";
    const result = await model.generateContentStream(prompt);

    for await (const chunk of result.stream) {
      const chunkText = chunk.text();
      process.stdout.write(chunkText);
    }
    console.log("\nStream finished.");
  } catch (error) {
    console.error("Error in step 5:", error);
    process.exit(1);
  }
}

run();
