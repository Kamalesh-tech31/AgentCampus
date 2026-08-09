import os
import logging
from dotenv import load_dotenv

# Load environment variables from .env file at application startup
load_dotenv()

from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from app.api import health, students, orchestrate

logger = logging.getLogger(__name__)
logger.info(f"[AgentCampus] Startup — GROQ_API_KEY configured: {bool(os.getenv('GROQ_API_KEY'))}")

app = FastAPI(
    title="AgentCampus Backend API",
    description="Backend API for AgentCampus multi-agent orchestration",
    version="0.1.0",
)

# CORS configuration allowing local frontend requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Aggregate all API routers under /api prefix
api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(students.router)
api_router.include_router(orchestrate.router)

app.include_router(api_router)
