"""Tests for the agent pipeline components."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from democrata_server.domain.agents.entities import (
    ExtractionResult,
    ExtractedEntities,
    IntentResult,
    QueryType,
    RetrievalStrategy,
    SourceQuote,
    UnsupportedClaim,
    VerificationResult,
)
from democrata_server.domain.rag.entities import RetrievalResult
from democrata_server.adapters.agents.config import AgentConfig
from democrata_server.adapters.agents.planner import LLMQueryPlanner
from democrata_server.adapters.agents.extractor import LLMDataExtractor
from democrata_server.adapters.agents.retriever import IntentDrivenRetriever


class TestIntentResult:
    def test_default_factual(self):
        intent = IntentResult.default_factual("test query")

        assert intent.query_type == QueryType.FACTUAL
        assert intent.retrieval_strategy == RetrievalStrategy.SINGLE_FOCUS
        assert intent.expected_components == ["text_block"]
        assert intent.rewritten_queries == ["test query"]
        assert intent.confidence == 0.5

    def test_entities_has_entities(self):
        entities_empty = ExtractedEntities()
        assert not entities_empty.has_entities()

        entities_with_parties = ExtractedEntities(parties=["Labor"])
        assert entities_with_parties.has_entities()

        entities_with_topics = ExtractedEntities(topics=["climate"])
        assert entities_with_topics.has_entities()


class TestExtractionResult:
    def test_empty_extraction(self):
        result = ExtractionResult.empty("chart", "No data available")

        assert result.component_type == "chart"
        assert result.extracted_data == {}
        assert result.completeness == 0.0
        assert "No data available" in result.warnings

    def test_is_complete(self):
        complete = ExtractionResult(
            component_type="text_block",
            extracted_data={"content": "test"},
            completeness=0.8,
        )
        assert complete.is_complete()

        incomplete = ExtractionResult(
            component_type="chart",
            extracted_data={"series": []},
            completeness=0.3,
        )
        assert not incomplete.is_complete()

        empty_data = ExtractionResult(
            component_type="chart",
            extracted_data={},
            completeness=0.8,
        )
        assert not empty_data.is_complete()


class TestVerificationResult:
    def test_valid_result(self):
        result = VerificationResult.valid()

        assert result.is_valid
        assert result.confidence_score == 1.0
        assert len(result.unsupported_claims) == 0

    def test_invalid_result(self):
        claims = [
            UnsupportedClaim(claim_text="Wrong fact", severity="error"),
        ]
        result = VerificationResult.invalid(claims)

        assert not result.is_valid
        assert result.confidence_score == 0.0
        assert len(result.unsupported_claims) == 1


class TestRetrievalResult:
    def test_insufficient_result(self):
        result = RetrievalResult.insufficient("No matching documents")

        assert not result.is_sufficient
        assert len(result.chunks) == 0
        assert "No matching documents" in result.warnings

    def test_context_texts(self):
        # Create mock chunks
        chunk1 = MagicMock()
        chunk1.text = "First chunk"
        chunk2 = MagicMock()
        chunk2.text = "Second chunk"

        result = RetrievalResult(
            chunks=[chunk1, chunk2],
            strategy_used="single_focus",
            is_sufficient=True,
        )

        texts = result.context_texts
        assert texts == ["First chunk", "Second chunk"]


class TestAgentConfig:
    def test_from_env_defaults(self, monkeypatch):
        # Clear any existing env vars
        monkeypatch.delenv("AGENT_PLANNER_MODEL", raising=False)
        monkeypatch.delenv("AGENT_EXTRACTOR_MODEL", raising=False)
        monkeypatch.delenv("AGENT_COMPOSER_MODEL", raising=False)
        monkeypatch.delenv("AGENT_VERIFIER_MODEL", raising=False)
        monkeypatch.delenv("AGENT_VERIFIER_ENABLED", raising=False)

        config = AgentConfig.from_env()

        assert config.planner_model == "gpt-4o-mini"
        assert config.extractor_model == "gpt-4o"
        assert config.composer_model == "gpt-4o"
        assert config.verifier_model == "gpt-4o-mini"
        assert config.verifier_enabled is True

    def test_from_env_custom(self, monkeypatch):
        monkeypatch.setenv("AGENT_PLANNER_MODEL", "custom-planner")
        monkeypatch.setenv("AGENT_VERIFIER_ENABLED", "false")

        config = AgentConfig.from_env()

        assert config.planner_model == "custom-planner"
        assert config.verifier_enabled is False


class TestLLMQueryPlanner:
    @pytest.fixture
    def planner(self):
        return LLMQueryPlanner(
            api_key="test-key",
            model="gpt-4o-mini",
        )

    def test_parse_intent_valid_json(self, planner):
        response = '''
        {
            "query_type": "comparative",
            "entities": {
                "parties": ["Labor", "Liberal"],
                "topics": ["climate"]
            },
            "expected_components": ["comparison", "chart"],
            "retrieval_strategy": "multi_entity",
            "rewritten_queries": ["Labor climate policy", "Liberal climate policy"],
            "confidence": 0.9
        }
        '''

        result = planner._parse_intent(response, "test query")

        assert result.query_type == QueryType.COMPARATIVE
        assert result.entities.parties == ["Labor", "Liberal"]
        assert result.expected_components == ["comparison", "chart"]
        assert result.retrieval_strategy == RetrievalStrategy.MULTI_ENTITY
        assert len(result.rewritten_queries) == 2
        assert result.confidence == 0.9

    def test_parse_intent_markdown_wrapped(self, planner):
        response = '''```json
        {
            "query_type": "factual",
            "entities": {},
            "expected_components": ["text_block"],
            "retrieval_strategy": "single_focus",
            "rewritten_queries": ["test"],
            "confidence": 0.8
        }
        ```'''

        result = planner._parse_intent(response, "test query")

        assert result.query_type == QueryType.FACTUAL

    def test_parse_intent_invalid_json_fallback(self, planner):
        response = "This is not valid JSON"

        result = planner._parse_intent(response, "original query")

        # Should fall back to default
        assert result.query_type == QueryType.FACTUAL
        assert result.rewritten_queries == ["original query"]


class TestLLMDataExtractor:
    @pytest.fixture
    def extractor(self):
        return LLMDataExtractor(
            api_key="test-key",
            model="gpt-4o",
        )

    def test_build_prompt_with_entities(self, extractor):
        intent = IntentResult(
            query_type=QueryType.COMPARATIVE,
            entities=ExtractedEntities(
                parties=["Labor", "Liberal"],
                topics=["climate"],
            ),
            expected_components=["comparison"],
            retrieval_strategy=RetrievalStrategy.MULTI_ENTITY,
        )

        prompt = extractor._build_prompt(
            "comparison",
            ["Context about climate policy"],
            intent,
        )

        assert "Labor" in prompt
        assert "Liberal" in prompt
        assert "climate" in prompt

    def test_parse_extraction_valid(self, extractor):
        response = '''
        {
            "title": "Vote Results",
            "votes_for": 85,
            "votes_against": 60,
            "source_quotes": ["The bill passed 85-60"],
            "completeness": 0.9,
            "warnings": []
        }
        '''

        result = extractor._parse_extraction(response, "voting_breakdown")

        assert result.component_type == "voting_breakdown"
        assert result.extracted_data["votes_for"] == 85
        assert result.completeness == 0.9
        assert len(result.source_quotes) == 1

    def test_parse_extraction_invalid_fallback(self, extractor):
        response = "Invalid JSON"

        result = extractor._parse_extraction(response, "chart")

        assert result.component_type == "chart"
        assert result.completeness == 0.0
        assert len(result.warnings) > 0


class TestIntentDrivenRetriever:
    @pytest.fixture
    def mock_embedder(self):
        embedder = AsyncMock()
        embedder.embed_single = AsyncMock(return_value=[0.1] * 768)
        return embedder

    @pytest.fixture
    def mock_vector_store(self):
        store = AsyncMock()
        # Create mock chunks
        chunk = MagicMock()
        chunk.id = uuid4()
        chunk.text = "Test chunk"
        chunk.document_id = uuid4()
        chunk.metadata = {}
        store.search = AsyncMock(return_value=[chunk] * 5)
        return store

    @pytest.fixture
    def retriever(self, mock_embedder, mock_vector_store):
        return IntentDrivenRetriever(
            embedder=mock_embedder,
            vector_store=mock_vector_store,
            default_top_k=10,
            min_chunks_for_sufficiency=3,
        )

    @pytest.mark.asyncio
    async def test_retrieve_single_focus(self, retriever, mock_embedder, mock_vector_store):
        intent = IntentResult(
            query_type=QueryType.FACTUAL,
            entities=ExtractedEntities(),
            expected_components=["text_block"],
            retrieval_strategy=RetrievalStrategy.SINGLE_FOCUS,
        )

        result = await retriever.retrieve("test query", intent)

        assert result.is_sufficient
        assert result.strategy_used == "single_focus"
        mock_embedder.embed_single.assert_called_once_with("test query")
        mock_vector_store.search.assert_called_once()

    @pytest.mark.asyncio
    async def test_retrieve_insufficient_chunks(self, retriever, mock_vector_store):
        # Return only 1 chunk (below threshold)
        chunk = MagicMock()
        chunk.id = uuid4()
        chunk.text = "Only chunk"
        chunk.document_id = uuid4()
        mock_vector_store.search = AsyncMock(return_value=[chunk])

        intent = IntentResult(
            query_type=QueryType.FACTUAL,
            entities=ExtractedEntities(),
            expected_components=["text_block"],
            retrieval_strategy=RetrievalStrategy.SINGLE_FOCUS,
        )

        result = await retriever.retrieve("test query", intent)

        assert not result.is_sufficient
        assert len(result.warnings) > 0

    @pytest.mark.asyncio
    async def test_retrieve_multi_entity(self, mock_embedder):
        # Create mock vector store with unique chunks for each search
        mock_vector_store = AsyncMock()
        call_count = [0]

        async def mock_search(*args, **kwargs):
            chunks = []
            for i in range(3):  # Return 3 chunks per search
                chunk = MagicMock()
                chunk.id = uuid4()  # Unique ID for each chunk
                chunk.text = f"Chunk {call_count[0]}-{i}"
                chunk.document_id = uuid4()
                chunk.metadata = {}
                chunks.append(chunk)
            call_count[0] += 1
            return chunks

        mock_vector_store.search = mock_search

        retriever = IntentDrivenRetriever(
            embedder=mock_embedder,
            vector_store=mock_vector_store,
            default_top_k=10,
            min_chunks_for_sufficiency=3,
        )

        intent = IntentResult(
            query_type=QueryType.COMPARATIVE,
            entities=ExtractedEntities(parties=["Labor", "Liberal"]),
            expected_components=["comparison"],
            retrieval_strategy=RetrievalStrategy.MULTI_ENTITY,
            rewritten_queries=["Labor policy", "Liberal policy"],
        )

        result = await retriever.retrieve("compare policies", intent)

        assert result.is_sufficient
        assert result.strategy_used == "multi_entity"
        # Should have called embed for each rewritten query
        assert mock_embedder.embed_single.call_count == 2
        # Should have 6 unique chunks (3 from each search)
        assert len(result.chunks) == 6

    @pytest.mark.asyncio
    async def test_build_filters(self, retriever):
        intent = IntentResult(
            query_type=QueryType.VOTING,
            entities=ExtractedEntities(
                document_types=["vote", "bill"],
                date_from="2024-01-01",
                date_to="2024-12-31",
            ),
            expected_components=["voting_breakdown"],
            retrieval_strategy=RetrievalStrategy.SINGLE_FOCUS,
        )

        filters = retriever._build_filters(intent)

        assert filters["document_type"] == ["vote", "bill"]
        assert filters["date_from"] == "2024-01-01"
        assert filters["date_to"] == "2024-12-31"
