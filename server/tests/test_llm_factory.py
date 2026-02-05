import os

import pytest

from democrata_server.adapters.llm.config import (
    EmbeddingConfig,
    EmbeddingProvider,
    LLMConfig,
    LLMProvider,
)
from democrata_server.adapters.llm.embedder import OpenAIEmbedder
from democrata_server.adapters.llm.factory import create_embedder, create_llm_client
from democrata_server.adapters.llm.langchain_client import LangChainLLMClient
from democrata_server.adapters.llm.ollama_client import OllamaLLMClient
from democrata_server.adapters.llm.ollama_embedder import OllamaEmbedder


class TestLLMConfig:
    def test_openai_config(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "openai")
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        monkeypatch.setenv("LLM_MODEL", "gpt-4")

        config = LLMConfig.from_env()

        assert config.provider == LLMProvider.OPENAI
        assert config.model == "gpt-4"
        assert config.api_key == "test-key"

    def test_ollama_config(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "ollama")
        monkeypatch.setenv("OLLAMA_BASE_URL", "http://my-ollama:11434")
        monkeypatch.setenv("LLM_MODEL", "mistral")

        config = LLMConfig.from_env()

        assert config.provider == LLMProvider.OLLAMA
        assert config.model == "mistral"
        assert config.base_url == "http://my-ollama:11434"

    def test_default_provider_is_openai(self, monkeypatch):
        monkeypatch.delenv("LLM_PROVIDER", raising=False)
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        config = LLMConfig.from_env()

        assert config.provider == LLMProvider.OPENAI


class TestEmbeddingConfig:
    def test_openai_config(self, monkeypatch):
        monkeypatch.setenv("EMBEDDING_PROVIDER", "openai")
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        monkeypatch.setenv("EMBEDDING_MODEL", "text-embedding-3-large")

        config = EmbeddingConfig.from_env()

        assert config.provider == EmbeddingProvider.OPENAI
        assert config.model == "text-embedding-3-large"

    def test_ollama_config(self, monkeypatch):
        monkeypatch.setenv("EMBEDDING_PROVIDER", "ollama")
        monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")

        config = EmbeddingConfig.from_env()

        assert config.provider == EmbeddingProvider.OLLAMA
        assert config.model == "nomic-embed-text"


class TestFactory:
    def test_create_openai_embedder(self):
        config = EmbeddingConfig(
            provider=EmbeddingProvider.OPENAI,
            model="text-embedding-3-small",
            api_key="test-key",
        )

        embedder = create_embedder(config)

        assert isinstance(embedder, OpenAIEmbedder)

    def test_create_ollama_embedder(self):
        config = EmbeddingConfig(
            provider=EmbeddingProvider.OLLAMA,
            model="nomic-embed-text",
            base_url="http://localhost:11434",
        )

        embedder = create_embedder(config)

        assert isinstance(embedder, OllamaEmbedder)

    def test_create_openai_llm_client(self):
        config = LLMConfig(
            provider=LLMProvider.OPENAI,
            model="gpt-4o-mini",
            api_key="test-key",
        )

        client = create_llm_client(config)

        assert isinstance(client, LangChainLLMClient)

    def test_create_ollama_llm_client(self):
        config = LLMConfig(
            provider=LLMProvider.OLLAMA,
            model="llama3.2",
            base_url="http://localhost:11434",
        )

        client = create_llm_client(config)

        assert isinstance(client, OllamaLLMClient)


class TestOllamaClients:
    def test_ollama_embedder_initialization(self):
        embedder = OllamaEmbedder(
            base_url="http://localhost:11434",
            model="nomic-embed-text",
        )

        assert embedder.base_url == "http://localhost:11434"
        assert embedder.model == "nomic-embed-text"

    def test_ollama_llm_initialization(self):
        client = OllamaLLMClient(
            base_url="http://localhost:11434",
            model="llama3.2",
            temperature=0.5,
        )

        assert client.base_url == "http://localhost:11434"
        assert client.model == "llama3.2"
        assert client.temperature == 0.5
