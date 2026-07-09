from __future__ import annotations

from datetime import datetime
from pathlib import Path
import json
import re
import socket
import urllib.error
import urllib.request
from typing import Any, Optional

from pydantic import BaseModel, Field
from pptx import Presentation
from pptx.util import Inches, Pt
from sqlalchemy import Select, select
from sqlalchemy.orm import Session, selectinload

from app.models.learning import (
    AgentTaskRecord,
    ClassroomResource,
    ClassroomSession,
    ClassroomSubmission,
    LearningProject,
    LearningProjectEvent,
    LearningSyllabusItem,
)
from app.models.user import User
from app.schemas import (
    ClassroomPracticeSubmitRequest,
    ClassroomQuizSubmitRequest,
    ClassroomReflectionSubmitRequest,
    ClassroomSlidesCompleteRequest,
    SyllabusItemStatusRequest,
)
from app.core.config import get_settings
from app.services.llm_client import LLMResponseError, qwen_chat_json, validate_qwen_config
from app.services.syllabus_service import update_syllabus_item_status


class _SlideSpec(BaseModel):
    title: str
    bullets: list[str] = Field(min_length=2, max_length=6)
    speaker_notes: str


class _QuizSpec(BaseModel):
    id: str
    prompt: str
    answer: str
    explanation: str


class _PracticeSpec(BaseModel):
    title: str
    steps: list[str] = Field(min_length=3, max_length=8)
    expected_artifact: str
    acceptance_criteria: list[str] = Field(min_length=2, max_length=6)


class _ClassroomPackage(BaseModel):
    title: str
    learning_summary: str
    slides: list[_SlideSpec] = Field(min_length=5, max_length=9)
    quiz: list[_QuizSpec] = Field(min_length=2, max_length=5)
    practice: _PracticeSpec
    reflection_prompts: list[str] = Field(min_length=3, max_length=6)
    safety_notes: list[str] = Field(default_factory=list)


class _QuizEvaluation(BaseModel):
    score: int = Field(ge=0, le=100)
    passed: bool
    feedback: str


class _PracticeEvaluation(BaseModel):
    score: int = Field(ge=0, le=100)
    passed: bool
    feedback: str


class _ReflectionEvaluation(BaseModel):
    score: int = Field(ge=0, le=100)
    passed: bool
    feedback: str


def _item_or_404(db: Session, user: User, item_id: int) -> LearningSyllabusItem:
    item = db.scalar(
        select(LearningSyllabusItem).where(LearningSyllabusItem.id == item_id, LearningSyllabusItem.user_id == user.id)
    )
    if item is None:
        raise KeyError("syllabus item not found")
    return item


def _project_or_404(db: Session, user: User, project_id: int) -> LearningProject:
    project = db.scalar(
        select(LearningProject).where(LearningProject.id == project_id, LearningProject.user_id == user.id)
    )
    if project is None:
        raise KeyError("project not found")
    return project


def _session_query() -> Select[tuple[ClassroomSession]]:
    return select(ClassroomSession).options(
        selectinload(ClassroomSession.resources),
        selectinload(ClassroomSession.submissions),
    )


def _get_session(db: Session, user: User, session_id: int) -> ClassroomSession:
    session = db.scalar(_session_query().where(ClassroomSession.id == session_id, ClassroomSession.user_id == user.id))
    if session is None:
        raise KeyError("classroom session not found")
    return session


def _latest_session(db: Session, user: User, item_id: int) -> Optional[ClassroomSession]:
    return db.scalar(
        _session_query()
        .where(ClassroomSession.syllabus_item_id == item_id, ClassroomSession.user_id == user.id)
        .order_by(ClassroomSession.created_at.desc())
    )


def get_or_create_classroom_session(db: Session, user: User, item_id: int) -> ClassroomSession:
    item = _item_or_404(db, user, item_id)
    project = _project_or_404(db, user, item.project_id)
    session = _latest_session(db, user, item.id)
    if session is None:
        session = ClassroomSession(
            syllabus_item_id=item.id,
            project_id=project.id,
            user_id=user.id,
            title=item.title,
            progress_state=_build_progress_state(False, False, False, False, False),
        )
        db.add(session)
        db.add(
            LearningProjectEvent(
                project_id=project.id,
                user_id=user.id,
                event_type="classroom_started",
                summary=f"进入课堂：{item.title}",
                payload={"item_id": item.id},
            )
        )
        db.flush()
    if item.status == "pending":
        update_syllabus_item_status(
            db,
            user,
            item.id,
            SyllabusItemStatusRequest(status="in_progress", reason="进入课堂自动开始学习"),
        )
    db.commit()
    return _get_session(db, user, session.id)


