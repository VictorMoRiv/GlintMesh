import { genAI, modelName } from './config.js';

const tools = [
  {
    functionDeclarations: [
      {
        name: "get_financial_summary",
        description: "Obtiene un resumen financiero basado en un periodo",
        parameters: {
          type: "OBJECT",
          properties: {
            periodo: {
              type: "STRING",
              description: "El periodo del reporte (ej. 'último mes', 'año 2023')",
            },
          },
          required: ["periodo"],
        },
      },
    ],
  },
];

const model = genAI.getGenerativeModel({
  model: modelName,
  tools: tools
});

async function run() {
  try {
    const prompt = "Dame el reporte del último mes";
    const result = await model.generateContent(prompt);
    const response = result.response;

    // Gemini SDK returns function calls in candidate.content.parts
    const parts = response.candidates[0].content.parts;
    const functionCalls = parts.filter(part => part.functionCall);

    console.log("Function Calls:", JSON.stringify(functionCalls, null, 2));
  } catch (error) {
    console.error("Error in step 2:", error);
    process.exit(1);
  }
}

run();
