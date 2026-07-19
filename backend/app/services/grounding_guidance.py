from __future__ import annotations

from math import isfinite


GROUNDING_SYSTEM_SUFFIX = """
防幻觉规则：
1. 只能依据已给知识库、上传资料、检索结果、明确上下文和可验证来源生成。
2. 资料不足时必须明确写出缺口或降级方案，不得编造 URL、论文、页码、结论、数据或课程内容。
3. 若输出涉及引用、阅读资源、来源或事实性细节，优先使用可追溯来源；不确定就留空或标注不可确认。
4. 尽量复用已有知识点、课程内容和学习路径，不要为了补足结构而硬凑新的知识点。
""".strip()


def hybrid_grounding_score(
    sim_vector: float,
    sim_keyword: float,
    source_weight: float,
    *,
    lambda_weight: float = 0.68,
    gamma_weight: float = 0.16,
) -> float:
    vector = _clamp(sim_vector)
    keyword = _clamp(sim_keyword)
    source = max(0.0, float(source_weight))
    return lambda_weight * vector + (1.0 - lambda_weight) * keyword + gamma_weight * source


def default_source_weight(
    *,
    doc_type: str = "",
    source_uri: str = "",
    parse_status: str = "",
    retrieval_weight: float = 1.0,
) -> float:
    weight = 1.0
    normalized_type = (doc_type or "").lower()
    if normalized_type in {"ppt", "pptx"}:
        weight += 0.18
    elif normalized_type in {"pdf", "doc", "docx"}:
        weight += 0.12
    elif normalized_type in {"md", "txt"}:
        weight += 0.05
    if (source_uri or "").startswith("http"):
        weight += 0.08
    if (parse_status or "").lower() == "ready":
        weight += 0.08
    weight += min(max(float(retrieval_weight), 0.0), 2.0) * 0.05
    return weight


def _clamp(value: float) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return 0.0
    if not isfinite(numeric):
        return 0.0
    return max(0.0, min(1.0, numeric))
