from __future__ import annotations

import json
import uuid
import re
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from openai import AsyncOpenAI
from pydantic import BaseModel

from backend.core.settings import get_settings
from backend.schemas.accommodation import HotelOption
from backend.schemas.itinerary import LocalInsight
from backend.schemas.replit_api import (
    TravelPlanInput,
    TravelPlanOutput,
    TravelSummary,
    APIDayPlan,
    BudgetBreakdown,
    LiveResearch,
)
from backend.schemas.transport import FlightOption
from backend.schemas.travel_intent import TravelIntent
from backend.orchestration.graph import build_graph

router = APIRouter()
graph = build_graph()

# ── Intent-extraction system prompt ──────────────────────────────────────────

_INTENT_PROMPT = """You are Aura, a conversational AI travel planning assistant. \
Your job is to gather trip details through natural, friendly conversation, then hand off \
to a team of specialized planning agents.

You need to collect:
- origin      : city or location they are departing from
- destination : where they want to travel
- days        : trip length as a plain integer string (e.g. "3", "7")
- budget      : must map to exactly one of "budget", "moderate", or "luxury"
- style       : must map to exactly one of "relaxed", "balanced", "action-packed", "culture", "foodie"
- preferences : optional — interests, dietary needs, things to avoid (empty string if none)

Conversation rules:
- Be warm, enthusiastic, and genuinely curious
- Let the conversation flow — ask about 1–2 things at a time, never fire a form
- Accept natural language and infer sensibly:
    "a week" → "7", "long weekend" → "3", "two weeks" → "14"
    "cheap / backpacking" → "budget", "mid-range / normal" → "moderate", "splurge / high-end" → "luxury"
    "chill / slow" → "relaxed", "mix of everything" → "balanced", "packed / adventure" → "action-packed"
    "history / museums / art" → "culture", "food lover / local eats" → "foodie"
- If the user gives multiple details at once, acknowledge them all and ask only about what is still missing
- Preferences are optional — ask once; if the user skips or you already have the required fields, proceed
- Keep each response concise: 2–4 sentences max before the intent signal

When you have origin, destination, days, budget, and style — preferences are optional — respond with \
a short enthusiastic confirmation that you are ready to start (e.g. "I have everything I need — \
spinning up the agents now!"). Then on the very last line of your reply output this marker \
with no trailing text whatsoever:

__INTENT__{"origin":"VALUE","destination":"VALUE","days":"NUMBER","budget":"LEVEL","style":"STYLE","preferences":"VALUE"}

JSON rules:
- days  : quoted integer string — "3", "7", "14"
- budget: exactly "budget", "moderate", or "luxury"
- style : exactly "relaxed", "balanced", "action-packed", "culture", or "foodie"
- preferences: empty string "" if not provided
- Output the marker on the LAST line; nothing after it
"""


# ── Chat streaming endpoint ───────────────────────────────────────────────────

class _ChatMessage(BaseModel):
    role: str
    content: str


class _ChatRequest(BaseModel):
    messages: list[_ChatMessage]


@router.post("/api/chat")
@router.post("/chat")
async def chat_stream(request: _ChatRequest):
    """Stream an intent-extraction conversation with gpt-4o-mini via SSE."""
    settings = get_settings()
    client = AsyncOpenAI(api_key=settings.openai_api_key)

    async def _generate():
        api_messages: list[dict[str, str]] = [
            {"role": "system", "content": _INTENT_PROMPT},
        ]
        api_messages.extend(
            {"role": m.role, "content": m.content} for m in request.messages
        )

        try:
            stream = await client.chat.completions.create(
                model=settings.openai_model_name,
                messages=api_messages,
                stream=True,
                temperature=0.7,
                max_tokens=512,
            )
            async for chunk in stream:
                content = chunk.choices[0].delta.content
                if content:
                    yield f"data: {json.dumps({'type': 'delta', 'content': content})}\n\n"
        except Exception as exc:
            fallback = "I'm having a little trouble right now — please try again in a moment."
            yield f"data: {json.dumps({'type': 'delta', 'content': fallback})}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )

