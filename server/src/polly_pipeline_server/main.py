from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI

from polly_pipeline_server.api.http import router

# Load .env from project root (parent of server/)
project_root = Path(__file__).parent.parent.parent.parent
load_dotenv(project_root / ".env")
from polly_pipeline_server.api.http.middleware.cors import setup_cors

app = FastAPI(
    title="Demócrata",
    description="Political data ingestion and RAG query API",
    version="0.1.0",
)

setup_cors(app)
app.include_router(router)
