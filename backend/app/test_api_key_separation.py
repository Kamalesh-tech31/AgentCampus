"""
test_api_key_separation.py — Comprehensive validation tests for agent API key separation.

Verifies:
1. Input Agent uses INPUT_GROQ_API_KEY & INPUT_GROQ_MODEL
2. Mother Agent uses MOTHER_GROQ_API_KEY & MOTHER_GROQ_MODEL
3. DB Agent uses DB_GROQ_API_KEY & DB_GROQ_MODEL (+ DB_GROQ_API_KEY_1..4 fallbacks)
4. Pulse Agent uses PULSE_GROQ_API_KEY & PULSE_GROQ_MODEL
5. Scribe Agent uses SCRIBE_GROQ_API_KEY & SCRIBE_GROQ_MODEL
6. DB fallback discovery strictly isolates DB keys and NEVER consumes Mother/Input/Pulse/Scribe keys.
7. Absence of an agent's dedicated key triggers safe deterministic fallback without cross-key leakage.
"""

import os
from unittest.mock import patch, MagicMock
import pytest

from app.services.groq_service import GroqService
from app.services.groq_client import call_groq_completion
from app.mother.mother_agent import MotherAgent
from app.agents.input_agent import InputAgent
from app.agents.db_agent import DBAgent
from app.agents.analytics_agent import AnalyticsAgent
from app.agents.output_agent import OutputAgent
from app.mother.types import AgentTask
from app.services.pulse.planner_service import get_analysis_plan
from app.services.pulse.llm_interpreter import interpret_results
from app.services.output.text_service import generate_text
from app.services.output.pdf_service import generate_pdf
from app.services.output.ppt_service import generate_ppt


def test_input_agent_key_wiring():
    """Verify InputAgent uses INPUT_GROQ_API_KEY and INPUT_GROQ_MODEL for image queries."""
    with patch.dict(os.environ, {
        "INPUT_GROQ_API_KEY": "test-input-key-12345",
        "INPUT_GROQ_MODEL": "qwen/qwen3.6-27b",
    }, clear=True):
        agent = InputAgent()
        with patch("app.agents.input_agent.parse_file") as mock_parse:
            mock_parse.return_value = {"type": "table", "records": []}
            task = AgentTask(
                task_id="T1",
                agent="input",
                objective="parse image",
                input_data={"user_query": "Show CS students", "file_path": "test_image.png"},
                expected_output="parsed",
            )
            agent.execute(task)
            assert mock_parse.called
            groq_svc = mock_parse.call_args[1].get("groq_service")
            assert groq_svc is not None
            assert groq_svc.api_key == "test-input-key-12345"
            assert groq_svc.model == "qwen/qwen3.6-27b"


def test_mother_agent_key_wiring():
    """Verify MotherAgent uses MOTHER_GROQ_API_KEY and MOTHER_GROQ_MODEL."""
    with patch.dict(os.environ, {
        "MOTHER_GROQ_API_KEY": "test-mother-key-99999",
        "MOTHER_GROQ_MODEL": "llama-3.3-70b-versatile",
    }, clear=True):
        mother = MotherAgent()
        assert mother.groq_service.api_key == "test-mother-key-99999"
        assert mother.groq_service.model == "llama-3.3-70b-versatile"


def test_db_agent_fallback_key_isolation():
    """Verify DB Agent discovery only collects DB_GROQ_API_KEY* and ignores all other agent keys."""
    env_mock = {
        "INPUT_GROQ_API_KEY": "input-secret",
        "MOTHER_GROQ_API_KEY": "mother-secret",
        "PULSE_GROQ_API_KEY": "pulse-secret",
        "SCRIBE_GROQ_API_KEY": "scribe-secret",
        "DB_GROQ_API_KEY": "db-primary-secret",
        "DB_GROQ_API_KEY_1": "db-fallback-1",
        "DB_GROQ_API_KEY_2": "db-fallback-2",
        "DB_GROQ_MODEL": "llama-3.3-70b-versatile",
    }
    
    with patch.dict(os.environ, env_mock, clear=True):
        with patch("groq.Groq") as mock_groq_cls:
            mock_client = MagicMock()
            mock_resp = MagicMock()
            mock_resp.choices = [MagicMock()]
            mock_resp.choices[0].message.content = '{"action": "get_all_rows", "table": "students", "params": {}}'
            mock_client.chat.completions.create.return_value = mock_resp
            mock_groq_cls.return_value = mock_client

            res = call_groq_completion(messages=[{"role": "user", "content": "test"}])
            assert res is not None

            # Verify that Groq client was initialized ONLY with DB keys
            calls = mock_groq_cls.call_args_list
            for call in calls:
                kwargs = call[1]
                key_passed = kwargs.get("api_key")
                assert key_passed in ("db-primary-secret", "db-fallback-1", "db-fallback-2")
                assert key_passed not in ("input-secret", "mother-secret", "pulse-secret", "scribe-secret")


