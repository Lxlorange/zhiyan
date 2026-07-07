from fastapi import APIRouter

from app.api.routes_auth import router as auth_router
from app.api.routes_course import router as course_router
from app.api.routes_directions import router as directions_router
from app.api.routes_profile import router as profile_router
from app.api.routes_teacher import router as teacher_router
from app.api.routes_workflow import router as workflow_router

router = APIRouter(prefix="/api")
router.include_router(auth_router)
router.include_router(directions_router)
router.include_router(profile_router)
router.include_router(workflow_router)
router.include_router(course_router)
router.include_router(teacher_router)
