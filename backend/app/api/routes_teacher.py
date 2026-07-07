from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.models.user import User
from app.schemas import TeacherDashboardResponse
from app.services.ai_workflow import build_teacher_dashboard

router = APIRouter(prefix="/teacher", tags=["teacher"])


@router.get("/dashboard", response_model=TeacherDashboardResponse)
def teacher_dashboard(_: User = Depends(get_current_user)) -> TeacherDashboardResponse:
    return build_teacher_dashboard()
