# PLANIT — Implementation Plan

> MCP-Orchestrated Multi-Agent Travel Planning System

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Technology Stack — Final Decisions](#2-technology-stack--final-decisions)
3. [Dependency Manifest](#3-dependency-manifest)
4. [Project Folder Structure](#4-project-folder-structure)
5. [Core Data Models](#5-core-data-models)
6. [MCP Server Design](#6-mcp-server-design)
7. [Agent Architecture](#7-agent-architecture)
8. [LangGraph Orchestration](#8-langgraph-orchestration)
9. [FastAPI Backend](#9-fastapi-backend)
10. [Frontend Architecture](#10-frontend-architecture)
11. [Module Build Order](#11-module-build-order)
12. [Testing Strategy](#12-testing-strategy)
13. [Environment & Configuration](#13-environment--configuration)
14. [Risks & Mitigations](#14-risks--mitigations)

---

## 1. Architecture Overview

### 1.1 System Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         FRONTEND (Next.js)                         │
│  TailwindCSS · ShadCN UI · Framer Motion · Chat Interface          │
└──────────────────────────────┬──────────────────────────────────────┘
                               │  REST / WebSocket
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      FASTAPI BACKEND (Python)                      │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                  LangGraph Orchestrator                       │   │
│  │                                                               │   │
│  │   ┌─────────┐   ┌──────────┐   ┌───────────┐                │   │
│  │   │Greeting │──▶│ Planning │──▶│ Transport │                │   │
│  │   │ Agent   │   │  Agent   │   │   Agent   │                │   │
│  │   └─────────┘   └────┬─────┘   └─────┬─────┘                │   │
│  │                      │               │                        │   │
│  │              ┌───────▼───────┐  ┌────▼──────┐                │   │
│  │              │Accommodation │  │Local Expert│                │   │
│  │              │    Agent     │  │   Agent    │                │   │
│  │              └───────┬───────┘  └────┬──────┘                │   │
│  │                      │               │                        │   │
│  │              ┌───────▼───────────────▼──────┐                │   │
│  │              │  Constraint / Itinerary Agent │                │   │
│  │              └──────────────┬────────────────┘                │   │
│  │                             │                                 │   │
│  │                    ┌────────▼────────┐                        │   │
│  │                    │  Payment Agent  │                        │   │
│  │                    └─────────────────┘                        │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                               │                                     │
│                    MCP Client (httpx)                                │
└───────────────────────────────┬─────────────────────────────────────┘
                                │  Structured JSON over HTTP
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    SINGLE MCP SERVER (FastMCP)                      │
│                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────┐         │
│  │search_flights│  │search_hotels │  │web_search_places  │         │
│  │  (Amadeus)   │  │  (Amadeus)   │  │    (Tavily)       │         │
│  └──────┬───────┘  └──────┬───────┘  └────────┬──────────┘         │
└─────────┼─────────────────┼────────────────────┼────────────────────┘
          │                 │                    │
          ▼                 ▼                    ▼
   Amadeus Flight     Amadeus Hotel       Tavily Search
       API                API                 API
```

### 1.2 Core Design Principles

| Principle | Description |
|---|---|
| **Agent ≠ API caller** | Agents reason with LLM. They _never_ call external APIs directly. All data flows through MCP tools. |
| **Single MCP Server** | One FastMCP process exposes all three tools (`search_flights`, `search_hotels`, `web_search_places`). Simple to deploy and manage. |
| **Structured State** | LangGraph's `TypedDict` state is the single source of truth shared across all agents. Pydantic models validate every boundary. |
| **Modular Build** | Each module is built, tested, and verified independently before integrating the next. |
| **Feedback Loop** | After itinerary generation, the user can iterate. The Planning Agent re-computes only affected parts. |

---

## 2. Technology Stack — Final Decisions

### 2.1 Backend

| Component | Choice | Rationale |
|---|---|---|
| **Language** | Python 3.12 | Required by project env. `uv` is already configured. |
| **Package Manager** | uv | Already initialized in `.venv`. Fast resolver, lockfile support. |
| **Web Framework** | FastAPI | Async-native, Pydantic-first, WebSocket support for streaming. |
| **ASGI Server** | Uvicorn | Standard for FastAPI. Hot-reload in dev. |
| **Agent Orchestration** | LangGraph | Graph-based agent workflow. Explicit state, conditional routing, human-in-the-loop support, checkpointing. |
| **LLM Interface** | LangChain ChatGroq | Ultra-fast inference via Groq. `langchain-groq` provides `bind_tools()` for native tool calling. Fallback: `langchain-google-genai` (Gemini). |
| **MCP Protocol** | FastMCP (Python SDK) | Official MCP Python SDK. `@mcp.tool` decorator, Pydantic input models, async-first. Runs as a standalone process. |
| **Data Validation** | Pydantic v2 | `BaseModel`, `Field`, `field_validator`. Used everywhere: state, schemas, MCP I/O, API request/response. |
| **HTTP Client** | httpx | Async HTTP client. Used by MCP server for external API calls and by the backend for MCP client communication. |
| **Web Scraping** | BeautifulSoup4 + requests | Backup for web search if Tavily is unavailable. |
| **Env Management** | python-dotenv | `.env` file loading for API keys. |

### 2.2 External APIs

| API | Package | Purpose |
|---|---|---|
| **Amadeus (Flights)** | `amadeus` (official SDK) | Flight search via `shopping.flight_offers_search` |
| **Amadeus (Hotels)** | `amadeus` (official SDK) | Hotel search via `reference_data.locations.hotels.by_city` and `shopping.hotel_offers_search` |
| **Tavily Search** | `tavily-python` | Discovering local attractions, hidden gems, cultural insights |
| **Groq LLM** | `langchain-groq` + `groq` | Primary LLM for all agent reasoning. Models: `llama-3.3-70b-versatile` or `mixtral-8x7b-32768`. |

### 2.3 Frontend

| Component | Choice | Rationale |
|---|---|---|
| **Framework** | Next.js 14+ (App Router) | SSR, API routes, file-based routing. |
| **Styling** | TailwindCSS v3 | Utility-first, rapid prototyping. |
| **Components** | ShadCN UI | Accessible, composable, Radix-based components. |
| **Animations** | Framer Motion | Layout animations, page transitions, micro-interactions. |
| **State** | React Context + `useState` / `useReducer` | Simple enough for chat-based UI. No heavy state library needed. |
| **HTTP Client** | `fetch` / `axios` | REST for initial request. WebSocket for streaming agent responses. |

### 2.4 DevOps (Future — not in initial build)

| Component | Choice |
|---|---|
| Containerization | Docker + docker-compose |
| CI/CD | GitHub Actions |
| Deployment | Vercel (frontend) + Railway/Render (backend) |

---

## 3. Dependency Manifest

### 3.1 Updated `requirements.txt` (Backend)

The current `requirements.txt` needs to be updated. Here is the full dependency list with rationale:

```
# === Web Framework ===
fastapi                    # API server
uvicorn[standard]          # ASGI server with hot-reload

# === Data Validation ===
pydantic>=2.0              # Structured data models everywhere
pydantic-settings          # Settings management from .env

# === LLM & Agent Orchestration ===
langchain                  # Core LangChain framework
langchain-groq             # ChatGroq — primary LLM provider
langchain-core             # Base abstractions (tools, messages)
langgraph                  # Agent orchestration graphs

# === MCP Protocol ===
fastmcp                    # FastMCP server SDK

# === External API SDKs ===
amadeus                    # Amadeus flight + hotel API SDK
tavily-python              # Tavily web search API

# === HTTP & Networking ===
httpx                      # Async HTTP client (MCP communication, API fallbacks)
requests                   # Sync HTTP (backup/utility)
beautifulsoup4             # HTML parsing for web scraping fallback

# === Environment ===
python-dotenv              # .env file loading

# === Testing ===
pytest                     # Test runner
pytest-asyncio             # Async test support
httpx                      # Already listed — also used for TestClient
```

**Changes from current `requirements.txt`:**
- **Added**: `amadeus`, `langchain-groq`, `langchain-core`, `pydantic-settings`, `pytest`, `pytest-asyncio`
- **Removed**: `groq` (replaced by `langchain-groq` which includes it)
- **Kept**: Everything else

### 3.2 Frontend `package.json` Dependencies (created during Module 10)

```
next, react, react-dom
tailwindcss, postcss, autoprefixer
@shadcn/ui (via npx shadcn-ui init)
framer-motion
axios (or native fetch)
lucide-react (icons)
```

---

## 4. Project Folder Structure

```
itinerai-core/
│
├── .env                          # API keys (NEVER committed)
├── .env.example                  # Template with placeholder keys
├── .gitignore
├── requirements.txt              # Updated Python dependencies
├── pyproject.toml                # uv project config (if needed)
├── PROJECT_CONTEXT.md            # Existing context document
├── IMPLEMENTATION.md             # This file
│
├── backend/
│   ├── __init__.py
│   ├── main.py                   # FastAPI app entry point
│   │
│   ├── api/                      # FastAPI route handlers
│   │   ├── __init__.py
│   │   ├── routes.py             # REST endpoints (/chat, /itinerary, /feedback)
│   │   └── websocket.py          # WebSocket endpoint for streaming
│   │
│   ├── core/                     # Application core (startup, config)
│   │   ├── __init__.py
│   │   ├── settings.py           # Pydantic Settings (loads .env)
│   │   └── dependencies.py       # FastAPI dependency injection
│   │
│   ├── schemas/                  # Pydantic models (request/response + state)
│   │   ├── __init__.py
│   │   ├── travel_intent.py      # TravelIntent model
│   │   ├── travel_state.py       # TravelState (LangGraph state)
│   │   ├── transport.py          # FlightOption, TransportSearchParams
│   │   ├── accommodation.py      # HotelOption, AccommodationSearchParams
│   │   ├── itinerary.py          # DayPlan, Itinerary, BudgetSummary
│   │   ├── payment.py            # BookingConfirmation, PaymentSummary
│   │   └── api_models.py         # API request/response wrappers
│   │
│   ├── agents/                   # LangGraph agent nodes
│   │   ├── __init__.py
│   │   ├── base_agent.py         # Shared agent utilities (prompt builder, error handling)
│   │   ├── greeting_agent/
│   │   │   ├── __init__.py
│   │   │   ├── agent.py          # Greeting node function
│   │   │   └── prompts.py        # System prompt for intent extraction
│   │   ├── planning_agent/
│   │   │   ├── __init__.py
│   │   │   ├── agent.py          # Planning/routing node function
│   │   │   └── prompts.py
│   │   ├── transport_agent/
│   │   │   ├── __init__.py
│   │   │   ├── agent.py          # Transport node (calls search_flights via MCP)
│   │   │   └── prompts.py
│   │   ├── accommodation_agent/
│   │   │   ├── __init__.py
│   │   │   ├── agent.py          # Accommodation node (calls search_hotels via MCP)
│   │   │   └── prompts.py
│   │   ├── local_expert_agent/
│   │   │   ├── __init__.py
│   │   │   ├── agent.py          # Local expert node (calls web_search_places via MCP)
│   │   │   └── prompts.py
│   │   ├── constraint_agent/
│   │   │   ├── __init__.py
│   │   │   ├── agent.py          # Constraint validation + itinerary assembly
│   │   │   └── prompts.py
│   │   └── payment_agent/
│   │       ├── __init__.py
│   │       ├── agent.py          # Simulated booking confirmation
│   │       └── prompts.py
│   │
│   ├── orchestration/            # LangGraph graph definitions
│   │   ├── __init__.py
│   │   ├── graph.py              # Main StateGraph definition (nodes, edges, compile)
│   │   ├── state.py              # TravelState TypedDict with reducers
│   │   └── router.py             # Conditional edge functions
│   │
│   ├── mcp_servers/              # The single MCP server (run as separate process)
│   │   ├── __init__.py
│   │   ├── server.py             # FastMCP("planit_mcp") — registers all 3 tools
│   │   ├── tools/
│   │   │   ├── __init__.py
│   │   │   ├── search_flights.py     # Amadeus flight search tool
│   │   │   ├── search_hotels.py      # Amadeus hotel search tool
│   │   │   └── web_search_places.py  # Tavily web search tool
│   │   └── utils/
│   │       ├── __init__.py
│   │       ├── amadeus_client.py     # Shared Amadeus API client
│   │       └── error_handler.py      # MCP error formatting
│   │
│   ├── services/                 # Business logic layer (between API and agents)
│   │   ├── __init__.py
│   │   ├── chat_service.py       # Manages conversation flow
│   │   └── mcp_client.py         # Client to call the MCP server from agents
│   │
│   ├── utils/                    # Shared utilities
│   │   ├── __init__.py
│   │   ├── logger.py             # Structured logging setup
│   │   └── helpers.py            # Date parsing, budget formatting, etc.
│   │
│   └── config/                   # Configuration files
│       ├── __init__.py
│       └── prompts.yaml          # Optional: externalized prompt templates
│
├── frontend/                     # Next.js application (Module 10)
│   └── .gitkeep                  # Placeholder until frontend build
│
└── tests/                        # All tests live here
    ├── __init__.py
    ├── conftest.py               # Shared fixtures (mock LLM, mock MCP, etc.)
    ├── test_schemas/             # Pydantic model tests
    │   └── test_travel_intent.py
    ├── test_mcp_server/          # MCP server tool tests
    │   ├── test_search_flights.py
    │   ├── test_search_hotels.py
    │   └── test_web_search.py
    ├── test_agents/              # Agent unit tests
    │   ├── test_greeting_agent.py
    │   └── test_planning_agent.py
    ├── test_orchestration/       # Graph integration tests
    │   └── test_graph.py
    └── test_api/                 # API endpoint tests
        └── test_routes.py
```

### 4.1 Folder Structure Changes from Current State

| Change | Reason |
|---|---|
| **Removed** `backend/models/` | Redundant with `backend/schemas/`. Pydantic models go in `schemas/`. |
| **Removed** `backend/tools/` | MCP tools live inside `backend/mcp_servers/tools/`. No standalone tools directory needed. |
| **Restructured** `backend/mcp_servers/` | Collapsed three separate server folders into one `server.py` + `tools/` directory. GEMINI.md mandates **a single MCP server**. |
| **Added** `backend/mcp_servers/utils/` | Shared Amadeus client and error handling for MCP tools. |
| **Added** `tests/` at root | Top-level test directory mirroring backend structure. |
| **Added** `backend/services/mcp_client.py` | Client-side code for agents to call the MCP server. |
| **Added** `backend/orchestration/` files | `graph.py`, `state.py`, `router.py` for clean LangGraph separation. |
| **Added** `backend/agents/base_agent.py` | Shared utilities across all agents (prompt builders, LLM instantiation). |

---

## 5. Core Data Models

### 5.1 TravelIntent (User Input)

```
TravelIntent
├── destination: str                # Required. e.g., "Paris, France"
├── source_location: Optional[str]  # Origin city. e.g., "Mumbai, India"
├── start_date: Optional[str]       # ISO date. e.g., "2025-06-15"
├── end_date: Optional[str]         # ISO date. e.g., "2025-06-22"
├── duration_days: Optional[int]    # Alternative to end_date
├── num_travelers: int              # Default: 1
├── budget: float                   # In USD
├── currency: str                   # Default: "USD"
├── preferences: Optional[str]      # Free-text. e.g., "adventure, local food"
├── travel_style: Optional[str]     # "budget" | "mid-range" | "luxury"
└── special_requirements: Optional[str]  # Dietary, accessibility, etc.
```

### 5.2 TravelState (LangGraph Shared State)

This is the central `TypedDict` flowing through the entire graph.

```
TravelState
├── messages: Annotated[list, add_messages]      # Conversation history (appends)
├── travel_intent: Optional[TravelIntent]         # Extracted user intent
├── intent_confirmed: bool                        # User confirmed intent?
│
├── flight_options: list[FlightOption]            # From Transport Agent
├── hotel_options: list[HotelOption]              # From Accommodation Agent
├── local_insights: list[LocalInsight]            # From Local Expert Agent
│
├── itinerary: Optional[Itinerary]                # Generated day-by-day plan
├── budget_summary: Optional[BudgetSummary]       # Cost breakdown
│
├── feedback: Optional[str]                       # User feedback text
├── feedback_type: Optional[str]                  # "modify" | "approve" | "reject"
├── iteration_count: int                          # Feedback loop counter (max 5)
│
├── booking_confirmation: Optional[BookingConfirmation]  # From Payment Agent
├── current_phase: str                            # "greeting"|"planning"|"data_gathering"|"itinerary"|"feedback"|"payment"|"complete"
└── errors: list[str]                             # Error log (appends)
```

### 5.3 Supporting Models

```
FlightOption
├── airline: str
├── flight_number: str
├── origin: str          # IATA code
├── destination: str     # IATA code
├── departure_time: str
├── arrival_time: str
├── duration: str
├── price: float
├── currency: str
└── stops: int

HotelOption
├── name: str
├── address: str
├── rating: float
├── price_per_night: float
├── currency: str
├── amenities: list[str]
└── source_url: Optional[str]

LocalInsight
├── name: str
├── category: str        # "attraction"|"restaurant"|"activity"|"hidden_gem"
├── description: str
├── estimated_cost: Optional[float]
└── source_url: Optional[str]

DayPlan
├── day_number: int
├── date: str
├── activities: list[LocalInsight]
├── transport: Optional[FlightOption]
├── hotel: Optional[HotelOption]
└── estimated_day_cost: float

Itinerary
├── title: str
├── destination: str
├── start_date: str
├── end_date: str
├── days: list[DayPlan]
└── total_estimated_cost: float

BudgetSummary
├── transport_cost: float
├── accommodation_cost: float
├── activities_cost: float
├── food_estimate: float
├── miscellaneous: float
├── total: float
└── within_budget: bool

BookingConfirmation
├── booking_reference: str     # Generated UUID
├── status: str                # "confirmed" | "pending"
├── flight_summary: str
├── hotel_summary: str
├── estimated_total_cost: float
└── timestamp: str
```

---

## 6. MCP Server Design

### 6.1 Architecture

A **single FastMCP process** (`planit_mcp`) runs independently and exposes three tools.

**How it runs:**
```bash
# Terminal 1: Start MCP server
python -m backend.mcp_servers.server
# This starts on stdio or streamable HTTP (port 8001)
```

**How agents communicate with it:**
- Agents do NOT call the MCP server directly.
- Agents use LangChain's `@tool` decorator to define tool wrappers.
- These tool wrappers internally use `httpx` to call the MCP server.
- This keeps agents decoupled from MCP transport details.

### 6.2 Tool: `search_flights`

| Property | Value |
|---|---|
| **MCP Tool Name** | `search_flights` |
| **External API** | Amadeus Flight Offers Search |
| **Input Model** | `FlightSearchInput` |
| **Output** | JSON array of `FlightOption` |

**Input Schema:**
```
FlightSearchInput
├── origin: str              # IATA code (e.g., "BOM")
├── destination: str         # IATA code (e.g., "CDG")
├── departure_date: str      # ISO date
├── return_date: Optional[str]
├── adults: int              # Default: 1
├── max_results: int         # Default: 5
└── currency: str            # Default: "USD"
```

**Implementation Notes:**
- Uses `amadeus` SDK: `client.shopping.flight_offers_search.get(...)`
- Handles `ResponseError` from Amadeus gracefully
- Returns top N results sorted by price
- Caches results by (origin, destination, date) for re-planning reuse

### 6.3 Tool: `search_hotels`

| Property | Value |
|---|---|
| **MCP Tool Name** | `search_hotels` |
| **External API** | Amadeus Hotel Search |
| **Input Model** | `HotelSearchInput` |
| **Output** | JSON array of `HotelOption` |

**Input Schema:**
```
HotelSearchInput
├── city_code: str           # IATA city code (e.g., "PAR")
├── check_in: str            # ISO date
├── check_out: str           # ISO date
├── adults: int              # Default: 1
├── max_results: int         # Default: 5
├── price_range: Optional[str]  # "budget"|"mid"|"luxury"
└── currency: str            # Default: "USD"
```

**Implementation Notes:**
- Two-step: First `reference_data.locations.hotels.by_city`, then `shopping.hotel_offers_search`
- Filters by price range if specified
- Returns structured `HotelOption` list

### 6.4 Tool: `web_search_places`

| Property | Value |
|---|---|
| **MCP Tool Name** | `web_search_places` |
| **External API** | Tavily Search |
| **Input Model** | `WebSearchInput` |
| **Output** | JSON array of `LocalInsight` |

**Input Schema:**
```
WebSearchInput
├── query: str               # e.g., "hidden gems in Paris for food lovers"
├── search_depth: str        # "basic" | "advanced"
├── max_results: int         # Default: 5
└── include_domains: Optional[list[str]]  # Prioritize specific sites
```

**Implementation Notes:**
- Uses `tavily-python` SDK: `TavilyClient.search(query=..., search_depth=...)`
- LLM post-processes raw results into structured `LocalInsight` objects
- Falls back to `requests` + BeautifulSoup if Tavily is unavailable

---

## 7. Agent Architecture

### 7.1 Shared Agent Base

All agents share a common pattern:

1. **Receive** current `TravelState` as input
2. **Build** a prompt from state + system instruction
3. **Call** LLM (ChatGroq) with/without tool bindings
4. **Parse** structured output (Pydantic)
5. **Return** a partial state update `dict`

`base_agent.py` provides:
- LLM instantiation (`get_llm()` using `ChatGroq`)
- Prompt template builder
- Structured output parser
- Error wrapping

### 7.2 Agent Breakdown

#### Greeting Agent
- **Purpose:** Extract `TravelIntent` from natural language
- **LLM:** ChatGroq with structured output (`with_structured_output(TravelIntent)`)
- **Behavior:**
  - If intent is incomplete → returns a clarification question in `messages`
  - If intent is complete → sets `travel_intent` and `intent_confirmed = True`
- **No MCP tools used**

#### Planning Agent
- **Purpose:** Central orchestrator. Decides which agents to invoke next.
- **LLM:** ChatGroq for reasoning about next steps
- **Behavior:**
  - Reads `current_phase` and `TravelState`
  - Returns routing decision (which agent node to visit next)
  - On feedback: determines which parts of the itinerary need recomputation
  - Implements smart caching: skips re-calling agents whose data hasn't changed
- **No MCP tools used** (routing only)

#### Transport Agent
- **Purpose:** Find flight options
- **LLM:** ChatGroq to construct search parameters from `TravelIntent`
- **MCP Tool:** `search_flights` (via tool wrapper)
- **Output:** Updates `flight_options` in state

#### Accommodation Agent
- **Purpose:** Find hotel options
- **LLM:** ChatGroq to construct search parameters
- **MCP Tool:** `search_hotels` (via tool wrapper)
- **Output:** Updates `hotel_options` in state

#### Local Expert Agent
- **Purpose:** Discover attractions, hidden gems, cultural tips
- **LLM:** ChatGroq for RAG-style reasoning over search results
- **MCP Tool:** `web_search_places` (via tool wrapper)
- **Output:** Updates `local_insights` in state

#### Constraint / Itinerary Agent
- **Purpose:** Validate all constraints and assemble optimized itinerary
- **LLM:** ChatGroq with structured output (`with_structured_output(Itinerary)`)
- **Behavior:**
  - Validates: budget ≤ total cost, dates align, flights connect properly
  - Assembles day-by-day plan from all gathered data
  - Computes `BudgetSummary`
  - Sets `current_phase = "feedback"`
- **No MCP tools used** (pure reasoning)

#### Payment Agent
- **Purpose:** Simulate booking confirmation
- **LLM:** ChatGroq to generate booking summary
- **Behavior:**
  - Generates a mock `booking_reference` (UUID)
  - Summarizes flights, hotels, total cost
  - Sets `current_phase = "complete"`
- **No MCP tools used** (simulation only)

---

## 8. LangGraph Orchestration

### 8.1 Graph Structure

```
                    START
                      │
                      ▼
                ┌───────────┐
                │  greeting  │◄──────────────────────────┐
                └─────┬─────┘                            │
                      │                                  │
              intent_confirmed?                          │
              ┌───No──┤──Yes──┐                          │
              │               │                          │
              ▼               ▼                          │
         (loop back)    ┌──────────┐                     │
                        │ planning │◄──────────┐         │
                        └────┬─────┘           │         │
                             │                 │         │
                    ┌────────┼────────┐        │         │
                    ▼        ▼        ▼        │         │
              ┌──────┐ ┌────────┐ ┌──────┐    │         │
              │trans- │ │ accom- │ │local │    │         │
              │ port  │ │ modat- │ │expert│    │         │
              └──┬───┘ │  ion   │ └──┬───┘    │         │
                 │     └───┬────┘    │         │         │
                 └────────┬┘─────────┘         │         │
                          ▼                    │         │
                   ┌────────────┐              │         │
                   │ constraint │              │         │
                   └──────┬─────┘              │         │
                          │                    │         │
                    feedback phase             │         │
                   ┌──────┤──────┐             │         │
                   │      │      │             │         │
                approve  modify  new_trip      │         │
                   │      │      │             │         │
                   ▼      ▼      ▼             │         │
              ┌────────┐  │   (back to         │         │
              │payment │  │    greeting)────────┼─────────┘
              └───┬────┘  │                    │
                  │       └────────────────────┘
                  ▼
                 END
```

### 8.2 State Reducers

| Field | Reducer | Behavior |
|---|---|---|
| `messages` | `add_messages` (built-in) | Appends new messages to history |
| `flight_options` | Overwrite (no reducer) | Replaced each time Transport Agent runs |
| `hotel_options` | Overwrite | Replaced each time Accommodation Agent runs |
| `local_insights` | Overwrite | Replaced each time Local Expert runs |
| `errors` | `operator.add` | Accumulates error strings |
| `iteration_count` | Overwrite | Incremented by Planning Agent |
| Everything else | Overwrite | Direct assignment |

### 8.3 Conditional Edge Functions

```
route_after_greeting:
  if state.intent_confirmed → "planning"
  else → "greeting" (ask again)

route_after_planning:
  returns list of parallel nodes: ["transport", "accommodation", "local_expert"]
  (LangGraph supports fan-out to multiple nodes)

route_after_constraint:
  → waits for user feedback (human-in-the-loop interrupt)

route_after_feedback:
  if feedback_type == "approve" → "payment"
  if feedback_type == "modify" → "planning" (re-plan)
  if feedback_type == "reject" or "new_trip" → "greeting"
  if iteration_count > 5 → "payment" (force finalize)
```

### 8.4 Human-in-the-Loop

LangGraph's `interrupt()` mechanism is used after the Constraint Agent generates an itinerary:

1. Graph compiles with `checkpointer` (MemorySaver or SQLite)
2. After Constraint Agent, graph yields control back to the API
3. FastAPI sends the itinerary to the frontend
4. User provides feedback
5. FastAPI resumes the graph with `graph.invoke(Command(resume=feedback_data), config=thread_config)`
6. Planning Agent determines what to re-compute

---

## 9. FastAPI Backend

### 9.1 API Endpoints

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/chat` | Send a user message, receive agent response |
| `GET` | `/api/itinerary/{thread_id}` | Get current itinerary for a session |
| `POST` | `/api/feedback` | Submit feedback on an itinerary |
| `POST` | `/api/confirm` | Confirm and "book" the itinerary |
| `GET` | `/api/health` | Health check |
| `WS` | `/api/ws/{thread_id}` | WebSocket for streaming agent responses |

### 9.2 Session Management

- Each user conversation = one LangGraph **thread** (identified by `thread_id`)
- Thread state is persisted via LangGraph's `MemorySaver` (in-memory for dev, SQLite for prod)
- Frontend sends `thread_id` with every request
- New conversation = new `thread_id` (UUID generated by backend)

### 9.3 Request/Response Flow

```
Frontend POST /api/chat { thread_id, message }
  → FastAPI receives request
  → Invokes LangGraph graph with thread config
  → Graph runs through agent nodes
  → If interrupt (feedback needed) → returns itinerary + "awaiting_feedback" status
  → If complete → returns final result
  → Response: { thread_id, response, phase, itinerary?, status }
```

---

## 10. Frontend Architecture

### 10.1 Page Structure

```
frontend/
├── app/
│   ├── layout.tsx            # Root layout (fonts, theme)
│   ├── page.tsx              # Landing page / hero
│   └── plan/
│       └── page.tsx          # Main planning interface
├── components/
│   ├── chat/
│   │   ├── ChatWindow.tsx    # Main chat container
│   │   ├── MessageBubble.tsx # Individual message
│   │   ├── ChatInput.tsx     # Text input + send button
│   │   └── TypingIndicator.tsx
│   ├── itinerary/
│   │   ├── ItineraryCard.tsx # Day-by-day view
│   │   ├── FlightCard.tsx    # Flight option display
│   │   ├── HotelCard.tsx     # Hotel option display
│   │   └── BudgetChart.tsx   # Budget breakdown visualization
│   ├── feedback/
│   │   ├── FeedbackPanel.tsx # Modification controls
│   │   └── ApproveButton.tsx
│   └── ui/                   # ShadCN components
├── lib/
│   ├── api.ts                # Backend API client
│   └── types.ts              # TypeScript types (mirroring Pydantic)
└── styles/
    └── globals.css           # Tailwind base + custom styles
```

### 10.2 UI Design Direction

- **Aesthetic**: Glassmorphism + dark mode, similar to sarvam.ai
- **Layout**: Split-panel — chat on the left, itinerary visualization on the right
- **Animations**: Framer Motion for message appearance, panel transitions, card reveals
- **Key Interactions:**
  - Conversational chat for initial input
  - Auto-generated itinerary cards appear as structured output
  - Inline feedback controls ("Adjust Budget", "Add Activity", etc.)
  - Animated loading states during agent processing

---

## 11. Module Build Order

This is the heart of the modular approach. **Build one → test it → move to the next.**

### Phase 1: Foundation (No LLM, No API)

| Module | What to Build | Test Criteria | Dependencies |
|---|---|---|---|
| **M1: Schemas** | All Pydantic models in `backend/schemas/` | Models instantiate, validate, reject bad input | None |
| **M2: Config & Settings** | `backend/core/settings.py`, `.env.example` | Settings load from `.env`, defaults work | M1 |
| **M3: Utilities** | `backend/utils/logger.py`, `helpers.py` | Logger outputs structured logs, helpers parse dates correctly | None |

### Phase 2: MCP Server (External API Integration)

| Module | What to Build | Test Criteria | Dependencies |
|---|---|---|---|
| **M4: Amadeus Client** | `backend/mcp_servers/utils/amadeus_client.py` | Client authenticates, returns raw data from Amadeus test env | M2 |
| **M5: MCP Tool — search_flights** | `backend/mcp_servers/tools/search_flights.py` | Tool accepts `FlightSearchInput`, returns valid `FlightOption[]` JSON | M1, M4 |
| **M6: MCP Tool — search_hotels** | `backend/mcp_servers/tools/search_hotels.py` | Tool accepts `HotelSearchInput`, returns valid `HotelOption[]` JSON | M1, M4 |
| **M7: MCP Tool — web_search_places** | `backend/mcp_servers/tools/web_search_places.py` | Tool accepts `WebSearchInput`, returns valid `LocalInsight[]` JSON | M1 |
| **M8: MCP Server Assembly** | `backend/mcp_servers/server.py` | Server starts, all 3 tools are registered, respond to test calls | M5, M6, M7 |

### Phase 3: Agent Layer (LLM Integration)

| Module | What to Build | Test Criteria | Dependencies |
|---|---|---|---|
| **M9: Base Agent** | `backend/agents/base_agent.py` | LLM instantiates, prompt builder works, structured output parses | M2 |
| **M10: MCP Client** | `backend/services/mcp_client.py` | Client can call running MCP server and receive structured responses | M8 |
| **M11: Greeting Agent** | `backend/agents/greeting_agent/` | Extracts `TravelIntent` from sample messages, handles ambiguity | M1, M9 |
| **M12: Transport Agent** | `backend/agents/transport_agent/` | Constructs search params from intent, calls MCP, returns flights | M9, M10 |
| **M13: Accommodation Agent** | `backend/agents/accommodation_agent/` | Constructs search params, calls MCP, returns hotels | M9, M10 |
| **M14: Local Expert Agent** | `backend/agents/local_expert_agent/` | Constructs query, calls MCP, returns insights | M9, M10 |
| **M15: Constraint Agent** | `backend/agents/constraint_agent/` | Validates budget/dates, assembles itinerary from gathered data | M1, M9 |
| **M16: Payment Agent** | `backend/agents/payment_agent/` | Generates mock booking confirmation | M1, M9 |

### Phase 4: Orchestration (Graph Assembly)

| Module | What to Build | Test Criteria | Dependencies |
|---|---|---|---|
| **M17: LangGraph State** | `backend/orchestration/state.py` | State TypedDict compiles, reducers work correctly | M1 |
| **M18: Graph Definition** | `backend/orchestration/graph.py`, `router.py` | Full graph compiles, nodes connect, conditional edges route correctly | M11-M16, M17 |
| **M19: End-to-End Flow** | Integration test: greeting → itinerary generation | Complete flow works with real LLM + real MCP server | M18 |

### Phase 5: API Layer

| Module | What to Build | Test Criteria | Dependencies |
|---|---|---|---|
| **M20: FastAPI Routes** | `backend/api/routes.py`, `backend/main.py` | `/chat` endpoint invokes graph, returns structured response | M18 |
| **M21: Chat Service** | `backend/services/chat_service.py` | Session management, thread persistence, feedback submission | M20 |
| **M22: WebSocket** | `backend/api/websocket.py` | Streaming agent responses via WebSocket | M21 |

### Phase 6: Frontend

| Module | What to Build | Test Criteria | Dependencies |
|---|---|---|---|
| **M23: Next.js Setup** | Initialize Next.js + Tailwind + ShadCN | App runs, base layout renders | None |
| **M24: Chat Interface** | Chat components, API integration | User can type, messages display, bot responds | M20 |
| **M25: Itinerary View** | Itinerary cards, flight/hotel cards, budget chart | Structured itinerary renders beautifully | M24 |
| **M26: Feedback Flow** | Feedback panel, modification controls | User can modify and re-plan | M25 |
| **M27: Polish** | Animations, loading states, error handling, responsive design | Production-ready UI | M26 |

---

## 12. Testing Strategy

### 12.1 Test Levels

| Level | Tool | What |
|---|---|---|
| **Unit** | `pytest` | Pydantic models, utility functions, individual agent logic (with mocked LLM) |
| **Integration** | `pytest` + `httpx.AsyncClient` | MCP tools against real APIs (test env), agent chains with real LLM |
| **E2E (Backend)** | `pytest` + FastAPI `TestClient` | Full API flow: chat → itinerary → feedback → confirm |
| **E2E (Frontend)** | Manual + Playwright (future) | Full user flow in browser |

### 12.2 Mocking Strategy

| Component | Mock Approach |
|---|---|
| **LLM (Groq)** | `unittest.mock.patch` on `ChatGroq.invoke()`. Return pre-defined `AIMessage` with structured content. |
| **Amadeus API** | Mock `amadeus.Client` methods. Return sample flight/hotel JSON. |
| **Tavily API** | Mock `TavilyClient.search()`. Return sample search results. |
| **MCP Server** | Run a lightweight mock MCP server in tests, or mock `mcp_client.py` |

### 12.3 Test Commands

```bash
# Run all tests
pytest tests/ -v

# Run specific module tests
pytest tests/test_schemas/ -v
pytest tests/test_mcp_server/ -v
pytest tests/test_agents/ -v

# Run with coverage
pytest tests/ --cov=backend --cov-report=html
```

---

## 13. Environment & Configuration

### 13.1 `.env` File

```env
# === LLM ===
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxx
GROQ_MODEL_NAME=llama-3.3-70b-versatile

# === MCP Server ===
MCP_SERVER_HOST=localhost
MCP_SERVER_PORT=8001

# === Amadeus ===
AMADEUS_CLIENT_ID=xxxxxxxxxxxxx
AMADEUS_CLIENT_SECRET=xxxxxxxxxxxxx
AMADEUS_HOSTNAME=test          # "test" for dev, "production" for prod

# === Tavily ===
TAVILY_API_KEY=tvly-xxxxxxxxxxxxx

# === App ===
APP_ENV=development
LOG_LEVEL=DEBUG
```

### 13.2 Settings Model

`backend/core/settings.py` will use `pydantic-settings`:

```
class Settings(BaseSettings):
    groq_api_key: str
    groq_model_name: str = "llama-3.3-70b-versatile"
    mcp_server_host: str = "localhost"
    mcp_server_port: int = 8001
    amadeus_client_id: str
    amadeus_client_secret: str
    amadeus_hostname: str = "test"
    tavily_api_key: str
    app_env: str = "development"
    log_level: str = "DEBUG"

    class Config:
        env_file = ".env"
```

### 13.3 Running the System

```bash
# Terminal 1: Start the MCP Server
python -m backend.mcp_servers.server

# Terminal 2: Start the FastAPI Backend
uvicorn backend.main:app --reload --port 8000

# Terminal 3: Start the Frontend (after Module 23+)
cd frontend && npm run dev
```

---

## 14. Risks & Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| **Amadeus Rate Limits** (test env = 10 req/sec) | Slow data gathering during demos | Cache responses aggressively. Implement mock mode for development. |
| **Groq Rate Limits** (free tier limits) | Agent calls may fail mid-flow | Implement retry with backoff in `base_agent.py`. Fall back to smaller model. |
| **LangGraph Infinite Loops** | Token burn, hung requests | `iteration_count` max (5) in state. Hard timeout in graph config. |
| **Tavily API Down** | Local Expert Agent fails | Fallback to `requests` + BeautifulSoup scraping. Graceful degradation. |
| **MCP Server Crash** | All tool calls fail | Health checks. Auto-restart. Agents catch tool errors and continue with partial data. |
| **Large Context Window** | Token overflow in multi-turn conversations | Summarize old messages. Only pass relevant state fields to each agent's prompt. |
| **IATA Code Resolution** | User says "Paris" not "CDG" | Greeting Agent uses LLM to resolve city names to IATA codes. Fallback: hardcoded mapping of common cities. |

---

> **Next Step:** Approve this plan, then we begin with **Module M1: Schemas** — building and testing all Pydantic data models.
