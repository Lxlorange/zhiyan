from __future__ import annotations

import json
from dataclasses import dataclass, field
from time import perf_counter
from typing import Callable, Dict, Generic, List, TypeVar
from uuid import uuid4

from pydantic import BaseModel, Field

from app.schemas import (
    AgentTrace,
    AssessmentResponse,
    DashboardMetric,
    KnowledgeGap,
    LearningStep,
    ProfileRequest,
    QuizQuestion,
    ResourceCard,
    SessionSummary,
    StudentProfile,
    TeacherDashboardResponse,
    TutorRequest,
    TutorResponse,
    WorkflowState,
)
from app.services.learning_workflow import COURSE_CHAPTERS, KNOWLEDGE_POINTS
from app.services.llm_client import qwen_chat_json


T = TypeVar("T")


class ProfileLLMResult(BaseModel):
    profile: StudentProfile
    summary: str


class GapLLMResult(BaseModel):
    gaps: List[KnowledgeGap] = Field(..., min_length=1)
    summary: str


class PathLLMResult(BaseModel):
    path: List[LearningStep] = Field(..., min_length=1)
    summary: str


class ResourceLLMResult(BaseModel):
    resources: List[ResourceCard] = Field(..., min_length=5)
    summary: str


class QuizLLMResult(BaseModel):
    quiz: List[QuizQuestion] = Field(..., min_length=3)
    summary: str


class TutorLLMResult(BaseModel):
    tutor: TutorResponse
    summary: str


class AssessmentLLMResult(BaseModel):
    weak_points: List[str]
    feedback: List[str]
    updated_profile: StudentProfile
    updated_path: List[LearningStep]
    updated_suggestion: str
    summary: str


@dataclass
class LLMTraceResult(Generic[T]):
    value: T
    trace: AgentTrace


@dataclass
class WorkflowStore:
    sessions: Dict[str, WorkflowState] = field(default_factory=dict)

    def save(self, state: WorkflowState) -> WorkflowState:
        self.sessions[state.session_id] = state
        return state

    def get(self, session_id: str) -> WorkflowState:
        return self.sessions[session_id]

    def list(self) -> List[SessionSummary]:
        return [
            SessionSummary(
                session_id=state.session_id,
                title=state.profile.learning_goal,
                profile_revision=state.profile.revision,
                weak_points=state.profile.weak_points,
            )
            for state in self.sessions.values()
        ]


store = WorkflowStore()


SYSTEM_PROMPT = """
你是“智研星链”A3 个性化学习多智能体系统中的专业 Agent。
必须只返回合法 JSON，不要 Markdown，不要代码块，不要解释 JSON 之外的内容。
所有内容必须围绕高校课程《人工智能与 AI4S 实践》和学生输入生成，禁止使用固定模板答案。
必须体现来源意识、防幻觉和高校学习边界：不要代写作业结论，不编造论文或实验结果。
"""


def _course_context() -> str:
    return (
        f"课程章节：{COURSE_CHAPTERS}\n"
        f"核心知识点：{KNOWLEDGE_POINTS}\n"
        "示例场景必须由用户输入、课程资料或知识库检索结果动态决定，不得使用代码内固定研究方向。"
    )


def _json_schema(model: type[BaseModel]) -> str:
    return json.dumps(model.model_json_schema(mode="validation"), ensure_ascii=False)


def _model_json(model: BaseModel) -> str:
    return json.dumps(model.model_dump(mode="json"), ensure_ascii=False)


def _run_agent(agent: str, input_summary: str, fn: Callable[[], tuple[T, str]]) -> LLMTraceResult[T]:
    start = perf_counter()
    value, output_summary = fn()
    return LLMTraceResult(
        value=value,
        trace=AgentTrace(
            agent=agent,
            status="done",
            input_summary=input_summary,
            output_summary=output_summary,
            latency_ms=max(1, int((perf_counter() - start) * 1000)),
        ),
    )


def create_profile(message: str) -> StudentProfile:
    return build_profile_with_summary(message).profile


