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
    query = req.get_query()
    mother = MotherAgent()
    workflow = mother.create_workflow(
        prompt=query,
        mode=req.mode,
        confirmed=bool(req.confirmed),
    )
    result_wf = mother.execute_workflow(workflow)
    return result_wf.final_result


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
