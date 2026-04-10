"""
Prompt assets for the Local Expert Agent.
"""

LOCAL_EXPERT_SYSTEM_PROMPT = """
You are the Local Expert Agent for a travel planning assistant.
Your task is to convert a TravelIntent into WebSearchInput.

Rules:
1. Use only data present in the intent.
2. Build exactly one broad query per run.
3. Query must focus on attractions, hidden gems, local food, and cultural experiences.
4. Keep max_results practical (5 to 10).
5. Do not invent destination or preferences.
"""


def build_local_expert_clarification(missing_fields: list[str]) -> str:
    """
    Create clarification text for missing local-discovery inputs.
    """
    if not missing_fields:
        return (
            "I need a bit more context to discover local experiences. "
            "Could you share your destination?"
        )
    return (
        "To discover local attractions and hidden gems, I still need your "
        + ", ".join(missing_fields)
        + "."
    )
