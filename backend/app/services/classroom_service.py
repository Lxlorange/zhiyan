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
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt
from sqlalchemy import Select, select
from sqlalchemy.orm import Session, object_session, selectinload

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
    ClassroomDialogueRequest,
    ClassroomPracticeSubmitRequest,
    ClassroomQuizSubmitRequest,
    ClassroomReflectionSubmitRequest,
    ClassroomSlidesCompleteRequest,
    ClassroomVisualizationGenerateRequest,
    ClassroomVoiceGenerateRequest,
    SyllabusItemStatusRequest,
)
from app.core.config import get_settings
from app.services.knowledge_ingestion_service import build_rag_context
from app.services.llm_client import LLMConfigurationError, LLMResponseError, qwen_chat_json, validate_qwen_config
from app.services.syllabus_service import update_syllabus_item_status
from app.services.visualization_3d_renderer import render_three_physics_html


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


class _ConceptCardSpec(BaseModel):
    name: str
    explanation: str
    scenario: str
    misconception: str
    relation_to_project: str


class _DiagramSpec(BaseModel):
    title: str
    diagram_type: str
    mermaid: str
    explanation: str


class _VoiceScriptSpec(BaseModel):
    one_minute: str
    five_minutes: str
    segments: list[str] = Field(min_length=1, max_length=8)


class _ReproductionDemoSpec(BaseModel):
    title: str
    task: str
    input_format: str
    code_skeleton: str = ""
    steps: list[str] = Field(min_length=1, max_length=8)
    expected_output: str
    parameters: list[str] = Field(min_length=1, max_length=8)
    common_errors: list[str] = Field(min_length=1, max_length=8)
    report_suggestions: list[str] = Field(min_length=1, max_length=8)


class _GuidingQuestionSpec(BaseModel):
    prompt: str
    intent: str
    hint: str


class _ReadingSpec(BaseModel):
    title: str
    why: str
    source: str
    keywords: list[str] = Field(min_length=1, max_length=8)


class _ClassroomPackage(BaseModel):
    title: str
    learning_summary: str
    slides: list[_SlideSpec] = Field(min_length=5, max_length=9)
    concept_cards: list[_ConceptCardSpec] = Field(min_length=3, max_length=6)
    diagram: _DiagramSpec
    guiding_questions: list[_GuidingQuestionSpec] = Field(min_length=3, max_length=6)
    voice_script: _VoiceScriptSpec
    reproduction_demo: _ReproductionDemoSpec
    readings: list[_ReadingSpec] = Field(min_length=2, max_length=5)
    quiz: list[_QuizSpec] = Field(min_length=2, max_length=5)
    practice: _PracticeSpec
    reflection_prompts: list[str] = Field(min_length=3, max_length=6)
    safety_notes: list[str]


class _VisualizationFrame(BaseModel):
    label: str
    metrics: dict[str, float]
    narrative: str


class _VisualizationControl(BaseModel):
    name: str
    label: str
    min_value: float
    max_value: float
    default_value: float
    description: str


class _PhysicsObjectSpec(BaseModel):
    id: str
    label: str
    role: str
    shape: str
    size: list[float] = Field(min_length=3, max_length=3)
    position: list[float] = Field(min_length=3, max_length=3)
    velocity: list[float] = Field(min_length=3, max_length=3)
    mass: float
    color: str


class _PhysicsSceneSpec(BaseModel):
    scene_kind: str
    gravity: list[float] = Field(min_length=3, max_length=3)
    camera: dict[str, list[float]]
    objects: list[_PhysicsObjectSpec] = Field(min_length=4, max_length=9)


class _VisualizationDemo(BaseModel):
    title: str
    demo_type: str
    learning_goal: str
    description: str
    variables: list[str] = Field(min_length=2, max_length=8)
    frames: list[_VisualizationFrame] = Field(min_length=4, max_length=12)
    controls: list[_VisualizationControl]
    teaching_points: list[str] = Field(min_length=3, max_length=8)
    student_tasks: list[str] = Field(min_length=2, max_length=6)
    safety_notes: list[str] = Field(min_length=1)
    physics_scene: _PhysicsSceneSpec


class _DialogueCard(BaseModel):
    card_type: str
    title: str
    content: str
    metadata: dict[str, Any]


class _DialogueAgentResponse(BaseModel):
    answer: str
    cards: list[_DialogueCard]
    suggested_actions: list[str]
    profile_update_suggestion: str


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


def generate_classroom_visualization(
    db: Session,
    user: User,
    session_id: int,
    request: ClassroomVisualizationGenerateRequest,
) -> ClassroomSession:
    session = _get_session(db, user, session_id)
    item = _item_or_404(db, user, session.syllabus_item_id)
    project = _project_or_404(db, user, session.project_id)
    package = _classroom_package_or_error(session)
    demo = _generate_visualization_demo(project, item, package, request.instruction)
    html_path = _write_visualization_html(session.id, item, demo)

    resource = ClassroomResource(
        session_id=session.id,
        syllabus_item_id=item.id,
        project_id=project.id,
        user_id=user.id,
        resource_type="interactive_visualization",
        title=demo.title,
        content_data=demo.model_dump(mode="json"),
        file_path=str(html_path),
        source="THU-MAIC/OpenMAIC-inspired; Three.js; cannon-es",
        status="ready",
    )
    db.add(resource)
    db.add(
        AgentTaskRecord(
            session_id=f"classroom-{session.id}",
            user_id=user.id,
            agent="VisualizationAgent+PhysicsSimulationAgent",
            status="completed",
            input_summary=f"{project.title} / {item.title}",
            output_summary=f"生成 3D 物理演示：{demo.title}",
            latency_ms=0,
        )
    )
    _write_event(
        db,
        project,
        user,
        "classroom_visualization_generated",
        f"生成 3D 物理演示：{demo.title}",
        {"session_id": session.id, "demo_type": demo.demo_type},
    )
    db.commit()
    return _get_session(db, user, session.id)


