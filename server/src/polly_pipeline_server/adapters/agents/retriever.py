import asyncio
import logging
from typing import Any

from polly_pipeline_server.domain.agents.entities import IntentResult, RetrievalStrategy
from polly_pipeline_server.domain.rag.entities import RetrievalResult

logger = logging.getLogger(__name__)


class IntentDrivenRetriever:
    """Retriever that uses intent classification to optimize context retrieval."""

    def __init__(
        self,
        embedder: Any,  # Embedder protocol
        vector_store: Any,  # VectorStore protocol
        default_top_k: int = 10,
        min_chunks_for_sufficiency: int = 3,
    ):
        self.embedder = embedder
        self.vector_store = vector_store
        self.default_top_k = default_top_k
        self.min_chunks_for_sufficiency = min_chunks_for_sufficiency

    async def retrieve(
        self,
        query: str,
        intent: IntentResult,
    ) -> RetrievalResult:
        """Retrieve context chunks based on query and classified intent."""
        strategy = intent.retrieval_strategy

        if strategy == RetrievalStrategy.MULTI_ENTITY:
            return await self._retrieve_multi_entity(query, intent)
        elif strategy == RetrievalStrategy.CHRONOLOGICAL:
            return await self._retrieve_chronological(query, intent)
        elif strategy == RetrievalStrategy.BROAD:
            return await self._retrieve_broad(query, intent)
        else:  # SINGLE_FOCUS
            return await self._retrieve_single_focus(query, intent)

    async def _retrieve_single_focus(
        self,
        query: str,
        intent: IntentResult,
    ) -> RetrievalResult:
        """Standard single embedding search."""
        embedding = await self.embedder.embed_single(query)
        filters = self._build_filters(intent)

        chunks = await self.vector_store.search(
            vector=embedding,
            k=self.default_top_k,
            filters=filters,
        )

        is_sufficient = len(chunks) >= self.min_chunks_for_sufficiency

        return RetrievalResult(
            chunks=chunks,
            strategy_used=RetrievalStrategy.SINGLE_FOCUS.value,
            is_sufficient=is_sufficient,
            warnings=[] if is_sufficient else ["Few relevant documents found"],
        )

    async def _retrieve_multi_entity(
        self,
        query: str,
        intent: IntentResult,
    ) -> RetrievalResult:
        """Parallel searches for multiple entities, then merge and dedupe."""
        rewritten_queries = intent.rewritten_queries
        if not rewritten_queries:
            rewritten_queries = [query]

        # Execute parallel searches
        search_tasks = []
        for rq in rewritten_queries:
            search_tasks.append(self._search_single(rq, intent))

        results = await asyncio.gather(*search_tasks, return_exceptions=True)

        # Merge and dedupe chunks
        all_chunks = []
        seen_ids = set()
        coverage: dict[str, float] = {}

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.warning(f"Search failed for query {i}: {result}")
                continue

            query_chunks = result
            coverage[rewritten_queries[i]] = len(query_chunks) / self.default_top_k

            for chunk in query_chunks:
                chunk_id = str(chunk.id)
                if chunk_id not in seen_ids:
                    seen_ids.add(chunk_id)
                    all_chunks.append(chunk)

        # Sort by relevance (assuming chunks have a score or position)
        # For now, keep order from retrieval
        chunks = all_chunks[: self.default_top_k * 2]  # Allow more for multi-entity

        is_sufficient = len(chunks) >= self.min_chunks_for_sufficiency

        return RetrievalResult(
            chunks=chunks,
            strategy_used=RetrievalStrategy.MULTI_ENTITY.value,
            coverage=coverage,
            is_sufficient=is_sufficient,
            warnings=[] if is_sufficient else ["Limited coverage for some entities"],
        )

    async def _retrieve_chronological(
        self,
        query: str,
        intent: IntentResult,
    ) -> RetrievalResult:
        """Date-filtered search for chronological queries."""
        embedding = await self.embedder.embed_single(query)
        filters = self._build_filters(intent)

        chunks = await self.vector_store.search(
            vector=embedding,
            k=self.default_top_k,
            filters=filters,
        )

        # Sort chunks by date if available in metadata
        sorted_chunks = sorted(
            chunks,
            key=lambda c: c.metadata.get("date", "9999-99-99"),
        )

        is_sufficient = len(sorted_chunks) >= self.min_chunks_for_sufficiency

        return RetrievalResult(
            chunks=sorted_chunks,
            strategy_used=RetrievalStrategy.CHRONOLOGICAL.value,
            is_sufficient=is_sufficient,
            warnings=[] if is_sufficient else ["Few chronological events found"],
        )

    async def _retrieve_broad(
        self,
        query: str,
        intent: IntentResult,
    ) -> RetrievalResult:
        """Broader search with diversity for analytical queries."""
        embedding = await self.embedder.embed_single(query)
        # Don't apply strict filters for broad search
        filters = {}
        if intent.entities.document_types:
            filters["document_type"] = intent.entities.document_types

        # Retrieve more chunks for diversity
        chunks = await self.vector_store.search(
            vector=embedding,
            k=self.default_top_k + 10,
            filters=filters if filters else None,
        )

        is_sufficient = len(chunks) >= self.min_chunks_for_sufficiency

        return RetrievalResult(
            chunks=chunks,
            strategy_used=RetrievalStrategy.BROAD.value,
            is_sufficient=is_sufficient,
            warnings=[] if is_sufficient else ["Limited diverse content found"],
        )

    async def _search_single(
        self,
        query: str,
        intent: IntentResult,
    ) -> list[Any]:
        """Execute a single search for a rewritten query."""
        embedding = await self.embedder.embed_single(query)
        filters = self._build_filters(intent)

        chunks = await self.vector_store.search(
            vector=embedding,
            k=self.default_top_k // 2,  # Smaller k for multi-entity
            filters=filters,
        )

        return chunks

    def _build_filters(self, intent: IntentResult) -> dict[str, Any] | None:
        """Build vector store filters from intent entities."""
        filters: dict[str, Any] = {}

        if intent.entities.document_types:
            filters["document_type"] = intent.entities.document_types

        if intent.entities.date_from:
            filters["date_from"] = intent.entities.date_from

        if intent.entities.date_to:
            filters["date_to"] = intent.entities.date_to

        return filters if filters else None
