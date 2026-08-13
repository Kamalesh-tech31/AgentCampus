import logging
from typing import Dict, List, Any, Tuple, Optional
from app.db.client import supabase
from app.db.schema_registry import get_live_schema, get_known_fields

logger = logging.getLogger(__name__)

ALLOWED_OPERATORS = {"eq", "neq", "gt", "gte", "lt", "lte", "like", "ilike"}
ALLOWED_AGGREGATES = {"average", "sum", "min", "max"}
NUMERIC_TYPES = {
    "numeric", "int", "integer", "int2", "int4", "int8", "int32", "int64",
    "float", "float4", "float8", "number", "double", "double precision",
    "real", "smallint", "bigint", "decimal"
}


def _is_numeric_column_type(raw_type: str) -> bool:
    """Checks if a database schema column type belongs to the numeric family."""
    t = str(raw_type).lower()
    if t in NUMERIC_TYPES:
        return True
    return any(sub in t for sub in ("int", "num", "float", "double", "real", "dec", "small", "big"))


def generic_filter(
    table: str,
    filters: List[Dict[str, Any]],
    limit: Optional[int] = None,
) -> Tuple[List[Dict[str, Any]], bool, int]:
    """
    Executes a filtered select query on table:
    1. Validates table exists in live schema.
    2. Validates every filter field and operator.
    3. Executes query with select('*', count='exact').
    4. Returns tuple: (matching_records, is_truncated, total_count).
    """
    known_fields = get_known_fields(table)
    query = supabase.table(table).select("*", count="exact")

    for f in filters:
        field = f.get("field")
        op = f.get("op", "eq")
        val = f.get("value")

        if not field or field not in known_fields:
            raise ValueError(
                f"Field '{field}' is not a registered field for table '{table}'. "
                f"Allowed fields: {list(known_fields.keys())}"
            )

        if op not in ALLOWED_OPERATORS:
            raise ValueError(
                f"Filter operator '{op}' is not allowed. "
                f"Allowed operators: {sorted(list(ALLOWED_OPERATORS))}"
            )

        filter_func = getattr(query, op)
        query = filter_func(field, val)

    if limit is not None:
        query = query.limit(limit)

    response = query.execute()
    data = response.data or []
    total = response.count if response.count is not None else len(data)
    truncated = (total > len(data))

    return data, truncated, total


def generic_get_all(
    table: str, limit: Optional[int] = None
) -> Tuple[List[Dict[str, Any]], bool, int]:
    """
    Executes an unfiltered select query on table using select('*', count='exact').
    Returns tuple: (all_records, is_truncated, total_count).
    """
    get_known_fields(table)  # Validates table exists
    query = supabase.table(table).select("*", count="exact")

    if limit is not None:
        query = query.limit(limit)

    response = query.execute()
    data = response.data or []
    total = response.count if response.count is not None else len(data)
    truncated = (total > len(data))

    return data, truncated, total


