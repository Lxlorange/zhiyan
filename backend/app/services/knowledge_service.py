from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.learning import Course, CourseChapter, DocumentChunk, KnowledgeDocument, KnowledgePoint
from app.schemas import CourseMapResponse, KnowledgePointRead, KnowledgeSearchHit
from app.services.learning_workflow import COURSE_CHAPTERS, KNOWLEDGE_POINTS


COURSE_CODE = "AI4S-PRACTICE"
COURSE_TITLE = "人工智能与 AI4S 实践"


POINT_DESCRIPTIONS = {
    "混淆矩阵": "分类任务中 TP、FP、FN、TN 的结构化表示，是理解准确率、召回率、精确率和 F1 值的基础。",
    "准确率": "预测正确样本占总样本比例。在类别不平衡任务中可能掩盖少数类漏检风险。",
    "召回率": "真实正类中被模型识别出的比例。安全预警和跌倒检测更关注漏检风险，因此召回率很关键。",
    "F1 值": "精确率和召回率的调和平均，用于平衡误报和漏检。",
    "类别不平衡": "不同类别样本数量差异明显，会导致准确率等单一指标产生误导。",
    "CSI 特征": "WiFi 信道状态信息的振幅和相位变化，可反映人体活动对无线信道的影响。",
    "数据集划分": "训练集、验证集和测试集分别服务于训练、调参与泛化评估，是实验可信度的基础。",
    "Python 指标计算": "用 Python 根据 y_true、y_pred 计算混淆矩阵、准确率、召回率和 F1 值。",
    "实验报告规范": "课程项目报告需要说明背景、数据、方法、评价指标、结果分析、局限性和引用来源。",
}


DOCUMENT_SEEDS = [
    {
        "title": "分类评价指标讲义",
        "doc_type": "lecture",
        "summary": "解释混淆矩阵、准确率、召回率、F1 值及其在跌倒检测中的使用边界。",
        "chunks": [
            {
                "point": "混淆矩阵",
                "keywords": ["混淆矩阵", "TP", "FP", "FN", "TN", "准确率", "召回率"],
                "content": "混淆矩阵把分类结果拆成 TP、FP、FN、TN。跌倒检测中 FN 表示真实跌倒未被识别，通常风险高于普通误报。",
            },
            {
                "point": "召回率",
                "keywords": ["召回率", "漏检", "跌倒检测", "安全预警"],
                "content": "召回率衡量真实跌倒中被识别出的比例。安全预警场景更怕漏检，因此不能只看准确率。",
            },
            {
                "point": "类别不平衡",
                "keywords": ["类别不平衡", "准确率陷阱", "F1"],
                "content": "当正常活动样本远多于跌倒样本时，模型即使漏检跌倒也可能得到较高准确率，需要结合召回率和 F1 值评估。",
            },
        ],
    },
    {
        "title": "WiFi CSI 跌倒检测案例",
        "doc_type": "case",
        "summary": "介绍 CSI 特征、无线感知应用、数据采集和课程项目实验设计。",
        "chunks": [
            {
                "point": "CSI 特征",
                "keywords": ["CSI", "无线感知", "人体活动识别", "振幅", "相位"],
                "content": "WiFi CSI 的振幅和相位会受到人体活动影响。跌倒、行走、静止等活动会造成不同的信道变化模式。",
            },
            {
                "point": "数据集划分",
                "keywords": ["训练集", "验证集", "测试集", "泛化", "实验可信度"],
                "content": "课程项目中训练集用于训练模型，验证集用于调参，测试集用于最终评估泛化能力，三者不能混用。",
            },
        ],
    },
    {
        "title": "课程项目报告检查清单",
        "doc_type": "rubric",
        "summary": "约束 AI4S 课程项目报告结构、引用来源和实验结论边界。",
        "chunks": [
            {
                "point": "实验报告规范",
                "keywords": ["报告", "检查清单", "引用", "局限性", "实验结论"],
                "content": "实验报告应包含问题背景、数据来源、方法设计、指标选择、结果分析、局限性说明和引用来源，不能编造实验结果。",
            },
            {
                "point": "Python 指标计算",
                "keywords": ["Python", "指标计算", "混淆矩阵", "代码案例"],
                "content": "代码实践建议从 y_true 和 y_pred 开始，先计算混淆矩阵，再分别输出准确率、召回率、精确率和 F1 值。",
            },
        ],
    },
]


def seed_course_knowledge(db: Session) -> None:
    existing = db.scalar(select(Course).where(Course.code == COURSE_CODE))
    if existing:
        return

    course = Course(
        code=COURSE_CODE,
        title=COURSE_TITLE,
        description="面向高校 AI4S 入门课程的知识库，覆盖机器学习评价指标、无线感知和课程项目实践。",
    )
    db.add(course)
    db.flush()

    chapters: list[CourseChapter] = []
    for index, title in enumerate(COURSE_CHAPTERS, start=1):
        chapter = CourseChapter(
            course_id=course.id,
            title=title,
            summary=f"{title} 的课程知识、练习与实践材料。",
            order_index=index,
        )
        db.add(chapter)
        chapters.append(chapter)
    db.flush()

    chapter_by_topic = {
        "混淆矩阵": chapters[2],
        "准确率": chapters[2],
        "召回率": chapters[6],
        "F1 值": chapters[6],
        "类别不平衡": chapters[6],
        "CSI 特征": chapters[5],
        "数据集划分": chapters[6],
        "Python 指标计算": chapters[1],
        "实验报告规范": chapters[7],
    }

    point_by_name: dict[str, KnowledgePoint] = {}
    for name in KNOWLEDGE_POINTS:
        point = KnowledgePoint(
            chapter_id=chapter_by_topic[name].id,
            name=name,
            description=POINT_DESCRIPTIONS[name],
            prerequisites=["机器学习分类任务"] if name in {"召回率", "F1 值", "类别不平衡"} else [],
            tags=["A3", "AI4S", "WiFi CSI"],
            difficulty="medium",
        )
        db.add(point)
        point_by_name[name] = point
    db.flush()

    for doc_seed in DOCUMENT_SEEDS:
        document = KnowledgeDocument(
            course_id=course.id,
            title=doc_seed["title"],
            doc_type=doc_seed["doc_type"],
            source_uri=f"seed://{COURSE_CODE}/{doc_seed['doc_type']}",
            summary=doc_seed["summary"],
        )
        db.add(document)
        db.flush()
        for index, chunk_seed in enumerate(doc_seed["chunks"], start=1):
            point = point_by_name.get(chunk_seed["point"])
            db.add(
                DocumentChunk(
                    document_id=document.id,
                    knowledge_point_id=point.id if point else None,
                    chunk_index=index,
                    content=chunk_seed["content"],
                    keywords=chunk_seed["keywords"],
                )
            )

    db.commit()


def get_course_map_from_db(db: Session) -> CourseMapResponse:
    seed_course_knowledge(db)
    course = db.scalar(select(Course).where(Course.code == COURSE_CODE))
    if course is None:
        return CourseMapResponse(course=COURSE_TITLE, chapters=COURSE_CHAPTERS, knowledge_points=KNOWLEDGE_POINTS)

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
    terms = [term.strip() for term in query.replace("，", " ").replace("、", " ").split() if term.strip()]
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
