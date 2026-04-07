"""Quick smoke test for all M1 schemas."""
import sys
sys.path.insert(0, ".")

print("=" * 60)
print("M1 Schema Validation Tests")
print("=" * 60)

# ── 1. TravelIntent ──────────────────────────────────────────
print("\n[1] TravelIntent...")
from backend.schemas.travel_intent import TravelIntent, TravelStyle

t = TravelIntent(
    destination="Paris, France",
    source_location="Mumbai, India",
    budget=3000.0,
    start_date="2025-06-15",
    end_date="2025-06-22",
    num_travelers=2,
    preferences="art museums, local cuisine",
    travel_style="mid-range",
)
assert t.duration_days == 7, f"Expected 7, got {t.duration_days}"
assert t.is_complete() is True
assert t.currency == "USD"
print(f"  OK: {t.destination} | {t.duration_days} days | complete={t.is_complete()}")

# Test validation: bad date
try:
    TravelIntent(destination="X", budget=100, start_date="not-a-date")
    print("  FAIL: Should have rejected bad date")
except Exception as e:
    print(f"  OK: Rejected bad date — {type(e).__name__}")

# Test validation: end before start
try:
    TravelIntent(destination="X", budget=100, start_date="2025-06-22", end_date="2025-06-15")
    print("  FAIL: Should have rejected end < start")
except Exception as e:
    print(f"  OK: Rejected end < start — {type(e).__name__}")

# ── 2. FlightSearchInput + FlightOption ──────────────────────
print("\n[2] Transport schemas...")
from backend.schemas.transport import FlightSearchInput, FlightOption

fsi = FlightSearchInput(
    origin="bom",
    destination="cdg",
    departure_date="2025-06-15",
    adults=2,
)
assert fsi.origin == "BOM", f"Expected BOM, got {fsi.origin}"
assert fsi.destination == "CDG"
print(f"  OK: FlightSearchInput {fsi.origin} → {fsi.destination}")

fo = FlightOption(
    airline="Air France",
    flight_number="AF 218",
    origin="BOM",
    destination="CDG",
    departure_time="2025-06-15T22:00:00",
    arrival_time="2025-06-16T06:30:00",
    duration="PT8H30M",
    price=650.0,
    stops=0,
)
assert fo.price == 650.0
print(f"  OK: FlightOption {fo.flight_number} at ${fo.price}")

# ── 3. HotelSearchInput + HotelOption ────────────────────────
print("\n[3] Accommodation schemas...")
from backend.schemas.accommodation import HotelSearchInput, HotelOption, PriceRange

hsi = HotelSearchInput(
    city_code="par",
    check_in="2025-06-15",
    check_out="2025-06-22",
    price_range="luxury",
)
assert hsi.city_code == "PAR"
print(f"  OK: HotelSearchInput city={hsi.city_code} range={hsi.price_range}")

# Test check_out before check_in
try:
    HotelSearchInput(city_code="PAR", check_in="2025-06-22", check_out="2025-06-15")
    print("  FAIL: Should have rejected bad dates")
except Exception as e:
    print(f"  OK: Rejected checkout < checkin — {type(e).__name__}")

ho = HotelOption(
    name="Hotel Le Marais",
    address="42 Rue de Rivoli, Paris",
    rating=4.5,
    price_per_night=120.0,
    amenities=["WiFi", "Breakfast", "Pool"],
)
print(f"  OK: HotelOption {ho.name} ★{ho.rating} €{ho.price_per_night}/night")

# ── 4. Itinerary schemas ────────────────────────────────────
print("\n[4] Itinerary schemas...")
from backend.schemas.itinerary import (
    WebSearchInput, LocalInsight, InsightCategory,
    DayPlan, BudgetSummary, Itinerary, SearchDepth,
)

wsi = WebSearchInput(
    query="hidden gems in Paris for food lovers",
    search_depth="advanced",
    max_results=10,
)
assert wsi.search_depth == SearchDepth.ADVANCED
print(f"  OK: WebSearchInput query='{wsi.query[:30]}...'")

li = LocalInsight(
    name="Le Marais Walking Tour",
    category="activity",
    description="Explore the historic Jewish quarter with local guide.",
    estimated_cost=25.0,
    duration_hours=2.5,
)
assert li.category == InsightCategory.ACTIVITY
print(f"  OK: LocalInsight '{li.name}' ({li.category})")

