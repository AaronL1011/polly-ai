"""Factory functions for creating agent instances."""

from typing import Any

from democrata_server.domain.agents.ports import (
    DataExtractor,
    QueryPlanner,
    ResponseComposer,
    ResponseVerifier,
)
from democrata_server.domain.rag.ports import ContextRetriever

from .config import AgentConfig
from .composer import LLMResponseComposer
from .extractor import LLMDataExtractor
from .planner import LLMQueryPlanner
from .retriever import IntentDrivenRetriever
from .verifier import LLMResponseVerifier


def create_query_planner(config: AgentConfig | None = None) -> QueryPlanner:
    """Create a query planner instance."""
    config = config or AgentConfig.from_env()

    return LLMQueryPlanner(
        api_key=config.openai_api_key,
        base_url=config.openai_base_url,
        model=config.planner_model,
        temperature=0.1,  # Low temperature for consistent classification
    )


def create_data_extractor(config: AgentConfig | None = None) -> DataExtractor:
    """Create a data extractor instance."""
    config = config or AgentConfig.from_env()

    return LLMDataExtractor(
        api_key=config.openai_api_key,
        base_url=config.openai_base_url,
        model=config.extractor_model,
        temperature=0.1,  # Low temperature for accurate extraction
    )


def create_response_composer(config: AgentConfig | None = None) -> ResponseComposer:
    """Create a response composer instance."""
    config = config or AgentConfig.from_env()

    return LLMResponseComposer(
        api_key=config.openai_api_key,
        base_url=config.openai_base_url,
        model=config.composer_model,
        temperature=0.3,  # Slightly higher for more natural responses
    )


def create_response_verifier(config: AgentConfig | None = None) -> ResponseVerifier | None:
    """Create a response verifier instance if enabled."""
    config = config or AgentConfig.from_env()

    if not config.verifier_enabled:
        return None

    return LLMResponseVerifier(
        api_key=config.openai_api_key,
        base_url=config.openai_base_url,
        model=config.verifier_model,
        temperature=0.1,  # Low temperature for consistent verification
    )


def create_context_retriever(
    embedder: Any,
    vector_store: Any,
    config: AgentConfig | None = None,
) -> ContextRetriever:
    """Create a context retriever instance."""
    config = config or AgentConfig.from_env()

    return IntentDrivenRetriever(
        embedder=embedder,
        vector_store=vector_store,
        default_top_k=config.default_top_k,
        min_chunks_for_sufficiency=config.min_chunks_for_sufficiency,
    )
