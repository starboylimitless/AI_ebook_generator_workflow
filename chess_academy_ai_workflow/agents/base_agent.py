from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from chess_academy_ai_workflow.utils.llm_client import LLMClient
from chess_academy_ai_workflow.utils.logging_utils import setup_logger


class AgentError(Exception):
    pass


class BaseAgent(ABC):
    """
    Base class for all agents providing:

    ✔ Shared LLM client
    ✔ Logging
    ✔ Retry logic
    ✔ JSON IO helpers
    ✔ Strict JSON parsing (production safe)
    ✔ Execution timing
    ✔ Schema validation helpers
    """

    def __init__(
        self,
        name: str,
        prompts_dir: Path,
        output_dir: Path,
        llm_client: Optional[LLMClient] = None,
        max_retries: int = 2,
    ) -> None:
        self.name = name
        self.prompts_dir = prompts_dir
        self.output_dir = output_dir
        self.llm = llm_client
        self.max_retries = max_retries
        self.logger = setup_logger(f"agent.{name}")

    # --------------------------------------------------
    # ABSTRACT METHODS
    # --------------------------------------------------

    @abstractmethod
    def run(self, *args: Any, **kwargs: Any) -> Any:
        ...

    @abstractmethod
    def validate(self, result: Any) -> None:
        ...

    # --------------------------------------------------
    # PROMPT LOADING
    # --------------------------------------------------

    def _load_prompt(self, filename: str) -> str:
        path = self.prompts_dir / filename
        if not path.exists():
            raise FileNotFoundError(f"Prompt file not found: {path}")

        with path.open("r", encoding="utf-8") as f:
            return f.read()

    # --------------------------------------------------
    # LLM CALLS
    # --------------------------------------------------

    def _call_llm(self, prompt_file: str, user_prompt: str) -> str:
        """
        Raw LLM call (string response).
        """
        system_prompt = self._load_prompt(prompt_file)
        self.logger.info("Calling LLM for %s", self.name)

        if self.llm is None:
            self.llm = LLMClient()
        response = self.llm.complete(system_prompt, user_prompt)

        if not isinstance(response, str):
            raise ValueError("LLM returned non-string response")

        return response.strip()

    def _call_llm_json(self, prompt_file: str, user_prompt: str) -> Dict[str, Any]:
        """
        Production-safe JSON extraction.
        Automatically strips markdown fences and extra commentary.
        """

        raw = self._call_llm(prompt_file, user_prompt)

        # Remove markdown fences if present
        raw = raw.replace("```json", "").replace("```", "").strip()

        # Extract first JSON object found
        start = raw.find("{")
        end = raw.rfind("}")

        if start == -1 or end == -1:
            self.logger.error("No JSON object found in LLM output:\n%s", raw)
            raise ValueError("LLM did not return JSON")

        cleaned = raw[start:end + 1]

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            self.logger.error("Invalid JSON returned from LLM:\n%s", cleaned)
            raise ValueError("LLM returned malformed JSON") from e

    # --------------------------------------------------
    # RETRY EXECUTION
    # --------------------------------------------------

    def _run_with_retries(self, execute_fn, description: str) -> Any:
        """
        Executes function with retry + validation + timing.
        """

        last_error: Optional[Exception] = None

        for attempt in range(self.max_retries + 1):
            try:
                self.logger.info(
                    "Starting %s (attempt %d)", description, attempt + 1
                )

                start_time = time.time()

                result = execute_fn()

                self.validate(result)

                duration = time.time() - start_time
                self.logger.info(
                    "Completed %s successfully in %.2fs",
                    description,
                    duration,
                )

                return result

            except Exception as e:
                last_error = e
                self.logger.exception(
                    "Error during %s on attempt %d: %s",
                    description,
                    attempt + 1,
                    e,
                )

                if attempt < self.max_retries:
                    time.sleep(1.0 * (attempt + 1))
                else:
                    break

        raise AgentError(f"{self.name} failed after retries") from last_error

    # --------------------------------------------------
    # JSON OUTPUT
    # --------------------------------------------------

    def _save_json(self, data: Any, filename: str) -> Path:
        path = self.output_dir / filename
        path.parent.mkdir(parents=True, exist_ok=True)

        if is_dataclass(data):
            serializable = asdict(data)
        else:
            serializable = data

        with path.open("w", encoding="utf-8") as f:
            json.dump(serializable, f, indent=2, ensure_ascii=False)

        self.logger.info("Wrote JSON output to %s", path)
        return path

    # --------------------------------------------------
    # VALIDATION HELPERS
    # --------------------------------------------------

    def _require_fields(self, data: Dict[str, Any], fields: list[str]) -> None:
        """
        Utility for schema validation inside agents.
        """
        for field in fields:
            if field not in data:
                raise ValueError(f"Missing required field: {field}")
