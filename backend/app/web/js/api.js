import { getState } from './store.js'

function emitApiError({ status = '-', statusText = '', path, method = 'GET', message }) {
  window.dispatchEvent(new CustomEvent('api-error', {
    detail: {
      status,
      statusText,
      path,
      method,
      message
    }
  }))
}

export async function request(path, options = {}) {
  const token = getState().token
  const method = options.method || 'GET'
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {})
  }
  if (token) {
    headers.Authorization = `Bearer ${token}`
  }

  let response
  try {
    response = await fetch(path, {
      headers,
      ...options
    })
  } catch (error) {
    const message = error.message || '网络请求失败'
    emitApiError({ status: 'NETWORK', path, method, message })
    throw error
  }

  if (!response.ok) {
    const text = await response.text()
    let detail = text
    try {
      const payload = JSON.parse(text)
      detail = payload.detail || text
    } catch {
      detail = text
    }
    const error = new Error(detail)
    error.status = response.status
    error.statusText = response.statusText
    error.path = path
    error.method = method
    emitApiError({
      status: response.status,
      statusText: response.statusText,
      path,
      method,
      message: detail
    })
    throw error
  }
  if (response.status === 204) {
    return null
  }
  const responseText = await response.text()
  return responseText ? JSON.parse(responseText) : null
}

export function registerUser(payload) {
  return request('/api/auth/register', {
    method: 'POST',
    body: JSON.stringify(payload)
  })
}

export function loginUser(payload) {
  return request('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify(payload)
  })
}

export function getCurrentUser() {
  return request('/api/auth/me')
}

export function updateCurrentUser(payload) {
  return request('/api/auth/me', {
    method: 'PATCH',
    body: JSON.stringify(payload)
  })
}

export function getDirectionTemplates() {
  return request('/api/direction-templates')
}

export function analyzeDirection(payload) {
  return request('/api/directions/analyze', {
    method: 'POST',
    body: JSON.stringify(payload)
  })
}

export function createDirection(payload) {
  return request('/api/directions', {
    method: 'POST',
    body: JSON.stringify(payload)
  })
}

export function getDirections() {
  return request('/api/directions')
}

export function regenerateDirection(directionId) {
  return request(`/api/directions/${directionId}/regenerate`, { method: 'POST' })
}

export function createLearningProject(payload) {
  return request('/api/learning-projects', {
    method: 'POST',
    body: JSON.stringify(payload)
  })
}

export function getLearningProjects() {
  return request('/api/learning-projects')
}

export function getLearningProjectHome(projectId) {
  return request(`/api/learning-projects/${projectId}/home`)
}

export function updateLearningProject(projectId, payload) {
  return request(`/api/learning-projects/${projectId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload)
  })
}

export function archiveLearningProject(projectId) {
  return request(`/api/learning-projects/${projectId}/archive`, { method: 'POST' })
}

export function pauseLearningProject(projectId) {
  return request(`/api/learning-projects/${projectId}/pause`, { method: 'POST' })
}

export function resumeLearningProject(projectId) {
  return request(`/api/learning-projects/${projectId}/resume`, { method: 'POST' })
}

export function requestSyllabusRegeneration(projectId) {
  return generateSyllabus(projectId, { generation_goal: '根据当前项目目标重新生成完整学习清单' })
}

export function copyLearningProject(projectId) {
  return request(`/api/learning-projects/${projectId}/copy`, { method: 'POST' })
}

export function shareLearningProject(projectId) {
  return request(`/api/learning-projects/${projectId}/share`, { method: 'POST' })
}

export function exportLearningProject(projectId) {
  return request(`/api/learning-projects/${projectId}/export`)
}

export function startWorkflow(message) {
  return request('/api/workflow/start', {
    method: 'POST',
    body: JSON.stringify({ message })
  })
}

export function createDialogueProfile(message) {
  return request('/api/profile/dialogue', {
    method: 'POST',
    body: JSON.stringify({ message })
  })
}

export function searchKnowledge(query, limit = 6) {
  return request('/api/course/knowledge/search', {
    method: 'POST',
    body: JSON.stringify({ query, limit })
  })
}

export function askTutor({ sessionId, question, profile }) {
  return request('/api/tutor', {
    method: 'POST',
    body: JSON.stringify({
      session_id: sessionId,
      question,
      profile
    })
  })
}

export function submitAssessment({ sessionId, answers }) {
  return request('/api/assessments', {
    method: 'POST',
    body: JSON.stringify({
      session_id: sessionId,
      answers
    })
  })
}

export function getWorkflow(sessionId) {
  return request(`/api/workflow/${sessionId}`)
}

export function getTeacherDashboard() {
  return request('/api/teacher/dashboard')
}

export function generateSyllabus(projectId, payload = {}) {
  return request(`/api/learning-projects/${projectId}/syllabus/generate`, {
    method: 'POST',
    body: JSON.stringify(payload)
  })
}

export function getCurrentSyllabus(projectId) {
  return request(`/api/learning-projects/${projectId}/syllabus`)
}

export function getSyllabusVersions(projectId) {
  return request(`/api/learning-projects/${projectId}/syllabus/versions`)
}

export function getSyllabusVersion(versionId) {
  return request(`/api/syllabus-versions/${versionId}`)
}

export function activateSyllabusVersion(versionId) {
  return request(`/api/syllabus-versions/${versionId}/activate`, { method: 'POST' })
}

export function copySyllabusVersion(versionId) {
  return request(`/api/syllabus-versions/${versionId}/copy`, { method: 'POST' })
}

export function compareSyllabusVersions(baseVersionId, targetVersionId) {
  return request(`/api/syllabus-versions/${baseVersionId}/compare/${targetVersionId}`)
}

export function addSyllabusItem(versionId, payload) {
  return request(`/api/syllabus-versions/${versionId}/items`, {
    method: 'POST',
    body: JSON.stringify(payload)
  })
}

export function updateSyllabusItem(itemId, payload) {
  return request(`/api/syllabus-items/${itemId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload)
  })
}

export function deleteSyllabusItem(itemId) {
  return request(`/api/syllabus-items/${itemId}`, { method: 'DELETE' })
}

export function reorderSyllabusItems(versionId, itemIds) {
  return request(`/api/syllabus-versions/${versionId}/reorder`, {
    method: 'POST',
    body: JSON.stringify({ item_ids: itemIds })
  })
}

export function updateSyllabusItemStatus(itemId, status, reason = '') {
  return request(`/api/syllabus-items/${itemId}/status`, {
    method: 'POST',
    body: JSON.stringify({ status, reason })
  })
}

export function splitSyllabusItem(itemId, payload) {
  return request(`/api/syllabus-items/${itemId}/split`, {
    method: 'POST',
    body: JSON.stringify(payload)
  })
}

export function mergeSyllabusItems(payload) {
  return request('/api/syllabus-items/merge', {
    method: 'POST',
    body: JSON.stringify(payload)
  })
}

export function regenerateSyllabusStage(versionId, payload) {
  return request(`/api/syllabus-versions/${versionId}/regenerate-stage`, {
    method: 'POST',
    body: JSON.stringify(payload)
  })
}

export function adaptSyllabus(projectId, payload) {
  return request(`/api/learning-projects/${projectId}/syllabus/adapt`, {
    method: 'POST',
    body: JSON.stringify(payload)
  })
}

export function generateDailyPlan(projectId, payload = {}) {
  return request(`/api/learning-projects/${projectId}/daily-plan/generate`, {
    method: 'POST',
    body: JSON.stringify(payload)
  })
}

export function getDailyPlans(projectId) {
  return request(`/api/learning-projects/${projectId}/daily-plans`)
}
