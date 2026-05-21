"""
Constraint Agent node implementation.
"""

from __future__ import annotations

import json
import re
from datetime import date, timedelta
from typing import Any, Mapping, Optional, TypeVar

from pydantic import BaseModel, ValidationError

from backend.agents.base_agent import BaseAgent, wrap_agent_error
from backend.agents.constraint_agent.prompts import (
    build_constraint_clarification,
    build_constraint_warnings,
)
from backend.schemas.accommodation import HotelOption
from backend.schemas.itinerary import (
    BudgetSummary,
    DayPlan,
    InsightCategory,
    Itinerary,
    LocalInsight,
)
from backend.schemas.transport import FlightOption
from backend.schemas.travel_intent import TravelIntent
from backend.utils.logger import get_logger

logger = get_logger("agents.constraint")
TModel = TypeVar("TModel", bound=BaseModel)


class ConstraintAgent(BaseAgent):
    """Validate constraints and assemble a human-readable itinerary."""

    def __init__(self, *, llm: Optional[Any] = None):
        super().__init__("constraint_agent", llm=llm)

    # ── Main entry point ─────────────────────────────────────────────

    async def run(self, state: Mapping[str, Any]) -> dict[str, Any]:
        intent = _normalize_intent(state.get("travel_intent"))
        if intent is None:
            return {
                "messages": [build_constraint_clarification(
                    ["destination", "trip start date", "trip end date or duration"]
                )],
                "current_phase": "planning",
            }

        missing_fields = _missing_core_fields(intent)
        if missing_fields:
            return {
                "messages": [build_constraint_clarification(missing_fields)],
                "current_phase": "planning",
            }

        flights = _normalize_model_list(state.get("flight_options"), FlightOption)
        hotels = _normalize_model_list(state.get("hotel_options"), HotelOption)
        insights = _normalize_model_list(state.get("local_insights"), LocalInsight)

        try:
            # One smart LLM call builds the complete day plan
            day_plans, highlights = await self._build_smart_day_plans(
                intent, flights, hotels, insights
            )

            start_date, end_date, _ = _resolve_trip_window(intent)
            itinerary = Itinerary(
                title=f"Your {intent.duration_days or len(day_plans)}-Day Trip to {intent.destination}",
                destination=intent.destination or "Unknown",
                source_location=intent.source_location,
                start_date=start_date,
                end_date=end_date,
                num_travelers=max(1, intent.num_travelers),
                days=day_plans,
                highlights=highlights or [i.name for i in insights[:3]],
                warnings=[],
            )

            nights = _trip_nights(start_date, end_date)
            budget_summary = _compute_budget_summary(
                intent=intent, flights=flights, hotels=hotels,
                insights=insights, nights=nights,
            )
            warnings = build_constraint_warnings(
                missing_sources=_missing_sources(flights, hotels, insights),
                over_budget=bool(
                    budget_summary.budget_limit > 0
                    and budget_summary.total > budget_summary.budget_limit
                ),
            )
            itinerary.total_estimated_cost = budget_summary.total
            itinerary.budget_summary = budget_summary
            itinerary.warnings = warnings

            return {
                "itinerary": itinerary,
                "budget_summary": budget_summary,
                "current_phase": "feedback",
            }

        except Exception as error:
            wrapped = wrap_agent_error(
                "constraint_agent", "run", error,
                context={"current_phase": state.get("current_phase", "itinerary")},
            )
            return {
                "errors": [wrapped.message],
                "messages": [
                    "I could not assemble your itinerary. "
                    "Please confirm your destination, dates, and budget."
                ],
                "current_phase": "planning",
            }

    # ── Day plan builder ─────────────────────────────────────────────

    async def _build_smart_day_plans(
        self,
        intent: TravelIntent,
        flights: list[FlightOption],
        hotels: list[HotelOption],
        insights: list[LocalInsight],
    ) -> tuple[list[DayPlan], list[str]]:
        """
        Use LLM to generate realistic Morning/Afternoon/Evening day plans.
        Falls back to a clean deterministic builder if the LLM fails.
        """
        if self._llm is not None:
            try:
                return await self._llm_day_plans(intent, flights, hotels, insights)
            except Exception as e:
                logger.warning(f"LLM day plan failed: {e}. Using deterministic fallback.")

        return _build_deterministic_day_plans(intent, flights, hotels, insights), []

    async def _llm_day_plans(
        self,
        intent: TravelIntent,
        flights: list[FlightOption],
        hotels: list[HotelOption],
        insights: list[LocalInsight],
    ) -> tuple[list[DayPlan], list[str]]:
        """One focused LLM call → structured JSON day plan."""
        from langchain_core.messages import HumanMessage, SystemMessage

        destination = intent.destination or "destination"
        trip_days = intent.duration_days or 3
        start_date, _, _ = _resolve_trip_window(intent)
        travelers = max(1, intent.num_travelers)

        # Flight context (concise — never the full object)
        flight_ctx = ""
        if flights:
            f = flights[0]
            dep_time = getattr(f, "departure_time", "")
            dep_label = dep_time.split("T")[1][:5] if dep_time and "T" in dep_time else ""
            flight_ctx = (
                f"Outbound flight: {f.airline} {f.flight_number} "
                f"{getattr(f, 'origin', '?')} → {getattr(f, 'destination', '?')}"
                + (f" at {dep_label}" if dep_label else "")
            )

        # Hotel context (concise)
        hotel_ctx = ""
        if hotels:
            h = hotels[0]
            price_str = f" (~₹{h.price_per_night:.0f}/night)" if h.price_per_night else ""
            hotel_ctx = f"Hotel: {h.name}{price_str}"

        # Use ONLY insight names as inspiration — never dump raw article body
        insight_ctx = "\n".join(
            f"- {getattr(i, 'name', '')[:70]}"
            for i in insights[:8]
        ) or "Popular local attractions and cuisine"

        system = (
            "You are an expert travel planner. Create realistic, well-paced itineraries. "
            "Think like a seasoned traveler: Day 1 starts with arrival logistics and light exploration. "
            "Last day ends with checkout and departure. Middle days have rich morning/afternoon/evening activities. "
            "Be specific, vivid, and concise. Never copy article headlines verbatim."
        )

        user = f"""Plan a {trip_days}-day trip to {destination} for {travelers} person(s).

Trip details:
- Start date: {start_date}
- Style: {intent.travel_style.value if intent.travel_style else 'flexible'}
- Preferences: {intent.preferences or 'general sightseeing and local cuisine'}
- {flight_ctx}
- {hotel_ctx}

Local themes to weave in (rewrite in your own words — do not copy these titles):
{insight_ctx}

Output ONLY valid JSON (no markdown fences, no extra text):
{{
  "highlights": ["3 vivid trip highlights as short strings"],
  "days": [
    {{
      "day": 1,
      "title": "Arrival & First Impressions",
      "activities": [
        "Morning: Land, clear customs, and take a cab to the hotel — check in and freshen up.",
        "Afternoon: Short stroll around the hotel neighbourhood to get your bearings.",
        "Evening: Head to a popular local street-food area for dinner.",
        "Night: Return to hotel and rest."
      ]
    }}
  ]
}}

Rules:
- Generate exactly {trip_days} day objects.
- Each day must have 3–5 activities prefixed with Morning/Afternoon/Evening/Night + colon.
- Each activity: max 25 words, vivid and specific. No marketing language.
- Day 1 MUST start with flight arrival + hotel check-in.
- Last day MUST end with hotel checkout + departure to airport."""

        result = self._llm.invoke([SystemMessage(content=system), HumanMessage(content=user)])
        raw = getattr(result, "content", str(result))

        # Strip markdown fences if model wraps response
        raw = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            raise ValueError("LLM returned no valid JSON for day plan")

        data = json.loads(match.group())
        highlights: list[str] = data.get("highlights", [])
        llm_days: list[dict] = data.get("days", [])

        hotel = hotels[0] if hotels else None
        flight = flights[0] if flights else None
        day_plans: list[DayPlan] = []
        start = date.fromisoformat(start_date)

        for idx, day_data in enumerate(llm_days[:trip_days]):
            current_date = (start + timedelta(days=idx)).isoformat()
            activity_strings: list[str] = day_data.get("activities", [])

            # Each "Morning: ..." string → LocalInsight with clean description
            day_activities = [
                LocalInsight(
                    name=act.split(":")[0].strip() if ":" in act else f"Activity {i + 1}",
                    category=InsightCategory.ACTIVITY,
                    description=(act.split(":", 1)[1].strip() if ":" in act else act)[:500],
                )
                for i, act in enumerate(activity_strings)
            ]

            hotel_cost = hotel.price_per_night if hotel else 0.0
            day_plans.append(DayPlan(
                day_number=idx + 1,
                date=current_date,
                title=day_data.get("title", f"Day {idx + 1}"),
                activities=day_activities,
                transport=flight if idx == 0 else None,
                hotel=hotel,
                estimated_day_cost=round(hotel_cost + 45.0 * travelers, 2),
            ))

        return day_plans, highlights


