from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

from bananatrade.agents.contexts import AnalysisContext, ObservationContext
from bananatrade.agents.validator import EvidenceMismatchError, validate_report
from bananatrade.gateway.errors import EmptyCompletionError, GatewayError, ModelNotAvailableError
from bananatrade.gateway.structured import StructuredOutputError
from bananatrade.storage.db import save_agent_output


class Gateway(Protocol):
    async def call(self, tier: str, prompt: str) -> dict[str, Any]: ...


async def run_stub(gateway: Gateway, trader_result: dict[str, Any], risk_approved: bool) -> str:
    """Run the Phase 0 decision gate; CIO is only eligible after both gates pass."""
    if trader_result.get("side") == "HOLD" or not risk_approved:
        return "DEFERRED"
    await gateway.call("tier4_cio", "Review the risk-approved paper trade.")
    return "CIO_CALLED"


async def run_agents(agents: list[Any], snapshot: dict[str, Any], store: Any = None, db_path: Path | None = None, triggers: list[Any] | None = None, analysis_agents: list[Any] | None = None) -> list[Any]:
    """Run observations, then analyses using only validated observation reports."""
    run_id = uuid4().hex
    valid = []
    reports = []
    context = ObservationContext(snapshot, triggers or [])
    for agent in agents:
        try:
            report = await agent.run(context)
            validate_report(report, snapshot)
            valid.append(report)
            reports.append(report)
            if store:
                store.save(report, agent, "accepted")
            if db_path:
                save_agent_output(db_path, run_id=run_id, agent=agent, result=report, status="success", gateway_result=getattr(agent, "last_gateway_result", {}))
        except EvidenceMismatchError as exc:
            if store:
                store.save(locals().get("report", None), agent, "rejected", str(exc))
            if db_path:
                save_agent_output(db_path, run_id=run_id, agent=agent, result=locals().get("report", {}), status="rejected", error=str(exc))
        except (GatewayError, StructuredOutputError, EmptyCompletionError, ModelNotAvailableError) as exc:
            if db_path:
                save_agent_output(db_path, run_id=run_id, agent=agent, result={}, status="failed", error=str(exc))
    for agent in analysis_agents or []:
        try:
            report = await agent.run(AnalysisContext(snapshot, triggers or [], reports))
            validate_report(report, snapshot)
            valid.append(report)
            if store:
                store.save(report, agent, "accepted")
            if db_path:
                save_agent_output(db_path, run_id=run_id, agent=agent, result=report, status="success", gateway_result=getattr(agent, "last_gateway_result", {}))
        except EvidenceMismatchError as exc:
            if store:
                store.save(locals().get("report", None), agent, "rejected", str(exc))
            if db_path:
                save_agent_output(db_path, run_id=run_id, agent=agent, result=locals().get("report", {}), status="rejected", error=str(exc))
        except (GatewayError, StructuredOutputError, EmptyCompletionError, ModelNotAvailableError) as exc:
            if db_path:
                save_agent_output(db_path, run_id=run_id, agent=agent, result={}, status="failed", error=str(exc))
    return valid
