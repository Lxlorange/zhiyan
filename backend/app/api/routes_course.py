from fastapi import APIRouter

from app.schemas import CourseMapResponse
from app.services.learning_workflow import COURSE_CHAPTERS, KNOWLEDGE_POINTS

router = APIRouter(prefix="/course", tags=["course"])


@router.get("/map", response_model=CourseMapResponse)
def course_map() -> CourseMapResponse:
    return CourseMapResponse(
        course="人工智能与 AI4S 实践",
        chapters=COURSE_CHAPTERS,
        knowledge_points=KNOWLEDGE_POINTS,
    )
