import {
  activateSyllabusVersion,
  adaptSyllabus,
  addSyllabusItem,
  analyzeDirection,
  askTutor,
  archiveLearningProject,
  copySyllabusVersion,
  copyLearningProject,
  createDirection,
  createDialogueProfile,
  createLearningProject,
  deleteSyllabusItem,
  exportLearningProject,
  generateDailyPlan,
  generateSyllabus,
  compareSyllabusVersions,
  getCurrentSyllabus,
  getDailyPlans,
  getDirections,
  getDirectionTemplates,
  getCurrentUser,
  getLearningProjectHome,
  getLearningProjects,
  getSyllabusVersion,
  getSyllabusVersions,
  getTeacherDashboard,
  getWorkflow,
  loginUser,
  pauseLearningProject,
  registerUser,
  regenerateDirection,
  reorderSyllabusItems,
  resumeLearningProject,
  requestSyllabusRegeneration,
  searchKnowledge,
  shareLearningProject,
  splitSyllabusItem,
  mergeSyllabusItems,
  regenerateSyllabusStage,
  startWorkflow,
  submitAssessment,
  updateSyllabusItem,
  updateSyllabusItemStatus,
  updateCurrentUser
} from './api.js'
import { clearAuth, getState, patchWorkflow, setAuth, setDashboard, setWorkflow } from './store.js'
import {
  initButtonLabels,
  readQuizAnswers,
  renderAll,
  renderAssessment,
  renderAuthMessage,
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
  renderSettings,
  renderDailyPlans,
  renderSyllabus,
  renderSyllabusProjects,
  renderSyllabusTrace,
  renderSyllabusVersions,
  renderTeacherDashboard,
  renderTrace,
  renderTutor,
  renderUserShell,
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
  },
  '/app/settings': {
    view: '#settingsPage',
    title: '账号设置',
    subtitle: '管理头像、姓名、学校专业与个人简介'
  }
}

let latestDirectionAnalysis = null
let selectedSyllabusProjectId = null
let currentSyllabus = null
let currentSyllabusVersions = []
let currentDailyPlans = []

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
    if (route === '/app/path') loadSyllabusWorkspace()
    if (route === '/app/settings') renderSettings(getState().user)
    return
  }

  setBodyMode('public')
  setActiveView('#publicHome')
}

