# PLANIT (~Plan Iteration)
## MCP-Orchestrated Multi-Agent Travel Planning System

---

# 1. OVERVIEW

PlanIT is a modular, multi-agent travel planning system built using the Model Context Protocol (MCP).

It transforms user travel requests into structured, optimized, and personalized itineraries using:

- LLM-based reasoning agents
- MCP-based data retrieval servers
- Deterministic execution pipelines
- Iterative feedback loops

---

# 2. CORE OBJECTIVE

Convert natural language travel intent into:

1. Structured TravelIntent
2. Real-time enriched data (transport, accommodation, local insights)
3. Optimized itinerary
4. Interactive feedback loop
5. Finalized travel plan

---

# 3. SYSTEM ARCHITECTURE

## 3.1 High-Level Flow

User Input
→ Greeting Agent
→ Planning Agent (Orchestrator)
→ MCP Servers (Data Retrieval)
→ Specialized Agents (Reasoning)
→ Constraint & Itinerary Agent
→ Feedback Loop
→ Final Output

---

## 3.2 Agent Breakdown

### 1. Greeting Agent
- LLM-powered (ChatGroq via LangChain)
- Extracts structured TravelIntent
- Performs validation and clarification

---

### 2. Planning Agent (Core Orchestrator)
- Built using LangGraph (preferred) or LangChain
- Maintains global state
- Routes tasks to agents
- Handles feedback loops

---

### 3. Local Expert Agent
- LLM-powered
- Uses MCP web search server (Tavily)
- Performs RAG-style reasoning
- Extracts hidden gems, cultural insights

---

### 4. Transport Agent (Planned)
- Uses MCP server over transport APIs
- Fetches:
  - Flights
  - Trains
  - Buses
- Returns structured transport options

Possible APIs:
- Amadeus
- Skyscanner (RapidAPI)
- Rome2Rio

---

### 5. Accommodation Agent (Planned)
- Uses MCP server over hotel APIs
- Fetches:
  - Hotels
  - Homestays
  - Budget stays

Possible APIs:
- Booking.com (RapidAPI)
- Expedia API
- Google Places API

---

### 6. Constraint & Itinerary Agent
- Validates:
  - Budget
  - Time constraints
  - Feasibility
- Generates optimized itinerary

---

### 7. Payment Agent (Future)
- Simulates booking confirmation
- Handles transaction flow (mock)

---

# 4. MCP ARCHITECTURE

## 4.1 Concept

MCP (Model Context Protocol) allows agents to interact with external tools in a standardized way.

Each MCP server:

- Accepts JSON input
- Returns structured JSON output
- Is stateless and deterministic

---

## 4.2 MCP Servers in PlanIT

### 1. Web Search MCP Server
- Uses Tavily API
- Returns search results

Input:
{
  "query": ""
}

Output:
{
  "results": [
    {
      "title": "",
      "snippet": "",
      "url": ""
    }
  ]
}

---

### 2. Transport MCP Server (Future)
- Wraps external APIs
- Returns transport options

---

### 3. Accommodation MCP Server (Future)
- Wraps hotel APIs
- Returns lodging options

---

## 4.3 MCP Tech

- FastAPI (backend)
- FastMCP (protocol handling)

---

# 5. TECH STACK

## 5.1 Backend

- Python 3.10+
- FastAPI
- FastMCP

---

## 5.2 LLM Layer

- Groq LLMs via LangChain
- ChatGroq interface

Reason:
- Ultra-fast inference
- Cost-efficient
- Suitable for agent pipelines

---

## 5.3 Agent Orchestration

- LangGraph (preferred)
- LangChain (fallback)

Responsibilities:
- Multi-agent workflow
- State transitions
- Tool calling

---

## 5.4 Data Modeling

- Pydantic

Used for:
- TravelIntent
- TravelState
- MCP schemas

---

## 5.5 Web Search

- Tavily API

Used in:
- Local Expert Agent MCP server

---

## 5.6 Frontend

- React (Vite or Next.js)
- Glassmorphism UI design
- Chatbot-style interface

Features:
- Chat-based input
- Structured output panels
- Itinerary visualization
- Feedback controls

---

## 5.7 DevOps (Future)

- Docker
- GitHub Actions
- Cloud deployment (AWS/GCP)

---

# 6. CORE DATA MODELS

## 6.1 TravelIntent

```python
class TravelIntent(BaseModel):
    destination: str
    start_date: Optional[str]
    end_date: Optional[str]
    duration_days: Optional[int]
    budget: int
    preferences: Optional[str]
    source_location: Optional[str]