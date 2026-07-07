from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter
from typing import Callable, Dict, List
from uuid import uuid4

from app.schemas import (
    AgentTrace,
    AssessmentResponse,
    KnowledgeGap,
    LearningStep,
    ProfileRequest,
    QuizQuestion,
    ResourceCard,
    SessionSummary,
    StudentProfile,
    TeacherDashboardResponse,
    DashboardMetric,
    TutorRequest,
    TutorResponse,
    WorkflowState,
)


COURSE_CHAPTERS = [
    "人工智能与 AI4S 概论",
    "Python 数据处理基础",
    "机器学习分类任务",
    "深度学习基础",
    "信号处理与无线感知入门",
    "WiFi CSI 跌倒检测案例",
    "实验评价指标与结果分析",
    "课程项目报告与展示规范",
]

KNOWLEDGE_POINTS = [
    "混淆矩阵",
    "准确率",
    "召回率",
    "F1 值",
    "类别不平衡",
    "CSI 特征",
    "数据集划分",
    "Python 指标计算",
    "实验报告规范",
]


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


def _trace(agent: str, input_summary: str, fn: Callable[[], str]) -> AgentTrace:
    start = perf_counter()
    output_summary = fn()
    latency_ms = max(1, int((perf_counter() - start) * 1000))
    return AgentTrace(
        agent=agent,
        status="done",
        input_summary=input_summary,
        output_summary=output_summary,
        latency_ms=latency_ms,
    )


def create_profile(message: str) -> StudentProfile:
    weak_points = ["混淆矩阵", "召回率与准确率", "数据集划分", "CSI 特征理解"]
    resource_preference = ["讲解文档", "思维导图", "分层练习", "代码案例", "论文导读"]
    cognitive_style = "案例驱动 + 图解说明 + 代码实践"
    practice_level = "Python 基础一般，能阅读简单代码"

    if "视频" in message or "动画" in message:
        resource_preference.append("视频脚本")
        cognitive_style = "图解说明 + 视频脚本 + 案例驱动"
    if "熟悉" in message or "项目" in message:
        practice_level = "具备基础项目实践经验，需要强化实验设计"
    if "公式" in message or "数学" in message:
        weak_points.append("指标公式理解")

    return StudentProfile(
        knowledge_base="具备计算机专业基础，机器学习和信号处理知识不系统",
        learning_goal="完成 AI4S 课程项目并理解 WiFi CSI 跌倒检测案例",
        cognitive_style=cognitive_style,
        weak_points=weak_points,
        practice_level=practice_level,
        resource_preference=resource_preference,
        learning_pace="每周 6-8 小时，适合短路径分阶段推进",
        interest_direction="无线感知与智慧健康 AI4S 应用",
        mastery={
            "混淆矩阵": 35,
            "召回率": 40,
            "准确率": 55,
            "数据集划分": 42,
            "CSI 特征": 38,
            "Python 指标计算": 58,
        },
    )


def diagnose_gaps(profile: StudentProfile) -> List[KnowledgeGap]:
    return [
        KnowledgeGap(
            id="gap-matrix",
            title="混淆矩阵概念不稳定",
            severity="high",
            evidence="学生同时提到召回率、准确率和混淆矩阵困惑，说明 TP/FP/FN/TN 关系未建立。",
            related_points=["混淆矩阵", "准确率", "召回率"],
        ),
        KnowledgeGap(
            id="gap-split",
            title="数据集划分与实验可信度不足",
            severity="medium",
            evidence="学生目标是课程项目，但未说明训练集、验证集、测试集和场景泛化策略。",
            related_points=["数据集划分", "实验评价指标"],
        ),
        KnowledgeGap(
            id="gap-csi",
            title="CSI 特征与应用场景连接较弱",
            severity="medium",
            evidence="学生关注 WiFi CSI 跌倒检测，但缺少 CSI 振幅/相位与人体活动的关系理解。",
            related_points=["CSI 特征", "无线感知", "人体活动识别"],
        ),
    ]


