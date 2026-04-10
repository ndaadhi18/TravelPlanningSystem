"""
Shared base utilities for PLANIT agent nodes.

M9 scope:
- LLM instantiation (`get_llm`)
- Prompt message builder
- Structured output parsing (Pydantic)
- Consistent error wrapping
"""

from __future__ import annotations

import inspect
import json
import re
from typing import Any, Callable, Mapping, Optional, TypeVar

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, ValidationError

from backend.core.settings import get_settings
from backend.utils.logger import get_logger

logger = get_logger("agents.base")

TModel = TypeVar("TModel", bound=BaseModel)


class AgentExecutionError(Exception):
    """Structured exception raised by shared base-agent helpers."""

    def __init__(
        self,
        agent_name: str,
        step: str,
        message: str,
        *,
        details: Optional[dict[str, Any]] = None,
        original_error: Optional[Exception] = None,
    ):
        super().__init__(message)
        self.agent_name = agent_name
        self.step = step
        self.message = message
        self.details = details or {}
        self.original_error = original_error

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "error": True,
            "agent_name": self.agent_name,
            "step": self.step,
            "message": self.message,
        }
        if self.details:
            payload["details"] = self.details
        return payload


def get_llm(
    *,
    model_name: Optional[str] = None,
    temperature: float = 0.2,
    llm_factory: Optional[Callable[..., Any]] = None,
    llm_override: Optional[Any] = None,
) -> Any:
    """
    Instantiate ChatGroq (or an injected LLM factory for tests).

    Args:
        model_name: Optional explicit model override.
        temperature: Sampling temperature.
        llm_factory: Optional injectable factory for tests.
        llm_override: Optional direct LLM instance to return as-is.
    """
    if llm_override is not None:
        return llm_override

    settings = get_settings()
    selected_model = model_name or settings.groq_model_name

    factory = llm_factory
    if factory is None:
        from langchain_groq import ChatGroq

        factory = ChatGroq

    kwargs: dict[str, Any] = {
        "api_key": settings.groq_api_key,
        "temperature": temperature,
    }

    # Be resilient to SDK signature variations (model vs model_name).
    try:
        signature = inspect.signature(factory)
        if "model" in signature.parameters:
            kwargs["model"] = selected_model
        elif "model_name" in signature.parameters:
            kwargs["model_name"] = selected_model
        else:
            kwargs["model"] = selected_model
    except (TypeError, ValueError):
        kwargs["model"] = selected_model

    return factory(**kwargs)


def build_prompt_messages(
    system_instruction: str,
    *,
    state: Optional[Mapping[str, Any]] = None,
    user_input: Optional[str] = None,
    additional_context: Optional[str] = None,
) -> list[BaseMessage]:
    """
    Build a canonical prompt message list used by agent nodes.
    """
    if not system_instruction or not system_instruction.strip():
        raise ValueError("system_instruction must be a non-empty string.")

    sections: list[str] = []
    if additional_context:
        sections.append(additional_context.strip())
    if state is not None:
        sections.append(
            "Current state:\n"
            + json.dumps(
                dict(state),
                indent=2,
                sort_keys=True,
                default=str,
            )
        )
    if user_input:
        sections.append(f"User input:\n{user_input.strip()}")

    messages: list[BaseMessage] = [SystemMessage(content=system_instruction.strip())]
    if sections:
        messages.append(HumanMessage(content="\n\n".join(section for section in sections if section)))
    return messages


def parse_structured_output(raw_output: Any, model_cls: type[TModel]) -> TModel:
    """
    Parse LLM output into a target Pydantic model.
    """
    if isinstance(raw_output, model_cls):
        return raw_output

    try:
        payload = _extract_payload(raw_output)
        if isinstance(payload, str):
            payload = _parse_json_payload(payload)
        return model_cls.model_validate(payload)
    except (ValidationError, TypeError, ValueError, json.JSONDecodeError) as e:
        raise AgentExecutionError(
            "base_agent",
            "structured_parse",
            f"Failed to parse structured output into {model_cls.__name__}.",
            details={"payload_preview": str(payload)[:400]},
            original_error=e,
        ) from e


