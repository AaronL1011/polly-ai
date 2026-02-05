"""Protocol definitions for agent interfaces."""

from typing import Any, Protocol

from democrata_server.domain.rag.entities import Component, Layout

from .entities import (
    ExtractionResult,
    IntentResult,
    VerificationResult,
)


class QueryPlanner(Protocol):
    """Analyzes user queries to determine intent and retrieval strategy."""

    async def analyze(self, query: str) -> IntentResult:
        """
        Classify query intent and extract entities.

        Args:
            query: The user's natural language query.

        Returns:
            IntentResult with query type, entities, and retrieval strategy.
        """
        ...


class DataExtractor(Protocol):
    """Extracts grounded, structured data from context for a component type."""

    async def extract(
        self,
        component_type: str,
        context: list[str],
        intent: IntentResult,
    ) -> ExtractionResult:
        """
        Extract structured data from context for a specific component type.

        Args:
            component_type: The type of component to extract data for.
            context: List of text chunks from retrieval.
            intent: The classified intent from the planner.

        Returns:
            ExtractionResult with structured data and source attributions.
        """
        ...


class ResponseComposer(Protocol):
    """Composes extracted data into a structured response with layout."""

    async def compose(
        self,
        query: str,
        intent: IntentResult,
        extractions: list[ExtractionResult],
    ) -> tuple[Layout, list[Component], dict[str, Any]]:
        """
        Compose extracted data into a structured response.

        Args:
            query: The original user query.
            intent: The classified intent.
            extractions: List of extraction results for each component.

        Returns:
            Tuple of (Layout, list of Components, token usage dict).
        """
        ...


class ResponseVerifier(Protocol):
    """Verifies response claims against source context."""

    async def verify(
        self,
        layout: Layout,
        components: list[Component],
        context: list[str],
    ) -> VerificationResult:
        """
        Verify that response claims are supported by source context.

        Args:
            layout: The response layout.
            components: List of response components.
            context: Original context chunks for verification.

        Returns:
            VerificationResult indicating validity and any unsupported claims.
        """
        ...
