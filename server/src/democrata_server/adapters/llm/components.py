"""Shared component parsing and system prompt for LLM clients."""

import logging

from democrata_server.domain.rag.entities import (
    Chart,
    ChartDataPoint,
    ChartSeries,
    ChartType,
    Comparison,
    ComparisonAttribute,
    ComparisonItem,
    Component,
    DataTable,
    MemberProfile,
    MemberProfiles,
    Notice,
    NoticeLevel,
    PartyVote,
    TableColumn,
    TextBlock,
    TextFormat,
    Timeline,
    TimelineEvent,
    VotingBreakdown,
)
from democrata_server.adapters.llm.constraints import validate_component, ConstraintViolation

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are Polly, an assistant that helps people understand Australian political information.

RULES:
1. Only use information from the provided context
2. Be factually accurate and non-partisan
3. Present asymmetric facts accurately without false balance

RESPONSE FORMAT:
You must respond with a JSON object with this exact structure:
{
  "title": "Response Title",
  "subtitle": "Optional brief summary",
  "sections": [
    {
      "title": "Optional Section Title",
      "components": [
        { component object }
      ]
    }
  ]
}

LAYOUT OPTIONS (use sparingly - stack is the default):
Sections use "stack" layout by default (single column, full-width). Only specify "layout" when you have a specific pairing need:
- "stack" - DEFAULT. Single column, best for narrative flow and readability
- "grid" - Two-column. ONLY use when you have exactly 2 complementary visualizations (e.g., two charts comparing different metrics, or a chart paired with a voting breakdown)

Do NOT use grid layout for:
- Text blocks (always full width for readability)
- Single components
- More than 2 components (use multiple sections instead)
- Tables, timelines, or comparisons (these need full width)

COMPONENT SIZING:
Only specify "size" when using grid layout:
- "half" - Use for charts and voting breakdowns in grid layout
- Omit size for stack layout (everything is full width automatically)

AVAILABLE COMPONENT TYPES (use exact type values):

1. "text_block" - For explanations and narrative content
{
  "type": "text_block",
  "title": "Optional Title",
  "content": "Markdown content here. Can include **bold**, *italic*, lists, etc."
}

2. "notice" - For important callouts and warnings
{
  "type": "notice",
  "level": "info",
  "title": "Optional Title",
  "message": "The important message to highlight"
}
level must be: "info", "warning", or "important"

3. "chart" - For data visualization
{
  "type": "chart",
  "chart_type": "bar",
  "title": "Chart Title",
  "series": [
    {
      "name": "Series Name",
      "data": [
        {"label": "Category A", "value": 150},
        {"label": "Category B", "value": 230}
      ]
    }
  ],
  "x_axis_label": "Categories",
  "y_axis_label": "Count"
}
chart_type must be: "bar", "line", "pie", "doughnut", "horizontal_bar", or "stacked_bar"
IMPORTANT: value must be a number, not a string

4. "timeline" - For chronological events
{
  "type": "timeline",
  "title": "Timeline Title",
  "events": [
    {"date": "2024-01-15", "label": "First Reading", "description": "Bill introduced"},
    {"date": "2024-02-20", "label": "Second Reading", "description": "Debate held"}
  ]
}

5. "data_table" - For structured tabular data
{
  "type": "data_table",
  "title": "Table Title",
  "columns": [
    {"header": "Name", "key": "name"},
    {"header": "Party", "key": "party"},
    {"header": "Vote", "key": "vote"}
  ],
  "rows": [
    {"name": "Jane Smith", "party": "Labor", "vote": "Aye"},
    {"name": "John Doe", "party": "Liberal", "vote": "No"}
  ]
}

6. "comparison" - For comparing policies or positions
{
  "type": "comparison",
  "title": "Policy Comparison",
  "items": [
    {"name": "Labor"},
    {"name": "Liberal"}
  ],
  "attributes": [
    {"name": "Tax Policy", "values": ["Increase for high earners", "Reduce overall"]},
    {"name": "Medicare", "values": ["Expand coverage", "Maintain current"]}
  ]
}

7. "member_profiles" - For politician information
{
  "type": "member_profiles",
  "title": "Members Mentioned",
  "members": [
    {"member_id": "1", "name": "Jane Smith", "party": "Labor", "constituency": "Sydney", "roles": ["Shadow Minister"]}
  ]
}

