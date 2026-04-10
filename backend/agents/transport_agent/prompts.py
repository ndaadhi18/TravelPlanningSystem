"""
Prompt assets for the Transport Agent.
"""

TRANSPORT_SYSTEM_PROMPT = """
You are the Transport Agent for a travel planning assistant.
Your task is to convert a TravelIntent into FlightSearchInput.

Rules:
1. Use only data present in the intent.
2. Produce strict FlightSearchInput-compatible values.
3. Use 3-letter uppercase IATA-like codes for origin/destination when possible.
4. Keep return_date null if unavailable.
5. Do not invent details that are not provided.
"""


def build_transport_clarification(missing_fields: list[str]) -> str:
    """
    Create clarification message for missing flight-search inputs.
    """
    if not missing_fields:
        return (
            "I need a few more transport details before I can search flights. "
            "Could you share your departure city and travel date?"
        )
    return (
        "To search flights, I still need your "
        + ", ".join(missing_fields)
        + "."
    )
