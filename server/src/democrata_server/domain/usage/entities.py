from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from uuid import UUID, uuid4


def utc_now() -> datetime:
    return datetime.now(UTC)


# Cost rates (per 1K tokens, in cents)
EMBEDDING_RATE_CENTS = 0.01  # ~$0.0001 per 1K tokens
LLM_INPUT_RATE_CENTS = 1.0  # ~$0.01 per 1K tokens
LLM_OUTPUT_RATE_CENTS = 3.0  # ~$0.03 per 1K tokens
VECTOR_QUERY_RATE_CENTS = 0.01  # ~$0.0001 per query


class UsageEventType(str, Enum):
    QUERY = "query"
    INGESTION = "ingestion"


@dataclass
class CostBreakdown:
    embedding_tokens: int = 0
    embedding_cost_cents: int = 0
    llm_input_tokens: int = 0
    llm_output_tokens: int = 0
    llm_cost_cents: int = 0
    vector_queries: int = 0
    vector_cost_cents: int = 0
    margin_cents: int = 0
    total_cents: int = 0
    total_credits: int = 0  # 1 credit = 1 cent

    @classmethod
    def zero(cls) -> "CostBreakdown":
        return cls()

    @classmethod
    def calculate(
        cls,
        embedding_tokens: int = 0,
        llm_input_tokens: int = 0,
        llm_output_tokens: int = 0,
        vector_queries: int = 0,
        margin: float = 0.4,
    ) -> "CostBreakdown":
        # Use float arithmetic then round at the end to avoid losing small values
        embedding_cost_f = (embedding_tokens / 1000) * EMBEDDING_RATE_CENTS
        llm_input_cost_f = (llm_input_tokens / 1000) * LLM_INPUT_RATE_CENTS
        llm_output_cost_f = (llm_output_tokens / 1000) * LLM_OUTPUT_RATE_CENTS
        llm_cost_f = llm_input_cost_f + llm_output_cost_f
        vector_cost_f = vector_queries * VECTOR_QUERY_RATE_CENTS

        subtotal_f = embedding_cost_f + llm_cost_f + vector_cost_f
        margin_f = subtotal_f * margin
        total_f = subtotal_f + margin_f

        # Round to nearest cent, minimum 1 cent if any cost was incurred
        embedding_cost = max(1, round(embedding_cost_f)) if embedding_tokens > 0 else 0
        llm_cost = max(1, round(llm_cost_f)) if (llm_input_tokens + llm_output_tokens) > 0 else 0
        vector_cost = max(1, round(vector_cost_f)) if vector_queries > 0 else 0
        margin_cents = max(1, round(margin_f)) if margin > 0 and subtotal_f > 0 else 0
        total = round(total_f) if total_f > 0 else 0

        return cls(
            embedding_tokens=embedding_tokens,
            embedding_cost_cents=embedding_cost,
            llm_input_tokens=llm_input_tokens,
            llm_output_tokens=llm_output_tokens,
            llm_cost_cents=llm_cost,
            vector_queries=vector_queries,
            vector_cost_cents=vector_cost,
            margin_cents=margin_cents,
            total_cents=total,
            total_credits=total,
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "embedding_tokens": self.embedding_tokens,
            "embedding_cost_cents": self.embedding_cost_cents,
            "llm_input_tokens": self.llm_input_tokens,
            "llm_output_tokens": self.llm_output_tokens,
            "llm_cost_cents": self.llm_cost_cents,
            "vector_queries": self.vector_queries,
            "vector_cost_cents": self.vector_cost_cents,
            "margin_cents": self.margin_cents,
            "total_cents": self.total_cents,
            "total_credits": self.total_credits,
        }


@dataclass
class UsageEvent:
    """
    Records a usage event for billing and analytics.
    
    Links to a billing account (user or org) and optionally tracks
    which specific user performed the action (for org member attribution).
    """

    id: UUID
    billing_account_id: UUID  # The account being charged
    event_type: UsageEventType
    session_id: str | None = None  # For anonymous tracking
    user_id: UUID | None = None  # Who performed the action (for org attribution)
    timestamp: datetime = field(default_factory=utc_now)
    query_hash: str | None = None
    query_preview: str | None = None  # Truncated for privacy
    cached: bool = False
    cost: CostBreakdown = field(default_factory=CostBreakdown.zero)
    credits_charged: int = 0

    @classmethod
    def create_query_event(
        cls,
        billing_account_id: UUID,
        query: str,
        cost: CostBreakdown,
        cached: bool = False,
        user_id: UUID | None = None,
        session_id: str | None = None,
    ) -> "UsageEvent":
        return cls(
            id=uuid4(),
            billing_account_id=billing_account_id,
            event_type=UsageEventType.QUERY,
            session_id=session_id,
            user_id=user_id,
            query_hash=str(hash(query)),
            query_preview=query[:50] + "..." if len(query) > 50 else query,
            cached=cached,
            cost=cost,
            credits_charged=0 if cached else cost.total_credits,
        )

    @classmethod
    def create_ingestion_event(
        cls,
        billing_account_id: UUID,
        cost: CostBreakdown,
        user_id: UUID | None = None,
        session_id: str | None = None,
    ) -> "UsageEvent":
        return cls(
            id=uuid4(),
            billing_account_id=billing_account_id,
            event_type=UsageEventType.INGESTION,
            session_id=session_id,
            user_id=user_id,
            cost=cost,
            credits_charged=cost.total_credits,
        )


@dataclass
class AnonymousSession:
    """
    Tracks anonymous user sessions for rate limiting and free tier management.
    
    Anonymous users are identified by a hash of their IP + User-Agent,
    and get limited free queries per day before needing to sign up.
    """

    session_id: str
    free_tier_remaining: int = 10  # Daily limit for anonymous users
    free_tier_reset_at: datetime | None = None
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    @classmethod
    def create(cls, session_id: str, daily_limit: int = 10) -> "AnonymousSession":
        now = utc_now()
        # Reset at midnight UTC
        tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0)
        from datetime import timedelta
        tomorrow += timedelta(days=1)
        
        return cls(
            session_id=session_id,
            free_tier_remaining=daily_limit,
            free_tier_reset_at=tomorrow,
            created_at=now,
            updated_at=now,
        )

    def can_query(self) -> bool:
        return self.free_tier_remaining > 0

    def consume_query(self) -> bool:
        """
        Consume one query from the free tier.
        Returns True if successful, False if no queries remaining.
        """
        if self.free_tier_remaining <= 0:
            return False
        self.free_tier_remaining -= 1
        self.updated_at = utc_now()
        return True

    def check_and_reset(self) -> bool:
        """
        Check if daily limit should be reset.
        Returns True if reset was performed.
        """
        now = utc_now()
        if self.free_tier_reset_at and now >= self.free_tier_reset_at:
            self.free_tier_remaining = 10
            # Set next reset to tomorrow midnight UTC
            tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0)
            from datetime import timedelta
            tomorrow += timedelta(days=1)
            self.free_tier_reset_at = tomorrow
            self.updated_at = now
            return True
        return False
