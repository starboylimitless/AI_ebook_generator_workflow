from __future__ import annotations
from dotenv import load_dotenv
load_dotenv()

import os
import time
from typing import List, Dict, Any
from openai import OpenAI


class LLMClient:
    """
    Production-safe LLM client.

    Features:
    - Uses GPT-4o-mini (lowest cost reliable model)
    - Automatic retries
    - Prevents blank outputs
    - Forces JSON responses
    - Safe for multi-agent pipelines
    """

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        temperature: float = 0.1,
        max_retries: int = 3,
    ):
        api_key = os.getenv("OPENAI_API_KEY")

        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment.")

        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.temperature = temperature
        self.max_retries = max_retries

        print(f"✅ LLM Client initialized → {model}")

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        extra_messages: List[Dict[str, str]] | None = None,
        temperature: float | None = None,
        max_tokens: int = 4000,
    ) -> str:
        """
        Generate response with retries + validation.
        Always returns non-empty text.
        """

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        if extra_messages:
            messages.extend(extra_messages)

        temperature = temperature if temperature is not None else self.temperature

        last_error = None

        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    response_format={"type": "json_object"},  # 🔥 forces valid JSON
                )

                output = response.choices[0].message.content

                if not output or not output.strip():
                    raise ValueError("Empty response from model")

                return output

            except Exception as e:
                last_error = e
                print(f"⚠ LLM error attempt {attempt}: {e}")
                time.sleep(attempt * 1.5)

        raise RuntimeError(f"LLM failed after retries: {last_error}")


# backward compatibility
MockLLMClient = LLMClient
