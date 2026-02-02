from dataclasses import fields, is_dataclass
from enum import Enum

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from polly_pipeline_server.api.http.deps import get_execute_query_use_case, get_session_id
from polly_pipeline_server.domain.rag.entities import Query, QueryFilters
from polly_pipeline_server.domain.rag.use_cases import ExecuteQuery

router = APIRouter()


class QueryRequest(BaseModel):
    query: str
    filters: dict | None = None


class ComponentData(BaseModel):
    id: str
    type: str
    data: dict
    size: str | None = None


class SectionData(BaseModel):
    title: str | None = None
    component_ids: list[str]
    layout: str | None = None


class LayoutData(BaseModel):
    title: str | None = None
    subtitle: str | None = None
    sections: list[SectionData]


class CostBreakdownData(BaseModel):
    embedding_tokens: int
    llm_input_tokens: int
    llm_output_tokens: int
    total_cents: int
    total_credits: int


class QueryMetadataData(BaseModel):
    documents_retrieved: int
    chunks_used: int
    processing_time_ms: int
    model: str


class SourceReferenceData(BaseModel):
    document_id: str
    source_name: str
    source_url: str | None = None
    source_date: str | None = None


class QueryResponse(BaseModel):
    layout: LayoutData
    components: list[ComponentData]
    cost: CostBreakdownData
    cached: bool
    metadata: QueryMetadataData
    sources: list[SourceReferenceData]


@router.post("/query", response_model=QueryResponse)
async def query(
    request: QueryRequest,
    session_id: str = Depends(get_session_id),
    execute_query: ExecuteQuery = Depends(get_execute_query_use_case),
) -> QueryResponse:
    filters = None
    if request.filters:
        filters = QueryFilters(
            document_types=request.filters.get("document_types"),
            date_from=request.filters.get("date_from"),
            date_to=request.filters.get("date_to"),
            sources=request.filters.get("sources"),
            member_ids=request.filters.get("member_ids"),
        )

    query_obj = Query(
        text=request.query,
        session_id=session_id,
        filters=filters,
    )

    try:
        result = await execute_query.execute(query_obj)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Convert domain objects to response format
    components_data = []
    for comp in result.result.components:
        comp_type = type(comp.content).__name__.lower()
        comp_dict = {
            "id": comp.id,
            "type": comp_type,
            "data": _serialize_component(comp.content),
            "size": comp.size,
        }
        components_data.append(ComponentData(**comp_dict))

    sections_data = [
        SectionData(title=s.title, component_ids=s.component_ids, layout=s.layout)
        for s in result.result.layout.sections
    ]

    layout_data = LayoutData(
        title=result.result.layout.title,
        subtitle=result.result.layout.subtitle,
        sections=sections_data,
    )

    cost_data = CostBreakdownData(
        embedding_tokens=result.cost.embedding_tokens,
        llm_input_tokens=result.cost.llm_input_tokens,
        llm_output_tokens=result.cost.llm_output_tokens,
        total_cents=result.cost.total_cents,
        total_credits=result.cost.total_credits,
    )

    metadata_data = QueryMetadataData(
        documents_retrieved=result.result.metadata.documents_retrieved,
        chunks_used=result.result.metadata.chunks_used,
        processing_time_ms=result.result.metadata.processing_time_ms,
        model=result.result.metadata.model,
    )

    sources_data = [
        SourceReferenceData(
            document_id=s.document_id,
            source_name=s.source_name,
            source_url=s.source_url,
            source_date=s.source_date,
        )
        for s in result.result.sources
    ]

    return QueryResponse(
        layout=layout_data,
        components=components_data,
        cost=cost_data,
        cached=result.result.cached,
        metadata=metadata_data,
        sources=sources_data,
    )


def _serialize_component(content) -> dict:
    if is_dataclass(content):
        result = {}
        for f in fields(content):
            value = getattr(content, f.name)
            result[f.name] = _serialize_value(value)
        return result
    return {"value": content}


def _serialize_value(value):
    if value is None:
        return None
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return [_serialize_value(v) for v in value]
    if isinstance(value, dict):
        return {k: _serialize_value(v) for k, v in value.items()}
    if is_dataclass(value):
        result = {}
        for f in fields(value):
            result[f.name] = _serialize_value(getattr(value, f.name))
        return result
    return str(value)
