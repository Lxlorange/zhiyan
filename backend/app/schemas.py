from typing import Optional

from pydantic import BaseModel, Field


class ProfileRequest(BaseModel):
    message: str = Field(..., min_length=1)


class StudentProfile(BaseModel):
    knowledge_base: str
    learning_goal: str
    cognitive_style: str
    weak_points: list[str]
    practice_level: str
    resource_preference: list[str]
    learning_pace: str
    interest_direction: str


class AgentTrace(BaseModel):
    agent: str
    status: str
    summary: str
    latency_ms: int


class ResourceCard(BaseModel):
    id: str
    type: str
    title: str
    target_profile: str
    knowledge_points: list[str]
    content: str
    sources: list[str]


class LearningStep(BaseModel):
    id: str
    title: str
    reason: str
    resources: list[str]
    estimated_minutes: int


class DemoWorkflowResponse(BaseModel):
    profile: StudentProfile
    weak_points: list[str]
    path: list[LearningStep]
    resources: list[ResourceCard]
    agent_trace: list[AgentTrace]


class TutorRequest(BaseModel):
    question: str = Field(..., min_length=1)
    profile: Optional[StudentProfile] = None


class TutorResponse(BaseModel):
    answer: str
    knowledge_points: list[str]
    sources: list[str]
    follow_up_exercise: str


class AssessmentRequest(BaseModel):
    answers: dict[str, str]


class AssessmentResponse(BaseModel):
    score: int
    weak_points: list[str]
    updated_suggestion: str
