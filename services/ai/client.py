import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


class AIClient:

    def __init__(self):

        self.client = OpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL"),
        )

        self.model = os.getenv(
            "MODEL",
            "deepseek-chat"
        )

    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
    ) -> str:

        if system_prompt is None:
            system_prompt = (
                "You are a senior Product Design mentor. "
                "Always return valid JSON only. "
                "Never use markdown. "
                "Never invent information."
            )

        response = self.client.chat.completions.create(
            model=self.model,
            temperature=0.2,
            messages=[
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
        )

        return response.choices[0].message.content.strip()


ai_client = AIClient()