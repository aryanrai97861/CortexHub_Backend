# backend/python_scripts/knowledge_graph_generator.py

import os
import sys
import json
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from typing import List, Optional

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser

# Load environment variables
load_dotenv()

# --- Configuration ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    print("GEMINI_API_KEY not found in .env.", file=sys.stderr)
    sys.exit(1)

# Define the models for structured output
class Concept(BaseModel):
    id: str = Field(..., description="Unique ID for the concept (e.g., 'concept_1')")
    name: str = Field(..., description="The name of the concept (e.g., 'CortexHub', 'AI Agents')")
    description: Optional[str] = Field(None, description="A brief description of the concept.")

class Relationship(BaseModel):
    source: str = Field(..., description="The ID of the source concept")
    target: str = Field(..., description="The ID of the target concept")
    type: str = Field(..., description="The type of relationship (e.g., 'is_a', 'uses', 'is_powered_by')")
    description: Optional[str] = Field(None, description="A brief description of the relationship.")

class KnowledgeGraph(BaseModel):
    concepts: List[Concept]
    relationships: List[Relationship]

# --- Prompt and Output Parser ---
parser = JsonOutputParser(pydantic_object=KnowledgeGraph)

prompt_template = """
You are an expert at extracting and structuring knowledge from text. Your task is to analyze the following context and identify key concepts and their relationships.

Follow these rules:
1. Identify at least 3 to 5 key concepts.
2. For each concept, provide a unique ID, a name, and a short description.
3. Identify the relationships between these concepts. For each relationship, provide a source concept ID, a target concept ID, and a relationship type.
4. The output must be a single JSON object.

Context:
{context}

{format_instructions}

JSON Output:
"""

prompt = PromptTemplate(
    template=prompt_template,
    input_variables=["context"],
    partial_variables={"format_instructions": parser.get_format_instructions()}
)

# --- LLM and Chain ---
model = ChatGoogleGenerativeAI(model="gemini-2.5-pro", google_api_key=GEMINI_API_KEY, temperature=0.1)
chain = prompt | model | parser

# --- Main execution block for when script is called by Node.js ---
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python script.py <operation> [args...]", file=sys.stderr)
        sys.exit(1)
        
    operation = sys.argv[1]

    if operation == "generate_graph":
        if len(sys.argv) < 3:
            print("Usage: python script.py generate_graph <text_context>", file=sys.stderr)
            sys.exit(1)

        text_context = sys.argv[2]
        
        try:
            # Invoke the chain with the provided context
            graph = chain.invoke({"context": text_context})
            
            # Print the structured JSON result to stdout
            print(json.dumps(graph))
        except Exception as e:
            error_result = {"error": str(e), "message": "Failed to generate knowledge graph."}
            print(json.dumps(error_result), file=sys.stderr)
            sys.exit(1)
    
    else:
        print(f"Unknown operation: {operation}", file=sys.stderr)
        sys.exit(1)