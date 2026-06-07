from __future__ import annotations

import json
import os
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ..exceptions import WorkbenchException
from .gas_portfolio import query_gas_portfolio_report
from .gas_risk_pack import query_gas_risk_pack

LOCAL_LLM_PORTFOLIO_ERROR = "LOCAL_LLM_PORTFOLIO_ERROR"

HttpPost = Callable[[str, dict[str, str], bytes, float], dict[str, Any]]


def run_local_llm_portfolio_question(
    report: dict[str, Any],
    question: str,
    *,
    run_id: str = "local-llm-gas-portfolio-question",
    dry_run: bool = False,
    base_url: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
    timeout_seconds: float = 30.0,
    http_post: HttpPost | None = None,
) -> dict[str, Any]:
    tool_response = query_gas_portfolio_report(report, question, run_id=f"{run_id}-tool")
    prompt = _narration_prompt(tool_response)

    if dry_run:
        narration = _dry_run_narration(tool_response)
        provider = {
            "kind": "deterministic_dry_run",
            "model_calls": False,
            "model": "none",
            "base_url": None,
        }
    else:
        resolved_base_url = (base_url or os.environ.get("ARTEMIS_OPENAI_COMPATIBLE_BASE_URL") or "http://localhost:11434/v1").rstrip("/")
        resolved_model = model or os.environ.get("ARTEMIS_OPENAI_COMPATIBLE_MODEL")
        if not resolved_model:
            raise WorkbenchException(
                LOCAL_LLM_PORTFOLIO_ERROR,
                "Local LLM model is required; pass --model or set ARTEMIS_OPENAI_COMPATIBLE_MODEL",
            )
        resolved_api_key = api_key if api_key is not None else os.environ.get("ARTEMIS_OPENAI_COMPATIBLE_API_KEY") or os.environ.get("OLLAMA_API_KEY") or ""
        narration = _call_openai_compatible_chat(
            resolved_base_url,
            resolved_model,
            resolved_api_key,
            prompt,
            timeout_seconds,
            http_post=http_post,
        )
        provider = {
            "kind": "openai_compatible",
            "model_calls": True,
            "model": resolved_model,
            "base_url": resolved_base_url,
        }

    return {
        "run_id": run_id,
        "question": question,
        "tool_first": True,
        "tool_response": tool_response,
        "prompt": prompt,
        "narration": narration,
        "provider": provider,
        "authority": "deterministic_tool_response",
        "agent_scope": "local_llm_may_narrate_tool_facts_only",
    }


def run_local_llm_gas_risk_pack_question(
    pack: dict[str, Any],
    question: str,
    *,
    run_id: str = "local-llm-gas-risk-question",
    dry_run: bool = False,
    base_url: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
    timeout_seconds: float = 30.0,
    http_post: HttpPost | None = None,
) -> dict[str, Any]:
    tool_response = query_gas_risk_pack(pack, question, run_id=f"{run_id}-tool")
    return _run_llm_over_tool_response(
        tool_response,
        question,
        run_id=run_id,
        dry_run=dry_run,
        base_url=base_url,
        model=model,
        api_key=api_key,
        timeout_seconds=timeout_seconds,
        http_post=http_post,
    )


def _run_llm_over_tool_response(
    tool_response: dict[str, Any],
    question: str,
    *,
    run_id: str,
    dry_run: bool,
    base_url: str | None,
    model: str | None,
    api_key: str | None,
    timeout_seconds: float,
    http_post: HttpPost | None,
) -> dict[str, Any]:
    prompt = _narration_prompt(tool_response)
    if dry_run:
        narration = _dry_run_narration(tool_response)
        provider = {
            "kind": "deterministic_dry_run",
            "model_calls": False,
            "model": "none",
            "base_url": None,
        }
    else:
        resolved_base_url = (base_url or os.environ.get("ARTEMIS_OPENAI_COMPATIBLE_BASE_URL") or "http://localhost:11434/v1").rstrip("/")
        resolved_model = model or os.environ.get("ARTEMIS_OPENAI_COMPATIBLE_MODEL")
        if not resolved_model:
            raise WorkbenchException(
                LOCAL_LLM_PORTFOLIO_ERROR,
                "Local LLM model is required; pass --model or set ARTEMIS_OPENAI_COMPATIBLE_MODEL",
            )
        resolved_api_key = api_key if api_key is not None else os.environ.get("ARTEMIS_OPENAI_COMPATIBLE_API_KEY") or os.environ.get("OLLAMA_API_KEY") or ""
        narration = _call_openai_compatible_chat(
            resolved_base_url,
            resolved_model,
            resolved_api_key,
            prompt,
            timeout_seconds,
            http_post=http_post,
        )
        provider = {
            "kind": "openai_compatible",
            "model_calls": True,
            "model": resolved_model,
            "base_url": resolved_base_url,
        }
    return {
        "run_id": run_id,
        "question": question,
        "tool_first": True,
        "tool_response": tool_response,
        "prompt": prompt,
        "narration": narration,
        "provider": provider,
        "authority": "deterministic_tool_response",
        "agent_scope": "local_llm_may_narrate_tool_facts_only",
    }


def _narration_prompt(tool_response: dict[str, Any]) -> str:
    return (
        "You are a non-authoritative trading analytics narrator. "
        "Use only the deterministic JSON tool response below. "
        "Do not add calculations, recommendations, missing data, or facts not present in JSON. "
        "If supported is false, say the tool does not support the question.\n\n"
        f"DETERMINISTIC_TOOL_RESPONSE:\n{json.dumps(tool_response, sort_keys=True)}"
    )


def _dry_run_narration(tool_response: dict[str, Any]) -> str:
    if not tool_response.get("supported"):
        return f"Unsupported by deterministic tool: {tool_response.get('answer')}"
    return str(tool_response.get("answer") or "")


def _call_openai_compatible_chat(
    base_url: str,
    model: str,
    api_key: str,
    prompt: str,
    timeout_seconds: float,
    *,
    http_post: HttpPost | None = None,
) -> str:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "Narrate deterministic tool facts only."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0,
        "stream": False,
    }
    body = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        data = (http_post or _urllib_post)(f"{base_url}/chat/completions", headers, body, timeout_seconds)
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise WorkbenchException(LOCAL_LLM_PORTFOLIO_ERROR, f"Local LLM call failed: {exc.__class__.__name__}") from exc

    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        raise WorkbenchException(LOCAL_LLM_PORTFOLIO_ERROR, "Local LLM response missing choices")
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    if not isinstance(message, dict):
        raise WorkbenchException(LOCAL_LLM_PORTFOLIO_ERROR, "Local LLM response missing message")
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise WorkbenchException(LOCAL_LLM_PORTFOLIO_ERROR, "Local LLM response missing content")
    return content.strip()


def _urllib_post(url: str, headers: dict[str, str], body: bytes, timeout_seconds: float) -> dict[str, Any]:
    request = Request(url, data=body, headers=headers, method="POST")
    with urlopen(request, timeout=timeout_seconds) as response:
        return json.loads(response.read().decode("utf-8"))
