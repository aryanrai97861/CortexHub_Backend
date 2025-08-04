# CortexHub Backend

## Overview
CortexHub Backend is the server-side component of the CortexHub platform, providing API endpoints, data processing, and integration with various AI and data processing services.

## Features
- Document processing and analysis
- AI-powered knowledge extraction
- Vector database integration for semantic search
- User authentication and authorization
- API endpoints for frontend integration
- File upload and management
- Data processing pipelines

## Tech Stack
- **Runtime**: Node.js with TypeScript
- **Web Framework**: Express.js
- **Database**: MongoDB, MySQL, ChromaDB (vector database)
- **AI/ML**: LangChain and LangGraph for AI workflows
- **Document Processing**: Various libraries for PDF, DOCX, XLSX, etc.
- **Environment Management**: dotenv

## Prerequisites
- Node.js (v18 or later)
- npm or yarn
- Python (for certain AI/ML components)
- ChromaDB (vector database)
- MongoDB
- MySQL


## Setup Instructions

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd cortexhubbackend
   ```

2. **Install dependencies**
   ```bash
   npm install
   # or
   yarn install
   ```

3. **Set up environment variables**
   Create a `.env` file in the root directory with the following variables:
   ```env
   PORT=3001
   NODE_ENV=development
   # Add other environment variables as needed
   ```

4. **Install Python dependencies**
   ```bash
   pip install -r requirements.txt
   ```

5. **Start the development server**
   ```bash
   npm run dev
   # or
   yarn dev
   ```

6. **Verify the server is running**
   The server should be running at `http://localhost:3001`

## API Documentation

### Available Endpoints
- `POST /api/upload` - Upload and process documents
- `GET /api/documents` - List all processed documents
- `GET /api/documents/:id` - Get a specific document
- `POST /api/query` - Query the knowledge base

## Development

### Project Structure
```
src/
  ├── config/       # Configuration files
  ├── controllers/  # Route controllers
  ├── models/       # Database models
  ├── routes/       # API routes
  ├── services/     # Business logic
  ├── utils/        # Utility functions
  └── server.ts     # Main application file
```

### Scripts
- `npm run dev` - Start development server with hot-reload
- `npm run build` - Build the application
- `npm start` - Start production server
- `npm test` - Run tests

## Deployment

1. Build the application:
   ```bash
   npm run build
   ```

2. Start the production server:
   ```bash
   npm start
   ```