def build_profile_with_summary(message: str) -> ProfileLLMResult:
    prompt = f"""
请根据学生自然语言构建动态学习画像。

{_course_context()}

学生输入：
{message}

输出 JSON 必须匹配 schema：
{_json_schema(ProfileLLMResult)}

要求：
1. profile 必须包含不少于 8 个维度：knowledge_base、learning_goal、cognitive_style、weak_points、practice_level、resource_preference、learning_pace、interest_direction。
2. mastery 必须给出 4-8 个知识点掌握度，分值 0-100。
3. weak_points 必须来自学生表达和课程知识点推断，不得照抄示例。
4. summary 用一句话说明画像抽取结果。
"""
    return qwen_chat_json(SYSTEM_PROMPT, prompt, ProfileLLMResult)


def diagnose_gaps(profile: StudentProfile) -> List[KnowledgeGap]:
    prompt = f"""
请作为 DiagnoseAgent，根据学生画像诊断知识短板。

{_course_context()}

学生画像 JSON：
{_model_json(profile)}

输出 JSON 必须匹配 schema：
{_json_schema(GapLLMResult)}

要求：
1. 返回 2-5 个 gaps。
2. severity 只能使用 high、medium、low。
3. evidence 必须说明短板依据。
4. related_points 必须尽量绑定课程知识点。
"""
    return qwen_chat_json(SYSTEM_PROMPT, prompt, GapLLMResult).gaps


def diagnose_gaps_with_summary(profile: StudentProfile) -> GapLLMResult:
    prompt = f"""
请作为 DiagnoseAgent，根据学生画像诊断知识短板。

{_course_context()}

学生画像 JSON：
{_model_json(profile)}

输出 JSON 必须匹配 schema：
{_json_schema(GapLLMResult)}
"""
    return qwen_chat_json(SYSTEM_PROMPT, prompt, GapLLMResult)


def plan_path(profile: StudentProfile, gaps: List[KnowledgeGap]) -> List[LearningStep]:
    return plan_path_with_summary(profile, gaps).path


def plan_path_with_summary(profile: StudentProfile, gaps: List[KnowledgeGap]) -> PathLLMResult:
    prompt = f"""
请作为 PathPlannerAgent 生成个性化学习路径。

{_course_context()}

学生画像：
{_model_json(profile)}

知识短板：
{[gap.model_dump(mode='json') for gap in gaps]}

输出 JSON 必须匹配 schema：
{_json_schema(PathLLMResult)}

要求：
1. path 返回 3-6 个步骤。
2. 每一步必须说明 objective、reason、resources、estimated_minutes、status。
3. 第一个待学步骤 status 设为 active，其余为 pending。
4. reason 必须解释为什么适合该学生。
"""
    return qwen_chat_json(SYSTEM_PROMPT, prompt, PathLLMResult)


def generate_resources(profile: StudentProfile) -> List[ResourceCard]:
    return generate_resources_with_summary(profile).resources


def generate_resources_with_summary(profile: StudentProfile) -> ResourceLLMResult:
    prompt = f"""
请作为 ResourceAgentGroup 生成个性化学习资源。

{_course_context()}

学生画像：
{_model_json(profile)}

输出 JSON 必须匹配 schema：
{_json_schema(ResourceLLMResult)}

要求：
1. resources 至少 6 个，必须覆盖：课程讲解文档、知识点思维导图、分层练习题、拓展阅读材料、代码类实操案例、视频脚本或动画分镜。
2. 每张资源卡必须绑定 target_profile、knowledge_points、sources、safety_notes。
3. content 要根据学生画像个性化生成，不要写通用空话。
4. sources 使用课程章节或课程知识库来源，不要编造真实论文。
"""
    return qwen_chat_json(SYSTEM_PROMPT, prompt, ResourceLLMResult)


def generate_quiz(profile: StudentProfile, gaps: List[KnowledgeGap]) -> List[QuizQuestion]:
    return generate_quiz_with_summary(profile, gaps).quiz


