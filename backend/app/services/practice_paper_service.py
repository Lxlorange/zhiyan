from __future__ import annotations

import re
import time
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.orm import Session, selectinload

from app.models.learning import (
    AgentTaskRecord,
    PracticePaper,
    PracticePaperAttempt,
    PracticePaperQuestion,
)
from app.models.user import User
from app.schemas import (
    PracticeKnowledgeNodeRead,
    PracticePaperAttemptRead,
    PracticePaperAttemptResult,
    PracticePaperCreateRequest,
    PracticePaperQuestionRead,
    PracticePaperRead,
    PracticePaperSubmitRequest,
    PracticePaperSubmitResponse,
)
from app.services.knowledge_service import search_knowledge
from app.services.llm_client import qwen_chat_json
from app.services.taxonomy_service import build_knowledge_link_graph


class _GeneratedPaperQuestion(BaseModel):
    id: str
    type: str = Field(..., pattern="^(choice|multiple|judgement|short)$")
    point: str
    prompt: str
    options: list[str] = Field(default_factory=list)
    answer: str
    explanation: str
    source_title: str = ""
    source_excerpt: str = ""
    difficulty: str = "medium"


class _GeneratedPaper(BaseModel):
    title: str
    description: str = ""
    questions: list[_GeneratedPaperQuestion] = Field(default_factory=list)
    source_summary: str = ""


def list_practice_papers(db: Session, user: User) -> list[PracticePaperRead]:
    papers = list(
        db.scalars(
            select(PracticePaper)
            .options(selectinload(PracticePaper.questions), selectinload(PracticePaper.attempts))
            .where(PracticePaper.user_id == user.id, PracticePaper.status != "deleted")
            .order_by(desc(PracticePaper.updated_at))
        )
    )
    return [_paper_read(paper, include_questions=False) for paper in papers]


def get_practice_paper(db: Session, user: User, paper_id: int) -> PracticePaperRead:
    paper = _get_paper_or_404(db, user, paper_id)
    return _paper_read(paper, include_questions=True)


def list_practice_knowledge_nodes(
    db: Session,
    user: User,
    project_id: Optional[int],
    query: str = "",
    limit: int = 120,
) -> list[PracticeKnowledgeNodeRead]:
    graph = build_knowledge_link_graph(db, user, project_id=project_id, query=query, limit=limit)
    nodes: list[PracticeKnowledgeNodeRead] = []
    seen: set[str] = set()
    for node in graph.nodes:
        label = str(node.label or "").strip()
        if not label or label in seen:
            continue
        seen.add(label)
        nodes.append(
            PracticeKnowledgeNodeRead(
                id=node.id,
                label=label,
                layer=node.layer,
                category=node.category,
                description=node.description,
                knowledge_point=label,
                source_title=str(node.meta.get("source_title") or node.meta.get("project_title") or ""),
            )
        )
    return nodes


def create_practice_paper(
    db: Session,
    user: User,
    request: PracticePaperCreateRequest,
) -> PracticePaperRead:
    selected_points = _selected_points(request.selected_nodes)
    if not selected_points:
        raise ValueError("至少选择一个知识节点")

    source_context = _source_context(db, selected_points, request.project_id)
    started = time.perf_counter()
    generated = _generate_paper_with_llm(request, selected_points, source_context)
    if not generated.questions:
        raise ValueError("模型没有返回题目")

    expected_count = min(request.question_count, 30)
    questions = generated.questions[:expected_count]
    paper = PracticePaper(
        user_id=user.id,
        project_id=request.project_id,
        title=generated.title or request.title,
        description=generated.description or request.description,
        source="knowledge_graph",
        difficulty=request.difficulty,
        question_types=request.question_types,
        selected_nodes=request.selected_nodes,
        knowledge_points=selected_points,
        status="ready",
        total_questions=len(questions),
        generation_trace=[
            {
                "agent": "QuestionPlannerAgent",
                "status": "completed",
                "summary": f"围绕 {len(selected_points)} 个知识节点规划试卷",
            },
            {
                "agent": "QuestionGenerationAgent",
                "status": "completed",
                "summary": generated.source_summary,
            },
        ],
    )
    db.add(paper)
    db.flush()
    for index, question in enumerate(questions, start=1):
        db.add(
            PracticePaperQuestion(
                paper_id=paper.id,
                user_id=user.id,
                question_id=question.id or f"q{index}",
                question_type=question.type,
                point=question.point,
                prompt=question.prompt,
                options=question.options,
                answer=question.answer,
                explanation=question.explanation,
                source_title=question.source_title,
                source_excerpt=question.source_excerpt[:800],
                difficulty=question.difficulty or request.difficulty,
                order_index=index,
            )
        )
    db.add(
        AgentTaskRecord(
            session_id=f"practice-paper:{paper.id}",
            user_id=user.id,
            agent="QuestionGenerationAgent",
            status="completed",
            input_summary=", ".join(selected_points)[:500],
            output_summary=f"生成试卷：{paper.title}，共 {len(questions)} 题",
            latency_ms=int((time.perf_counter() - started) * 1000),
        )
    )
    db.commit()
    db.refresh(paper)
    return get_practice_paper(db, user, paper.id)


