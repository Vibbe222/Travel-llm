from langchain_openai import ChatOpenAI

from settings import get_settings


class QwenLLMFactory:
    @staticmethod
    def get_llm(model=None, temperature=None):
        if temperature is None:
            raise ValueError("Parameter 'temperature' must be specified.")

        settings = get_settings()
        if not settings.dashscope_api_key:
            raise ValueError(
                "Missing DASHSCOPE_API_KEY. Please set DASHSCOPE_API_KEY in your .env file."
            )

        return ChatOpenAI(
            model=model or settings.model_name,
            temperature=temperature,
            streaming=True,
            api_key=settings.dashscope_api_key,
            base_url=settings.dashscope_base_url,
        )
