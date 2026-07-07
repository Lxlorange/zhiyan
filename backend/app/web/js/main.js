import {
  askTutor,
  getCurrentUser,
  getTeacherDashboard,
  getWorkflow,
  loginUser,
  registerUser,
  startWorkflow,
  submitAssessment
} from './api.js'
import { clearAuth, getState, patchWorkflow, setAuth, setDashboard, setWorkflow } from './store.js'
import {
  initButtonLabels,
  readQuizAnswers,
  renderAll,
  renderAssessment,
  renderAuthMessage,
  renderCurrentUser,
  renderTeacherDashboard,
  renderTrace,
  renderTutor,
  resetTutorAndAssessment,
  setBusy
} from './renderers.js'

const $ = (selector) => document.querySelector(selector)

const APP_ROUTES = {
  '/app/workbench': {
    view: '#workbenchView',
    title: '学习工作台',
    subtitle: '从对话输入启动完整学习闭环'
  },
  '/app/profile': {
    view: '#profilePage',
    title: '学习画像',
    subtitle: '画像构建与知识短板诊断'
  },
  '/app/path': {
    view: '#pathPage',
    title: '学习路径',
    subtitle: '动态路径规划与 Agent 协作轨迹'
  },
  '/app/resources': {
    view: '#resourcesPage',
    title: '资源中心',
    subtitle: '多 Agent 个性化资源生成'
  },
  '/app/tutor': {
    view: '#tutorPage',
    title: '智能辅导',
    subtitle: '围绕当前画像即时答疑'
  },
  '/app/assessment': {
    view: '#assessmentPage',
    title: '练习评估',
    subtitle: '提交练习并更新动态画像'
  },
  '/app/teacher': {
    view: '#teacherPage',
    title: '教师驾驶舱',
    subtitle: '班级统计、短板分布与教学建议'
  }
}

