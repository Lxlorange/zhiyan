<template>
  <div class="page classroom-page classroom-studio-page">
    <section class="page-hero classroom-hero">
      <div>
        <p class="eyebrow">AI Classroom</p>
        <h2>{{ currentItem?.title || 'AI 课堂' }}</h2>
      </div>
      <div class="classroom-hero-actions">
        <el-button @click="goBackToSyllabus">返回学习清单</el-button>
        <el-tag v-if="currentItem" :type="statusType(currentItem.status)">{{ statusLabel(currentItem.status) }}</el-tag>
      </div>
    </section>

    <el-empty v-if="!projectId || !itemId" description="请从项目学习清单进入课堂。" />
    <section v-else-if="loading" class="panel-like classroom-loading">正在加载课堂...</section>
    <el-empty v-else-if="!currentItem || !classroom" description="没有找到当前课堂，请返回学习清单重新进入。" />

    <section v-else class="classroom-studio">
      <aside class="classroom-left panel-like">
        <div class="classroom-mini-card">
          <span>学习进度</span>
          <strong>{{ completedGateCount }}/4</strong>
          <el-progress :percentage="gateProgress" :stroke-width="10" />
        </div>

        <nav class="classroom-gates" aria-label="课堂闸门">
          <button
            v-for="gate in gates"
            :key="gate.key"
            type="button"
            :class="{ active: activeGate === gate.key, done: gate.done }"
            @click="handleGateSelect(gate.key)"
          >
            <strong>{{ gate.title }}</strong>
            <span>{{ gate.done ? '已完成' : gate.kind }}</span>
          </button>
        </nav>

        <section class="classroom-chat">
          <header>
            <strong>课堂追问</strong>
            <el-tag size="small" effect="plain">DialogueAgent</el-tag>
          </header>
          <div class="classroom-chat-log">
            <article
              v-for="message in dialogueMessages"
              :key="`${message.created_at}-${message.role}-${message.content.slice(0, 16)}`"
              :class="message.role"
            >
              <span>{{ message.role === 'user' ? '我' : 'AI 助教' }}</span>
              <p>{{ message.content }}</p>
            </article>
            <p v-if="!dialogueMessages.length" class="empty-chat">生成课件后可以追问。</p>
          </div>
          <div class="quick-actions">
            <button v-for="action in quickActions" :key="action" type="button" @click="sendQuickAction(action)">
              {{ action }}
            </button>
          </div>
          <el-input v-model="chatMessage" type="textarea" :rows="3" placeholder="继续追问、要求举例或让 AI 生成练习..." />
          <el-button type="primary" :loading="sendingDialogue" :disabled="!pptPackage || !chatMessage.trim()" @click="handleSendDialogue">
            发送
          </el-button>
        </section>
      </aside>

      <main class="classroom-stage panel-like">
        <header class="classroom-stage-head">
          <div>
            <span>{{ activeGateMeta.kind }}</span>
            <h3>{{ activeGateMeta.title }}</h3>
          </div>
          <el-tag :type="activeGateMeta.done ? 'success' : 'warning'" effect="plain">
            {{ activeGateMeta.done ? '已通过' : '待完成' }}
          </el-tag>
        </header>

        <Transition name="panel-swap" mode="out-in">
          <section v-if="activeGate === 'ppt'" key="ppt" class="classroom-pane">
            <Transition name="panel-swap" mode="out-in">
              <div v-if="!pptPackage" key="ppt-preparing" class="classroom-generate classroom-preparing-card">
                <span class="classroom-preparing-dot" aria-hidden="true" />
                <h4>课堂资源正在后台生成</h4>
                <p>系统会按学习清单顺序预生成多模态课堂资源。当前学习项尚未就绪，请稍后刷新。</p>
                <div class="classroom-action-row">
                  <el-button @click="goBackToSyllabus">返回学习清单</el-button>
                  <el-button type="primary" :loading="loading" @click="loadClassroom">刷新状态</el-button>
                </div>
              </div>

              <div v-else key="ppt-content" class="multimodal-workbench">
                <el-tabs v-model="activeContentTab" class="classroom-tabs">
                  <el-tab-pane label="动态课件" name="slides">
                    <section class="slide-player-v2">
                      <div class="slide-canvas-v2">
                        <div class="slide-count">Slide {{ activeSlideIndex + 1 }} / {{ slideList.length }}</div>
                        <h4>{{ currentSlide?.title }}</h4>
                        <ul>
                          <li v-for="bullet in currentSlide?.bullets || []" :key="bullet">{{ bullet }}</li>
                        </ul>
                      </div>
                      <aside class="slide-note-v2">
                        <strong>讲解稿</strong>
                        <p>{{ currentSlide?.speaker_notes || '暂无讲稿。' }}</p>
                      </aside>
                    </section>
                    <div class="slide-controls-v2">
                      <el-button :disabled="activeSlideIndex <= 0" @click="goToSlide(activeSlideIndex - 1)">上一页</el-button>
                      <el-progress :percentage="slideReadPercent" :stroke-width="8" />
                      <el-button :disabled="activeSlideIndex >= slideList.length - 1" @click="goToSlide(activeSlideIndex + 1)">下一页</el-button>
                    </div>
                    <div class="slide-strip">
                      <button
                        v-for="(slide, index) in slideList"
                        :key="`${slide.title}-${index}`"
                        type="button"
                        :class="{ active: activeSlideIndex === index, viewed: visitedSlideIndices.has(index) }"
                        @click="goToSlide(index)"
                      >
                        <small>{{ index + 1 }}</small>
                        <span>{{ slide.title }}</span>
                      </button>
                    </div>
                    <div class="classroom-action-row">
                      <el-button v-if="pptResource" @click="downloadPpt">下载 PPT</el-button>
                      <el-button type="success" :disabled="!allSlidesViewed || classroom?.slides_completed" @click="handleCompleteSlides">
                        {{ classroom?.slides_completed ? '课件已完成' : `完成课件 ${slidesVisitedCount}/${slideList.length}` }}
                      </el-button>
                    </div>
                  </el-tab-pane>

                  <el-tab-pane label="概念卡" name="concepts">
                    <div class="concept-grid">
                      <article v-for="card in conceptCards" :key="card.name">
                        <strong>{{ card.name }}</strong>
                        <p>{{ card.explanation }}</p>
                        <small>{{ card.scenario }}</small>
                        <em>{{ card.misconception }}</em>
                      </article>
                    </div>
                  </el-tab-pane>

                  <el-tab-pane label="图解" name="diagram">
                    <section class="diagram-panel">
                      <h4>{{ diagramSpec.title || '学习图解' }}</h4>
                      <pre>{{ diagramSpec.mermaid }}</pre>
                      <p>{{ diagramSpec.explanation }}</p>
                    </section>
                  </el-tab-pane>

                  <el-tab-pane label="3D 物理演示" name="visualization">
                    <section class="visualization-panel">
                      <div v-if="!visualizationResource" class="classroom-generate">
                        <h4>生成 3D 物理演示</h4>
                        <el-input v-model="visualizationInstruction" type="textarea" :rows="4" placeholder="可选：指定信号传播、网络数据包、神经激活、排序碰撞、优化地形等 3D 演示方向..." />
                        <el-button type="primary" :loading="generatingVisualization" :disabled="!pptPackage" @click="handleGenerateVisualization">
                          生成 3D 演示
                        </el-button>
                      </div>
                      <div v-else class="visualization-frame-shell">
                        <header>
                          <strong>{{ visualizationResource.title }}</strong>
                          <div>
                            <el-button :loading="loadingVisualizationView" @click="loadVisualizationView">刷新预览</el-button>
                            <el-button @click="downloadVisualization">下载 HTML</el-button>
                          </div>
                        </header>
                        <iframe v-if="visualizationUrl" :src="visualizationUrl" title="课堂 3D 物理演示" />
                        <div v-else class="visualization-loading">正在载入 3D 演示...</div>
                      </div>
                    </section>
                  </el-tab-pane>

                  <el-tab-pane label="语音讲稿" name="voice">
                    <section class="voice-script">
                      <article>
                        <span>1 分钟</span>
                        <p>{{ voiceScript.one_minute }}</p>
                      </article>
                      <article>
                        <span>5 分钟</span>
                        <p>{{ voiceScript.five_minutes }}</p>
                      </article>
                      <div class="classroom-point-list">
                        <div v-for="segment in voiceScript.segments || []" :key="segment"><span>{{ segment }}</span></div>
                      </div>
                    </section>
                  </el-tab-pane>

                  <el-tab-pane label="复现 Demo" name="demo">
                    <section class="demo-panel">
                      <h4>{{ reproductionDemo.title || practiceSpec?.title }}</h4>
                      <p>{{ reproductionDemo.task }}</p>
                      <pre v-if="reproductionDemo.code_skeleton">{{ reproductionDemo.code_skeleton }}</pre>
                      <div class="classroom-point-list">
                        <div v-for="step in reproductionDemo.steps || []" :key="step"><span>{{ step }}</span></div>
                      </div>
                    </section>
                  </el-tab-pane>
                </el-tabs>
              </div>
            </Transition>
          </section>

          <section v-else-if="activeGate === 'quiz'" key="quiz" class="classroom-pane">
            <Transition name="panel-swap" mode="out-in">
              <div v-if="classroom?.quiz_passed" key="quiz-done" class="gate-complete-panel">
                <strong>例题已通过</strong>
                <p v-if="latestQuizFeedback" class="task-feedback">{{ latestQuizFeedback }}</p>
                <div class="classroom-action-row"><el-button type="primary" @click="activeGate = 'practice'">进入实操</el-button></div>
              </div>
              <div v-else key="quiz-form" class="classroom-form-stack">
                <el-alert v-if="!classroom?.slides_completed" title="请先翻完动态课件并完成课件学习" type="warning" :closable="false" />
                <div v-else class="quiz-list">
                  <label v-for="question in quizQuestions" :key="question.id">
                    <span>{{ question.id }}. {{ question.prompt }}</span>
                    <el-input v-model="quizAnswers[question.id]" placeholder="填写你的答案" />
                  </label>
                </div>
                <p v-if="latestQuizFeedback" class="task-feedback">{{ latestQuizFeedback }}</p>
                <div class="classroom-action-row">
                  <el-button type="primary" :disabled="!classroom?.slides_completed" :loading="submittingQuiz" @click="handleSubmitQuiz">提交例题</el-button>
                </div>
              </div>
            </Transition>
          </section>

          <section v-else-if="activeGate === 'practice'" key="practice" class="classroom-pane">
            <Transition name="panel-swap" mode="out-in">
              <div v-if="classroom?.practice_passed" key="practice-done" class="gate-complete-panel">
                <strong>实操已通过</strong>
                <p v-if="latestPracticeFeedback" class="task-feedback">{{ latestPracticeFeedback }}</p>
                <div class="classroom-action-row"><el-button type="primary" @click="activeGate = 'reflection'">进入复盘</el-button></div>
              </div>
              <div v-else key="practice-form" class="classroom-form-stack">
                <h4>{{ practiceSpec?.title || '完成实操任务' }}</h4>
                <div v-if="practiceSpec" class="classroom-point-list">
                  <div v-for="step in practiceSteps" :key="step"><span>{{ step }}</span></div>
                </div>
                <el-input v-model="practiceForm.artifact_url" placeholder="产物链接或文件路径，可选" />
                <el-input v-model="practiceForm.key_result" type="textarea" :rows="3" placeholder="关键结果，例如指标、截图描述、运行结果" />
                <el-input v-model="practiceForm.report" type="textarea" :rows="7" placeholder="实操报告：说明你做了什么、如何验证、遇到什么问题、结果是否达标" />
                <p v-if="latestPracticeFeedback" class="task-feedback">{{ latestPracticeFeedback }}</p>
                <div class="classroom-action-row">
                  <el-button type="primary" :disabled="!pptPackage" :loading="submittingPractice" @click="handleSubmitPractice">提交实操</el-button>
                </div>
              </div>
            </Transition>
          </section>

          <section v-else key="reflection" class="classroom-pane">
            <Transition name="panel-swap" mode="out-in">
              <div v-if="classroom?.reflection_passed" key="reflection-done" class="gate-complete-panel">
                <strong>复盘已通过</strong>
                <p v-if="latestReflectionFeedback" class="task-feedback">{{ latestReflectionFeedback }}</p>
                <div class="classroom-action-row"><el-button @click="goBackToSyllabus">返回学习清单</el-button></div>
              </div>
              <div v-else key="reflection-form" class="classroom-form-stack">
                <h4>提交学习复盘</h4>
                <div v-if="reflectionPrompts.length" class="classroom-prompts">
                  <div v-for="prompt in reflectionPrompts" :key="prompt">{{ prompt }}</div>
                </div>
                <el-input v-model="reflectionForm.reflection" type="textarea" :rows="8" placeholder="写下本节学到的内容、完成证据、仍然薄弱的知识点" />
                <el-input v-model="unresolvedQuestionsText" type="textarea" :rows="3" placeholder="未解决问题，每行一个" />
                <el-input v-model="reflectionForm.next_action" placeholder="下一步行动" />
                <p v-if="latestReflectionFeedback" class="task-feedback">{{ latestReflectionFeedback }}</p>
                <div class="classroom-action-row">
                  <el-button type="primary" :disabled="!pptPackage" :loading="submittingReflection" @click="handleSubmitReflection">提交复盘</el-button>
                </div>
              </div>
            </Transition>
          </section>
        </Transition>
      </main>

      <aside class="classroom-right panel-like">
        <div class="classroom-mini-card">
          <span>知识点</span>
          <div class="classroom-tags">
            <el-tag v-for="point in currentItem.knowledge_points" :key="point" effect="plain">{{ point }}</el-tag>
          </div>
        </div>
        <div class="classroom-mini-card">
          <span>引导问题</span>
          <button v-for="question in guidingQuestions" :key="question.prompt" type="button" @click="askGuidingQuestion(question.prompt)">
            {{ question.prompt }}
          </button>
        </div>
        <div class="classroom-mini-card">
          <span>最近反馈</span>
          <p>{{ latestFeedback || '暂无提交反馈。' }}</p>
        </div>
      </aside>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  completeClassroomSlides,
  downloadClassroomResource,
  generateClassroomVisualization,
  getCurrentSyllabus,
  getOrCreateClassroomSession,
  sendClassroomDialogue,
  submitClassroomPractice,
  submitClassroomQuiz,
  submitClassroomReflection,
  viewClassroomResource,
  type ClassroomResourceRead,
  type ClassroomSessionRead,
  type ClassroomSubmissionRead,
  type SyllabusVersionRead
} from '../services/apiClient'