def compute_filter(
    table: str,
    fields: List[str],
    aggregate: str,
    condition: Dict[str, Any],
    filters: Optional[List[Dict[str, Any]]] = None,
    limit: Optional[int] = None,
) -> Tuple[List[Dict[str, Any]], bool, int]:
    """
    Executes a computed filter on table rows:
    1. Validates every field in fields exists and is numeric via get_live_schema().
    2. Validates aggregate is in ALLOWED_AGGREGATES (average, sum, min, max).
    3. Fetches rows using count='exact'.
    4. Computes aggregate value per row in Python.
    5. Filters computed rows by condition.
    Returns tuple: (matching_computed_rows, is_truncated, total_count).
    """
    live_schema = get_live_schema(force_refresh=True)
    if table not in live_schema:
        raise ValueError(f"Table '{table}' does not exist in live database schema.")

    table_schema = live_schema[table]

    if not fields:
        raise ValueError("compute_filter requires at least one field in 'fields'.")

    # Re-validate every field in fields exists and is numeric across all Postgres numeric types
    for f in fields:
        if f not in table_schema:
            available_fields = [k for k, v in table_schema.items() if _is_numeric_column_type(str(v))]
            raise ValueError(
                f"Field '{f}' does not exist in table '{table}'. "
                f"Available numeric fields for compute_filter: {available_fields}"
            )
        field_type = str(table_schema[f]).lower()
        if not _is_numeric_column_type(field_type):
            raise ValueError(
                f"Field '{f}' in table '{table}' is of type '{field_type}', which is not numeric and cannot be aggregated."
            )

    if aggregate not in ALLOWED_AGGREGATES:
        raise ValueError(
            f"Aggregate '{aggregate}' is invalid. Allowed aggregates: {sorted(list(ALLOWED_AGGREGATES))}"
        )

    op = condition.get("op", "eq")
    target_val = condition.get("value")
    if op not in ALLOWED_OPERATORS:
        raise ValueError(
            f"Condition operator '{op}' is invalid. Allowed operators: {sorted(list(ALLOWED_OPERATORS))}"
        )

    # Fetch initial matching rows using count='exact'
    query = supabase.table(table).select("*", count="exact")
    if filters:
        for f in filters:
            f_field = f.get("field")
            f_op = f.get("op", "eq")
            f_val = f.get("value")
            if f_field and f_field in table_schema and f_op in ALLOWED_OPERATORS:
                filter_func = getattr(query, f_op)
                query = filter_func(f_field, f_val)

    if limit is not None:
        query = query.limit(limit)

    response = query.execute()
    raw_rows = response.data or []
    total = response.count if response.count is not None else len(raw_rows)
    truncated = (total > len(raw_rows))

    matching_computed_rows = []
    for row in raw_rows:
        row_vals = []
        for f in fields:
            v = row.get(f)
            if v is not None:
                try:
                    row_vals.append(float(v))
                except (ValueError, TypeError):
                    pass

        if not row_vals:
            continue

        if aggregate == "average":
            computed_val = sum(row_vals) / len(row_vals)
        elif aggregate == "sum":
            computed_val = sum(row_vals)
        elif aggregate == "min":
            computed_val = min(row_vals)
        elif aggregate == "max":
            computed_val = max(row_vals)

        # Check condition
        match = False
        if op == "gt" and computed_val > target_val: match = True
        elif op == "gte" and computed_val >= target_val: match = True
        elif op == "lt" and computed_val < target_val: match = True
        elif op == "lte" and computed_val <= target_val: match = True
        elif op == "eq" and computed_val == target_val: match = True
        elif op == "neq" and computed_val != target_val: match = True

        if match:
            computed_row = dict(row)
            computed_row["_computed"] = round(computed_val, 2)
            matching_computed_rows.append(computed_row)

    return matching_computed_rows, truncated, total


