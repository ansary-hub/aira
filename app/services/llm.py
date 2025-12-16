import asyncio

from google import genai
from google.genai import types

from app.config import get_settings

settings = get_settings()

# Module-level client (reused across calls)
_client: genai.Client | None = None


def get_gemini_client() -> genai.Client:
    """Get Google Gemini client (singleton)."""
    global _client
    if _client is None:
        _client = genai.Client(api_key=settings.google_api_key)
    return _client


async def generate_content(
    prompt: str,
    model: str | None = None,
    temperature: float | None = None,
) -> str:
    """
    Generate content using Google Gemini.

    Args:
        prompt: The prompt to send to the model
        model: Model to use (defaults to settings.gemini_model)
        temperature: Temperature for generation (defaults to settings.llm_temperature)

    Returns:
        Generated text response
    """
    client = get_gemini_client()
    model_name = model or settings.gemini_model
    temp = temperature if temperature is not None else settings.llm_temperature

    # Run synchronous API call in thread pool to avoid blocking
    def _call_api() -> str:
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=temp,
            ),
        )
        return response.text

    return await asyncio.to_thread(_call_api)
