from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ResearchType(StrEnum):
    COMPANY_ANALYSIS = "company_analysis"
    INDUSTRY_ANALYSIS = "industry_analysis"
    POLICY_IMPACT = "policy_impact"
    FINANCIAL_REPORT_REVIEW = "financial_report_review"
    RISK_EVENT_TRACKING = "risk_event_tracking"
    GENERAL_RESEARCH = "general_research"


class RiskDecision(StrEnum):
    PASS = "pass"
    RETRY = "retry"
    RECOLLECT = "recollect"


class Severity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=True)


class AgentOutput(StrictModel):

    agent_name: str
    summary: str

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class ResearchDirection(StrictModel):
    name: str
    reason: str


class TriageOutput(AgentOutput):
    research_type: ResearchType
    target: str
    directions: list[ResearchDirection] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    required_tools: list[str] = Field(default_factory=list)


class SourceItem(StrictModel):
    title: str
    source_type: str
    url: str | None = None
    published_at: str | None = None
    summary: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class ResearchOutput(AgentOutput):
    sources: list[SourceItem] = Field(default_factory=list)
    key_materials: list[str] = Field(default_factory=list)
    data_gaps: list[str] = Field(default_factory=list)


class AnalysisFinding(StrictModel):
    claim: str
    evidence: list[str] = Field(default_factory=list)
    confidence: str = "medium"


class AnalysisOutput(AgentOutput):
    findings: list[AnalysisFinding] = Field(default_factory=list)
    growth_drivers: list[str] = Field(default_factory=list)
    risk_points: list[str] = Field(default_factory=list)
    draft_report: str = ""


class RiskFinding(StrictModel):
    finding_type: str
    severity: Severity
    message: str
    suggested_action: str
    evidence_refs: list[str] = Field(default_factory=list)


class RiskOutput(AgentOutput):
    decision: RiskDecision
    findings: list[RiskFinding] = Field(default_factory=list)
    reason: str = ""


class SupervisorOutput(AgentOutput):
    final_report: str
    key_conclusions: list[str] = Field(default_factory=list)
    risk_summary: list[str] = Field(default_factory=list)
    follow_up_suggestions: list[str] = Field(default_factory=list)