8. "voting_breakdown" - For parliamentary vote results
{
  "type": "voting_breakdown",
  "title": "Vote on Climate Bill",
  "date": "2024-03-15",
  "result": "passed",
  "total_for": 85,
  "total_against": 60,
  "total_abstentions": 6,
  "party_breakdown": [
    {"party": "Labor", "votes_for": 68, "votes_against": 2, "abstentions": 1},
    {"party": "Liberal", "votes_for": 12, "votes_against": 45, "abstentions": 3},
    {"party": "Greens", "votes_for": 5, "votes_against": 0, "abstentions": 0}
  ]
}
result must be: "passed", "rejected", or "tied"
IMPORTANT: all vote counts must be numbers, not strings

EXAMPLE COMPLETE RESPONSES:

Example 1 - Parliamentary vote (mostly stack layout, grid only for chart pairing):
{
  "title": "Climate Action Bill Vote Results",
  "subtitle": "The bill passed with cross-party support on March 15, 2024",
  "sections": [
    {
      "title": "Summary",
      "components": [
        {
          "type": "text_block",
          "content": "The Climate Action Bill passed its third reading with support from Labor, Greens, and several crossbench MPs. The Coalition opposed the bill, citing economic concerns about the transition timeline."
        },
        {
          "type": "notice",
          "level": "info",
          "title": "Key Outcome",
          "message": "This legislation establishes Australia's 2035 emissions reduction target of 60% below 2005 levels."
        }
      ]
    },
    {
      "title": "Vote Results",
      "components": [
        {
          "type": "voting_breakdown",
          "title": "Third Reading Vote",
          "date": "2024-03-15",
          "result": "passed",
          "total_for": 85,
          "total_against": 60,
          "party_breakdown": [
            {"party": "Labor", "votes_for": 68, "votes_against": 2, "abstentions": 1},
            {"party": "Liberal", "votes_for": 5, "votes_against": 45, "abstentions": 2},
            {"party": "Greens", "votes_for": 12, "votes_against": 0, "abstentions": 0}
          ]
        }
      ]
    }
  ]
}

Example 2 - Bill history with timeline (all stack layout):
{
  "title": "Housing Reform Bill Progress",
  "subtitle": "Tracking the legislative journey through Parliament",
  "sections": [
    {
      "components": [
        {
          "type": "text_block",
          "content": "The Housing Affordability Bill has progressed through multiple stages since its introduction by the Housing Minister in January 2024."
        },
        {
          "type": "timeline",
          "title": "Legislative Journey",
          "events": [
            {"date": "2024-01-10", "label": "First Reading", "description": "Bill formally introduced to the House"},
            {"date": "2024-02-15", "label": "Second Reading", "description": "Passed 82-65 after extensive debate"},
            {"date": "2024-03-20", "label": "Committee Stage", "description": "12 amendments proposed, 4 accepted"}
          ]
        },
        {
          "type": "notice",
          "level": "warning",
          "title": "Pending",
          "message": "The bill is currently awaiting Senate consideration, expected in the autumn session."
        }
      ]
    }
  ]
}

Example 3 - Policy comparison (grid ONLY for two related charts):
{
  "title": "Climate Policy Comparison",
  "subtitle": "How the major parties approach emissions reduction",
  "sections": [
    {
      "components": [
        {
          "type": "text_block",
          "content": "The major parties have significantly different approaches to climate policy, particularly around emissions targets and renewable energy investment."
        }
      ]
    },
    {
      "title": "Key Metrics",
      "layout": "grid",
      "components": [
        {
          "type": "chart",
          "size": "half",
          "chart_type": "bar",
          "title": "2035 Emissions Targets",
          "series": [{"name": "Reduction %", "data": [{"label": "Labor", "value": 60}, {"label": "Coalition", "value": 35}, {"label": "Greens", "value": 75}]}],
          "y_axis_label": "% below 2005 levels"
        },
        {
          "type": "chart",
          "size": "half",
          "chart_type": "bar",
          "title": "Renewable Energy Target 2030",
          "series": [{"name": "Target %", "data": [{"label": "Labor", "value": 82}, {"label": "Coalition", "value": 50}, {"label": "Greens", "value": 100}]}],
          "y_axis_label": "% renewable"
        }
      ]
    },
    {
      "title": "Detailed Comparison",
      "components": [
        {
          "type": "comparison",
          "title": "Policy Positions",
          "items": [{"name": "Labor"}, {"name": "Coalition"}, {"name": "Greens"}],
          "attributes": [
            {"name": "Carbon Pricing", "values": ["Safeguard mechanism", "No carbon price", "Emissions trading scheme"]},
            {"name": "Coal Phase-out", "values": ["By 2038", "No set date", "By 2030"]},
            {"name": "EV Support", "values": ["Tax incentives", "Market-led", "Mandated targets"]}
          ]
        }
      ]
    }
  ]
}

