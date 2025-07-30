# backend/python_scripts/chroma_handler.py

import os
import sys
import json
from dotenv import load_dotenv
import chromadb
from chromadb.utils import embedding_functions # Import for ChromaDB's embedding function integration
from langchain_community.document_loaders import (
    PyPDFLoader,
    CSVLoader,
    UnstructuredWordDocumentLoader, # Handles .doc and .docx
    TextLoader,
    UnstructuredExcelLoader # For .xlsx files
)
# from langchain_google_genai import GoogleGenerativeAIEmbeddings # Uncomment for Gemini Embeddings
# from langchain_community.embeddings import SentenceTransformerEmbeddings # Not directly used with Chroma's embedding_function setup
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Load environment variables from .env file
load_dotenv()

# --- Configuration ---
# ChromaDB client setup
# Using PersistentClient for local storage. Data will be saved in './chroma_db' folder.
# For production, consider chromadb.HttpClient to connect to a separate ChromaDB server.
try:
    client = chromadb.PersistentClient(path="./chroma_db")
except Exception as e:
    print(f"Error initializing ChromaDB PersistentClient: {e}", file=sys.stderr)
    sys.exit(1)

COLLECTION_NAME = "cortexhub_documents"

# Choose your embedding function for ChromaDB
# Option 1: Use SentenceTransformer (local, default)
try:
    # This automatically downloads the model the first time it's used
    default_embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )
    print("Using SentenceTransformerEmbeddingFunction.", file=sys.stderr)
except Exception as e:
    print(f"Error initializing SentenceTransformerEmbeddingFunction: {e}", file=sys.stderr)
    print("Ensure 'sentence-transformers' is installed and model can be downloaded.", file=sys.stderr)
    sys.exit(1)

# Option 2: Use Google Gemini Embeddings (requires API key)
# Uncomment the following lines if you want to use Gemini embeddings
# GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
# if not GEMINI_API_KEY:
#     print("GEMINI_API_KEY not found in .env. Cannot use GoogleGenerativeAIEmbeddingFunction.", file=sys.stderr)
#     sys.exit(1)
# default_embedding_function = embedding_functions.GoogleGenerativeAIEmbeddingFunction(
#     api_key=GEMINI_API_KEY,
#     model_name="models/embedding-001" # Or "text-embedding-004" for newer models
# )
# print("Using GoogleGenerativeAIEmbeddingFunction.", file=sys.stderr)


# --- Functions for Document Processing and RAG ---

def get_or_create_collection():
    """Gets or creates a ChromaDB collection, handling embedding function conflicts."""
    try:
        # First, try to get existing collection without specifying embedding function
        try:
            collection = client.get_collection(name=COLLECTION_NAME)
            print(f"Found existing ChromaDB collection '{COLLECTION_NAME}'.", file=sys.stderr)
            return collection
        except Exception:
            # Collection doesn't exist, create it with our embedding function
            collection = client.create_collection(
                name=COLLECTION_NAME,
                embedding_function=default_embedding_function
            )
            print(f"Created new ChromaDB collection '{COLLECTION_NAME}' with SentenceTransformer embedding.", file=sys.stderr)
            return collection
            
    except Exception as e:
        # If we get an embedding function conflict, delete and recreate
        if "embedding function" in str(e).lower() and "conflict" in str(e).lower():
            print(f"Embedding function conflict detected. Recreating collection...", file=sys.stderr)
            try:
                client.delete_collection(name=COLLECTION_NAME)
                collection = client.create_collection(
                    name=COLLECTION_NAME,
                    embedding_function=default_embedding_function
                )
                print(f"Successfully recreated ChromaDB collection '{COLLECTION_NAME}'.", file=sys.stderr)
                return collection
            except Exception as recreate_error:
                print(f"Error recreating collection: {recreate_error}", file=sys.stderr)
                sys.exit(1)
        else:
            print(f"Error with ChromaDB collection: {e}", file=sys.stderr)
            sys.exit(1)

