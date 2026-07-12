from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.learning import Course, CourseChapter, DocumentChunk, KnowledgeDocument, KnowledgePoint
from app.schemas import CourseMapResponse, KnowledgePointRead, KnowledgeSearchHit


COURSE_CODE = "AI4S-PRACTICE"
COURSE_TITLE = "人工智能与科研学习实践"

ALL_COURSE_CHAPTERS = [
    "人工智能与科研学习概论",
    "Python 数据处理基础",
    "机器学习分类任务",
    "深度学习基础",
    "数据采集与实验设计",
    "科研选题与文献综述",
    "实验评价指标与结果分析",
    "课程论文写作与展示规范",
    "论文修改与引用规范",
    "模拟答辩与面试训练",
]

POINT_DESCRIPTIONS = {
    "混淆矩阵": "分类任务中 TP、FP、FN、TN 的结构化表示，是理解准确率、召回率、精确率和 F1 值的基础。",
    "准确率": "预测正确样本占总样本比例。在类别不平衡任务中可能掩盖少数类风险。",
    "召回率": "真实正类中被模型识别出的比例，适合衡量漏检风险。",
    "F1 值": "精确率和召回率的调和平均，用于平衡误报和漏检。",
    "类别不平衡": "不同类别样本数量差异明显，会导致准确率等单一指标产生误导。",
    "数据集划分": "训练集、验证集和测试集分别服务于训练、调参与泛化评估，是实验可信度的基础。",
    "Python 指标计算": "用 Python 根据 y_true、y_pred 计算混淆矩阵、准确率、召回率和 F1 值。",
    "综述性文献导读": "围绕研究背景、代表工作、方法谱系、数据集、指标和局限性整理文献矩阵。",
    "研究空白识别": "从现有工作限制、场景迁移、数据质量、实时性、可解释性和部署成本中提炼可研究问题。",
    "选题凝练": "把宽泛兴趣压缩成包含对象、方法、数据、评价指标和预期贡献的具体题目。",
    "数据采集方案": "规划数据来源、采集流程、标签定义、样本量、伦理安全边界和质量控制。",
    "实验变量控制": "控制影响实验结果的关键变量，明确自变量、因变量、控制变量和干扰因素。",
    "技术路线设计": "从数据、方法、模型、评价、部署或验证形成可执行路线。",
    "图表规范": "论文图表需要清楚标注数据来源、横纵轴、单位、对比基线、误差范围和实验设置。",
    "课程论文写作规范": "课程论文应包含摘要、引言、相关工作、方法、实验、结果、讨论、结论和参考文献。",
    "模拟答辩": "围绕研究意义、创新点、数据可信度、方法选择、指标解释、局限性和下一步追问进行训练。",
}

KNOWLEDGE_POINT_SEEDS = [
    ("混淆矩阵", 3),
    ("准确率", 3),
    ("召回率", 7),
    ("F1 值", 7),
    ("类别不平衡", 7),
    ("数据集划分", 7),
    ("Python 指标计算", 2),
    ("综述性文献导读", 6),
    ("研究空白识别", 6),
    ("选题凝练", 6),
    ("数据采集方案", 5),
    ("实验变量控制", 5),
    ("技术路线设计", 5),
    ("图表规范", 8),
    ("课程论文写作规范", 8),
    ("模拟答辩", 10),
]

