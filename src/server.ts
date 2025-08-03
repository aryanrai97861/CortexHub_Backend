// backend/src/server.ts

import dotenv from "dotenv";
dotenv.config();

import express, { Request, Response } from "express";
import cors from "cors";
import multer from "multer";
import { spawn } from "child_process";
import path from "path";
import fs from "fs"; // Import fs for file system operations

import connectDB from "./config/db";
import DocumentModel from "./models/Document";
import {connectMySQL,sequelize} from './config/mysql';
import workspaceRoutes from './routes/workspace';
require('./models/Workspace');
import User from "./models/User";
import agentRoutes from "./routes/agent";
import Task from "./models/Task";

// Import Google Gemini SDK
import {
  GoogleGenerativeAI,
  HarmBlockThreshold,
  HarmCategory,
} from "@google/generative-ai";

const app = express();
const PORT = process.env.PORT || 5000;

// --- Connect to MongoDB ---
connectDB();

// --- Connect to MySQL and then sync it ---
connectMySQL().then(async () => {
  try {
    await sequelize.sync({alter:true});
    console.log('MySQL models synchronized successfully');
    const ownerId='00000000-0000-0000-0000-000000000001';
    const existingUser=await User.findByPk(ownerId);
    if (!existingUser) {
      await User.create({
        id: ownerId,
        email: 'placeholder@example.com',
        username: 'PlaceholderUser',
        passwordHash: 'not_needed_for_this_example'
      });
      console.log('Created placeholder user for workspace ownership.');
    }
  } catch (error) {
    console.error('Error synchronizing MySQL models:', error);
    process.exit(1);
  }
});


// --- Configure Google Gemini API ---
const GEMINI_API_KEY = process.env.GEMINI_API_KEY;
if (!GEMINI_API_KEY) {
  console.error(
    "GEMINI_API_KEY is not set in environment variables. Gemini API calls will fail."
  );
  // process.exit(1); // Consider exiting if API key is critical for startup
}
const genAI = new GoogleGenerativeAI(GEMINI_API_KEY || ""); // Provide empty string if not set, handled by error above
const geminiModel = genAI.getGenerativeModel({ model: "gemini-2.5-pro" }); // Using the latest 2.5 Pro model

// --- Middleware ---
app.use(cors());
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// --- Multer for file uploads ---
// Configure storage for uploaded files
const storage = multer.diskStorage({
  destination: (req, file, cb) => {
    const uploadDir = path.join(__dirname, "../uploads");
    if (!fs.existsSync(uploadDir)) {
      fs.mkdirSync(uploadDir);
    }
    cb(null, uploadDir);
  },
  filename: (req, file, cb) => {
    cb(null, `${Date.now()}-${file.originalname}`);
  },
});
const upload = multer({ storage: storage });

// --- Helper function to run Python script ---
export const runPythonScript = (
  scriptPath: string,
  args: string[]
): Promise<string> => {
  return new Promise((resolve, reject) => {
    const pythonProcess = spawn("python", [scriptPath, ...args]);

    let stdout = "";
    let stderr = "";

    pythonProcess.stdout.on("data", (data) => {
      stdout += data.toString();
    });

    pythonProcess.stderr.on("data", (data) => {
      stderr += data.toString();
    });

    pythonProcess.on("close", (code) => {
      if (code === 0) {
        resolve(stdout.trim());
      } else {
        reject(
          new Error(
            `Python script exited with code ${code}. Stderr: ${stderr.trim()}`
          )
        );
      }
    });

    pythonProcess.on("error", (err) => {
      reject(new Error(`Failed to start Python script: ${err.message}`));
    });
  });
};

// --- API Routes ---
// Use the workspace router
app.use('/api/workspaces', workspaceRoutes);
//use the agent router
app.use('/api/agents',agentRoutes);

// @route   POST /api/generate-knowledge-graph
// @desc    Generates a knowledge graph from a workspace's documents
app.post('/api/generate-knowledge-graph',async(req:Request,res:Response)=>{
  const {workspaceId} = req.body;
  if(!workspaceId){
    return res.status(400).json({message:'Workspace ID is required.'});
  }

  try{
    // 1. Retrieve all processed documents for the workspace from MongoDB
    const documents=await DocumentModel.find({workspaceId:workspaceId,processed:true});

    if(documents.length===0){
      return res.status(400).json({message:'No processed document found'});
    }

      const allProcessedChunks:string[]=[];
      for(const doc of documents){
        if(doc.chromaDocumentId){
          allProcessedChunks.push(`Placeholder content for doc ID: ${doc.chromaDocumentId}.`);
        }
      }
      const textContext=allProcessedChunks.join('\n\n');

      if(!textContext){
        return res.status(400).json({message:'Could not retrieve content'});
      }

      // 3. Trigger the Python script to generate the knowledge graph
      const pythonScriptPath=path.join(__dirname,'../python_scripts/knowledge_graph_generator.py');
      const pythonArgs=['generate_graph',textContext];
      const pythonOutput=await runPythonScript(pythonScriptPath,pythonArgs);

      // 4. Parse the JSON output from the Python script
      const knowledgeGraph=JSON.parse(pythonOutput);

      res.status(200).json(knowledgeGraph);
  }catch(error:any){
    console.error('Error generating knowledge graph',error);
    res.status(500).json({message:'Failed to generate knowledge graph',error:error.message});
  }
});


