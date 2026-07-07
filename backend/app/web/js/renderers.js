const $ = (selector) => document.querySelector(selector)

export function setBusy(button, busy) {
  button.disabled = busy
  button.textContent = busy ? '处理中...' : button.dataset.label
}

export function initButtonLabels() {
  ;['#startBtn', '#startInlineBtn', '#askBtn', '#submitQuizBtn', '#loginBtn', '#registerBtn', '#logoutBtn'].forEach((selector) => {
    const button = $(selector)
    if (button) button.dataset.label = button.textContent
  })
}

export function renderCurrentUser(user) {
  $('#currentUserLabel').textContent = user ? `${user.full_name || user.username} / ${user.role}` : '未登录'
}

export function renderAuthMessage(message, type = 'error') {
  const node = document.querySelector('#authMessage')
  node.textContent = message || ''
  node.className = `auth-message ${type}`
}

export function renderMetrics(workflow) {
  $('#sessionMetric').textContent = workflow ? workflow.session_id.slice(0, 8) : '-'
  $('#profileMetric').textContent = workflow ? `v${workflow.profile.revision}` : '-'
  $('#gapMetric').textContent = workflow ? workflow.gaps.length : '-'
  $('#resourceMetric').textContent = workflow ? workflow.resources.length : '-'
}

export function renderProfile(workflow) {
  if (!workflow) return
  const profile = workflow.profile
  const items = [
    ['知识基础', profile.knowledge_base],
    ['学习目标', profile.learning_goal],
    ['认知风格', profile.cognitive_style],
    ['实践能力', profile.practice_level],
    ['资源偏好', profile.resource_preference.join('、')],
    ['学习节奏', profile.learning_pace],
    ['兴趣方向', profile.interest_direction],
    ['当前短板', profile.weak_points.join('、')]
  ]
  $('#profileView').className = 'profile-list'
  $('#profileView').innerHTML = items.map(([label, value]) => `
    <div class="kv"><span>${label}</span><p>${value}</p></div>
  `).join('')
}

export function renderGaps(workflow) {
  if (!workflow) return
  $('#gapsView').className = 'gap-list'
  $('#gapsView').innerHTML = workflow.gaps.map((gap) => `
    <div class="gap">
      <span>${gap.severity.toUpperCase()} / ${gap.related_points.join('、')}</span>
      <p><strong>${gap.title}</strong></p>
      <p>${gap.evidence}</p>
    </div>
  `).join('')
}

export function renderPath(workflow) {
  if (!workflow) return
  $('#pathView').className = 'timeline'
  $('#pathView').innerHTML = workflow.path.map((step, index) => `
    <div class="step">
      <span>Step ${index + 1} / ${step.estimated_minutes} 分钟 / ${step.status}</span>
      <p><strong>${step.title}</strong>：${step.objective}</p>
      <p>${step.reason}</p>
    </div>
  `).join('')
}

export function renderTrace(workflow) {
  if (!workflow) return
  $('#traceView').className = 'trace'
  $('#traceView').innerHTML = workflow.agent_trace.map((trace) => `
    <div class="trace-row">
      <span>${trace.agent} / ${trace.latency_ms}ms / ${trace.status}</span>
      <p>${trace.output_summary}</p>
    </div>
  `).join('')
}

export function renderResources(workflow) {
  if (!workflow) return
  $('#resourcesView').className = 'resources'
  $('#resourcesView').innerHTML = workflow.resources.map((resource) => `
    <article class="resource-card">
      <span class="tag">${resource.type}</span>
      <span class="tag">${resource.format_hint}</span>
      <h4>${resource.title}</h4>
      <p>${resource.content}</p>
      <div>${resource.knowledge_points.map((point) => `<span class="tag">${point}</span>`).join('')}</div>
      <small>来源：${resource.sources.join('、')}</small>
    </article>
  `).join('')
}

export function renderQuiz(workflow) {
  if (!workflow) return
  $('#quizView').className = 'quiz'
  $('#quizView').innerHTML = workflow.quiz.map((question) => `
    <div class="quiz-item">
      <span>${question.knowledge_point}</span>
      <p>${question.prompt}</p>
      <div class="quiz-options">
        ${question.options.map((option) => `
          <label>
            <input type="radio" name="${question.id}" value="${option}" />
            ${option}
          </label>
        `).join('')}
      </div>
    </div>
  `).join('')
}

export function renderTutor(tutor) {
  if (!tutor) return
  $('#tutorView').className = 'answer'
  $('#tutorView').innerHTML = `
    <div class="answer-box">
      <p>${tutor.answer}</p>
      <p><strong>策略：</strong>${tutor.strategy}</p>
      <p><strong>追问练习：</strong>${tutor.follow_up_exercise}</p>
      <p><strong>来源：</strong>${tutor.sources.join('、')}</p>
    </div>
  `
}

export function renderAssessment(assessment) {
  if (!assessment) return
  $('#assessmentView').className = 'answer'
  $('#assessmentView').innerHTML = `
    <div class="answer-box">
      <p><strong>得分：${assessment.score}</strong></p>
      <p>更新短板：${assessment.weak_points.join('、')}</p>
      <p>${assessment.updated_suggestion}</p>
    </div>
  `
}

export function renderTeacherDashboard(dashboard) {
  if (!dashboard) return
  const metricHtml = dashboard.metrics.map((metric) => `
    <div class="kv">
      <span>${metric.label}</span>
      <p><strong>${metric.value}</strong> ${metric.trend}</p>
    </div>
  `).join('')
  const weakPoints = Object.entries(dashboard.weak_point_distribution).map(([label, value]) => `
    <span class="tag">${label}: ${value}</span>
  `).join('')
  const suggestions = dashboard.teaching_suggestions.map((item) => `<li>${item}</li>`).join('')
  document.querySelector('#teacherView').className = 'dashboard'
  document.querySelector('#teacherView').innerHTML = `
    <div class="dashboard-grid">${metricHtml}</div>
    <div class="answer-box">
      <p><strong>高频短板：</strong>${weakPoints}</p>
      <ul>${suggestions}</ul>
    </div>
  `
}

export function resetTutorAndAssessment() {
  $('#assessmentView').className = 'answer empty'
  $('#assessmentView').textContent = '等待评估结果'
  $('#tutorView').className = 'answer empty'
  $('#tutorView').textContent = '等待辅导输出'
}

export function readQuizAnswers(workflow) {
  const answers = {}
  workflow.quiz.forEach((question) => {
    const checked = document.querySelector(`input[name="${question.id}"]:checked`)
    if (checked) answers[question.id] = checked.value
  })
  return answers
}

export function renderAll(workflow) {
  renderMetrics(workflow)
  renderProfile(workflow)
  renderGaps(workflow)
  renderPath(workflow)
  renderTrace(workflow)
  renderResources(workflow)
  renderQuiz(workflow)
  renderAssessment(workflow.assessment)
  renderTutor(workflow.tutor)
}
