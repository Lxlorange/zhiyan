import axios, { AxiosError } from 'axios'
import { ElMessageBox } from 'element-plus'

const TOKEN_KEY = 'access_token'
const USER_KEY = 'current_user'
const GENERATION_TIMEOUT_MS = 180000

declare module 'axios' {
  export interface AxiosRequestConfig {
    skipErrorPopup?: boolean
  }
}

type ApiErrorPayload = {
  detail?: string | Record<string, unknown> | Array<Record<string, unknown>>
  msg?: string
  message?: string
}

function stringifyErrorDetail(raw: unknown): string {
  if (typeof raw === 'string') return raw
  if (raw === null || raw === undefined) return '未知错误'
  if (Array.isArray(raw)) return raw.map((item) => stringifyErrorDetail(item)).filter(Boolean).join('；')
  if (typeof raw === 'object') {
    const entries = Object.entries(raw as Record<string, unknown>)
      .filter(([, value]) => value !== null && value !== undefined && value !== '')
      .map(([key, value]) => `${key.replace(/_/g, ' ')}：${stringifyErrorDetail(value)}`)
    return entries.length ? entries.join('；') : '未知错误'
  }
  try {
    return JSON.stringify(raw, null, 2)
  } catch {
    return String(raw)
  }
}

function extractErrorMsg(payload: ApiErrorPayload | undefined, fallback: string) {
  return stringifyErrorDetail(payload?.detail || payload?.msg || payload?.message || fallback)
}

function userFacingErrorMessage(url: string, status: number | string, detail: string) {
  const normalized = detail.toLowerCase()
  if (url.includes('/auth/login') && status === 401) return '用户名或密码不正确，请检查后重新登录。'
  if (status === 401) return '登录状态已失效，请重新登录。'
  if (status === 403) return '当前账号没有权限执行这个操作。'
  if (status === 404) return '没有找到对应的数据，请刷新后重试。'
  if (url.includes('/course/knowledge/import')) return `知识库导入失败：${detail}`
  if (status === 422) return '填写内容不完整或格式不正确，请检查后再提交。'
  if (status === 413) return detail
  if (status === 'NETWORK') return '网络连接失败，请检查后端服务是否正在运行。'
  if (normalized.includes('api key')) return '模型 API Key 未配置或不可用，请到系统设置检查。'
  if (normalized.includes('timeout') || normalized.includes('timed out')) return '请求超时，请稍后重试。'
  return `错误：${detail}，请您截图联系管理员处理`
}

