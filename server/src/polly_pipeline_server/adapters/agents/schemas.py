from pydantic import BaseModel, Field


class EntitiesSchema(BaseModel):
    """Extracted entities from a query."""

    parties: list[str] = Field(default_factory=list, description="Political party names mentioned or implied")
    members: list[str] = Field(default_factory=list, description="Politician names mentioned")
    bills: list[str] = Field(default_factory=list, description="Bill or legislation names")
    topics: list[str] = Field(default_factory=list, description="Policy topics or themes")
    date_from: str | None = Field(default=None, description="Start date in YYYY-MM-DD format")
    date_to: str | None = Field(default=None, description="End date in YYYY-MM-DD format")
    document_types: list[str] = Field(default_factory=list, description="Document types: bill, hansard, vote, member, report")


class PlannerOutputSchema(BaseModel):
    """Schema for query planner output."""

    query_type: str = Field(description="Query type: factual, comparative, timeline, voting, or analytical")
    response_depth: str = Field(default="standard", description="Response depth: brief, standard, or comprehensive")
    entities: EntitiesSchema = Field(default_factory=EntitiesSchema, description="Extracted entities")
    expected_components: list[str] = Field(description="Component types to include in response")
    retrieval_strategy: str = Field(description="Retrieval strategy: single_focus, multi_entity, chronological, or broad")
    rewritten_queries: list[str] = Field(description="Optimized queries for vector search")
    confidence: float = Field(default=0.8, ge=0.0, le=1.0, description="Confidence score 0-1")


class SourceQuoteSchema(BaseModel):
    """A quote from source context."""

    text: str = Field(description="The exact quote from the source")
    chunk_index: int | None = Field(default=None, description="Index of the source chunk")
    document_id: str | None = Field(default=None, description="ID of the source document")


class BaseExtractionSchema(BaseModel):
    """Base schema for all extraction outputs."""

    source_quotes: list[str] = Field(default_factory=list, description="Exact quotes from context supporting the extraction")
    completeness: float = Field(default=1.0, ge=0.0, le=1.0, description="Data completeness score 0-1")
    warnings: list[str] = Field(default_factory=list, description="Any data quality issues or missing fields")


class TextBlockExtractionSchema(BaseExtractionSchema):
    """Schema for text block extraction."""

    title: str | None = Field(default=None, description="Section title")
    key_points: list[dict] = Field(default_factory=list, description="Key facts with supporting quotes")
    summary_focus: str | None = Field(default=None, description="Main topic of the text")


class VotingExtractionSchema(BaseExtractionSchema):
    """Schema for voting breakdown extraction."""

    bill_name: str | None = Field(default=None, description="Exact bill name from text")
    vote_date: str | None = Field(default=None, description="Vote date in YYYY-MM-DD format")
    result: str | None = Field(default=None, description="Vote result: passed, rejected, or tied")
    votes_for: int | None = Field(default=None, description="Number of votes in favor")
    votes_against: int | None = Field(default=None, description="Number of votes against")
    total_abstentions: int | None = Field(default=None, description="Number of abstentions")
    party_breakdown: list[dict] = Field(default_factory=list, description="Per-party vote breakdown")


class TimelineEventSchema(BaseModel):
    """Schema for a timeline event."""

    date: str = Field(description="Event date in YYYY-MM-DD format")
    label: str = Field(description="Short event name")
    description: str | None = Field(default=None, description="Event description from text")
    source_quote: str | None = Field(default=None, description="Exact sentence from source")


class TimelineExtractionSchema(BaseExtractionSchema):
    """Schema for timeline extraction."""

    title: str | None = Field(default=None, description="Timeline title")
    events: list[TimelineEventSchema] = Field(default_factory=list, description="Chronological events")


class ComparisonAttributeSchema(BaseModel):
    """Schema for a comparison attribute."""

    name: str = Field(description="Attribute being compared")
    values: list[str] = Field(description="Values for each entity")
    source_quotes: list[str] = Field(default_factory=list, description="Sources for each value")


class ComparisonExtractionSchema(BaseExtractionSchema):
    """Schema for comparison extraction."""

    title: str | None = Field(default=None, description="Comparison title")
    items: list[dict] = Field(default_factory=list, description="Entities being compared")
    attributes: list[ComparisonAttributeSchema] = Field(default_factory=list, description="Comparison attributes")


class ChartDataPointSchema(BaseModel):
    """Schema for a chart data point."""

    label: str = Field(description="Category label")
    value: float = Field(description="Numerical value from text")


class ChartSeriesSchema(BaseModel):
    """Schema for a chart series."""

    name: str = Field(description="Series name")
    data: list[ChartDataPointSchema] = Field(description="Data points in the series")


class ChartExtractionSchema(BaseExtractionSchema):
    """Schema for chart extraction."""

    chart_type: str = Field(description="Chart type: bar, line, pie, horizontal_bar, stacked_bar")
    title: str | None = Field(default=None, description="Chart title")
    series: list[ChartSeriesSchema] = Field(default_factory=list, description="Chart data series")
    x_axis_label: str | None = Field(default=None, description="X-axis label")
    y_axis_label: str | None = Field(default=None, description="Y-axis label")


class DataTableExtractionSchema(BaseExtractionSchema):
    """Schema for data table extraction."""

    title: str | None = Field(default=None, description="Table title")
    columns: list[dict] = Field(default_factory=list, description="Column definitions")
    rows: list[dict] = Field(default_factory=list, description="Table rows")


class MemberSchema(BaseModel):
    """Schema for a member profile."""

    name: str = Field(description="Full name from text")
    party: str | None = Field(default=None, description="Party affiliation")
    constituency: str | None = Field(default=None, description="Electorate")
    roles: list[str] = Field(default_factory=list, description="Positions or roles")
    source_quote: str | None = Field(default=None, description="Source sentence")


class MemberProfilesExtractionSchema(BaseExtractionSchema):
    """Schema for member profiles extraction."""

    title: str | None = Field(default=None, description="Section title")
    members: list[MemberSchema] = Field(default_factory=list, description="Member profiles")


class NoticeSchema(BaseModel):
    """Schema for a notice."""

    level: str = Field(description="Notice level: info, warning, important")
    title: str | None = Field(default=None, description="Notice title")
    message: str = Field(description="Notice message from text")
    source_quote: str | None = Field(default=None, description="Source sentence")


class NoticeExtractionSchema(BaseExtractionSchema):
    """Schema for notice extraction."""

    notices: list[NoticeSchema] = Field(default_factory=list, description="Extracted notices")


class GenericExtractionSchema(BaseExtractionSchema):
    """Schema for generic extraction when no specific schema exists."""

    data: dict = Field(default_factory=dict, description="Extracted data")


# Mapping from component type to schema
EXTRACTION_SCHEMAS: dict[str, type[BaseExtractionSchema]] = {
    "text_block": TextBlockExtractionSchema,
    "voting_breakdown": VotingExtractionSchema,
    "timeline": TimelineExtractionSchema,
    "comparison": ComparisonExtractionSchema,
    "chart": ChartExtractionSchema,
    "data_table": DataTableExtractionSchema,
    "member_profiles": MemberProfilesExtractionSchema,
    "notice": NoticeExtractionSchema,
}


def get_extraction_schema(component_type: str) -> type[BaseExtractionSchema]:
    """Get the appropriate extraction schema for a component type."""
    return EXTRACTION_SCHEMAS.get(component_type, GenericExtractionSchema)