def generate_classroom_ppt(
    db: Session,
    user: User,
    session_id: int,
    instruction: str = "",
) -> ClassroomSession:
    session = _get_session(db, user, session_id)
    item = _item_or_404(db, user, session.syllabus_item_id)
    project = _project_or_404(db, user, session.project_id)
    package = _generate_classroom_package(project, item, instruction)
    ppt_path = _write_pptx_file(session.id, item, package)

    resource = ClassroomResource(
        session_id=session.id,
        syllabus_item_id=item.id,
        project_id=project.id,
        user_id=user.id,
        resource_type="pptx",
        title=f"{item.title} 课堂课件",
        content_data=package.model_dump(),
        file_path=str(ppt_path),
        source="THU-MAIC/OpenMAIC-inspired MIT",
        status="ready",
    )
    db.add(resource)
    db.flush()
    session.ppt_resource_id = resource.id
    session.slides_completed = False
    session.slide_progress = {"current_index": 0, "total_slides": len(package.slides), "visited_indices": [0]}
    session.progress_state = _build_progress_state(True, False, session.quiz_passed, session.practice_passed, session.reflection_passed)
    db.add(
        AgentTaskRecord(
            session_id=f"classroom-{session.id}",
            user_id=user.id,
            agent="OpenMAICStyleLessonAgent+PPTAgent",
            status="completed",
            input_summary=f"{project.title} / {item.title}",
            output_summary=f"生成 {len(package.slides)} 页课堂 PPT，并生成例题、实操和复盘要求",
            latency_ms=0,
        )
    )
    _write_event(db, project, user, "classroom_ppt_generated", f"生成课堂 PPT：{item.title}", {"resource_id": resource.id})
    _maybe_complete_session(db, user, session)
    db.commit()
    return _get_session(db, user, session.id)


def submit_quiz(
    db: Session,
    user: User,
    session_id: int,
    request: ClassroomQuizSubmitRequest,
) -> ClassroomSession:
    session = _get_session(db, user, session_id)
    if not session.slides_completed:
        raise ValueError("请先在页面中翻完课件并完成课件学习")
    item = _item_or_404(db, user, session.syllabus_item_id)
    package = _classroom_package_or_error(session)
    expected = {question.id: question.answer for question in package.quiz}
    correct_count = sum(1 for question_id, answer in request.answers.items() if expected.get(question_id, "").strip() == answer.strip())
    score = round((correct_count / max(len(package.quiz), 1)) * 100)
    passed = score >= 70
    feedback = f"答对 {correct_count}/{len(package.quiz)} 题，{'已达到通过标准' if passed else '请重新回看课件后再作答'}。"
    _add_submission(
        db,
        session=session,
        user=user,
        item=item,
        submission_type="quiz",
        content={"answers": request.answers, "expected": expected},
        score=score,
        passed=passed,
        feedback=feedback,
    )
    session.quiz_passed = passed
    session.progress_state = _build_progress_state(bool(session.ppt_resource_id), session.slides_completed, passed, session.practice_passed, session.reflection_passed)
    _maybe_complete_session(db, user, session)
    db.commit()
    return _get_session(db, user, session.id)


def complete_slides(
    db: Session,
    user: User,
    session_id: int,
    request: ClassroomSlidesCompleteRequest,
) -> ClassroomSession:
    session = _get_session(db, user, session_id)
    _classroom_package_or_error(session)
    visited = sorted({index for index in request.visited_indices if 0 <= index < request.total_slides})
    if len(visited) < request.total_slides:
        raise ValueError("课件页尚未全部浏览，不能进入例题环节")
    session.slides_completed = True
    session.slide_progress = {
        "current_index": request.current_index,
        "total_slides": request.total_slides,
        "visited_indices": visited,
        "completed_at": datetime.utcnow().isoformat(),
    }
    session.progress_state = _build_progress_state(True, True, session.quiz_passed, session.practice_passed, session.reflection_passed)
    item = _item_or_404(db, user, session.syllabus_item_id)
    _write_event(
        db,
        _project_or_404(db, user, session.project_id),
        user,
        "classroom_slides_completed",
        f"完成动态课件学习：{item.title}",
        {"session_id": session.id, "total_slides": request.total_slides},
    )
    db.commit()
    return _get_session(db, user, session.id)