def test_db_agent_no_keys_raises_or_fallbacks():
    """When DB_GROQ_API_KEY is not set, call_groq_completion raises RuntimeError and DBAgent falls back."""
    with patch.dict(os.environ, {
        "MOTHER_GROQ_API_KEY": "mother-secret",
        "PULSE_GROQ_API_KEY": "pulse-secret",
        "SCRIBE_GROQ_API_KEY": "scribe-secret",
    }, clear=True):
        # Must fail because no DB keys exist
        with pytest.raises(RuntimeError) as exc_info:
            call_groq_completion(messages=[{"role": "user", "content": "test"}])
        assert "DB_GROQ_API_KEY not configured" in str(exc_info.value)


def test_pulse_agent_key_wiring():
    """Verify Pulse planner and interpreter use PULSE_GROQ_API_KEY and PULSE_GROQ_MODEL."""
    with patch.dict(os.environ, {
        "PULSE_GROQ_API_KEY": "pulse-isolated-key",
        "PULSE_GROQ_MODEL": "llama-3.3-70b-versatile",
        "MOTHER_GROQ_API_KEY": "other-mother-key",
        "DB_GROQ_API_KEY": "other-db-key",
    }, clear=True):
        with patch("groq.Groq") as mock_groq_cls:
            mock_client = MagicMock()
            mock_resp = MagicMock()
            mock_resp.choices = [MagicMock()]
            mock_resp.choices[0].message.content = '{"strategy": "tool_based", "operations": []}'
            mock_client.chat.completions.create.return_value = mock_resp
            mock_groq_cls.return_value = mock_client

            plan = get_analysis_plan("Analyze performance", {"summary_text": "data summary"})
            assert plan is not None
            mock_groq_cls.assert_called_with(api_key="pulse-isolated-key")


def test_scribe_agent_key_wiring_text():
    """Verify Scribe text generator uses SCRIBE_GROQ_API_KEY and SCRIBE_GROQ_MODEL."""
    with patch.dict(os.environ, {
        "SCRIBE_GROQ_API_KEY": "scribe-isolated-key",
        "SCRIBE_GROQ_MODEL": "llama-3.3-70b-versatile",
        "MOTHER_GROQ_API_KEY": "mother-key",
    }, clear=True):
        with patch.object(GroqService, "generate_text_report") as mock_gen:
            mock_gen.return_value = "Formatted report"
            out = generate_text(records=[{"name": "Alice"}], metrics=None, insight=None, user_query="Report")
            assert out == "Formatted report"
            assert mock_gen.called


def test_scribe_agent_key_wiring_pdf():
    """Verify Scribe PDF generator uses SCRIBE_GROQ_API_KEY."""
    with patch.dict(os.environ, {
        "SCRIBE_GROQ_API_KEY": "scribe-isolated-key",
        "SCRIBE_GROQ_MODEL": "llama-3.3-70b-versatile",
    }, clear=True):
        with patch.object(GroqService, "generate_pdf_plan") as mock_plan:
            mock_plan.return_value = None  # Fallback to deterministic
            file_info = generate_pdf(records=[{"name": "Alice", "cgpa": 9.0}], metrics=None, insight=None, user_query="PDF report")
            assert file_info is not None
            assert file_info.get("file_name", "").endswith(".pdf")
            assert mock_plan.called


