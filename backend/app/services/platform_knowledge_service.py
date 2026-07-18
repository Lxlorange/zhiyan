from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.learning import Course, CourseChapter, KnowledgePoint


PLATFORM_COURSE_CODE = "PLATFORM-FEATURES"
PLATFORM_COURSE_TITLE = "平台功能介绍"
PLATFORM_CHAPTER_TITLE = "平台功能介绍"

PLATFORM_FEATURE_TOPICS: list[dict[str, object]] = [
    {
        "name": "知识库",
        "description": "上传 PDF、PPT、文档和压缩包，解析为可检索、可引用的学习资料。",
        "prerequisites": [],
        "difficulty": "easy",
    },
    {
        "name": "RAG 问答",
        "description": "基于已上传资料检索证据，再结合模型生成可追溯回答。",
        "prerequisites": ["知识库"],
        "difficulty": "easy",
    },
    {
        "name": "知识漏斗",
        "description": "把知识库证据归并为少量核心知识点，并显示先学什么、后学什么。",
        "prerequisites": ["知识库"],
        "difficulty": "easy",
    },
    {
        "name": "学习画像",
        "description": "沉淀学生目标、薄弱点、偏好、练习证据和学习节奏。",
        "prerequisites": [],
        "difficulty": "easy",
    },
    {
        "name": "项目规划",
        "description": "围绕学生目标生成项目、阶段目标、输出要求和推进策略。",
        "prerequisites": ["学习画像"],
        "difficulty": "medium",
    },
    {
        "name": "学习清单",
        "description": "把项目目标拆解为可执行的学习条目，并支持动态调整。",
        "prerequisites": ["项目规划", "知识漏斗"],
        "difficulty": "medium",
    },
    {
        "name": "每日计划",
        "description": "根据学习清单、可用时间和进度生成当天学习安排。",
        "prerequisites": ["学习清单"],
        "difficulty": "medium",
    },
    {
        "name": "AI 课堂",
        "description": "围绕学习条目生成讲解、PPT、可视化、练习和反思反馈。",
        "prerequisites": ["每日计划"],
        "difficulty": "medium",
    },
    {
        "name": "练习试卷",
        "description": "从知识图节点生成题目，记录作答结果并反哺学习画像。",
        "prerequisites": ["知识漏斗", "AI 课堂"],
        "difficulty": "medium",
    },
    {
        "name": "科研工具",
        "description": "支持文献阅读、论文写作、实验方法和答辩准备等科研任务。",
        "prerequisites": ["项目规划", "知识库"],
        "difficulty": "medium",
    },
]


def ensure_platform_knowledge_points(db: Session, *, commit: bool = True) -> list[KnowledgePoint]:
    course = db.scalar(select(Course).where(Course.code == PLATFORM_COURSE_CODE))
    if course is None:
        course = Course(
            code=PLATFORM_COURSE_CODE,
            title=PLATFORM_COURSE_TITLE,
            description="平台内置功能知识点，用于和用户知识库节点一起构建知识漏斗。",
        )
        db.add(course)
        db.flush()
    else:
        course.title = PLATFORM_COURSE_TITLE
        course.description = "平台内置功能知识点，用于和用户知识库节点一起构建知识漏斗。"

    chapter = db.scalar(
        select(CourseChapter).where(
            CourseChapter.course_id == course.id,
            CourseChapter.order_index == 1,
        )
    )
    if chapter is None:
        chapter = CourseChapter(
            course_id=course.id,
            title=PLATFORM_CHAPTER_TITLE,
            summary="平台功能之间的先修关系和学习路径。",
            order_index=1,
        )
        db.add(chapter)
        db.flush()
    else:
        chapter.title = PLATFORM_CHAPTER_TITLE
        chapter.summary = "平台功能之间的先修关系和学习路径。"

    points_by_name = {
        point.name: point
        for point in db.scalars(select(KnowledgePoint).where(KnowledgePoint.chapter_id == chapter.id)).all()
    }
    result: list[KnowledgePoint] = []
    for item in PLATFORM_FEATURE_TOPICS:
        name = str(item["name"])
        point = points_by_name.get(name)
        tags = ["platform_feature", "taxonomy_topic", "CONCEPTUAL", PLATFORM_COURSE_TITLE]
        prerequisites = [str(value) for value in item.get("prerequisites", [])]
        if point is None:
            point = KnowledgePoint(
                chapter_id=chapter.id,
                name=name,
                description=str(item["description"]),
                prerequisites=prerequisites,
                tags=tags,
                difficulty=str(item["difficulty"]),
            )
            db.add(point)
            db.flush()
        else:
            point.description = str(item["description"])
            point.prerequisites = prerequisites
            point.tags = tags
            point.difficulty = str(item["difficulty"])
        result.append(point)
    if commit:
        db.commit()
    else:
        db.flush()
    return result
