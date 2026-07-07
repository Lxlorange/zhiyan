const state = {
  workflow: null,
  dashboard: null,
  token: localStorage.getItem('access_token'),
  user: JSON.parse(localStorage.getItem('current_user') || 'null')
}

export function getState() {
  return state
}

export function setWorkflow(workflow) {
  state.workflow = workflow
}

export function patchWorkflow(patch) {
  state.workflow = {
    ...state.workflow,
    ...patch
  }
}

export function setDashboard(dashboard) {
  state.dashboard = dashboard
}

export function setAuth({ access_token, user }) {
  state.token = access_token
  state.user = user
  localStorage.setItem('access_token', access_token)
  localStorage.setItem('current_user', JSON.stringify(user))
}

export function clearAuth() {
  state.token = null
  state.user = null
  localStorage.removeItem('access_token')
  localStorage.removeItem('current_user')
}
