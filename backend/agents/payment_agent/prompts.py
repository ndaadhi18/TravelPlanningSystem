"""
Prompt assets for the Payment Agent.
"""

PAYMENT_SYSTEM_PROMPT = """
You are the Payment Agent for a travel planning assistant.
Generate a concise, user-friendly booking confirmation summary from structured trip data.

Rules:
1. Use only data present in the state.
2. Keep the tone clear and reassuring.
3. Mention destination, dates, and total estimated cost.
4. Do not mention real payment processing; this is a mock confirmation.
"""


def build_payment_clarification(missing_fields: list[str]) -> str:
    """
    Clarification message when booking confirmation inputs are incomplete.
    """
    if not missing_fields:
        return (
            "I need one more detail before finalizing your booking confirmation. "
            "Please confirm your itinerary."
        )
    return (
        "Before I finalize booking confirmation, I still need your "
        + ", ".join(missing_fields)
        + "."
    )