// @route   POST /api/universal-upload
// @desc    Uploads a file, processes it, and stores embeddings in ChromaDB
app.post(
  "/api/universal-upload",
  upload.single("file"),
  async (req: Request, res: Response) => {
    if (!req.file) {
      return res.status(400).json({ message: "No file uploaded." });
    }

    const { originalname, mimetype, path: filePath } = req.file;
    // A placeholder workspaceId, which will be passed from the frontend later
    const {workspaceId} = req.body;
    if(!workspaceId || typeof workspaceId !== 'string'){
      return res.status(400).json({message:'Workspace ID is required.'})
    }

    try {
      // 1. Save document metadata to MongoDB
      const newDocument = new DocumentModel({
        fileName: originalname,
        originalType: mimetype,
        processed: false,
        workspaceId:workspaceId
      });
      await newDocument.save();
      const mongoDocumentId = (newDocument._id as any).toString(); // Convert to string explicitly

      // 2. Trigger Python script to process and embed document
      const pythonScriptPath = path.join(
        __dirname,
        "../python_scripts/chroma_handler.py"
      );
      const pythonArgs = [
        "embed_document",
        filePath,
        mimetype,
        mongoDocumentId,
      ];

      // The Python script will print "SUCCESS:document_id" or "FAILURE:error_message"
      const pythonOutput = await runPythonScript(pythonScriptPath, pythonArgs);

      const successMatch = pythonOutput.match(/SUCCESS:(.+)$/m);
      if (successMatch) {
        const chromaDocId = successMatch[1].trim();
        // 3. Update MongoDB document with ChromaDB ID
        newDocument.processed = true;
        newDocument.chromaDocumentId = chromaDocId;
        await newDocument.save();

        // 4. Respond to frontend
        res.status(200).json({
          message: "File uploaded and processed successfully!",
          documentId: mongoDocumentId, // Send MongoDB ID back to frontend
          chromaDocumentId: chromaDocId,
        });
      } else {
        throw new Error(`Python processing failed: ${pythonOutput}`);
      }
    } catch (error: any) {
      console.error("File upload and processing error:", error);
      res
        .status(500)
        .json({ message: "Error processing file", error: error.message });
    } finally {
      // Optional: Clean up the uploaded file after processing
      // fs.unlink(filePath, (err) => {
      //   if (err) console.error('Error deleting temp file:', err);
      // });
    }
  }
);

