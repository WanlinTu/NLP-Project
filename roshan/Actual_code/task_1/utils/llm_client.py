"""
LLM client wrapper supporting both ACCRE (vLLM/Qwen) and OpenAI API.
Handles retries, concurrency control, and structured JSON parsing.
"""

import json
import logging
import os
import time
import threading
from typing import Any, Optional

from openai import OpenAI

from config import (
    PROVIDER,
    ACCRE_BASE_URL, ACCRE_API_KEY, ACCRE_MODEL,
    OPENAI_BASE_URL, OPENAI_MODEL,
    TEMPERATURE, MAX_RETRIES, RETRY_BASE_DELAY, REQUEST_TIMEOUT,
    MAX_IN_FLIGHT_LLM,
)

log = logging.getLogger(__name__)

# Global concurrency limiter
_semaphore = threading.BoundedSemaphore(MAX_IN_FLIGHT_LLM)


def get_client() -> tuple[OpenAI, str]:
    """
    Create an OpenAI client based on the configured provider.

    Returns:
        (client, model_name)
    """
    if PROVIDER == "accre":
        client = OpenAI(base_url=ACCRE_BASE_URL, api_key=ACCRE_API_KEY)
        model = ACCRE_MODEL
    elif PROVIDER == "openai":
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")
        client = OpenAI(base_url=OPENAI_BASE_URL, api_key=api_key)
        model = OPENAI_MODEL
    else:
        raise ValueError(f"Unknown provider: {PROVIDER}")

    return client, model


def call_llm(
    client: OpenAI,
    model: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float = TEMPERATURE,
    max_tokens: int = 4096,
) -> Optional[str]:
    """
    Call the LLM with retry logic and concurrency control.

    Returns the response content string, or None on failure.
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with _semaphore:
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout=REQUEST_TIMEOUT,
                )
            content = response.choices[0].message.content
            return content

        except Exception as e:
            delay = RETRY_BASE_DELAY * (2 ** (attempt - 1))
            log.warning(f"  LLM call attempt {attempt}/{MAX_RETRIES} failed: {e}. Retrying in {delay}s...")
            if attempt < MAX_RETRIES:
                time.sleep(delay)
            else:
                log.error(f"  LLM call failed after {MAX_RETRIES} attempts: {e}")
                return None


def call_llm_json(
    client: OpenAI,
    model: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float = TEMPERATURE,
    max_tokens: int = 4096,
) -> Optional[Any]:
    """
    Call the LLM and parse the response as JSON.

    Handles cases where the LLM wraps JSON in markdown code blocks.
    Returns parsed JSON object, or None on failure.
    """
    content = call_llm(client, model, system_prompt, user_prompt, temperature, max_tokens)
    if content is None:
        return None

    return parse_json_response(content)


def parse_json_response(content: str) -> Optional[Any]:
    """
    Parse JSON from LLM response, handling markdown code blocks.
    """
    # Strip markdown code blocks if present
    content = content.strip()
    if content.startswith("```"):
        # Remove opening ```json or ```
        content = content.split("\n", 1)[1] if "\n" in content else content[3:]
        # Remove closing ```
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        # Try to find JSON within the response
        # Look for the first { or [ and last } or ]
        start_obj = content.find("{")
        start_arr = content.find("[")
        if start_obj == -1 and start_arr == -1:
            log.error(f"  No JSON found in response: {content[:200]}...")
            return None

        if start_arr != -1 and (start_obj == -1 or start_arr < start_obj):
            start = start_arr
            end = content.rfind("]")
        else:
            start = start_obj
            end = content.rfind("}")

        if end == -1 or end <= start:
            log.error(f"  Malformed JSON in response: {content[:200]}...")
            return None

        try:
            return json.loads(content[start:end + 1])
        except json.JSONDecodeError as e:
            log.error(f"  JSON parse error: {e}. Content: {content[start:start+200]}...")
            return None