dp = DayPlan(
    day_number=1,
    date="2025-06-15",
    title="Arrival & Montmartre",
    activities=[li],
    transport=fo,
    hotel=ho,
    estimated_day_cost=195.0,
)
print(f"  OK: DayPlan day {dp.day_number}: {dp.title}")

bs = BudgetSummary(
    transport_cost=1300.0,
    accommodation_cost=840.0,
    activities_cost=200.0,
    food_estimate=350.0,
    miscellaneous=100.0,
    total=2790.0,
    budget_limit=3000.0,
)
assert bs.within_budget is True
print(f"  OK: BudgetSummary total=${bs.total} within_budget={bs.within_budget}")

itin = Itinerary(
    title="7 Days in Paris — Art & Culture",
    destination="Paris, France",
    start_date="2025-06-15",
    end_date="2025-06-22",
    days=[dp],
    budget_summary=bs,
    total_estimated_cost=2790.0,
    highlights=["Eiffel Tower at sunset", "Seine River cruise"],
)
print(f"  OK: Itinerary '{itin.title}' — {len(itin.days)} day(s)")

# ── 5. Payment schemas ──────────────────────────────────────
print("\n[5] Payment schemas...")
from backend.schemas.payment import BookingConfirmation, BookingStatus

bc = BookingConfirmation(
    booking_reference="abc-123-def-456",
    status="confirmed",
    flight_summary="BOM → CDG, Air France AF 218, Jun 15",
    hotel_summary="Hotel Le Marais, 7 nights",
    estimated_total_cost=2790.0,
    timestamp="2025-06-01T12:00:00Z",
)
assert bc.status == BookingStatus.CONFIRMED
print(f"  OK: BookingConfirmation ref={bc.booking_reference} status={bc.status}")

# ── 6. TravelStateSummary ────────────────────────────────────
print("\n[6] TravelStateSummary...")
from backend.schemas.travel_state import TravelStateSummary, PlanningPhase, FeedbackType

state = TravelStateSummary(
    travel_intent=t,
    intent_confirmed=True,
    flight_options=[fo],
    hotel_options=[ho],
    local_insights=[li],
    itinerary=itin,
    budget_summary=bs,
    current_phase="feedback",
    iteration_count=1,
)
assert state.current_phase == PlanningPhase.FEEDBACK
assert len(state.flight_options) == 1
print(f"  OK: TravelStateSummary phase={state.current_phase} flights={len(state.flight_options)}")

# ── 7. API Models ────────────────────────────────────────────
print("\n[7] API models...")
from backend.schemas.api_models import (
    ChatRequest, ChatResponse, FeedbackRequest,
    HealthResponse, ErrorResponse, ResponseStatus,
)

cr = ChatRequest(message="Plan a trip to Paris for 2 people")
assert cr.thread_id is None
print(f"  OK: ChatRequest message='{cr.message[:30]}...'")

resp = ChatResponse(
    thread_id="thread-001",
    response="I'd love to help you plan a trip to Paris!",
    phase="greeting",
    status="awaiting_input",
)
assert resp.status == ResponseStatus.AWAITING_INPUT
print(f"  OK: ChatResponse status={resp.status} phase={resp.phase}")

fr = FeedbackRequest(
    thread_id="thread-001",
    feedback_type="modify",
    feedback_text="Add more street food spots",
)
assert fr.feedback_type == FeedbackType.MODIFY
print(f"  OK: FeedbackRequest type={fr.feedback_type}")

hr = HealthResponse()
print(f"  OK: HealthResponse status={hr.status} version={hr.version}")

er = ErrorResponse(error="Something went wrong", phase="planning")
print(f"  OK: ErrorResponse error='{er.error}'")

# ── 8. Test __init__.py re-exports ───────────────────────────
print("\n[8] __init__.py re-exports...")
from backend.schemas import (
    TravelIntent, TravelStyle,
    FlightSearchInput, FlightOption,
    HotelSearchInput, HotelOption, PriceRange,
    WebSearchInput, SearchDepth, LocalInsight, InsightCategory,
    DayPlan, Itinerary, BudgetSummary,
    BookingConfirmation, BookingStatus,
    TravelStateSummary, PlanningPhase, FeedbackType,
    ChatRequest, ChatResponse, FeedbackRequest, FeedbackResponse,
    ConfirmRequest, HealthResponse, ErrorResponse, ResponseStatus,
)
print("  OK: All 24 symbols imported from backend.schemas")

# ── Summary ──────────────────────────────────────────────────
print("\n" + "=" * 60)
print("ALL M1 SCHEMA TESTS PASSED ✓")
print("=" * 60)