function getRoute() {
  return location.hash.replace(/^#/, '') || '/home'
}

function routeTo(path) {
  if (getRoute() === path) {
    renderRoute()
    return
  }
  location.hash = path
}

function setBodyMode(mode) {
  document.body.className = `${mode}-mode`
}

function setActiveView(selector) {
  document.querySelectorAll('.view, .page-view').forEach((node) => {
    node.classList.remove('active')
  })
  const node = $(selector)
  if (node) node.classList.add('active')
}

function setActiveAuthTab(route) {
  $('#signinTab')?.classList.toggle('active', route === '/signin')
  $('#registerTab')?.classList.toggle('active', route === '/register')
  $('#signinPanel')?.classList.toggle('active', route === '/signin')
  $('#registerPanel')?.classList.toggle('active', route === '/register')
  $('#authTitle').textContent = route === '/register' ? '创建账号后进入学习工作台' : '登录后进入你的学习工作台'
  $('#authSubtitle').textContent = route === '/register'
    ? '注册页只处理账号创建，不展示平台侧边栏。注册成功后自动进入工作台。'
    : '登录页是独立入口，不展示平台侧边栏。进入后再按学习流程切换不同页面。'
}

function setActiveSideNav(route) {
  document.querySelectorAll('.side-nav a[data-route]').forEach((link) => {
    link.classList.toggle('active', link.dataset.route === route)
  })
}

function renderRoute() {
  let route = getRoute()
  const isAuthed = Boolean(getState().token)

  if (route === '/' || route === '') {
    route = '/home'
  }

  if (route.startsWith('/app') && !isAuthed) {
    routeTo('/signin')
    return
  }

  if (isAuthed && (route === '/signin' || route === '/register')) {
    routeTo('/app/workbench')
    return
  }

  if (route === '/signin' || route === '/register') {
    setBodyMode('auth')
    setActiveView('#auth')
    setActiveAuthTab(route)
    return
  }

  if (route.startsWith('/app')) {
    const config = APP_ROUTES[route] || APP_ROUTES['/app/workbench']
    setBodyMode('app')
    setActiveView(config.view)
    setActiveSideNav(APP_ROUTES[route] ? route : '/app/workbench')
    $('#topbarTitle').textContent = config.title
    $('#topbarSubtitle').textContent = config.subtitle
    return
  }

  setBodyMode('public')
  setActiveView('#publicHome')
}

function ensureAuthenticated() {
  if (!getState().token) {
    renderCurrentUser(null)
    routeTo('/signin')
    throw new Error('请先登录或注册')
  }
}

async function handleStartWorkflow() {
  ensureAuthenticated()
  const button = document.activeElement?.id === 'startInlineBtn' ? $('#startInlineBtn') : $('#startBtn')
  setBusy(button, true)
  try {
    const workflow = await startWorkflow($('#studentInput').value)
    setWorkflow(workflow)
    const dashboard = await getTeacherDashboard()
    setDashboard(dashboard)
    resetTutorAndAssessment()
    renderAll(workflow)
    renderTeacherDashboard(dashboard)
    routeTo('/app/profile')
  } finally {
    setBusy(button, false)
  }
}

async function handleAskTutor() {
  ensureAuthenticated()
  if (!getState().workflow) {
    await handleStartWorkflow()
    routeTo('/app/tutor')
  }
  const workflow = getState().workflow
  const button = $('#askBtn')
  setBusy(button, true)
  try {
    const tutor = await askTutor({
      sessionId: workflow.session_id,
      question: $('#questionInput').value,
      profile: workflow.profile
    })
    patchWorkflow({ tutor })
    renderTutor(tutor)
    const latest = await getWorkflow(workflow.session_id)
    patchWorkflow({ agent_trace: latest.agent_trace })
    renderTrace(getState().workflow)
  } finally {
    setBusy(button, false)
  }
}

async function handleSubmitQuiz() {
  ensureAuthenticated()
  const workflow = getState().workflow
  if (!workflow) {
    routeTo('/app/workbench')
    return
  }
  const button = $('#submitQuizBtn')
  setBusy(button, true)
  try {
    const assessment = await submitAssessment({
      sessionId: workflow.session_id,
      answers: readQuizAnswers(workflow)
    })
    const latest = await getWorkflow(workflow.session_id)
    setWorkflow({ ...latest, assessment })
    const dashboard = await getTeacherDashboard()
    setDashboard(dashboard)
    renderAll(getState().workflow)
    renderAssessment(assessment)
    renderTeacherDashboard(dashboard)
  } finally {
    setBusy(button, false)
  }
}

async function handleLogin() {
  const button = $('#loginBtn')
  setBusy(button, true)
  renderAuthMessage('')
  try {
    const token = await loginUser({
      username: $('#loginUsername').value,
      password: $('#loginPassword').value
    })
    setAuth(token)
    renderCurrentUser(token.user)
    renderAuthMessage('')
    routeTo('/app/workbench')
  } catch (error) {
    renderAuthMessage('登录失败：请检查用户名和密码。')
  } finally {
    setBusy(button, false)
  }
}

async function handleRegister() {
  const button = $('#registerBtn')
  setBusy(button, true)
  renderAuthMessage('')
  try {
    const token = await registerUser({
      username: $('#registerUsername').value,
      email: $('#registerEmail').value,
      full_name: $('#registerFullName').value,
      role: $('#registerRole').value,
      password: $('#registerPassword').value
    })
    setAuth(token)
    renderCurrentUser(token.user)
    renderAuthMessage('')
    routeTo('/app/workbench')
  } catch (error) {
    renderAuthMessage('注册失败：用户名或邮箱可能已存在，可尝试直接登录。')
  } finally {
    setBusy(button, false)
  }
}

function handleLogout() {
  clearAuth()
  setWorkflow(null)
  renderCurrentUser(null)
  renderRoute()
  routeTo('/home')
}

async function hydrateAuth() {
  if (!getState().token) {
    renderCurrentUser(null)
    renderRoute()
    return
  }
  try {
    const user = await getCurrentUser()
    setAuth({ access_token: getState().token, user })
    renderCurrentUser(user)
  } catch {
    clearAuth()
    renderCurrentUser(null)
  }
  renderRoute()
}

function bindEvents() {
  initButtonLabels()
  renderCurrentUser(getState().user)
  $('#startBtn').addEventListener('click', handleStartWorkflow)
  $('#startInlineBtn').addEventListener('click', handleStartWorkflow)
  $('#askBtn').addEventListener('click', handleAskTutor)
  $('#submitQuizBtn').addEventListener('click', handleSubmitQuiz)
  $('#loginBtn').addEventListener('click', handleLogin)
  $('#registerBtn').addEventListener('click', handleRegister)
  $('#logoutBtn').addEventListener('click', handleLogout)
  window.addEventListener('hashchange', renderRoute)
}

bindEvents()
renderRoute()
hydrateAuth()