# ── Module-level node entrypoint ─────────────────────────────────────


async def constraint_node(state: Mapping[str, Any], *, llm: Optional[Any] = None) -> dict[str, Any]:
    """LangGraph-compatible constraint node entrypoint."""
    agent = ConstraintAgent(llm=llm)
    return await agent.run(state)


# ── Helper functions ─────────────────────────────────────────────────


def _normalize_intent(raw_intent: Any) -> Optional[TravelIntent]:
    if raw_intent is None:
        return None
    if isinstance(raw_intent, TravelIntent):
        return raw_intent
    if isinstance(raw_intent, Mapping):
        try:
            return TravelIntent.model_validate(raw_intent)
        except ValidationError:
            return None
    return None


def _missing_core_fields(intent: TravelIntent) -> list[str]:
    missing: list[str] = []
    if not intent.destination:
        missing.append("destination")
    if not intent.start_date:
        missing.append("trip start date")
    if not intent.end_date and not intent.duration_days:
        missing.append("trip end date or duration")
    return missing


def _normalize_model_list(raw: Any, model_cls: type[TModel]) -> list[TModel]:
    if not isinstance(raw, list):
        return []
    parsed: list[TModel] = []
    for item in raw:
        try:
            if isinstance(item, model_cls):
                parsed.append(item)
            else:
                parsed.append(model_cls.model_validate(item))
        except ValidationError:
            logger.warning(f"Skipping malformed {model_cls.__name__} entry in state.")
    return parsed


