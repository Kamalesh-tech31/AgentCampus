"""
test_db_fallback_mock.py — Deterministic mocked tests for DB Agent Groq multi-key fallback.

Simulates:
1. DB_GROQ_API_KEY -> 429, DB_GROQ_API_KEY_1 -> SUCCESS
2. key1 -> 429, key2 -> 429, key3 -> SUCCESS
3. all keys -> 429 -> returns clear quota/rate-limit failure.
Does NOT make any real API requests or consume LLM quota.
"""

import os
from unittest.mock import patch, MagicMock
import pytest
from app.services.groq_client import call_groq_completion


def test_fallback_advances_from_key0_to_key1_on_429():
    """Scenario 1: primary DB_GROQ_API_KEY returns 429; DB_GROQ_API_KEY_1 succeeds."""
    env = {
        "DB_GROQ_API_KEY": "secret-key-0",
        "DB_GROQ_API_KEY_1": "secret-key-1",
        "DB_GROQ_MODEL": "llama-3.3-70b-versatile",
    }
    with patch.dict(os.environ, env, clear=True):
        with patch("groq.Groq") as mock_groq:
            client0 = MagicMock()
            client0.chat.completions.create.side_effect = Exception("429 rate limit exceeded")
            
            client1 = MagicMock()
            mock_resp = MagicMock()
            mock_resp.choices = [MagicMock()]
            mock_resp.choices[0].message.content = '{"action": "bulk_update", "table": "students", "params": {"field": "cgpa", "operation": "subtract", "value": 1}}'
            client1.chat.completions.create.return_value = mock_resp

            def client_factory(api_key):
                if api_key == "secret-key-0":
                    return client0
                elif api_key == "secret-key-1":
                    return client1
                return MagicMock()

            mock_groq.side_effect = client_factory

            res = call_groq_completion(messages=[{"role": "user", "content": "Reduce CGPA"}])
            assert res is not None
            assert "bulk_update" in res

            # Verify that client was called with secret-key-0 first, then secret-key-1
            called_keys = [call[1]["api_key"] for call in mock_groq.call_args_list]
            assert "secret-key-0" in called_keys
            assert "secret-key-1" in called_keys


def test_fallback_advances_through_key1_key2_to_key3():
    """Scenario 2: key1 -> 429, key2 -> 429, key3 -> SUCCESS."""
    env = {
        "DB_GROQ_API_KEY": "secret-key-primary",
        "DB_GROQ_API_KEY_1": "secret-key-fb1",
        "DB_GROQ_API_KEY_2": "secret-key-fb2",
        "DB_GROQ_MODEL": "llama-3.3-70b-versatile",
    }
    with patch.dict(os.environ, env, clear=True):
        with patch("groq.Groq") as mock_groq:
            client0 = MagicMock()
            client0.chat.completions.create.side_effect = Exception("429 Rate limit reached")
            client1 = MagicMock()
            client1.chat.completions.create.side_effect = Exception("429 Quota exhausted")
            
            client2 = MagicMock()
            mock_resp = MagicMock()
            mock_resp.choices = [MagicMock()]
            mock_resp.choices[0].message.content = '{"action": "bulk_update", "table": "students", "params": {"field": "cgpa", "operation": "subtract", "value": 1}}'
            client2.chat.completions.create.return_value = mock_resp

            def client_factory(api_key):
                if api_key == "secret-key-primary":
                    return client0
                elif api_key == "secret-key-fb1":
                    return client1
                elif api_key == "secret-key-fb2":
                    return client2
                return MagicMock()

            mock_groq.side_effect = client_factory

            res = call_groq_completion(messages=[{"role": "user", "content": "Reduce CGPA"}])
            assert res is not None
            assert "bulk_update" in res

            called_keys = [call[1]["api_key"] for call in mock_groq.call_args_list]
            assert called_keys[:3] == ["secret-key-primary", "secret-key-fb1", "secret-key-fb2"]


def test_fallback_all_keys_429_fails_gracefully():
    """Scenario 3: all configured keys return 429 -> raises RuntimeError cleanly."""
    env = {
        "DB_GROQ_API_KEY": "secret-key-primary",
        "DB_GROQ_API_KEY_1": "secret-key-fb1",
        "DB_GROQ_MODEL": "llama-3.3-70b-versatile",
    }
    with patch.dict(os.environ, env, clear=True):
        with patch("groq.Groq") as mock_groq:
            client = MagicMock()
            client.chat.completions.create.side_effect = Exception("429 Rate limit reached")
            mock_groq.return_value = client

            with pytest.raises(RuntimeError) as exc_info:
                call_groq_completion(messages=[{"role": "user", "content": "Reduce CGPA"}])

            assert "All Groq fallback options exhausted" in str(exc_info.value)
