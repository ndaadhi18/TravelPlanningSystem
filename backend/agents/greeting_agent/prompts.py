"""
Prompt assets for the Greeting Agent.
"""

from __future__ import annotations

from backend.schemas.travel_intent import TravelIntent

GREETING_SYSTEM_PROMPT = """
You are the Greeting Agent for a travel planning assistant.
Extract the user's request into the TravelIntent schema accurately.

Rules:
1. Use only information provided by the user.
2. Do not hallucinate destination, dates, budget, or traveler count.
3. Keep unknown fields empty/null/default according to schema.
4. Normalize obvious formatting (for example, uppercase currency codes).
5. Do not ask follow-up questions in the structured output itself.
"""


def build_clarification_question(intent: TravelIntent) -> str:
    """
    Create a concise clarification question for incomplete travel intent.
    """
    missing_parts: list[str] = []

    if not intent.destination:
        missing_parts.append("destination")
    if intent.budget <= 0:
        missing_parts.append("budget")
    if not intent.start_date and not intent.duration_days:
        missing_parts.append("trip dates or trip duration")

    if not missing_parts:
        return (
            "Thanks! I have most details. Could you share any travel preferences "
            "(for example food, museums, nightlife, or pace) before I continue?"
        )

    joined = ", ".join(missing_parts)
    return (
        "Great start. To continue planning, could you share your "
        f"{joined}?"
    )
