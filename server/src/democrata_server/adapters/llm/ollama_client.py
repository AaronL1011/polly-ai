import json
from typing import Any

import httpx

from democrata_server.domain.rag.entities import (
    Component,
    Layout,
    Section,
    TextBlock,
    TextFormat,
)

from .components import RESPONSE_SCHEMA, SYSTEM_PROMPT, parse_component


class OllamaLLMClient:
    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "llama3.2",
        temperature: float = 0.3,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.temperature = temperature
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=120.0)
        return self._client

    async def generate_response(
        self, query: str, context: list[str], system_prompt: str | None = None
    ) -> tuple[Layout, list[Component], dict[str, Any]]:
        context_text = "\n\n---\n\n".join(context) if context else "No context available."

        user_message = f"""Context from political documents:

{context_text}

---

User question: {query}

Respond with a JSON object as specified."""

        client = await self._get_client()

        response = await client.post(
            f"{self.base_url}/api/chat",
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt or SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                "stream": False,
                "options": {
                    "temperature": self.temperature,
                },
                "format": RESPONSE_SCHEMA,
            },
        )
        response.raise_for_status()
        data = response.json()

        content = data.get("message", {}).get("content", "")
        # Ollama provides token counts differently
        token_usage = {
            "input_tokens": data.get("prompt_eval_count", 0),
            "output_tokens": data.get("eval_count", 0),
            "model": self.model,
        }

        layout, components = self._parse_response(content)
        return layout, components, token_usage

    def _parse_response(self, content: str) -> tuple[Layout, list[Component]]:
        try:
            json_str = content
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                json_str = content.split("```")[1].split("```")[0]

            data = json.loads(json_str.strip())
            return self._build_layout_from_data(data)
        except (json.JSONDecodeError, IndexError, KeyError):
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

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
