from dataclasses import dataclass
from uuid import UUID

from .entities import Chunk, Document, DocumentMetadata, Job
from .ports import BlobStore, Embedder, JobStore, TextExtractor, VectorStore


@dataclass
class IngestDocumentResult:
    job: Job
    document: Document
    chunks: list[Chunk]


class IngestDocument:
    def __init__(
        self,
        blob_store: BlobStore,
        embedder: Embedder,
        vector_store: VectorStore,
        job_store: JobStore,
        text_extractor: TextExtractor,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
    ):
        self.blob_store = blob_store
        self.embedder = embedder
        self.vector_store = vector_store
        self.job_store = job_store
        self.text_extractor = text_extractor
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    async def execute(
        self,
        content: bytes | str,
        filename: str,
        content_type: str,
        metadata: DocumentMetadata,
    ) -> IngestDocumentResult:
        job = Job.create()
        job.start()
        await self.job_store.save(job)

        try:
            # Store raw blob if bytes
            blob_ref = None
            text_content: str
            if isinstance(content, bytes):
                blob_ref = f"documents/{job.id}/{filename}"
                await self.blob_store.put(blob_ref, content, content_type)
                text_content = self.text_extractor.extract(content, content_type, filename)
            else:
                text_content = content

            # Create document
            document = Document.create(metadata=metadata, content=text_content)
            document.blob_ref = blob_ref

            # Chunk the content with document metadata for source tracking
            chunks = self._chunk_text(document.id, text_content, metadata)

            # Embed chunks
            if chunks:
                texts = [c.text for c in chunks]
                embeddings = await self.embedder.embed(texts)
                for chunk, embedding in zip(chunks, embeddings):
                    chunk.embedding = embedding

                # Store in vector store
                await self.vector_store.upsert(chunks)

            # Complete job
            job.complete(documents=1, chunks=len(chunks))
            await self.job_store.save(job)

            return IngestDocumentResult(job=job, document=document, chunks=chunks)

        except Exception as e:
            job.fail(str(e))
            await self.job_store.save(job)
            raise

    def _chunk_text(
        self, document_id: UUID, text: str, metadata: DocumentMetadata
    ) -> list[Chunk]:
        chunks: list[Chunk] = []
        start = 0
        position = 0

        # Build metadata to attach to each chunk for source tracking
        chunk_metadata = {
            "source_name": metadata.title or metadata.source,
            "source_url": metadata.source_url or "",
            "source_date": metadata.date or "",
        }

        while start < len(text):
            end = start + self.chunk_size
            chunk_text = text[start:end]

            if chunk_text.strip():
                chunk = Chunk.create(document_id, chunk_text, position)
                chunk.metadata = chunk_metadata.copy()
                chunks.append(chunk)
                position += 1

            start = end - self.chunk_overlap
            if start >= len(text) - self.chunk_overlap:
                break

        return chunks


class GetJobStatus:
    def __init__(self, job_store: JobStore):
        self.job_store = job_store

    async def execute(self, job_id: UUID) -> Job | None:
        return await self.job_store.get(job_id)
