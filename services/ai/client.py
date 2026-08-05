import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

DEFAULT_SYSTEM_PROMPT_PATH = (
    Path(__file__).resolve().parents[2] / "prompts" / "default_system.txt"
)

class AIClient:

    def __init__(self):

        self.client = OpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL"),
            timeout=float(os.getenv("OPENAI_TIMEOUT_SECONDS", "60")),
            max_retries=int(os.getenv("OPENAI_MAX_RETRIES", "2")),
        )

        self.model = os.getenv("MODEL", "deepseek-chat")

    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
    ) -> str:

        if system_prompt is None:
            system_prompt = DEFAULT_SYSTEM_PROMPT_PATH.read_text(
                encoding="utf-8-sig",
            ).strip()

        response = self.client.chat.completions.create(
            model=self.model,
            temperature=0,
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

        content = response.choices[0].message.content
        if not content:
            raise ValueError("AI response did not contain any content.")

        return content.strip()


ai_client = AIClient()
