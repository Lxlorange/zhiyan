const $ = (selector) => document.querySelector(selector)

export function setBusy(button, busy) {
  button.disabled = busy
  button.textContent = busy ? '处理中...' : button.dataset.label
}

export function initButtonLabels() {
  ;[
    '#startBtn',
    '#startInlineBtn',
    '#analyzeDirectionBtn',
    '#saveDirectionBtn',
    '#profileDialogueBtn',
    '#knowledgeSearchBtn',
    '#askBtn',
    '#submitQuizBtn',
    '#loginBtn',
    '#registerBtn',
    '#logoutBtn'
  ].forEach((selector) => {
    const button = $(selector)
    if (button) button.dataset.label = button.textContent
  })
}

export function renderDirectionProgress(message, state = 'idle') {
  const node = $('#directionProgressView')
  if (!node) return
  node.className = `agent-progress ${state}`
  node.innerHTML = `
    <span class="pulse-dot"></span>
    <strong>${message}</strong>
  `
}

export function renderDirectionTemplates(templates) {
  const select = $('#directionTemplateSelect')
  const view = $('#directionTemplatesView')
  if (!templates || templates.length === 0) {
    view.className = 'template-list empty'
    view.textContent = '暂无方向模板'
    return
  }
  select.innerHTML = '<option value="">不使用模板</option>' + templates.map((template) => `
    <option value="${template.id}">${template.title}</option>
  `).join('')
  view.className = 'template-list'
  view.innerHTML = templates.map((template) => `
    <article class="template-card" data-template-id="${template.id}">
      <div>
        <span class="tag">${template.is_teacher_recommended ? '教师推荐' : '方向模板'}</span>
        ${template.tags.map((tag) => `<span class="tag">${tag}</span>`).join('')}
      </div>
      <h4>${template.title}</h4>
      <p>${template.description}</p>
      <small>周期：${template.recommended_period} / 产出：${template.stage_outputs.join('、')}</small>
    </article>
  `).join('')
}

export function renderDirectionAnalysis(result) {
  if (!result) return
  const project = result.suggested_project || {}
  $('#directionResultView').className = 'answer'
  $('#directionResultView').innerHTML = `
    <div class="answer-box">
      <p><strong>${result.normalized_title}</strong> / ${result.domain} / ${result.route_type}</p>
      <p>${result.description}</p>
      <p><strong>推荐目标：</strong>${result.recommended_goal}</p>
      <p><strong>预期产出：</strong>${result.expected_output}</p>
      <p><strong>初步知识点：</strong>${(result.initial_knowledge_points || []).join('、')}</p>
      <p><strong>建议项目：</strong>${project.title || '-'}</p>
      <p><strong>下一步：</strong>${project.next_step || '-'}</p>
      ${result.clarification_questions?.length ? `<p><strong>澄清问题：</strong>${result.clarification_questions.join('；')}</p>` : ''}
      ${result.risk_notes?.length ? `<p><strong>风险提示：</strong>${result.risk_notes.join('；')}</p>` : ''}
    </div>
  `
}

export function renderSavedDirections(directions) {
  const node = $('#savedDirectionsView')
  if (!directions || directions.length === 0) {
    node.className = 'project-list empty'
    node.textContent = '暂无方向。请先在左侧分析并保存方向。'
    return
  }
  node.className = 'project-list'
  node.innerHTML = directions.map((direction) => `
    <article class="project-card">
      <div>
        <span class="tag">${direction.status}</span>
        <span class="tag">${direction.goal_type}</span>
        <span class="tag">v${direction.analysis_revision || 1}</span>
        <span class="tag">${direction.review_status || 'pending'}</span>
      </div>
      <h4>${direction.normalized_title}</h4>
      <p>${direction.description}</p>
      <small>知识点：${Object.values(direction.extracted_data?.initial_knowledge_points || direction.extracted_data?.suggested_project?.related_knowledge_points || {}).join('、')}</small>
      ${direction.review_notes ? `<small>审核意见：${direction.review_notes}</small>` : ''}
      <div class="project-actions">
        <button class="secondary create-project-btn" data-direction-id="${direction.id}">创建学习项目</button>
        <button class="ghost regenerate-direction-btn" data-direction-id="${direction.id}">重新理解</button>
      </div>
    </article>
  `).join('')
}