def extract_budget(budget_str: str) -> float:
    match = re.search(r'\d+', budget_str.replace(',', ''))
    return float(match.group()) if match else 2000.0


def _get_field(item: Any, name: str) -> Any:
    if isinstance(item, dict):
        return item.get(name)
    return getattr(item, name, None)


def _format_price(amount: Any, currency: str = "USD") -> str:
    try:
        value = float(amount)
    except (TypeError, ValueError):
        value = 0.0
    return f"{value:.2f} {currency}"


def _build_search_queries(intent: TravelIntent) -> list[str]:
    queries: list[str] = []
    if intent.source_location and intent.destination:
        queries.append(
            f"Flights from {intent.source_location} to {intent.destination} on {intent.start_date}"
        )
    if intent.destination:
        queries.append(
            f"Hotels in {intent.destination} from {intent.start_date} for {intent.duration_days} nights"
        )
        queries.append(
            f"Best attractions and local insights in {intent.destination}"
        )
    return queries


def _flight_to_live_item(flight: FlightOption | dict[str, Any]) -> dict[str, Any]:
    airline = _get_field(flight, "airline") or "Flight"
    flight_number = _get_field(flight, "flight_number") or ""
    origin = _get_field(flight, "origin") or "N/A"
    destination = _get_field(flight, "destination") or "N/A"
    departure_time = _get_field(flight, "departure_time") or ""
    arrival_time = _get_field(flight, "arrival_time") or ""
    price = _get_field(flight, "price") or 0
    currency = _get_field(flight, "currency") or "USD"
    return {
        "category": "flight",
        "title": f"{airline} {flight_number}".strip(),
        "url": "",
        "snippet": f"{origin} → {destination} | {departure_time} → {arrival_time}",
        "price_hint": _format_price(price, currency),
        "source": "Flight search",
    }


def _hotel_to_live_item(hotel: HotelOption | dict[str, Any]) -> dict[str, Any]:
    name = _get_field(hotel, "name") or "Hotel"
    address = _get_field(hotel, "address") or ""
    price_per_night = _get_field(hotel, "price_per_night") or 0
    total_price = _get_field(hotel, "total_price")
    currency = _get_field(hotel, "currency") or "USD"
    snippet = address or "Live hotel option"
    price_hint = _format_price(total_price if total_price is not None else price_per_night, currency)
    return {
        "category": "hotel",
        "title": name,
        "url": _get_field(hotel, "source_url") or "",
        "snippet": snippet,
        "price_hint": price_hint,
        "source": "Hotel search",
    }


def _insight_to_live_item(insight: LocalInsight | dict[str, Any]) -> dict[str, Any]:
    title = _get_field(insight, "name") or "Local insight"
    description = _get_field(insight, "description") or ""
    category = _get_field(insight, "category")
    if hasattr(category, "value"):
        category = category.value
    estimated_cost = _get_field(insight, "estimated_cost")
    return {
        "category": category or "activity",
        "title": title,
        "url": _get_field(insight, "source_url") or "",
        "snippet": description,
        "price_hint": _format_price(estimated_cost, "USD") if estimated_cost is not None else "Check live site",
        "source": "Tavily local search",
    }


def _build_live_research(state: dict[str, Any], intent: TravelIntent) -> LiveResearch:
    return LiveResearch(
        status="live",
        searched_at=datetime.utcnow().isoformat() + "Z",
        queries=_build_search_queries(intent),
        hotels=[_hotel_to_live_item(item) for item in (state.get("hotel_options") or [])][:3],
        markets=[],
        activities=[_insight_to_live_item(item) for item in (state.get("local_insights") or [])][:5],
        transport=[_flight_to_live_item(item) for item in (state.get("flight_options") or [])][:3],
        notes=[
            "Live MCP search results are included where available.",
            "OpenAI gpt-4o-mini powers itinerary generation and tool selection.",
        ],
    )


