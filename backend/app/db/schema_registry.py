import os
import time
import logging
from typing import Dict, Any, Optional
import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

_live_schema_cache: Optional[Dict[str, Dict[str, str]]] = None
_cache_timestamp: float = 0.0
CACHE_TTL_SECONDS: float = 120.0  # 2-minute in-memory cache


def get_live_schema(force_refresh: bool = False) -> Dict[str, Dict[str, str]]:
    """
    Queries live database schema (via Supabase OpenAPI specification / information_schema).
    Caches the schema in memory for ~2 minutes (CACHE_TTL_SECONDS).
    Returns a mapping of table_name -> {column_name: column_type}.
    """
    global _live_schema_cache, _cache_timestamp

    now = time.time()
    if not force_refresh and _live_schema_cache is not None and (now - _cache_timestamp < CACHE_TTL_SECONDS):
        return _live_schema_cache

    supabase_url = os.getenv("SUPABASE_URL", "")
    supabase_key = os.getenv("SUPABASE_KEY", "")

    if not supabase_url or not supabase_key:
        logger.warning("[SchemaRegistry] SUPABASE_URL or SUPABASE_KEY missing; using empty schema.")
        return {}

    try:
        url = f"{supabase_url.rstrip('/')}/rest/v1/"
        headers = {
            "apiKey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
        }
        response = httpx.get(url, headers=headers, timeout=10.0)

        if response.status_code != 200:
            logger.error(f"[SchemaRegistry] Failed to fetch OpenAPI schema: HTTP {response.status_code}")
            return _live_schema_cache or {}

        spec = response.json()
        definitions = spec.get("definitions", {})

        schema: Dict[str, Dict[str, str]] = {}
        for table_name, table_def in definitions.items():
            properties = table_def.get("properties", {})
            table_fields: Dict[str, str] = {}
            for col_name, col_props in properties.items():
                col_type = col_props.get("format") or col_props.get("type") or "text"
                table_fields[col_name] = col_type
            schema[table_name] = table_fields

        _live_schema_cache = schema
        _cache_timestamp = now
        logger.info(f"[SchemaRegistry] Live schema updated ({len(schema)} tables discovered: {list(schema.keys())})")
        return schema

    except Exception as exc:
        logger.error(f"[SchemaRegistry] Exception fetching live schema: {exc}")
        return _live_schema_cache or {}


def invalidate_schema_cache() -> None:
    """Invalidates the in-memory schema cache so the next call fetches fresh schema."""
    global _live_schema_cache, _cache_timestamp
    _live_schema_cache = None
    _cache_timestamp = 0.0
    logger.info("[SchemaRegistry] In-memory schema cache invalidated.")


def get_known_fields(table: str) -> Dict[str, str]:
    """
    Returns dictionary of fields and types for table from live schema.
    Raises ValueError if table is not found in live schema.
    """
    schema = get_live_schema()
    if table not in schema:
        raise ValueError(
            f"Table '{table}' is not registered in the database schema. "
            f"Available tables: {list(schema.keys())}"
        )
    return schema[table]
