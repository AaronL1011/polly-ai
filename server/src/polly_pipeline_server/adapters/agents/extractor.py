"""LLM-based data extractor for grounded extraction from context."""

import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from polly_pipeline_server.domain.agents.entities import (
    ExtractionResult,
    IntentResult,
    SourceQuote,
)

from .prompts.extractor import EXTRACTION_PROMPTS, GENERIC_EXTRACTION_PROMPT
from .schemas import BaseExtractionSchema, get_extraction_schema

logger = logging.getLogger(__name__)


class LLMDataExtractor:
    """Data extractor that uses an LLM to extract grounded, structured data."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str = "gpt-4o",
        temperature: float = 0.1,
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.temperature = temperature

    def _get_structured_llm(self, component_type: str) -> Any:
        """Get an LLM configured with structured output for the given component type."""
        schema = get_extraction_schema(component_type)
        base_llm = ChatOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            model=self.model,
            temperature=self.temperature,
        )
        return base_llm.with_structured_output(schema)

    async def extract(
        self,
        component_type: str,
        context: list[str],
        intent: IntentResult,
    ) -> ExtractionResult:
        """Extract structured data from context for a specific component type."""
        if not context:
            return ExtractionResult.empty(component_type, "No context available")

        prompt = self._build_prompt(component_type, context, intent)
        structured_llm = self._get_structured_llm(component_type)

        messages = [
            SystemMessage(content="You are a data extractor. Extract only facts explicitly stated in the context."),
            HumanMessage(content=prompt),
        ]

        try:
            response: BaseExtractionSchema = await structured_llm.ainvoke(messages)
            return self._build_extraction_result(response, component_type)
        except Exception as e:
            logger.warning(f"Extraction failed for {component_type}: {e}")
            return ExtractionResult.empty(component_type, str(e))

    def _build_prompt(
        self,
        component_type: str,
        context: list[str],
        intent: IntentResult,
    ) -> str:
        """Build the extraction prompt for the given component type."""
        prompt_template = EXTRACTION_PROMPTS.get(component_type, GENERIC_EXTRACTION_PROMPT)
        context_text = "\n\n---\n\n".join(context)

        # Build query focus from intent
        query_focus_parts = []
        if intent.entities.parties:
            query_focus_parts.append(f"Parties: {', '.join(intent.entities.parties)}")
        if intent.entities.members:
            query_focus_parts.append(f"Members: {', '.join(intent.entities.members)}")
        if intent.entities.bills:
            query_focus_parts.append(f"Bills: {', '.join(intent.entities.bills)}")
        if intent.entities.topics:
            query_focus_parts.append(f"Topics: {', '.join(intent.entities.topics)}")

        query_focus = "; ".join(query_focus_parts) if query_focus_parts else "General query"

        # Format the prompt
        format_kwargs: dict[str, Any] = {
            "context": context_text,
            "query_focus": query_focus,
        }

        # Add entities for comparison prompts
        if component_type == "comparison" and intent.entities.parties:
            format_kwargs["entities"] = ", ".join(intent.entities.parties)
        elif component_type == "comparison":
            format_kwargs["entities"] = "entities mentioned in context"

        # Handle component_type for generic prompt
        if component_type not in EXTRACTION_PROMPTS:
            format_kwargs["component_type"] = component_type

        return prompt_template.format(**format_kwargs)

    def _build_extraction_result(
        self, data: BaseExtractionSchema, component_type: str
    ) -> ExtractionResult:
        """Build ExtractionResult from structured output schema."""
        # Extract source quotes
        source_quotes = [SourceQuote(text=quote) for quote in data.source_quotes]

        # Convert schema to dict for extracted_data, excluding base fields
        data_dict = data.model_dump(exclude={"source_quotes", "completeness", "warnings"})

        return ExtractionResult(
            component_type=component_type,
            extracted_data=data_dict,
            source_quotes=source_quotes,
            completeness=data.completeness,
            warnings=data.warnings,
        )
