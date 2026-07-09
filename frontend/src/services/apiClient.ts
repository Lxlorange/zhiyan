import axios, { AxiosError } from 'axios'
import { ElMessageBox } from 'element-plus'

const TOKEN_KEY = 'access_token'
const USER_KEY = 'current_user'
const GENERATION_TIMEOUT_MS = 180000

export const api = axios.create({
  baseURL: '/api',
  timeout: 120000
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY)
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError<{ detail?: string | Record<string, unknown> }>) => {
    const method = error.config?.method?.toUpperCase() || 'GET'
    const url = error.config?.url || '-'
    const status = error.response?.status || 'NETWORK'
    const rawDetail = error.response?.data?.detail || error.message || '未知错误'
    const detail = typeof rawDetail === 'string' ? rawDetail : JSON.stringify(rawDetail, null, 2)

    await ElMessageBox.alert(`${method} ${url}\n\n${status}: ${detail}`, '接口调用失败', {
      confirmButtonText: '知道了',
      type: 'error'
    })

    return Promise.reject(error)
  }
)

export interface User {
  id: number
  username: string
  email: string
  full_name: string
  avatar_url: string
  school: string
  major: string
  bio: string
  role: string
  is_active: boolean
}

export interface TokenResponse {
  access_token: string
  token_type: string
  user: User
}

export interface DirectionTemplate {
  id: number
  title: string
  description: string
  recommended_period: string
  tags: string[]
  stage_outputs: string[]
  is_teacher_recommended: boolean
}

export interface DirectionAnalyzeResponse {
  normalized_title: string
  description: string
  domain: string
  route_type: string
  recommended_goal: string
  expected_output: string
  initial_knowledge_points: string[]
  clarification_questions: string[]
  risk_notes: string[]
  suggested_project: Record<string, unknown>
  agent_summary: string
}

export interface ProjectPlanMessage {
  role: 'user' | 'assistant'
  content: string
  created_at: string
}

export interface ProjectPlanRead {
  id: number
  learning_type: string
  learning_goal: string
  extra_requirements: string
  title: string
  plan_data: Record<string, any>
  messages: ProjectPlanMessage[]
  status: string
  direction_id?: number | null
  project_id?: number | null
  created_at: string
  updated_at: string
}

export interface LearningProjectRead {
  id: number
  direction_id: number
  title: string
  research_direction: string
  subject: string
  goal_type: string
  learning_goal: string
  foundation_summary: string
  expected_output: string
  recommended_period: string
  daily_minutes: number
  difficulty: string
  related_course: string
  related_knowledge_points: string[]
  related_documents: string[]
  status: string
  current_stage: string
  progress: number
  risk_notes: string[]
  personalization_strategy: string[]
  today_recommendations: string[]
  recent_classrooms: Record<string, unknown>[]
  current_weak_points: string[]
  output_checklist: string[]
  next_step: string
  generated_resource_count: number
  completed_item_count: number
  shared_token: string
}

export interface ProjectPlanBuildResponse {
  plan: ProjectPlanRead
  project: LearningProjectRead
}

export interface SyllabusOperationRead {
  id: number
  operation_type: string
  summary: string
  payload: Record<string, unknown>
  item_id?: number | null
  created_at: string
}

export interface SyllabusItemRead {
  id: number
  syllabus_version_id: number
  project_id: number
  title: string
  item_type: string
  stage: string
  difficulty: string
  estimated_minutes: number
  recommendation_reason: string
  objective: string
  prerequisites: string[]
  knowledge_points: string[]
  related_documents: string[]
  recommended_resource_types: string[]
  classroom_types: string[]
  completion_criteria: string
  assessment_method: string
  status: string
  user_order: number
  is_locked: boolean
  is_manual: boolean
}

export interface SyllabusVersionRead {
  id: number
  project_id: number
  version_no: number
  generation_method: string
  generation_reason: string
  profile_revision?: number | null
  knowledge_base_version: string
  user_adjustments: Record<string, unknown>[]
  is_current: boolean
  status: string
  agent_summary: Record<string, unknown>
  created_at: string
  updated_at: string
  items: SyllabusItemRead[]
  operations: SyllabusOperationRead[]
}

export interface SyllabusVersionSummary {
  id: number
  project_id: number
  version_no: number
  generation_method: string
  generation_reason: string
  is_current: boolean
  status: string
  created_at: string
}

export interface SyllabusEnsureResponse {
  state: 'ready' | 'started' | 'generating' | 'failed'
  message: string
  syllabus?: SyllabusVersionRead | null
}

export function saveAuth(payload: TokenResponse) {
  localStorage.setItem(TOKEN_KEY, payload.access_token)
  localStorage.setItem(USER_KEY, JSON.stringify(payload.user))
}

export function clearAuth() {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USER_KEY)
}

export function readStoredUser(): User | null {
  const raw = localStorage.getItem(USER_KEY)
  return raw ? (JSON.parse(raw) as User) : null
}

export function loginUser(username: string, password: string) {
  return api.post<TokenResponse>('/auth/login', { username, password })
}

