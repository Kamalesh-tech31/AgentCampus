import asyncio
import threading
import time
from queue import Queue as ThreadQueue, Empty
from typing import Optional, AsyncGenerator
from app.mother.state import WorkflowState
from app.orchestration.crew_flow import AgentCampusFlow
from app.agents.registry import AgentRegistry
from app.contracts import (
    DynamicPlan,
    PlanStep,
    OrchestrationEvent,
    OrchestrationResult,
    StudentRecord,
    OrchestrationMetrics,
)


def _build_final_result(workflow: WorkflowState) -> OrchestrationResult:
    """Build a contract-compliant OrchestrationResult from completed workflow results."""
    output_raw = workflow.results.get("output", {})
    # OutputAgent places the full OrchestrationResult dict under "result" key
    result_dict = output_raw.get("result", {})

    summary = result_dict.get("summary") or output_raw.get(
        "summary",
        f"Successfully executed {workflow.request_type} query via CrewAI Flow",
    )
    query_executed = (
        result_dict.get("queryExecuted")
        or workflow.results.get("db", {}).get("sql")
    )
    affected_count = result_dict.get("affectedCount")

    # Parse validated StudentRecord list if present
    data_raw = result_dict.get("data", [])
    data = [StudentRecord.model_validate(r) for r in data_raw] if data_raw else None

    # Parse OrchestrationMetrics if analytics ran
    metrics_raw = result_dict.get("metrics")
    metrics = OrchestrationMetrics.model_validate(metrics_raw) if metrics_raw else None

    # Update plan steps to "complete"
    if workflow.plan:
        executed = {t.agent for t in workflow.task_history if t.status == "completed"}
        updated_steps = []
        for step in workflow.plan.steps:
            if step.agent in executed:
                updated_steps.append(
                    PlanStep(
                        id=step.id,
                        step_number=step.step_number,
                        agent=step.agent,
                        action=step.action,
                        description=step.description,
                        status="complete",
                        live_message=f"{step.agent} completed via CrewAI Flow",
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

    return OrchestrationResult(
        summary=summary,
        query_executed=query_executed,
        affected_count=affected_count,
        data=data,
        metrics=metrics,
        raw_plan=workflow.plan,
    )


class CrewAdapter:
    """Internal adapter executing MotherAgent's WorkflowState using CrewAI AgentCampusFlow."""

    def __init__(self, registry: Optional[AgentRegistry] = None):
        self.registry = registry or AgentRegistry()

    def run_workflow(self, workflow: WorkflowState) -> WorkflowState:
        """Non-streaming: run full CrewAI Flow, collect events, return completed WorkflowState."""
        workflow.status = "running"
        flow = AgentCampusFlow(workflow=workflow, registry=self.registry)

        # Batch AGENT_STARTED events before execution
        for step in workflow.plan.steps if workflow.plan else []:
            workflow.events.append(
                OrchestrationEvent(
                    type="AGENT_STARTED",
                    task_id=workflow.workflow_id,
                    timestamp=time.time(),
                    agent_id=step.agent,
                    message=f"Executing {step.agent} agent via CrewAI Flow...",
                )
            )

        flow.kickoff()

        failed_tasks = [t for t in workflow.task_history if t.status == "failed"]
        if failed_tasks:
            workflow.status = "failed"
            workflow.events.append(
                OrchestrationEvent(
                    type="AGENT_FAILED",
                    task_id=workflow.workflow_id,
                    timestamp=time.time(),
                    agent_id=failed_tasks[0].agent,
                    message=f"Task {failed_tasks[0].agent} failed during CrewAI Flow execution",
                )
            )
            return workflow

        workflow.status = "completed"

        for t in workflow.task_history:
            if t.status == "completed":
                workflow.events.append(
                    OrchestrationEvent(
                        type="AGENT_COMPLETED",
                        task_id=workflow.workflow_id,
                        timestamp=time.time(),
                        agent_id=t.agent,
                        message=f"Agent {t.agent} completed successfully",
                    )
                )

        final_res = _build_final_result(workflow)
        workflow.final_result = final_res
        workflow.events.append(
            OrchestrationEvent(
                type="RESULT_READY",
                task_id=workflow.workflow_id,
                timestamp=time.time(),
                result=final_res,
            )
        )
        return workflow

    async def run_workflow_streaming(
        self, workflow: WorkflowState
    ) -> AsyncGenerator[OrchestrationEvent, None]:
        """
        Streaming: yields OrchestrationEvent objects incrementally as each agent
        step executes inside AgentCampusFlow running in a background thread.
        No CrewAI types escape this method — only contract OrchestrationEvent objects are yielded.
        """
        # Yield initial events already queued by MotherAgent (TASK_CREATED, PLAN_UPDATED)
        for event in workflow.events:
            yield event

        workflow.status = "running"
        event_queue: ThreadQueue = ThreadQueue()

        flow = AgentCampusFlow(
            workflow=workflow,
            registry=self.registry,
            event_queue=event_queue,
        )

        # Run CrewAI Flow kickoff in a daemon thread
        def run_flow():
            try:
                flow.kickoff()
            except Exception as exc:
                event_queue.put(
                    OrchestrationEvent(
                        type="AGENT_FAILED",
                        task_id=workflow.workflow_id,
                        timestamp=time.time(),
                        message=f"CrewAI Flow error: {exc}",
                    )
                )
            finally:
                event_queue.put(None)  # Sentinel — signals completion to async reader

        thread = threading.Thread(target=run_flow, daemon=True)
        thread.start()

        # Yield events from the queue as they arrive from the running flow thread
        while True:
            try:
                item = event_queue.get_nowait()
                if item is None:
                    break
                yield item
            except Empty:
                await asyncio.sleep(0.05)

        thread.join(timeout=60)

        # Check for failures
        failed_tasks = [t for t in workflow.task_history if t.status == "failed"]
        if failed_tasks:
            workflow.status = "failed"
            yield OrchestrationEvent(
                type="AGENT_FAILED",
                task_id=workflow.workflow_id,
                timestamp=time.time(),
                agent_id=failed_tasks[0].agent,
                message=f"Agent {failed_tasks[0].agent} failed during execution",
            )
            return

        # Build and yield the final RESULT_READY event
        workflow.status = "completed"
        final_res = _build_final_result(workflow)
        workflow.final_result = final_res

        yield OrchestrationEvent(
            type="RESULT_READY",
            task_id=workflow.workflow_id,
            timestamp=time.time(),
            result=final_res,
        )
