import { getState } from './store.js'

export async function request(path, options = {}) {
  const token = getState().token
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {})
  }
  if (token) {
    headers.Authorization = `Bearer ${token}`
  }

  const response = await fetch(path, {
    headers,
    ...options
  })
  if (!response.ok) {
    throw new Error(await response.text())
  }
  return response.json()
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

export function startWorkflow(message) {
  return request('/api/workflow/start', {
    method: 'POST',
    body: JSON.stringify({ message })
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