def invoke_llm(llm: Any, messages: list[BaseMessage], *, agent_name: str) -> Any:
    """Invoke an LLM and wrap provider/runtime failures consistently."""
    try:
        return llm.invoke(messages)
    except Exception as e:
        raise wrap_agent_error(agent_name, "llm_invoke", e) from e


def invoke_structured_output(
    llm: Any,
    messages: list[BaseMessage],
    model_cls: type[TModel],
    *,
    agent_name: str,
) -> TModel:
    """
    Invoke an LLM and parse structured output into a Pydantic model.
    """
    try:
        if hasattr(llm, "with_structured_output"):
            structured_llm = llm.with_structured_output(model_cls)
            result = structured_llm.invoke(messages)
        else:
            result = llm.invoke(messages)
        return parse_structured_output(result, model_cls)
    except AgentExecutionError:
        raise
    except Exception as e:
        raise wrap_agent_error(agent_name, "structured_invoke", e) from e


def wrap_agent_error(
    agent_name: str,
    step: str,
    error: Exception,
    *,
    context: Optional[Mapping[str, Any]] = None,
) -> AgentExecutionError:
    """Create and log a consistent agent execution error."""
    message = f"{agent_name} failed during {step}: {error}"
    logger.error(message)
    if context:
        logger.debug(f"{agent_name} context at failure: {dict(context)}")

    return AgentExecutionError(
        agent_name=agent_name,
        step=step,
        message=message,
        details={"error_type": type(error).__name__},
        original_error=error,
    )


class BaseAgent:
    """Reusable base class that wraps common agent utilities."""

    def __init__(
        self,
        agent_name: str,
        *,
        llm: Optional[Any] = None,
        llm_factory: Optional[Callable[..., Any]] = None,
    ):
        self.agent_name = agent_name
        self._llm = llm
        self._llm_factory = llm_factory

    @property
    def llm(self) -> Any:
        if self._llm is None:
            self._llm = get_llm(llm_factory=self._llm_factory)
        return self._llm

    def build_messages(
        self,
        system_instruction: str,
        *,
        state: Optional[Mapping[str, Any]] = None,
        user_input: Optional[str] = None,
        additional_context: Optional[str] = None,
    ) -> list[BaseMessage]:
        return build_prompt_messages(
            system_instruction,
            state=state,
            user_input=user_input,
            additional_context=additional_context,
        )

    def invoke(self, messages: list[BaseMessage]) -> Any:
        return invoke_llm(self.llm, messages, agent_name=self.agent_name)

    def invoke_structured(self, messages: list[BaseMessage], model_cls: type[TModel]) -> TModel:
        return invoke_structured_output(
            self.llm,
            messages,
            model_cls,
            agent_name=self.agent_name,
        )


def _extract_payload(raw_output: Any) -> Any:
    if isinstance(raw_output, (dict, list, str)):
        return raw_output
    if hasattr(raw_output, "model_dump") and callable(raw_output.model_dump):
        return raw_output.model_dump()
    if hasattr(raw_output, "content"):
        return raw_output.content
    return raw_output


def _parse_json_payload(text: str) -> Any:
    stripped = text.strip()
    if not stripped:
        return {}

    # Handle fenced JSON outputs from LLMs.
    fenced_match = re.match(r"^```(?:json)?\s*(.*?)\s*```$", stripped, flags=re.DOTALL)
    if fenced_match:
        stripped = fenced_match.group(1).strip()

    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        # Attempt to parse first object/array block if extra commentary exists.
        block_match = re.search(r"(\{.*\}|\[.*\])", stripped, flags=re.DOTALL)
        if block_match:
            return json.loads(block_match.group(1))
        raise


__all__ = [
    "AgentExecutionError",
    "BaseAgent",
    "build_prompt_messages",
    "get_llm",
    "invoke_llm",
    "invoke_structured_output",
    "parse_structured_output",
    "wrap_agent_error",
]
