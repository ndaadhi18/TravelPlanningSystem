"""
Prompt assets for the Accommodation Agent.
"""

ACCOMMODATION_SYSTEM_PROMPT = """
You are the Accommodation Agent for a travel planning assistant.
Your task is to convert a TravelIntent into HotelSearchInput.

Rules:
1. Use only data present in the intent.
2. Produce strict HotelSearchInput-compatible values.
3. Use a 3-letter uppercase city code for city_code.
4. Keep price_range only as one of: budget, mid, luxury.
5. Do not invent details that are not provided.
"""


def build_accommodation_clarification(missing_fields: list[str]) -> str:
    """
    Create clarification message for missing hotel-search inputs.
    """
    if not missing_fields:
        return (
            "I need a few more accommodation details before I can search hotels. "
            "Could you share your destination and stay dates?"
        )
    return (
        "To search hotels, I still need your "
        + ", ".join(missing_fields)
        + "."
    )