async function showApiError(context: {
  method: string
  url: string
  status: number | string
  detail: string
  source?: unknown
}) {
  console.error('[API Error]', {
    method: context.method,
    url: context.url,
    status: context.status,
    detail: context.detail,
    source: context.source
  })

  await ElMessageBox.alert(
    userFacingErrorMessage(context.url, context.status, context.detail),
    '操作失败',
    {
      confirmButtonText: '知道了',
      type: 'error'
    }
  )
}

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
  async (error: AxiosError<ApiErrorPayload>) => {
    if (error.config?.skipErrorPopup) return Promise.reject(error)

    const method = error.config?.method?.toUpperCase() || 'GET'
    const url = error.config?.url || '-'
    const status = error.response?.status || 'NETWORK'
    const detail = extractErrorMsg(error.response?.data, error.message || '未知错误')
    await showApiError({ method, url, status, detail, source: error })

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
  llm_provider: string
  llm_model: string
  llm_base_url: string
  llm_api_key_configured: boolean
  llm_api_key_tail: string
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

export interface ParsedProjectPlanAttachment {
  filename: string
  content_type: string
  size: number
  parser: 'text' | 'pdf'
  text: string
  page_count?: number | null
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
  study_weekends: boolean
  study_weekdays: number[]
  difficulty: string
  related_course: string
  related_knowledge_points: string[]
  related_documents: string[]
  research_training: Record<string, any>
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

export interface ClassroomResourceRead {
  id: number
  resource_type: string
  title: string
  content_data: Record<string, any>
  file_path: string
  source: string
  status: string
  created_at: string
}

export interface ClassroomSubmissionRead {
  id: number
  submission_type: string
  content: Record<string, any>
  score: number
  passed: boolean
  feedback: string
  created_at: string
}

export interface ClassroomSessionRead {
  id: number
  syllabus_item_id: number
  project_id: number
  title: string
  status: string
  progress_state: Record<string, any>
  ppt_resource_id?: number | null
  slides_completed: boolean
  slide_progress: Record<string, any>
  generation_started_at?: string | null
  generation_error: string
  quiz_passed: boolean
  practice_passed: boolean
  reflection_passed: boolean
  completed_at?: string | null
  resources: ClassroomResourceRead[]
  submissions: ClassroomSubmissionRead[]
}

export interface ClassroomDialogueResponse {
  answer: string
  cards: Record<string, any>[]
  suggested_actions: string[]
  profile_update_suggestion: string
  session: ClassroomSessionRead
}

export interface DailyPlanItemRead {
  id: number
  day_index: number
  planned_date: string
  title: string
  estimated_minutes: number
  learning_focus: string
  resource_types: string[]
  status: string
  user_order: number
  syllabus_item_id?: number | null
  project_id: number
  is_overdue: boolean
  is_today: boolean
  can_start: boolean
}

export interface DailyPlanRead {
  id: number
  project_id: number
  syllabus_version_id: number
  title: string
  start_date: string
  daily_minutes: number
  study_weekends: boolean
  study_weekdays: number[]
  generation_reason: string
  status: string
  created_at: string
  items: DailyPlanItemRead[]
}

export interface DailyPlanCoachResponse {
  answer: string
  extracted_profile_signals: Record<string, any>
  suggested_plan_actions: string[]
  profile_revision?: number | null
  plan: DailyPlanRead
}

export interface ProfileVersionRead {
  id: number
  revision: number
  source: string
  update_reason: string
  extracted_features: Record<string, any>
  profile_data: Record<string, any>
  created_at: string
}

export interface ProfileCenterResponse {
  profile_id?: number | null
  current_revision: number
  profile_data: Record<string, any>
  entries: ProfileEntryRead[]
  versions: ProfileVersionRead[]
  recommendations: string[]
}

export interface ProfileEntryRead {
  key: string
  label: string
  value: any
  confidence: number
  source: string
  source_object_id?: string | null
  agent: string
  is_confirmed: boolean
  is_enabled: boolean
  revision: number
  updated_at?: string | null
}

export interface LiteraturePaperRead {
  id: number
  project_id?: number | null
  title: string
  authors: string[]
  venue: string
  year: string
  source_uri: string
  abstract: string
  keywords: string[]
  reading_status: string
  notes: string
  citation_text: string
  created_at: string
  updated_at: string
}

export interface ResearchToolRunRead {
  id: number
  project_id?: number | null
  tool_type: string
  title: string
  input_text: string
  output_data: Record<string, any>
  agent_trace: Record<string, any>[]
  status: string
  created_at: string
}

export interface PracticeKnowledgeNodeRead {
  id: string
  label: string
  layer: string
  category: string
  description: string
  knowledge_point: string
  source_title: string
  selected: boolean
}

export interface ModelProviderOption {
  id: string
  name: string
  base_url: string
  models: string[]
  description: string
}

export interface UserModelSettingsRead {
  provider: string
  model: string
  base_url: string
  api_key_configured: boolean
  api_key_tail: string
  provider_options: ModelProviderOption[]
}

export interface UserModelSettingsUpdate {
  provider: string
  model: string
  base_url: string
  api_key?: string | null
}

export interface PracticePaperQuestionRead {
  id: number
  question_id: string
  type: string
  point: string
  prompt: string
  options: string[]
  answer: string
  explanation: string
  source_title: string
  source_excerpt: string
  difficulty: string
  order_index: number
}

export interface PracticePaperAttemptResult {
  question_id: string
  question_db_id: number
  point: string
  user_answer: any
  correct_answer: string
  is_correct: boolean
  explanation: string
  remediation: string
}

export interface PracticePaperAttemptRead {
  id: number
  paper_id: number
  answers: Record<string, any>
  results: PracticePaperAttemptResult[]
  score: number
  correct_count: number
  total_count: number
  wrong_points: string[]
  summary: string
  created_at: string
}

export interface PracticePaperRead {
  id: number
  project_id?: number | null
  title: string
  description: string
  source: string
  difficulty: string
  question_types: string[]
  selected_nodes: Record<string, any>[]
  knowledge_points: string[]
  status: string
  total_questions: number
  last_score: number
  best_score: number
  attempt_count: number
  generation_trace: Record<string, any>[]
  created_at: string
  updated_at: string
  questions: PracticePaperQuestionRead[]
  attempts: PracticePaperAttemptRead[]
}

export interface PracticePaperSubmitResponse {
  paper: PracticePaperRead
  attempt: PracticePaperAttemptRead
}

export interface AgentTraceRead {
  agent: string
  status: string
  input_summary: string
  output_summary: string
  latency_ms: number
}

export interface WorkspaceOverviewResponse {
  projects: LearningProjectRead[]
  profile: ProfileCenterResponse
  resources: ClassroomResourceRead[]
  agent_tasks: AgentTraceRead[]
  submissions: ClassroomSubmissionRead[]
  literature: LiteraturePaperRead[]
  tool_runs: ResearchToolRunRead[]
  metrics: Record<string, number>
}

export interface KnowledgePointRead {
  id: number
  name: string
  description: string
  chapter: string
  prerequisites: string[]
  tags: string[]
  difficulty: string
}

export interface KnowledgeSearchHit {
  chunk_id?: number | null
  document_title: string
  document_type: string
  knowledge_point: string
  content: string
  source_uri: string
  keywords: string[]
  page_no?: number | null
  slide_no?: number | null
  section_title?: string
  distance?: number | null
  keyword_hit?: number | null
}

export interface KnowledgeImportJobRead {
  id: number
  course_code: string
  course_title: string
  source_name: string
  status: string
  total_files: number
  parsed_files: number
  failed_files: number
  total_chunks: number
  error_message: string
  options: Record<string, any>
  created_at: string
  updated_at: string
}

export interface KnowledgeStorageUsageRead {
  quota_bytes: number
  used_bytes: number
  remaining_bytes: number
  quota_mb: number
  used_mb: number
  remaining_mb: number
  used_percent: number
  document_count: number
  job_count: number
}

export interface KnowledgeDocumentRead {
  id: number
  title: string
  doc_type: string
  source_uri: string
  summary: string
  file_name: string
  file_hash: string
  course_code: string
  parse_status: string
  parse_meta: Record<string, any>
  chunk_count: number
  created_at: string
}

export interface KnowledgeChunkRead {
  id: number
  document_id: number
  chunk_index: number
  content: string
  keywords: string[]
  knowledge_point: string
  page_no?: number | null
  slide_no?: number | null
  section_title: string
  token_count: number
}

export interface DatabaseCitation {
  id: string
  source_type: string
  title: string
  document_type: string
  knowledge_point: string
  content: string
  source_uri: string
  page_no?: number | null
  slide_no?: number | null
  section_title: string
  score?: number | null
  review_url: string
}

export interface DatabaseAskResponse {
  answer: string
  citations: DatabaseCitation[]
  related_points: string[]
  follow_up_questions: string[]
  confidence: 'low' | 'medium' | 'high' | string
  used_llm: boolean
}

export interface DatabaseGraphNode {
  id: string
  name: string
  category: string
  description: string
  count: number
}

export interface DatabaseGraphEdge {
  source: string
  target: string
  relation: string
}

export interface DatabaseGraphResponse {
  nodes: DatabaseGraphNode[]
  edges: DatabaseGraphEdge[]
}

export interface KnowledgeLinkNode {
  id: string
  label: string
  layer: 'project' | 'document' | 'knowledge_base' | string
  category: string
  description: string
  meta: Record<string, any>
  weight: number
}

export interface KnowledgeLinkEdge {
  source: string
  target: string
  relation: string
  strength: string
  reason: string
}

export interface KnowledgePathSuggestionStep {
  id: string
  label: string
  layer: 'project' | 'document' | 'knowledge_base' | string
  reason: string
  order?: number
  phase?: string
  estimated_minutes?: number
  evidence?: string[]
}

export interface KnowledgePathSuggestion {
  project_id?: number | null
  project_title: string
  strategy?: string
  dynamic_signals?: string[]
  steps: KnowledgePathSuggestionStep[]
}

export interface KnowledgeLinkGraphResponse {
  nodes: KnowledgeLinkNode[]
  edges: KnowledgeLinkEdge[]
  path_suggestions: KnowledgePathSuggestion[]
  attribution: string
  meta: Record<string, any>
}

export interface DatabaseNodeDetailResponse {
  name: string
  description: string
  citations: DatabaseCitation[]
  related_points: string[]
  suggested_questions: string[]
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
  if (!raw) return null
  try {
    return JSON.parse(raw) as User
  } catch {
    clearAuth()
    return null
  }
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

export function getCurrentUserSilently() {
  return api.get<User>('/auth/me', {
    timeout: 8000,
    skipErrorPopup: true
  })
}

export function updateCurrentUser(payload: Partial<User>) {
  return api.patch<User>('/auth/me', payload)
}

export function uploadCurrentUserAvatar(file: File) {
  const formData = new FormData()
  formData.append('file', file)
  return api.post<User>('/auth/me/avatar', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
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
      await showApiError({ method: 'POST', url: path, status: response.status, detail })
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
          const detail = stringifyErrorDetail(data.detail || data.msg || data.message || '未知错误')
          await showApiError({ method: 'POST', url: path, status: data.status || 'STREAM', detail, source: data })
          throw new Error(data.detail)
        }
      }
    }
  } catch (error) {
    if (!errorShown) {
      const detail = error instanceof Error ? error.message : String(error)
      await showApiError({ method: 'POST', url: path, status: 'NETWORK', detail, source: error })
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

export function parseProjectPlanAttachment(file: File) {
  const formData = new FormData()
  formData.append('file', file)
  return api.post<ParsedProjectPlanAttachment>('/project-plans/attachments/parse', formData, {
    timeout: GENERATION_TIMEOUT_MS
  })
}

export function listLearningProjects(options: { includeDeleted?: boolean } = {}) {
  return api.get<LearningProjectRead[]>('/learning-projects', {
    params: {
      include_deleted: options.includeDeleted || undefined
    }
  })
}

export function archiveLearningProject(projectId: number) {
  return api.post<LearningProjectRead>(`/learning-projects/${projectId}/archive`)
}

export function pauseLearningProject(projectId: number) {
  return api.post<LearningProjectRead>(`/learning-projects/${projectId}/pause`)
}

export function resumeLearningProject(projectId: number) {
  return api.post<LearningProjectRead>(`/learning-projects/${projectId}/resume`)
}

export function restoreLearningProject(projectId: number) {
  return api.post<LearningProjectRead>(`/learning-projects/${projectId}/restore`)
}

export function updateLearningProject(projectId: number, payload: Partial<{
  title: string
  learning_goal: string
  expected_output: string
  recommended_period: string
  daily_minutes: number
  study_weekends: boolean
  study_weekdays: number[]
  difficulty: string
  status: string
  deadline: string | null
  teacher_notes: string
}>) {
  return api.patch<LearningProjectRead>(`/learning-projects/${projectId}`, payload)
}

export function copyLearningProject(projectId: number) {
  return api.post<LearningProjectRead>(`/learning-projects/${projectId}/copy`)
}

export function deleteLearningProject(projectId: number) {
  return api.delete<void>(`/learning-projects/${projectId}`)
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

export function generateDailyPlan(projectId: number, payload: {
  start_date?: string
  daily_minutes?: number
  study_weekends?: boolean
  study_weekdays?: number[]
  title?: string
}) {
  return api.post<DailyPlanRead>(`/learning-projects/${projectId}/daily-plan/generate`, payload)
}

export function listDailyPlans(projectId: number, limit = 3) {
  return api.get<DailyPlanRead[]>(`/learning-projects/${projectId}/daily-plans`, { params: { limit } })
}

export function moveDailyPlanItem(itemId: number, plannedDate: string) {
  return api.patch<DailyPlanRead>(`/daily-plan-items/${itemId}/schedule`, {
    planned_date: plannedDate
  })
}

export function shiftDailyPlanItem(itemId: number, direction: 'next' | 'previous' = 'next') {
  return api.patch<DailyPlanRead>(`/daily-plan-items/${itemId}/shift`, { direction })
}

export function sendDailyPlanCoachMessage(planId: number, payload: {
  message: string
  active_item_id?: number | null
}) {
  return api.post<DailyPlanCoachResponse>(`/daily-plans/${planId}/coach`, payload, {
    timeout: GENERATION_TIMEOUT_MS
  })
}

export function updateSyllabusItemStatus(itemId: number, status: string, reason = '') {
  return api.post<SyllabusVersionRead>(`/syllabus-items/${itemId}/status`, { status, reason })
}

export function deleteSyllabusItem(itemId: number) {
  return api.delete<void>(`/syllabus-items/${itemId}`)
}

export function getOrCreateClassroomSession(itemId: number) {
  return api.post<ClassroomSessionRead>(`/syllabus-items/${itemId}/classroom`)
}

export function getClassroomSession(sessionId: number) {
  return api.get<ClassroomSessionRead>(`/classroom-sessions/${sessionId}`)
}

export function generateClassroomPpt(sessionId: number, instruction = '') {
  return api.post<ClassroomSessionRead>(`/classroom-sessions/${sessionId}/ppt`, { instruction })
}

export type ClassroomVisualizationKind = 'auto' | 'diagram' | 'simulation' | 'code' | 'timeline' | 'visualization3d'

export function generateClassroomVisualization(
  sessionId: number,
  payload: string | { instruction?: string; preferred_kind?: ClassroomVisualizationKind } = ''
) {
  const body = typeof payload === 'string'
    ? { instruction: payload, preferred_kind: 'auto' as ClassroomVisualizationKind }
    : { preferred_kind: 'auto' as ClassroomVisualizationKind, ...payload }
  return api.post<ClassroomSessionRead>(`/classroom-sessions/${sessionId}/visualization`, body, {
    timeout: GENERATION_TIMEOUT_MS
  })
}

export function generateClassroomVoice(sessionId: number, payload: {
  voice_name?: string
  speed?: number
  text_scope?: 'current_slide' | 'one_minute' | 'five_minutes' | 'all_slides'
  slide_index?: number
  page_context?: string
} = {}) {
  return api.post<ClassroomSessionRead>(`/classroom-sessions/${sessionId}/voice`, payload, {
    timeout: GENERATION_TIMEOUT_MS
  })
}

export function saveClassroomNote(sessionId: number, payload: {
  markdown: string
  slide_index?: number
  slide_title?: string
}) {
  return api.post<ClassroomSessionRead>(`/classroom-sessions/${sessionId}/notes`, payload)
}

export function sendClassroomDialogue(sessionId: number, payload: {
  message: string
  quick_action?: string
}) {
  return api.post<ClassroomDialogueResponse>(`/classroom-sessions/${sessionId}/dialogue`, payload, {
    timeout: GENERATION_TIMEOUT_MS
  })
}

export function submitClassroomQuiz(sessionId: number, answers: Record<string, string | string[]>) {
  return api.post<ClassroomSessionRead>(`/classroom-sessions/${sessionId}/quiz`, { answers })
}

export function completeClassroomSlides(sessionId: number, payload: {
  current_index: number
  total_slides: number
  visited_indices: number[]
}) {
  return api.post<ClassroomSessionRead>(`/classroom-sessions/${sessionId}/slides/complete`, payload)
}

export function submitClassroomPractice(sessionId: number, payload: {
  report: string
  artifact_url?: string
  key_result?: string
}) {
  return api.post<ClassroomSessionRead>(`/classroom-sessions/${sessionId}/practice`, payload)
}

export function submitClassroomReflection(sessionId: number, payload: {
  reflection: string
  unresolved_questions?: string[]
  next_action?: string
}) {
  return api.post<ClassroomSessionRead>(`/classroom-sessions/${sessionId}/reflection`, payload)
}

export function downloadClassroomResource(resourceId: number) {
  return api.get<Blob>(`/classroom-resources/${resourceId}/download`, {
    responseType: 'blob'
  })
}

export function viewClassroomResource(resourceId: number) {
  return api.get<Blob>(`/classroom-resources/${resourceId}/view`, {
    responseType: 'blob'
  })
}

export function getWorkspaceOverview() {
  return api.get<WorkspaceOverviewResponse>('/workspace/overview')
}

export function getProfileCenter() {
  return api.get<ProfileCenterResponse>('/workspace/profile')
}

export function updateProfileEntry(payload: {
  key: string
  value: any
  confidence?: number
  source?: string
  source_object_id?: string | null
  is_confirmed?: boolean
  is_enabled?: boolean
  update_reason?: string
}) {
  return api.patch<ProfileCenterResponse>('/workspace/profile/entries', payload)
}

export function deleteProfileEntry(key: string) {
  return api.delete<ProfileCenterResponse>(`/workspace/profile/entries/${encodeURIComponent(key)}`)
}

export function listLiterature() {
  return api.get<LiteraturePaperRead[]>('/workspace/literature')
}

export function createLiterature(payload: {
  project_id?: number | null
  title: string
  authors?: string[]
  venue?: string
  year?: string
  source_uri?: string
  abstract?: string
  keywords?: string[]
  reading_status?: string
  notes?: string
}) {
  return api.post<LiteraturePaperRead>('/workspace/literature', payload)
}

export function updateLiterature(paperId: number, payload: Partial<{
  title: string
  authors: string[]
  venue: string
  year: string
  source_uri: string
  abstract: string
  keywords: string[]
  reading_status: string
  notes: string
}>) {
  return api.patch<LiteraturePaperRead>(`/workspace/literature/${paperId}`, payload)
}

export function listResearchToolRuns() {
  return api.get<ResearchToolRunRead[]>('/workspace/research-tools/runs')
}

export function runResearchTool(payload: {
  project_id?: number | null
  tool_type: 'polish' | 'format' | 'citation' | 'review' | 'method' | 'experiment' | 'reproduce' | 'topic' | 'defense' | 'paper_reading'
  input_text: string
  extra_requirement?: string
}) {
  return api.post<ResearchToolRunRead>('/workspace/research-tools/run', payload, {
    timeout: GENERATION_TIMEOUT_MS
  })
}

export function listPracticePapers() {
  return api.get<PracticePaperRead[]>('/practice-papers')
}

export function listPracticeKnowledgeNodes(payload: {
  project_id?: number | null
  query?: string
  limit?: number
} = {}) {
  return api.get<PracticeKnowledgeNodeRead[]>('/practice-papers/knowledge-nodes', {
    params: {
      project_id: payload.project_id || undefined,
      query: payload.query || undefined,
      limit: payload.limit || 120
    }
  })
}

export function createPracticePaper(payload: {
  title: string
  description?: string
  project_id?: number | null
  selected_nodes: Record<string, any>[]
  question_types: string[]
  difficulty: 'easy' | 'medium' | 'hard'
  question_count: number
}) {
  return api.post<PracticePaperRead>('/practice-papers', payload, {
    timeout: GENERATION_TIMEOUT_MS
  })
}

export function getPracticePaper(paperId: number) {
  return api.get<PracticePaperRead>(`/practice-papers/${paperId}`)
}

export function submitPracticePaper(paperId: number, answers: Record<string, any>) {
  return api.post<PracticePaperSubmitResponse>(`/practice-papers/${paperId}/submit`, { answers })
}

export function deletePracticePaper(paperId: number) {
  return api.delete<void>(`/practice-papers/${paperId}`)
}

export function listKnowledgePoints() {
  return api.get<KnowledgePointRead[]>('/course/knowledge-points')
}

export function searchKnowledge(query: string, limit = 6) {
  return api.post<KnowledgeSearchHit[]>('/course/knowledge/search', { query, limit })
}

export function searchKnowledgeEnhanced(query: string, limit = 8) {
  return api.post<KnowledgeSearchHit[]>('/course/knowledge/search/enhanced', { query, limit }, {
    timeout: GENERATION_TIMEOUT_MS
  })
}

export function askDatabase(payload: {
  question: string
  project_id?: number | null
  knowledge_points?: string[]
  limit?: number
}) {
  return api.post<DatabaseAskResponse>('/database/ask', payload, {
    timeout: GENERATION_TIMEOUT_MS
  })
}

export function getDatabaseGraph(payload: {
  project_id?: number | null
  scope?: 'all' | 'project'
} = {}) {
  return api.get<DatabaseGraphResponse>('/database/graph', {
    params: payload
  })
}

export function getKnowledgeLinkGraph(payload: {
  project_id?: number | null
  query?: string
  limit?: number
} = {}) {
  return api.get<KnowledgeLinkGraphResponse>('/database/knowledge-links', {
    params: {
      project_id: payload.project_id || undefined,
      query: payload.query || undefined,
      limit: payload.limit || 140
    }
  })
}

export function getDatabaseNodeDetail(name: string, projectId?: number | null) {
  return api.get<DatabaseNodeDetailResponse>(`/database/nodes/${encodeURIComponent(name)}`, {
    params: { project_id: projectId || undefined }
  })
}

export function getDatabaseChunkReview(chunkId: number) {
  return api.get(`/database/chunks/${chunkId}/review`)
}

export function importKnowledgePackage(file: File, payload: {
  course_code?: string
  course_title?: string
  use_ocr?: boolean
  rebuild_course?: boolean
}) {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('course_code', payload.course_code || '')
  formData.append('course_title', payload.course_title || '')
  formData.append('use_ocr', String(Boolean(payload.use_ocr)))
  formData.append('rebuild_course', String(Boolean(payload.rebuild_course)))
  return api.post<KnowledgeImportJobRead>('/course/knowledge/import', formData, {
    timeout: 30 * 60 * 1000
  })
}

export function getKnowledgeStorageUsage() {
  return api.get<KnowledgeStorageUsageRead>('/course/knowledge/storage')
}

export function listKnowledgeImportJobs(limit = 20) {
  return api.get<KnowledgeImportJobRead[]>('/course/knowledge/import-jobs', { params: { limit } })
}

export function getKnowledgeImportJob(jobId: number) {
  return api.get<KnowledgeImportJobRead>(`/course/knowledge/import-jobs/${jobId}`)
}

export function deleteKnowledgeImportJob(jobId: number) {
  return api.delete<void>(`/course/knowledge/import-jobs/${jobId}`)
}

export function listKnowledgeDocuments(payload: {
  course_code?: string
  query?: string
  limit?: number
} = {}) {
  return api.get<KnowledgeDocumentRead[]>('/course/knowledge/documents', {
    params: {
      course_code: payload.course_code || undefined,
      query: payload.query || undefined,
      limit: payload.limit || 50
    }
  })
}

export function listKnowledgeDocumentChunks(documentId: number, limit = 100) {
  return api.get<KnowledgeChunkRead[]>(`/course/knowledge/documents/${documentId}/chunks`, {
    params: { limit }
  })
}

export function deleteKnowledgeDocument(documentId: number) {
  return api.delete<void>(`/course/knowledge/documents/${documentId}`)
}

export function rebuildKnowledgeEmbeddings(limit = 200) {
  return api.post<{ rebuilt: number }>('/course/knowledge/embeddings/rebuild', null, {
    params: { limit },
    timeout: 30 * 60 * 1000
  })
}

export function getModelSettings() {
  return api.get<UserModelSettingsRead>('/system/model-settings')
}

export function updateModelSettings(payload: UserModelSettingsUpdate) {
  return api.put<UserModelSettingsRead>('/system/model-settings', payload)
}

export function verifyModelSettings() {
  return api.post<{ ok: boolean; provider: string; model: string; message: string }>('/system/model-settings/verify')
}
