from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.user import User
from app.schemas import ModelProviderOption, UserModelSettingsRead, UserModelSettingsUpdate
from app.services.llm_client import LLMConfigurationError, LLMResponseError, resolve_chat_config


@dataclass(frozen=True)
class ModelProvider:
    id: str
    name: str
    base_url: str
    models: tuple[str, ...]
    description: str


MODEL_PROVIDERS: tuple[ModelProvider, ...] = (
    ModelProvider(
        id="qwen",
        name="通义千问",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        models=("qwen-plus", "qwen-max"),
        description="适合中文学习规划、知识库问答和结构化 JSON 输出。",
    ),
    ModelProvider(
        id="deepseek",
        name="DeepSeek",
        base_url="https://api.deepseek.com/v1",
        models=("deepseek-chat",),
        description="同样使用 OpenAI-compatible chat completions 协议，适合成本敏感场景。",
    ),
    ModelProvider(
        id="openai-compatible",
        name="OpenAI-compatible",
        base_url="https://api.openai.com/v1",
        models=("gpt-4o-mini",),
        description="保留一个通用兼容入口，可连接实现 chat/completions 的服务。",
    ),
)


def provider_options() -> list[ModelProviderOption]:
    return [
        ModelProviderOption(
            id=item.id,
            name=item.name,
            base_url=item.base_url,
            models=list(item.models),
            description=item.description,
        )
        for item in MODEL_PROVIDERS
    ]


def _provider_or_error(provider_id: str) -> ModelProvider:
    for provider in MODEL_PROVIDERS:
        if provider.id == provider_id:
            return provider
    raise ValueError("unsupported model provider")


def _normalize_base_url(value: str) -> str:
    cleaned = value.strip().rstrip("/")
    if not cleaned.startswith(("http://", "https://")):
        raise ValueError("base_url must start with http:// or https://")
    return cleaned


def get_user_model_settings(user: User) -> UserModelSettingsRead:
    config = resolve_chat_config(user)
    return UserModelSettingsRead(
        provider=config.provider,
        model=config.model,
        base_url=config.base_url,
        api_key_configured=bool(config.api_key),
        api_key_tail=config.api_key[-4:] if config.api_key else "",
        provider_options=provider_options(),
    )


def update_user_model_settings(db: Session, user: User, request: UserModelSettingsUpdate) -> UserModelSettingsRead:
    provider = _provider_or_error(request.provider)
    if request.model not in provider.models:
        raise ValueError("selected model is not available for this provider")

    user.llm_provider = provider.id
    user.llm_model = request.model
    user.llm_base_url = _normalize_base_url(request.base_url or provider.base_url)
    if request.api_key is not None:
        user.llm_api_key = request.api_key.strip()
    db.add(user)
    db.commit()
    db.refresh(user)
    return get_user_model_settings(user)


def verify_user_model_settings(user: User) -> dict[str, str | bool]:
    config = resolve_chat_config(user)
    if not config.api_key:
        raise LLMConfigurationError("当前模型缺少 API Key，请先在系统设置中保存自己的 API Key。")

    payload = {
        "model": config.model,
        "messages": [
            {"role": "system", "content": "你是连接测试助手。"},
            {"role": "user", "content": "请只返回 JSON：{\"ok\": true}"},
        ],
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }
    request = urllib.request.Request(
        f"{config.base_url.rstrip('/')}/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = json.loads(response.read().decode("utf-8"))
    except (TimeoutError, socket.timeout) as exc:
        raise LLMResponseError("模型连接测试超时") from exc
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise LLMResponseError(f"模型连接测试失败：{exc.code} {detail}") from exc
    except urllib.error.URLError as exc:
        raise LLMResponseError(f"无法连接模型服务：{exc.reason}") from exc

    if not body.get("choices"):
        raise LLMResponseError("模型连接成功但响应缺少 choices")
    return {
        "ok": True,
        "provider": config.provider,
        "model": config.model,
        "message": "模型连接测试通过",
    }
