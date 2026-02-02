from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from uuid import UUID, uuid4


def utc_now() -> datetime:
    return datetime.now(UTC)


class DocumentType(str, Enum):
    BILL = "bill"
    HANSARD = "hansard"
    MEMBER = "member"
    VOTE = "vote"
    REPORT = "report"
    OTHER = "other"


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


@dataclass
class DocumentMetadata:
    document_type: DocumentType
    source: str
    source_url: str | None = None
    date: str | None = None
    title: str | None = None
    description: str | None = None
    tags: list[str] = field(default_factory=list)


@dataclass
class Document:
    id: UUID
    metadata: DocumentMetadata
    blob_ref: str | None = None  # S3 key or local path
    content: str | None = None  # Inline text content
    created_at: datetime = field(default_factory=utc_now)

    @classmethod
    def create(cls, metadata: DocumentMetadata, content: str | None = None) -> "Document":
        return cls(id=uuid4(), metadata=metadata, content=content)


@dataclass
class Chunk:
    id: UUID
    document_id: UUID
    text: str
    position: int  # Order within document
    embedding: list[float] | None = None
    metadata: dict[str, str] = field(default_factory=dict)

    @classmethod
    def create(cls, document_id: UUID, text: str, position: int) -> "Chunk":
        return cls(id=uuid4(), document_id=document_id, text=text, position=position)


@dataclass
class Job:
    id: UUID
    status: JobStatus = JobStatus.PENDING
    progress_percent: int = 0
    documents_processed: int = 0
    chunks_created: int = 0
    error_message: str | None = None
    created_at: datetime = field(default_factory=utc_now)
    completed_at: datetime | None = None

    @classmethod
    def create(cls) -> "Job":
        return cls(id=uuid4())

    def start(self) -> None:
        self.status = JobStatus.RUNNING

    def complete(self, documents: int, chunks: int) -> None:
        self.status = JobStatus.SUCCESS
        self.documents_processed = documents
        self.chunks_created = chunks
        self.progress_percent = 100
        self.completed_at = utc_now()

    def fail(self, error: str) -> None:
        self.status = JobStatus.FAILED
        self.error_message = error
        self.completed_at = utc_now()
