import os
import logging
from dotenv import load_dotenv

# Load environment variables from .env file at application startup
load_dotenv()

from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from app.api import health, students, orchestrate, database, files

logger = logging.getLogger(__name__)

def _log_api_key_diagnostics():
    input_key_ok = bool(os.getenv("INPUT_GROQ_API_KEY"))
    input_model = os.getenv("INPUT_GROQ_MODEL", "qwen/qwen3.6-27b")

    mother_key_ok = bool(os.getenv("MOTHER_GROQ_API_KEY"))
    mother_model = os.getenv("MOTHER_GROQ_MODEL", "llama-3.3-70b-versatile")

    db_key_ok = bool(os.getenv("DB_GROQ_API_KEY"))
    db_fallbacks = [k for k, v in os.environ.items() if k.startswith("DB_GROQ_API_KEY_") and v.strip()]
    db_model = os.getenv("DB_GROQ_MODEL", "llama-3.3-70b-versatile")

    pulse_key_ok = bool(os.getenv("PULSE_GROQ_API_KEY"))
    pulse_model = os.getenv("PULSE_GROQ_MODEL", "llama-3.3-70b-versatile")

    scribe_key_ok = bool(os.getenv("SCRIBE_GROQ_API_KEY"))
    scribe_model = os.getenv("SCRIBE_GROQ_MODEL", "llama-3.3-70b-versatile")

    logger.info("[AgentCampus] API Key Configuration Diagnostics:")
    logger.info(f"  Input:  API Key: {'CONFIGURED' if input_key_ok else 'MISSING'}, Model: {input_model}")
    logger.info(f"  Mother: API Key: {'CONFIGURED' if mother_key_ok else 'MISSING'}, Model: {mother_model}")
    logger.info(f"  DB:     Primary Key: {'CONFIGURED' if db_key_ok else 'MISSING'}, Fallback Keys: {len(db_fallbacks)} configured, Model: {db_model}")
    logger.info(f"  Pulse:  API Key: {'CONFIGURED' if pulse_key_ok else 'MISSING'}, Model: {pulse_model}")
    logger.info(f"  Scribe: API Key: {'CONFIGURED' if scribe_key_ok else 'MISSING'}, Model: {scribe_model}")

_log_api_key_diagnostics()

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
api_router.include_router(database.router)
api_router.include_router(files.router)

app.include_router(api_router)

