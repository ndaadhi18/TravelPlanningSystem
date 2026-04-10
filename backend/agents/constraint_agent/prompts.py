"""
Prompt assets for the Constraint Agent.
"""

CONSTRAINT_SYSTEM_PROMPT = """
You are the Constraint Agent for a travel planning assistant.
Your task is to assemble an Itinerary object from gathered travel data.

Rules:
1. Use only data available in state.
2. Preserve destination and trip dates from TravelIntent.
3. Build a practical day-by-day plan with available activities.
4. If any data source is missing, still create a partial itinerary and include warnings.
5. Do not call external tools from this step.
"""


def build_constraint_warnings(
    *,
    missing_sources: list[str],
    over_budget: bool,
) -> list[str]:
    """
    Build user-facing warnings for partial-data and budget constraints.
    """
    warnings: list[str] = []
    for source in missing_sources:
        warnings.append(
            f"Limited data: no {source} were available, so parts of the itinerary are estimated."
        )
    if over_budget:
        warnings.append(
            "This draft exceeds your stated budget. Consider lower-cost flights, hotels, or fewer paid activities."
        )
    return warnings


def build_constraint_clarification(missing_fields: list[str]) -> str:
    """
    Clarification message when core itinerary inputs are missing.
    """
    if not missing_fields:
        return (
            "I need a little more trip information before assembling your itinerary. "
            "Please share your destination and dates."
        )
    return (
        "Before I assemble your itinerary, I still need your "
        + ", ".join(missing_fields)
        + "."
    )
