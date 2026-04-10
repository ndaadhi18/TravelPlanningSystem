"""
Payment Agent node implementation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, Optional, TypeVar
from uuid import uuid4

from pydantic import BaseModel, ValidationError

from backend.agents.base_agent import AgentExecutionError, BaseAgent, wrap_agent_error
from backend.agents.payment_agent.prompts import (
    PAYMENT_SYSTEM_PROMPT,
    build_payment_clarification,
)
from backend.schemas.accommodation import HotelOption
from backend.schemas.itinerary import BudgetSummary, Itinerary
from backend.schemas.payment import BookingConfirmation, BookingStatus
from backend.schemas.transport import FlightOption
from backend.schemas.travel_intent import TravelIntent
from backend.utils.logger import get_logger

logger = get_logger("agents.payment")
TModel = TypeVar("TModel", bound=BaseModel)


class PaymentAgent(BaseAgent):
    """Generate a simulated booking confirmation and complete the workflow."""

    def __init__(self, *, llm: Optional[Any] = None):
        super().__init__("payment_agent", llm=llm)

    async def run(self, state: Mapping[str, Any]) -> dict[str, Any]:
        intent = _normalize_model(state.get("travel_intent"), TravelIntent)
        itinerary = _normalize_model(state.get("itinerary"), Itinerary)
        budget_summary = _normalize_model(state.get("budget_summary"), BudgetSummary)
        flights = _normalize_model_list(state.get("flight_options"), FlightOption)
        hotels = _normalize_model_list(state.get("hotel_options"), HotelOption)

        if itinerary is None:
            clarification = build_payment_clarification(["approved itinerary"])
            return {
                "messages": [clarification],
                "current_phase": "feedback",
            }

        try:
            confirmation = self._build_booking_confirmation(
                intent=intent,
                itinerary=itinerary,
                budget_summary=budget_summary,
                flights=flights,
                hotels=hotels,
                state=state,
            )
            return {
                "booking_confirmation": confirmation,
                "current_phase": "complete",
            }
        except Exception as error:
            wrapped = wrap_agent_error(
                "payment_agent",
                "run",
                error,
                context={"current_phase": state.get("current_phase", "payment")},
            )
            return {
                "errors": [wrapped.message],
                "messages": [
                    "I could not finalize your booking confirmation right now. "
                    "Please confirm your itinerary details and try again."
                ],
                "current_phase": "feedback",
            }

    def _build_booking_confirmation(
        self,
        *,
        intent: Optional[TravelIntent],
        itinerary: Itinerary,
        budget_summary: Optional[BudgetSummary],
        flights: list[FlightOption],
        hotels: list[HotelOption],
        state: Mapping[str, Any],
    ) -> BookingConfirmation:
        selected_flight = flights[0] if flights else _extract_first_day_flight(itinerary)
        selected_hotel = hotels[0] if hotels else _extract_first_day_hotel(itinerary)

        nights = _trip_nights(itinerary.start_date, itinerary.end_date)
        flight_cost = selected_flight.price if selected_flight else 0.0
        hotel_cost = _hotel_cost(selected_hotel, nights)

        currency = _resolve_currency(
            budget_summary=budget_summary,
            intent=intent,
            flight=selected_flight,
            hotel=selected_hotel,
        )
        total_cost = _resolve_total_cost(
            budget_summary=budget_summary,
            itinerary=itinerary,
            flight_cost=flight_cost,
            hotel_cost=hotel_cost,
        )

        flight_summary = _build_flight_summary(selected_flight)
        hotel_summary = _build_hotel_summary(selected_hotel, nights)
        itinerary_summary = _build_itinerary_summary(itinerary)
        confirmation_message = self._build_confirmation_message(
            itinerary=itinerary,
            total_cost=total_cost,
            currency=currency,
            state=state,
        )

        return BookingConfirmation(
            booking_reference=str(uuid4()),
            status=BookingStatus.CONFIRMED,
            flight_summary=flight_summary,
            hotel_summary=hotel_summary,
            itinerary_summary=itinerary_summary,
            flight_cost=round(flight_cost, 2),
            hotel_cost=round(hotel_cost, 2),
            estimated_total_cost=round(total_cost, 2),
            currency=currency,
            num_travelers=max(1, itinerary.num_travelers),
            destination=itinerary.destination,
            start_date=itinerary.start_date,
            end_date=itinerary.end_date,
            timestamp=datetime.now(timezone.utc).isoformat(),
            confirmation_message=confirmation_message,
        )

    def _build_confirmation_message(
        self,
        *,
        itinerary: Itinerary,
        total_cost: float,
        currency: str,
        state: Mapping[str, Any],
    ) -> str:
        if self._llm is not None:
            messages = self.build_messages(
                PAYMENT_SYSTEM_PROMPT,
                state={
                    "destination": itinerary.destination,
                    "start_date": itinerary.start_date,
                    "end_date": itinerary.end_date,
                    "num_travelers": itinerary.num_travelers,
                    "total_estimated_cost": total_cost,
                    "currency": currency,
                },
                user_input=_extract_latest_user_text(state),
            )
            try:
                llm_response = self.invoke(messages)
                text = _to_text(llm_response).strip()
                if text:
                    return text
            except AgentExecutionError:
                logger.warning("LLM payment summary generation failed; using fallback text.")

        return (
            f"Your mock booking is confirmed for {itinerary.destination} "
            f"from {itinerary.start_date} to {itinerary.end_date}. "
            f"Estimated total: {total_cost:.2f} {currency}."
        )


async def payment_node(state: Mapping[str, Any], *, llm: Optional[Any] = None) -> dict[str, Any]:
    """LangGraph-compatible payment node entrypoint."""
    agent = PaymentAgent(llm=llm)
    return await agent.run(state)


def _normalize_model(raw: Any, model_cls: type[TModel]) -> Optional[TModel]:
    if raw is None:
        return None
    if isinstance(raw, model_cls):
        return raw
    if isinstance(raw, Mapping):
        try:
            return model_cls.model_validate(raw)
        except ValidationError:
            return None
    return None


def _normalize_model_list(raw: Any, model_cls: type[TModel]) -> list[TModel]:
    if not isinstance(raw, list):
        return []
    parsed: list[TModel] = []
    for item in raw:
        normalized = _normalize_model(item, model_cls)
        if normalized is not None:
            parsed.append(normalized)
    return parsed


def _extract_first_day_flight(itinerary: Itinerary) -> Optional[FlightOption]:
    for day in itinerary.days:
        if day.transport is not None:
            return day.transport
    return None


def _extract_first_day_hotel(itinerary: Itinerary) -> Optional[HotelOption]:
    for day in itinerary.days:
        if day.hotel is not None:
            return day.hotel
    return None


def _hotel_cost(hotel: Optional[HotelOption], nights: int) -> float:
    if hotel is None:
        return 0.0
    if hotel.total_price is not None:
        return hotel.total_price
    return hotel.price_per_night * max(1, nights)


def _trip_nights(start_date: Optional[str], end_date: Optional[str]) -> int:
    if not start_date or not end_date:
        return 1
    try:
        start = datetime.fromisoformat(start_date).date()
        end = datetime.fromisoformat(end_date).date()
    except ValueError:
        return 1
    return max(1, (end - start).days)


def _resolve_currency(
    *,
    budget_summary: Optional[BudgetSummary],
    intent: Optional[TravelIntent],
    flight: Optional[FlightOption],
    hotel: Optional[HotelOption],
) -> str:
    return (
        (budget_summary.currency if budget_summary else None)
        or (intent.currency if intent else None)
        or (flight.currency if flight else None)
        or (hotel.currency if hotel else None)
        or "USD"
    )


def _resolve_total_cost(
    *,
    budget_summary: Optional[BudgetSummary],
    itinerary: Itinerary,
    flight_cost: float,
    hotel_cost: float,
) -> float:
    if budget_summary and budget_summary.total > 0:
        return budget_summary.total
    if itinerary.total_estimated_cost > 0:
        return itinerary.total_estimated_cost
    return flight_cost + hotel_cost


def _build_flight_summary(flight: Optional[FlightOption]) -> str:
    if flight is None:
        return "Flight details are not available in this draft."
    return (
        f"{flight.origin} -> {flight.destination}, {flight.airline} {flight.flight_number}, "
        f"departure {flight.departure_time}, arrival {flight.arrival_time}, "
        f"{flight.price:.2f} {flight.currency}."
    )


def _build_hotel_summary(hotel: Optional[HotelOption], nights: int) -> str:
    if hotel is None:
        return "Hotel details are not available in this draft."
    if hotel.total_price is not None:
        total_text = f"{hotel.total_price:.2f} {hotel.currency} total"
    else:
        total_text = f"{hotel.price_per_night:.2f} {hotel.currency} per night"
    return (
        f"{hotel.name}, {nights} nights, {total_text}."
    )


def _build_itinerary_summary(itinerary: Itinerary) -> str:
    total_days = len(itinerary.days)
    highlights = ", ".join(itinerary.highlights[:3]) if itinerary.highlights else "custom highlights"
    return (
        f"{total_days} day plan for {itinerary.destination} from {itinerary.start_date} to "
        f"{itinerary.end_date}, including {highlights}."
    )


def _extract_latest_user_text(state: Mapping[str, Any]) -> str:
    messages = state.get("messages")
    if isinstance(messages, list) and messages:
        candidate = messages[-1]
        if isinstance(candidate, str):
            return candidate.strip()
        if isinstance(candidate, Mapping):
            content = candidate.get("content")
            if isinstance(content, str):
                return content.strip()
        content = getattr(candidate, "content", None)
        if isinstance(content, str):
            return content.strip()
    return ""


def _to_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, Mapping):
        for key in ("content", "text", "message"):
            text = value.get(key)
            if isinstance(text, str):
                return text
        return str(value)
    content = getattr(value, "content", None)
    if isinstance(content, str):
        return content
    return str(value)


__all__ = [
    "PaymentAgent",
    "payment_node",
]