def generic_weighted_compute(
    table: str,
    weights: List[Dict[str, Any]],
    filters: Optional[List[Dict[str, Any]]] = None,
    sort: str = "desc",
    limit: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Executes an empirical relative weighted composite computation across rows in table:
    1. Validates table and numeric fields against live schema.
    2. Enforces strict weight-sum constraint (|sum(weights) - 1.0| <= 0.01).
    3. Fetches target rows using count='exact'.
    4. Option A Exclusion Strategy: Filters out rows with missing/null values in component fields and counts excluded_count.
    5. Approach 1 Empirical Query-Time Min/Max Normalization: Computes empirical min and max for each field across returned rows.
       Scores are relative rankings derived strictly from the actual rows returned for that query.
    6. Calculates relative composite score per row: sum(weight_i * normalized_val_i).
    7. Sorts and returns matching records with _weighted_score, excluded_count, and audit message.
    """
    live_schema = get_live_schema(force_refresh=True)
    if table not in live_schema:
        raise ValueError(f"Table '{table}' does not exist in live schema.")

    known_cols = live_schema[table]

    if not weights or not isinstance(weights, list):
        raise ValueError("weighted_compute requires a non-empty list of 'weights' objects.")

    # 1. Strict weight-sum validation (absolute weight contributions must sum to 1.00)
    total_weight = sum(abs(float(w.get("weight", 0.0))) for w in weights if isinstance(w, dict))
    if abs(total_weight - 1.0) > 0.01:
        raise ValueError(
            f"Invalid weight configuration: Weights sum to {total_weight:.2f} ({total_weight*100:.0f}%), not 1.00 (100%). Please adjust weights so they sum to 100%."
        )

    # Validate weight fields exist and are numeric
    weight_fields = []
    for w in weights:
        if not isinstance(w, dict):
            continue
        f = w.get("field")
        if not f or f not in known_cols:
            raise ValueError(f"Specified field '{f}' does not exist in table '{table}'. Only registered numeric fields can be weighted.")
        if not _is_numeric_column_type(str(known_cols[f])):
            raise ValueError(f"Field '{f}' in table '{table}' is of type '{known_cols[f]}', which is not numeric and cannot be weighted.")
        weight_fields.append(f)

    # 2. Fetch rows via generic_filter or generic_get_all
    if filters:
        raw_rows, truncated, total_count = generic_filter(table, filters, limit=None)
    else:
        raw_rows, truncated, total_count = generic_get_all(table, limit=None)

    if not raw_rows:
        return {
            "success": True,
            "data": [],
            "excluded_count": 0,
            "total": 0,
            "truncated": False,
            "message": f"No rows returned from table '{table}' for weighted computation.",
        }

    # 3. Option A Exclusion Strategy: Filter out rows missing any weighted field
    valid_rows = []
    excluded_count = 0
    for row in raw_rows:
        has_all_fields = True
        for f in weight_fields:
            val = row.get(f)
            if val is None or str(val).strip() == "":
                has_all_fields = False
                break
        if has_all_fields:
            valid_rows.append(row)
        else:
            excluded_count += 1

    if not valid_rows:
        return {
            "success": True,
            "data": [],
            "excluded_count": excluded_count,
            "total": total_count,
            "truncated": False,
            "message": f"All {total_count} rows were excluded due to missing data in weighted fields ({', '.join(weight_fields)}).",
        }

    # 4. Approach 1 Empirical Query-Time Min/Max Normalization (relative to filtered result set)
    empirical_bounds = {}
    for f in weight_fields:
        field_vals = [float(r[f]) for r in valid_rows]
        min_v = min(field_vals)
        max_v = max(field_vals)
        range_v = (max_v - min_v) if (max_v - min_v) != 0 else 1.0
        empirical_bounds[f] = {"min": min_v, "max": max_v, "range": range_v}

    # 5. Compute relative composite score per valid row
    computed_records = []
    for row in valid_rows:
        composite_score = 0.0
        for w in weights:
            f = w["field"]
            weight = float(w["weight"])
            val = float(row[f])
            bounds = empirical_bounds[f]

            if bounds["range"] > 0:
                normalized_val = (val - bounds["min"]) / bounds["range"]
            else:
                normalized_val = 1.0

            composite_score += weight * normalized_val

        r_copy = dict(row)
        r_copy["_weighted_score"] = round(composite_score, 4)
        computed_records.append(r_copy)

    # 6. Sort records by _weighted_score
    reverse_sort = True if sort.lower() == "desc" else False
    computed_records.sort(key=lambda r: r["_weighted_score"], reverse=reverse_sort)

    if limit is not None and len(computed_records) > limit:
        computed_records = computed_records[:limit]

    msg = f"Computed relative weighted scores for {len(computed_records)} rows in '{table}'"
    if excluded_count > 0:
        msg += f" ({excluded_count} rows excluded due to missing field data)."
    else:
        msg += "."

    return {
        "success": True,
        "data": computed_records,
        "excluded_count": excluded_count,
        "total": total_count,
        "truncated": truncated,
        "message": msg,
    }
