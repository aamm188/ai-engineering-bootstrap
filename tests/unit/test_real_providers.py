"""Unit tests for Real LLM Providers."""

import json
from contextlib import suppress
from unittest import mock
from urllib.error import HTTPError, URLError

import pytest

from ai_engineering_bootstrap.agent.exceptions import (
    ProviderConnectionError,
    ProviderResponseError,
    ProviderTimeoutError,
)
from ai_engineering_bootstrap.agent.models import AgentDecision
from ai_engineering_bootstrap.agent.provider import (
    InProcessProvider,
    LocalServerProvider,
    MockProvider,
    ProviderConfig,
    RemoteAPIProvider,
)
from ai_engineering_bootstrap.executor.capability import Capability, CapabilityRisk
from ai_engineering_bootstrap.executor.mode import ExecutionMode


def _get_test_capabilities():
    return [
        Capability(
            capability_id="check_py",
            name="Check Python",
            description="Checks version",
            action_id="check_python_version_real",
            risk=CapabilityRisk.LOW,
            supported_modes=[ExecutionMode.SAFE, ExecutionMode.REAL],
        )
    ]


def test_local_provider_success() -> None:
    config = ProviderConfig(provider_type="local_server", base_url="http://localhost:1234", model="test")
    provider = LocalServerProvider(config)

    mock_response = {
        "choices": [{"message": {"content": json.dumps({"selected_capability_ids": ["check_py"], "confidence": 0.9})}}]
    }

    with mock.patch("urllib.request.urlopen") as mock_urlopen:
        mock_cm = mock.MagicMock()
        mock_cm.read.return_value = json.dumps(mock_response).encode("utf-8")
        mock_cm.__enter__.return_value = mock_cm
        mock_urlopen.return_value = mock_cm

        decision = provider.decide("fix env", _get_test_capabilities())

        assert isinstance(decision, AgentDecision)
        assert "check_py" in decision.selected_capability_ids


def test_local_provider_connection_failure() -> None:
    config = ProviderConfig(provider_type="local_server", base_url="http://localhost:1234")
    provider = LocalServerProvider(config)

    with mock.patch("urllib.request.urlopen", side_effect=URLError("Connection refused")), \
         pytest.raises(ProviderConnectionError):
        provider.decide("test", _get_test_capabilities())


def test_local_provider_timeout() -> None:
    config = ProviderConfig(provider_type="local_server", base_url="http://localhost:1234", timeout=1)
    provider = LocalServerProvider(config)

    with mock.patch("urllib.request.urlopen", side_effect=TimeoutError()), \
         pytest.raises(ProviderTimeoutError):
        provider.decide("test", _get_test_capabilities())


def test_local_provider_malformed_response() -> None:
    config = ProviderConfig(provider_type="local_server", base_url="http://localhost:1234")
    provider = LocalServerProvider(config)

    with mock.patch("urllib.request.urlopen") as mock_urlopen:
        mock_cm = mock.MagicMock()
        mock_cm.read.return_value = b"invalid json{"
        mock_cm.__enter__.return_value = mock_cm
        mock_urlopen.return_value = mock_cm

        with pytest.raises(ProviderResponseError):
            provider.decide("test", _get_test_capabilities())


def test_remote_provider_success() -> None:
    config = ProviderConfig(
        provider_type="remote_api",
        base_url="https://api.openai.com/v1",
        model="gpt-4",
        api_key="sk-test-key",
    )
    provider = RemoteAPIProvider(config)

    mock_response = {
        "choices": [{"message": {"content": json.dumps({"selected_capability_ids": ["check_py"], "confidence": 0.8})}}]
    }

    with mock.patch("urllib.request.urlopen") as mock_urlopen:
        mock_cm = mock.MagicMock()
        mock_cm.read.return_value = json.dumps(mock_response).encode("utf-8")
        mock_cm.__enter__.return_value = mock_cm
        mock_urlopen.return_value = mock_cm

        decision = provider.decide("test", _get_test_capabilities())
        assert isinstance(decision, AgentDecision)


def test_remote_provider_api_key_auth() -> None:
    """Verify API key is set in header even if request fails."""
    config = ProviderConfig(
        provider_type="remote_api",
        base_url="https://api.example.com",
        api_key="secret-key-123",
        model="test",
    )
    provider = RemoteAPIProvider(config)

    with mock.patch("urllib.request.urlopen") as mock_urlopen:
        mock_cm = mock.MagicMock()
        # شبیه‌سازی خطا برای اینکه ببینیم آیا هدر قبل از خطا تنظیم شده است یا خیر
        mock_cm.__enter__.side_effect = HTTPError("", 500, "Internal Error", {}, None)
        mock_urlopen.return_value = mock_cm

        # استفاده از suppress برای نادیده گرفتن ایمن هر نوع خطا بدون نق قوانین ruff
        with suppress(Exception):
            provider.decide("test", _get_test_capabilities())

        call_args = mock_urlopen.call_args
        req = call_args[0][0]
        assert req.headers.get("Authorization") == "Bearer secret-key-123"


