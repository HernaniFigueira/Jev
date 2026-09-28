"""Model definitions for analysis results."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class StackInfo:
    languages: list[str] = field(default_factory=list)
    frameworks: list[str] = field(default_factory=list)
    databases: list[str] = field(default_factory=list)
    infrastructures: list[str] = field(default_factory=list)
    package_managers: list[str] = field(default_factory=list)
    services: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class FlowPoint:
    """A detected flow / decision point in the project."""
    name: str
    category: str  # e.g. routing, classification, validation, payment, chatbot...
    description: str
    evidence: list[str] = field(default_factory=list)  # file paths + signals
    confidence: float = 0.5  # 0..1 heuristic confidence
    files: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class JEVOpportunity:
    use_case: str                       # 🎯 Caso de uso
    entry_point: str                    # 🔄 Onde JEV entra
    utility_score: float                # 📊 0..10
    benefit: str                        # ✅ Benefício esperado
    pros: list[str]                     # ⚖️ prós
    cons: list[str]                     # ⚖️ contras
    implementation_complexity: str      # 🛠️ Baixa / Média / Alta
    cost_impact: str                    # 💰 impacto em custo
    risks: list[str]                    # ⚠️ riscos
    recommendation: str                 # ⏱️ AGORA / DEPOIS / NÃO USAR
    trigger_scale: str                  # 📈 escala que justifica
    current_solution: str               # 🔁 solução atual/alternativa
    category: str = ""
    flow_evidence: list[str] = field(default_factory=list)
    affected_files: list[str] = field(default_factory=list)
    comparison: dict[str, Any] = field(default_factory=dict)  # solution comparator
    score_breakdown: dict[str, Any] = field(default_factory=dict)  # why this score

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AnalysisReport:
    project_name: str
    source_type: str  # local / github
    source_path: str
    stack: StackInfo
    architecture_summary: str
    flows: list[FlowPoint] = field(default_factory=list)
    opportunities: list[JEVOpportunity] = field(default_factory=list)
    architecture_nodes: list[dict[str, Any]] = field(default_factory=list)
    architecture_edges: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    analysis_mode: str = "static"
    mocked_fields: list[str] = field(default_factory=list)

    def summary(self) -> dict[str, Any]:
        counts = {"AGORA": 0, "DEPOIS": 0, "NÃO USAR": 0}
        for o in self.opportunities:
            counts[o.recommendation] = counts.get(o.recommendation, 0) + 1
        return {
            "project_name": self.project_name,
            "flows_analyzed": len(self.flows),
            "agora": counts["AGORA"],
            "depois": counts["DEPOIS"],
            "nao_usar": counts["NÃO USAR"],
            "stack": self.stack.to_dict(),
            "architecture_summary": self.architecture_summary,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_name": self.project_name,
            "source_type": self.source_type,
            "source_path": self.source_path,
            "stack": self.stack.to_dict(),
            "architecture_summary": self.architecture_summary,
            "flows": [f.to_dict() for f in self.flows],
            "opportunities": [o.to_dict() for o in self.opportunities],
            "architecture_nodes": self.architecture_nodes,
            "architecture_edges": self.architecture_edges,
            "warnings": self.warnings,
            "limitations": self.limitations,
            "analysis_mode": self.analysis_mode,
            "mocked_fields": self.mocked_fields,
            "counts": self.summary(),
        }