def submit_practice(
    db: Session,
    user: User,
    session_id: int,
    request: ClassroomPracticeSubmitRequest,
) -> ClassroomSession:
    session = _get_session(db, user, session_id)
    item = _item_or_404(db, user, session.syllabus_item_id)
    package = _classroom_package_or_error(session)
    evaluation = qwen_chat_json(
        "你是高校 AI 课程实操助教。请只输出 JSON，判断学生实操是否达到验收标准。",
        (
            f"学习项：{item.title}\n"
            f"实操任务：{package.practice.model_dump()}\n"
            f"学生报告：{request.report}\n"
            f"产物链接：{request.artifact_url}\n"
            f"关键结果：{request.key_result}\n"
            '输出格式：{"score":0-100,"passed":true/false,"feedback":"..."}'
        ),
        _PracticeEvaluation,
    )
    _add_submission(
        db,
        session=session,
        user=user,
        item=item,
        submission_type="practice",
        content=request.model_dump(),
        score=evaluation.score,
        passed=evaluation.passed,
        feedback=evaluation.feedback,
    )
    session.practice_passed = evaluation.passed
    session.progress_state = _build_progress_state(bool(session.ppt_resource_id), session.slides_completed, session.quiz_passed, evaluation.passed, session.reflection_passed)
    _maybe_complete_session(db, user, session)
    db.commit()
    return _get_session(db, user, session.id)


def submit_reflection(
    db: Session,
    user: User,
    session_id: int,
    request: ClassroomReflectionSubmitRequest,
) -> ClassroomSession:
    session = _get_session(db, user, session_id)
    item = _item_or_404(db, user, session.syllabus_item_id)
    evaluation = qwen_chat_json(
        "你是高校课程复盘评估助教。请只输出 JSON，判断复盘是否具体、真实、能支持后续路径调整。",
        (
            f"学习项：{item.title}\n"
            f"完成标准：{item.completion_criteria}\n"
            f"复盘内容：{request.reflection}\n"
            f"未解决问题：{request.unresolved_questions}\n"
            f"下一步行动：{request.next_action}\n"
            '输出格式：{"score":0-100,"passed":true/false,"feedback":"..."}'
        ),
        _ReflectionEvaluation,
    )
    _add_submission(
        db,
        session=session,
        user=user,
        item=item,
        submission_type="reflection",
        content=request.model_dump(),
        score=evaluation.score,
        passed=evaluation.passed,
        feedback=evaluation.feedback,
    )
    session.reflection_passed = evaluation.passed
    session.progress_state = _build_progress_state(bool(session.ppt_resource_id), session.slides_completed, session.quiz_passed, session.practice_passed, evaluation.passed)
    _maybe_complete_session(db, user, session)
    db.commit()
    return _get_session(db, user, session.id)


def _generate_classroom_package_strict_unused(project: LearningProject, item: LearningSyllabusItem, instruction: str) -> _ClassroomPackage:
    return qwen_chat_json(
        "你是 OpenMAIC 风格的多智能体课程生成系统，负责生成可导出 PPT 的课堂资源、例题、实操任务和复盘问题。只输出 JSON。",
        (
            "参考 THU-MAIC/OpenMAIC 的课堂产物组织方式：slides、quizzes、interactive/practice、PBL/reflection。\n"
            f"项目：{project.title}\n"
            f"研究方向：{project.research_direction}\n"
            f"学习目标：{project.learning_goal}\n"
            f"学习项：{item.title}\n"
            f"学习项目标：{item.objective}\n"
            f"知识点：{item.knowledge_points}\n"
            f"完成标准：{item.completion_criteria}\n"
            f"评估方式：{item.assessment_method}\n"
            f"补充要求：{instruction}\n"
            "请生成 5-9 页 slides，每页含 title、bullets、speaker_notes；2-5 道 quiz，每题必须有 id、prompt、answer、explanation；"
            "practice 要包含 steps、expected_artifact、acceptance_criteria；reflection_prompts 至少 3 条。"
        ),
        _ClassroomPackage,
    )


