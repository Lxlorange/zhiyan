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
    if (error.config?.skipErrorPopup) return Promise.reject(error)

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

export interface ProfileDialogueResponse {
  profile_id: number
  profile: Record<string, any>
  update_reason: string
  extracted_features: Record<string, any>
  revision: number
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

export interface DashboardMetric {
  label: string
  value: string
  trend: string
}

export interface TeacherDashboardResponse {
  metrics: DashboardMetric[]
  weak_point_distribution: Record<string, number>
  resource_type_distribution: Record<string, number>
  at_risk_students: Array<{
    session_id: string
    title: string
    profile_revision: number
    weak_points: string[]
  }>
  teaching_suggestions: string[]
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

export function listDailyPlans(projectId: number) {
  return api.get<DailyPlanRead[]>(`/learning-projects/${projectId}/daily-plans`)
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

export function updateProfileByDialogue(message: string) {
  return api.post<ProfileDialogueResponse>('/profile/dialogue', { message }, {
    timeout: GENERATION_TIMEOUT_MS
  })
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

export function importKnowledgePackage(file: File, payload: {
  course_code?: string
  course_title?: string
  use_ocr?: boolean
  rebuild_course?: boolean
}) {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('course_code', payload.course_code || 'IMPORTED-COURSEWARE')
  formData.append('course_title', payload.course_title || '导入课程课件知识库')
  formData.append('use_ocr', String(Boolean(payload.use_ocr)))
  formData.append('rebuild_course', String(Boolean(payload.rebuild_course)))
  return api.post<KnowledgeImportJobRead>('/course/knowledge/import', formData, {
    timeout: 30 * 60 * 1000
  })
}

export function listKnowledgeImportJobs(limit = 20) {
  return api.get<KnowledgeImportJobRead[]>('/course/knowledge/import-jobs', { params: { limit } })
}

export function getKnowledgeImportJob(jobId: number) {
  return api.get<KnowledgeImportJobRead>(`/course/knowledge/import-jobs/${jobId}`)
}

export function rebuildKnowledgeEmbeddings(limit = 200) {
  return api.post<{ rebuilt: number }>('/course/knowledge/embeddings/rebuild', null, {
    params: { limit },
    timeout: 30 * 60 * 1000
  })
}

export function getTeacherDashboard() {
  return api.get<TeacherDashboardResponse>('/teacher/dashboard')
}
