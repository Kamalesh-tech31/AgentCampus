import time
import logging
from typing import Dict, Optional
from app.db.schema_registry import get_live_schema

logger = logging.getLogger(__name__)

_columns_cache: Dict[str, Dict[str, str]] = {}
_cache_timestamps: Dict[str, float] = {}
CACHE_TTL_SECONDS: float = 300.0  # 5-minute TTL cache for column discovery


def get_table_columns(table_name: str, force_refresh: bool = False) -> Dict[str, str]:
    """
    Returns column_name -> data_type mapping for table_name from live database schema.
    Caches in memory with a 5-minute TTL (300s). Supports force_refresh=True.
    Case-insensitive / singular-plural tolerant table name matching against live schema.
    """
    now = time.time()

    if not force_refresh and table_name in _columns_cache:
        if now - _cache_timestamps.get(table_name, 0.0) < CACHE_TTL_SECONDS:
            return _columns_cache[table_name]

    # Fetch live schema from schema_registry
    live_schema = get_live_schema(force_refresh=force_refresh)

    # 1. Direct match
    if table_name in live_schema:
        cols = dict(live_schema[table_name])
        _columns_cache[table_name] = cols
        _cache_timestamps[table_name] = now
        return cols

    # 2. Case-insensitive / singular-plural tolerant matching against live_schema keys
    table_lower = table_name.lower().rstrip("s")
    for tbl, cols in live_schema.items():
        if tbl.lower().rstrip("s") == table_lower:
            matched_cols = dict(cols)
            _columns_cache[table_name] = matched_cols
            _cache_timestamps[table_name] = now
            return matched_cols

    return {}


def invalidate_columns_cache() -> None:
    """Invalidates the 5-minute column discovery cache."""
    global _columns_cache, _cache_timestamps
    _columns_cache.clear()
    _cache_timestamps.clear()
    logger.info("[Schema] Column discovery cache invalidated.")
