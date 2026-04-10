"""
Tests for Module M9: Base Agent utilities.

Validates:
- LLM instantiation
- Prompt builder behavior
- Structured output parsing
- Error wrapping
"""

import os
import sys
from types import SimpleNamespace
from unittest.mock import patch

from pydantic import BaseModel

sys.path.insert(0, os.path.abspath("."))

from backend.agents.base_agent import (
    AgentExecutionError,
    BaseAgent,
    build_prompt_messages,
    get_llm,
    parse_structured_output,
    wrap_agent_error,
)
from langchain_core.messages import HumanMessage, SystemMessage


class DemoModel(BaseModel):
    answer: str
    score: int


def test_llm_instantiation_with_injected_factory() -> None:
    print("\n[1] Testing get_llm() instantiation with injectable factory...")
    captured = {}

    class FakeLLM:
        pass

    def fake_factory(**kwargs):
        captured.update(kwargs)
        return FakeLLM()

    fake_settings = SimpleNamespace(
        groq_api_key="groq_test_key",
        groq_model_name="llama-test-model",
    )

    with patch("backend.agents.base_agent.get_settings", return_value=fake_settings):
        llm = get_llm(llm_factory=fake_factory, temperature=0.1)

    assert isinstance(llm, FakeLLM)
    assert captured["api_key"] == "groq_test_key"
    assert captured["temperature"] == 0.1
    assert captured.get("model") == "llama-test-model" or captured.get("model_name") == "llama-test-model"
    print("  OK: get_llm() used settings + factory correctly")


def test_prompt_builder_output() -> None:
    print("\n[2] Testing prompt builder...")
    messages = build_prompt_messages(
        "You are a travel planner.",
        state={"destination": "Paris", "budget": 2000},
        user_input="Plan a 3-day itinerary.",
        additional_context="Keep suggestions budget friendly.",
    )

    assert len(messages) == 2
    assert isinstance(messages[0], SystemMessage)
    assert isinstance(messages[1], HumanMessage)
    assert "travel planner" in messages[0].content.lower()
    assert "destination" in messages[1].content
    assert "Plan a 3-day itinerary." in messages[1].content
    print("  OK: prompt builder composes expected message structure")


def test_structured_output_parsing() -> None:
    print("\n[3] Testing structured output parser...")
    parsed_from_dict = parse_structured_output(
        {"answer": "looks good", "score": 9},
        DemoModel,
    )
    assert parsed_from_dict.answer == "looks good"
    assert parsed_from_dict.score == 9

    class FakeMessage:
        content = '{"answer":"from-json","score":7}'

    parsed_from_message = parse_structured_output(FakeMessage(), DemoModel)
    assert parsed_from_message.answer == "from-json"
    assert parsed_from_message.score == 7
    print("  OK: structured parser handles dict + message content")


def test_structured_output_parse_error() -> None:
    print("\n[4] Testing structured output parse failure wrapping...")
    try:
        parse_structured_output("not-json-at-all", DemoModel)
        print("  FAIL: parser should have raised AgentExecutionError")
        sys.exit(1)
    except AgentExecutionError as err:
        assert err.step == "structured_parse"
        print("  OK: invalid payload is wrapped as AgentExecutionError")


def test_error_wrapper() -> None:
    print("\n[5] Testing wrap_agent_error helper...")
    wrapped = wrap_agent_error(
        "greeting_agent",
        "invoke",
        ValueError("bad prompt"),
        context={"thread_id": "thread-123"},
    )
    assert isinstance(wrapped, AgentExecutionError)
    assert wrapped.agent_name == "greeting_agent"
    assert wrapped.step == "invoke"
    assert "bad prompt" in wrapped.message
    print("  OK: wrap_agent_error creates structured error")


def test_base_agent_with_injected_llm() -> None:
    print("\n[6] Testing BaseAgent with injected mock LLM...")

    class MockLLM:
        def invoke(self, _messages):
            return {"answer": "mocked", "score": 5}

        def with_structured_output(self, _model_cls):
            return self

    agent = BaseAgent("test_agent", llm=MockLLM())
    messages = agent.build_messages(
        "You are a tester.",
        state={"phase": "debug"},
        user_input="Say hi",
    )
    parsed = agent.invoke_structured(messages, DemoModel)
    assert parsed.answer == "mocked"
    assert parsed.score == 5
    print("  OK: BaseAgent invoke_structured works with injected LLM")


if __name__ == "__main__":
    print("=" * 60)
    print("M9 Base Agent Tests")
    print("=" * 60)
    try:
        test_llm_instantiation_with_injected_factory()
        test_prompt_builder_output()
        test_structured_output_parsing()
        test_structured_output_parse_error()
        test_error_wrapper()
        test_base_agent_with_injected_llm()
        print("\n" + "=" * 60)
        print("✓ All M9 tests passed!")
        print("=" * 60)
    except Exception as e:
        print(f"\nFAIL: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
