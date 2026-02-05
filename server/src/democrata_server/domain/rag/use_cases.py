import logging
import time
import asyncio
from dataclasses import dataclass

from democrata_server.domain.agents.entities import IntentResult
from democrata_server.domain.agents.ports import (
    DataExtractor,
    QueryPlanner,
    ResponseComposer,
    ResponseVerifier,
)
from democrata_server.domain.ingestion.ports import Embedder, VectorStore
from democrata_server.domain.usage.entities import CostBreakdown

from .entities import (
    Component,
    Layout,
    Notice,
    NoticeLevel,
    Query,
    QueryMetadata,
    RAGResult,
    Section,
    SourceReference,
    TextBlock,
    TextFormat,
)
from .ports import Cache, ContextRetriever

logger = logging.getLogger(__name__)


@dataclass
class ExecuteQueryResult:
    result: RAGResult
    cost: CostBreakdown


class ExecuteQuery:
    """
    Orchestrates the agent-based RAG pipeline.

    The pipeline consists of:
    1. Planner: Classifies query intent and extracts entities
    2. Retriever: Retrieves context using intent-driven strategies
    3. Extractor: Extracts grounded data from context for each component
    4. Composer: Formats extracted data into a structured response
    5. Verifier (optional): Validates response claims against context
    """

    def __init__(
        self,
        planner: QueryPlanner,
        retriever: ContextRetriever,
        extractor: DataExtractor,
        composer: ResponseComposer,
        cache: Cache,
        verifier: ResponseVerifier | None = None,
        cache_ttl_seconds: int = 3600,
        cost_margin: float = 0.4,
    ):
        self.planner = planner
        self.retriever = retriever
        self.extractor = extractor
        self.composer = composer
        self.verifier = verifier
        self.cache = cache
        self.cache_ttl_seconds = cache_ttl_seconds
        self.cost_margin = cost_margin

    async def execute(self, query: Query) -> ExecuteQueryResult:
        """Execute the agent-based RAG pipeline."""
        start_time = time.time()
        cache_key = self.cache.query_key(query)

        # Check cache
        cached = await self.cache.get(cache_key)
        if cached is not None:
            return ExecuteQueryResult(
                result=cached,
                cost=CostBreakdown.zero(),
            )

        total_input_tokens = 0
        total_output_tokens = 0
        model_used = "unknown"

        try:
            # Step 1: Plan - Classify intent and extract entities
            intent = await self.planner.analyze(query.text)
            logger.debug(
                f"Intent: {intent.query_type}, depth: {intent.response_depth.value}, "
                f"components: {intent.expected_components}"
            )

            # Step 2: Retrieve - Get context using intent-driven strategy
            retrieval = await self.retriever.retrieve(query.text, intent)

            # Step 3: Check sufficiency
            if not retrieval.is_sufficient:
                result = self._insufficient_data_response(query, intent, retrieval.warnings)
                processing_time_ms = int((time.time() - start_time) * 1000)
                result.metadata = QueryMetadata(
                    documents_retrieved=0,
                    chunks_used=len(retrieval.chunks),
                    processing_time_ms=processing_time_ms,
                    model=model_used,
                )
                return ExecuteQueryResult(
                    result=result,
                    cost=CostBreakdown.zero(),
                )

            # Step 4: Extract - Grounded extraction for each component type
            context_texts = retrieval.context_texts
            extraction_tasks = [
                self.extractor.extract(
                    component_type,
                    context_texts,
                    intent,
                )
                for component_type in intent.expected_components
            ]
            extractions = await asyncio.gather(*extraction_tasks)
            for extraction in extractions:
                logger.debug(
                    f"Extracted {extraction.component_type}: completeness={extraction.completeness}"
                )

            # Step 5: Compose - Format extracted data into response
            layout, components, token_usage = await self.composer.compose(
                query.text,
                intent,
                extractions,
            )
            total_input_tokens += token_usage.get("input_tokens", 0)
            total_output_tokens += token_usage.get("output_tokens", 0)
            model_used = token_usage.get("model", model_used)

            # Step 6: Verify (optional) - Check claims against context
            if self.verifier and context_texts:
                verification = await self.verifier.verify(layout, components, context_texts)
                if not verification.is_valid:
                    logger.warning(
                        f"Verification found issues: {len(verification.unsupported_claims)} claims"
                    )
                    components = self._filter_unsupported_claims(
                        components, verification
                    )

            processing_time_ms = int((time.time() - start_time) * 1000)

            # Aggregate sources from retrieved chunks
            sources = self._aggregate_sources(retrieval.chunks)

            # Build result
            result = RAGResult(
                layout=layout,
                components=components,
                metadata=QueryMetadata(
                    documents_retrieved=len(
                        set(c.document_id for c in retrieval.chunks)
                    ),
                    chunks_used=len(retrieval.chunks),
                    processing_time_ms=processing_time_ms,
                    model=model_used,
                ),
                sources=sources,
                cached=False,
            )

            # Calculate cost (approximate tokens for planner/extractor)
            embedding_tokens = len(query.text.split()) * len(intent.rewritten_queries)
            vector_queries = (
                len(intent.rewritten_queries)
                if intent.retrieval_strategy.value == "multi_entity"
                else 1
            )

            cost = CostBreakdown.calculate(
                embedding_tokens=embedding_tokens,
                llm_input_tokens=total_input_tokens,
                llm_output_tokens=total_output_tokens,
                vector_queries=vector_queries,
                margin=self.cost_margin,
            )

            result.cost = cost

            # Cache result
            await self.cache.set(cache_key, result, self.cache_ttl_seconds)

            return ExecuteQueryResult(result=result, cost=cost)

        except Exception as e:
            logger.exception(f"Pipeline error: {e}")
            return self._error_response(query, str(e), start_time)

    def _insufficient_data_response(
        self,
        query: Query,
        intent: IntentResult,
        warnings: list[str],
    ) -> RAGResult:
        """Generate a response when insufficient context is available."""
        warning_text = "; ".join(warnings) if warnings else "Limited relevant information found."

        notice = Component.create(
            Notice(
                message=f"Unable to fully answer this query: {warning_text}",
                level=NoticeLevel.WARNING,
                title="Limited Information",
            )
        )

        suggestion_text = (
            f"The query '{query.text}' could not be fully answered. "
            f"Try:\n"
            f"- Using different keywords\n"
            f"- Narrowing the date range\n"
            f"- Specifying particular politicians or parties"
        )

        text = Component.create(
            TextBlock(
                content=suggestion_text,
                format=TextFormat.MARKDOWN,
            )
        )

        section = Section(component_ids=[notice.id, text.id])
        layout = Layout(
            title="Unable to Answer Query",
            subtitle="Insufficient information available",
            sections=[section],
        )

        return RAGResult(
            layout=layout,
            components=[notice, text],
            metadata=QueryMetadata(
                documents_retrieved=0,
                chunks_used=0,
                processing_time_ms=0,
                model="none",
            ),
            cached=False,
        )

    def _filter_unsupported_claims(
        self,
        components: list[Component],
        verification: "VerificationResult",
    ) -> list[Component]:
        """Add a notice about verification issues without removing components."""
        from democrata_server.domain.agents.entities import VerificationResult

        if not verification.unsupported_claims:
            return components

        # Count severity
        errors = [c for c in verification.unsupported_claims if c.severity == "error"]

        if errors:
            notice = Component.create(
                Notice(
                    message="Some information could not be fully verified against source documents. Please verify critical facts independently.",
                    level=NoticeLevel.WARNING,
                    title="Verification Warning",
                )
            )
            # Insert at position 1 (after first component)
            components.insert(min(1, len(components)), notice)

        return components

    def _error_response(
        self,
        query: Query,
        error: str,
        start_time: float,
    ) -> ExecuteQueryResult:
        """Generate a response when the pipeline encounters an error."""
        processing_time_ms = int((time.time() - start_time) * 1000)

        notice = Component.create(
            Notice(
                message="An error occurred while processing your query. Please try again.",
                level=NoticeLevel.WARNING,
                title="Error",
            )
        )

        section = Section(component_ids=[notice.id])
        layout = Layout(
            title="Error Processing Query",
            sections=[section],
        )

        result = RAGResult(
            layout=layout,
            components=[notice],
            metadata=QueryMetadata(
                documents_retrieved=0,
                chunks_used=0,
                processing_time_ms=processing_time_ms,
                model="error",
            ),
            cached=False,
        )

        return ExecuteQueryResult(
            result=result,
            cost=CostBreakdown.zero(),
        )

    def _aggregate_sources(self, chunks: list) -> list[SourceReference]:
        """Aggregate unique document sources from retrieved chunks."""
        seen_docs: dict[str, SourceReference] = {}
        for chunk in chunks:
            doc_id = str(chunk.document_id)
            if doc_id not in seen_docs:
                seen_docs[doc_id] = SourceReference(
                    document_id=doc_id,
                    source_name=chunk.metadata.get("source_name", "Unknown"),
                    source_url=chunk.metadata.get("source_url") or None,
                    source_date=chunk.metadata.get("source_date") or None,
                )
        return list(seen_docs.values())