@router.post("/api/plan", response_model=TravelPlanOutput)
@router.post("/plan", response_model=TravelPlanOutput)
async def create_plan(input_data: TravelPlanInput):
    tomorrow_str = (datetime.utcnow().date() + timedelta(days=1)).isoformat()
    user_text = (
        f"I want to travel from {input_data.origin} to {input_data.destination} for "
        f"{input_data.days} days starting on {tomorrow_str}. My budget is {input_data.budget}. "
        f"I prefer {input_data.style} style and my preferences are: {input_data.preferences}."
    )

    days_match = re.search(r'\d+', str(input_data.days))
    parsed_days = int(days_match.group()) if days_match else 3

    intent = TravelIntent(
        destination=input_data.destination or "Unknown",
        source_location=input_data.origin or "Unknown",
        start_date=tomorrow_str,
        budget=extract_budget(input_data.budget),
        duration_days=parsed_days,
        preferences=input_data.preferences,
    )

    initial_state = {
        "messages": [user_text],
        "user_input": user_text,
        "travel_intent": intent,
        "intent_confirmed": True,
    }

    try:
        final_state = await graph.ainvoke(
            initial_state,
            config={"configurable": {"thread_id": str(uuid.uuid4())}},
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

    itinerary = final_state.get("itinerary")
    if not itinerary:
        errors = final_state.get("errors", [])
        msgs = final_state.get("messages", [])
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate itinerary. Errors: {errors}. Messages: {msgs}",
        )

    days_out: list[APIDayPlan] = []
    for d in itinerary.days:
        activities = []

        # Flight info goes first on travel days
        if getattr(d, "transport", None):
            t = d.transport
            dep = getattr(t, "origin", "?")
            arr = getattr(t, "destination", "?")
            dep_time = getattr(t, "departure_time", "")
            dep_label = dep_time.split("T")[1][:5] if dep_time and "T" in dep_time else ""
            activities.append(
                f"\u2708 Fly {t.airline} {t.flight_number}: {dep} \u2192 {arr}"
                + (f" at {dep_label}" if dep_label else "")
                + (f" \u00b7 {t.price:.0f} {t.currency}" if getattr(t, "price", 0) else "")
            )

        for a in (getattr(d, "activities", []) or []):
            name = getattr(a, "name", "").strip()
            desc = getattr(a, "description", "").strip()
            # Reconstruct "Morning: Land, clear customs and check in..." format
            if name and desc:
                activities.append(f"{name}: {desc}")
            elif desc:
                activities.append(desc)
            elif name:
                activities.append(name)

        # Hotel check-in note (append at end so it doesn't break flow)
        if getattr(d, "hotel", None) and d.day_number == 1:
            rating = f" (★{d.hotel.rating:.1f})" if d.hotel.rating else ""
            price = f" · ₹{d.hotel.price_per_night:.0f}/night" if d.hotel.price_per_night else ""
            activities.insert(1, f"\U0001f3e8 Staying at {d.hotel.name}{rating}{price}")

        days_out.append(
            APIDayPlan(
                day=f"Day {getattr(d, 'day_number', '?')}",
                title=d.title or f"Day {getattr(d, 'day_number', '?')} Plan",
                activities=activities,
            )

        )

    budget_summary = getattr(itinerary, "budget_summary", None)
    budget_breakdown = BudgetBreakdown(
        transport=f"{getattr(budget_summary, 'transport_cost', 0)} USD",
        stay=f"{getattr(budget_summary, 'accommodation_cost', 0)} USD",
        food=f"{getattr(budget_summary, 'food_estimate', 0)} USD",
    )

    return TravelPlanOutput(
        summary=TravelSummary(
            route=f"{input_data.origin} -> {input_data.destination}",
            days=str(input_data.days),
            budget=input_data.budget,
            style=input_data.style,
        ),
        highlights=(
            itinerary.highlights
            if getattr(itinerary, "highlights", None)
            else ["Generated by LangGraph Agents", "Checked real-time data using MCP"]
        ),
        plan=days_out,
        budget=budget_breakdown,
        live_research=_build_live_research(final_state, intent),
    )