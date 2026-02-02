from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from uuid import uuid4


class TextFormat(str, Enum):
    PLAIN = "plain"
    MARKDOWN = "markdown"


class ChartType(str, Enum):
    BAR = "bar"
    LINE = "line"
    PIE = "pie"
    DOUGHNUT = "doughnut"
    HORIZONTAL_BAR = "horizontal_bar"
    STACKED_BAR = "stacked_bar"


class NoticeLevel(str, Enum):
    INFO = "info"
    WARNING = "warning"
    IMPORTANT = "important"


# --- Component Types ---


@dataclass
class SourceReference:
    document_id: str
    source_name: str
    source_url: str | None = None
    source_date: str | None = None
    section_ref: str | None = None


@dataclass
class TextBlock:
    content: str
    title: str | None = None
    format: TextFormat = TextFormat.MARKDOWN
    sources: list[SourceReference] = field(default_factory=list)


@dataclass
class ChartDataPoint:
    label: str
    value: float
    category: str | None = None


@dataclass
class ChartSeries:
    name: str
    data: list[ChartDataPoint]


@dataclass
class Chart:
    chart_type: ChartType
    series: list[ChartSeries]
    title: str | None = None
    x_axis_label: str | None = None
    y_axis_label: str | None = None
    caption: str | None = None
    sources: list[SourceReference] = field(default_factory=list)


@dataclass
class TimelineEvent:
    date: str
    label: str
    description: str | None = None
    reference_url: str | None = None
    significance: int = 3  # 1-5


@dataclass
class Timeline:
    events: list[TimelineEvent]
    title: str | None = None
    caption: str | None = None
    sources: list[SourceReference] = field(default_factory=list)


@dataclass
class ComparisonItem:
    name: str
    description: str | None = None


@dataclass
class ComparisonAttribute:
    name: str
    values: list[str]  # Parallel to items


@dataclass
class Comparison:
    items: list[ComparisonItem]
    attributes: list[ComparisonAttribute]
    title: str | None = None
    caption: str | None = None
    sources: list[SourceReference] = field(default_factory=list)


@dataclass
class TableColumn:
    header: str
    key: str
    sortable: bool = False
    align: str = "left"


@dataclass
class DataTable:
    columns: list[TableColumn]
    rows: list[dict[str, str]]
    title: str | None = None
    caption: str | None = None
    sources: list[SourceReference] = field(default_factory=list)


@dataclass
class Notice:
    message: str
    level: NoticeLevel = NoticeLevel.INFO
    title: str | None = None


@dataclass
class MemberProfile:
    member_id: str
    name: str
    party: str
    constituency: str | None = None
    roles: list[str] = field(default_factory=list)
    photo_url: str | None = None
    biography: str | None = None
    profile_url: str | None = None


@dataclass
class MemberProfiles:
    members: list[MemberProfile]
    title: str | None = None
    caption: str | None = None
    sources: list[SourceReference] = field(default_factory=list)


@dataclass
class PartyVote:
    party: str
    votes_for: int
    votes_against: int
    abstentions: int = 0
    not_voting: int = 0


@dataclass
class VotingBreakdown:
    total_for: int
    total_against: int
    party_breakdown: list[PartyVote]
    title: str | None = None
    date: str | None = None
    total_abstentions: int = 0
    result: str | None = None
    caption: str | None = None
    sources: list[SourceReference] = field(default_factory=list)


# --- Composite Types ---

ComponentContent = (
    TextBlock
    | Chart
    | Timeline
    | Comparison
    | DataTable
    | Notice
    | MemberProfiles
    | VotingBreakdown
)


@dataclass
class Component:
    id: str
    content: ComponentContent
    size: str | None = None  # 'full', 'half', 'third', 'two-thirds', 'auto'

    @classmethod
    def create(
        cls, content: ComponentContent, size: str | None = None
    ) -> "Component":
        return cls(id=str(uuid4()), content=content, size=size)


@dataclass
class Section:
    component_ids: list[str]
    title: str | None = None
    layout: str | None = None  # 'stack', 'grid', 'two-column', 'three-column'


@dataclass
class Layout:
    sections: list[Section]
    title: str | None = None
    subtitle: str | None = None


@dataclass
class QueryFilters:
    document_types: list[str] | None = None
    date_from: str | None = None
    date_to: str | None = None
    sources: list[str] | None = None
    member_ids: list[str] | None = None


@dataclass
class Query:
    text: str
    session_id: str | None = None
    filters: QueryFilters | None = None


@dataclass
class QueryMetadata:
    documents_retrieved: int
    chunks_used: int
    processing_time_ms: int
    model: str


@dataclass
class RAGResult:
    layout: Layout
    components: list[Component]
    metadata: QueryMetadata
    sources: list[SourceReference] = field(default_factory=list)
    cached: bool = False
    cost: Any = None  # CostBreakdown from usage domain


@dataclass
class RetrievalResult:
    """Result of context retrieval with coverage metrics."""

    chunks: list[Any]  # list[Chunk] from ingestion domain
    strategy_used: str  # RetrievalStrategy value
    coverage: dict[str, float] = field(default_factory=dict)  # Per-entity coverage scores
    is_sufficient: bool = True
    warnings: list[str] = field(default_factory=list)

    @property
    def context_texts(self) -> list[str]:
        """Extract text content from chunks."""
        return [chunk.text for chunk in self.chunks]

    @classmethod
    def insufficient(cls, reason: str) -> "RetrievalResult":
        """Create an insufficient retrieval result."""
        return cls(
            chunks=[],
            strategy_used="single_focus",
            is_sufficient=False,
            warnings=[reason],
        )
