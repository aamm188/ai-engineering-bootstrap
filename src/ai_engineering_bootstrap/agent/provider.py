"""LLM Provider abstraction supporting multiple deployment modes."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from ai_engineering_bootstrap.agent.exceptions import (
    ProviderConnectionError,
    ProviderResponseError,
    ProviderTimeoutError,
)
from ai_engineering_bootstrap.agent.models import AgentDecision
from ai_engineering_bootstrap.executor.capability import Capability


@dataclass
class ProviderConfig:
    """Provider-independent configuration."""

    provider_type: str
    model: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    timeout: int = 30
    options: dict[str, Any] = field(default_factory=dict)


class LLMProvider(ABC):
    """Abstract contract for LLM providers."""

    @abstractmethod
    def decide(
        self,
        context: str,
        available_capabilities: list[Capability],
    ) -> AgentDecision:
        """Generate an agent decision."""
        raise NotImplementedError


class MockProvider(LLMProvider):
    """Deterministic mock provider for testing."""

    def decide(
        self,
        context: str,
        available_capabilities: list[Capability],
    ) -> AgentDecision:
        selected_ids = []
        if "fix" in context.lower() and available_capabilities:
            selected_ids = [available_capabilities[0].capability_id]

        return AgentDecision(
            reasoning_summary="Mock decision generated for testing.",
            selected_capability_ids=selected_ids,
            confidence=0.95,
            requires_human_approval=False,
        )


class LocalServerProvider(LLMProvider):
    """Provider for OpenAI-compatible local servers such as LM Studio."""

    def __init__(self, config: ProviderConfig) -> None:
        self.config = config

    def decide(
        self,
        context: str,
        available_capabilities: list[Capability],
    ) -> AgentDecision:
        if not self.config.base_url:
            raise ProviderConnectionError(
                "base_url is required for LocalServerProvider."
            )

        prompt = self._build_prompt(context, available_capabilities)
        payload = self._build_payload(prompt)

        try:
            result = self._request(payload)
            return self._parse_response(result)
        except urllib.error.HTTPError as error:
            error_body = self._read_error_body(error)
            raise ProviderConnectionError(
                f"HTTP Error {error.code}: {error.reason}. Details: {error_body}"
            ) from error
        except urllib.error.URLError as error:
            raise ProviderConnectionError(
                f"Failed to connect: {error.reason}"
            ) from error
        except TimeoutError as error:
            raise ProviderTimeoutError("Request timed out.") from error
        except json.JSONDecodeError as error:
            raise ProviderResponseError(
                f"Invalid response JSON: {error}"
            ) from error

    def _build_payload(self, prompt: str) -> dict[str, Any]:
        system_prompt = (
            "You are an agent decision engine. "
            "Return ONLY one valid JSON object matching the requested schema. "
            "Do not explain outside JSON. "
            "/no_think"
        )

        return {
            "model": self.config.model or "default",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "temperature": float(self.config.options.get("temperature", 0.1)),
            "max_tokens": int(self.config.options.get("max_tokens", 700)),
            "stream": False,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "agent_decision",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "reasoning_summary": {"type": "string"},
                            "selected_capability_ids": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "confidence": {"type": "number"},
                        },
                        "required": [
                            "reasoning_summary",
                            "selected_capability_ids",
                            "confidence",
                        ],
                        "additionalProperties": False,
                    },
                },
            },
        }

    def _request(self, payload: dict[str, Any]) -> dict[str, Any]:
        data = json.dumps(payload).encode("utf-8")
        base_url = self.config.base_url.rstrip("/")
        request = urllib.request.Request(
            f"{base_url}/v1/chat/completions",
            data=data,
            headers={"Content-Type": "application/json"},
        )

        with urllib.request.urlopen(request, timeout=self.config.timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    @staticmethod
    def _read_error_body(error: urllib.error.HTTPError) -> str:
        try:
            return error.read().decode("utf-8")
        except (UnicodeDecodeError, AttributeError, ValueError):
            return "Could not read error body"

    def _build_prompt(
        self,
        context: str,
        capabilities: list[Capability],
    ) -> str:
        cap_list = "\n".join(
            f"- ID: {capability.capability_id}, "
            f"Description: {capability.description}"
            for capability in capabilities
        )
        thinking_instruction = (
            "/think"
            if bool(self.config.options.get("enable_thinking", False))
            else "/no_think"
        )

        return (
            f"Context: {context}\n\n"
            f"Available capabilities:\n{cap_list}\n\n"
            "Select only capabilities that exist in the provided list. "
            "Respond with exactly this JSON structure: "
            '{"reasoning_summary":"...",'
            '"selected_capability_ids":["id1"],"confidence":0.95}\n\n'
            f"{thinking_instruction}"
        )

    def _parse_response(self, data: dict[str, Any]) -> AgentDecision:
        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ProviderResponseError(
                "Provider response contains no choices."
            )

        choice = choices[0]
        if not isinstance(choice, dict):
            raise ProviderResponseError("Provider response contains invalid choice data.")

        finish_reason = choice.get("finish_reason")
        if finish_reason == "length":
            raise ProviderResponseError(
                "Provider response was truncated before a complete JSON decision "
                "was returned. Increase max_tokens or disable thinking mode."
            )

        if finish_reason not in (None, "stop"):
            raise ProviderResponseError(
                f"Provider returned an unusable finish_reason={finish_reason!r}."
            )

        message = choice.get("message") or {}
        if not isinstance(message, dict):
            raise ProviderResponseError("Provider response contains invalid message data.")

        content = message.get("content")

        if not isinstance(content, str) or not content.strip():
            content = message.get("reasoning_content")

        if not isinstance(content, str) or not content.strip():
            reasoning = message.get("reasoning")
            if isinstance(reasoning, str):
                content = reasoning

        if not isinstance(content, str) or not content.strip():
            raise ProviderResponseError(
                "Provider returned empty decision content. "
                f"finish_reason={finish_reason!r}."
            )

        return self._decision_from_content(content)

    @staticmethod
    def _decision_from_content(content: str) -> AgentDecision:
        normalized = content.strip()

        if normalized.startswith("```json"):
            normalized = normalized[len("```json"):].strip()
        elif normalized.startswith("```"):
            normalized = normalized[3:].strip()

        if normalized.endswith("```"):
            normalized = normalized[:-3].strip()

        try:
            decision_data = json.loads(normalized)
        except json.JSONDecodeError as error:
            raise ProviderResponseError(
                f"Could not parse JSON. Received: {normalized[:300]}..."
            ) from error

        if not isinstance(decision_data, dict):
            raise ProviderResponseError("Provider decision must be a JSON object.")

        selected = decision_data.get("selected_capability_ids", [])
        if not isinstance(selected, list) or not all(
            isinstance(item, str) for item in selected
        ):
            raise ProviderResponseError(
                "selected_capability_ids must be a JSON array of strings."
            )

        try:
            confidence = float(decision_data.get("confidence", 0.5))
        except (TypeError, ValueError) as error:
            raise ProviderResponseError("confidence must be numeric.") from error

        return AgentDecision(
            reasoning_summary=str(decision_data.get("reasoning_summary", "")),
            selected_capability_ids=selected,
            confidence=confidence,
        )


class RemoteAPIProvider(LLMProvider):
    """Provider for remote APIs."""

    def __init__(self, config: ProviderConfig) -> None:
        self.config = config

    def decide(
        self,
        context: str,
        available_capabilities: list[Capability],
    ) -> AgentDecision:
        if not self.config.base_url or not self.config.api_key:
            raise ProviderConnectionError("base_url and api_key required.")

        prompt = self._build_prompt(context, available_capabilities)
        payload = {
            "model": self.config.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": float(self.config.options.get("temperature", 0.1)),
        }

        try:
            data = json.dumps(payload).encode("utf-8")
            request = urllib.request.Request(
                f"{self.config.base_url.rstrip('/')}/chat/completions",
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.config.api_key}",
                },
            )
            with urllib.request.urlopen(
                request,
                timeout=self.config.timeout,
            ) as response:
                result = json.loads(response.read().decode("utf-8"))
                return self._parse_response(result)
        except urllib.error.HTTPError as error:
            raise ProviderResponseError(f"API Error: {error.code}") from error
        except urllib.error.URLError as error:
            raise ProviderConnectionError(
                f"Connection failed: {error.reason}"
            ) from error
        except TimeoutError as error:
            raise ProviderTimeoutError("Request timed out.") from error
        except json.JSONDecodeError as error:
            raise ProviderResponseError(
                f"Invalid response: {error}"
            ) from error

    def _build_prompt(
        self,
        context: str,
        capabilities: list[Capability],
    ) -> str:
        cap_list = ", ".join(
            capability.capability_id for capability in capabilities
        )
        return (
            f"Select IDs for: {context}. "
            f"Available: [{cap_list}]. Output JSON."
        )

    def _parse_response(self, data: dict[str, Any]) -> AgentDecision:
        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ProviderResponseError(
                "Provider response contains no choices."
            )

        message = choices[0].get("message") or {}
        content = message.get("content")

        if not isinstance(content, str) or not content.strip():
            raise ProviderResponseError("No content in API response.")

        try:
            decision_data = json.loads(content)
        except json.JSONDecodeError as error:
            raise ProviderResponseError(
                f"Could not parse JSON: {content[:300]}..."
            ) from error

        if not isinstance(decision_data, dict):
            raise ProviderResponseError("Provider decision must be a JSON object.")

        selected = decision_data.get("selected_capability_ids", [])
        if not selected and "capability_id" in decision_data:
            selected = [decision_data["capability_id"]]

        if not isinstance(selected, list) or not all(
            isinstance(item, str) for item in selected
        ):
            raise ProviderResponseError(
                "selected_capability_ids must be a JSON array of strings."
            )

        try:
            confidence = float(decision_data.get("confidence", 0.5))
        except (TypeError, ValueError) as error:
            raise ProviderResponseError("confidence must be numeric.") from error

        return AgentDecision(
            reasoning_summary=str(decision_data.get("reasoning_summary", "")),
            selected_capability_ids=selected,
            confidence=confidence,
        )

    def _build_prompt(
        self,
        context: str,
        capabilities: list[Capability],
    ) -> str:
        cap_list = ", ".join(
            capability.capability_id for capability in capabilities
        )
        return (
            f"Select IDs for: {context}. "
            f"Available: [{cap_list}]. Output JSON."
        )


class InProcessProvider(LLMProvider):
    """Provider for in-process models."""

    def __init__(self, config: ProviderConfig) -> None:
        self.config = config
        self.model = config.options.get("model_instance")

    def decide(
        self,
        context: str,
        available_capabilities: list[Capability],
    ) -> AgentDecision:
        if self.model is None:
            raise ProviderConnectionError("No model instance provided.")

        try:
            prompt = self._build_prompt(context, available_capabilities)

            if not hasattr(self.model, "generate"):
                raise ProviderResponseError(
                    "Model has no 'generate' method."
                )

            output = self.model.generate(prompt)
            decision_data = json.loads(output)

            if not isinstance(decision_data, dict):
                raise ProviderResponseError(
                    "Provider decision must be a JSON object."
                )

            selected = decision_data.get("selected_capability_ids", [])
            if not selected and "capability_id" in decision_data:
                selected = [decision_data["capability_id"]]

            if not isinstance(selected, list) or not all(
                isinstance(item, str) for item in selected
            ):
                raise ProviderResponseError(
                    "selected_capability_ids must be a JSON array of strings."
                )

            try:
                confidence = float(
                    decision_data.get("confidence", 0.5)
                )
            except (TypeError, ValueError) as error:
                raise ProviderResponseError(
                    "confidence must be numeric."
                ) from error

            return AgentDecision(
                reasoning_summary=str(
                    decision_data.get("reasoning_summary", "")
                ),
                selected_capability_ids=selected,
                confidence=confidence,
            )
        except (ProviderConnectionError, ProviderResponseError):
            raise
        except json.JSONDecodeError as error:
            raise ProviderResponseError(
                f"Could not parse JSON: {error}"
            ) from error
        except Exception as error:
            raise ProviderResponseError(
                f"Model execution failed: {error}"
            ) from error

    def _build_prompt(
        self,
        context: str,
        capabilities: list[Capability],
    ) -> str:
        return (
            f"Context: {context}. "
            f"Available: {[c.capability_id for c in capabilities]}. "
            "Output JSON."
        )


def build_provider(config: ProviderConfig) -> LLMProvider:
    """Create a provider from a validated provider configuration."""

    if config.provider_type == "local_server":
        return LocalServerProvider(config)

    if config.provider_type == "remote_api":
        api_key = config.api_key

        if not api_key:
            env_name = config.options.get("api_key_env")
            if env_name:
                api_key = os.environ.get(str(env_name))

        if not api_key:
            raise ProviderConnectionError(
                "Remote API provider requires an API key."
            )

        return RemoteAPIProvider(
            ProviderConfig(
                provider_type=config.provider_type,
                model=config.model,
                base_url=config.base_url,
                api_key=api_key,
                timeout=config.timeout,
                options=config.options,
            )
        )

    if config.provider_type == "in_process":
        return InProcessProvider(config)

    if config.provider_type == "mock":
        return MockProvider()

    raise ValueError(
        f"Unsupported provider type: {config.provider_type}"
    )


__all__ = [
    "InProcessProvider",
    "LLMProvider",
    "LocalServerProvider",
    "MockProvider",
    "ProviderConfig",
    "RemoteAPIProvider",
    "build_provider",
]
