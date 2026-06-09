import os

from langchain_openai import ChatOpenAI


class QwenLLMFactory:
    BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    DEFAULT_MODEL = "deepseek-v4-flash"

    @staticmethod
    def get_llm(model=None, temperature=None):
        if temperature is None:
            raise ValueError("Parameter 'temperature' must be specified.")

        api_key = os.getenv("DASHSCOPE_API_KEY")
        if not api_key:
            raise ValueError(
                "Missing DASHSCOPE_API_KEY. Please set DASHSCOPE_API_KEY in your .env file."
            )

        return ChatOpenAI(
            model=model or QwenLLMFactory.DEFAULT_MODEL,
            temperature=temperature,
            streaming=True,
            api_key=api_key,
            base_url=QwenLLMFactory.BASE_URL,
        )
