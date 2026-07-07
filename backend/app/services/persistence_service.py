from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.learning import (
    AgentTaskRecord,
    AnswerRecord,
    GeneratedResourceRecord,
    LearningPathRecord,
    StudentProfileRecord,
    StudentProfileVersion,
    WorkflowSessionRecord,
)
from app.models.user import User
from app.schemas import AssessmentResponse, ProfileDialogueResponse, SessionSummary, StudentProfile, WorkflowState


def _dump_model(model) -> dict:
    return model.model_dump(mode="json")


def upsert_profile_from_dialogue(
    db: Session,
    user: User,
    profile: StudentProfile,
    update_reason: str,
    extracted_features: dict,
    source: str = "dialogue",
) -> StudentProfileRecord:
    current = db.scalar(select(StudentProfileRecord).where(StudentProfileRecord.user_id == user.id))
    profile_data = _dump_model(profile)
    if current is None:
        current = StudentProfileRecord(
            user_id=user.id,
            current_revision=profile.revision,
            profile_data=profile_data,
        )
        db.add(current)
        db.flush()
    else:
        current.current_revision = max(current.current_revision + 1, profile.revision)
        profile.revision = current.current_revision
        profile_data = _dump_model(profile)
        current.profile_data = profile_data

    db.add(
        StudentProfileVersion(
            profile_id=current.id,
            revision=profile.revision,
            source=source,
            update_reason=update_reason,
            extracted_features=extracted_features,
            profile_data=profile_data,
        )
    )
    db.commit()
    db.refresh(current)
    return current


def build_profile_dialogue_response(
    db: Session,
    user: User,
    profile: StudentProfile,
    update_reason: str,
    extracted_features: dict,
) -> ProfileDialogueResponse:
    record = upsert_profile_from_dialogue(
        db=db,
        user=user,
        profile=profile,
        update_reason=update_reason,
        extracted_features=extracted_features,
    )
    return ProfileDialogueResponse(
        profile_id=record.id,
        profile=StudentProfile(**record.profile_data),
        update_reason=update_reason,
        extracted_features=extracted_features,
        revision=record.current_revision,
    )


def persist_workflow_state(db: Session, user: User, state: WorkflowState) -> None:
    profile_record = upsert_profile_from_dialogue(
        db=db,
        user=user,
        profile=state.profile,
        update_reason="根据学生自然语言描述生成初始学习画像，并启动学习闭环。",
        extracted_features={
            "weak_points": state.profile.weak_points,
            "resource_preference": state.profile.resource_preference,
            "mastery": state.profile.mastery,
        },
        source="workflow",
    )

    state_data = _dump_model(state)
    session = db.scalar(select(WorkflowSessionRecord).where(WorkflowSessionRecord.session_id == state.session_id))
    if session is None:
        session = WorkflowSessionRecord(
            session_id=state.session_id,
            user_id=user.id,
            profile_id=profile_record.id,
            title=state.profile.learning_goal,
            state_data=state_data,
        )
        db.add(session)
    else:
        session.profile_id = profile_record.id
        session.title = state.profile.learning_goal
        session.state_data = state_data

    db.execute(delete(GeneratedResourceRecord).where(GeneratedResourceRecord.session_id == state.session_id))
    for resource in state.resources:
        db.add(
            GeneratedResourceRecord(
                session_id=state.session_id,
                user_id=user.id,
                resource_key=resource.id,
                resource_type=resource.type,
                title=resource.title,
                knowledge_points=resource.knowledge_points,
                content_data=_dump_model(resource),
                sources=resource.sources,
                safety_notes=resource.safety_notes,
            )
        )

    db.execute(delete(AgentTaskRecord).where(AgentTaskRecord.session_id == state.session_id))
    for trace in state.agent_trace:
        db.add(
            AgentTaskRecord(
                session_id=state.session_id,
                user_id=user.id,
                agent=trace.agent,
                status=trace.status,
                input_summary=trace.input_summary,
                output_summary=trace.output_summary,
                latency_ms=trace.latency_ms,
            )
        )

    db.add(
        LearningPathRecord(
            session_id=state.session_id,
            user_id=user.id,
            revision=state.profile.revision,
            reason="初始路径由画像、短板诊断和资源偏好生成。",
            steps_data=[_dump_model(step) for step in state.path],
        )
    )
    db.commit()


def persist_assessment_result(
    db: Session,
    user: User,
    state: WorkflowState,
    assessment: AssessmentResponse,
    answers: dict[str, str],
) -> None:
    quiz_by_id = {question.id: question for question in state.quiz}
    for question_id, answer in answers.items():
        question = quiz_by_id.get(question_id)
        if question is None:
            continue
        db.add(
            AnswerRecord(
                session_id=state.session_id,
                user_id=user.id,
                question_id=question_id,
                knowledge_point=question.knowledge_point,
                answer=answer,
                expected_answer=question.answer,
                is_correct=assessment.correct.get(question_id, False),
            )
        )

    upsert_profile_from_dialogue(
        db=db,
        user=user,
        profile=assessment.updated_profile,
        update_reason=assessment.updated_suggestion,
        extracted_features={
            "score": assessment.score,
            "weak_points": assessment.weak_points,
            "correct": assessment.correct,
        },
        source="assessment",
    )

    db.add(
        LearningPathRecord(
            session_id=state.session_id,
            user_id=user.id,
            revision=assessment.updated_profile.revision,
            reason=assessment.updated_suggestion,
            steps_data=[_dump_model(step) for step in assessment.updated_path],
        )
    )
    session = db.scalar(select(WorkflowSessionRecord).where(WorkflowSessionRecord.session_id == state.session_id))
    if session:
        session.state_data = _dump_model(state)
    db.commit()


def get_persisted_workflow_state(db: Session, user: User, session_id: str) -> Optional[WorkflowState]:
    session = db.scalar(
        select(WorkflowSessionRecord).where(
            WorkflowSessionRecord.session_id == session_id,
            WorkflowSessionRecord.user_id == user.id,
        )
    )
    if session is None:
        return None
    return WorkflowState(**session.state_data)


def list_persisted_sessions(db: Session, user: User) -> list[SessionSummary]:
    rows = db.scalars(
        select(WorkflowSessionRecord)
        .where(WorkflowSessionRecord.user_id == user.id)
        .order_by(WorkflowSessionRecord.updated_at.desc())
    ).all()
    summaries: list[SessionSummary] = []
    for row in rows:
        state = WorkflowState(**row.state_data)
        summaries.append(
            SessionSummary(
                session_id=row.session_id,
                title=row.title,
                profile_revision=state.profile.revision,
                weak_points=state.profile.weak_points,
            )
        )
    return summaries
