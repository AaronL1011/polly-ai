from uuid import UUID

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchAny,
    PointStruct,
    Range,
    VectorParams,
)

from polly_pipeline_server.domain.ingestion.entities import Chunk


class QdrantVectorStore:
    def __init__(
        self,
        url: str = "http://localhost:6333",
        collection: str = "polly_chunks",
        vector_size: int = 768,
    ):
        self.client = QdrantClient(url=url)
        self.collection = collection
        self.vector_size = vector_size
        self._ensure_collection()

    def _ensure_collection(self) -> None:
        collections = self.client.get_collections().collections
        if not any(c.name == self.collection for c in collections):
            self.client.create_collection(
                collection_name=self.collection,
                vectors_config=VectorParams(
                    size=self.vector_size,
                    distance=Distance.COSINE,
                ),
            )

    async def upsert(self, chunks: list[Chunk]) -> None:
        if not chunks:
            return

        points = [
            PointStruct(
                id=str(chunk.id),
                vector=chunk.embedding or [],
                payload={
                    "document_id": str(chunk.document_id),
                    "text": chunk.text,
                    "position": chunk.position,
                    **chunk.metadata,
                },
            )
            for chunk in chunks
            if chunk.embedding
        ]

        if points:
            self.client.upsert(collection_name=self.collection, points=points)

    async def search(
        self, vector: list[float], k: int = 10, filters: dict | None = None
    ) -> list[Chunk]:
        query_filter = None # TODO: Enable filters when they dont restrict results too much
        # query_filter = self._build_filter(filters) if filters else None

        results = self.client.query_points(
            collection_name=self.collection,
            query=vector,
            limit=k,
            query_filter=query_filter,
        )

        chunks = []
        for result in results.points:
            payload = result.payload or {}
            chunk_id = result.id
            chunks.append(
                Chunk(
                    id=UUID(chunk_id) if isinstance(chunk_id, str) else UUID(int=chunk_id),
                    document_id=UUID(payload.get("document_id", "")),
                    text=payload.get("text", ""),
                    position=payload.get("position", 0),
                    metadata={
                        key: value
                        for key, value in payload.items()
                        if key not in ("document_id", "text", "position")
                    },
                )
            )
        return chunks

    def _build_filter(self, filters: dict) -> Filter | None:
        """Build Qdrant filter from filter dictionary."""
        conditions: list[FieldCondition] = []

        # Document type filter (match any of the specified types)
        if document_types := filters.get("document_type"):
            if isinstance(document_types, list) and document_types:
                conditions.append(
                    FieldCondition(
                        key="document_type",
                        match=MatchAny(any=document_types),
                    )
                )
            elif isinstance(document_types, str):
                conditions.append(
                    FieldCondition(
                        key="document_type",
                        match=MatchAny(any=[document_types]),
                    )
                )

        # Date range filters (assumes 'date' field in payload as YYYY-MM-DD string)
        date_range_params: dict[str, str | None] = {}
        if date_from := filters.get("date_from"):
            date_range_params["gte"] = date_from
        if date_to := filters.get("date_to"):
            date_range_params["lte"] = date_to

        if date_range_params:
            conditions.append(
                FieldCondition(
                    key="date",
                    range=Range(**date_range_params),
                )
            )

        if not conditions:
            return None

        return Filter(must=conditions)

    async def delete_by_document(self, document_id: UUID) -> None:
        self.client.delete(
            collection_name=self.collection,
            points_selector={
                "filter": {"must": [{"key": "document_id", "match": {"value": str(document_id)}}]}
            },
        )