function ensureAuthenticated() {
  if (!getState().token) {
    renderUserShell(null)
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

async function loadSyllabusWorkspace(projectId = selectedSyllabusProjectId) {
  ensureAuthenticated()
  try {
    const projects = await getLearningProjects()
    selectedSyllabusProjectId = projectId || projects[0]?.id || null
    renderSyllabusProjects(projects, selectedSyllabusProjectId)
    if (!selectedSyllabusProjectId) {
      currentSyllabus = null
      currentSyllabusVersions = []
      currentDailyPlans = []
      renderSyllabus(null)
      renderSyllabusVersions([])
      renderDailyPlans([])
      renderSyllabusTrace(null)
      return
    }
    await refreshSyllabusData()
  } catch (error) {
    renderAuthMessage(`学习清单工作台加载失败：${error.message}`)
  }
}

async function refreshSyllabusData() {
  if (!selectedSyllabusProjectId) return
  try {
    currentSyllabusVersions = await getSyllabusVersions(selectedSyllabusProjectId)
  } catch {
    currentSyllabusVersions = []
  }
  try {
    currentSyllabus = await getCurrentSyllabus(selectedSyllabusProjectId)
  } catch {
    currentSyllabus = null
  }
  try {
    currentDailyPlans = await getDailyPlans(selectedSyllabusProjectId)
  } catch {
    currentDailyPlans = []
  }
  renderSyllabusVersions(currentSyllabusVersions, currentSyllabus?.id)
  renderSyllabus(currentSyllabus)
  renderDailyPlans(currentDailyPlans)
  renderSyllabusTrace(currentSyllabus)
}

function requireCurrentSyllabus() {
  if (!currentSyllabus) {
    throw new Error('请先生成或选择一个学习清单版本')
  }
  return currentSyllabus
}

async function handleGenerateSyllabus() {
  ensureAuthenticated()
  if (!selectedSyllabusProjectId) return
  const button = $('#generateSyllabusBtn')
  setBusy(button, true)
  try {
    const goal = window.prompt('本次清单生成目标', '围绕当前科研方向生成完整学习清单')
    currentSyllabus = await generateSyllabus(selectedSyllabusProjectId, {
      generation_goal: goal || '围绕当前科研方向生成完整学习清单'
    })
    await refreshSyllabusData()
  } catch (error) {
    renderAuthMessage(`生成学习清单失败：${error.message}`)
  } finally {
    setBusy(button, false)
  }
}

async function handleCopySyllabus() {
  ensureAuthenticated()
  const version = requireCurrentSyllabus()
  const button = $('#copySyllabusBtn')
  setBusy(button, true)
  try {
    currentSyllabus = await copySyllabusVersion(version.id)
    await refreshSyllabusData()
  } catch (error) {
    renderAuthMessage(`复制清单版本失败：${error.message}`)
  } finally {
    setBusy(button, false)
  }
}

async function handleActivateSyllabus() {
  ensureAuthenticated()
  const version = requireCurrentSyllabus()
  const button = $('#activateSyllabusBtn')
  setBusy(button, true)
  try {
    currentSyllabus = await activateSyllabusVersion(version.id)
    await refreshSyllabusData()
  } catch (error) {
    renderAuthMessage(`设置当前版本失败：${error.message}`)
  } finally {
    setBusy(button, false)
  }
}

async function handleCompareSyllabus() {
  ensureAuthenticated()
  const button = $('#compareSyllabusBtn')
  setBusy(button, true)
  try {
    if (currentSyllabusVersions.length < 2) {
      throw new Error('至少需要两个版本才能比较')
    }
    const [latest, previous] = currentSyllabusVersions
    const result = await compareSyllabusVersions(previous.id, latest.id)
    renderAuthMessage(
      `版本比较：新增 ${result.added.length} 项，移除 ${result.removed.length} 项，变更 ${result.changed.length} 项。`,
      'success'
    )
  } catch (error) {
    renderAuthMessage(`比较版本失败：${error.message}`)
  } finally {
    setBusy(button, false)
  }
}

async function handleAddSyllabusItem() {
  ensureAuthenticated()
  const version = requireCurrentSyllabus()
  const button = $('#addSyllabusItemBtn')
  setBusy(button, true)
  try {
    const title = window.prompt('新增学习项标题', '补充论文精读与复现实验记录')
    if (!title) return
    currentSyllabus = await addSyllabusItem(version.id, {
      title,
      item_type: 'paper_reading',
      stage: '补充学习',
      difficulty: 'medium',
      estimated_minutes: 45,
      recommendation_reason: '用户根据科研方向手动补充',
      objective: `围绕“${title}”补齐背景、方法和实践记录`,
      prerequisites: [],
      knowledge_points: [],
      related_documents: [],
      recommended_resource_types: ['讲解文档', '论文笔记'],
      classroom_types: ['总结讲解', '引导性提问'],
      completion_criteria: '形成一页学习笔记或复现记录',
      assessment_method: '通过课堂追问或阶段复盘检查理解程度'
    })
    await refreshSyllabusData()
  } catch (error) {
    renderAuthMessage(`新增学习项失败：${error.message}`)
  } finally {
    setBusy(button, false)
  }
}

async function handleMergeSyllabusItems() {
  ensureAuthenticated()
  requireCurrentSyllabus()
  const ids = currentItemIds().slice(0, 2)
  const button = $('#mergeSyllabusItemsBtn')
  setBusy(button, true)
  try {
    if (ids.length < 2) throw new Error('至少需要两个学习项才能合并')
    const title = window.prompt('合并后的学习项标题', '合并学习项')
    if (!title) return
    currentSyllabus = await mergeSyllabusItems({
      item_ids: ids,
      title,
      reason: '用户认为前两个学习项可以合并学习'
    })
    await refreshSyllabusData()
  } catch (error) {
    renderAuthMessage(`合并学习项失败：${error.message}`)
  } finally {
    setBusy(button, false)
  }
}

async function handleRegenerateStage() {
  ensureAuthenticated()
  const version = requireCurrentSyllabus()
  const firstStage = version.items?.find((item) => item.status !== 'deleted')?.stage || ''
  const stage = window.prompt('要重新生成的阶段名称', firstStage)
  if (!stage) return
  const button = $('#regenerateStageBtn')
  setBusy(button, true)
  try {
    currentSyllabus = await regenerateSyllabusStage(version.id, {
      stage,
      instruction: '优化该阶段的顺序、难度和资源类型，并补充可复现实践内容'
    })
    await refreshSyllabusData()
  } catch (error) {
    renderAuthMessage(`重生成阶段失败：${error.message}`)
  } finally {
    setBusy(button, false)
  }
}

async function handleGenerateDailyPlan() {
  ensureAuthenticated()
  if (!selectedSyllabusProjectId) return
  const button = $('#generateDailyPlanBtn')
  setBusy(button, true)
  try {
    await generateDailyPlan(selectedSyllabusProjectId, {})
    await refreshSyllabusData()
  } catch (error) {
    renderAuthMessage(`生成每日计划失败：${error.message}`)
  } finally {
    setBusy(button, false)
  }
}

async function handleAdaptSyllabus() {
  ensureAuthenticated()
  if (!selectedSyllabusProjectId) return
  const button = $('#adaptSyllabusBtn')
  setBusy(button, true)
  try {
    currentSyllabus = await adaptSyllabus(selectedSyllabusProjectId, {
      trigger_type: 'student_feedback',
      evidence: $('#adaptEvidenceInput').value || '用户希望系统根据学习反馈调整路径',
      require_confirmation: false
    })
    await refreshSyllabusData()
  } catch (error) {
    renderAuthMessage(`动态调整路径失败：${error.message}`)
  } finally {
    setBusy(button, false)
  }
}

function currentItemIds() {
  return (currentSyllabus?.items || [])
    .filter((item) => item.status !== 'deleted')
    .sort((a, b) => a.user_order - b.user_order)
    .map((item) => item.id)
}

async function moveSyllabusItem(itemId, direction) {
  const version = requireCurrentSyllabus()
  const ids = currentItemIds()
  const index = ids.indexOf(itemId)
  const target = index + direction
  if (index < 0 || target < 0 || target >= ids.length) return
  ;[ids[index], ids[target]] = [ids[target], ids[index]]
  currentSyllabus = await reorderSyllabusItems(version.id, ids)
  await refreshSyllabusData()
}

function buildSplitPart(item, title, minutes) {
  return {
    title,
    item_type: item.item_type,
    stage: item.stage,
    difficulty: item.difficulty,
    estimated_minutes: minutes,
    recommendation_reason: `由“${item.title}”拆分，便于分步学习`,
    objective: item.objective,
    prerequisites: item.prerequisites || [],
    knowledge_points: item.knowledge_points || [],
    related_documents: item.related_documents || [],
    recommended_resource_types: item.recommended_resource_types || [],
    classroom_types: item.classroom_types || [],
    completion_criteria: item.completion_criteria,
    assessment_method: item.assessment_method
  }
}

async function handleSyllabusClick(event) {
  const button = event.target.closest('button')
  if (!button) return
  try {
    const itemId = Number(button.dataset.itemId)
    if (button.classList.contains('syllabus-version-pill')) {
      const versionId = Number(button.dataset.versionId)
      currentSyllabus = await getSyllabusVersion(versionId)
      renderSyllabusVersions(currentSyllabusVersions, currentSyllabus.id)
      renderSyllabus(currentSyllabus)
      renderSyllabusTrace(currentSyllabus)
      return
    }
    if (button.classList.contains('syllabus-move-up-btn')) {
      await moveSyllabusItem(itemId, -1)
      return
    }
    if (button.classList.contains('syllabus-move-down-btn')) {
      await moveSyllabusItem(itemId, 1)
      return
    }
    if (button.classList.contains('syllabus-status-btn')) {
      currentSyllabus = await updateSyllabusItemStatus(itemId, button.dataset.status, '用户在学习清单页手动标记')
      await refreshSyllabusData()
      return
    }
    if (button.classList.contains('syllabus-delete-btn')) {
      await deleteSyllabusItem(itemId)
      await refreshSyllabusData()
      return
    }
    if (button.classList.contains('syllabus-edit-btn')) {
      const item = currentSyllabus.items.find((candidate) => Number(candidate.id) === itemId)
      if (!item) return
      const title = window.prompt('学习项标题', item.title)
      if (!title) return
      const minutes = Number(window.prompt('预计学习分钟数', item.estimated_minutes))
      currentSyllabus = await updateSyllabusItem(itemId, {
        title,
        estimated_minutes: Number.isFinite(minutes) && minutes > 0 ? minutes : item.estimated_minutes
      })
      await refreshSyllabusData()
      return
    }
    if (button.classList.contains('syllabus-split-btn')) {
      const item = currentSyllabus.items.find((candidate) => Number(candidate.id) === itemId)
      if (!item) return
      currentSyllabus = await splitSyllabusItem(itemId, {
        reason: '用户希望降低单项粒度',
        parts: [
          buildSplitPart(item, `${item.title}：基础理解`, Math.max(15, Math.floor(item.estimated_minutes / 2))),
          buildSplitPart(item, `${item.title}：实践巩固`, Math.max(15, Math.ceil(item.estimated_minutes / 2)))
        ]
      })
      await refreshSyllabusData()
    }
  } catch (error) {
    renderAuthMessage(`学习清单操作失败：${error.message}`)
  }
}

async function handleSyllabusProjectChange(event) {
  if (event.target.id !== 'syllabusProjectSelect') return
  selectedSyllabusProjectId = Number(event.target.value)
  await loadSyllabusWorkspace(selectedSyllabusProjectId)
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
    renderUserShell(token.user)
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
    renderUserShell(token.user)
    renderAuthMessage('')
    routeTo('/app/directions')
  } catch (error) {
    renderAuthMessage('注册失败：用户名或邮箱可能已存在，可尝试直接登录。')
  } finally {
    setBusy(button, false)
  }
}

async function handleSaveSettings() {
  ensureAuthenticated()
  const button = $('#saveSettingsBtn')
  setBusy(button, true)
  try {
    const user = await updateCurrentUser({
      full_name: $('#settingsFullName').value,
      email: $('#settingsEmail').value,
      avatar_url: $('#settingsAvatarUrl').value,
      school: $('#settingsSchool').value,
      major: $('#settingsMajor').value,
      bio: $('#settingsBio').value
    })
    setAuth({ access_token: getState().token, user })
    renderUserShell(user)
    renderSettings(user)
    renderAuthMessage('账号信息已保存。', 'success')
  } catch (error) {
    renderAuthMessage(`保存账号信息失败：${error.message}`)
  } finally {
    setBusy(button, false)
  }
}

function handleUserMenuClick() {
  routeTo('/app/settings')
}

function handleLogout() {
  clearAuth()
  setWorkflow(null)
  renderUserShell(null)
  renderRoute()
  routeTo('/home')
}

async function hydrateAuth() {
  if (!getState().token) {
    renderUserShell(null)
    renderRoute()
    return
  }
  try {
    const user = await getCurrentUser()
    setAuth({ access_token: getState().token, user })
    renderUserShell(user)
  } catch {
    clearAuth()
    renderUserShell(null)
  }
  renderRoute()
}

function bindEvents() {
  initButtonLabels()
  renderUserShell(getState().user)
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
  $('#generateSyllabusBtn').addEventListener('click', handleGenerateSyllabus)
  $('#copySyllabusBtn').addEventListener('click', handleCopySyllabus)
  $('#activateSyllabusBtn').addEventListener('click', handleActivateSyllabus)
  $('#compareSyllabusBtn').addEventListener('click', handleCompareSyllabus)
  $('#addSyllabusItemBtn').addEventListener('click', handleAddSyllabusItem)
  $('#mergeSyllabusItemsBtn').addEventListener('click', handleMergeSyllabusItems)
  $('#regenerateStageBtn').addEventListener('click', handleRegenerateStage)
  $('#generateDailyPlanBtn').addEventListener('click', handleGenerateDailyPlan)
  $('#adaptSyllabusBtn').addEventListener('click', handleAdaptSyllabus)
  $('#syllabusProjectView').addEventListener('change', handleSyllabusProjectChange)
  $('#syllabusVersionView').addEventListener('click', handleSyllabusClick)
  $('#pathView').addEventListener('click', handleSyllabusClick)
  $('#saveSettingsBtn').addEventListener('click', handleSaveSettings)
  $('#userMenuBtn').addEventListener('click', handleUserMenuClick)
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
