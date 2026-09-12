import { SchemaType } from '@google/generative-ai';
import { genAI, modelName } from './config.js';

const schema = {
  description: "Financial KPI card",
  type: SchemaType.OBJECT,
  properties: {
    component: {
      type: SchemaType.STRING,
      enum: ["kpi_card"],
    },
    props: {
      type: SchemaType.OBJECT,
      properties: {
        label: { type: SchemaType.STRING },
        value: { type: SchemaType.STRING },
        change: { type: SchemaType.STRING },
      },
      required: ["label", "value", "change"],
    },
  },
  required: ["component", "props"],
};

const model = genAI.getGenerativeModel({
  model: modelName,
  generationConfig: {
    responseMimeType: "application/json",
    responseSchema: schema,
  },
});

async function run() {
  try {
    const prompt = 'Genera una tarjeta con label "Utilidad neta", value "$482,300" y change "+12%"';
    const result = await model.generateContent(prompt);
    const response = result.response;
    console.log(JSON.parse(response.text()));
  } catch (error) {
    console.error("Error in step 3:", error);
    process.exit(1);
  }
}

run();