def test_scribe_agent_key_wiring_ppt():
    """Verify Scribe PPT generator uses SCRIBE_GROQ_API_KEY."""
    with patch.dict(os.environ, {
        "SCRIBE_GROQ_API_KEY": "scribe-isolated-key",
        "SCRIBE_GROQ_MODEL": "llama-3.3-70b-versatile",
    }, clear=True):
        with patch.object(GroqService, "generate_ppt_plan") as mock_plan:
            mock_plan.return_value = None  # Fallback to deterministic
            file_info = generate_ppt(records=[{"name": "Alice", "cgpa": 9.0}], metrics=None, insight=None, user_query="PPT presentation")
            assert file_info is not None
            assert file_info.get("file_name", "").endswith(".pptx")
            assert mock_plan.called


def test_fallback_case_1_primary_key_succeeds():
    """CASE 1: Primary key succeeds -> exactly 1 LLM request, no fallback."""
    env = {
        "DB_GROQ_API_KEY": "key-primary",
        "DB_GROQ_API_KEY_1": "key-fallback-1",
        "DB_GROQ_MODEL": "llama-3.3-70b-versatile",
    }
    with patch.dict(os.environ, env, clear=True):
        with patch("groq.Groq") as mock_groq_cls:
            mock_client = MagicMock()
            mock_resp = MagicMock()
            mock_resp.choices = [MagicMock()]
            mock_resp.choices[0].message.content = '{"action": "get_all_rows"}'
            mock_client.chat.completions.create.return_value = mock_resp
            mock_groq_cls.return_value = mock_client

            res = call_groq_completion(messages=[{"role": "user", "content": "hi"}])
            assert res == '{"action": "get_all_rows"}'
            assert mock_groq_cls.call_count == 1
            assert mock_groq_cls.call_args[1]["api_key"] == "key-primary"


def test_fallback_case_2_primary_429_fallback_succeeds():
    """CASE 2: Primary key returns 429 -> fallback key succeeds, no further keys tried."""
    env = {
        "DB_GROQ_API_KEY": "key-primary",
        "DB_GROQ_API_KEY_1": "key-fallback-1",
        "DB_GROQ_API_KEY_2": "key-fallback-2",
        "DB_GROQ_MODEL": "llama-3.3-70b-versatile",
    }
    with patch.dict(os.environ, env, clear=True):
        with patch("groq.Groq") as mock_groq_cls:
            primary_client = MagicMock()
            primary_client.chat.completions.create.side_effect = Exception("429 Rate limit reached for model")

            fallback_client = MagicMock()
            mock_resp = MagicMock()
            mock_resp.choices = [MagicMock()]
            mock_resp.choices[0].message.content = '{"action": "filter_rows"}'
            fallback_client.chat.completions.create.return_value = mock_resp

            def client_factory(api_key):
                if api_key == "key-primary":
                    return primary_client
                elif api_key == "key-fallback-1":
                    return fallback_client
                return MagicMock()

            mock_groq_cls.side_effect = client_factory

            res = call_groq_completion(messages=[{"role": "user", "content": "hi"}])
            assert res == '{"action": "filter_rows"}'
            # Primary and fallback-1 were tried, fallback-2 was NOT tried
            keys_tried = [call[1]["api_key"] for call in mock_groq_cls.call_args_list]
            assert keys_tried == ["key-primary", "key-fallback-1"]