// @route   POST /api/universal-qa
// @desc    Receives a query, retrieves context from ChromaDB, and gets AI response
app.post("/api/universal-qa", async (req: Request, res: Response) => {
  const { query, documentIds,workspaceId } = req.body; // documentIds will be an array of MongoDB IDs

  if (!query) {
    return res.status(400).json({ message: "Query is required." });
  }
  if(!workspaceId){
    return res.status(400).json({message:"Workspace ID is required."});
  }

  try {
    let chromaDocumentIds: string[] = [];

    // If specific document IDs are provided from frontend, find their ChromaDB IDs
    if (documentIds && documentIds.length > 0) {
      const documents = await DocumentModel.find({
        _id: { $in: documentIds },
        workspaceId:workspaceId,
        processed: true,
      });
      chromaDocumentIds = documents
        .map((doc) => doc.chromaDocumentId!)
        .filter(Boolean) as string[];
      if (chromaDocumentIds.length === 0) {
        return res
          .status(400)
          .json({
            message: "No processed documents found for the provided IDs.",
          });
      }
    } else {
      // If no specific document IDs are provided, query all processed documents
      const allProcessedDocs = await DocumentModel.find({ 
        workspaceId:workspaceId,
        processed: true,
       });
      chromaDocumentIds = allProcessedDocs
        .map((doc) => doc.chromaDocumentId!)
        .filter(Boolean) as string[];
      if (chromaDocumentIds.length === 0) {
        return res
          .status(400)
          .json({
            message:
              "No documents have been processed yet. Please upload a file first.",
          });
      }
    }

    // 1. Trigger Python script to query ChromaDB for relevant chunks
    const pythonScriptPath = path.join(
      __dirname,
      "../python_scripts/chroma_handler.py"
    );
    const queryArgs = ["query_documents", query, chromaDocumentIds.join(",")]; // Pass IDs as comma-separated string
    const relevantChunksJson = await runPythonScript(
      pythonScriptPath,
      queryArgs
    );
    // FIX: The Python script returns an array of objects, not strings.
    const relevantChunks: { text: string; source: string }[] = JSON.parse(relevantChunksJson);

    if (relevantChunks.length === 0) {
      return res.status(200).json({
        answer:
          "I couldn't find relevant information in the uploaded documents for your query. Please try rephrasing or upload more relevant files.",
        citations: [],
        nextSteps: [],
        chartData: undefined, // Ensure chartData is undefined if no relevant info
      });
    }

    // 2. Construct prompt for LLM (RAG)
    // FIX: Map the objects to their 'text' property to create the context.
    const context = relevantChunks.map(chunk => chunk.text).join("\n\n");
    const llmPrompt = `You are an intelligent assistant. Answer the following question based ONLY on the provided context. If the answer cannot be found in the context, state that you don't have enough information.
If the question asks for numerical comparison or data visualization, suggest a chart type (e.g., "bar chart", "line chart", "pie chart") and briefly describe what it would show.

Context:
${context}

Question: "${query}"

Answer:`;

    // 3. Call Google Gemini 2.5 Pro API
    const result = await geminiModel.generateContent({
      contents: [{ role: "user", parts: [{ text: llmPrompt }] }],
      safetySettings: [
        {
          category: HarmCategory.HARM_CATEGORY_HARASSMENT,
          threshold: HarmBlockThreshold.BLOCK_NONE,
        },
        {
          category: HarmCategory.HARM_CATEGORY_HATE_SPEECH,
          threshold: HarmBlockThreshold.BLOCK_NONE,
        },
        {
          category: HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
          threshold: HarmBlockThreshold.BLOCK_NONE,
        },
        {
          category: HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
          threshold: HarmBlockThreshold.BLOCK_NONE,
        },
      ],
    });

    const response = result.response;
    const aiAnswer = response.text();

    let chartData: string | undefined;
    let nextSteps: string[] = [];

    if(aiAnswer.toLowerCase().includes('chart') || aiAnswer.toLowerCase().includes('visualize')){
      chartData = 'A chart showing data from the context would be beneficial.';
      if (aiAnswer.toLowerCase().includes('bar chart')) chartData = "Bar chart showing comparison.";
      if (aiAnswer.toLowerCase().includes('line chart')) chartData = "Line chart showing trends over time.";
      if (aiAnswer.toLowerCase().includes('pie chart')) chartData = "Pie chart showing proportions.";
    }

    // 4. Extract citations (simplified for now)
    // FIX: Use the 'source' from the chunks for better citations.
    const citations = relevantChunks.map(chunk => chunk.source);

    // 5. Simulate chart data and next steps based on AI's answer
    // In a real app, you might use another LLM call or regex to extract chart/next step suggestions

    if (
      aiAnswer.toLowerCase().includes("chart") ||
      aiAnswer.toLowerCase().includes("visualize")
    ) {
      chartData = "A chart showing data from the context would be beneficial.";
      if (aiAnswer.toLowerCase().includes("bar chart"))
        chartData = "Bar chart showing comparison.";
      if (aiAnswer.toLowerCase().includes("line chart"))
        chartData = "Line chart showing trends over time.";
      if (aiAnswer.toLowerCase().includes("pie chart"))
        chartData = "Pie chart showing proportions.";
    }

    if (aiAnswer.toLowerCase().includes('suggested next steps')) {
      nextSteps = ["Review the detailed report.", "Discuss findings with the team."];
    } else if (aiAnswer.toLowerCase().includes('further analysis')) {
      nextSteps = ["Perform further analysis on identified areas."];
    }

    // 6. Respond to frontend
    res.status(200).json({
      answer: typeof aiAnswer === 'string' ? aiAnswer : JSON.stringify(aiAnswer),
      citations: citations,
      chartData: chartData,
      nextSteps: nextSteps,
    });
  } catch (error: any) {
    console.error("AI query error:", error);
    if (error.message.includes("API key not valid")) {
      res
        .status(401)
        .json({ message: "Gemini API key is invalid or not configured." });
    } else {
      res
        .status(500)
        .json({ message: "Error getting AI response", error: error.message });
    }
  }
});

// --- Basic Route ---
app.get("/", (req: Request, res: Response) => {
  res.send("CortexHub Backend is running and connected to MongoDB!");
});

// --- Start the Server ---
app.listen(PORT, () => {
  console.log(`CortexHub Backend listening on port ${PORT}`);
  console.log(`Access it at: http://localhost:${PORT}`);
});