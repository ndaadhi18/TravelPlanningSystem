from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, HTTPException
import uuid
import re

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
        activities = [a.name for a in getattr(d, "activities", []) or []]
        if getattr(d, "hotel", None):
            activities.insert(0, f"Check in to {d.hotel.name}")
        if getattr(d, "transport", None):
            activities.append(
                f"Flight options for day: {d.transport.airline} {d.transport.flight_number}"
            )

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