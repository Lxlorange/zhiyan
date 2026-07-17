from __future__ import annotations

import json
import re
from typing import Any

from json_repair import repair_json


class LLMJsonParseError(RuntimeError):
    pass


def parse_llm_json(text: str) -> Any:
    candidates = _json_candidates(text)
    last_error: Exception | None = None
    for candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError as exc:
            last_error = exc
        try:
            return json.loads(_repair_common_json_issues(candidate))
        except json.JSONDecodeError as exc:
            last_error = exc
        try:
            repaired = repair_json(candidate, return_objects=False)
            return json.loads(repaired)
        except Exception as exc:
            last_error = exc
    if last_error is None:
        raise LLMJsonParseError("模型未返回 JSON 内容")
    raise LLMJsonParseError(_json_error_message(candidates[-1] if candidates else text, last_error)) from last_error


def _json_candidates(text: str) -> list[str]:
    cleaned = _strip_reasoning_prefix(text.strip())
    candidates: list[str] = []

    for match in re.finditer(r"```(?:json)?\s*([\s\S]*?)```", cleaned, flags=re.IGNORECASE):
        block = match.group(1).strip()
        if block.startswith(("{", "[")):
            candidates.append(block)

    candidates.append(cleaned)
    balanced = _extract_balanced_json(cleaned)
    if balanced and balanced not in candidates:
        candidates.append(balanced)

    result: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        value = candidate.strip()
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _strip_reasoning_prefix(text: str) -> str:
    matches = list(re.finditer(r"</(?:think|thinking|reasoning)>\s*", text, flags=re.IGNORECASE))
    if not matches:
        return text
    return text[matches[-1].end() :].strip()


def _extract_balanced_json(text: str) -> str:
    starts = [index for index in [text.find("{"), text.find("[")] if index >= 0]
    if not starts:
        return ""
    start = min(starts)
    depth = 0
    in_string = False
    escape_next = False
    for index in range(start, len(text)):
        char = text[index]
        if escape_next:
            escape_next = False
            continue
        if char == "\\" and in_string:
            escape_next = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if char in "{[":
            depth += 1
        elif char in "}]":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return text[start:]


def _repair_common_json_issues(value: str) -> str:
    fixed = value
    fixed = re.sub(
        r'([,{]\s*)"([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(true|false|null|[+-]?\d+(?:\.\d+)?)"(?=\s*[,}])',
        lambda match: f'{match.group(1)}"{match.group(2)}": {match.group(3)}',
        fixed,
    )
    fixed = re.sub(
        r'"([^"\\]*(?:\\.[^"\\]*)*)"',
        lambda match: '"' + re.sub(r"\\([a-zA-Z])", lambda slash: f"\\{slash.group(1)}" if slash.group(1) in "bfnrtu" else f"\\\\{slash.group(1)}", match.group(1)) + '"',
        fixed,
    )
    fixed = re.sub(r'\\([^"\\/bfnrtu\n\r])', lambda match: "\\\\" + match.group(1) if re.match(r"[A-Za-z]", match.group(1)) else match.group(0), fixed)
    stripped = fixed.strip()
    if stripped.startswith("[") and not stripped.endswith("]"):
        last_object = fixed.rfind("}")
        if last_object > 0:
            fixed = fixed[: last_object + 1] + "]"
    elif stripped.startswith("{") and not stripped.endswith("}"):
        open_count = fixed.count("{")
        close_count = fixed.count("}")
        if open_count > close_count:
            fixed += "}" * (open_count - close_count)
    return fixed


def _json_error_message(candidate: str, error: Exception) -> str:
    message = str(error)
    position = getattr(error, "pos", None)
    if isinstance(position, int):
        start = max(0, position - 160)
        end = min(len(candidate), position + 160)
        context = candidate[start:end].replace("\n", "\\n")
        return f"模型返回 JSON 无法解析：{message}。错误附近内容：{context}"
    return f"模型返回 JSON 无法解析：{message}"