def generate_classroom_voice(
    db: Session,
    user: User,
    session_id: int,
    request: ClassroomVoiceGenerateRequest,
) -> ClassroomSession:
    session = _get_session(db, user, session_id)
    item = _item_or_404(db, user, session.syllabus_item_id)
    project = _project_or_404(db, user, session.project_id)
    package = _classroom_package_or_error(session)
    voice_text = _voice_text_for_scope(package, request.text_scope)
    voice_path = _write_voice_script_file(session.id, item, request, voice_text)
    resource = ClassroomResource(
        session_id=session.id,
        syllabus_item_id=item.id,
        project_id=project.id,
        user_id=user.id,
        resource_type="voice_script",
        title=f"{item.title} 语音讲解稿",
        content_data={
            "voice_name": request.voice_name,
            "speed": request.speed,
            "text_scope": request.text_scope,
            "text": voice_text,
            "provider": "browser_speech_synthesis",
            "xunfei_ready": False,
        },
        file_path=str(voice_path),
        source="Browser SpeechSynthesis; Xunfei TTS adapter pending",
        status="ready",
    )
    db.add(resource)
    db.add(
        AgentTaskRecord(
            session_id=f"classroom-{session.id}",
            user_id=user.id,
            agent="VoiceAgent",
            status="completed",
            input_summary=f"{request.text_scope} / {request.voice_name}",
            output_summary=f"生成课堂语音播放稿：{item.title}",
            latency_ms=0,
        )
    )
    _write_event(db, project, user, "classroom_voice_script_generated", f"生成语音讲解稿：{item.title}", {"resource_id": resource.id})
    db.commit()
    return _get_session(db, user, session.id)


def send_classroom_dialogue(
    db: Session,
    user: User,
    session_id: int,
    request: ClassroomDialogueRequest,
) -> dict[str, Any]:
    session = _get_session(db, user, session_id)
    item = _item_or_404(db, user, session.syllabus_item_id)
    project = _project_or_404(db, user, session.project_id)
    package = _classroom_package_or_error(session)
    response = _generate_dialogue_response(project, item, session, package, request)

    _add_submission(
        db,
        session=session,
        user=user,
        item=item,
        submission_type="dialogue_user",
        content={"role": "user", "message": request.message, "quick_action": request.quick_action},
        score=0,
        passed=True,
        feedback="课堂追问已记录",
    )
    _add_submission(
        db,
        session=session,
        user=user,
        item=item,
        submission_type="dialogue_assistant",
        content={
            "role": "assistant",
            "message": response.answer,
            "cards": [card.model_dump() for card in response.cards],
            "suggested_actions": response.suggested_actions,
            "profile_update_suggestion": response.profile_update_suggestion,
        },
        score=0,
        passed=True,
        feedback="AI 助教已回答",
    )
    db.add(
        AgentTaskRecord(
            session_id=f"classroom-{session.id}",
            user_id=user.id,
            agent="DialogueAgent",
            status="completed",
            input_summary=request.message[:300],
            output_summary=response.answer[:500],
            latency_ms=0,
        )
    )
    db.commit()
    return {
        "answer": response.answer,
        "cards": [card.model_dump() for card in response.cards],
        "suggested_actions": response.suggested_actions,
        "profile_update_suggestion": response.profile_update_suggestion,
        "session": _get_session(db, user, session.id),
    }


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
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank_layout = prs.slide_layouts[6]

    title_slide = prs.slides.add_slide(blank_layout)
    _paint_slide_background(title_slide, prs)
    _add_label(title_slide, "AI CLASSROOM", Inches(0.72), Inches(0.58), Inches(2.2), Inches(0.32), Pt(11), RGBColor(79, 70, 229), bold=True)
    _add_text(
        title_slide,
        package.title,
        Inches(0.72),
        Inches(1.55),
        Inches(8.2),
        Inches(1.4),
        Pt(36),
        RGBColor(30, 27, 75),
        bold=True,
    )
    _add_text(title_slide, item.title, Inches(0.76), Inches(3.05), Inches(8.8), Inches(0.55), Pt(18), RGBColor(71, 85, 105))
    _add_text(title_slide, package.learning_summary, Inches(0.78), Inches(3.85), Inches(6.6), Inches(1.4), Pt(17), RGBColor(49, 46, 129))
    _add_accent_panel(title_slide, Inches(9.25), Inches(1.12), Inches(3.25), Inches(4.95), "个性化课堂", item.knowledge_points[:4] or [item.title])

    for index, spec in enumerate(package.slides, start=1):
        slide = prs.slides.add_slide(blank_layout)
        _paint_slide_background(slide, prs)
        _add_label(slide, f"SLIDE {index:02d}", Inches(0.7), Inches(0.46), Inches(1.6), Inches(0.3), Pt(10), RGBColor(79, 70, 229), bold=True)
        _add_text(slide, spec.title, Inches(0.72), Inches(0.92), Inches(8.7), Inches(0.72), Pt(28), RGBColor(30, 27, 75), bold=True)
        for bullet_index, bullet in enumerate(spec.bullets[:5]):
            top = Inches(1.95 + bullet_index * 0.78)
            _add_bullet_card(slide, bullet, Inches(0.9), top, Inches(7.6), Inches(0.58), bullet_index + 1)
        _add_speaker_panel(slide, spec.speaker_notes)
        _add_footer(slide, package.title, index, len(package.slides))
        notes = slide.notes_slide.notes_text_frame
        notes.text = spec.speaker_notes

    quiz_slide = prs.slides.add_slide(blank_layout)
    _paint_slide_background(quiz_slide, prs)
    _add_text(quiz_slide, "课堂例题", Inches(0.72), Inches(0.72), Inches(4.8), Inches(0.62), Pt(30), RGBColor(30, 27, 75), bold=True)
    for index, question in enumerate(package.quiz[:4]):
        left = Inches(0.78 + (index % 2) * 6.0)
        top = Inches(1.72 + (index // 2) * 2.15)
        _add_question_card(quiz_slide, f"{question.id}. {question.prompt}", question.explanation, left, top)

    practice_slide = prs.slides.add_slide(blank_layout)
    _paint_slide_background(practice_slide, prs)
    _add_text(practice_slide, package.practice.title, Inches(0.72), Inches(0.72), Inches(7.5), Inches(0.62), Pt(30), RGBColor(30, 27, 75), bold=True)
    for index, step in enumerate(package.practice.steps[:6]):
        _add_bullet_card(practice_slide, step, Inches(0.9), Inches(1.68 + index * 0.72), Inches(8.2), Inches(0.52), index + 1)
    _add_accent_panel(practice_slide, Inches(9.65), Inches(1.45), Inches(2.7), Inches(4.45), "验收标准", package.practice.acceptance_criteria[:4])

    prs.save(path)
    return path


def _voice_text_for_scope(package: _ClassroomPackage, scope: str) -> str:
    if scope == "all_slides":
        return "\n\n".join([f"{slide.title}。{slide.speaker_notes}" for slide in package.slides])
    if scope == "five_minutes":
        return package.voice_script.five_minutes or package.voice_script.one_minute
    if scope == "one_minute":
        return package.voice_script.one_minute or package.learning_summary
    first_slide = package.slides[0] if package.slides else None
    return first_slide.speaker_notes if first_slide else (package.voice_script.one_minute or package.learning_summary)


def _write_voice_script_file(
    session_id: int,
    item: LearningSyllabusItem,
    request: ClassroomVoiceGenerateRequest,
    voice_text: str,
) -> Path:
    output_dir = Path(__file__).resolve().parents[2] / "generated" / "voice"
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"classroom-{session_id}-item-{item.id}-{request.text_scope}.txt"
    path.write_text(voice_text, encoding="utf-8")
    return path


def _paint_slide_background(slide: Any, prs: Presentation) -> None:
    bg = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height)
    bg.fill.solid()
    bg.fill.fore_color.rgb = RGBColor(248, 251, 255)
    bg.line.fill.background()
    accent = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(10.4), Inches(-0.45), Inches(3.7), Inches(2.15))
    accent.fill.solid()
    accent.fill.fore_color.rgb = RGBColor(224, 231, 255)
    accent.line.fill.background()
    bar = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.72), Inches(6.76), Inches(2.1), Inches(0.09))
    bar.fill.solid()
    bar.fill.fore_color.rgb = RGBColor(34, 197, 94)
    bar.line.fill.background()