export function registerUser(payload: {
  username: string
  email: string
  password: string
  full_name: string
  role?: 'student' | 'teacher' | 'admin'
}) {
  return api.post<TokenResponse>('/auth/register', {
    role: 'student',
    ...payload
  })
}

export function getCurrentUser() {
  return api.get<User>('/auth/me')
}

export function updateCurrentUser(payload: Partial<User>) {
  return api.patch<User>('/auth/me', payload)
}

export function getDirectionTemplates() {
  return api.get<DirectionTemplate[]>('/direction-templates')
}

export function analyzeDirection(payload: { message: string; template_id?: number | null; extra_context?: string }) {
  return api.post<DirectionAnalyzeResponse>('/directions/analyze', payload)
}

export function createProjectPlan(payload: {
  learning_type: string
  learning_goal: string
  extra_requirements: string
}) {
  return api.post<ProjectPlanRead>('/project-plans', payload)
}

type ProjectPlanStreamHandlers = {
  onToken: (content: string) => void
  onPlan: (plan: ProjectPlanRead) => void
  onDone?: () => void
}

async function requestProjectPlanStream(
  path: string,
  payload: Record<string, unknown>,
  handlers: ProjectPlanStreamHandlers
) {
  let errorShown = false
  try {
    const response = await fetch(`/api${path}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(localStorage.getItem(TOKEN_KEY)
          ? { Authorization: `Bearer ${localStorage.getItem(TOKEN_KEY)}` }
          : {})
      },
      body: JSON.stringify(payload)
    })

    if (!response.ok || !response.body) {
      const detail = await response.text()
      errorShown = true
      await ElMessageBox.alert(`POST ${path}\n\n${response.status}: ${detail}`, '接口调用失败', {
        confirmButtonText: '知道了',
        type: 'error'
      })
      throw new Error(detail || `HTTP ${response.status}`)
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder('utf-8')
    let buffer = ''

    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const events = buffer.split('\n\n')
      buffer = events.pop() || ''

      for (const rawEvent of events) {
        const lines = rawEvent.split('\n')
        const event = lines.find((line) => line.startsWith('event:'))?.replace('event:', '').trim()
        const dataLine = lines.find((line) => line.startsWith('data:'))?.replace('data:', '').trim()
        if (!event || !dataLine) continue
        const data = JSON.parse(dataLine)

        if (event === 'token') handlers.onToken(data.content || '')
        if (event === 'plan') handlers.onPlan(data as ProjectPlanRead)
        if (event === 'done') handlers.onDone?.()
        if (event === 'error') {
          errorShown = true
          await ElMessageBox.alert(`POST ${path}\n\n${data.status}: ${data.detail}`, '接口调用失败', {
            confirmButtonText: '知道了',
            type: 'error'
          })
          throw new Error(data.detail)
        }
      }
    }
  } catch (error) {
    if (!errorShown) {
      const detail = error instanceof Error ? error.message : String(error)
      await ElMessageBox.alert(`POST ${path}\n\nNETWORK: ${detail}`, '接口调用失败', {
        confirmButtonText: '知道了',
        type: 'error'
      })
    }
    throw error
  }
}

export function streamProjectPlan(
  payload: {
    learning_type: string
    learning_goal: string
    extra_requirements: string
  },
  handlers: ProjectPlanStreamHandlers
) {
  return requestProjectPlanStream('/project-plans/stream', payload, handlers)
}

export function streamAdjustProjectPlan(
  planId: number,
  message: string,
  handlers: ProjectPlanStreamHandlers
) {
  return requestProjectPlanStream(`/project-plans/${planId}/messages/stream`, { message }, handlers)
}

export function buildProjectPlan(planId: number) {
  return api.post<ProjectPlanBuildResponse>(`/project-plans/${planId}/build`)
}

export function listLearningProjects() {
  return api.get<LearningProjectRead[]>('/learning-projects')
}

export function generateSyllabus(projectId: number, generationGoal = '') {
  return api.post<SyllabusVersionRead>(`/learning-projects/${projectId}/syllabus/generate`, {
    generation_goal: generationGoal,
    force_new_version: true
  }, {
    timeout: GENERATION_TIMEOUT_MS
  })
}

export function ensureSyllabus(projectId: number, generationGoal = '') {
  return api.post<SyllabusEnsureResponse>(`/learning-projects/${projectId}/syllabus/ensure`, {
    generation_goal: generationGoal,
    force_new_version: false
  })
}

export function getCurrentSyllabus(projectId: number) {
  return api.get<SyllabusVersionRead>(`/learning-projects/${projectId}/syllabus`)
}

export function getSyllabusVersions(projectId: number) {
  return api.get<SyllabusVersionSummary[]>(`/learning-projects/${projectId}/syllabus/versions`)
}

export function updateSyllabusItemStatus(itemId: number, status: string, reason = '') {
  return api.post<SyllabusVersionRead>(`/syllabus-items/${itemId}/status`, { status, reason })
}