def load_and_chunk_document(file_path: str, file_type: str):
    """Loads and chunks a document based on its type."""
    loader = None
    if file_type == 'application/pdf':
        loader = PyPDFLoader(file_path)
    elif file_type == 'text/csv':
        loader = CSVLoader(file_path)
    elif file_type in ['application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'application/msword']:
        loader = UnstructuredWordDocumentLoader(file_path) # Handles .doc and .docx
    elif file_type in ['application/vnd.openxmlformats-officedocument.spreadsheetml.sheet']:
        loader = UnstructuredExcelLoader(file_path) # Handles .xlsx
    elif file_type == 'text/plain':
        loader = TextLoader(file_path)
    else:
        # Fallback for other types or if mimetype is generic
        try:
            # Requires `pip install unstructured` and potentially other dependencies
            from langchain_community.document_loaders import UnstructuredFileLoader
            loader = UnstructuredFileLoader(file_path)
            print(f"Using UnstructuredFileLoader for {file_type}. Ensure 'unstructured' and its dependencies are installed.", file=sys.stderr)
        except ImportError:
            print("UnstructuredFileLoader not available. Please install 'unstructured' and its dependencies for broader file support.", file=sys.stderr)
            raise ValueError(f"Unsupported file type: {file_type}. Install 'unstructured' for more formats.")

    if not loader:
        raise ValueError(f"No suitable loader found for file type: {file_type}")

    documents = loader.load()
    
    if not documents:
        print(f"Loader returned no documents for {file_path}. File might be empty or unreadable.", file=sys.stderr)
        return []

    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    chunks = text_splitter.split_documents(documents)
    return chunks

def embed_and_store_document(file_path: str, file_type: str, document_id: str):
    """Embeds document chunks and stores them in ChromaDB."""
    try:
        chunks = load_and_chunk_document(file_path, file_type)
        if not chunks:
            print("No chunks found after loading and splitting document. Skipping embedding.", file=sys.stderr)
            return None

        collection = get_or_create_collection()

        ids = []
        texts = []
        metadatas = []

        for i, chunk in enumerate(chunks):
            chunk_id = f"{document_id}-{i}"
            ids.append(chunk_id)
            texts.append(chunk.page_content)
            
            chunk_metadata = {
                "document_id": document_id,
                "filename": os.path.basename(file_path),
                "chunk_index": i,
                "file_type": file_type,
            }
            # Add page number for PDFs if available
            if file_type == 'application/pdf' and 'page' in chunk.metadata:
                chunk_metadata["page"] = chunk.metadata["page"]
            
            # Add other relevant metadata from LangChain loader if present
            for key, value in chunk.metadata.items():
                if key not in chunk_metadata and isinstance(value, (str, int, float, bool)):
                    chunk_metadata[key] = value

            metadatas.append(chunk_metadata)

        # Add documents to ChromaDB. Embeddings are generated by the collection's embedding_function.
        collection.add(
            documents=texts,
            metadatas=metadatas,
            ids=ids
        )
        print(f"Successfully embedded and stored {len(chunks)} chunks for document ID: {document_id}", file=sys.stderr)
        return document_id
    except Exception as e:
        print(f"Error in embed_and_store_document: {e}", file=sys.stderr)
        # FIX: Clean up the uploaded file if processing failed
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"Cleaned up temporary file: {file_path}", file=sys.stderr)
        sys.exit(1)

def query_documents(query_text: str, document_ids: list[str], k: int = 4):
    """Queries ChromaDB for relevant chunks and returns their content and source metadata."""
    try:
        collection = get_or_create_collection()
        
        where_clause = {"document_id": {"$in": document_ids}} if document_ids else {}

        # CRITICAL FIX: query_texts expects a list, and embeddings are generated by collection's function
        results = collection.query(
            query_texts=[query_text], # Pass query text directly, collection uses its embedding function
            n_results=k,
            where=where_clause,
            include=['documents', 'metadatas']
        )
        
        # FIX: Format results to include text content and source information
        formatted_results = []
        if results['documents'] and results['documents'][0]:
            for i, doc_content in enumerate(results['documents'][0]):
                metadata = results['metadatas'][0][i]
                source_info = metadata.get('filename', 'Unknown Source')
                if 'page' in metadata:
                    source_info += f" (Page {metadata['page']})"
                
                formatted_results.append({
                    "text": doc_content,
                    "source": source_info
                })
        return formatted_results
    except Exception as e:
        print(f"Error in query_documents: {e}", file=sys.stderr)
        sys.exit(1)

# --- Main execution block for when script is called by Node.js ---
if __name__ == "__main__":
    # This block is executed when Node.js calls this script
    # It expects arguments from Node.js: operation, then data
    operation = sys.argv[1]

    if operation == "embed_document":
        file_path = sys.argv[2]
        file_type = sys.argv[3]
        document_id = sys.argv[4]
        try:
            result_id = embed_and_store_document(file_path, file_type, document_id)
            if result_id:
                print(f"SUCCESS:{result_id}") # Node.js will parse this
            else:
                # This case should ideally not be reached if embed_and_store_document handles errors
                print("FAILURE:Embedding failed (no document ID returned)", file=sys.stderr)
                sys.exit(1)
        except Exception as e:
            print(f"FAILURE:Embedding process failed: {e}", file=sys.stderr)
            sys.exit(1)

    elif operation == "query_documents":
        query_text = sys.argv[2]
        # document_ids are passed as a comma-separated string, parse it
        document_ids_str = sys.argv[3]
        document_ids = document_ids_str.split(',') if document_ids_str else []
        
        try:
            relevant_chunks_with_sources = query_documents(query_text, document_ids)
            # Output relevant chunks as JSON for Node.js to parse
            print(json.dumps(relevant_chunks_with_sources)) # Only JSON goes to stdout
        except Exception as e:
            print(f"FAILURE:Query process failed: {e}", file=sys.stderr)
            sys.exit(1)

    else:
        print(f"Unknown operation: {operation}", file=sys.stderr)
        sys.exit(1)