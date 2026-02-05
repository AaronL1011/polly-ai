"""LLM-based response verifier for checking claims against source context."""

import json
import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from democrata_server.domain.agents.entities import (
    UnsupportedClaim,
    VerificationResult,
)
from democrata_server.domain.rag.entities import Component, Layout

from .prompts.verifier import VERIFIER_PROMPT

logger = logging.getLogger(__name__)


class LLMResponseVerifier:
    """Response verifier that uses an LLM to check claims against source context."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str = "gpt-4o-mini",
        temperature: float = 0.1,
    ):
        self.llm = ChatOpenAI(
            api_key=api_key,
            base_url=base_url,
            model=model,
            temperature=temperature,
        )
        self.model = model

    async def verify(
        self,
        layout: Layout,
        components: list[Component],
        context: list[str],
    ) -> VerificationResult:
        """Verify that response claims are supported by source context."""
        if not context:
            return VerificationResult.valid()  # Can't verify without context

        # Serialize response for verification
        response_text = self._serialize_response(layout, components)
        context_text = "\n\n---\n\n".join(context)

        prompt = VERIFIER_PROMPT.format(
            context=context_text,
            response=response_text,
        )

        messages = [
            SystemMessage(content="You are a fact-checker. Verify claims against the source context. Output JSON only."),
            HumanMessage(content=prompt),
        ]

        try:
            response = await self.llm.ainvoke(messages)
            content = response.content
            return self._parse_verification(content)
        except Exception as e:
            logger.warning(f"Verification failed: {e}")
            return VerificationResult(
                is_valid=True,  # Default to valid if verification fails
                warnings=[f"Verification skipped: {e}"],
            )

    def _serialize_response(self, layout: Layout, components: list[Component]) -> str:
        """Serialize layout and components to text for verification."""
        parts = []

        if layout.title:
            parts.append(f"Title: {layout.title}")
        if layout.subtitle:
            parts.append(f"Subtitle: {layout.subtitle}")

        for component in components:
            content = component.content
            content_type = type(content).__name__

            # Serialize component content based on type
            if hasattr(content, "content"):  # TextBlock
                parts.append(f"[{content_type}] {content.content}")
            elif hasattr(content, "message"):  # Notice
                parts.append(f"[{content_type}] {content.message}")
            elif hasattr(content, "total_for"):  # VotingBreakdown
                parts.append(
                    f"[{content_type}] Votes: {content.total_for} for, "
                    f"{content.total_against} against"
                )
            elif hasattr(content, "events"):  # Timeline
                events_text = "; ".join(
                    f"{e.date}: {e.label}" for e in content.events
                )
                parts.append(f"[{content_type}] Events: {events_text}")
            elif hasattr(content, "series"):  # Chart
                series_text = "; ".join(
                    f"{s.name}: {[d.value for d in s.data]}" for s in content.series
                )
                parts.append(f"[{content_type}] Data: {series_text}")
            elif hasattr(content, "attributes"):  # Comparison
                attrs_text = "; ".join(
                    f"{a.name}: {a.values}" for a in content.attributes
                )
                parts.append(f"[{content_type}] {attrs_text}")
            elif hasattr(content, "rows"):  # DataTable
                parts.append(f"[{content_type}] {len(content.rows)} rows")
            elif hasattr(content, "members"):  # MemberProfiles
                members_text = ", ".join(m.name for m in content.members)
                parts.append(f"[{content_type}] Members: {members_text}")
            else:
                parts.append(f"[{content_type}] (content)")

        return "\n".join(parts)

    def _parse_verification(self, content: str) -> VerificationResult:
        """Parse LLM response into VerificationResult."""
        try:
            json_str = self._extract_json(content)
            data = json.loads(json_str)
            return self._build_verification_result(data)
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"Failed to parse verification response: {e}")
            return VerificationResult(
                is_valid=True,
                warnings=[f"Verification parse error: {e}"],
            )

    def _extract_json(self, content: str) -> str:
        """Extract JSON from response, handling markdown code blocks."""
        if "```json" in content:
            return content.split("```json")[1].split("```")[0]
        elif "```" in content:
            return content.split("```")[1].split("```")[0]
        return content

    def _build_verification_result(self, data: dict[str, Any]) -> VerificationResult:
        """Build VerificationResult from parsed JSON data."""
        is_valid = data.get("is_valid", True)

        unsupported_claims = []
        for claim_data in data.get("unsupported_claims", []):
            unsupported_claims.append(
                UnsupportedClaim(
                    claim_text=claim_data.get("claim_text", ""),
                    component_id=claim_data.get("component_id"),
                    severity=claim_data.get("severity", "warning"),
                )
            )

        confidence_score = float(data.get("confidence_score", 1.0))
        confidence_score = max(0.0, min(1.0, confidence_score))

        warnings = data.get("warnings", [])

        return VerificationResult(
            is_valid=is_valid,
            unsupported_claims=unsupported_claims,
            confidence_score=confidence_score,
            warnings=warnings if isinstance(warnings, list) else [str(warnings)],
        )