def _resolve_trip_window(intent: TravelIntent) -> tuple[str, str, int]:
    if not intent.start_date:
        raise ValueError("TravelIntent.start_date is required for itinerary assembly.")
    start = date.fromisoformat(intent.start_date)
    if intent.end_date:
        end = date.fromisoformat(intent.end_date)
    elif intent.duration_days:
        end = start + timedelta(days=intent.duration_days)
    else:
        end = start + timedelta(days=1)
    trip_days = max(1, (end - start).days)
    return start.isoformat(), end.isoformat(), trip_days


def _build_deterministic_day_plans(
    intent: TravelIntent,
    flights: list[FlightOption],
    hotels: list[HotelOption],
    insights: list[LocalInsight],
) -> list[DayPlan]:
    """Fallback: build a clean day plan without LLM."""
    start_date, _, trip_days = _resolve_trip_window(intent)
    travelers = max(1, intent.num_travelers)
    start = date.fromisoformat(start_date)
    hotel = hotels[0] if hotels else None
    flight = flights[0] if flights else None

    # Generic but sensible time-of-day labels
    _day_titles = [
        "Arrival & First Impressions",
        "Local Culture & Hidden Gems",
        "Iconic Landmarks & Neighbourhoods",
        "Food, Markets & Local Life",
        "Day Trips & Scenic Escapes",
        "Relaxation & Leisure",
        "Final Explorations & Departure Prep",
    ]

    _default_schedule = [
        ("Morning", "Arrive, check in to hotel, and freshen up after the journey."),
        ("Afternoon", "Explore the neighbourhood and grab lunch at a local eatery."),
        ("Evening", "Dinner at a popular local restaurant — try the signature dish."),
        ("Night", "Rest at hotel."),
    ]

    plans: list[DayPlan] = []
    for day_idx in range(trip_days):
        current_date = (start + timedelta(days=day_idx)).isoformat()
        title = _day_titles[day_idx] if day_idx < len(_day_titles) else f"Day {day_idx + 1} Exploration"

        # Slot 2–3 insights per day
        day_insights = insights[day_idx::trip_days][:2]
        if day_insights:
            day_activities = [
                LocalInsight(
                    name=slot,
                    category=InsightCategory.ACTIVITY,
                    description=_default_schedule[i][1] if day_idx == 0 else getattr(ins, "name", "")[:80],
                )
                for i, (slot, ins) in enumerate(
                    zip(["Morning", "Afternoon", "Evening"], [None] + list(day_insights))  # type: ignore[list-item]
                )
                if ins is not None or day_idx == 0
            ]
        else:
            day_activities = [
                LocalInsight(
                    name=label,
                    category=InsightCategory.ACTIVITY,
                    description=desc,
                )
                for label, desc in _default_schedule
            ]

        hotel_cost = hotel.price_per_night if hotel else 0.0
        plans.append(DayPlan(
            day_number=day_idx + 1,
            date=current_date,
            title=title,
            activities=day_activities,
            transport=flight if day_idx == 0 else None,
            hotel=hotel,
            estimated_day_cost=round(hotel_cost + 45.0 * travelers, 2),
        ))

    return plans


