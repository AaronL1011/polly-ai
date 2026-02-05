"""Component constraints for validating data sufficiency before component creation.

These constraints ensure components only render when they have meaningful data,
preventing charts with single data points, comparisons with one item, etc.
"""

import logging
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ConstraintViolation(str, Enum):
    """Types of constraint violations."""

    INSUFFICIENT_DATA = "insufficient_data"
    INVALID_STRUCTURE = "invalid_structure"
    POOR_FIT = "poor_fit"  # Data exists but doesn't suit this component type


@dataclass
class ValidationResult:
    """Result of component validation."""

    is_valid: bool
    violation: ConstraintViolation | None = None
    reason: str | None = None
    suggestion: str | None = None  # Alternative component type or action

    @classmethod
    def valid(cls) -> "ValidationResult":
        return cls(is_valid=True)

    @classmethod
    def invalid(
        cls,
        violation: ConstraintViolation,
        reason: str,
        suggestion: str | None = None,
    ) -> "ValidationResult":
        return cls(
            is_valid=False,
            violation=violation,
            reason=reason,
            suggestion=suggestion,
        )


# --- Constraint Definitions ---

# Chart constraints
CHART_MIN_DATA_POINTS = 2  # Single point chart is meaningless
CHART_MAX_DATA_POINTS = 20  # Too many points becomes unreadable
PIE_MAX_SLICES = 7  # Pie charts lose clarity with too many slices
LINE_MIN_DATA_POINTS = 3  # Need at least 3 points to show a trend

# Comparison constraints
COMPARISON_MIN_ITEMS = 2  # Can't compare fewer than 2 things
COMPARISON_MAX_ITEMS = 5  # Too many items becomes unwieldy
COMPARISON_MIN_ATTRIBUTES = 1  # Need at least one attribute to compare

# Timeline constraints
TIMELINE_MIN_EVENTS = 2  # Single event isn't a timeline

# DataTable constraints
TABLE_MIN_ROWS = 2  # Single row is better as text or key-value
TABLE_MIN_COLUMNS = 2  # Single column is just a list

# VotingBreakdown constraints
VOTING_MIN_TOTAL_VOTES = 1  # Must have at least some vote data

# MemberProfiles constraints
MEMBERS_MIN_COUNT = 1  # At least one member


def validate_chart(data: dict) -> ValidationResult:
    """Validate chart component data."""
    series = data.get("series", [])
    chart_type = data.get("chart_type", "bar")

    if not series:
        return ValidationResult.invalid(
            ConstraintViolation.INSUFFICIENT_DATA,
            "Chart has no series data",
            suggestion="text_block",
        )

    # Count total data points across all series
    total_points = sum(len(s.get("data", [])) for s in series)

    if total_points < CHART_MIN_DATA_POINTS:
        return ValidationResult.invalid(
            ConstraintViolation.INSUFFICIENT_DATA,
            f"Chart has only {total_points} data point(s), minimum is {CHART_MIN_DATA_POINTS}",
            suggestion="text_block",
        )

    # Check for valid numeric values
    for s in series:
        for point in s.get("data", []):
            value = point.get("value")
            if value is None:
                return ValidationResult.invalid(
                    ConstraintViolation.INVALID_STRUCTURE,
                    "Chart data point missing value",
                )
            try:
                float(value)
            except (TypeError, ValueError):
                return ValidationResult.invalid(
                    ConstraintViolation.INVALID_STRUCTURE,
                    f"Chart data point has non-numeric value: {value}",
                )

    # Chart-type-specific constraints
    if chart_type in ("pie", "doughnut"):
        # Pie charts need positive values and limited slices
        first_series = series[0] if series else {}
        points = first_series.get("data", [])

        if len(points) > PIE_MAX_SLICES:
            return ValidationResult.invalid(
                ConstraintViolation.POOR_FIT,
                f"Pie chart has {len(points)} slices, maximum recommended is {PIE_MAX_SLICES}",
                suggestion="bar",  # Convert to bar chart
            )

        # Check for negative values in pie charts
        for point in points:
            if float(point.get("value", 0)) < 0:
                return ValidationResult.invalid(
                    ConstraintViolation.POOR_FIT,
                    "Pie chart cannot display negative values",
                    suggestion="bar",
                )

    elif chart_type == "line":
        # Line charts need enough points to show a trend
        for s in series:
            if len(s.get("data", [])) < LINE_MIN_DATA_POINTS:
                return ValidationResult.invalid(
                    ConstraintViolation.POOR_FIT,
                    f"Line chart series has only {len(s.get('data', []))} points, minimum is {LINE_MIN_DATA_POINTS}",
                    suggestion="bar",
                )

    # Warn about too many data points (but still allow)
    if total_points > CHART_MAX_DATA_POINTS:
        logger.warning(
            f"Chart has {total_points} data points, may be hard to read (max recommended: {CHART_MAX_DATA_POINTS})"
        )

    return ValidationResult.valid()


