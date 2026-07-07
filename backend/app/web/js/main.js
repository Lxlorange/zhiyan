import {
  analyzeDirection,
  askTutor,
  archiveLearningProject,
  copyLearningProject,
  createDirection,
  createDialogueProfile,
  createLearningProject,
  exportLearningProject,
  getDirections,
  getDirectionTemplates,
  getCurrentUser,
  getLearningProjectHome,
  getLearningProjects,
  getTeacherDashboard,
  getWorkflow,
  loginUser,
  pauseLearningProject,
  registerUser,
  regenerateDirection,
  resumeLearningProject,
  requestSyllabusRegeneration,
  searchKnowledge,
  shareLearningProject,
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
  renderDirectionAnalysis,
  renderDirectionProgress,
  renderDirectionTemplates,
  renderDialogueProfile,
  renderKnowledgeSearch,
  renderLearningProjects,
  renderMetrics,
  renderProjectExport,
  renderProjectHome,
  renderProfile,
  renderSavedDirections,
  renderTeacherDashboard,
  renderTrace,
  renderTutor,
  resetTutorAndAssessment,
  setBusy
} from './renderers.js'

const $ = (selector) => document.querySelector(selector)

const APP_ROUTES = {
  '/app/directions': {
    view: '#directionsPage',
    title: '探索方向',
    subtitle: '从科研方向生成可持续学习项目'
  },
  '/app/projects': {
    view: '#projectsPage',
    title: '学习项目',
    subtitle: '管理方向、目标、阶段和项目首页'
  },
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

let latestDirectionAnalysis = null

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
    routeTo('/app/directions')
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
    if (route === '/app/directions') loadDirectionTemplates()
    if (route === '/app/projects') loadDirectionsAndProjects()
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

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, (char) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;'
  })[char])
}

function showApiErrorModal(error) {
  const modal = $('#apiErrorModal')
  const content = $('#apiErrorContent')
  if (!modal || !content) return
  const status = escapeHtml(error.status || '-')
  const statusText = escapeHtml(error.statusText || '')
  const method = escapeHtml(error.method || 'GET')
  const path = escapeHtml(error.path || '-')
  const message = escapeHtml(error.message || '未知错误')
  content.innerHTML = `
    <p><strong>状态码：</strong>${status} ${statusText}</p>
    <p><strong>接口：</strong>${method} ${path}</p>
    <p><strong>错误信息：</strong></p>
    <code>${message}</code>
  `
  modal.classList.add('active')
  modal.setAttribute('aria-hidden', 'false')
}

function hideApiErrorModal() {
  const modal = $('#apiErrorModal')
  if (!modal) return
  modal.classList.remove('active')
  modal.setAttribute('aria-hidden', 'true')
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
  } catch (error) {
    renderAuthMessage(`AI 链路执行失败：${error.message}`)
  } finally {
    setBusy(button, false)
  }
}

async function loadDirectionTemplates() {
  try {
    renderDirectionTemplates(await getDirectionTemplates())
  } catch (error) {
    renderAuthMessage(`方向模板加载失败：${error.message}`)
  }
}

async function loadDirectionsAndProjects() {
  try {
    const directions = await getDirections()
    const projects = await getLearningProjects()
    renderSavedDirections(directions)
    renderLearningProjects(projects)
  } catch (error) {
    renderAuthMessage(`学习项目加载失败：${error.message}`)
  }
}

function readDirectionPayload() {
  const templateId = $('#directionTemplateSelect').value
  return {
    message: $('#directionInput').value,
    template_id: templateId ? Number(templateId) : null,
    extra_context: $('#directionExtraInput').value
  }
}

async function handleAnalyzeDirection() {
  ensureAuthenticated()
  const button = $('#analyzeDirectionBtn')
  setBusy(button, true)
  renderDirectionProgress('DirectionAgent 正在读取画像、模板和课程知识库...', 'running')
  try {
    latestDirectionAnalysis = await analyzeDirection(readDirectionPayload())
    renderDirectionAnalysis(latestDirectionAnalysis)
    renderDirectionProgress('方向理解完成，可保存为学习项目方向。', 'done')
  } catch (error) {
    renderAuthMessage(`方向分析失败：${error.message}`)
    renderDirectionProgress('方向理解失败，请查看接口错误弹窗。', 'error')
  } finally {
    setBusy(button, false)
  }
}

async function handleSaveDirection() {
  ensureAuthenticated()
  const button = $('#saveDirectionBtn')
  setBusy(button, true)
  renderDirectionProgress('正在保存方向并写入 Agent 轨迹...', 'running')
  try {
    await createDirection(readDirectionPayload())
    latestDirectionAnalysis = null
    renderDirectionProgress('方向已保存，进入学习项目管理。', 'done')
    await loadDirectionsAndProjects()
    routeTo('/app/projects')
  } catch (error) {
    renderAuthMessage(`方向保存失败：${error.message}`)
    renderDirectionProgress('方向保存失败，请查看接口错误弹窗。', 'error')
  } finally {
    setBusy(button, false)
  }
}

