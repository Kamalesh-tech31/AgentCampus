from typing import AsyncGenerator, Dict, Any, Optional
from fastapi import APIRouter
from fastapi.responses import StreamingResponse, JSONResponse
from app.contracts.orchestration import OrchestrationRequest, OrchestrationResult
from app.mother.mother_agent import MotherAgent
from app.orchestration.adapter import CrewAdapter

router = APIRouter(prefix="/orchestrate", tags=["orchestration"])


@router.post("", response_model=OrchestrationResult)
def orchestrate_sync(req: OrchestrationRequest):
    """
    Synchronous orchestration endpoint for frontend 3-mode integration:
    - Mode: modify | explore | analyze
    - Returns structured execution tracking, result, output format/file, and confirmation state.
    """
    try:
        query = req.get_query()
        mother = MotherAgent()
        workflow = mother.create_workflow(
            prompt=query,
            mode=req.mode,
            confirmed=bool(req.confirmed),
        )
        result_wf = mother.execute_workflow(workflow)
        if result_wf.final_result is None:
            return OrchestrationResult(
                summary="Workflow executed but returned no result.",
                success=False,
                error_type="INTERNAL_SERVER_ERROR",
                mode=req.mode,
                output_format="text",
            )
        return result_wf.final_result
    except Exception as exc:
        err_str = str(exc)
        is_rate_limit = "429" in err_str or "rate limit" in err_str.lower() or "quota" in err_str.lower()
        err_type = "RATE_LIMITED" if is_rate_limit else "INTERNAL_SERVER_ERROR"
        msg = (
            "The AI service rate limit has been reached. Please try again later."
            if is_rate_limit
            else f"Request processing error: {err_str}"
        )
        return OrchestrationResult(
            summary=msg,
            success=False,
            error_type=err_type,
            mode=req.mode,
            output_format="text",
        )


async def _sse_event_generator(
    prompt: str,
    mode: Optional[str] = None,
    confirmed: bool = False,
) -> AsyncGenerator[str, None]:
    """
    Production SSE pipeline:
    MotherAgent → DynamicPlan → CrewAdapter → AgentCampusFlow → Agents → OrchestrationEvents → SSE
    No CrewAI types escape this function — only contract JSON strings.
    """
    mother = MotherAgent()
    adapter = CrewAdapter()
    workflow = mother.create_workflow(
        prompt=prompt,
        mode=mode,
        confirmed=confirmed,
    )

    async for event in adapter.run_workflow_streaming(workflow):
        yield f"data: {event.model_dump_json(by_alias=True)}\n\n"


@router.post("/stream")
async def orchestrate_stream(req: OrchestrationRequest):
    """
    Server-Sent Events (SSE) streaming orchestration endpoint with real-time agent events.
    """
    query = req.get_query()
    return StreamingResponse(
        _sse_event_generator(
            prompt=query,
            mode=req.mode,
            confirmed=bool(req.confirmed),
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