def validate_comparison(data: dict) -> ValidationResult:
    """Validate comparison component data."""
    items = data.get("items", [])
    attributes = data.get("attributes", [])

    # Filter to items with names
    valid_items = [i for i in items if i.get("name")]
    valid_attributes = [a for a in attributes if a.get("name") and a.get("values")]

    if len(valid_items) < COMPARISON_MIN_ITEMS:
        return ValidationResult.invalid(
            ConstraintViolation.INSUFFICIENT_DATA,
            f"Comparison has only {len(valid_items)} item(s), minimum is {COMPARISON_MIN_ITEMS}",
            suggestion="text_block",
        )

    if len(valid_attributes) < COMPARISON_MIN_ATTRIBUTES:
        return ValidationResult.invalid(
            ConstraintViolation.INSUFFICIENT_DATA,
            f"Comparison has no attributes to compare",
            suggestion="text_block",
        )

    if len(valid_items) > COMPARISON_MAX_ITEMS:
        logger.warning(
            f"Comparison has {len(valid_items)} items, may be hard to read (max recommended: {COMPARISON_MAX_ITEMS})"
        )

    # Check that attribute values align with item count
    for attr in valid_attributes:
        values = attr.get("values", [])
        if len(values) != len(valid_items):
            logger.warning(
                f"Comparison attribute '{attr.get('name')}' has {len(values)} values but {len(valid_items)} items"
            )

    return ValidationResult.valid()


def validate_timeline(data: dict) -> ValidationResult:
    """Validate timeline component data."""
    events = data.get("events", [])

    # Filter to events with date or label
    valid_events = [e for e in events if e.get("date") or e.get("label")]

    if len(valid_events) < TIMELINE_MIN_EVENTS:
        return ValidationResult.invalid(
            ConstraintViolation.INSUFFICIENT_DATA,
            f"Timeline has only {len(valid_events)} event(s), minimum is {TIMELINE_MIN_EVENTS}",
            suggestion="text_block",
        )

    return ValidationResult.valid()


def validate_data_table(data: dict) -> ValidationResult:
    """Validate data table component data."""
    columns = data.get("columns", [])
    rows = data.get("rows", [])

    # Filter to valid columns and rows
    valid_columns = [c for c in columns if c.get("header") or c.get("key")]
    valid_rows = [r for r in rows if isinstance(r, dict) and r]

    if len(valid_columns) < TABLE_MIN_COLUMNS:
        return ValidationResult.invalid(
            ConstraintViolation.INSUFFICIENT_DATA,
            f"Table has only {len(valid_columns)} column(s), minimum is {TABLE_MIN_COLUMNS}",
            suggestion="text_block",
        )

    if len(valid_rows) < TABLE_MIN_ROWS:
        return ValidationResult.invalid(
            ConstraintViolation.INSUFFICIENT_DATA,
            f"Table has only {len(valid_rows)} row(s), minimum is {TABLE_MIN_ROWS}",
            suggestion="text_block",
        )

    return ValidationResult.valid()


def validate_voting_breakdown(data: dict) -> ValidationResult:
    """Validate voting breakdown component data."""
    total_for = int(data.get("total_for", 0))
    total_against = int(data.get("total_against", 0))
    party_breakdown = data.get("party_breakdown", [])

    # Check if we have meaningful vote totals
    has_totals = total_for > 0 or total_against > 0

    # Check if we have meaningful party breakdown
    has_party_votes = any(
        int(p.get("votes_for", 0)) > 0 or int(p.get("votes_against", 0)) > 0
        for p in party_breakdown
        if p.get("party")
    )

    if not has_totals and not has_party_votes:
        return ValidationResult.invalid(
            ConstraintViolation.INSUFFICIENT_DATA,
            "Voting breakdown has no vote data",
            suggestion="text_block",
        )

    # Validate party breakdown if present
    valid_parties = [p for p in party_breakdown if p.get("party")]
    if party_breakdown and not valid_parties:
        logger.warning("Voting breakdown has party_breakdown but no valid party entries")

    return ValidationResult.valid()


def validate_member_profiles(data: dict) -> ValidationResult:
    """Validate member profiles component data."""
    members = data.get("members", [])

    # Filter to members with names
    valid_members = [m for m in members if m.get("name")]

    if len(valid_members) < MEMBERS_MIN_COUNT:
        return ValidationResult.invalid(
            ConstraintViolation.INSUFFICIENT_DATA,
            "Member profiles has no valid members",
            suggestion=None,
        )

    return ValidationResult.valid()


def validate_text_block(data: dict) -> ValidationResult:
    """Validate text block component data."""
    content = data.get("content", "").strip()

    if not content:
        return ValidationResult.invalid(
            ConstraintViolation.INSUFFICIENT_DATA,
            "Text block has no content",
        )

    return ValidationResult.valid()


def validate_notice(data: dict) -> ValidationResult:
    """Validate notice component data."""
    message = data.get("message", "").strip()

    if not message:
        return ValidationResult.invalid(
            ConstraintViolation.INSUFFICIENT_DATA,
            "Notice has no message",
        )

    return ValidationResult.valid()


# Validator registry
COMPONENT_VALIDATORS = {
    "chart": validate_chart,
    "comparison": validate_comparison,
    "timeline": validate_timeline,
    "data_table": validate_data_table,
    "voting_breakdown": validate_voting_breakdown,
    "member_profiles": validate_member_profiles,
    "text_block": validate_text_block,
    "notice": validate_notice,
}


def validate_component(component_type: str, data: dict) -> ValidationResult:
    """
    Validate component data against constraints.

    Args:
        component_type: The normalized component type (e.g., 'chart', 'text_block')
        data: The component data dictionary

    Returns:
        ValidationResult indicating if the component should be created
    """
    validator = COMPONENT_VALIDATORS.get(component_type)

    if validator is None:
        # Unknown component type - let parse_component handle it
        return ValidationResult.valid()

    try:
        return validator(data)
    except Exception as e:
        logger.warning(f"Error validating {component_type}: {e}")
        return ValidationResult.invalid(
            ConstraintViolation.INVALID_STRUCTURE,
            f"Validation error: {e}",
        )