def submit_practice_paper(
    db: Session,
    user: User,
    paper_id: int,
    request: PracticePaperSubmitRequest,
) -> PracticePaperSubmitResponse:
    paper = _get_paper_or_404(db, user, paper_id)
    questions = sorted(paper.questions, key=lambda item: item.order_index)
    if not questions:
        raise ValueError("试卷没有题目")

    results: list[PracticePaperAttemptResult] = []
    correct_count = 0
    wrong_points: list[str] = []
    for question in questions:
        answer_key = question.question_id
        user_answer = request.answers.get(answer_key)
        is_correct = _judge_answer(question, user_answer)
        if is_correct:
            correct_count += 1
        else:
            wrong_points.append(question.point)
        results.append(
            PracticePaperAttemptResult(
                question_id=question.question_id,
                question_db_id=question.id,
                point=question.point,
                user_answer=user_answer,
                correct_answer=question.answer,
                is_correct=is_correct,
                explanation=question.explanation,
                remediation=_remediation(question, is_correct),
            )
        )

    total_count = len(questions)
    score = round(correct_count / total_count * 100) if total_count else 0
    attempt = PracticePaperAttempt(
        paper_id=paper.id,
        user_id=user.id,
        answers=request.answers,
        results=[result.model_dump(mode="json") for result in results],
        score=score,
        correct_count=correct_count,
        total_count=total_count,
        wrong_points=sorted(set(wrong_points)),
        summary=_attempt_summary(score, correct_count, total_count, wrong_points),
    )
    paper.attempt_count += 1
    paper.last_score = score
    paper.best_score = max(paper.best_score, score)
    paper.status = "completed" if score >= 80 else "reviewing"
    paper.updated_at = datetime.utcnow()
    db.add(attempt)
    db.add(
        AgentTaskRecord(
            session_id=f"practice-paper:{paper.id}",
            user_id=user.id,
            agent="EvaluationAgent",
            status="completed",
            input_summary=f"提交试卷 {paper.title}",
            output_summary=attempt.summary,
            latency_ms=0,
        )
    )
    db.commit()
    db.refresh(attempt)
    db.refresh(paper)
    return PracticePaperSubmitResponse(
        paper=get_practice_paper(db, user, paper.id),
        attempt=_attempt_read(attempt),
    )


def delete_practice_paper(db: Session, user: User, paper_id: int) -> None:
    paper = _get_paper_or_404(db, user, paper_id)
    paper.status = "deleted"
    paper.updated_at = datetime.utcnow()
    db.commit()


def _get_paper_or_404(db: Session, user: User, paper_id: int) -> PracticePaper:
    paper = db.scalar(
        select(PracticePaper)
        .options(selectinload(PracticePaper.questions), selectinload(PracticePaper.attempts))
        .where(PracticePaper.id == paper_id, PracticePaper.user_id == user.id, PracticePaper.status != "deleted")
    )
    if paper is None:
        raise KeyError("practice paper not found")
    return paper


def _paper_read(paper: PracticePaper, include_questions: bool) -> PracticePaperRead:
    return PracticePaperRead(
        id=paper.id,
        project_id=paper.project_id,
        title=paper.title,
        description=paper.description,
        source=paper.source,
        difficulty=paper.difficulty,
        question_types=paper.question_types or [],
        selected_nodes=paper.selected_nodes or [],
        knowledge_points=paper.knowledge_points or [],
        status=paper.status,
        total_questions=paper.total_questions,
        last_score=paper.last_score,
        best_score=paper.best_score,
        attempt_count=paper.attempt_count,
        generation_trace=paper.generation_trace or [],
        created_at=paper.created_at,
        updated_at=paper.updated_at,
        questions=[_question_read(question) for question in sorted(paper.questions, key=lambda item: item.order_index)] if include_questions else [],
        attempts=[_attempt_read(attempt) for attempt in sorted(paper.attempts, key=lambda item: item.created_at, reverse=True)],
    )


def _question_read(question: PracticePaperQuestion) -> PracticePaperQuestionRead:
    return PracticePaperQuestionRead(
        id=question.id,
        question_id=question.question_id,
        type=question.question_type,
        point=question.point,
        prompt=question.prompt,
        options=question.options or [],
        answer=question.answer,
        explanation=question.explanation,
        source_title=question.source_title,
        source_excerpt=question.source_excerpt,
        difficulty=question.difficulty,
        order_index=question.order_index,
    )


def _attempt_read(attempt: PracticePaperAttempt) -> PracticePaperAttemptRead:
    return PracticePaperAttemptRead(
        id=attempt.id,
        paper_id=attempt.paper_id,
        answers=attempt.answers or {},
        results=[PracticePaperAttemptResult.model_validate(item) for item in (attempt.results or [])],
        score=attempt.score,
        correct_count=attempt.correct_count,
        total_count=attempt.total_count,
        wrong_points=attempt.wrong_points or [],
        summary=attempt.summary,
        created_at=attempt.created_at,
    )