type GateKey = 'ppt' | 'quiz' | 'practice' | 'reflection'

const props = defineProps<{ projectId: number | null; itemId: number | null }>()
const router = useRouter()
const loading = ref(false)
const generatingVisualization = ref(false)
const loadingVisualizationView = ref(false)
const sendingDialogue = ref(false)
const submittingQuiz = ref(false)
const submittingPractice = ref(false)
const submittingReflection = ref(false)
const syllabus = ref<SyllabusVersionRead | null>(null)
const classroom = ref<ClassroomSessionRead | null>(null)
const activeGate = ref<GateKey>('ppt')
const activeContentTab = ref('slides')
const activeSlideIndex = ref(0)
const visitedSlideIndices = ref<Set<number>>(new Set([0]))
const visualizationInstruction = ref('')
const visualizationUrl = ref('')
const chatMessage = ref('')
const unresolvedQuestionsText = ref('')
const quizAnswers = reactive<Record<string, string>>({})
const practiceForm = reactive({ report: '', artifact_url: '', key_result: '' })
const reflectionForm = reactive({ reflection: '', next_action: '' })
const quickActions = ['讲简单点', '举例', '出一道题', '联系科研方向', '总结本页']

const currentItem = computed(() => syllabus.value?.items.find((item) => item.id === props.itemId) || null)
const pptResource = computed<ClassroomResourceRead | null>(() => {
  if (!classroom.value?.ppt_resource_id) return null
  return classroom.value.resources.find((resource) => resource.id === classroom.value?.ppt_resource_id) || null
})
const visualizationResource = computed<ClassroomResourceRead | null>(() => {
  const resources = classroom.value?.resources || []
  return [...resources].reverse().find((resource) => resource.resource_type === 'interactive_visualization') || null
})
const pptPackage = computed<Record<string, any> | null>(() => pptResource.value?.content_data || null)
const slideList = computed<any[]>(() => pptPackage.value?.slides || [])
const quizQuestions = computed<any[]>(() => pptPackage.value?.quiz || [])
const currentSlide = computed(() => slideList.value[activeSlideIndex.value] || null)
const slidesVisitedCount = computed(() => visitedSlideIndices.value.size)
const allSlidesViewed = computed(() => Boolean(slideList.value.length) && slidesVisitedCount.value >= slideList.value.length)
const conceptCards = computed<any[]>(() => pptPackage.value?.concept_cards || [])
const diagramSpec = computed<Record<string, any>>(() => pptPackage.value?.diagram || {})
const guidingQuestions = computed<any[]>(() => pptPackage.value?.guiding_questions || [])
const voiceScript = computed<Record<string, any>>(() => pptPackage.value?.voice_script || {})
const reproductionDemo = computed<Record<string, any>>(() => pptPackage.value?.reproduction_demo || {})
const practiceSpec = computed(() => pptPackage.value?.practice || null)
const practiceSteps = computed<string[]>(() => practiceSpec.value?.steps || [])
const reflectionPrompts = computed<string[]>(() => pptPackage.value?.reflection_prompts || [])
const gates = computed(() => [
  { key: 'ppt' as GateKey, title: '课件学习', kind: '多模态资源', done: Boolean(classroom.value?.slides_completed) },
  { key: 'quiz' as GateKey, title: '回答例题', kind: '测验', done: Boolean(classroom.value?.quiz_passed) },
  { key: 'practice' as GateKey, title: '完成实操', kind: '实践', done: Boolean(classroom.value?.practice_passed) },
  { key: 'reflection' as GateKey, title: '提交复盘', kind: '复盘', done: Boolean(classroom.value?.reflection_passed) }
])
const activeGateMeta = computed(() => gates.value.find((gate) => gate.key === activeGate.value) || gates.value[0])
const completedGateCount = computed(() => gates.value.filter((gate) => gate.done).length)
const gateProgress = computed(() => Math.round((completedGateCount.value / 4) * 100))
const slideReadPercent = computed(() => {
  if (!slideList.value.length) return 0
  return Math.round((slidesVisitedCount.value / slideList.value.length) * 100)
})
const latestSubmission = computed(() => {
  const submissions = classroom.value?.submissions || []
  return submissions[submissions.length - 1] || null
})
const latestFeedback = computed(() => latestSubmission.value?.feedback || '')
const latestQuizFeedback = computed(() => latestSubmissionByType('quiz')?.feedback || '')
const latestPracticeFeedback = computed(() => latestSubmissionByType('practice')?.feedback || '')
const latestReflectionFeedback = computed(() => latestSubmissionByType('reflection')?.feedback || '')
const dialogueMessages = computed(() => {
  const submissions = classroom.value?.submissions || []
  return submissions
    .filter((submission) => submission.submission_type === 'dialogue_user' || submission.submission_type === 'dialogue_assistant')
    .map((submission) => ({
      role: String(submission.content.role || (submission.submission_type === 'dialogue_user' ? 'user' : 'assistant')),
      content: String(submission.content.message || ''),
      created_at: submission.created_at
    }))
})

