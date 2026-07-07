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
  mastery: Record<string, number>
  revision: number
}

export interface ResourceCard {
  id: string
  type: string
  title: string
  target_profile: string
  knowledge_points: string[]
  content: string
  format_hint: string
  sources: string[]
  safety_notes: string[]
}

export interface LearningStep {
  id: string
  title: string
  objective: string
  reason: string
  resources: string[]
  estimated_minutes: number
  status: string
}

export interface AgentTrace {
  agent: string
  status: string
  input_summary: string
  output_summary: string
  latency_ms: number
}

export interface KnowledgeGap {
  id: string
  title: string
  severity: string
  evidence: string
  related_points: string[]
}

export interface QuizQuestion {
  id: string
  prompt: string
  options: string[]
  answer: string
  knowledge_point: string
}

export interface WorkflowState {
  session_id: string
  profile: StudentProfile
  gaps: KnowledgeGap[]
  path: LearningStep[]
  resources: ResourceCard[]
  quiz: QuizQuestion[]
  agent_trace: AgentTrace[]
}

export interface TutorResponse {
  answer: string
  knowledge_points: string[]
  sources: string[]
  follow_up_exercise: string
  strategy: string
}

export function runDemoWorkflow(message: string) {
  return api.post<WorkflowState>('/workflow/start', { message })
}

export function askTutor(question: string, profile?: StudentProfile) {
  return api.post<TutorResponse>('/tutor', { question, profile })
}
