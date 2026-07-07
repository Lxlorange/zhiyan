import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 20000
})

export interface StudentProfile {
  knowledge_base: string
  learning_goal: string
  cognitive_style: string
  weak_points: string[]
  practice_level: string
  resource_preference: string[]
  learning_pace: string
  interest_direction: string
}

export interface ResourceCard {
  id: string
  type: string
  title: string
  target_profile: string
  knowledge_points: string[]
  content: string
  sources: string[]
}

export interface LearningStep {
  id: string
  title: string
  reason: string
  resources: string[]
  estimated_minutes: number
}

export interface AgentTrace {
  agent: string
  status: string
  summary: string
  latency_ms: number
}

export interface DemoWorkflowResponse {
  profile: StudentProfile
  weak_points: string[]
  path: LearningStep[]
  resources: ResourceCard[]
  agent_trace: AgentTrace[]
}

export interface TutorResponse {
  answer: string
  knowledge_points: string[]
  sources: string[]
  follow_up_exercise: string
}

export function runDemoWorkflow(message: string) {
  return api.post<DemoWorkflowResponse>('/demo-workflow', { message })
}

export function askTutor(question: string, profile?: StudentProfile) {
  return api.post<TutorResponse>('/tutor', { question, profile })
}