onMounted(loadClassroom)
onBeforeUnmount(() => revokeVisualizationUrl())
watch(() => [props.projectId, props.itemId] as const, () => loadClassroom())
watch(() => visualizationResource.value?.id, () => {
  if (visualizationResource.value) void loadVisualizationView()
  else revokeVisualizationUrl()
})

async function loadClassroom() {
  if (!props.projectId || !props.itemId) return
  loading.value = true
  try {
    const [{ data: syllabusData }, { data: classroomData }] = await Promise.all([
      getCurrentSyllabus(props.projectId),
      getOrCreateClassroomSession(props.itemId)
    ])
    syllabus.value = syllabusData
    classroom.value = classroomData
    hydrateQuizAnswers()
    syncVisitedSlidesFromSession()
    if (visualizationResource.value) await loadVisualizationView()
  } finally {
    loading.value = false
  }
}

async function handleGenerateVisualization() {
  if (!classroom.value) return
  generatingVisualization.value = true
  try {
    const { data } = await generateClassroomVisualization(classroom.value.id, visualizationInstruction.value)
    classroom.value = data
    await loadVisualizationView()
    ElMessage.success('3D 物理演示已生成')
  } finally {
    generatingVisualization.value = false
  }
}

async function loadVisualizationView() {
  if (!visualizationResource.value) return
  loadingVisualizationView.value = true
  try {
    const { data } = await viewClassroomResource(visualizationResource.value.id)
    revokeVisualizationUrl()
    visualizationUrl.value = URL.createObjectURL(data)
  } finally {
    loadingVisualizationView.value = false
  }
}