export function renderLearningProjects(projects) {
  const node = $('#learningProjectsView')
  if (!projects || projects.length === 0) {
    node.className = 'project-list empty'
    node.textContent = '暂无学习项目'
    return
  }
  node.className = 'project-list'
  node.innerHTML = projects.map((project) => `
    <article class="project-card">
      <div>
        <span class="tag">${project.status}</span>
        <span class="tag">${project.goal_type}</span>
        <span class="tag">${project.difficulty}</span>
        ${project.deadline ? `<span class="tag">DDL ${new Date(project.deadline).toLocaleDateString()}</span>` : ''}
      </div>
      <h4>${project.title}</h4>
      <p>${project.learning_goal}</p>
      <small>进度：${project.progress}% / 每日 ${project.daily_minutes} 分钟 / 周期 ${project.recommended_period}</small>
      <div class="project-actions">
        <button class="secondary project-home-btn" data-project-id="${project.id}">查看首页</button>
        <button class="secondary project-pause-btn" data-project-id="${project.id}">暂停</button>
        <button class="secondary project-resume-btn" data-project-id="${project.id}">恢复</button>
        <button class="secondary project-regenerate-syllabus-btn" data-project-id="${project.id}">重生成清单</button>
        <button class="secondary project-copy-btn" data-project-id="${project.id}">复制</button>
        <button class="secondary project-share-btn" data-project-id="${project.id}">分享</button>
        <button class="secondary project-export-btn" data-project-id="${project.id}">导出</button>
        <button class="ghost project-archive-btn" data-project-id="${project.id}">归档</button>
      </div>
    </article>
  `).join('')
}

export function renderProjectHome(home) {
  if (!home) return
  const project = home.project
  $('#projectHomeView').className = 'answer'
  $('#projectHomeView').innerHTML = `
    <div class="answer-box">
      <p><strong>${project.title}</strong></p>
      <p>${project.learning_goal}</p>
      <p><strong>当前阶段：</strong>${home.current_stage}</p>
      <p><strong>今日建议：</strong>${home.today_recommendations.join('、') || '暂无'}</p>
      <p><strong>当前薄弱点：</strong>${home.current_weak_points.join('、') || '暂无'}</p>
      <p><strong>资源数量：</strong>${home.generated_resource_count} / <strong>完成项：</strong>${home.completed_item_count}</p>
      ${project.deadline ? `<p><strong>截止时间：</strong>${new Date(project.deadline).toLocaleString()}</p>` : ''}
      ${project.teacher_notes ? `<p><strong>教师备注：</strong>${project.teacher_notes}</p>` : ''}
      <p><strong>下一步：</strong>${home.next_step}</p>
      <p><strong>项目产出：</strong>${home.output_checklist.join('、')}</p>
      ${project.shared_token ? `<p><strong>分享令牌：</strong>${project.shared_token}</p>` : ''}
    </div>
  `
}

export function renderProjectExport(exportResult) {
  if (!exportResult) return
  $('#projectHomeView').className = 'answer'
  $('#projectHomeView').innerHTML = `
    <div class="answer-box">
      <p><strong>项目导出 Markdown</strong></p>
      <pre>${exportResult.markdown}</pre>
    </div>
  `
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

export function renderDialogueProfile(result) {
  if (!result) return
  const profile = result.profile
  $('#profileDialogueResult').className = 'answer'
  $('#profileDialogueResult').innerHTML = `
    <div class="answer-box">
      <p><strong>画像版本：v${result.revision}</strong></p>
      <p>${result.update_reason}</p>
      <p><strong>抽取维度：</strong>知识基础、学习目标、认知风格、易错点、实践能力、资源偏好、学习节奏、兴趣方向</p>
      <p><strong>当前短板：</strong>${profile.weak_points.join('、')}</p>
    </div>
  `
}

export function renderKnowledgeSearch(hits) {
  const node = $('#knowledgeSearchView')
  if (!hits || hits.length === 0) {
    node.className = 'knowledge-results empty'
    node.textContent = '未检索到课程资料'
    return
  }
  node.className = 'knowledge-results'
  node.innerHTML = hits.map((hit) => `
    <div class="answer-box">
      <p><strong>${hit.knowledge_point}</strong> / ${hit.document_title} / ${hit.document_type}</p>
      <p>${hit.content}</p>
      <p><strong>来源：</strong>${hit.source_uri}</p>
      <div>${hit.keywords.map((keyword) => `<span class="tag">${keyword}</span>`).join('')}</div>
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
