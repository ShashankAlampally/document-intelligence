"""Manual connection check; does not search documents or run an agent."""

from app.config import Settings
from app.shared.groq_client import GroqModel


def main() -> None:
    try:
        result = GroqModel(Settings()).complete(
            [{"role": "user", "content": "Reply with exactly: Connection working"}]
        )
    except Exception as error:
        # Avoid printing provider exceptions, which may contain request details.
        raise SystemExit(
            f"Connection failed ({type(error).__name__}). Check key, model, network and quota."
        ) from None
    print(result["message"].get("content", "No text returned"))
    print(f"Token usage: {result['usage']}")


if __name__ == "__main__":
    main()