async function handleSendDialogue() {
  if (!classroom.value || !chatMessage.value.trim()) return
  const message = chatMessage.value.trim()
  chatMessage.value = ''
  sendingDialogue.value = true
  try {
    const { data } = await sendClassroomDialogue(classroom.value.id, { message })
    classroom.value = data.session
  } finally {
    sendingDialogue.value = false
  }
}

function sendQuickAction(action: string) {
  if (!pptPackage.value) return
  chatMessage.value = action
  void handleSendDialogue()
}

function askGuidingQuestion(question: string) {
  chatMessage.value = question
  void handleSendDialogue()
}

async function handleSubmitQuiz() {
  if (!classroom.value) return
  submittingQuiz.value = true
  try {
    const { data } = await submitClassroomQuiz(classroom.value.id, { ...quizAnswers })
    classroom.value = data
    if (data.quiz_passed) activeGate.value = 'practice'
    ElMessage.success(data.quiz_passed ? '例题已通过' : '例题未通过，请修改后再提交')
  } finally {
    submittingQuiz.value = false
  }
}

function handleGateSelect(key: GateKey) {
  if (key !== 'ppt' && !classroom.value?.slides_completed) {
    activeGate.value = 'ppt'
    ElMessage.warning('请先完成课件学习')
    return
  }
  activeGate.value = key
}

