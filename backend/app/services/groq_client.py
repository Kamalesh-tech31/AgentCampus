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
) -> Optional[str]:
    """
    Executes a Groq chat completion call with multi-model and multi-key fallback:
    1. For each API key (GROQ_API_KEY, GROQ_API_KEY_2, GROQ_API_KEY_3, GROQ_API_KEY_4):
       Iterates through model fallback chain (llama-3.3-70b-versatile -> llama-3.1-8b-instant -> mixtral-8x7b-32768).
    2. If a model hits a 429 / rate-limit / quota error, tries the next model on the same key first
       (since each model has its own separate rate limits).
    3. If all models on a key are exhausted, tries the next API key.
    4. Logs clearly which key and model served each request.
    5. Raises an explicit error if all options are exhausted (never swallows failures silently).
    """
    import groq

    # Collect all configured GROQ_API_KEY environment variables
    keys_to_try = []
    for k, v in os.environ.items():
        if k.startswith("GROQ_API_KEY") and v.strip():
            keys_to_try.append((k, v.strip()))

    keys_to_try.sort(key=lambda x: x[0])

    if not keys_to_try:
        logger.warning("[GroqFallback] No Groq API keys configured in environment.")
        raise RuntimeError("GROQ_API_KEY not configured in environment.")

    primary_model = model or os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    models_to_try = [primary_model]
    for m in GROQ_MODEL_FALLBACK_CHAIN:
        if m not in models_to_try:
            models_to_try.append(m)

    for target_model in models_to_try:
        for key_name, api_key in keys_to_try:
            try:
                client = groq.Groq(api_key=api_key)
                logger.info(f"[GroqFallback] Requesting via {key_name} with model={target_model}...")
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
                    logger.info(f"[GroqFallback] Request SUCCESSFULLY SERVED by key={key_name} model={target_model}")
                    return content
            except Exception as exc:
                err_str = str(exc).lower()
                last_error = exc
                if "429" in err_str or "rate limit" in err_str or "quota" in err_str or "tokens per day" in err_str:
                    logger.warning(
                        f"[GroqFallback] {key_name} on model={target_model} hit 429/rate-limit error. Trying next key with model={target_model}..."
                    )
                    continue
                else:
                    logger.error(f"[GroqFallback] Non-rate-limit error on {key_name}/{target_model}: {exc}")
                    continue

    raise RuntimeError(f"All Groq fallback options exhausted across all configured keys and models. Last error: {last_error}")


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