DOCUMENT_SEEDS = [
    {
        "title": "A3 赛题要求摘要",
        "doc_type": "contest_requirement",
        "source_uri": "docs/A3-基于大模型的个性化资源生成与学习多智能体系统开发 - A组赛题 - 软件杯大赛官网.html",
        "summary": "系统需通过对话式画像、多智能体资源生成、个性化学习路径、智能辅导、学习效果评估实现个性化多模态学习资源生成。",
        "chunks": [
            {
                "point": "课程论文写作规范",
                "keywords": ["A3", "赛题", "多智能体", "个性化学习", "多模态资源"],
                "content": "A3 赛题要求系统能够依据学生提供的专业、课程内容、知识短板、学习需求等信息，生成多类型个性化学习资源，并体现多智能体协同。",
            },
            {
                "point": "图表规范",
                "keywords": ["防幻觉", "内容安全", "流式输出", "来源"],
                "content": "赛题非功能要求强调界面现代、流式输出、Markdown/多模态内容卡片、防幻觉、内容安全过滤和生成进度追踪。",
            },
        ],
    },
    {
        "title": "科研学习通用资料规范",
        "doc_type": "research_guideline",
        "source_uri": "seed://AI4S-PRACTICE/research-guideline",
        "summary": "提供通用科研学习流程和来源约束，不绑定任何具体研究方向。",
        "chunks": [
            {
                "point": "综述性文献导读",
                "keywords": ["文献综述", "来源", "论文摘要", "研究脉络"],
                "content": "综述性回答应明确区分已提供来源、模型推理和待用户补充来源。正式写作前必须核对论文标题、作者、年份、会议/期刊、DOI 或链接。",
            },
            {
                "point": "选题凝练",
                "keywords": ["选题", "研究问题", "边界", "贡献"],
                "content": "具体选题应包含研究对象、任务目标、方法路线、数据来源、评价方式和可交付成果，避免只停留在宽泛方向。",
            },
            {
                "point": "研究空白识别",
                "keywords": ["研究空白", "局限性", "创新点", "可行性"],
                "content": "研究空白需要从已读资料中归纳，不能把没有来源的猜测写成事实；可以用“待验证假设”标注不确定内容。",
            },
        ],
    },
    {
        "title": "实验助手通用检查清单",
        "doc_type": "experiment_rubric",
        "source_uri": "seed://AI4S-PRACTICE/experiment-assistant-checklist",
        "summary": "实验助手生成技术路线、数据采集方案、指标、变量、图表规范和阶段计划时使用的通用约束。",
        "chunks": [
            {
                "point": "技术路线设计",
                "keywords": ["技术路线", "数据", "方法", "模型", "评价"],
                "content": "技术路线建议按数据来源、数据处理、方法或模型、训练/验证、评价指标、误差分析、可复现材料展开。",
            },
            {
                "point": "数据采集方案",
                "keywords": ["数据采集", "样本", "标签", "伦理", "质量控制"],
                "content": "数据采集方案应说明数据来源、采集对象、标签定义、样本量、划分策略、隐私伦理和质量控制方法。",
            },
            {
                "point": "实验变量控制",
                "keywords": ["变量", "控制变量", "干扰因素", "消融"],
                "content": "实验设计应明确自变量、因变量、控制变量和干扰因素，并给出必要的消融或对比实验。",
            },
            {
                "point": "图表规范",
                "keywords": ["图表", "混淆矩阵", "对比表", "曲线", "论文"],
                "content": "论文图表建议包含系统流程图、数据统计表、指标对比表、错误案例分析和关键实验结果图；每个图表都需说明数据来源与实验设置。",
            },
        ],
    },
    {
        "title": "课程论文写作与引用规范",
        "doc_type": "writing_spec",
        "source_uri": "seed://AI4S-PRACTICE/course-paper-writing-spec",
        "summary": "辅助论文撰写、格式检查、引用规范和防幻觉约束。",
        "chunks": [
            {
                "point": "课程论文写作规范",
                "keywords": ["摘要", "引言", "相关工作", "方法", "实验", "参考文献"],
                "content": "课程论文结构建议为：题目、摘要、关键词、引言、相关工作、方法、实验设置、结果与分析、讨论、结论、参考文献。所有数据和引用必须可追溯。",
            },
            {
                "point": "图表规范",
                "keywords": ["图题", "表题", "单位", "来源", "编号"],
                "content": "图表必须编号并写明图题/表题；坐标轴需标单位；表格需说明数据来源；不要用无来源的模型输出替代真实实验结果。",
            },
            {
                "point": "模拟答辩",
                "keywords": ["开题", "中期", "答辩", "追问", "评分"],
                "content": "模拟答辩应覆盖研究意义、相关工作差异、数据采集合理性、指标选择、失败案例、创新点真实性和后续改进计划，并给出评分与修改建议。",
            },
        ],
    },
]


