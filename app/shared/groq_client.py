"""Small Groq connection; workflow decisions belong in the graph."""

from app.config import Settings
from app.shared.groq_rate_limit import GroqRateLimit


class GroqModel:
    def __init__(self, settings: Settings, client=None, *, rate_limit=None) -> None:
        self.settings = settings
        self.rate_limit = rate_limit if rate_limit is not None else GroqRateLimit(settings)
        self.raw_responses = client is None
        if client is not None:
            self.client = client
            return
        key = settings.groq_api_key.get_secret_value().strip()
        if not key:
            raise ValueError("Set RFP_GROQ_API_KEY in your local .env before calling the model")
        try:
            from groq import Groq
        except ImportError as error:
            raise RuntimeError("Install agent dependencies: pip install -e '.[agents]'") from error
        # The shared handler owns retries; avoid nested SDK retry loops.
        self.client = Groq(api_key=key, timeout=settings.llm_timeout, max_retries=0)

    def _request(self, arguments: dict):
        if self.raw_responses:
            raw = self.client.chat.completions.with_raw_response.create(**arguments)
            return raw.parse(), raw.headers
        return self.client.chat.completions.create(**arguments), {}

    def complete(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        *,
        tool_choice: str | None = None,
        response_format: dict | None = None,
    ) -> dict:
        """Return the assistant message and usage for later workflow logging.

        Tool requests are returned to the caller, never executed by this adapter.
        SDK failures propagate so the workflow can handle them explicitly.
        """
        if not messages:
            raise ValueError("At least one message is required")
        arguments = {
            "model": self.settings.llm_model,
            "messages": messages,
            "max_completion_tokens": self.settings.llm_max_tokens,
            "temperature": 0,
        }
        if tools:
            arguments["tools"] = tools
        if tool_choice is not None:
            arguments["tool_choice"] = tool_choice
        if response_format is not None:
            arguments["response_format"] = response_format
        response = self.rate_limit.execute(
            lambda: self._request(arguments), self.rate_limit.estimate(arguments)
        )
        if not response.choices:
            raise ValueError("Model returned no assistant message")
        choice = response.choices[0]
        return {
            "message": choice.message.model_dump(exclude_none=True),
            "usage": response.usage.model_dump() if response.usage else {},
            "finish_reason": choice.finish_reason,
        }