def _selected_points(nodes: list[dict[str, Any]]) -> list[str]:
    points: list[str] = []
    for node in nodes:
        value = str(node.get("knowledge_point") or node.get("label") or node.get("name") or "").strip()
        if value:
            points.append(value)
    return list(dict.fromkeys(points))[:20]


def _source_context(db: Session, points: list[str], project_id: Optional[int]) -> list[dict[str, Any]]:
    query = " ".join(points)
    hits = [hit.model_dump(mode="json") for hit in search_knowledge(db, query, limit=14)]
    if project_id:
        hits.insert(
            0,
            {
                "document_title": f"学习项目 {project_id}",
                "document_type": "learning_project",
                "knowledge_point": "项目范围",
                "content": query,
                "source_uri": f"project:{project_id}",
            },
        )
    return hits[:14]


def _generate_paper_with_llm(
    request: PracticePaperCreateRequest,
    points: list[str],
    source_context: list[dict[str, Any]],
) -> _GeneratedPaper:
    context = "\n\n".join(
        f"[{index}] {item.get('document_title', '')} / {item.get('knowledge_point', '')}\n{item.get('content', '')}"
        for index, item in enumerate(source_context, start=1)
    )
    prompt = f"""
你是 DeepTutor 风格的 QuestionGenerationAgent，要根据知识图谱中选中的节点生成一份可保存、可作答、可解析的练习试卷。
只能返回合法 JSON，必须严格匹配 schema。

试卷标题：{request.title}
试卷说明：{request.description}
选中知识节点：{points}
题型范围：{request.question_types}
难度：{request.difficulty}
题目数量：{request.question_count}

资料库片段：
{context}

生成要求：
1. questions 数量必须接近题目数量，最少 1 题。
2. 每道题必须绑定 point，point 必须来自选中知识节点或其直接相关表达。
3. 题型只能使用 choice、multiple、judgement、short。
4. choice 必须有 4 个选项，answer 必须等于某个选项文本或选项字母；multiple 至少 4 个选项，answer 用逗号分隔正确选项。
5. judgement 的 answer 只能是 正确 或 错误。
6. short 必须给出可判分的参考答案和具体解析。
7. explanation 要说明为什么正确、常见错误是什么、如何补救。
8. source_title/source_excerpt 必须尽量来自资料库片段；资料不足时在 explanation 里说明还需要补充材料，不得编造来源。
9. 不要输出 markdown，不要输出代码块。

schema:
{_GeneratedPaper.model_json_schema(mode="validation")}
"""
    return qwen_chat_json(
        "你是高校个性化学习平台的试卷生成智能体。你会先覆盖知识点，再生成题目、答案、解析和补救提示。",
        prompt,
        _GeneratedPaper,
        user=user,
    )


def _judge_answer(question: PracticePaperQuestion, user_answer: Any) -> bool:
    if user_answer is None or user_answer == "":
        return False
    expected = _normalize_answer(question.answer)
    actual = _normalize_answer(user_answer)
    if question.question_type in {"choice", "judgement"}:
        return actual == expected or actual in _choice_aliases(question, expected)
    if question.question_type == "multiple":
        return set(_split_multi(actual)) == set(_split_multi(expected))
    expected_tokens = [token for token in re.split(r"[\s,，。；;、/]+", expected) if len(token) >= 2]
    if not expected_tokens:
        return actual == expected
    hits = sum(1 for token in expected_tokens if token in actual)
    return hits >= max(1, min(3, len(expected_tokens) // 2))


def _normalize_answer(value: Any) -> str:
    if isinstance(value, list):
        return ",".join(str(item).strip() for item in value)
    return str(value or "").strip().lower()


def _split_multi(value: str) -> list[str]:
    return [item.strip() for item in re.split(r"[,，、/;；]+", value) if item.strip()]


def _choice_aliases(question: PracticePaperQuestion, expected: str) -> set[str]:
    aliases: set[str] = set()
    options = question.options or []
    for index, option in enumerate(options):
        letter = chr(ord("a") + index)
        if _normalize_answer(option) == expected or expected == letter:
            aliases.add(letter)
            aliases.add(chr(ord("A") + index).lower())
            aliases.add(_normalize_answer(option))
    return aliases


def _remediation(question: PracticePaperQuestion, is_correct: bool) -> str:
    if is_correct:
        return "本题已掌握，可以继续完成同类变式或进入下一知识节点。"
    return f"建议回看「{question.point}」相关资料，重点复盘：{question.explanation or question.answer}"


def _attempt_summary(score: int, correct_count: int, total_count: int, wrong_points: list[str]) -> str:
    if score >= 80:
        return f"本次得分 {score}，答对 {correct_count}/{total_count}。整体掌握较好。"
    if wrong_points:
        return f"本次得分 {score}，答对 {correct_count}/{total_count}。建议优先复习：{'、'.join(sorted(set(wrong_points))[:5])}。"
    return f"本次得分 {score}，答对 {correct_count}/{total_count}。"
