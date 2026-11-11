from langchain_anthropic import ChatAnthropic
from app.config import settings

def get_llm():
    return ChatAnthropic(
        model=settings.ANTHROPIC_MODEL,
        api_key=settings.ANTHROPIC_API_KEY,
    )