function goToSlide(index: number) {
  if (!slideList.value.length) return
  activeSlideIndex.value = Math.min(Math.max(index, 0), slideList.value.length - 1)
  visitedSlideIndices.value = new Set([...visitedSlideIndices.value, activeSlideIndex.value])
}

async function handleCompleteSlides() {
  if (!classroom.value || !slideList.value.length) return
  const { data } = await completeClassroomSlides(classroom.value.id, {
    current_index: activeSlideIndex.value,
    total_slides: slideList.value.length,
    visited_indices: Array.from(visitedSlideIndices.value)
  })
  classroom.value = data
  activeGate.value = 'quiz'
  ElMessage.success('课件学习已完成，可以进入例题环节')
}

async function handleSubmitPractice() {
  if (!classroom.value) return
  submittingPractice.value = true
  try {
    const { data } = await submitClassroomPractice(classroom.value.id, { ...practiceForm })
    classroom.value = data
    if (data.practice_passed) activeGate.value = 'reflection'
    ElMessage.success(data.practice_passed ? '实操已通过' : '实操未通过，请根据反馈补充')
  } finally {
    submittingPractice.value = false
  }
}

async function handleSubmitReflection() {
  if (!classroom.value) return
  submittingReflection.value = true
  try {
    const { data } = await submitClassroomReflection(classroom.value.id, {
      reflection: reflectionForm.reflection,
      unresolved_questions: unresolvedQuestionsText.value.split('\n').map((line) => line.trim()).filter(Boolean),
      next_action: reflectionForm.next_action
    })
    classroom.value = data
    if (data.status === 'completed') {
      await refreshSyllabus()
      ElMessage.success('课堂已完成，学习进度已更新')
    } else {
      ElMessage.success(data.reflection_passed ? '复盘已通过' : '复盘未通过，请继续补充')
    }
  } finally {
    submittingReflection.value = false
  }
}