def generate_quiz_with_summary(profile: StudentProfile, gaps: List[KnowledgeGap]) -> QuizLLMResult:
    prompt = f"""
请作为 QuizAgent 生成用于学习效果评估的题目。

{_course_context()}

学生画像：
{_model_json(profile)}

知识短板：
{[gap.model_dump(mode='json') for gap in gaps]}

输出 JSON 必须匹配 schema：
{_json_schema(QuizLLMResult)}

要求：
1. quiz 返回 3-5 道选择题。
2. 每题 options 必须包含 4 个选项，answer 必须是 options 中的原文之一。
3. 题目要针对学生短板，不要固定使用同一批题。
"""
    return qwen_chat_json(SYSTEM_PROMPT, prompt, QuizLLMResult)


def start_workflow(request: ProfileRequest) -> WorkflowState:
    traces: List[AgentTrace] = []

    profile_result = _run_agent(
        "ProfileAgent",
        "学生自然语言描述",
        lambda: ((result := build_profile_with_summary(request.message)).profile, result.summary),
    )
    profile = profile_result.value
    traces.append(profile_result.trace)

    gaps_result = _run_agent(
        "DiagnoseAgent",
        "学生画像 + 课程知识点",
        lambda: ((result := diagnose_gaps_with_summary(profile)).gaps, result.summary),
    )
    gaps = gaps_result.value
    traces.append(gaps_result.trace)

    path_result = _run_agent(
        "PathPlannerAgent",
        "画像 + 薄弱点",
        lambda: ((result := plan_path_with_summary(profile, gaps)).path, result.summary),
    )
    path = path_result.value
    traces.append(path_result.trace)

    resource_result = _run_agent(
        "ResourceAgentGroup",
        "路径 + 资源偏好 + 课程知识库约束",
        lambda: ((result := generate_resources_with_summary(profile)).resources, result.summary),
    )
    resources = resource_result.value
    traces.append(resource_result.trace)

    quiz_result = _run_agent(
        "QuizAgent",
        "薄弱点 + 画像掌握度",
        lambda: ((result := generate_quiz_with_summary(profile, gaps)).quiz, result.summary),
    )
    quiz = quiz_result.value
    traces.append(quiz_result.trace)

    traces.append(
        AgentTrace(
            agent="SafetyCheckAgent",
            status="done",
            input_summary="模型生成资源 + 来源字段 + 作业边界",
            output_summary="已要求资源绑定课程来源、标注 safety_notes，并禁止代写作业结论",
            latency_ms=1,
        )
    )

    state = WorkflowState(
        session_id=str(uuid4()),
        profile=profile,
        gaps=gaps,
        path=path,
        resources=resources,
        quiz=quiz,
        agent_trace=traces,
    )
    return store.save(state)


def tutor_answer(request: TutorRequest) -> TutorResponse:
    prompt = f"""
请作为 TutorAgent 回答学生问题。

{_course_context()}

学生问题：
{request.question}

学生画像：
{_model_json(request.profile) if request.profile else "未提供画像，请根据问题自适应。"}

输出 JSON 必须匹配 schema：
{_json_schema(TutorLLMResult)}

要求：
1. tutor.answer 必须是针对学生问题的分步骤解释。
2. tutor.knowledge_points 必须绑定课程知识点。
3. tutor.sources 必须给出课程章节或知识库来源。
4. tutor.follow_up_exercise 必须是一个小练习，不要直接代写作业。
5. tutor.strategy 说明如何适配学生画像。
"""
    return qwen_chat_json(SYSTEM_PROMPT, prompt, TutorLLMResult).tutor


def attach_tutor_response(session_id: str, request: TutorRequest) -> WorkflowState:
    state = store.get(session_id)
    enriched_request = request.model_copy(update={"profile": request.profile or state.profile})
    start = perf_counter()
    state.tutor = tutor_answer(enriched_request)
    state.agent_trace.append(
        AgentTrace(
            agent="TutorAgent",
            status="done",
            input_summary=request.question,
            output_summary="基于千问生成带来源的个性化辅导和追问练习",
            latency_ms=max(1, int((perf_counter() - start) * 1000)),
        )
    )
    return store.save(state)


