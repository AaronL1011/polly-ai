import json
import logging

from democrata_server.domain.usage.entities import UsageEvent

logger = logging.getLogger("democrata.usage")


class StructuredUsageLogger:
    """Logs usage events as structured JSON for observability."""

    def __init__(self, log_level: int = logging.INFO):
        self.log_level = log_level
        if not logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter("%(message)s"))
            logger.addHandler(handler)
            logger.setLevel(log_level)

    async def log(self, event: UsageEvent) -> None:
        log_data = {
            "event_id": str(event.id),
            "event_type": event.event_type.value,
            "timestamp": event.timestamp.isoformat(),
            "billing_account_id": str(event.billing_account_id),
            "session_id": event.session_id,
            "user_id": str(event.user_id) if event.user_id else None,
            "cached": event.cached,
            "credits_charged": event.credits_charged,
            "cost": {
                "embedding_tokens": event.cost.embedding_tokens,
                "llm_input_tokens": event.cost.llm_input_tokens,
                "llm_output_tokens": event.cost.llm_output_tokens,
                "total_cents": event.cost.total_cents,
                "total_credits": event.cost.total_credits,
            },
        }
        if event.query_preview:
            log_data["query_preview"] = event.query_preview
        
        logger.log(self.log_level, json.dumps(log_data))
