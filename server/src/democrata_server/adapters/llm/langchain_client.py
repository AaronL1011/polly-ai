import json
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from democrata_server.domain.rag.entities import (
    Component,
    Layout,
    Section,
    TextBlock,
    TextFormat,
)

from .components import SYSTEM_PROMPT, parse_component


class LangChainLLMClient:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str = "gpt-4o-mini",
        temperature: float = 0.3,
    ):
        self.llm = ChatOpenAI(
            api_key=api_key,
            base_url=base_url,
            model=model,
            temperature=temperature,
        )
        self.model = model

    async def generate_response(
        self, query: str, context: list[str], system_prompt: str | None = None
    ) -> tuple[Layout, list[Component], dict[str, Any]]:
        context_text = "\n\n---\n\n".join(context) if context else "No context available."

        user_message = f"""Context from political documents:

{context_text}

---

User question: {query}

Respond with a JSON object as specified."""

        messages = [
            SystemMessage(content=system_prompt or SYSTEM_PROMPT),
            HumanMessage(content=user_message),
        ]

        response = await self.llm.ainvoke(messages)
        content = response.content

        usage = response.usage_metadata or {}
        token_usage = {
            "input_tokens": usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
            "model": self.model,
        }

        layout, components = self._parse_response(content)
        return layout, components, token_usage

    def _parse_response(self, content: str) -> tuple[Layout, list[Component]]:
        try:
            # Extract JSON from response (may be wrapped in markdown code blocks)
            json_str = content
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                json_str = content.split("```")[1].split("```")[0]

            data = json.loads(json_str.strip())
            return self._build_layout_from_data(data)
        except (json.JSONDecodeError, IndexError, KeyError):
            # Fallback: wrap raw content in a text block
            return self._fallback_response(content)

    def _build_layout_from_data(self, data: dict) -> tuple[Layout, list[Component]]:
        components: list[Component] = []
        sections: list[Section] = []

        for section_data in data.get("sections", []):
            component_ids = []
            for comp_data in section_data.get("components", []):
                component = parse_component(comp_data)
                if component:
                    components.append(component)
                    component_ids.append(component.id)

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

    def _fallback_response(self, content: str) -> tuple[Layout, list[Component]]:
        text_block = Component.create(
            TextBlock(
                content=content,
                format=TextFormat.MARKDOWN,
            )
        )
        section = Section(component_ids=[text_block.id])
        layout = Layout(sections=[section])
        return layout, [text_block]
