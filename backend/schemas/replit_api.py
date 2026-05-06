from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field

class TravelPlanInput(BaseModel):
    origin: str = ""
    destination: str = ""
    days: str = ""
    budget: str = ""
    style: str = ""
    preferences: str = ""


class TravelSummary(BaseModel):
    route: str
    days: str
    budget: str
    style: str


class APIDayPlan(BaseModel):
    day: str
    title: str
    activities: List[str] = Field(default_factory=list)


class BudgetBreakdown(BaseModel):
    transport: str
    stay: str
    food: str


class LiveSearchItem(BaseModel):
    category: str
    title: str
    url: str
    snippet: str
    price_hint: str = "Check live site"
    source: str = "Web search"


class LiveResearch(BaseModel):
    status: str
    searched_at: str
    queries: List[str] = Field(default_factory=list)
    hotels: List[LiveSearchItem] = Field(default_factory=list)
    markets: List[LiveSearchItem] = Field(default_factory=list)
    activities: List[LiveSearchItem] = Field(default_factory=list)
    transport: List[LiveSearchItem] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)


class TravelPlanOutput(BaseModel):
    summary: TravelSummary
    highlights: List[str]
    plan: List[APIDayPlan]
    budget: BudgetBreakdown
    live_research: Optional[LiveResearch] = None