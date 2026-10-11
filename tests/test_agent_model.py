from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.config import Settings
from app.shared.groq_client import GroqModel


def test_model_returns_tool_request_and_usage_without_executing_it():
    message = {"role": "assistant", "tool_calls": [{"id": "call_1"}]}
    client = Mock()
    client.chat.completions.create.return_value = SimpleNamespace(
        choices=[SimpleNamespace(message=Mock(), finish_reason="tool_calls")],
        usage=Mock(),
    )
    response = client.chat.completions.create.return_value
    response.choices[0].message.model_dump.return_value = message
    response.usage.model_dump.return_value = {"total_tokens": 15}
    settings = Settings(_env_file=None, llm_model="test-model", llm_max_tokens=100)
    result = GroqModel(settings, client).complete(
        [{"role": "user", "content": "Find the deadline"}], tools=[{"type": "function"}]
    )
    assert result["message"] == message
    assert result["usage"] == {"total_tokens": 15}
    arguments = client.chat.completions.create.call_args.kwargs
    assert arguments["model"] == "test-model"
    assert arguments["max_completion_tokens"] == 100
    assert arguments["tools"] == [{"type": "function"}]


def test_model_requires_key_without_injected_client(monkeypatch):
    monkeypatch.delenv("RFP_GROQ_API_KEY", raising=False)
    with pytest.raises(ValueError, match="RFP_GROQ_API_KEY"):
        GroqModel(Settings(_env_file=None, groq_api_key=""))


def test_model_propagates_failures_and_rejects_empty_responses():
    client = Mock()
    model = GroqModel(Settings(_env_file=None), client)
    with pytest.raises(ValueError, match="At least one"):
        model.complete([])
    client.chat.completions.create.side_effect = TimeoutError()
    with pytest.raises(TimeoutError):
        model.complete([{"role": "user", "content": "Hello"}])
    client.chat.completions.create.side_effect = None
    client.chat.completions.create.return_value = SimpleNamespace(choices=[])
    with pytest.raises(ValueError, match="no assistant"):
        model.complete([{"role": "user", "content": "Hello"}])