def _compute_budget_summary(
    *,
    intent: TravelIntent,
    flights: list[FlightOption],
    hotels: list[HotelOption],
    insights: list[LocalInsight],
    nights: int,
) -> BudgetSummary:
    transport_cost = flights[0].price if flights else 0.0

    accommodation_cost = 0.0
    if hotels:
        primary = hotels[0]
        if primary.total_price is not None:
            accommodation_cost = primary.total_price
        else:
            accommodation_cost = primary.price_per_night * max(1, nights)

    activities_cost = sum(item.estimated_cost or 0.0 for item in insights)
    food_estimate = 30.0 * max(1, intent.num_travelers) * max(1, nights)
    miscellaneous = 15.0 * max(1, intent.num_travelers) * max(1, nights)
    total = transport_cost + accommodation_cost + activities_cost + food_estimate + miscellaneous

    currency = (
        intent.currency
        or (flights[0].currency if flights else None)
        or (hotels[0].currency if hotels else "USD")
    )

    return BudgetSummary(
        transport_cost=round(transport_cost, 2),
        accommodation_cost=round(accommodation_cost, 2),
        activities_cost=round(activities_cost, 2),
        food_estimate=round(food_estimate, 2),
        miscellaneous=round(miscellaneous, 2),
        total=round(total, 2),
        budget_limit=max(0.0, intent.budget),
        currency=currency,
    )


def _trip_nights(start_date: str, end_date: str) -> int:
    return max(1, (date.fromisoformat(end_date) - date.fromisoformat(start_date)).days)


def _missing_sources(
    flights: list[FlightOption],
    hotels: list[HotelOption],
    insights: list[LocalInsight],
) -> list[str]:
    missing: list[str] = []
    if not flights:
        missing.append("flight options")
    if not hotels:
        missing.append("hotel options")
    if not insights:
        missing.append("local insights")
    return missing


__all__ = [
    "ConstraintAgent",
    "constraint_node",
]
