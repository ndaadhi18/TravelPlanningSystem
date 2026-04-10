"""
Constraint Agent node implementation.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Mapping, Optional, TypeVar

from pydantic import BaseModel, ValidationError

from backend.agents.base_agent import AgentExecutionError, BaseAgent, wrap_agent_error
from backend.agents.constraint_agent.prompts import (
    CONSTRAINT_SYSTEM_PROMPT,
    build_constraint_clarification,
    build_constraint_warnings,
)
from backend.schemas.accommodation import HotelOption
from backend.schemas.itinerary import BudgetSummary, DayPlan, Itinerary, LocalInsight
from backend.schemas.transport import FlightOption
from backend.schemas.travel_intent import TravelIntent
from backend.utils.logger import get_logger

logger = get_logger("agents.constraint")
TModel = TypeVar("TModel", bound=BaseModel)


class ConstraintAgent(BaseAgent):
    """Validate constraints and assemble itinerary + budget summary."""

    def __init__(self, *, llm: Optional[Any] = None):
        super().__init__("constraint_agent", llm=llm)

    async def run(self, state: Mapping[str, Any]) -> dict[str, Any]:
        intent = _normalize_intent(state.get("travel_intent"))
        if intent is None:
            clarification = build_constraint_clarification(
                ["destination", "trip start date", "trip end date or duration"]
            )
            return {
                "messages": [clarification],
                "current_phase": "planning",
            }

        missing_fields = _missing_core_fields(intent)
        if missing_fields:
            clarification = build_constraint_clarification(missing_fields)
            return {
                "messages": [clarification],
                "current_phase": "planning",
            }

        flights = _normalize_model_list(state.get("flight_options"), FlightOption)
        hotels = _normalize_model_list(state.get("hotel_options"), HotelOption)
        insights = _normalize_model_list(state.get("local_insights"), LocalInsight)

        try:
            itinerary = self._assemble_itinerary(intent, flights, hotels, insights, state)

            nights = _trip_nights(itinerary.start_date, itinerary.end_date)
            budget_summary = _compute_budget_summary(
                intent=intent,
                flights=flights,
                hotels=hotels,
                insights=insights,
                nights=nights,
            )

            missing_sources = _missing_sources(flights, hotels, insights)
            warnings = build_constraint_warnings(
                missing_sources=missing_sources,
                over_budget=bool(
                    budget_summary.budget_limit > 0
                    and budget_summary.total > budget_summary.budget_limit
                ),
            )

            itinerary.total_estimated_cost = budget_summary.total
            itinerary.budget_summary = budget_summary
            itinerary.warnings = _merge_unique(itinerary.warnings, warnings)
            if not itinerary.highlights:
                itinerary.highlights = [i.name for i in insights[:3]]

            return {
                "itinerary": itinerary,
                "budget_summary": budget_summary,
                "current_phase": "feedback",
            }
        except Exception as error:
            wrapped = wrap_agent_error(
                "constraint_agent",
                "run",
                error,
                context={"current_phase": state.get("current_phase", "itinerary")},
            )
            return {
                "errors": [wrapped.message],
                "messages": [
                    "I could not assemble your itinerary right now. "
                    "Please confirm your destination, dates, and budget, then I will retry."
                ],
                "current_phase": "planning",
            }

    def _assemble_itinerary(
        self,
        intent: TravelIntent,
        flights: list[FlightOption],
        hotels: list[HotelOption],
        insights: list[LocalInsight],
        state: Mapping[str, Any],
    ) -> Itinerary:
        if self._llm is not None:
            messages = self.build_messages(
                CONSTRAINT_SYSTEM_PROMPT,
                state={
                    "travel_intent": intent.model_dump(mode="json"),
                    "flight_options": [f.model_dump(mode="json") for f in flights],
                    "hotel_options": [h.model_dump(mode="json") for h in hotels],
                    "local_insights": [i.model_dump(mode="json") for i in insights],
                },
                user_input=_extract_latest_user_text(state),
            )
            try:
                llm_itinerary = self.invoke_structured(messages, Itinerary)
                return _coerce_itinerary(llm_itinerary, intent, flights, hotels, insights)
            except AgentExecutionError:
                logger.warning("LLM itinerary assembly failed; using deterministic fallback.")

        return _build_deterministic_itinerary(intent, flights, hotels, insights)


async def constraint_node(state: Mapping[str, Any], *, llm: Optional[Any] = None) -> dict[str, Any]:
    """LangGraph-compatible constraint node entrypoint."""
    agent = ConstraintAgent(llm=llm)
    return await agent.run(state)


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


def _build_deterministic_itinerary(
    intent: TravelIntent,
    flights: list[FlightOption],
    hotels: list[HotelOption],
    insights: list[LocalInsight],
) -> Itinerary:
    start_date, end_date, trip_days = _resolve_trip_window(intent)
    day_plans = _build_day_plans(
        start_date=start_date,
        trip_days=trip_days,
        travelers=max(1, intent.num_travelers),
        flight=flights[0] if flights else None,
        hotel=hotels[0] if hotels else None,
        insights=insights,
    )

    return Itinerary(
        title=_build_itinerary_title(intent.destination or "Trip"),
        destination=intent.destination or "Unknown Destination",
        source_location=intent.source_location,
        start_date=start_date,
        end_date=end_date,
        num_travelers=max(1, intent.num_travelers),
        days=day_plans,
        total_estimated_cost=0.0,
        highlights=[i.name for i in insights[:3]],
        warnings=[],
    )


def _coerce_itinerary(
    itinerary: Itinerary,
    intent: TravelIntent,
    flights: list[FlightOption],
    hotels: list[HotelOption],
    insights: list[LocalInsight],
) -> Itinerary:
    start_date, end_date, trip_days = _resolve_trip_window(intent)
    itinerary.destination = intent.destination or itinerary.destination
    itinerary.source_location = intent.source_location
    itinerary.start_date = start_date
    itinerary.end_date = end_date
    itinerary.num_travelers = max(1, intent.num_travelers)
    if not itinerary.days:
        itinerary.days = _build_day_plans(
            start_date=start_date,
            trip_days=trip_days,
            travelers=itinerary.num_travelers,
            flight=flights[0] if flights else None,
            hotel=hotels[0] if hotels else None,
            insights=insights,
        )
    return itinerary


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


def _build_day_plans(
    *,
    start_date: str,
    trip_days: int,
    travelers: int,
    flight: Optional[FlightOption],
    hotel: Optional[HotelOption],
    insights: list[LocalInsight],
) -> list[DayPlan]:
    start = date.fromisoformat(start_date)
    plans: list[DayPlan] = []

    for day_idx in range(trip_days):
        current_date = (start + timedelta(days=day_idx)).isoformat()
        day_activities = insights[day_idx::trip_days][:3]
        activities_cost = sum(i.estimated_cost or 0.0 for i in day_activities)
        hotel_cost = hotel.price_per_night if hotel else 0.0
        food_misc_estimate = 45.0 * travelers
        day_cost = activities_cost + hotel_cost + food_misc_estimate

        plans.append(
            DayPlan(
                day_number=day_idx + 1,
                date=current_date,
                title=f"Day {day_idx + 1} in destination",
                activities=day_activities,
                transport=flight if day_idx == 0 else None,
                hotel=hotel,
                notes=None,
                estimated_day_cost=round(day_cost, 2),
            )
        )

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
        primary_hotel = hotels[0]
        if primary_hotel.total_price is not None:
            accommodation_cost = primary_hotel.total_price
        else:
            accommodation_cost = primary_hotel.price_per_night * max(1, nights)

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
    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    return max(1, (end - start).days)


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


def _build_itinerary_title(destination: str) -> str:
    return f"Personalized trip to {destination}"


def _merge_unique(existing: list[str], incoming: list[str]) -> list[str]:
    merged = list(existing)
    for item in incoming:
        if item not in merged:
            merged.append(item)
    return merged


def _extract_latest_user_text(state: Mapping[str, Any]) -> str:
    messages = state.get("messages")
    if isinstance(messages, list) and messages:
        candidate = messages[-1]
        if isinstance(candidate, str):
            return candidate.strip()
        if isinstance(candidate, dict):
            content = candidate.get("content")
            if isinstance(content, str):
                return content.strip()
        content = getattr(candidate, "content", None)
        if isinstance(content, str):
            return content.strip()
    return ""


__all__ = [
    "ConstraintAgent",
    "constraint_node",
]