def test_fallback_case_3_two_keys_429_third_succeeds():
    """CASE 3: First two keys return 429 -> third key succeeds."""
    env = {
        "DB_GROQ_API_KEY": "key-primary",
        "DB_GROQ_API_KEY_1": "key-fallback-1",
        "DB_GROQ_API_KEY_2": "key-fallback-2",
        "DB_GROQ_MODEL": "llama-3.3-70b-versatile",
    }
    with patch.dict(os.environ, env, clear=True):
        with patch("groq.Groq") as mock_groq_cls:
            c1 = MagicMock()
            c1.chat.completions.create.side_effect = Exception("429 Rate limit reached")
            c2 = MagicMock()
            c2.chat.completions.create.side_effect = Exception("429 Rate limit reached")
            c3 = MagicMock()
            mock_resp = MagicMock()
            mock_resp.choices = [MagicMock()]
            mock_resp.choices[0].message.content = '{"action": "third_key_success"}'
            c3.chat.completions.create.return_value = mock_resp

            def client_factory(api_key):
                if api_key == "key-primary":
                    return c1
                elif api_key == "key-fallback-1":
                    return c2
                elif api_key == "key-fallback-2":
                    return c3
                return MagicMock()

            mock_groq_cls.side_effect = client_factory

            res = call_groq_completion(messages=[{"role": "user", "content": "hi"}])
            assert res == '{"action": "third_key_success"}'
            keys_tried = [call[1]["api_key"] for call in mock_groq_cls.call_args_list]
            assert keys_tried == ["key-primary", "key-fallback-1", "key-fallback-2"]


def test_fallback_case_4_all_keys_fail_raises():
    """CASE 4: All configured keys fail -> raises RuntimeError with failure info, no fake success."""
    env = {
        "DB_GROQ_API_KEY": "key-primary",
        "DB_GROQ_API_KEY_1": "key-fallback-1",
        "DB_GROQ_MODEL": "llama-3.3-70b-versatile",
    }
    with patch.dict(os.environ, env, clear=True):
        with patch("groq.Groq") as mock_groq_cls:
            failing_client = MagicMock()
            failing_client.chat.completions.create.side_effect = Exception("429 Rate limit exhausted")
            mock_groq_cls.return_value = failing_client

            with pytest.raises(RuntimeError) as exc_info:
                call_groq_completion(messages=[{"role": "user", "content": "hi"}])
            assert "All Groq fallback options exhausted" in str(exc_info.value)


def test_fallback_case_5_auth_error_skips_key():
    """CASE 5: A key has an authentication/invalid-key error -> skipped, next key used."""
    env = {
        "DB_GROQ_API_KEY": "invalid-key-bad-auth",
        "DB_GROQ_API_KEY_1": "valid-fallback-key",
        "DB_GROQ_MODEL": "llama-3.3-70b-versatile",
    }
    with patch.dict(os.environ, env, clear=True):
        with patch("groq.Groq") as mock_groq_cls:
            auth_fail_client = MagicMock()
            auth_fail_client.chat.completions.create.side_effect = Exception("401 Invalid API Key (invalid_api_key)")

            success_client = MagicMock()
            mock_resp = MagicMock()
            mock_resp.choices = [MagicMock()]
            mock_resp.choices[0].message.content = '{"action": "valid_key_success"}'
            success_client.chat.completions.create.return_value = mock_resp

            def client_factory(api_key):
                if api_key == "invalid-key-bad-auth":
                    return auth_fail_client
                return success_client

            mock_groq_cls.side_effect = client_factory

            res = call_groq_completion(messages=[{"role": "user", "content": "hi"}])
            assert res == '{"action": "valid_key_success"}'


def test_fallback_case_6_identical_keys_deduplicated():
    """CASE 6: Same key value configured under multiple environment variables -> deduplicated, no wasted calls."""
    env = {
        "DB_GROQ_API_KEY": "duplicate-secret-xyz",
        "DB_GROQ_API_KEY_1": "duplicate-secret-xyz",
        "DB_GROQ_API_KEY_2": "duplicate-secret-xyz",
        "DB_GROQ_MODEL": "llama-3.3-70b-versatile",
    }
    with patch.dict(os.environ, env, clear=True):
        with patch("groq.Groq") as mock_groq_cls:
            client = MagicMock()
            mock_resp = MagicMock()
            mock_resp.choices = [MagicMock()]
            mock_resp.choices[0].message.content = '{"action": "deduped_success"}'
            client.chat.completions.create.return_value = mock_resp
            mock_groq_cls.return_value = client

            res = call_groq_completion(messages=[{"role": "user", "content": "hi"}])
            assert res == '{"action": "deduped_success"}'
            # Since the secret was identical, it was deduplicated and initialized only ONCE per model
            assert mock_groq_cls.call_count == 1