def _add_text(slide: Any, text: str, left: Any, top: Any, width: Any, height: Any, size: Any, color: RGBColor, bold: bool = False) -> Any:
    shape = slide.shapes.add_textbox(left, top, width, height)
    frame = shape.text_frame
    frame.clear()
    frame.word_wrap = True
    paragraph = frame.paragraphs[0]
    paragraph.text = text
    paragraph.font.size = size
    paragraph.font.bold = bold
    paragraph.font.color.rgb = color
    return shape


def _add_label(slide: Any, text: str, left: Any, top: Any, width: Any, height: Any, size: Any, color: RGBColor, bold: bool = False) -> None:
    shape = _add_text(slide, text, left, top, width, height, size, color, bold)
    shape.text_frame.paragraphs[0].alignment = PP_ALIGN.LEFT


def _add_bullet_card(slide: Any, text: str, left: Any, top: Any, width: Any, height: Any, number: int) -> None:
    card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
    card.fill.solid()
    card.fill.fore_color.rgb = RGBColor(255, 255, 255)
    card.line.color.rgb = RGBColor(219, 228, 255)
    badge = slide.shapes.add_shape(MSO_SHAPE.OVAL, left + Inches(0.12), top + Inches(0.12), Inches(0.34), Inches(0.34))
    badge.fill.solid()
    badge.fill.fore_color.rgb = RGBColor(79, 70, 229)
    badge.line.fill.background()
    badge_frame = badge.text_frame
    badge_frame.clear()
    badge_paragraph = badge_frame.paragraphs[0]
    badge_paragraph.text = str(number)
    badge_paragraph.alignment = PP_ALIGN.CENTER
    badge_paragraph.font.size = Pt(10)
    badge_paragraph.font.bold = True
    badge_paragraph.font.color.rgb = RGBColor(255, 255, 255)
    _add_text(slide, text, left + Inches(0.6), top + Inches(0.11), width - Inches(0.76), height - Inches(0.12), Pt(16), RGBColor(49, 46, 129))


def _add_speaker_panel(slide: Any, notes: str) -> None:
    panel = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(9.15), Inches(1.6), Inches(3.35), Inches(4.55))
    panel.fill.solid()
    panel.fill.fore_color.rgb = RGBColor(240, 253, 244)
    panel.line.color.rgb = RGBColor(187, 247, 208)
    _add_label(slide, "TEACHER NOTES", Inches(9.42), Inches(1.9), Inches(2.4), Inches(0.32), Pt(10), RGBColor(22, 101, 52), bold=True)
    _add_text(slide, notes, Inches(9.42), Inches(2.34), Inches(2.75), Inches(3.35), Pt(13), RGBColor(22, 101, 52))


def _add_accent_panel(slide: Any, left: Any, top: Any, width: Any, height: Any, title: str, items: list[str]) -> None:
    panel = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
    panel.fill.solid()
    panel.fill.fore_color.rgb = RGBColor(238, 242, 255)
    panel.line.color.rgb = RGBColor(199, 210, 254)
    _add_text(slide, title, left + Inches(0.28), top + Inches(0.28), width - Inches(0.5), Inches(0.4), Pt(17), RGBColor(49, 46, 129), bold=True)
    for index, item_text in enumerate(items[:5]):
        _add_text(slide, f"{index + 1}. {item_text}", left + Inches(0.3), top + Inches(0.86 + index * 0.58), width - Inches(0.6), Inches(0.44), Pt(13), RGBColor(71, 85, 105))


def _add_question_card(slide: Any, prompt: str, explanation: str, left: Any, top: Any) -> None:
    card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, Inches(5.35), Inches(1.75))
    card.fill.solid()
    card.fill.fore_color.rgb = RGBColor(255, 255, 255)
    card.line.color.rgb = RGBColor(219, 228, 255)
    _add_text(slide, prompt, left + Inches(0.28), top + Inches(0.22), Inches(4.75), Inches(0.66), Pt(15), RGBColor(30, 27, 75), bold=True)
    _add_text(slide, explanation, left + Inches(0.28), top + Inches(0.95), Inches(4.75), Inches(0.52), Pt(12), RGBColor(71, 85, 105))


def _add_footer(slide: Any, title: str, index: int, total: int) -> None:
    _add_text(slide, title[:48], Inches(0.72), Inches(6.92), Inches(5.2), Inches(0.25), Pt(9), RGBColor(100, 116, 139))
    footer = _add_text(slide, f"{index}/{total}", Inches(12.0), Inches(6.9), Inches(0.55), Inches(0.25), Pt(10), RGBColor(100, 116, 139), bold=True)
    footer.text_frame.paragraphs[0].alignment = PP_ALIGN.RIGHT


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


