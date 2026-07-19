from __future__ import annotations

import json
import re
import socket
import urllib.error
import urllib.request
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, Optional, Type, TypeVar

from pydantic import BaseModel, ValidationError

from app.core.config import get_settings
from app.models.user import User
from app.services.grounding_guidance import GROUNDING_SYSTEM_SUFFIX
from app.services.json_repair_service import LLMJsonParseError, parse_llm_json

T = TypeVar("T", bound=BaseModel)


class LLMConfigurationError(RuntimeError):
    pass


class LLMResponseError(RuntimeError):
    pass


@dataclass(frozen=True)
class ChatModelConfig:
    provider: str
    model: str
    base_url: str
    api_key: str
    timeout_seconds: int


def resolve_chat_config(user: Optional[User] = None, *, timeout_seconds: Optional[int] = None) -> ChatModelConfig:
    settings = get_settings()
    provider = (getattr(user, "llm_provider", "") or settings.llm_provider or "qwen").strip()
    model = (getattr(user, "llm_model", "") or settings.qwen_model).strip()
    base_url = (getattr(user, "llm_base_url", "") or settings.qwen_base_url).strip().rstrip("/")
    api_key = (getattr(user, "llm_api_key", "") or settings.qwen_api_key).strip()
    return ChatModelConfig(
        provider=provider,
        model=model,
        base_url=base_url,
        api_key=api_key,
        timeout_seconds=timeout_seconds or settings.qwen_timeout_seconds,
    )


def validate_qwen_config(user: Optional[User] = None) -> None:
    config = resolve_chat_config(user)
    if not config.api_key:
        raise LLMConfigurationError("缺少模型 API Key，请在系统设置中配置，或在 backend/.env 中配置管理员默认 Key。")
    if not config.base_url:
        raise LLMConfigurationError("缺少模型 Base URL，请在系统设置中配置。")


def _extract_json_object(text: str) -> Any:
    try:
        return parse_llm_json(text)
    except LLMJsonParseError as exc:
        raise LLMResponseError(str(exc)) from exc


def qwen_chat_json(system_prompt: str, user_prompt: str, schema_model: Type[T], user: Optional[User] = None) -> T:
    config = resolve_chat_config(user)
    validate_qwen_config(user)

    payload = {
        "model": config.model,
        "messages": [
            {"role": "system", "content": f"{system_prompt}\n\n{GROUNDING_SYSTEM_SUFFIX}".strip()},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.3,
        "response_format": {"type": "json_object"},
    }
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        f"{config.base_url}/chat/completions",
        data=data,
        headers={
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=config.timeout_seconds) as response:
            body = json.loads(response.read().decode("utf-8"))
    except (TimeoutError, socket.timeout) as exc:
        raise LLMResponseError(f"{config.provider} 接口请求超时：{config.timeout_seconds} 秒内未返回") from exc
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise LLMResponseError(f"{config.provider} 接口返回错误：{exc.code} {detail}") from exc
    except urllib.error.URLError as exc:
        raise LLMResponseError(f"无法连接 {config.provider} 接口：{exc.reason}") from exc

    try:
        content = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMResponseError(f"{config.provider} 接口响应缺少 choices[0].message.content") from exc

    raw_json = _extract_json_object(content)
    try:
        return schema_model.model_validate(raw_json)
    except ValidationError as exc:
        raise LLMResponseError(f"模型 JSON 未通过结构校验：{exc}") from exc


def qwen_chat_stream_text(system_prompt: str, user_prompt: str, user: Optional[User] = None) -> Iterator[str]:
    config = resolve_chat_config(user)
    validate_qwen_config(user)

    payload = {
        "model": config.model,
        "messages": [
            {"role": "system", "content": f"{system_prompt}\n\n{GROUNDING_SYSTEM_SUFFIX}".strip()},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.3,
        "stream": True,
    }
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        f"{config.base_url}/chat/completions",
        data=data,
        headers={
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=config.timeout_seconds) as response:
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
        raise LLMResponseError(f"{config.provider} 流式接口请求超时：{config.timeout_seconds} 秒内未返回") from exc
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise LLMResponseError(f"{config.provider} 流式接口返回错误：{exc.code} {detail}") from exc
    except urllib.error.URLError as exc:
        raise LLMResponseError(f"无法连接 {config.provider} 流式接口：{exc.reason}") from exc