def _write_pptx_file(session_id: int, item: LearningSyllabusItem, package: _ClassroomPackage) -> Path:
    output_dir = Path(__file__).resolve().parents[2] / "generated" / "pptx"
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"classroom-{session_id}-item-{item.id}.pptx"

    prs = Presentation()
    title_slide = prs.slides.add_slide(prs.slide_layouts[0])
    title_slide.shapes.title.text = package.title
    title_slide.placeholders[1].text = item.title

    for spec in package.slides:
        slide = prs.slides.add_slide(prs.slide_layouts[1])
        slide.shapes.title.text = spec.title
        text_frame = slide.placeholders[1].text_frame
        text_frame.clear()
        for index, bullet in enumerate(spec.bullets):
            paragraph = text_frame.paragraphs[0] if index == 0 else text_frame.add_paragraph()
            paragraph.text = bullet
            paragraph.font.size = Pt(22)
        notes = slide.notes_slide.notes_text_frame
        notes.text = spec.speaker_notes

    quiz_slide = prs.slides.add_slide(prs.slide_layouts[5])
    quiz_slide.shapes.title.text = "课堂例题"
    box = quiz_slide.shapes.add_textbox(Inches(0.8), Inches(1.5), Inches(8.5), Inches(4.5))
    frame = box.text_frame
    for question in package.quiz:
        paragraph = frame.add_paragraph()
        paragraph.text = f"{question.id}. {question.prompt}"
        paragraph.font.size = Pt(18)

    practice_slide = prs.slides.add_slide(prs.slide_layouts[5])
    practice_slide.shapes.title.text = package.practice.title
    box = practice_slide.shapes.add_textbox(Inches(0.8), Inches(1.5), Inches(8.5), Inches(4.5))
    frame = box.text_frame
    for step in package.practice.steps:
        paragraph = frame.add_paragraph()
        paragraph.text = step
        paragraph.font.size = Pt(18)

    prs.save(path)
    return path


def _classroom_package_or_error(session: ClassroomSession) -> _ClassroomPackage:
    ppt_resource = next((resource for resource in session.resources if resource.id == session.ppt_resource_id), None)
    if ppt_resource is None:
        raise ValueError("请先生成课堂 PPT")
    return _ClassroomPackage.model_validate(ppt_resource.content_data)


def _add_submission(
    db: Session,
    *,
    session: ClassroomSession,
    user: User,
    item: LearningSyllabusItem,
    submission_type: str,
    content: dict,
    score: int,
    passed: bool,
    feedback: str,
) -> None:
    db.add(
        ClassroomSubmission(
            session_id=session.id,
            syllabus_item_id=item.id,
            project_id=item.project_id,
            user_id=user.id,
            submission_type=submission_type,
            content=content,
            score=score,
            passed=passed,
            feedback=feedback,
        )
    )


def _build_progress_state(ppt_ready: bool, slides_completed: bool, quiz_passed: bool, practice_passed: bool, reflection_passed: bool) -> dict:
    return {
        "ppt_ready": ppt_ready,
        "slides_completed": slides_completed,
        "quiz_passed": quiz_passed,
        "practice_passed": practice_passed,
        "reflection_passed": reflection_passed,
        "can_complete": all([ppt_ready, slides_completed, quiz_passed, practice_passed, reflection_passed]),
    }


def _maybe_complete_session(db: Session, user: User, session: ClassroomSession) -> None:
    if not all([session.ppt_resource_id, session.slides_completed, session.quiz_passed, session.practice_passed, session.reflection_passed]):
        session.status = "learning"
        return
    if session.status == "completed":
        return
    session.status = "completed"
    session.completed_at = datetime.utcnow()
    session.progress_state = _build_progress_state(True, True, True, True, True)
    update_syllabus_item_status(
        db,
        user,
        session.syllabus_item_id,
        SyllabusItemStatusRequest(status="completed", reason="课堂 PPT、例题、实操与复盘均已通过"),
    )


