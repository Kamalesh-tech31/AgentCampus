import os
import logging
from typing import Callable, Any, Optional, Dict
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Fallback sequence of models (each model has independent quota limits on Groq)
GROQ_MODEL_FALLBACK_CHAIN = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "mixtral-8x7b-32768",
]


def call_groq_completion(
    messages: list,
    model: Optional[str] = None,
    response_format: Optional[Dict[str, str]] = None,
    temperature: float = 0.0,
    api_key_env_prefix: str = "DB_GROQ_API_KEY",
) -> Optional[str]:
    """
    Executes a Groq chat completion call with multi-model and multi-key fallback:
    1. Collects primary key and fallback keys for api_key_env_prefix (e.g. DB_GROQ_API_KEY, DB_GROQ_API_KEY_1..4).
    2. Deduplicates identical secret values to prevent redundant retry attempts.
    3. Iterates through fallback chain (models and keys) logging safe key variable names.
    4. Distinguishes HTTP 429 rate limits from HTTP 401 authentication errors.
    5. Returns immediately on first successful response; raises explicit RuntimeError if all options fail.
    """
    import groq

    # Collect configured API keys for specified prefix (e.g. DB_GROQ_API_KEY, DB_GROQ_API_KEY_1..4)
    keys_to_try = []
    
    primary_key = os.getenv(api_key_env_prefix)
    if primary_key and primary_key.strip():
        keys_to_try.append((api_key_env_prefix, primary_key.strip()))

    fallback_keys = []
    prefix_underscore = f"{api_key_env_prefix}_"
    for k, v in os.environ.items():
        if k.startswith(prefix_underscore) and v.strip():
            fallback_keys.append((k, v.strip()))

    fallback_keys.sort(key=lambda x: x[0])
    for item in fallback_keys:
        if item not in keys_to_try:
            keys_to_try.append(item)

    # Deduplicate keys by actual secret value so identical key strings are not redundantly retried
    seen_values = set()
    deduped_keys = []
    for item in keys_to_try:
        if item[1] not in seen_values:
            seen_values.add(item[1])
            deduped_keys.append(item)
    keys_to_try = deduped_keys

    if not keys_to_try:
        logger.warning(f"[GroqFallback] No Groq API keys configured in environment for prefix '{api_key_env_prefix}'.")
        raise RuntimeError(f"{api_key_env_prefix} not configured in environment.")

    model_env_var = api_key_env_prefix.replace("API_KEY", "MODEL")
    primary_model = model or os.getenv(model_env_var) or os.getenv("DB_GROQ_MODEL", "llama-3.3-70b-versatile")
    models_to_try = [primary_model]
    for m in GROQ_MODEL_FALLBACK_CHAIN:
        if m not in models_to_try:
            models_to_try.append(m)

    attempt_num = 0
    last_error = None

    for target_model in models_to_try:
        for key_name, api_key in keys_to_try:
            attempt_num += 1
            try:
                client = groq.Groq(api_key=api_key)
                logger.info(f"[GroqFallback] Attempt {attempt_num} requesting via env_var={key_name} with model={target_model}...")
                kwargs = {
                    "model": target_model,
                    "messages": messages,
                    "temperature": temperature,
                }
                if response_format:
                    kwargs["response_format"] = response_format

                response = client.chat.completions.create(**kwargs)
                content = response.choices[0].message.content
                if content:
                    logger.info(f"[GroqFallback] Attempt {attempt_num} SUCCESSFULLY SERVED by env_var={key_name} model={target_model}")
                    return content
            except Exception as exc:
                err_str = str(exc).lower()
                last_error = exc
                if "401" in err_str or "auth" in err_str or "invalid_api_key" in err_str or "invalid api key" in err_str:
                    logger.warning(f"[GroqFallback] Attempt {attempt_num} using env_var={key_name} failed with HTTP 401 Auth Error. Skipping key.")
                    continue
                elif "429" in err_str or "rate limit" in err_str or "quota" in err_str or "tokens per day" in err_str:
                    logger.warning(
                        f"[GroqFallback] Attempt {attempt_num} using env_var={key_name} model={target_model} failed with HTTP 429 Rate-Limit/Quota. Trying next key..."
                    )
                    continue
                else:
                    logger.error(f"[GroqFallback] Attempt {attempt_num} using env_var={key_name} model={target_model} failed with Error: {exc}")
                    continue

    raise RuntimeError(f"All Groq fallback options exhausted across all configured keys and models for '{api_key_env_prefix}'. Last error: {last_error}")


def with_groq_fallback(func: Callable) -> Callable:
    """
    Decorator wrapper that catches rate limit / 429 errors from Groq API calls
    and retries with multi-model and multi-key fallback.
    """
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as exc:
            err_str = str(exc).lower()
            if "429" in err_str or "rate limit" in err_str or "quota" in err_str or "tokens per day" in err_str:
                logger.warning(f"[GroqFallbackDecorator] Rate limit hit. Retrying function with multi-model/key failover...")
                return func(*args, **kwargs)
            raise exc
    return wrapper
