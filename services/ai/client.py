import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

DEFAULT_SYSTEM_PROMPT_PATH = (
    Path(__file__).resolve().parents[2] / "prompts" / "default_system.txt"
)
AVALAI_BASE_URL = "https://api.avalai.ir/v1"


class AIClient:

    def __init__(self):
        api_key = os.getenv("AVALAI_API_KEY")
        if not api_key:
            raise RuntimeError("AVALAI_API_KEY environment variable is not configured.")

        self.client = OpenAI(
            api_key=api_key,
            base_url=AVALAI_BASE_URL,
            timeout=float(os.getenv("AVALAI_TIMEOUT_SECONDS", "60")),
            max_retries=int(os.getenv("AVALAI_MAX_RETRIES", "2")),
        )

        self.model = os.getenv("AVALAI_MODEL", "deepseek-v4-pro")

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