def seed_course_knowledge(db: Session) -> None:
    course = db.scalar(select(Course).where(Course.code == COURSE_CODE))
    if course is None:
        course = Course(
            code=COURSE_CODE,
            title=COURSE_TITLE,
            description="面向高校科研学习的通用知识库，覆盖评价指标、实验设计、论文写作和模拟答辩。",
        )
        db.add(course)
        db.flush()
    else:
        course.title = COURSE_TITLE
        course.description = "面向高校科研学习的通用知识库，覆盖评价指标、实验设计、论文写作和模拟答辩。"

    chapters = _upsert_chapters(db, course)
    point_by_name = _upsert_points(db, chapters)
    _delete_stale_seed_documents(db, course)
    _upsert_documents(db, course, point_by_name)
    db.commit()


def _delete_stale_seed_documents(db: Session, course: Course) -> None:
    current_titles = [doc_seed["title"] for doc_seed in DOCUMENT_SEEDS]
    for document in db.scalars(
        select(KnowledgeDocument).where(
            KnowledgeDocument.course_id == course.id,
            KnowledgeDocument.source_uri.like("seed://AI4S-PRACTICE/%"),
            KnowledgeDocument.title.notin_(current_titles),
        )
    ).all():
        db.delete(document)
    db.flush()


def _upsert_chapters(db: Session, course: Course) -> dict[int, CourseChapter]:
    chapters_by_order = {
        chapter.order_index: chapter
        for chapter in db.scalars(select(CourseChapter).where(CourseChapter.course_id == course.id)).all()
    }
    for index, title in enumerate(ALL_COURSE_CHAPTERS, start=1):
        chapter = chapters_by_order.get(index)
        if chapter is None:
            chapter = CourseChapter(course_id=course.id, order_index=index, title=title, summary=f"{title} 的课程知识、练习与实践材料。")
            db.add(chapter)
            chapters_by_order[index] = chapter
        else:
            chapter.title = title
            chapter.summary = f"{title} 的课程知识、练习与实践材料。"
    db.flush()
    return chapters_by_order


def _upsert_points(db: Session, chapters: dict[int, CourseChapter]) -> dict[str, KnowledgePoint]:
    existing_points = db.scalars(select(KnowledgePoint)).all()
    point_by_name = {point.name: point for point in existing_points}
    for name, chapter_order in KNOWLEDGE_POINT_SEEDS:
        chapter = chapters[chapter_order]
        point = point_by_name.get(name)
        if point is None:
            point = KnowledgePoint(
                chapter_id=chapter.id,
                name=name,
                description=POINT_DESCRIPTIONS[name],
                prerequisites=["机器学习分类任务"] if name in {"召回率", "F1 值", "类别不平衡"} else [],
                tags=["A3", "AI4S", "科研训练"],
                difficulty="medium",
            )
            db.add(point)
            point_by_name[name] = point
        else:
            point.chapter_id = chapter.id
            point.description = POINT_DESCRIPTIONS[name]
            point.tags = ["A3", "AI4S", "科研训练"]
    db.flush()
    return point_by_name