async function handleProjectsClick(event) {
  const button = event.target.closest('button')
  if (!button) return
  try {
    if (button.classList.contains('create-project-btn')) {
      const project = await createLearningProject({ direction_id: Number(button.dataset.directionId) })
      await loadDirectionsAndProjects()
      renderProjectHome(await getLearningProjectHome(project.id))
      return
    }
    if (button.classList.contains('regenerate-direction-btn')) {
      await regenerateDirection(Number(button.dataset.directionId))
      await loadDirectionsAndProjects()
      return
    }
    const projectId = Number(button.dataset.projectId)
    if (!projectId) return
    if (button.classList.contains('project-home-btn')) {
      renderProjectHome(await getLearningProjectHome(projectId))
    } else if (button.classList.contains('project-pause-btn')) {
      await pauseLearningProject(projectId)
      await loadDirectionsAndProjects()
    } else if (button.classList.contains('project-resume-btn')) {
      await resumeLearningProject(projectId)
      await loadDirectionsAndProjects()
    } else if (button.classList.contains('project-regenerate-syllabus-btn')) {
      const project = await requestSyllabusRegeneration(projectId)
      await loadDirectionsAndProjects()
      renderProjectHome(await getLearningProjectHome(project.id))
    } else if (button.classList.contains('project-copy-btn')) {
      await copyLearningProject(projectId)
      await loadDirectionsAndProjects()
    } else if (button.classList.contains('project-share-btn')) {
      const project = await shareLearningProject(projectId)
      await loadDirectionsAndProjects()
      renderProjectHome(await getLearningProjectHome(project.id))
    } else if (button.classList.contains('project-export-btn')) {
      renderProjectExport(await exportLearningProject(projectId))
    } else if (button.classList.contains('project-archive-btn')) {
      await archiveLearningProject(projectId)
      await loadDirectionsAndProjects()
    }
  } catch (error) {
    renderAuthMessage(`项目操作失败：${error.message}`)
  }
}

async function handleDialogueProfile() {
  ensureAuthenticated()
  const button = $('#profileDialogueBtn')
  setBusy(button, true)
  try {
    const result = await createDialogueProfile($('#profileDialogueInput').value)
    const workflow = getState().workflow
    if (workflow) {
      patchWorkflow({ profile: result.profile })
      renderProfile(getState().workflow)
      renderMetrics(getState().workflow)
    } else {
      setWorkflow({
        session_id: 'profile-only',
        profile: result.profile,
        gaps: [],
        path: [],
        resources: [],
        quiz: [],
        agent_trace: []
      })
      renderProfile(getState().workflow)
      renderMetrics(getState().workflow)
    }
    renderDialogueProfile(result)
  } catch (error) {
    renderAuthMessage(`画像生成失败：${error.message}`)
  } finally {
    setBusy(button, false)
  }
}

async function handleKnowledgeSearch() {
  ensureAuthenticated()
  const button = $('#knowledgeSearchBtn')
  setBusy(button, true)
  try {
    const hits = await searchKnowledge($('#knowledgeSearchInput').value)
    renderKnowledgeSearch(hits)
  } catch (error) {
    renderAuthMessage(`知识库检索失败：${error.message}`)
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
  } catch (error) {
    renderAuthMessage(`智能辅导失败：${error.message}`)
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
  } catch (error) {
    renderAuthMessage(`练习评估失败：${error.message}`)
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
    routeTo('/app/directions')
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
    routeTo('/app/directions')
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
  $('#analyzeDirectionBtn').addEventListener('click', handleAnalyzeDirection)
  $('#saveDirectionBtn').addEventListener('click', handleSaveDirection)
  $('#savedDirectionsView').addEventListener('click', handleProjectsClick)
  $('#learningProjectsView').addEventListener('click', handleProjectsClick)
  $('#profileDialogueBtn').addEventListener('click', handleDialogueProfile)
  $('#knowledgeSearchBtn').addEventListener('click', handleKnowledgeSearch)
  $('#askBtn').addEventListener('click', handleAskTutor)
  $('#submitQuizBtn').addEventListener('click', handleSubmitQuiz)
  $('#loginBtn').addEventListener('click', handleLogin)
  $('#registerBtn').addEventListener('click', handleRegister)
  $('#logoutBtn').addEventListener('click', handleLogout)
  $('#apiErrorCloseBtn').addEventListener('click', hideApiErrorModal)
  $('#apiErrorModal').addEventListener('click', (event) => {
    if (event.target.id === 'apiErrorModal') hideApiErrorModal()
  })
  window.addEventListener('hashchange', renderRoute)
  window.addEventListener('api-error', (event) => showApiErrorModal(event.detail))
  window.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') hideApiErrorModal()
  })
}

bindEvents()
renderRoute()
hydrateAuth()