def _generate_visualization_demo(
    project: LearningProject,
    item: LearningSyllabusItem,
    package: _ClassroomPackage,
    instruction: str,
) -> _VisualizationDemo:
    knowledge_context = build_rag_context_for_classroom(project, item, instruction)
    raw = _qwen_chat_raw_json(
        (
            "你是 VisualizationAgent + PhysicsSimulationAgent，负责为高校 AI 课堂生成 Three.js + cannon-es "
            "可交互 3D 物理演示规格。只输出 JSON，不输出 Markdown、HTML 或 JavaScript。"
        ),
        (
            "请生成一个与学习主题强相关的 3D 物理演示数据规格，后端会把该 JSON 渲染为 Three.js + cannon-es HTML。\n"
            "顶层字段必须完整包含：title, demo_type, learning_goal, description, variables, frames, controls, "
            "teaching_points, student_tasks, safety_notes, physics_scene。\n"
            "demo_type 必须从以下值选择：signal_wave, network_packet, neural_activation, optimization_landscape, "
            "sorting_collision, graph_diffusion, physics_system。\n"
            "physics_scene 必须包含 scene_kind, gravity, camera, objects。\n"
            "scene_kind 必须从以下值选择：signal_wave, network_packet, neural_activation, optimization_landscape, "
            "sorting_collision, graph_diffusion, general_physics。\n"
            "camera 必须包含 position 和 target，二者都是 3 个数字的数组。\n"
            "objects 必须包含 4 到 9 个对象；每个对象必须包含 id, label, role, shape, size, position, velocity, mass, color。\n"
            "shape 只能使用 sphere, box, cylinder, packet, node；size/position/velocity 都必须是 3 个数字的数组；color 必须是十六进制颜色。\n"
            "frames 需要 4 到 12 帧；每帧必须包含 label, narrative, metrics；metrics 至少包含 progress, force, activity 三个 0 到 1 或合理正数。\n"
            "controls 至少 3 个，建议包含 speed, force, damping 或 gravity；每个控制器必须包含 name, label, min_value, max_value, default_value, description。\n"
            "必须结合课程知识库来源和课堂摘要生成内容，不能输出空数组、占位符、模板化泛泛描述或具体题目无关的演示。\n"
            f"项目：{project.title}\n"
            f"研究方向：{project.research_direction}\n"
            f"学习项：{item.title}\n"
            f"学习目标：{item.objective}\n"
            f"知识点：{item.knowledge_points}\n"
            f"课程知识库来源：\n{knowledge_context}\n"
            f"课堂摘要：{package.learning_summary}\n"
            f"补充要求：{instruction}\n"
        ),
    )
    normalized = _normalize_visualization_demo(raw)
    try:
        return _VisualizationDemo.model_validate(normalized)
    except Exception as exc:
        raise LLMResponseError(f"3D 物理演示 JSON 归一化后仍未通过结构校验：{exc}") from exc


def _generate_dialogue_response(
    project: LearningProject,
    item: LearningSyllabusItem,
    session: ClassroomSession,
    package: _ClassroomPackage,
    request: ClassroomDialogueRequest,
) -> _DialogueAgentResponse:
    knowledge_context = build_rag_context_for_classroom(project, item, request.message)
    history = [
        submission.content
        for submission in session.submissions
        if submission.submission_type in {"dialogue_user", "dialogue_assistant"}
    ][-10:]
    return qwen_chat_json(
        (
            "你是 DialogueAgent，是课堂中的 AI 助教。"
            "回答必须依托当前课堂上下文，短而可执行；需要时输出 cards 用于前端卡片展示。"
            "只输出 JSON，不输出 Markdown 外壳。"
        ),
        (
            f"项目：{project.title}\n"
            f"研究方向：{project.research_direction}\n"
            f"学习项：{item.title}\n"
            f"学习目标：{item.objective}\n"
            f"课堂摘要：{package.learning_summary}\n"
            f"概念卡：{[card.model_dump() for card in package.concept_cards]}\n"
            f"引导问题：{[question.model_dump() for question in package.guiding_questions]}\n"
            f"课程知识库来源：\n{knowledge_context}\n"
            f"最近对话：{history}\n"
            f"快捷动作：{request.quick_action}\n"
            f"学生问题：{request.message}\n"
            "输出字段：answer, cards, suggested_actions, profile_update_suggestion。"
            "cards 每项包含 card_type, title, content, metadata；card_type 可为 concept, example, code, quiz, diagram, next_step。"
        ),
        _DialogueAgentResponse,
    )


def _normalize_visualization_demo(raw: Any, project: LearningProject, item: LearningSyllabusItem, package: _ClassroomPackage) -> dict:
    if not isinstance(raw, dict):
        raise LLMResponseError("3D 物理演示 JSON 顶层必须是对象")
    data = raw
    variables = [_normalize_visualization_variable(value) for value in _as_list(data.get("variables"))]
    variables = [value for value in variables if value]
    if len(variables) < 2:
        raise LLMResponseError("3D 物理演示 JSON 缺少 variables，至少需要 2 个变量")
    frames = [
        _normalize_visualization_frame(frame, index, variables)
        for index, frame in enumerate(_as_list(data.get("frames")), start=1)
    ]
    if len(frames) < 4:
        raise LLMResponseError("3D 物理演示 JSON 缺少 frames，至少需要 4 帧")
    controls = [
        _normalize_visualization_control(control, index)
        for index, control in enumerate(_as_list(data.get("controls")), start=1)
    ]
    if not controls:
        raise LLMResponseError("3D 物理演示 JSON 缺少 controls，至少需要 1 个控制器")
    safety_notes = _as_str_list(data.get("safety_notes"))
    if not safety_notes:
        raise LLMResponseError("3D 物理演示 JSON 缺少 safety_notes")
    teaching_points = _as_str_list(data.get("teaching_points"))
    if len(teaching_points) < 3:
        raise LLMResponseError("3D 物理演示 JSON 缺少 teaching_points，至少需要 3 条")
    student_tasks = _as_str_list(data.get("student_tasks"))
    if len(student_tasks) < 2:
        raise LLMResponseError("3D 物理演示 JSON 缺少 student_tasks，至少需要 2 条")
    demo_type = _normalize_demo_type(_require_text(data.get("demo_type"), "visualization.demo_type"))
    return {
        "title": _require_text(data.get("title"), "visualization.title"),
        "demo_type": demo_type,
        "learning_goal": _require_text(data.get("learning_goal"), "visualization.learning_goal"),
        "description": _require_text(data.get("description"), "visualization.description"),
        "variables": variables[:8],
        "frames": frames[:12],
        "controls": controls,
        "teaching_points": teaching_points[:8],
        "student_tasks": student_tasks[:6],
        "safety_notes": safety_notes,
        "physics_scene": _normalize_physics_scene(data.get("physics_scene"), demo_type),
    }


