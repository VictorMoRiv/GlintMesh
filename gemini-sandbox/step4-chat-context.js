import { genAI, modelName } from './config.js';

const model = genAI.getGenerativeModel({ model: modelName });

async function run() {
  try {
    const chat = model.startChat({
      history: [],
    });

    const msg1 = "Dame el reporte del último mes";
    const result1 = await chat.sendMessage(msg1);
    const response1 = result1.response;
    console.log("Response 1:", response1.text());

    const msg2 = "el usuario seleccionó ver gastos de marketing";
    const result2 = await chat.sendMessage(msg2);
    const response2 = result2.response;
    console.log("Response 2:", response2.text());
  } catch (error) {
    console.error("Error in step 4:", error);
    process.exit(1);
  }
}

run();