def plan_path(profile: StudentProfile, gaps: List[KnowledgeGap]) -> List[LearningStep]:
    return [
        LearningStep(
            id="step-eval",
            title="补齐分类任务与评价指标",
            objective="能用混淆矩阵解释准确率、召回率和 F1 值",
            reason=f"当前画像中 {gaps[0].title}，先补指标能降低后续实验理解成本。",
            resources=["res-doc", "res-mindmap", "res-quiz"],
            estimated_minutes=45,
            status="active",
        ),
        LearningStep(
            id="step-csi",
            title="理解 WiFi CSI 数据与人体活动识别",
            objective="能解释 CSI 特征为什么可用于跌倒检测",
            reason="项目兴趣集中在无线感知，需要先建立 CSI 特征和场景约束的基本认识。",
            resources=["res-reading", "res-video"],
            estimated_minutes=50,
        ),
        LearningStep(
            id="step-code",
            title="完成跌倒检测评价指标代码实操",
            objective="能用 Python 计算并解释评价指标",
            reason=f"画像显示学生偏好 {profile.cognitive_style}，代码实践能连接概念和实验结果。",
            resources=["res-code"],
            estimated_minutes=80,
        ),
        LearningStep(
            id="step-report",
            title="整理课程项目报告检查清单",
            objective="能把学习结果转化为课程项目材料",
            reason="A3 演示需要体现资源生成后能进入真实学习任务，而不是停留在问答。",
            resources=["res-project"],
            estimated_minutes=35,
        ),
    ]


def generate_resources(profile: StudentProfile) -> List[ResourceCard]:
    return [
        ResourceCard(
            id="res-doc",
            type="课程讲解文档",
            title="召回率、准确率与跌倒检测风险",
            target_profile=profile.cognitive_style,
            knowledge_points=["混淆矩阵", "召回率", "准确率"],
            content="用宿舍跌倒检测场景解释漏检风险，强调召回率在安全预警任务中的意义。",
            format_hint="Markdown 讲义",
            sources=["第 7 章 实验评价指标与结果分析"],
            safety_notes=["不替学生生成可直接提交的实验结论"],
        ),
        ResourceCard(
            id="res-mindmap",
            type="知识点思维导图",
            title="分类评价指标知识图谱",
            target_profile="偏图解理解的学生",
            knowledge_points=["TP/FP/FN/TN", "Precision", "Recall", "F1"],
            content="graph TD; A[混淆矩阵]-->B[准确率]; A-->C[召回率]; A-->D[精确率]; C-->E[安全预警漏检风险];",
            format_hint="Mermaid",
            sources=["第 3 章 机器学习分类任务"],
        ),
        ResourceCard(
            id="res-quiz",
            type="分层练习题",
            title="混淆矩阵专项练习",
            target_profile="存在概念混淆的学生",
            knowledge_points=["混淆矩阵", "错因分析"],
            content="包含 3 道基础题、2 道应用题和 1 道项目思考题，答题后触发画像更新。",
            format_hint="交互题卡",
            sources=["课程题库：评价指标专项"],
        ),
        ResourceCard(
            id="res-reading",
            type="拓展阅读材料",
            title="WiFi CSI 人体活动识别论文导读",
            target_profile="希望从课程学习过渡到科研入门的学生",
            knowledge_points=["CSI", "人体活动识别", "无线感知"],
            content="整理问题背景、常见模型、数据采集难点和可复现实验建议。",
            format_hint="论文导读卡",
            sources=["第 6 章 WiFi CSI 跌倒检测案例"],
        ),
        ResourceCard(
            id="res-code",
            type="代码类实操案例",
            title="跌倒检测评价指标 Python 代码骨架",
            target_profile=profile.practice_level,
            knowledge_points=["Python 实践", "指标计算", "实验复现"],
            content="提供 y_true/y_pred 输入、混淆矩阵计算和指标输出的代码骨架。",
            format_hint="Python snippet",
            sources=["第 2 章 Python 数据处理基础", "第 7 章 实验评价指标与结果分析"],
        ),
        ResourceCard(
            id="res-video",
            type="多模态教学视频脚本",
            title="为什么跌倒检测更怕漏检",
            target_profile="偏视频和案例说明的学生",
            knowledge_points=["召回率", "应用风险", "智慧健康"],
            content="30 秒动画分镜：正常活动、跌倒样本、漏检后果、指标选择。",
            format_hint="视频脚本/动画分镜",
            sources=["第 6 章 WiFi CSI 跌倒检测案例"],
        ),
        ResourceCard(
            id="res-project",
            type="课程项目学习材料",
            title="WiFi CSI 跌倒检测实验报告检查清单",
            target_profile="目标为课程项目的学生",
            knowledge_points=["实验报告规范", "数据集划分", "评价指标"],
            content="检查背景、数据、方法、指标、对比实验、局限性和引用来源是否完整。",
            format_hint="Checklist",
            sources=["第 8 章 课程项目报告与展示规范"],
            safety_notes=["只做结构审阅和依据提示，不代写报告正文"],
        ),
    ]


