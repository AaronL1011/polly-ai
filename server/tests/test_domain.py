import pytest
from uuid import uuid4

from democrata_server.domain.ingestion.entities import (
    Chunk,
    Document,
    DocumentMetadata,
    DocumentType,
    Job,
    JobStatus,
)
from democrata_server.domain.usage.entities import CostBreakdown, UsageEvent


class TestDocumentEntities:
    def test_create_document(self):
        metadata = DocumentMetadata(
            document_type=DocumentType.BILL,
            source="test",
            title="Test Bill",
        )
        doc = Document.create(metadata=metadata, content="Test content")

        assert doc.id is not None
        assert doc.metadata.document_type == DocumentType.BILL
        assert doc.content == "Test content"

    def test_create_chunk(self):
        doc_id = uuid4()
        chunk = Chunk.create(document_id=doc_id, text="Test text", position=0)

        assert chunk.id is not None
        assert chunk.document_id == doc_id
        assert chunk.text == "Test text"
        assert chunk.position == 0


class TestJobLifecycle:
    def test_job_creation(self):
        job = Job.create()
        assert job.status == JobStatus.PENDING
        assert job.progress_percent == 0

    def test_job_start(self):
        job = Job.create()
        job.start()
        assert job.status == JobStatus.RUNNING

    def test_job_complete(self):
        job = Job.create()
        job.start()
        job.complete(documents=5, chunks=50)

        assert job.status == JobStatus.SUCCESS
        assert job.documents_processed == 5
        assert job.chunks_created == 50
        assert job.progress_percent == 100
        assert job.completed_at is not None

    def test_job_fail(self):
        job = Job.create()
        job.start()
        job.fail("Something went wrong")

        assert job.status == JobStatus.FAILED
        assert job.error_message == "Something went wrong"
        assert job.completed_at is not None


class TestCostBreakdown:
    def test_zero_cost(self):
        cost = CostBreakdown.zero()
        assert cost.total_cents == 0
        assert cost.total_credits == 0

    def test_calculate_cost(self):
        cost = CostBreakdown.calculate(
            embedding_tokens=100,
            llm_input_tokens=1000,
            llm_output_tokens=500,
            vector_queries=1,
            margin=0.4,
        )

        assert cost.embedding_tokens == 100
        assert cost.llm_input_tokens == 1000
        assert cost.llm_output_tokens == 500
        assert cost.total_cents > 0
        assert cost.margin_cents > 0

    def test_margin_calculation(self):
        cost_no_margin = CostBreakdown.calculate(
            llm_input_tokens=1000,
            llm_output_tokens=500,
            margin=0,
        )
        cost_with_margin = CostBreakdown.calculate(
            llm_input_tokens=1000,
            llm_output_tokens=500,
            margin=0.4,
        )

        assert cost_with_margin.total_cents > cost_no_margin.total_cents
