from fastapi import APIRouter

from app.api.routes_auth import router as auth_router
from app.api.routes_classroom import router as classroom_router
from app.api.routes_course import router as course_router
from app.api.routes_database import router as database_router
from app.api.routes_directions import router as directions_router
from app.api.routes_profile import router as profile_router
from app.api.routes_practice_papers import router as practice_papers_router
from app.api.routes_syllabus import router as syllabus_router
from app.api.routes_system import router as system_router
from app.api.routes_workflow import router as workflow_router
from app.api.routes_workspace import router as workspace_router

router = APIRouter(prefix="/api")
router.include_router(auth_router)
router.include_router(classroom_router)
router.include_router(directions_router)
router.include_router(profile_router)
router.include_router(practice_papers_router)
router.include_router(workflow_router)
router.include_router(course_router)
router.include_router(database_router)
router.include_router(syllabus_router)
router.include_router(system_router)
router.include_router(workspace_router)