def _normalize_visualization_variable(raw: Any) -> str:
    if isinstance(raw, dict):
        return _require_text(raw.get("label") or raw.get("name") or raw.get("title") or raw.get("id"), "visualization.variables[]")
    return str(raw).strip()


def _normalize_visualization_frame(raw: Any, index: int, variables: list[str]) -> dict:
    if not isinstance(raw, dict):
        raise LLMResponseError(f"3D 物理演示 JSON frames[{index}] 必须是对象")
    metrics = _numeric_metrics(raw.get("metrics") if isinstance(raw.get("metrics"), dict) else {})
    if not metrics:
        raise LLMResponseError(f"3D 物理演示 JSON frames[{index}] 缺少可渲染的 metrics")
    return {
        "label": _require_text(raw.get("label"), f"visualization.frames[{index}].label"),
        "metrics": metrics,
        "narrative": _require_text(raw.get("narrative"), f"visualization.frames[{index}].narrative"),
    }


def _normalize_visualization_control(raw: Any, index: int) -> dict:
    if not isinstance(raw, dict):
        raise LLMResponseError(f"3D 物理演示 JSON controls[{index}] 必须是对象")
    return {
        "name": _require_text(raw.get("name"), f"visualization.controls[{index}].name"),
        "label": _require_text(raw.get("label"), f"visualization.controls[{index}].label"),
        "min_value": _require_metric(raw.get("min_value"), f"visualization.controls[{index}].min_value"),
        "max_value": _require_metric(raw.get("max_value"), f"visualization.controls[{index}].max_value"),
        "default_value": _require_metric(raw.get("default_value"), f"visualization.controls[{index}].default_value"),
        "description": _require_text(raw.get("description"), f"visualization.controls[{index}].description"),
    }


def _normalize_demo_type(value: str) -> str:
    allowed = {
        "signal_wave",
        "network_packet",
        "neural_activation",
        "optimization_landscape",
        "sorting_collision",
        "graph_diffusion",
        "physics_system",
    }
    normalized = value.strip().lower().replace("-", "_").replace(" ", "_")
    if normalized not in allowed:
        raise LLMResponseError(f"3D 物理演示 JSON demo_type 非法：{value}；允许值：{', '.join(sorted(allowed))}")
    return normalized


def _normalize_physics_scene(raw: Any, demo_type: str) -> dict:
    if not isinstance(raw, dict):
        raise LLMResponseError("3D 物理演示 JSON 缺少 physics_scene 对象")
    allowed_kinds = {
        "signal_wave",
        "network_packet",
        "neural_activation",
        "optimization_landscape",
        "sorting_collision",
        "graph_diffusion",
        "general_physics",
    }
    scene_kind = _require_text(raw.get("scene_kind"), "visualization.physics_scene.scene_kind")
    scene_kind = scene_kind.strip().lower().replace("-", "_").replace(" ", "_")
    if scene_kind not in allowed_kinds:
        raise LLMResponseError(f"3D 物理演示 JSON scene_kind 非法：{scene_kind}；允许值：{', '.join(sorted(allowed_kinds))}")
    if demo_type != "physics_system" and scene_kind == "general_physics":
        raise LLMResponseError("3D 物理演示 JSON scene_kind 不能在具体 demo_type 下使用 general_physics")
    camera = raw.get("camera")
    if not isinstance(camera, dict):
        raise LLMResponseError("3D 物理演示 JSON physics_scene.camera 必须是对象")
    objects = [
        _normalize_physics_object(obj, index)
        for index, obj in enumerate(_as_list(raw.get("objects")), start=1)
    ]
    if len(objects) < 4:
        raise LLMResponseError("3D 物理演示 JSON physics_scene.objects 至少需要 4 个对象")
    if len(objects) > 9:
        raise LLMResponseError("3D 物理演示 JSON physics_scene.objects 最多允许 9 个对象")
    return {
        "scene_kind": scene_kind,
        "gravity": _vector3(raw.get("gravity"), "visualization.physics_scene.gravity"),
        "camera": {
            "position": _vector3(camera.get("position"), "visualization.physics_scene.camera.position"),
            "target": _vector3(camera.get("target"), "visualization.physics_scene.camera.target"),
        },
        "objects": objects,
    }


def _normalize_physics_object(raw: Any, index: int) -> dict:
    if not isinstance(raw, dict):
        raise LLMResponseError(f"3D 物理演示 JSON physics_scene.objects[{index}] 必须是对象")
    allowed_shapes = {"sphere", "box", "cylinder", "packet", "node"}
    shape = _require_text(raw.get("shape"), f"visualization.physics_scene.objects[{index}].shape")
    shape = shape.strip().lower().replace("-", "_").replace(" ", "_")
    if shape not in allowed_shapes:
        raise LLMResponseError(f"3D 物理演示 JSON objects[{index}].shape 非法：{shape}；允许值：{', '.join(sorted(allowed_shapes))}")
    mass = _require_metric(raw.get("mass"), f"visualization.physics_scene.objects[{index}].mass")
    if mass < 0:
        raise LLMResponseError(f"3D 物理演示 JSON objects[{index}].mass 不能小于 0")
    return {
        "id": _require_text(raw.get("id"), f"visualization.physics_scene.objects[{index}].id"),
        "label": _require_text(raw.get("label"), f"visualization.physics_scene.objects[{index}].label"),
        "role": _require_text(raw.get("role"), f"visualization.physics_scene.objects[{index}].role"),
        "shape": shape,
        "size": _positive_vector3(raw.get("size"), f"visualization.physics_scene.objects[{index}].size"),
        "position": _vector3(raw.get("position"), f"visualization.physics_scene.objects[{index}].position"),
        "velocity": _vector3(raw.get("velocity"), f"visualization.physics_scene.objects[{index}].velocity"),
        "mass": mass,
        "color": _require_color(raw.get("color"), f"visualization.physics_scene.objects[{index}].color"),
    }


