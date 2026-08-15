import logging
import time
import uuid
from typing import Optional, List, TYPE_CHECKING
from app.mother.state import WorkflowState
from app.mother.task_manager import TaskManager
from app.mother.types import AgentTask
from app.services.groq_service import GroqService
from app.contracts import (
    DynamicPlan,
    PlanStep,
    OrchestrationEvent,
    OrchestrationResult,
    StudentRecord,
    OrchestrationMetrics,
    DynamicPlanRequestType,
    AgentStatus,
    ActivityLog,
    AgentType,
)


if TYPE_CHECKING:
    from app.agents.registry import AgentRegistry

logger = logging.getLogger(__name__)


class MotherAgent:
    """Mother Agent central orchestrator controlling multi-agent workflow execution."""

    def __init__(
        self,
        registry: Optional["AgentRegistry"] = None,
        groq_service: Optional[GroqService] = None,
    ):
        if registry is None:
            from app.agents.registry import AgentRegistry

            registry = AgentRegistry()
        self.registry = registry
        self.task_manager = TaskManager()
        if groq_service is None:
            import os
            groq_service = GroqService(
                api_key=os.getenv("MOTHER_GROQ_API_KEY"),
                model=os.getenv("MOTHER_GROQ_MODEL", "llama-3.3-70b-versatile"),
            )
        self.groq_service = groq_service

    def classify_intent(self, prompt: str) -> DynamicPlanRequestType:
        prompt_lower = prompt.lower()

        analytics_keywords = [
            "average",
            "avg",
            "highest",
            "lowest",
            "metrics",
            "percentile",
            "analytics",
            "analyze",
            "analysis",
            "distribution",
            "statistic",
            "statistics",
            "stats",
            "breakdown",
            "at risk",
            "at-risk",
            "risk",
            "probation",
            "performance",
            "compare",
            "correlation",
            "outlier",
            "standard deviation",
        ]
        if any(kw in prompt_lower for kw in analytics_keywords):
            return "analytics"

        write_keywords = [
            "update",
            "delete",
            "insert",
            "add",
            "modify",
            "set cgpa",
            "change",
        ]
        if any(kw in prompt_lower for kw in write_keywords):
            return "write"

        complex_keywords = ["complex", "multi-step", "pipeline"]
        if any(kw in prompt_lower for kw in complex_keywords):
            return "complex"

        return "read"

    def determine_next_agent(self, workflow: WorkflowState) -> Optional[str]:
        completed_agents = [
            t.agent for t in workflow.task_history if t.status == "completed"
        ]

        if "input" not in completed_agents:
            return "input"

        if "db" not in completed_agents:
            return "db"

        if workflow.results.get("db", {}).get("requires_confirmation"):
            return None

        plan_agents = [s.agent for s in workflow.plan.steps] if workflow.plan else []
        requires_analytics = (
            "analytics" in plan_agents or workflow.request_type == "analytics"
        )

        if (
            requires_analytics
            and "analytics" not in completed_agents
        ):
            return "analytics"

        if "output" not in completed_agents:
            return "output"

        return None


    def synthesize_plan(self, workflow: WorkflowState) -> DynamicPlan:
        """
        Synthesizes DynamicPlan using Groq LLM intelligence when available.
        Falls back safely to deterministic plan synthesis if Groq is unconfigured, disabled, or fails.
        """
        groq_payload = self.groq_service.generate_plan(workflow.user_query)
        if groq_payload:
            logger.info("Successfully generated workflow plan using Groq LLM intelligence.")
            workflow.request_type = groq_payload.request_type

            steps: List[PlanStep] = []
            for idx, s in enumerate(groq_payload.steps, start=1):
                steps.append(
                    PlanStep(
                        id=f"step-{idx}",
                        step_number=idx,
                        agent=s.agent,  # type: ignore
                        action=s.action,
                        description=s.description,
                        status="waiting",
                    )
                )

            return DynamicPlan(
                task_id=workflow.workflow_id,
                title=groq_payload.title,
                intent=groq_payload.intent,
                request_type=groq_payload.request_type,
                steps=steps,
            )

        logger.info("Using deterministic fallback plan synthesis.")
        steps: List[PlanStep] = [
            PlanStep(
                id="step-1",
                step_number=1,
                agent="input",
                action="Intent Parsing",
                description="Extract parameters from natural language query",
                status="waiting",
            ),
            PlanStep(
                id="step-2",
                step_number=2,
                agent="db",
                action="Database Query",
                description="Execute SQL query on campus database",
                status="waiting",
            ),
        ]

        if workflow.request_type == "analytics":
            steps.append(
                PlanStep(
                    id="step-3",
                    step_number=3,
                    agent="analytics",
                    action="Metrics Calculation",
                    description="Compute statistical metrics and aggregations",
                    status="waiting",
                )
            )
            steps.append(
                PlanStep(
                    id="step-4",
                    step_number=4,
                    agent="output",
                    action="Format Output",
                    description="Format summary table and response payload",
                    status="waiting",
                )
            )
        else:
            steps.append(
                PlanStep(
                    id="step-3",
                    step_number=3,
                    agent="output",
                    action="Format Output",
                    description="Format summary table and response payload",
                    status="waiting",
                )
            )

        return DynamicPlan(
            task_id=workflow.workflow_id,
            title=workflow.user_query[:32]
            if len(workflow.user_query) <= 32
            else f"{workflow.user_query[:32]}...",
            intent=f"Process {workflow.request_type} query",
            request_type=workflow.request_type,
            steps=steps,
        )

    def create_workflow(
        self,
        prompt: str,
        mode: Optional[str] = None,
        confirmed: bool = False,
    ) -> WorkflowState:
        workflow_id = f"WF-{uuid.uuid4().hex[:6].upper()}"

        # Resolve mode & request_type
        if mode:
            mode_clean = str(mode).lower().strip()
            if mode_clean in ("modify", "write", "mutation"):
                resolved_mode = "modify"
                request_type = "write"
            elif mode_clean in ("explore", "read", "view", "query"):
                resolved_mode = "explore"
                request_type = "read"
            elif mode_clean in ("analyze", "analytics", "report", "pulse"):
                resolved_mode = "analyze"
                request_type = "analytics"
            else:
                request_type = self.classify_intent(prompt)
                resolved_mode = (
                    "modify"
                    if request_type == "write"
                    else ("analyze" if request_type == "analytics" else "explore")
                )
        else:
            request_type = self.classify_intent(prompt)
            resolved_mode = (
                "modify"
                if request_type == "write"
                else ("analyze" if request_type == "analytics" else "explore")
            )

        workflow = WorkflowState(
            workflow_id=workflow_id,
            user_query=prompt,
            mode=resolved_mode,
            confirmed=confirmed,
            request_type=request_type,
            status="planning",
        )
        workflow.plan = self.synthesize_plan(workflow)

        # Initial events
        workflow.events.append(
            OrchestrationEvent(
                type="TASK_CREATED",
                task_id=workflow_id,
                timestamp=time.time(),
                message=f"Created task [{resolved_mode} mode]: {prompt}",
            )
        )
        workflow.events.append(
            OrchestrationEvent(
                type="PLAN_UPDATED",
                task_id=workflow_id,
                timestamp=time.time(),
                plan=workflow.plan,
            )
        )
        return workflow

    def execute_workflow(
        self, workflow: WorkflowState, use_crew: bool = False
    ) -> WorkflowState:
        """Executes workflow using CrewAdapter when use_crew=True, or deterministic loop when use_crew=False."""
        if use_crew:
            from app.orchestration.adapter import CrewAdapter

            adapter = CrewAdapter(registry=self.registry)
            return adapter.run_workflow(workflow)

        # Deterministic fallback loop
        workflow.status = "running"

        while workflow.status == "running":
            next_agent = self.determine_next_agent(workflow)

            if next_agent is None:
                # Workflow complete
                workflow.status = "completed"

                output_result = workflow.results.get("output", {})
                result_dict = output_result.get("result", {}) if isinstance(output_result, dict) else {}

                summary_text = (
                    result_dict.get("summary")
                    or (output_result.get("summary") if isinstance(output_result, dict) else None)
                    or f"Successfully executed {workflow.request_type} query"
                )
                query_executed = (
                    result_dict.get("queryExecuted")
                    or workflow.results.get("input", {}).get("sql")
                    or workflow.results.get("db", {}).get("sql")
                )
                output_format = (
                    output_result.get("output_format")
                    or result_dict.get("outputFormat")
                    or result_dict.get("output_format")
                )
                output_file = (
                    output_result.get("output_file")
                    or result_dict.get("outputFile")
                    or result_dict.get("output_file")
                )

                data_raw = result_dict.get("data") or workflow.results.get("db", {}).get("records")
                data = None
                if isinstance(data_raw, list) and data_raw:
                    parsed_records = []
                    for r in data_raw:
                        if isinstance(r, dict):
                            try:
                                parsed_records.append(StudentRecord.model_validate(r))
                            except Exception:
                                pass
                    if parsed_records:
                        data = parsed_records

                metrics_raw = result_dict.get("metrics") or workflow.results.get("analytics", {}).get("metrics")
                metrics = (
                    OrchestrationMetrics.model_validate(metrics_raw)
                    if (isinstance(metrics_raw, dict) and metrics_raw)
                    else None
                )

                db_res = workflow.results.get("db", {})
                req_confirm = bool(db_res.get("requires_confirmation")) if isinstance(db_res, dict) else False
                confirm_details = db_res if req_confirm else None

                exec_summary = {
                    "agents": [
                        {"agent": t.agent, "status": t.status}
                        for t in workflow.task_history
                    ]
                }

                final_res = OrchestrationResult(
                    summary=summary_text,
                    query_executed=query_executed,
                    raw_plan=workflow.plan,
                    output_format=output_format or "text",
                    output_file=output_file,
                    data=data,
                    metrics=metrics,
                    mode=workflow.mode,
                    requires_confirmation=req_confirm,
                    confirmation_details=confirm_details,
                    execution=exec_summary,
                )
                workflow.final_result = final_res

                workflow.events.append(
                    OrchestrationEvent(
                        type="RESULT_READY",
                        task_id=workflow.workflow_id,
                        timestamp=time.time(),
                        result=final_res,
                    )
                )
                break

            # Verify agent exists in registry
            if next_agent not in self.registry.list_agents():
                workflow.status = "failed"
                workflow.events.append(
                    OrchestrationEvent(
                        type="AGENT_FAILED",
                        task_id=workflow.workflow_id,
                        timestamp=time.time(),
                        agent_id="mother",  # Orchestrator reporting failure
                        message=f"Unknown agent: {next_agent}",
                    )
                )
                break

            # Create task
            task = self.task_manager.create_task(
                agent=next_agent,
                objective=f"Execute {next_agent} task for workflow {workflow.workflow_id}",
                input_data={
                    "user_query": workflow.user_query,
                    "mode": workflow.mode,
                    "confirmed": workflow.confirmed,
                    **workflow.results,
                },
                expected_output=f"Completed {next_agent} task",
            )
            workflow.current_task = task


            # Emit AGENT_STARTED
            workflow.events.append(
                OrchestrationEvent(
                    type="AGENT_STARTED",
                    task_id=workflow.workflow_id,
                    timestamp=time.time(),
                    agent_id=next_agent,
                    message=f"Executing {next_agent} agent...",
                )
            )

            # Execute agent
            try:
                agent = self.registry.get(next_agent)
                agent_result = agent.execute(task)
            except Exception as exc:
                self.task_manager.update_task_status(task, "failed")
                workflow.task_history.append(task)
                workflow.status = "failed"
                workflow.events.append(
                    OrchestrationEvent(
                        type="AGENT_FAILED",
                        task_id=workflow.workflow_id,
                        timestamp=time.time(),
                        agent_id=next_agent,
                        message=f"Agent {next_agent} failed: {str(exc)}",
                    )
                )
                break

            if agent_result.status == "completed":
                self.task_manager.update_task_status(task, "completed")
                workflow.task_history.append(task)
                workflow.results[next_agent] = agent_result.result

                # Update step status in plan
                if workflow.plan:
                    updated_steps = []
                    for step in workflow.plan.steps:
                        if step.agent == next_agent:
                            updated_steps.append(
                                PlanStep(
                                    id=step.id,
                                    step_number=step.step_number,
                                    agent=step.agent,
                                    action=step.action,
                                    description=step.description,
                                    status="complete",
                                    live_message=f"{next_agent} agent completed successfully",
                                )
                            )
                        else:
                            updated_steps.append(step)
                    workflow.plan = DynamicPlan(
                        task_id=workflow.plan.task_id,
                        title=workflow.plan.title,
                        intent=workflow.plan.intent,
                        request_type=workflow.plan.request_type,
                        steps=updated_steps,
                    )

                # Emit AGENT_COMPLETED
                workflow.events.append(
                    OrchestrationEvent(
                        type="AGENT_COMPLETED",
                        task_id=workflow.workflow_id,
                        timestamp=time.time(),
                        agent_id=next_agent,
                        message=f"Agent {next_agent} completed successfully",
                    )
                )
            else:
                self.task_manager.update_task_status(task, "failed")
                workflow.task_history.append(task)
                workflow.status = "failed"
                workflow.events.append(
                    OrchestrationEvent(
                        type="AGENT_FAILED",
                        task_id=workflow.workflow_id,
                        timestamp=time.time(),
                        agent_id=next_agent,
                        message=agent_result.error or f"Agent {next_agent} reported failure",
                    )
                )
                break

        if workflow.final_result is None:
            failed_task = next((t for t in workflow.task_history if t.status == "failed"), None)
            err_msg = (
                f"Agent {failed_task.agent} failed during workflow execution."
                if failed_task
                else "Workflow execution failed."
            )
            is_rate_limit = any(
                "rate limit" in str(getattr(e, "message", "")).lower() or "429" in str(getattr(e, "message", ""))
                for e in workflow.events
            )
            err_type = "RATE_LIMITED" if is_rate_limit else "AGENT_EXECUTION_ERROR"
            display_msg = (
                "The AI service rate limit has been reached. Please try again later."
                if is_rate_limit
                else err_msg
            )
            workflow.final_result = OrchestrationResult(
                summary=display_msg,
                query_executed=None,
                raw_plan=workflow.plan,
                output_format="text",
                mode=workflow.mode,
                success=False,
                error_type=err_type,
                execution={
                    "agents": [
                        {"agent": t.agent, "status": t.status}
                        for t in workflow.task_history
                    ]
                },
            )

        return workflow
