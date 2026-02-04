"""LLM-based query planner for intent classification and entity extraction."""

import logging

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from polly_pipeline_server.domain.agents.entities import (
    ExtractedEntities,
    IntentResult,
    QueryType,
    ResponseDepth,
    RetrievalStrategy,
)

from .prompts.planner import PLANNER_PROMPT
from .schemas import PlannerOutputSchema

logger = logging.getLogger(__name__)


class LLMQueryPlanner:
    """Query planner that uses an LLM to classify intent and extract entities."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str = "gpt-4o-mini",
        temperature: float = 0.1,
    ):
        base_llm = ChatOpenAI(
            api_key=api_key,
            base_url=base_url,
            model=model,
            temperature=temperature,
        )
        self.llm = base_llm.with_structured_output(PlannerOutputSchema)
        self.model = model

    async def analyze(self, query: str) -> IntentResult:
        """Classify query intent and extract entities."""
        prompt = PLANNER_PROMPT.format(query=query)

        messages = [
            SystemMessage(content="You are a query analyzer for an Australian political information system."),
            HumanMessage(content=prompt),
        ]

        try:
            response: PlannerOutputSchema = await self.llm.ainvoke(messages)
            return self._build_intent_result(response, query)
        except Exception as e:
            logger.warning(f"Planner failed, using default intent: {e}")
            return IntentResult.default_factual(query)

    def _build_intent_result(self, data: PlannerOutputSchema, original_query: str) -> IntentResult:
        """Build IntentResult from structured output schema."""
        # Parse query type
        try:
            query_type = QueryType(data.query_type)
        except ValueError:
            query_type = QueryType.FACTUAL

        # Parse retrieval strategy
        try:
            retrieval_strategy = RetrievalStrategy(data.retrieval_strategy)
        except ValueError:
            retrieval_strategy = RetrievalStrategy.SINGLE_FOCUS

        # Parse entities from the nested schema
        entities = ExtractedEntities(
            parties=data.entities.parties,
            members=data.entities.members,
            bills=data.entities.bills,
            topics=data.entities.topics,
            date_from=data.entities.date_from,
            date_to=data.entities.date_to,
            document_types=data.entities.document_types,
        )

        # Parse expected components
        expected_components = data.expected_components or ["text_block"]

        # Parse rewritten queries
        rewritten_queries = data.rewritten_queries or [original_query]

        # Parse response depth
        try:
            response_depth = ResponseDepth(data.response_depth)
        except ValueError:
            response_depth = ResponseDepth.STANDARD

        return IntentResult(
            query_type=query_type,
            entities=entities,
            expected_components=expected_components,
            retrieval_strategy=retrieval_strategy,
            rewritten_queries=rewritten_queries,
            confidence=data.confidence,
            response_depth=response_depth,
        )
