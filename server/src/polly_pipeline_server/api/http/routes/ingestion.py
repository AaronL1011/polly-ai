from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from polly_pipeline_server.adapters.usage.memory_store import InMemoryJobStore
from polly_pipeline_server.api.http.deps import get_ingest_document_use_case, get_job_store
from polly_pipeline_server.domain.ingestion.entities import DocumentMetadata, DocumentType
from polly_pipeline_server.domain.ingestion.use_cases import IngestDocument

router = APIRouter()


class UploadMetadata(BaseModel):
    document_type: str = "other"
    source: str = "upload"
    date: str | None = None
    title: str | None = None
    description: str | None = None
    tags: list[str] = []


class JobResponse(BaseModel):
    job_id: str
    status: str
    progress_percent: int = 0


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    progress_percent: int
    documents_processed: int
    chunks_created: int
    error_message: str | None = None


@router.post("/upload", response_model=JobResponse)
async def upload(
    file: Annotated[UploadFile, File()],
    document_type: Annotated[str, Form()] = "other",
    source: Annotated[str, Form()] = "upload",
    source_url: Annotated[str | None, Form()] = None,
    title: Annotated[str | None, Form()] = None,
    ingest_use_case: IngestDocument = Depends(get_ingest_document_use_case),
) -> JobResponse:
    content = await file.read()

    try:
        doc_type = DocumentType(document_type)
    except ValueError:
        doc_type = DocumentType.OTHER

    metadata = DocumentMetadata(
        document_type=doc_type,
        source=source,
        source_url=source_url,
        title=title or file.filename,
    )

    result = await ingest_use_case.execute(
        content=content,
        filename=file.filename or "unknown",
        content_type=file.content_type or "application/octet-stream",
        metadata=metadata,
    )

    return JobResponse(
        job_id=str(result.job.id),
        status=result.job.status.value,
        progress_percent=result.job.progress_percent,
    )


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    job_id: str,
    job_store: InMemoryJobStore = Depends(get_job_store),
) -> JobStatusResponse:
    try:
        uuid = UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job ID format")

    job = await job_store.get(uuid)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return JobStatusResponse(
        job_id=str(job.id),
        status=job.status.value,
        progress_percent=job.progress_percent,
        documents_processed=job.documents_processed,
        chunks_created=job.chunks_created,
        error_message=job.error_message,
    )