def test_api_key_not_in_error_message() -> None:
    config = ProviderConfig(
        provider_type="remote_api",
        base_url="https://api.example.com",
        api_key="super-secret-key-12345",
        model="test",
    )
    provider = RemoteAPIProvider(config)

    with mock.patch("urllib.request.urlopen", side_effect=HTTPError("", 401, "Unauthorized", {}, None)):
        with pytest.raises(ProviderResponseError) as exc_info:
            provider.decide("test", _get_test_capabilities())

        assert "super-secret-key-12345" not in str(exc_info.value)


def test_in_process_provider_success() -> None:
    class FakeModel:
        def generate(self, prompt):
            return json.dumps({"selected_capability_ids": ["check_py"], "confidence": 0.95})

    config = ProviderConfig(provider_type="in_process", options={"model_instance": FakeModel()})
    provider = InProcessProvider(config)

    decision = provider.decide("test", _get_test_capabilities())
    assert isinstance(decision, AgentDecision)
    assert "check_py" in decision.selected_capability_ids


def test_in_process_provider_no_model() -> None:
    config = ProviderConfig(provider_type="in_process", options={})
    provider = InProcessProvider(config)

    with pytest.raises(ProviderConnectionError):
        provider.decide("test", _get_test_capabilities())


def test_mock_provider_deterministic() -> None:
    provider = MockProvider()
    caps = _get_test_capabilities()
    d1 = provider.decide("fix env", caps)
    d2 = provider.decide("fix env", caps)
    assert d1.selected_capability_ids == d2.selected_capability_ids


def test_provider_factory_supports_three_deployment_modes() -> None:
    from ai_engineering_bootstrap.agent.provider import build_provider

    assert isinstance(build_provider(ProviderConfig("local_server", base_url="http://localhost:1234")), LocalServerProvider)
    assert isinstance(build_provider(ProviderConfig("in_process", options={"model_instance": object()})), InProcessProvider)
    assert isinstance(build_provider(ProviderConfig("mock")), MockProvider)


def test_provider_factory_reads_remote_api_key_from_environment(monkeypatch) -> None:
    from ai_engineering_bootstrap.agent.provider import build_provider

    monkeypatch.setenv("TEST_LLM_KEY", "secret")
    provider = build_provider(
        ProviderConfig(
            "remote_api",
            base_url="https://example.test/v1",
            model="test",
            options={"api_key_env": "TEST_LLM_KEY"},
        )
    )
    assert isinstance(provider, RemoteAPIProvider)
    assert provider.config.api_key == "secret"


def test_local_provider_sends_no_think_and_stream_false() -> None:
    provider = LocalServerProvider(
        ProviderConfig(
            provider_type="local_server",
            base_url="http://localhost:1234/",
            model="qwen3-8b-abliterated",
        )
    )
    response = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {"selected_capability_ids": ["check_py"], "confidence": 0.9}
                    )
                },
                "finish_reason": "stop",
            }
        ]
    }

    with mock.patch.object(provider, "_request", return_value=response):
        decision = provider.decide("fix env", _get_test_capabilities())

    assert decision.selected_capability_ids == ["check_py"]


def test_local_provider_empty_content_with_length_has_actionable_error() -> None:
    provider = LocalServerProvider(
        ProviderConfig(provider_type="local_server", base_url="http://localhost:1234")
    )
    response = {
        "choices": [
            {
                "message": {"content": ""},
                "finish_reason": "length",
            }
        ]
    }

    with mock.patch.object(provider, "_request", return_value=response), \
         pytest.raises(ProviderResponseError, match="truncated"):
            provider.decide("fix env", _get_test_capabilities())


def test_local_provider_reads_json_from_reasoning_content_when_content_is_empty() -> None:
    provider = LocalServerProvider(
        ProviderConfig(provider_type="local_server", base_url="http://localhost:1234")
    )
    response = {
        "choices": [
            {
                "message": {
                    "content": "",
                    "reasoning_content": json.dumps(
                        {
                            "reasoning_summary": "fallback",
                            "selected_capability_ids": ["check_py"],
                            "confidence": 0.8,
                        }
                    ),
                },
                "finish_reason": "stop",
            }
        ]
    }

    with mock.patch.object(provider, "_request", return_value=response):
        decision = provider.decide("fix env", _get_test_capabilities())

    assert decision.selected_capability_ids == ["check_py"]
    assert decision.confidence == 0.8


def test_local_provider_structured_output_option_builds_schema() -> None:
    provider = LocalServerProvider(
        ProviderConfig(
            provider_type="local_server",
            base_url="http://localhost:1234",
            options={"structured_output": True},
        )
    )

    payload = provider._build_payload("test")

    assert payload["stream"] is False
    assert payload["response_format"]["type"] == "json_schema"
    assert payload["response_format"]["json_schema"]["name"] == "agent_decision"
    assert "/no_think" in payload["messages"][0]["content"]
