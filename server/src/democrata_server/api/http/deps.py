import hashlib
import os
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status

from democrata_server.adapters.agents import (
    AgentConfig,
    create_context_retriever,
    create_data_extractor,
    create_query_planner,
    create_response_composer,
    create_response_verifier,
)
from democrata_server.adapters.auth.supabase import SupabaseAuthProvider
from democrata_server.adapters.billing.stripe import StripePaymentProvider
from democrata_server.adapters.cache.redis import RedisCache
from democrata_server.adapters.extraction import ContentTypeExtractor
from democrata_server.adapters.llm.factory import (
    Embedder,
    LLMClient,
    create_embedder,
    create_llm_client,
)
from democrata_server.adapters.storage.local import LocalBlobStore
from democrata_server.adapters.storage.postgres import (
    PostgresBillingAccountRepository,
    PostgresConnectionPool,
    PostgresInvitationRepository,
    PostgresMembershipRepository,
    PostgresOrganizationRepository,
    PostgresTransactionRepository,
    PostgresUserRepository,
)
from democrata_server.adapters.storage.qdrant import QdrantVectorStore
from democrata_server.adapters.usage.memory_store import (
    InMemoryAnonymousSessionStore,
    InMemoryBillingAccountStore,
    InMemoryJobStore,
)
from democrata_server.domain.agents.ports import (
    DataExtractor,
    QueryPlanner,
    ResponseComposer,
    ResponseVerifier,
)
from democrata_server.domain.auth.entities import User
from democrata_server.domain.ingestion.use_cases import IngestDocument
from democrata_server.domain.rag.ports import ContextRetriever
from democrata_server.domain.rag.use_cases import ExecuteQuery


@lru_cache
def get_blob_store() -> LocalBlobStore:
    return LocalBlobStore(base_path=os.getenv("BLOB_STORAGE_PATH", "./data/blobs"))


@lru_cache
def get_vector_store() -> QdrantVectorStore:
    return QdrantVectorStore(
        url=os.getenv("QDRANT_URL", "http://localhost:6333"),
        collection=os.getenv("QDRANT_COLLECTION", "democrata_chunks"),
        vector_size=int(os.getenv("EMBEDDING_DIMENSIONS", "768")),
    )


@lru_cache
def get_embedder() -> Embedder:
    return create_embedder()


@lru_cache
def get_llm_client() -> LLMClient:
    return create_llm_client()


@lru_cache
def get_cache() -> RedisCache:
    return RedisCache(url=os.getenv("REDIS_URL", "redis://localhost:6379/0"))


@lru_cache
def get_job_store() -> InMemoryJobStore:
    return InMemoryJobStore()


@lru_cache
def get_anonymous_session_store() -> InMemoryAnonymousSessionStore:
    return InMemoryAnonymousSessionStore()


@lru_cache
def get_billing_account_store() -> InMemoryBillingAccountStore:
    return InMemoryBillingAccountStore()


@lru_cache
def get_text_extractor() -> ContentTypeExtractor:
    return ContentTypeExtractor()


# --- Agent Dependencies ---


@lru_cache
def get_agent_config() -> AgentConfig:
    return AgentConfig.from_env()


@lru_cache
def get_query_planner() -> QueryPlanner:
    return create_query_planner(get_agent_config())


@lru_cache
def get_data_extractor() -> DataExtractor:
    return create_data_extractor(get_agent_config())


@lru_cache
def get_response_composer() -> ResponseComposer:
    return create_response_composer(get_agent_config())


@lru_cache
def get_response_verifier() -> ResponseVerifier | None:
    return create_response_verifier(get_agent_config())


@lru_cache
def get_context_retriever() -> ContextRetriever:
    return create_context_retriever(
        embedder=get_embedder(),
        vector_store=get_vector_store(),
        config=get_agent_config(),
    )


# --- Use Cases ---


def get_ingest_document_use_case() -> IngestDocument:
    return IngestDocument(
        blob_store=get_blob_store(),
        embedder=get_embedder(),
        vector_store=get_vector_store(),
        job_store=get_job_store(),
        text_extractor=get_text_extractor(),
    )


def get_execute_query_use_case() -> ExecuteQuery:
    return ExecuteQuery(
        planner=get_query_planner(),
        retriever=get_context_retriever(),
        extractor=get_data_extractor(),
        composer=get_response_composer(),
        verifier=get_response_verifier(),
        cache=get_cache(),
        cost_margin=float(os.getenv("COST_MARGIN", "0.4")),
    )