def _upsert_documents(db: Session, course: Course, point_by_name: dict[str, KnowledgePoint]) -> None:
    existing_docs = {
        document.title: document
        for document in db.scalars(select(KnowledgeDocument).where(KnowledgeDocument.course_id == course.id)).all()
    }
    for doc_seed in DOCUMENT_SEEDS:
        document = existing_docs.get(doc_seed["title"])
        if document is None:
            document = KnowledgeDocument(
                course_id=course.id,
                title=doc_seed["title"],
                doc_type=doc_seed["doc_type"],
                source_uri=doc_seed["source_uri"],
                summary=doc_seed["summary"],
            )
            db.add(document)
            db.flush()
        else:
            document.doc_type = doc_seed["doc_type"]
            document.source_uri = doc_seed["source_uri"]
            document.summary = doc_seed["summary"]

        existing_chunks = {
            chunk.chunk_index: chunk
            for chunk in db.scalars(select(DocumentChunk).where(DocumentChunk.document_id == document.id)).all()
        }
        for index, chunk_seed in enumerate(doc_seed["chunks"], start=1):
            point = point_by_name.get(chunk_seed["point"])
            chunk = existing_chunks.get(index)
            if chunk is None:
                db.add(
                    DocumentChunk(
                        document_id=document.id,
                        knowledge_point_id=point.id if point else None,
                        chunk_index=index,
                        content=chunk_seed["content"],
                        keywords=chunk_seed["keywords"],
                    )
                )
            else:
                chunk.knowledge_point_id = point.id if point else None
                chunk.content = chunk_seed["content"]
                chunk.keywords = chunk_seed["keywords"]


def get_course_map_from_db(db: Session) -> CourseMapResponse:
    seed_course_knowledge(db)
    course = db.scalar(select(Course).where(Course.code == COURSE_CODE))
    if course is None:
        return CourseMapResponse(
            course=COURSE_TITLE,
            chapters=ALL_COURSE_CHAPTERS,
            knowledge_points=[name for name, _ in KNOWLEDGE_POINT_SEEDS],
        )

    chapters = db.scalars(
        select(CourseChapter).where(CourseChapter.course_id == course.id).order_by(CourseChapter.order_index)
    ).all()
    chapter_ids = [chapter.id for chapter in chapters]
    points = db.scalars(select(KnowledgePoint).where(KnowledgePoint.chapter_id.in_(chapter_ids))).all()
    return CourseMapResponse(
        course=course.title,
        chapters=[chapter.title for chapter in chapters],
        knowledge_points=[point.name for point in points],
    )


def list_knowledge_points(db: Session) -> list[KnowledgePointRead]:
    seed_course_knowledge(db)
    rows = db.execute(
        select(KnowledgePoint, CourseChapter)
        .join(CourseChapter, KnowledgePoint.chapter_id == CourseChapter.id)
        .order_by(CourseChapter.order_index, KnowledgePoint.id)
    ).all()
    return [
        KnowledgePointRead(
            id=point.id,
            name=point.name,
            description=point.description,
            chapter=chapter.title,
            prerequisites=point.prerequisites,
            tags=point.tags,
            difficulty=point.difficulty,
        )
        for point, chapter in rows
    ]


def search_knowledge(db: Session, query: str, limit: int = 6) -> list[KnowledgeSearchHit]:
    seed_course_knowledge(db)
    terms = [term.strip() for term in query.replace("，", " ").replace("、", " ").replace("/", " ").split() if term.strip()]
    if not terms:
        terms = [query.strip()] if query.strip() else []

    filters = []
    for term in terms:
        pattern = f"%{term}%"
        filters.extend(
            [
                DocumentChunk.content.ilike(pattern),
                KnowledgePoint.name.ilike(pattern),
                KnowledgePoint.description.ilike(pattern),
                KnowledgeDocument.title.ilike(pattern),
                KnowledgeDocument.summary.ilike(pattern),
            ]
        )

    statement = (
        select(DocumentChunk, KnowledgeDocument, KnowledgePoint)
        .join(KnowledgeDocument, DocumentChunk.document_id == KnowledgeDocument.id)
        .join(KnowledgePoint, DocumentChunk.knowledge_point_id == KnowledgePoint.id, isouter=True)
        .limit(limit)
    )
    if filters:
        statement = statement.where(or_(*filters))

    rows = db.execute(statement).all()
    return [
        KnowledgeSearchHit(
            document_title=document.title,
            document_type=document.doc_type,
            knowledge_point=point.name if point else "课程资料",
            content=chunk.content,
            source_uri=document.source_uri,
            keywords=chunk.keywords,
        )
        for chunk, document, point in rows
    ]