def generate_quiz() -> List[QuizQuestion]:
    return [
        QuizQuestion(
            id="q1",
            prompt="真实跌倒 10 次，模型识别出 8 次。召回率是多少？",
            options=["60%", "70%", "80%", "90%"],
            answer="80%",
            knowledge_point="召回率",
        ),
        QuizQuestion(
            id="q2",
            prompt="正常活动样本远多于跌倒样本时，只看准确率最大的风险是什么？",
            options=["训练更快", "可能掩盖跌倒漏检", "一定过拟合", "无法计算混淆矩阵"],
            answer="可能掩盖跌倒漏检",
            knowledge_point="类别不平衡",
        ),
        QuizQuestion(
            id="q3",
            prompt="课程项目中测试集的主要作用是什么？",
            options=["调参", "最终评估泛化能力", "替代训练集", "生成报告标题"],
            answer="最终评估泛化能力",
            knowledge_point="数据集划分",
        ),
    ]


def start_workflow(request: ProfileRequest) -> WorkflowState:
    traces: List[AgentTrace] = []

    profile_box: Dict[str, StudentProfile] = {}
    traces.append(_trace("ProfileAgent", "学生自然语言描述", lambda: _set_profile(profile_box, request.message)))
    profile = profile_box["value"]

    gaps_box: Dict[str, List[KnowledgeGap]] = {}
    traces.append(_trace("DiagnoseAgent", "学生画像 + 课程知识点", lambda: _set_gaps(gaps_box, profile)))
    gaps = gaps_box["value"]

    path_box: Dict[str, List[LearningStep]] = {}
    traces.append(_trace("PathPlannerAgent", "画像 + 薄弱点", lambda: _set_path(path_box, profile, gaps)))
    path = path_box["value"]

    resources_box: Dict[str, List[ResourceCard]] = {}
    traces.append(_trace("ResourceAgentGroup", "路径 + 资源偏好", lambda: _set_resources(resources_box, profile)))
    resources = resources_box["value"]

    quiz_box: Dict[str, List[QuizQuestion]] = {}
    traces.append(_trace("QuizAgent", "薄弱点 + 评价指标章节", lambda: _set_quiz(quiz_box)))
    quiz = quiz_box["value"]

    traces.append(
        AgentTrace(
            agent="SafetyCheckAgent",
            status="done",
            input_summary="资源卡片 + 来源材料",
            output_summary="已标注来源、作业边界和低风险资源类型",
            latency_ms=12,
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


def _set_profile(target: Dict[str, StudentProfile], message: str) -> str:
    target["value"] = create_profile(message)
    return "生成 8 维学习画像和初始掌握度"


def _set_gaps(target: Dict[str, List[KnowledgeGap]], profile: StudentProfile) -> str:
    target["value"] = diagnose_gaps(profile)
    return "识别混淆矩阵、数据集划分、CSI 特征 3 类短板"


def _set_path(target: Dict[str, List[LearningStep]], profile: StudentProfile, gaps: List[KnowledgeGap]) -> str:
    target["value"] = plan_path(profile, gaps)
    return "规划 4 步个性化学习路径"


def _set_resources(target: Dict[str, List[ResourceCard]], profile: StudentProfile) -> str:
    target["value"] = generate_resources(profile)
    return "生成 7 类个性化资源卡片"


def _set_quiz(target: Dict[str, List[QuizQuestion]]) -> str:
    target["value"] = generate_quiz()
    return "生成 3 道诊断练习题"


def tutor_answer(request: TutorRequest) -> TutorResponse:
    strategy = "基于课程知识库的场景化解释"
    if request.profile and "视频脚本" in request.profile.resource_preference:
        strategy = "先给结论，再给可转成动画分镜的例子"

    return TutorResponse(
        answer=(
            "在跌倒检测这类安全预警任务中，漏检一次真实跌倒的代价通常高于误报。"
            "准确率会受到正常样本数量影响，当正常活动远多于跌倒样本时，模型即使漏掉不少跌倒也可能保持较高准确率。"
            "召回率直接衡量真实跌倒中有多少被识别出来，因此更能反映安全场景的核心风险。"
        ),
        knowledge_points=["召回率", "准确率", "混淆矩阵", "类别不平衡"],
        sources=["第 7 章 实验评价指标与结果分析", "第 6 章 WiFi CSI 跌倒检测案例"],
        follow_up_exercise="给定 10 次真实跌倒中模型识别出 8 次、误报 3 次，计算召回率并解释它的含义。",
        strategy=strategy,
    )


def attach_tutor_response(session_id: str, request: TutorRequest) -> WorkflowState:
    state = store.get(session_id)
    state.tutor = tutor_answer(request)
    state.agent_trace.append(
        AgentTrace(
            agent="TutorAgent",
            status="done",
            input_summary=request.question,
            output_summary="生成带来源的场景化辅导和追问练习",
            latency_ms=18,
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

    weak_points = ["类别不平衡下准确率的局限", "F1 值使用场景"]
    if not correct.get("q3", False):
        weak_points.append("训练集/验证集/测试集职责")

    updated_profile = state.profile.copy(deep=True)
    updated_profile.revision += 1
    updated_profile.weak_points = weak_points
    updated_profile.mastery["召回率"] = 72 if correct.get("q1", False) else 48
    updated_profile.mastery["类别不平衡"] = 68 if correct.get("q2", False) else 35
    updated_profile.mastery["数据集划分"] = 70 if correct.get("q3", False) else 40

    updated_path = plan_path(updated_profile, diagnose_gaps(updated_profile))
    updated_path.insert(
        1,
        LearningStep(
            id="step-remedial",
            title="补救：类别不平衡与 F1 值专项",
            objective="能说明为什么类别不平衡时不能只看准确率",
            reason="评估结果显示学生仍需要理解准确率局限和 F1 值使用场景。",
            resources=["res-doc", "res-quiz"],
            estimated_minutes=25,
            status="active",
        ),
    )

    response = AssessmentResponse(
        score=score,
        weak_points=weak_points,
        correct=correct,
        feedback=[
            "召回率题目用于检查是否理解漏检风险。",
            "类别不平衡题目用于检查是否能识别准确率陷阱。",
            "数据集划分题目用于检查实验可信度意识。",
        ],
        updated_profile=updated_profile,
        updated_path=updated_path,
        updated_suggestion="下一轮学习路径已插入类别不平衡与 F1 值专项补救节点。",
    )

    state.profile = updated_profile
    state.path = updated_path
    state.assessment = response
    state.agent_trace.append(
        AgentTrace(
            agent="AssessmentAgent",
            status="done",
            input_summary="学生练习答案",
            output_summary=f"得分 {score}，画像更新到 v{updated_profile.revision}",
            latency_ms=21,
        )
    )
    store.save(state)
    return response


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

    if not sessions:
        weak_point_distribution = {
            "混淆矩阵": 3,
            "召回率与准确率": 3,
            "数据集划分": 2,
            "CSI 特征理解": 2,
        }
        resource_type_distribution = {
            "课程讲解文档": 1,
            "知识点思维导图": 1,
            "分层练习题": 1,
            "拓展阅读材料": 1,
            "代码类实操案例": 1,
            "多模态教学视频脚本": 1,
            "课程项目学习材料": 1,
        }

    return TeacherDashboardResponse(
        metrics=[
            DashboardMetric(label="活跃学习会话", value=str(max(1, len(sessions))), trend="演示环境实时生成"),
            DashboardMetric(label="课程知识点", value=str(len(KNOWLEDGE_POINTS)), trend="覆盖 8 个章节"),
            DashboardMetric(label="资源类型", value=str(len(resource_type_distribution)), trend="满足至少 5 种资源要求"),
            DashboardMetric(label="Agent 节点", value="7", trend="画像/诊断/规划/资源/辅导/评估/校验"),
        ],
        weak_point_distribution=weak_point_distribution,
        resource_type_distribution=resource_type_distribution,
        at_risk_students=sessions[:5],
        teaching_suggestions=[
            "下节课优先讲解混淆矩阵与召回率，减少学生在安全预警指标上的误用。",
            "为课程项目补充训练集、验证集、测试集划分示例，强化实验可信度。",
            "把 WiFi CSI 特征解释做成图解卡片，帮助学生从信号数据过渡到 AI4S 应用。",
        ],
    )
