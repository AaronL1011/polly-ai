import logging
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI

# Load .env from project root (parent of server/)
project_root = Path(__file__).parent.parent.parent.parent
load_dotenv(project_root / ".env")

from democrata_server.api.http import router
from democrata_server.api.http.deps import get_postgres_pool
from democrata_server.api.http.middleware.cors import setup_cors

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown tasks."""
    # Startup
    logger.info("Starting up Demócrata server...")

    # Initialize PostgreSQL connection pool
    try:
        pool = get_postgres_pool()
        await pool.connect()
        logger.info("PostgreSQL connection pool initialized")
    except Exception as e:
        logger.warning(f"PostgreSQL connection failed (may not be configured): {e}")

    yield

    # Shutdown
    logger.info("Shutting down Demócrata server...")
    try:
        pool = get_postgres_pool()
        await pool.disconnect()
        logger.info("PostgreSQL connection pool closed")
    except Exception:
        pass


app = FastAPI(
    title="Demócrata",
    description="Political data ingestion and RAG query API",
    version="0.1.0",
    lifespan=lifespan,
)

setup_cors(app)
app.include_router(router)