def _write_event(db: Session, project: LearningProject, user: User, event_type: str, summary: str, payload: dict) -> None:
    db.add(
        LearningProjectEvent(
            project_id=project.id,
            user_id=user.id,
            event_type=event_type,
            summary=summary,
            payload=payload,
        )
    )


def _generate_classroom_package(project: LearningProject, item: LearningSyllabusItem, instruction: str) -> _ClassroomPackage:
    system_prompt = (
        "你是 OpenMAIC 风格的多智能体课程生成系统，负责生成可导出 PPT 的课堂资源、例题、实操任务和复盘问题。"
        "只输出 JSON，不要 Markdown。"
    )
    user_prompt = (
        "参考 THU-MAIC/OpenMAIC 的课堂产物组织方式：slides、quizzes、interactive/practice、PBL/reflection。\n"
        "必须输出这些顶层字段：title, learning_summary, slides, quiz, practice, reflection_prompts, safety_notes。\n"
        "slides 每项必须包含 title, bullets, speaker_notes。quiz 每项必须包含 id, prompt, answer, explanation。\n"
        "practice 必须包含 title, steps, expected_artifact, acceptance_criteria。\n"
        f"项目：{project.title}\n"
        f"研究方向：{project.research_direction}\n"
        f"学习目标：{project.learning_goal}\n"
        f"学习项：{item.title}\n"
        f"学习项目标：{item.objective}\n"
        f"知识点：{item.knowledge_points}\n"
        f"完成标准：{item.completion_criteria}\n"
        f"评估方式：{item.assessment_method}\n"
        f"补充要求：{instruction}\n"
        "请生成 5-9 页 slides、2-5 道 quiz、1 个 practice、至少 3 条 reflection_prompts。"
    )
    raw = _qwen_chat_raw_json(system_prompt, user_prompt)
    normalized = _normalize_classroom_package(raw, project, item)
    try:
        return _ClassroomPackage.model_validate(normalized)
    except Exception as exc:
        raise LLMResponseError(f"课堂包 JSON 归一化后仍未通过结构校验：{exc}") from exc


def _qwen_chat_raw_json(system_prompt: str, user_prompt: str) -> Any:
    settings = get_settings()
    validate_qwen_config()
    payload = {
        "model": settings.qwen_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
    }
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        f"{settings.qwen_base_url.rstrip('/')}/chat/completions",
        data=data,
        headers={"Authorization": f"Bearer {settings.qwen_api_key}", "Content-Type": "application/json"},
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
    return _extract_raw_json(content)


def _extract_raw_json(text: str) -> Any:
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


def _normalize_classroom_package(raw: Any, project: LearningProject, item: LearningSyllabusItem) -> dict:
    data = raw if isinstance(raw, dict) else {"slides": raw if isinstance(raw, list) else []}
    slides = [_normalize_slide(slide, index) for index, slide in enumerate(_as_list(data.get("slides") or data.get("ppt") or data.get("deck")), start=1)]
    if len(slides) < 5:
        slides.extend(_fallback_slides(project, item, start=len(slides) + 1))
    slides = slides[:9]

    quiz_raw = data.get("quiz") or data.get("quizzes") or data.get("questions") or data.get("exercises")
    quiz = [_normalize_quiz(question, index, item) for index, question in enumerate(_as_list(quiz_raw), start=1)]
    if len(quiz) < 2:
        quiz.extend(_fallback_quiz(item, start=len(quiz) + 1))
    quiz = quiz[:5]

    practice = _normalize_practice(data.get("practice") or data.get("interactive") or data.get("lab") or {}, item)
    reflection_prompts = _as_str_list(data.get("reflection_prompts") or data.get("reflection") or data.get("pbl"))
    if len(reflection_prompts) < 3:
        reflection_prompts.extend([
            f"解释本节 {item.title} 与项目目标的关系。",
            "列出一个已经掌握的证据和一个仍然不确定的问题。",
            "写出下一步要验证或复现的具体行动。",
        ])
    return {
        "title": _first_text(data.get("title"), f"{item.title} 课堂课件"),
        "learning_summary": _first_text(data.get("learning_summary") or data.get("summary"), item.objective),
        "slides": slides,
        "quiz": quiz,
        "practice": practice,
        "reflection_prompts": reflection_prompts[:6],
        "safety_notes": _as_str_list(data.get("safety_notes") or data.get("notes")),
    }


