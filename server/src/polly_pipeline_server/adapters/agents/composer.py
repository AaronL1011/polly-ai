"""LLM-based response composer for formatting extracted data into components."""

import json
import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from polly_pipeline_server.domain.agents.entities import ExtractionResult, IntentResult
from polly_pipeline_server.domain.rag.entities import (
    Component,
    Layout,
    Notice,
    NoticeLevel,
    Section,
    TextBlock,
    TextFormat,
)

from polly_pipeline_server.adapters.llm.components import parse_component

from .prompts.composer import COMPOSER_PROMPT

logger = logging.getLogger(__name__)


class LLMResponseComposer:
    """Response composer that uses an LLM to format extracted data into components."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str = "gpt-4o",
        temperature: float = 0.1,
    ):
        self.llm = ChatOpenAI(
            api_key=api_key,
            base_url=base_url,
            model=model,
            temperature=temperature,
        )
        self.model = model

    async def compose(
        self,
        query: str,
        intent: IntentResult,
        extractions: list[ExtractionResult],
    ) -> tuple[Layout, list[Component], dict[str, Any]]:
        """Compose extracted data into a structured response."""
        # Check if we have any usable extractions
        valid_extractions = [e for e in extractions if e.is_complete()]

        if not valid_extractions:
            return self._insufficient_data_response(query, extractions)

        prompt = self._build_prompt(query, intent, valid_extractions)

        messages = [
            SystemMessage(content="You are a response composer. Format the extracted data into a structured response. Output JSON only."),
            HumanMessage(content=prompt),
        ]

        try:
            response = await self.llm.ainvoke(messages)
            content = response.content

            usage = response.usage_metadata or {}
            token_usage = {
                "input_tokens": usage.get("input_tokens", 0),
                "output_tokens": usage.get("output_tokens", 0),
                "model": self.model,
            }

            layout, components = self._parse_response(content)

            # Add warnings from extractions if needed
            components = self._add_extraction_warnings(components, extractions)

            return layout, components, token_usage
        except Exception as e:
            logger.warning(f"Composer failed: {e}")
            return self._fallback_response(query, str(e))

    def _build_prompt(
        self,
        query: str,
        intent: IntentResult,
        extractions: list[ExtractionResult],
    ) -> str:
        """Build the composer prompt with extracted data."""
        # Format intent
        intent_str = f"Type: {intent.query_type.value}, Components: {intent.expected_components}"

        # Format extracted data
        extracted_data_parts = []
        for extraction in extractions:
            extracted_data_parts.append(
                f"## {extraction.component_type}\n"
                f"Completeness: {extraction.completeness}\n"
                f"Data: {json.dumps(extraction.extracted_data, indent=2)}\n"
                f"Warnings: {extraction.warnings}"
            )
        extracted_data_str = "\n\n".join(extracted_data_parts)

        return COMPOSER_PROMPT.format(
            query=query,
            intent=intent_str,
            response_depth=intent.response_depth.value,
            extracted_data=extracted_data_str,
        )

    def _parse_response(self, content: str) -> tuple[Layout, list[Component]]:
        """Parse LLM response into Layout and Components."""
        try:
            json_str = self._extract_json(content)
            data = json.loads(json_str)
            return self._build_layout_from_data(data)
        except (json.JSONDecodeError, IndexError, KeyError) as e:
            logger.warning(f"Failed to parse composer response: {e}")
            return self._fallback_layout(content)

    def _extract_json(self, content: str) -> str:
        """Extract JSON from response, handling markdown code blocks."""
        if "```json" in content:
            return content.split("```json")[1].split("```")[0]
        elif "```" in content:
            return content.split("```")[1].split("```")[0]
        return content

    def _build_layout_from_data(self, data: dict) -> tuple[Layout, list[Component]]:
        """Build Layout and Components from parsed JSON data."""
        components: list[Component] = []
        sections: list[Section] = []

        for section_data in data.get("sections", []):
            component_ids = []
            for comp_data in section_data.get("components", []):
                component = parse_component(comp_data)
                if component:
                    components.append(component)
                    component_ids.append(component.id)

            # Skip sections with no valid components
            if not component_ids:
                section_title = section_data.get("title", "untitled")
                logger.debug(f"Skipping empty section: {section_title}")
                continue

            sections.append(
                Section(
                    title=section_data.get("title"),
                    component_ids=component_ids,
                    layout=section_data.get("layout"),
                )
            )

        layout = Layout(
            title=data.get("title"),
            subtitle=data.get("subtitle"),
            sections=sections,
        )

        return layout, components

    def _add_extraction_warnings(
        self,
        components: list[Component],
        extractions: list[ExtractionResult],
    ) -> list[Component]:
        """Add notice components for extraction warnings if significant."""
        all_warnings = []
        low_completeness = []

        for extraction in extractions:
            if extraction.completeness < 0.5:
                low_completeness.append(extraction.component_type)
            all_warnings.extend(extraction.warnings)

        if low_completeness:
            warning_msg = f"Limited data available for: {', '.join(low_completeness)}. Some information may be incomplete."
            notice = Component.create(
                Notice(
                    message=warning_msg,
                    level=NoticeLevel.INFO,
                    title="Data Availability",
                )
            )
            # Add notice near the beginning
            components.insert(min(1, len(components)), notice)

        return components

    def _insufficient_data_response(
        self,
        query: str,
        extractions: list[ExtractionResult],
    ) -> tuple[Layout, list[Component], dict[str, Any]]:
        """Generate a response when insufficient data is available."""
        warnings = []
        for extraction in extractions:
            warnings.extend(extraction.warnings)

        warning_text = "; ".join(warnings) if warnings else "No relevant information found in the available documents."

        notice = Component.create(
            Notice(
                message=f"Unable to answer this query: {warning_text}",
                level=NoticeLevel.WARNING,
                title="Insufficient Information",
            )
        )

        text = Component.create(
            TextBlock(
                content=f"The query '{query}' could not be answered with the available information. Try refining your search or using different keywords.",
                format=TextFormat.MARKDOWN,
            )
        )

        section = Section(component_ids=[notice.id, text.id])
        layout = Layout(
            title="Unable to Answer Query",
            subtitle="Insufficient information available",
            sections=[section],
        )

        return layout, [notice, text], {"input_tokens": 0, "output_tokens": 0, "model": self.model}

    def _fallback_response(
        self,
        query: str,
        error: str,
    ) -> tuple[Layout, list[Component], dict[str, Any]]:
        """Generate a fallback response when composition fails."""
        text = Component.create(
            TextBlock(
                content=f"An error occurred while generating the response. Please try again.",
                format=TextFormat.MARKDOWN,
            )
        )

        section = Section(component_ids=[text.id])
        layout = Layout(
            title="Error",
            sections=[section],
        )

        return layout, [text], {"input_tokens": 0, "output_tokens": 0, "model": self.model}

    def _fallback_layout(self, content: str) -> tuple[Layout, list[Component]]:
        """Create a fallback layout with the raw content."""
        text = Component.create(
            TextBlock(
                content=content,
                format=TextFormat.MARKDOWN,
            )
        )
        section = Section(component_ids=[text.id])
        layout = Layout(sections=[section])
        return layout, [text]