def _vector3(value: Any, field_path: str) -> list[float]:
    if not isinstance(value, list) or len(value) != 3:
        raise LLMResponseError(f"模型 JSON 字段 {field_path} 必须是长度为 3 的数字数组")
    vector: list[float] = []
    for index, item in enumerate(value):
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise LLMResponseError(f"模型 JSON 字段 {field_path}[{index}] 必须是数字")
        vector.append(float(item))
    return vector


def _positive_vector3(value: Any, field_path: str) -> list[float]:
    vector = _vector3(value, field_path)
    if any(item <= 0 for item in vector):
        raise LLMResponseError(f"模型 JSON 字段 {field_path} 必须全部大于 0")
    return vector


def _require_color(value: Any, field_path: str) -> str:
    color = _require_text(value, field_path)
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
        raise LLMResponseError(f"模型 JSON 字段 {field_path} 必须是 #RRGGBB 十六进制颜色")
    return color


def _numeric_metrics(raw: dict[str, Any]) -> dict[str, float]:
    result: dict[str, float] = {}
    for key, value in raw.items():
        metric = _metric_value(value)
        if metric is not None:
            result[str(key)] = metric
    return result


def _metric_value(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            return float(stripped)
        except ValueError:
            return (sum(ord(ch) for ch in stripped) % 100) / 100
    if isinstance(value, list):
        return min(1.0, len(value) / 10)
    if isinstance(value, dict):
        return min(1.0, len(value) / 10)
    return None


def _require_metric(value: Any, field_path: str) -> float:
    metric = _metric_value(value)
    if metric is None:
        raise LLMResponseError(f"模型 JSON 字段 {field_path} 必须是可解析数值")
    return metric


def _write_visualization_html(session_id: int, item: LearningSyllabusItem, demo: _VisualizationDemo) -> Path:
    output_dir = Path(__file__).resolve().parents[2] / "generated" / "visualizations"
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"classroom-{session_id}-item-{item.id}-visualization.html"
    html_doc = render_three_physics_html(demo.model_dump(mode="json"), demo.title)
    path.write_text(html_doc, encoding="utf-8")
    return path


def _generate_classroom_package(project: LearningProject, item: LearningSyllabusItem, instruction: str) -> _ClassroomPackage:
    mode_hint = _classroom_mode_hint(project, item)
    knowledge_context = build_rag_context_for_classroom(project, item, instruction)
    system_prompt = (
        "你是面向高校学生的 OpenMAIC 风格多智能体课堂生成系统。"
        "只输出严格 JSON，不要 Markdown，不要解释 JSON 之外的内容。"
        "课堂必须由 ClassroomAgent、ExplanationAgent、ExerciseAgent、DemoAgent、SafetyAgent 协同产出，"
        "避免长文堆叠，内容要适合 Vue 页面分卡片渲染。"
    )
    user_prompt = (
        "参考 THU-MAIC/OpenMAIC 的课堂产物组织方式：slides、quizzes、interactive/practice、PBL/reflection、interactive HTML simulation。\n"
        "必须输出顶层字段：title, learning_summary, slides, concept_cards, diagram, guiding_questions, voice_script, "
        "reproduction_demo, readings, quiz, practice, reflection_prompts, safety_notes。\n"
        "slides: 5-9 项，每项包含 title, bullets, speaker_notes，bullets 2-6 条。\n"
        "concept_cards: 3-6 项，每项包含 name, explanation, scenario, misconception, relation_to_project。\n"
        "diagram: 包含 title, diagram_type, mermaid, explanation；mermaid 使用 flowchart TD 或 graph TD。\n"
        "guiding_questions: 3-6 项，每项包含 prompt, intent, hint。\n"
        "voice_script: 包含 one_minute, five_minutes, segments。\n"
        "reproduction_demo: 包含 title, task, input_format, code_skeleton, steps, expected_output, parameters, common_errors, report_suggestions。\n"
        "readings: 2-5 项，每项包含 title, why, source, keywords。\n"
        "quiz: 2-5 项，每项包含 id, prompt, answer, explanation。\n"
        "practice: 包含 title, steps, expected_artifact, acceptance_criteria。\n"
        "reflection_prompts: 3-6 条。safety_notes: 至少 1 条。\n"
        "严禁省略字段，严禁只返回 slides。字段缺失会被系统直接判定为生成失败。\n"
        "如果某字段暂时无法确定，必须基于学习项生成可执行内容；不得返回空字符串、空数组或占位符。\n"
        "文献综述模式必须给出论文/资料列表、摘要要点、来源字段、对比矩阵和阅读任务；不得编造已发表事实。\n"
        "选题凝练模式必须形成具体题目、研究问题、方法边界、数据与指标、预期贡献和不可做事项。\n"
        "实验助手模式必须生成技术路线、数据采集方案、评价指标、实验变量、图表规范建议和阶段计划。\n"
        "论文写作模式必须围绕课程论文结构、引用规范、图表规范和防幻觉边界设计练习。\n"
        "模拟答辩模式必须在 slides/guiding_questions/quiz/practice/reflection_prompts 中体现开题、中期、答辩问题、追问、评分和修改建议。\n"
        f"项目：{project.title}\n"
        f"研究方向：{project.research_direction}\n"
        f"学习目标：{project.learning_goal}\n"
        f"学习项：{item.title}\n"
        f"学习项目标：{item.objective}\n"
        f"知识点：{item.knowledge_points}\n"
        f"关联资料：{item.related_documents}\n"
        f"课程知识库来源：\n{knowledge_context}\n"
        f"完成标准：{item.completion_criteria}\n"
        f"评估方式：{item.assessment_method}\n"
        f"mode_hint：{mode_hint}\n"
        f"补充要求：{instruction}\n"
    )
    raw = _qwen_chat_raw_json(system_prompt, user_prompt)
    normalized = _normalize_classroom_package(raw, project, item)
    try:
        return _ClassroomPackage.model_validate(normalized)
    except Exception as exc:
        raise LLMResponseError(f"课堂包 JSON 归一化后仍未通过结构校验：{exc}") from exc


def build_rag_context_for_classroom(project: LearningProject, item: LearningSyllabusItem, instruction: str = "") -> str:
    query = "\n".join(
        [
            project.title,
            project.research_direction,
            project.learning_goal,
            item.title,
            item.objective,
            " ".join(item.knowledge_points or []),
            " ".join(item.related_documents or []),
            instruction,
        ]
    )
    db = object_session(project)
    if db is None:
        raise LLMResponseError("课堂生成无法获取数据库会话，不能检索课程知识库")
    return build_rag_context(db, query, limit=8)


def _classroom_mode_hint(project: LearningProject, item: LearningSyllabusItem) -> str:
    text = " ".join(
        [
            project.title,
            project.research_direction,
            project.learning_goal,
            item.title,
            item.item_type,
            " ".join(item.classroom_types or []),
            " ".join(item.knowledge_points or []),
        ]
    ).lower()
    if any(keyword in text for keyword in ["答辩", "defense", "interview", "面试"]):
        return "mock_defense"
    if any(keyword in text for keyword in ["实验助手", "experiment", "数据采集", "技术路线", "变量"]):
        return "experiment_assistant"
    if any(keyword in text for keyword in ["选题", "topic", "研究问题"]):
        return "topic_selection"
    if any(keyword in text for keyword in ["文献", "literature", "综述", "paper"]):
        return "literature_review"
    if any(keyword in text for keyword in ["论文", "写作", "格式", "引用"]):
        return "paper_writing"
    return "general_ai4s_lesson"


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
    if not isinstance(raw, dict):
        raise LLMResponseError("课堂包 JSON 顶层必须是对象")
    data = raw
    concept_cards = [_normalize_concept_card(value, item) for value in _as_list(data.get("concept_cards") or data.get("concepts"))]
    if len(concept_cards) < 3:
        raise LLMResponseError("课堂包 JSON 缺少 concept_cards，至少需要 3 张概念卡")
    guiding_questions = [_normalize_guiding_question(value, item) for value in _as_list(data.get("guiding_questions") or data.get("questions_to_think"))]
    if len(guiding_questions) < 3:
        raise LLMResponseError("课堂包 JSON 缺少 guiding_questions，至少需要 3 个引导问题")
    readings = [_normalize_reading(value, item) for value in _as_list(data.get("readings") or data.get("resources"))]
    if len(readings) < 2:
        raise LLMResponseError("课堂包 JSON 缺少 readings，至少需要 2 条阅读资源")
    slides = [_normalize_slide(slide, index) for index, slide in enumerate(_as_list(data.get("slides") or data.get("ppt") or data.get("deck")), start=1)]
    if len(slides) < 5:
        raise LLMResponseError("课堂包 JSON 缺少 slides，至少需要 5 页")
    slides = slides[:9]

    quiz_raw = data.get("quiz") or data.get("quizzes") or data.get("questions") or data.get("exercises")
    quiz = [_normalize_quiz(question, index, item) for index, question in enumerate(_as_list(quiz_raw), start=1)]
    if len(quiz) < 2:
        raise LLMResponseError("课堂包 JSON 缺少 quiz，至少需要 2 道题")
    quiz = quiz[:5]

    practice_source = data.get("practice") or data.get("interactive") or data.get("lab")
    if practice_source is None:
        raise LLMResponseError("课堂包 JSON 缺少 practice")
    practice = _normalize_practice(practice_source, item)
    reflection_prompts = _as_str_list(data.get("reflection_prompts") or data.get("reflection") or data.get("pbl"))
    if len(reflection_prompts) < 3:
        raise LLMResponseError("课堂包 JSON 缺少 reflection_prompts，至少需要 3 条")
    safety_notes = _as_str_list(data.get("safety_notes") or data.get("notes"))
    if not safety_notes:
        raise LLMResponseError("课堂包 JSON 缺少 safety_notes")
    return {
        "title": _require_text(data.get("title"), "classroom.title"),
        "learning_summary": _require_text(data.get("learning_summary") or data.get("summary"), "classroom.learning_summary"),
        "slides": slides,
        "concept_cards": concept_cards[:6],
        "diagram": _normalize_diagram(data.get("diagram") or data.get("mermaid"), item),
        "guiding_questions": guiding_questions[:6],
        "voice_script": _normalize_voice_script(data.get("voice_script") or data.get("script"), item),
        "reproduction_demo": _normalize_reproduction_demo(data.get("reproduction_demo") or data.get("demo"), item),
        "readings": readings[:5],
        "quiz": quiz,
        "practice": practice,
        "reflection_prompts": reflection_prompts[:6],
        "safety_notes": safety_notes,
    }


def _normalize_slide(raw: Any, index: int) -> dict:
    if not isinstance(raw, dict):
        raise LLMResponseError(f"课堂包 JSON slides[{index}] 必须是对象")
    slide = raw
    bullets = _as_str_list(slide.get("bullets") or slide.get("points") or slide.get("content") or slide.get("items"))
    if len(bullets) < 2:
        raise LLMResponseError(f"课堂包 JSON slides[{index}].bullets 至少需要 2 条")
    return {
        "title": _require_text(slide.get("title"), f"classroom.slides[{index}].title"),
        "bullets": bullets[:6],
        "speaker_notes": _require_text(slide.get("speaker_notes") or slide.get("notes"), f"classroom.slides[{index}].speaker_notes"),
    }


def _normalize_quiz(raw: Any, index: int, item: LearningSyllabusItem) -> dict:
    if not isinstance(raw, dict):
        raise LLMResponseError(f"课堂包 JSON quiz[{index}] 必须是对象")
    question = raw
    return {
        "id": _require_text(question.get("id"), f"classroom.quiz[{index}].id"),
        "prompt": _require_text(question.get("prompt") or question.get("question"), f"classroom.quiz[{index}].prompt"),
        "answer": _require_text(question.get("answer") or question.get("expected_answer"), f"classroom.quiz[{index}].answer"),
        "explanation": _require_text(question.get("explanation") or question.get("analysis"), f"classroom.quiz[{index}].explanation"),
    }


def _normalize_practice(raw: Any, item: LearningSyllabusItem) -> dict:
    if not isinstance(raw, dict):
        raise LLMResponseError("课堂包 JSON practice 必须是对象")
    practice = raw
    steps = _as_str_list(practice.get("steps") or practice.get("tasks") or practice.get("workflow"))
    if len(steps) < 3:
        raise LLMResponseError("课堂包 JSON practice.steps 至少需要 3 条")
    criteria = _as_str_list(practice.get("acceptance_criteria") or practice.get("criteria"))
    if len(criteria) < 2:
        raise LLMResponseError("课堂包 JSON practice.acceptance_criteria 至少需要 2 条")
    return {
        "title": _require_text(practice.get("title") or practice.get("name"), "classroom.practice.title"),
        "steps": steps[:8],
        "expected_artifact": _require_text(practice.get("expected_artifact") or practice.get("artifact"), "classroom.practice.expected_artifact"),
        "acceptance_criteria": criteria[:6],
    }


def _normalize_concept_card(raw: Any, item: LearningSyllabusItem) -> dict:
    if not isinstance(raw, dict):
        raise LLMResponseError("课堂包 JSON concept_cards[] 必须是对象")
    value = raw
    name = _require_text(value.get("name") or value.get("title"), "classroom.concept_cards[].name")
    return {
        "name": name,
        "explanation": _require_text(value.get("explanation") or value.get("description"), "classroom.concept_cards[].explanation"),
        "scenario": _require_text(value.get("scenario") or value.get("use_case"), "classroom.concept_cards[].scenario"),
        "misconception": _require_text(value.get("misconception") or value.get("pitfall"), "classroom.concept_cards[].misconception"),
        "relation_to_project": _require_text(value.get("relation_to_project") or value.get("project_relation"), "classroom.concept_cards[].relation_to_project"),
    }


def _normalize_diagram(raw: Any, item: LearningSyllabusItem) -> dict:
    if not isinstance(raw, dict):
        raise LLMResponseError("课堂包 JSON diagram 必须是对象")
    value = raw
    mermaid = _require_text(value.get("mermaid") or value.get("source"), "classroom.diagram.mermaid")
    return {
        "title": _require_text(value.get("title"), "classroom.diagram.title"),
        "diagram_type": _require_text(value.get("diagram_type") or value.get("type"), "classroom.diagram.diagram_type"),
        "mermaid": mermaid,
        "explanation": _require_text(value.get("explanation"), "classroom.diagram.explanation"),
    }


def _normalize_voice_script(raw: Any, item: LearningSyllabusItem) -> dict:
    if not isinstance(raw, dict):
        raise LLMResponseError("课堂包 JSON voice_script 必须是对象")
    value = raw
    segments = _as_str_list(value.get("segments"))
    if not segments:
        raise LLMResponseError("课堂包 JSON voice_script.segments 至少需要 1 条")
    return {
        "one_minute": _require_text(value.get("one_minute"), "classroom.voice_script.one_minute"),
        "five_minutes": _require_text(value.get("five_minutes"), "classroom.voice_script.five_minutes"),
        "segments": segments[:8],
    }


def _normalize_reproduction_demo(raw: Any, item: LearningSyllabusItem) -> dict:
    if not isinstance(raw, dict):
        raise LLMResponseError("课堂包 JSON reproduction_demo 必须是对象")
    value = raw
    steps = _as_str_list(value.get("steps"))
    if not steps:
        raise LLMResponseError("课堂包 JSON reproduction_demo.steps 至少需要 1 条")
    parameters = _as_str_list(value.get("parameters"))
    if not parameters:
        raise LLMResponseError("课堂包 JSON reproduction_demo.parameters 至少需要 1 条")
    common_errors = _as_str_list(value.get("common_errors") or value.get("errors"))
    if not common_errors:
        raise LLMResponseError("课堂包 JSON reproduction_demo.common_errors 至少需要 1 条")
    report_suggestions = _as_str_list(value.get("report_suggestions") or value.get("report"))
    if not report_suggestions:
        raise LLMResponseError("课堂包 JSON reproduction_demo.report_suggestions 至少需要 1 条")
    return {
        "title": _require_text(value.get("title") or value.get("name"), "classroom.reproduction_demo.title"),
        "task": _require_text(value.get("task"), "classroom.reproduction_demo.task"),
        "input_format": _require_text(value.get("input_format"), "classroom.reproduction_demo.input_format"),
        "code_skeleton": str(value.get("code_skeleton") or value.get("code") or ""),
        "steps": steps[:8],
        "expected_output": _require_text(value.get("expected_output"), "classroom.reproduction_demo.expected_output"),
        "parameters": parameters[:8],
        "common_errors": common_errors[:8],
        "report_suggestions": report_suggestions[:8],
    }


def _normalize_guiding_question(raw: Any, item: LearningSyllabusItem) -> dict:
    if not isinstance(raw, dict):
        raise LLMResponseError("课堂包 JSON guiding_questions[] 必须是对象")
    value = raw
    return {
        "prompt": _require_text(value.get("prompt") or value.get("question"), "classroom.guiding_questions[].prompt"),
        "intent": _require_text(value.get("intent"), "classroom.guiding_questions[].intent"),
        "hint": _require_text(value.get("hint"), "classroom.guiding_questions[].hint"),
    }


def _normalize_reading(raw: Any, item: LearningSyllabusItem) -> dict:
    if not isinstance(raw, dict):
        raise LLMResponseError("课堂包 JSON readings[] 必须是对象")
    value = raw
    keywords = _as_str_list(value.get("keywords"))
    if not keywords:
        raise LLMResponseError("课堂包 JSON readings[].keywords 至少需要 1 条")
    return {
        "title": _require_text(value.get("title"), "classroom.readings[].title"),
        "why": _require_text(value.get("why") or value.get("reason"), "classroom.readings[].why"),
        "source": _require_text(value.get("source") or value.get("uri"), "classroom.readings[].source"),
        "keywords": keywords[:8],
    }


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


def _require_text(value: Any, field_path: str) -> str:
    texts = _as_str_list(value)
    if not texts:
        raise LLMResponseError(f"模型 JSON 缺少必填字段 {field_path}")
    return texts[0]