async function refreshSyllabus() {
  if (!props.projectId) return
  const { data } = await getCurrentSyllabus(props.projectId)
  syllabus.value = data
}

function hydrateQuizAnswers() {
  for (const question of quizQuestions.value) {
    if (!quizAnswers[question.id]) quizAnswers[question.id] = ''
  }
}

function syncVisitedSlidesFromSession() {
  const progress = classroom.value?.slide_progress || {}
  const rawVisited = Array.isArray(progress.visited_indices) ? progress.visited_indices : [0]
  const visited = rawVisited
    .map((index: unknown) => Number(index))
    .filter((index: number) => Number.isInteger(index) && index >= 0)
  visitedSlideIndices.value = new Set(visited.length ? visited : [0])
  const nextIndex = Number(progress.current_index)
  activeSlideIndex.value = Number.isInteger(nextIndex) && nextIndex >= 0 ? nextIndex : 0
  if (slideList.value.length) goToSlide(activeSlideIndex.value)
}

function latestSubmissionByType(type: string): ClassroomSubmissionRead | null {
  const submissions = classroom.value?.submissions.filter((submission) => submission.submission_type === type) || []
  return submissions[submissions.length - 1] || null
}

function downloadPpt() {
  if (!pptResource.value) return
  void downloadClassroomResource(pptResource.value.id).then(({ data }) => {
    downloadBlob(data, `${pptResource.value?.title || 'classroom'}.pptx`)
  })
}

function downloadVisualization() {
  if (!visualizationResource.value) return
  void downloadClassroomResource(visualizationResource.value.id).then(({ data }) => {
    downloadBlob(data, `${visualizationResource.value?.title || 'visualization'}.html`)
  })
}

function downloadBlob(data: Blob, filename: string) {
  const url = URL.createObjectURL(data)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}

function revokeVisualizationUrl() {
  if (visualizationUrl.value) URL.revokeObjectURL(visualizationUrl.value)
  visualizationUrl.value = ''
}

async function goBackToSyllabus() {
  if (!props.projectId) return
  await router.push({ name: 'project-syllabus', params: { projectId: props.projectId } })
}

function statusLabel(status: string) {
  const labels: Record<string, string> = {
    pending: '未开始',
    in_progress: '学习中',
    completed: '已完成',
    mastered: '已掌握',
    skipped: '已跳过'
  }
  return labels[status] || status
}

function statusType(status: string): '' | 'success' | 'warning' | 'info' | 'primary' {
  if (['completed', 'mastered'].includes(status)) return 'success'
  if (status === 'in_progress') return 'warning'
  if (status === 'skipped') return 'info'
  return 'primary'
}
</script>
