"""
Optional LLM-backed review provider.

This is a clean provider/service layer: the rest of the app only calls
`llm_service.review(code, language)` and never knows (or cares) which
provider is behind it. Nothing here is required for the app to work — when
no provider/key is configured, `enabled` is False and static analysis
covers the full review on its own.

Supported providers (set LLM_PROVIDER in the environment):
  - "anthropic": uses ANTHROPIC_API_KEY + the Messages API
  - "openai":    uses OPENAI_API_KEY + the Chat Completions API
  - "" (unset):  disabled

API keys are ALWAYS read from environment variables (see .env.example) and
are never hardcoded or logged.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List

from app.config import settings

logger = logging.getLogger("codeagent.llm")

SYSTEM_PROMPT = (
    "You are a precise, senior code reviewer acting as one agent inside a "
    "larger multi-agent static-analysis pipeline. You will be given source "
    "code and a language. Static analysis has already covered syntax, "
    "common security patterns, and simple logic/perf/quality rules — focus "
    "on issues that require real understanding of intent: subtle logic "
    "bugs, edge cases, API misuse, and design concerns. "
    "Respond with ONLY a JSON array (no prose, no markdown fences). Each "
    "element must be an object with keys: "
    '"severity" (one of "error","warning","info"), '
    '"category" (one of "logic","quality","security","performance"), '
    '"line" (integer or null), "message" (short, specific), '
    '"suggestion" (concrete, actionable). '
    "Return at most 8 findings. If the code looks solid, return []."
)


def _build_user_prompt(code: str, language: str) -> str:
    return f"Language: {language}\n\nSource code:\n```{language}\n{code}\n```"


def _extract_json_array(text: str) -> List[Dict[str, Any]]:
    text = text.strip()
    # Strip common markdown code-fence wrapping defensively.
    text = re.sub(r"^```(json)?", "", text.strip(), flags=re.IGNORECASE).strip()
    text = re.sub(r"```$", "", text.strip()).strip()
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if match:
        text = match.group(0)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        logger.warning("LLM response was not valid JSON; ignoring LLM findings for this request.")
        return []
    if not isinstance(data, list):
        return []
    return data


class LLMService:
    def __init__(self) -> None:
        self._settings = settings

    @property
    def enabled(self) -> bool:
        return self._settings.llm_enabled

    @property
    def provider(self) -> str:
        return self._settings.llm_provider or "none"

    async def review(self, code: str, language: str) -> List[Dict[str, Any]]:
        if not self.enabled:
            return []
        try:
            import httpx
        except ImportError:
            logger.warning("httpx is not installed; skipping LLM review. `pip install httpx` to enable it.")
            return []

        try:
            if self._settings.llm_provider == "anthropic":
                raw_items = await self._call_anthropic(httpx, code, language)
            elif self._settings.llm_provider == "openai":
                raw_items = await self._call_openai(httpx, code, language)
            else:
                return []
        except Exception as exc:  # never let an LLM outage break the whole review
            logger.warning("LLM review call failed (%s); continuing with static analysis only.", exc)
            return []

        findings: List[Dict[str, Any]] = []
        valid_severities = {"error", "warning", "info"}
        valid_categories = {"logic", "quality", "security", "performance"}
        for item in raw_items:
            if not isinstance(item, dict) or "message" not in item:
                continue
            severity = str(item.get("severity", "info")).lower()
            category = str(item.get("category", "quality")).lower()
            findings.append(
                {
                    "category": category if category in valid_categories else "quality",
                    "severity": severity if severity in valid_severities else "info",
                    "line": item.get("line") if isinstance(item.get("line"), int) else None,
                    "message": str(item["message"])[:500],
                    "suggestion": str(item.get("suggestion", ""))[:500] or None,
                    "rule": "llm-review",
                    "source": "llm",
                }
            )
        return findings

    async def _call_anthropic(self, httpx, code: str, language: str) -> List[Dict[str, Any]]:
        async with httpx.AsyncClient(timeout=self._settings.llm_timeout_seconds) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self._settings.anthropic_api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": self._settings.llm_model,
                    "max_tokens": 1500,
                    "system": SYSTEM_PROMPT,
                    "messages": [{"role": "user", "content": _build_user_prompt(code, language)}],
                },
            )
            resp.raise_for_status()
            data = resp.json()
            text = "".join(
                block.get("text", "") for block in data.get("content", []) if block.get("type") == "text"
            )
            return _extract_json_array(text)

    async def _call_openai(self, httpx, code: str, language: str) -> List[Dict[str, Any]]:
        async with httpx.AsyncClient(timeout=self._settings.llm_timeout_seconds) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._settings.openai_api_key}",
                    "content-type": "application/json",
                },
                json={
                    "model": self._settings.llm_model,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": _build_user_prompt(code, language)},
                    ],
                    "temperature": 0.2,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            text = data["choices"][0]["message"]["content"]
            return _extract_json_array(text)


llm_service = LLMService()