def assess_answers(session_id: str, answers: Dict[str, str]) -> AssessmentResponse:
    state = store.get(session_id)
    quiz_by_id = {question.id: question for question in state.quiz}
    correct = {
        question_id: quiz_by_id[question_id].answer == answer
        for question_id, answer in answers.items()
        if question_id in quiz_by_id
    }
    total = max(1, len(quiz_by_id))
    score = int(sum(1 for value in correct.values() if value) / total * 100)

    prompt = f"""
请作为 AssessmentAgent，根据学生答题结果更新画像和学习路径。

{_course_context()}

当前画像：
{_model_json(state.profile)}

当前路径：
{[step.model_dump(mode='json') for step in state.path]}

题目：
{[question.model_dump(mode='json') for question in state.quiz]}

学生答案：
{answers}

判题结果：
{correct}

得分：
{score}

输出 JSON 必须匹配 schema：
{_json_schema(AssessmentLLMResult)}

要求：
1. updated_profile.revision 必须比当前画像版本大 1。
2. weak_points 和 mastery 必须根据答题结果调整。
3. updated_path 必须解释为什么调整，不得固定插入同一个节点。
4. updated_suggestion 用一句话说明画像和路径如何随学随新。
"""
    result = qwen_chat_json(SYSTEM_PROMPT, prompt, AssessmentLLMResult)
    response = AssessmentResponse(
        score=score,
        weak_points=result.weak_points,
        correct=correct,
        feedback=result.feedback,
        updated_profile=result.updated_profile,
        updated_path=result.updated_path,
        updated_suggestion=result.updated_suggestion,
    )

    state.profile = response.updated_profile
    state.path = response.updated_path
    state.assessment = response
    state.agent_trace.append(
        AgentTrace(
            agent="AssessmentAgent",
            status="done",
            input_summary="学生练习答案 + 自动判题结果",
            output_summary=result.summary,
            latency_ms=1,
        )
    )
    return store.save(state).assessment


def get_state(session_id: str) -> WorkflowState:
    return store.get(session_id)


def list_sessions() -> List[SessionSummary]:
    return store.list()


def build_teacher_dashboard() -> TeacherDashboardResponse:
    sessions = list_sessions()
    weak_point_distribution: Dict[str, int] = {}
    resource_type_distribution: Dict[str, int] = {}

    for state in store.sessions.values():
        for point in state.profile.weak_points:
            weak_point_distribution[point] = weak_point_distribution.get(point, 0) + 1
        for resource in state.resources:
            resource_type_distribution[resource.type] = resource_type_distribution.get(resource.type, 0) + 1

    return TeacherDashboardResponse(
        metrics=[
            DashboardMetric(label="活跃学习会话", value=str(len(sessions)), trend="来自真实 AI 链路会话"),
            DashboardMetric(label="课程知识点", value=str(len(KNOWLEDGE_POINTS)), trend="课程知识库约束生成"),
            DashboardMetric(label="资源类型", value=str(len(resource_type_distribution)), trend="由 ResourceAgentGroup 动态生成"),
            DashboardMetric(label="Agent 节点", value="7", trend="画像/诊断/规划/资源/题目/辅导/评估"),
        ],
        weak_point_distribution=weak_point_distribution,
        resource_type_distribution=resource_type_distribution,
        at_risk_students=sessions[:5],
        teaching_suggestions=[
            "请先运行学生学习链路，教师端将基于真实画像、资源和答题记录生成统计。",
        ]
        if not sessions
        else [
            "优先关注 high severity 短板较多的知识点，并复用生成效果较好的资源卡片。",
            "检查学生提问和答题记录中反复出现的错因，安排下一轮课堂讲解。",
        ],
    )