def get_session_id(request: Request) -> str:
    """Generate a session ID from client IP and user agent for anonymous tracking."""
    forwarded_for = request.headers.get("x-forwarded-for", "")
    if forwarded_for:
        client_ip = forwarded_for.split(",")[0].strip()
    elif request.client:
        client_ip = request.client.host
    else:
        client_ip = "unknown"
    user_agent = request.headers.get("user-agent", "unknown")
    fingerprint = f"{client_ip}|{user_agent}"
    return hashlib.sha256(fingerprint.encode()).hexdigest()[:16]


# --- Auth & User Dependencies ---


@lru_cache
def get_postgres_pool() -> PostgresConnectionPool:
    """Get the PostgreSQL connection pool (must be connected via lifespan)."""
    return PostgresConnectionPool(
        dsn=os.getenv("DATABASE_URL", "postgresql://democrata:democrata_dev@localhost:5432/democrata"),
    )


@lru_cache
def get_auth_provider() -> SupabaseAuthProvider:
    """Get the Supabase auth provider."""
    supabase_url = os.getenv("SUPABASE_URL", "")
    anon_key = os.getenv("SUPABASE_ANON_KEY", "")
    service_key = os.getenv("SUPABASE_SERVICE_KEY")

    if not supabase_url or not anon_key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_ANON_KEY must be configured")

    return SupabaseAuthProvider(
        supabase_url=supabase_url,
        supabase_anon_key=anon_key,
        supabase_service_key=service_key,
    )


async def ensure_user_exists_in_local_db(user: User) -> None:
    """
    Ensure the Supabase user exists in the local PostgreSQL database.
    
    When using Supabase Auth with a separate local database, users authenticate
    via Supabase but their records don't exist locally. This function creates
    the necessary auth.users and profiles records for foreign key constraints.
    """
    pool = get_postgres_pool()
    async with pool.pool.acquire() as conn:
        # Check if user exists in auth.users
        exists = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM auth.users WHERE id = $1)",
            user.id,
        )
        if not exists:
            # Create auth.users record
            await conn.execute(
                """
                INSERT INTO auth.users (id, email, email_confirmed_at, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (id) DO NOTHING
                """,
                user.id,
                user.email,
                user.created_at if user.email_verified else None,
                user.created_at,
                user.updated_at,
            )
            # Create profiles record
            await conn.execute(
                """
                INSERT INTO public.profiles (id, name, avatar_url, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (id) DO NOTHING
                """,
                user.id,
                user.name,
                user.avatar_url,
                user.created_at,
                user.updated_at,
            )


async def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
    auth_provider: SupabaseAuthProvider = Depends(get_auth_provider),
) -> User:
    """
    Extract and validate the current user from the Authorization header.

    Raises 401 if no valid token is provided.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization[7:]  # Remove "Bearer " prefix
    user = await auth_provider.get_user(token)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


async def get_current_user_optional(
    authorization: Annotated[str | None, Header()] = None,
    auth_provider: SupabaseAuthProvider = Depends(get_auth_provider),
) -> User | None:
    """
    Extract the current user if a valid token is provided, otherwise return None.

    Used for endpoints that support both authenticated and anonymous access.
    """
    if not authorization or not authorization.startswith("Bearer "):
        return None

    token = authorization[7:]
    return await auth_provider.get_user(token)


# --- Repository Dependencies ---


def get_user_repository() -> PostgresUserRepository:
    """Get the user repository."""
    return PostgresUserRepository(get_postgres_pool())


def get_organization_repository() -> PostgresOrganizationRepository:
    """Get the organization repository."""
    return PostgresOrganizationRepository(get_postgres_pool())


def get_membership_repository() -> PostgresMembershipRepository:
    """Get the membership repository."""
    return PostgresMembershipRepository(get_postgres_pool())


def get_invitation_repository() -> PostgresInvitationRepository:
    """Get the invitation repository."""
    return PostgresInvitationRepository(get_postgres_pool())


def get_billing_account_repository() -> PostgresBillingAccountRepository:
    """Get the billing account repository."""
    return PostgresBillingAccountRepository(get_postgres_pool())


def get_transaction_repository() -> PostgresTransactionRepository:
    """Get the transaction repository."""
    return PostgresTransactionRepository(get_postgres_pool())


# --- Payment Provider ---


@lru_cache
def get_payment_provider() -> StripePaymentProvider:
    """Get the Stripe payment provider."""
    secret_key = os.getenv("STRIPE_SECRET_KEY", "")
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET", "")

    if not secret_key:
        raise RuntimeError("STRIPE_SECRET_KEY must be configured")

    return StripePaymentProvider(
        secret_key=secret_key,
        webhook_secret=webhook_secret,
    )
