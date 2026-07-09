from __future__ import annotations

import json
import re
import socket
import urllib.error
import urllib.request
from collections.abc import Iterator
from typing import Any, Type, TypeVar

from pydantic import BaseModel, ValidationError

from app.core.config import get_settings

T = TypeVar("T", bound=BaseModel)


class LLMConfigurationError(RuntimeError):
    pass


class LLMResponseError(RuntimeError):
    pass


def validate_qwen_config() -> None:
    settings = get_settings()
    if settings.llm_provider.lower() != "qwen":
        raise LLMConfigurationError("LLM_PROVIDER 必须设置为 qwen")
    if not settings.qwen_api_key:
        raise LLMConfigurationError("缺少 QWEN_API_KEY，请在 backend/.env 中配置千问 API Key")


def _extract_json_object(text: str) -> Any:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    start_candidates = [index for index in [cleaned.find("{"), cleaned.find("[")] if index >= 0]
    if not start_candidates:
        raise LLMResponseError("模型未返回 JSON 内容")
    start = min(start_candidates)
    end = max(cleaned.rfind("}"), cleaned.rfind("]"))
    if end <= start:
        raise LLMResponseError("模型 JSON 内容不完整")
    return json.loads(cleaned[start : end + 1])


def qwen_chat_json(system_prompt: str, user_prompt: str, schema_model: Type[T]) -> T:
    settings = get_settings()
    validate_qwen_config()

    payload = {
        "model": settings.qwen_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.3,
        "response_format": {"type": "json_object"},
    }
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        f"{settings.qwen_base_url.rstrip('/')}/chat/completions",
        data=data,
        headers={
            "Authorization": f"Bearer {settings.qwen_api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=settings.qwen_timeout_seconds) as response:
            body = json.loads(response.read().decode("utf-8"))
    except (TimeoutError, socket.timeout) as exc:
        raise LLMResponseError(f"千问接口请求超时：{settings.qwen_timeout_seconds} 秒内未返回") from exc
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise LLMResponseError(f"千问接口返回错误：{exc.code} {detail}") from exc
    except urllib.error.URLError as exc:
        raise LLMResponseError(f"无法连接千问接口：{exc.reason}") from exc

    try:
        content = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMResponseError("千问接口响应缺少 choices[0].message.content") from exc

    raw_json = _extract_json_object(content)
    try:
        return schema_model.model_validate(raw_json)
    except ValidationError as exc:
        raise LLMResponseError(f"模型 JSON 未通过结构校验：{exc}") from exc


def qwen_chat_stream_text(system_prompt: str, user_prompt: str) -> Iterator[str]:
    settings = get_settings()
    validate_qwen_config()

    payload = {
        "model": settings.qwen_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.3,
        "stream": True,
    }
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        f"{settings.qwen_base_url.rstrip('/')}/chat/completions",
        data=data,
        headers={
            "Authorization": f"Bearer {settings.qwen_api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=settings.qwen_timeout_seconds) as response:
            for raw_line in response:
                line = raw_line.decode("utf-8", errors="ignore").strip()
                if not line or not line.startswith("data:"):
                    continue
                payload_text = line.removeprefix("data:").strip()
                if payload_text == "[DONE]":
                    break
                try:
                    body = json.loads(payload_text)
                except json.JSONDecodeError:
                    continue
                choices = body.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta") or {}
                content = delta.get("content")
                if content:
                    yield content
    except (TimeoutError, socket.timeout) as exc:
        raise LLMResponseError(f"千问流式接口请求超时：{settings.qwen_timeout_seconds} 秒内未返回") from exc
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise LLMResponseError(f"千问流式接口返回错误：{exc.code} {detail}") from exc
    except urllib.error.URLError as exc:
        raise LLMResponseError(f"无法连接千问流式接口：{exc.reason}") from exc
