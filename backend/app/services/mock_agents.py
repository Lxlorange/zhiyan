from app.schemas import (
    AgentTrace,
    AssessmentResponse,
    DemoWorkflowResponse,
    LearningStep,
    ProfileRequest,
    ResourceCard,
    StudentProfile,
    TutorRequest,
    TutorResponse,
)


def build_profile(request: ProfileRequest) -> StudentProfile:
    text = request.message
    practice_level = "Python 基础一般，能阅读简单代码"
    if "熟悉" in text or "项目" in text:
        practice_level = "具备基础项目实践经验，需要强化实验设计"

    return StudentProfile(
        knowledge_base="具备计算机专业基础，机器学习和信号处理知识不系统",
        learning_goal="完成 AI4S 课程项目并理解 WiFi CSI 跌倒检测案例",
        cognitive_style="案例驱动 + 图解说明 + 代码实践",
        weak_points=["混淆矩阵", "召回率与准确率", "数据集划分", "CSI 特征理解"],
        practice_level=practice_level,
        resource_preference=["讲解文档", "思维导图", "分层练习", "代码案例", "论文导读"],
        learning_pace="每周 6-8 小时，适合短路径分阶段推进",
        interest_direction="无线感知与智慧健康 AI4S 应用",
    )


def run_demo_workflow(request: ProfileRequest) -> DemoWorkflowResponse:
    profile = build_profile(request)
    weak_points = profile.weak_points

    path = [
        LearningStep(
            id="step-1",
            title="补齐分类任务与评价指标",
            reason="学生对召回率、准确率和混淆矩阵存在薄弱点，先补评价指标可降低后续实验理解成本。",
            resources=["res-doc", "res-mindmap", "res-quiz"],
            estimated_minutes=45,
        ),
        LearningStep(
            id="step-2",
            title="理解 WiFi CSI 数据与人体活动识别",
            reason="项目兴趣集中在无线感知，需要先建立 CSI 特征和场景约束的基本认识。",
            resources=["res-reading", "res-video"],
            estimated_minutes=50,
        ),
        LearningStep(
            id="step-3",
            title="完成跌倒检测代码实操",
            reason="画像显示学生适合案例驱动学习，代码实践能帮助连接概念和实验结果。",
            resources=["res-code"],
            estimated_minutes=80,
        ),
    ]

    resources = [
        ResourceCard(
            id="res-doc",
            type="课程讲解文档",
            title="召回率、准确率与跌倒检测风险",
            target_profile="数学基础一般、目标为课程项目的学生",
            knowledge_points=["混淆矩阵", "召回率", "准确率"],
            content="用宿舍跌倒检测场景解释漏检风险，强调召回率在安全预警任务中的意义。",
            sources=["第 7 章 实验评价指标与结果分析"],
        ),
        ResourceCard(
            id="res-mindmap",
            type="知识点思维导图",
            title="分类评价指标知识图谱",
            target_profile="偏图解理解的学生",
            knowledge_points=["TP/FP/FN/TN", "Precision", "Recall", "F1"],
            content="以 Mermaid 结构描述评价指标之间的计算关系和使用场景。",
            sources=["第 3 章 机器学习分类任务"],
        ),
        ResourceCard(
            id="res-quiz",
            type="分层练习题",
            title="混淆矩阵专项练习",
            target_profile="存在概念混淆的学生",
            knowledge_points=["混淆矩阵", "错因分析"],
            content="包含 3 道基础题、2 道应用题和 1 道项目思考题。",
            sources=["课程题库：评价指标专项"],
        ),
        ResourceCard(
            id="res-reading",
            type="拓展阅读材料",
            title="WiFi CSI 人体活动识别论文导读",
            target_profile="希望从课程学习过渡到科研入门的学生",
            knowledge_points=["CSI", "人体活动识别", "无线感知"],
            content="整理问题背景、常见模型、数据采集难点和可复现实验建议。",
            sources=["第 6 章 WiFi CSI 跌倒检测案例"],
        ),
        ResourceCard(
            id="res-code",
            type="代码类实操案例",
            title="跌倒检测评价指标 Python 代码骨架",
            target_profile="适合通过代码理解概念的学生",
            knowledge_points=["Python 实践", "指标计算", "实验复现"],
            content="提供 y_true/y_pred 输入、混淆矩阵计算和指标输出的代码骨架。",
            sources=["第 2 章 Python 数据处理基础", "第 7 章 实验评价指标与结果分析"],
        ),
        ResourceCard(
            id="res-video",
            type="多模态教学视频脚本",
            title="为什么跌倒检测更怕漏检",
            target_profile="偏视频和案例说明的学生",
            knowledge_points=["召回率", "应用风险", "智慧健康"],
            content="30 秒动画分镜：正常活动、跌倒样本、漏检后果、指标选择。",
            sources=["第 6 章 WiFi CSI 跌倒检测案例"],
        ),
    ]

    trace = [
        AgentTrace(agent="ProfileAgent", status="done", summary="抽取 8 维学生画像", latency_ms=260),
        AgentTrace(agent="DiagnoseAgent", status="done", summary="识别 4 个薄弱知识点", latency_ms=180),
        AgentTrace(agent="PathPlannerAgent", status="done", summary="生成 3 步学习路径", latency_ms=220),
        AgentTrace(agent="ResourceAgentGroup", status="done", summary="生成 6 类资源卡片", latency_ms=740),
        AgentTrace(agent="SafetyCheckAgent", status="done", summary="校验来源和作业边界", latency_ms=130),
    ]

    return DemoWorkflowResponse(profile=profile, weak_points=weak_points, path=path, resources=resources, agent_trace=trace)


def tutor_answer(request: TutorRequest) -> TutorResponse:
    return TutorResponse(
        answer=(
            "在跌倒检测这类安全预警任务中，漏检一次真实跌倒的代价通常高于误报。"
            "准确率会受到正常样本数量影响，当正常活动远多于跌倒样本时，模型即使漏掉不少跌倒也可能保持较高准确率。"
            "召回率直接衡量真实跌倒中有多少被识别出来，因此更能反映安全场景的核心风险。"
        ),
        knowledge_points=["召回率", "准确率", "混淆矩阵", "类别不平衡"],
        sources=["第 7 章 实验评价指标与结果分析", "第 6 章 WiFi CSI 跌倒检测案例"],
        follow_up_exercise="给定 10 次真实跌倒中模型识别出 8 次、误报 3 次，计算召回率并解释它的含义。",
    )


def assess_answers(_: dict[str, str]) -> AssessmentResponse:
    return AssessmentResponse(
        score=82,
        weak_points=["类别不平衡下准确率的局限", "F1 值使用场景"],
        updated_suggestion="下一轮学习路径建议加入类别不平衡专项图解和 2 道 F1 值应用题。",
    )
