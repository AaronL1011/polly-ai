import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class LLMProvider(Enum):
    OPENAI = "openai"
    OLLAMA = "ollama"


class EmbeddingProvider(Enum):
    OPENAI = "openai"
    OLLAMA = "ollama"


@dataclass
class LLMConfig:
    provider: LLMProvider
    model: str
    api_key: str | None = None
    base_url: str | None = None
    temperature: float = 0.1
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_env(cls) -> "LLMConfig":
        provider_str = os.getenv("LLM_PROVIDER", "openai").lower()
        provider = LLMProvider(provider_str)

        if provider == LLMProvider.OPENAI:
            return cls(
                provider=provider,
                model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
                api_key=os.getenv("OPENAI_API_KEY"),
                base_url=os.getenv("OPENAI_BASE_URL"),
                temperature=float(os.getenv("LLM_TEMPERATURE", "0.1")),
            )
        elif provider == LLMProvider.OLLAMA:
            return cls(
                provider=provider,
                model=os.getenv("LLM_MODEL", "llama3.2"),
                base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
                temperature=float(os.getenv("LLM_TEMPERATURE", "0.1")),
            )
        else:
            raise ValueError(f"Unsupported LLM provider: {provider_str}")


@dataclass
class EmbeddingConfig:
    provider: EmbeddingProvider
    model: str
    api_key: str | None = None
    base_url: str | None = None
    dimensions: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_env(cls) -> "EmbeddingConfig":
        provider_str = os.getenv("EMBEDDING_PROVIDER", "openai").lower()
        provider = EmbeddingProvider(provider_str)

        if provider == EmbeddingProvider.OPENAI:
            return cls(
                provider=provider,
                model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
                api_key=os.getenv("OPENAI_API_KEY"),
                base_url=os.getenv("OPENAI_BASE_URL"),
                dimensions=int(os.getenv("EMBEDDING_DIMENSIONS", "1536")),
            )
        elif provider == EmbeddingProvider.OLLAMA:
            return cls(
                provider=provider,
                model=os.getenv("EMBEDDING_MODEL", "nomic-embed-text"),
                base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
                dimensions=int(os.getenv("EMBEDDING_DIMENSIONS", "768")),
            )
        else:
            raise ValueError(f"Unsupported embedding provider: {provider_str}")