def _normalize_slide(raw: Any, index: int) -> dict:
    slide = raw if isinstance(raw, dict) else {"title": f"Slide {index}", "bullets": _as_str_list(raw)}
    bullets = _as_str_list(slide.get("bullets") or slide.get("points") or slide.get("content") or slide.get("items"))
    if len(bullets) < 2:
        bullets.extend(["核心概念与背景", "关键方法与应用场景"])
    return {
        "title": _first_text(slide.get("title"), f"课堂要点 {index}"),
        "bullets": bullets[:6],
        "speaker_notes": _first_text(slide.get("speaker_notes") or slide.get("notes"), "结合学生项目目标讲解本页内容。"),
    }


def _normalize_quiz(raw: Any, index: int, item: LearningSyllabusItem) -> dict:
    question = raw if isinstance(raw, dict) else {"prompt": str(raw)}
    return {
        "id": _first_text(question.get("id"), f"q{index}"),
        "prompt": _first_text(question.get("prompt") or question.get("question"), f"请解释 {item.title} 的核心思想。"),
        "answer": _first_text(question.get("answer") or question.get("expected_answer"), item.knowledge_points[0] if item.knowledge_points else item.title),
        "explanation": _first_text(question.get("explanation") or question.get("analysis"), "答案需要覆盖核心概念、适用场景和关键限制。"),
    }


def _normalize_practice(raw: Any, item: LearningSyllabusItem) -> dict:
    practice = raw if isinstance(raw, dict) else {"steps": _as_str_list(raw)}
    steps = _as_str_list(practice.get("steps") or practice.get("tasks") or practice.get("workflow"))
    if len(steps) < 3:
        steps.extend([
            f"搭建与 {item.title} 相关的最小实验环境。",
            "运行一个可复现的示例并记录输入输出。",
            "对照完成标准整理结果和问题。",
        ])
    criteria = _as_str_list(practice.get("acceptance_criteria") or practice.get("criteria"))
    if len(criteria) < 2:
        criteria.extend(["提交可复现步骤", "说明结果是否满足学习目标"])
    return {
        "title": _first_text(practice.get("title") or practice.get("name"), f"{item.title} 实操任务"),
        "steps": steps[:8],
        "expected_artifact": _first_text(practice.get("expected_artifact") or practice.get("artifact"), "实操报告、关键结果或可运行产物链接"),
        "acceptance_criteria": criteria[:6],
    }


def _fallback_slides(project: LearningProject, item: LearningSyllabusItem, start: int = 1) -> list[dict]:
    base = [
        ("学习目标与任务背景", [item.objective, project.learning_goal]),
        ("核心知识点", item.knowledge_points or [item.title, project.research_direction]),
        ("方法拆解", [item.recommendation_reason, item.completion_criteria]),
        ("例题与误区", [item.assessment_method, "说明常见错误和检查方式"]),
        ("实操与复盘", ["完成实践任务", "提交证据和下一步行动"]),
    ]
    return [
        {"title": title, "bullets": bullets[:6], "speaker_notes": "根据当前学习项展开讲解。"}
        for title, bullets in base[start - 1 :]
    ]


def _fallback_quiz(item: LearningSyllabusItem, start: int = 1) -> list[dict]:
    questions = [
        {"prompt": f"{item.title} 主要解决什么问题？", "answer": item.title},
        {"prompt": f"完成 {item.title} 后应该能产出什么证据？", "answer": item.completion_criteria or item.assessment_method or item.title},
    ]
    return [
        {"id": f"q{start + index}", "prompt": q["prompt"], "answer": q["answer"], "explanation": "围绕学习目标和完成标准作答。"}
        for index, q in enumerate(questions)
    ]


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _as_str_list(value: Any) -> list[str]:
    result: list[str] = []
    for item_value in _as_list(value):
        if isinstance(item_value, dict):
            text = item_value.get("text") or item_value.get("content") or item_value.get("title") or json.dumps(item_value, ensure_ascii=False)
        else:
            text = str(item_value)
        text = text.strip()
        if text:
            result.append(text)
    return result


def _first_text(value: Any, fallback: str) -> str:
    texts = _as_str_list(value)
    return texts[0] if texts else fallback