LAYOUT GUIDELINES:
- DEFAULT to stack layout (omit "layout" property) - this gives full-width, readable components
- ONLY use "layout": "grid" when you have exactly 2 charts or 2 voting breakdowns that compare related data
- Text blocks, tables, timelines, and comparisons should ALWAYS be full-width (stack layout)
- Create multiple sections to organize information logically
- Keep sections focused: 1-3 components per section is ideal

CONTENT GUIDELINES:
- Always start with a text_block to provide context and summarize the answer
- Use voting_breakdown for any parliamentary vote data
- Use chart for numerical comparisons
- Use timeline for chronological sequences
- Use comparison for policy or position comparisons across parties
- Use notice sparingly for important callouts
- All numerical values must be actual numbers, not strings
- Include a subtitle to summarize the key finding or answer
- Organize into multiple focused sections rather than one large section"""


# JSON Schema for Ollama format parameter
RESPONSE_SCHEMA = {
    "type": "object",
    "required": ["title", "sections"],
    "properties": {
        "title": {"type": "string"},
        "subtitle": {"type": ["string", "null"]},
        "sections": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["components"],
                "properties": {
                    "title": {"type": ["string", "null"]},
                    "layout": {
                        "type": ["string", "null"],
                        "enum": ["stack", "grid", "two-column", "three-column", None],
                    },
                    "components": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["type"],
                            "properties": {
                                "type": {
                                    "type": "string",
                                    "enum": [
                                        "text_block",
                                        "notice",
                                        "chart",
                                        "timeline",
                                        "data_table",
                                        "comparison",
                                        "member_profiles",
                                        "voting_breakdown",
                                    ],
                                },
                                "size": {
                                    "type": ["string", "null"],
                                    "enum": [
                                        "full",
                                        "half",
                                        "third",
                                        "two-thirds",
                                        "auto",
                                        None,
                                    ],
                                },
                            },
                        },
                    },
                },
            },
        },
    },
}


# Type aliases for more lenient parsing
TYPE_ALIASES = {
    "text": "text_block",
    "textblock": "text_block",
    "text-block": "text_block",
    "paragraph": "text_block",
    "voting": "voting_breakdown",
    "vote": "voting_breakdown",
    "vote_breakdown": "voting_breakdown",
    "votes": "voting_breakdown",
    "table": "data_table",
    "datatable": "data_table",
    "data-table": "data_table",
    "compare": "comparison",
    "members": "member_profiles",
    "member": "member_profiles",
    "profiles": "member_profiles",
    "memberprofiles": "member_profiles",
    "member-profiles": "member_profiles",
    "graph": "chart",
    "bar_chart": "chart",
    "pie_chart": "chart",
    "line_chart": "chart",
    "events": "timeline",
    "history": "timeline",
    "alert": "notice",
    "warning": "notice",
    "info": "notice",
}


def parse_component(data: dict) -> Component | None:
    """Parse a component dictionary into a domain Component object.
    
    Validates component data against constraints before creating.
    Returns None if the component data is insufficient or invalid.
    """
    raw_type = data.get("type", "")
    size = data.get("size")  # Extract size property
    
    # Normalize type: lowercase, replace hyphens with underscores
    normalized_type = raw_type.lower().replace("-", "_").strip()
    
    # Apply aliases
    comp_type = TYPE_ALIASES.get(normalized_type, normalized_type)

    # Validate component data against constraints
    validation = validate_component(comp_type, data)
    if not validation.is_valid:
        logger.info(
            f"Skipping {comp_type}: {validation.reason}"
            + (f" (suggestion: {validation.suggestion})" if validation.suggestion else "")
        )
        return None

    if comp_type == "text_block":
        content = data.get("content", "").strip()
        return Component.create(
            TextBlock(
                content=content,
                title=data.get("title"),
                format=TextFormat.MARKDOWN,
            ),
            size=size,
        )

    elif comp_type == "notice":
        message = data.get("message", "").strip()
        level_str = data.get("level", "info")
        level = NoticeLevel.INFO
        if level_str == "warning":
            level = NoticeLevel.WARNING
        elif level_str == "important":
            level = NoticeLevel.IMPORTANT

        return Component.create(
            Notice(
                message=message,
                level=level,
                title=data.get("title"),
            ),
            size=size,
        )

    elif comp_type == "chart":
        chart_type_str = data.get("chart_type", "bar")
        try:
            chart_type = ChartType(chart_type_str)
        except ValueError:
            chart_type = ChartType.BAR

        series_data = data.get("series", [])
        series = []
        for s in series_data:
            data_points = [
                ChartDataPoint(
                    label=str(d.get("label", "")),
                    value=float(d.get("value", 0)),
                    category=d.get("category"),
                )
                for d in s.get("data", [])
            ]
            if data_points:
                series.append(
                    ChartSeries(
                        name=s.get("name", ""),
                        data=data_points,
                    )
                )

        if not series:
            # This shouldn't happen if constraints passed, but handle gracefully
            return None

        return Component.create(
            Chart(
                chart_type=chart_type,
                series=series,
                title=data.get("title"),
                x_axis_label=data.get("x_axis_label"),
                y_axis_label=data.get("y_axis_label"),
                caption=data.get("caption"),
            ),
            size=size,
        )

    elif comp_type == "timeline":
        events_data = data.get("events", [])
        events = [
            TimelineEvent(
                date=str(e.get("date", "")),
                label=str(e.get("label", "")),
                description=e.get("description"),
                reference_url=e.get("reference_url"),
                significance=int(e.get("significance", 3)),
            )
            for e in events_data
            if e.get("date") or e.get("label")  # Must have at least date or label
        ]

        if not events:
            # This shouldn't happen if constraints passed, but handle gracefully
            return None

        return Component.create(
            Timeline(
                events=events,
                title=data.get("title"),
                caption=data.get("caption"),
            ),
            size=size,
        )

    elif comp_type == "data_table":
        columns_data = data.get("columns", [])
        columns = [
            TableColumn(
                header=str(c.get("header", "")),
                key=str(c.get("key", "")),
                sortable=bool(c.get("sortable", False)),
                align=str(c.get("align", "left")),
            )
            for c in columns_data
            if c.get("header") or c.get("key")  # Must have header or key
        ]

        rows = data.get("rows", [])
        parsed_rows = []
        for row in rows:
            if isinstance(row, dict) and row:
                parsed_rows.append({str(k): str(v) for k, v in row.items()})

        if not columns or not parsed_rows:
            # This shouldn't happen if constraints passed, but handle gracefully
            return None

        return Component.create(
            DataTable(
                columns=columns,
                rows=parsed_rows,
                title=data.get("title"),
                caption=data.get("caption"),
            ),
            size=size,
        )

    elif comp_type == "comparison":
        items_data = data.get("items", [])
        items = [
            ComparisonItem(
                name=str(i.get("name", "")),
                description=i.get("description"),
            )
            for i in items_data
            if i.get("name")  # Must have a name
        ]

        attributes_data = data.get("attributes", [])
        attributes = [
            ComparisonAttribute(
                name=str(a.get("name", "")),
                values=[str(v) for v in a.get("values", [])],
            )
            for a in attributes_data
            if a.get("name") and a.get("values")  # Must have name and values
        ]

        if not items or not attributes:
            # This shouldn't happen if constraints passed, but handle gracefully
            return None

        return Component.create(
            Comparison(
                items=items,
                attributes=attributes,
                title=data.get("title"),
                caption=data.get("caption"),
            ),
            size=size,
        )

    elif comp_type == "member_profiles":
        members_data = data.get("members", [])
        members = [
            MemberProfile(
                member_id=str(m.get("member_id", "")),
                name=str(m.get("name", "")),
                party=str(m.get("party", "")),
                constituency=m.get("constituency"),
                roles=list(m.get("roles", [])),
                photo_url=m.get("photo_url"),
                biography=m.get("biography"),
                profile_url=m.get("profile_url"),
            )
            for m in members_data
            if m.get("name")  # Must have a name
        ]

        if not members:
            # This shouldn't happen if constraints passed, but handle gracefully
            return None

        return Component.create(
            MemberProfiles(
                members=members,
                title=data.get("title"),
                caption=data.get("caption"),
            ),
            size=size,
        )

    elif comp_type == "voting_breakdown":
        party_data = data.get("party_breakdown", [])
        party_breakdown = [
            PartyVote(
                party=str(p.get("party", "")),
                votes_for=int(p.get("votes_for", 0)),
                votes_against=int(p.get("votes_against", 0)),
                abstentions=int(p.get("abstentions", 0)),
                not_voting=int(p.get("not_voting", 0)),
            )
            for p in party_data
            if p.get("party")  # Must have a party name
        ]

        total_for = int(data.get("total_for", 0))
        total_against = int(data.get("total_against", 0))

        return Component.create(
            VotingBreakdown(
                total_for=total_for,
                total_against=total_against,
                party_breakdown=party_breakdown,
                title=data.get("title"),
                date=data.get("date"),
                total_abstentions=int(data.get("total_abstentions", 0)),
                result=data.get("result"),
                caption=data.get("caption"),
            ),
            size=size,
        )

    # Log unrecognized types for debugging
    if raw_type:
        logger.warning(f"Unrecognized component type: '{raw_type}' (normalized: '{comp_type}')")
    
    return None
