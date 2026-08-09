from typing import AsyncGenerator
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from app.contracts.orchestration import OrchestrationRequest
from app.mother.mother_agent import MotherAgent
from app.orchestration.adapter import CrewAdapter

router = APIRouter(prefix="/orchestrate", tags=["orchestration"])


async def _sse_event_generator(prompt: str) -> AsyncGenerator[str, None]:
    """
    Production SSE pipeline:
    MotherAgent → DynamicPlan → CrewAdapter → AgentCampusFlow → Agents → OrchestrationEvents → SSE
    No CrewAI types escape this function — only contract JSON strings.
    """
    # Step 1: MotherAgent is the sole authority for intent classification and plan synthesis via Groq LLM
    mother = MotherAgent()
    adapter = CrewAdapter()
    workflow = mother.create_workflow(prompt)

    # Step 2: CrewAdapter drives AgentCampusFlow using the authoritative DynamicPlan
    async for event in adapter.run_workflow_streaming(workflow):
        yield f"data: {event.model_dump_json(by_alias=True)}\n\n"


@router.post("/stream")
async def orchestrate_stream(req: OrchestrationRequest):
    return StreamingResponse(
        _sse_event_generator(req.prompt),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
