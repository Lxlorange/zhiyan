<template>
  <div class="page classroom-page">
    <section class="page-hero classroom-hero">
      <div>
        <p class="eyebrow">OpenMAIC Style Classroom</p>
        <h2>{{ currentItem?.title || 'AI 课堂' }}</h2>
        <p>{{ currentItem?.objective || '课堂需要完成课件、例题、实操和复盘四个环节，全部通过后才会自动完成学习项。' }}</p>
      </div>
      <div class="classroom-hero-actions">
        <el-button @click="goBackToSyllabus">返回学习清单</el-button>
        <el-tag v-if="currentItem" :type="statusType(currentItem.status)">{{ statusLabel(currentItem.status) }}</el-tag>
      </div>
    </section>

    <el-empty v-if="!projectId || !itemId" description="缺少课堂参数，请从项目学习清单进入课堂。" />
    <section v-else-if="loading" class="panel-like classroom-loading">正在加载课堂...</section>
    <el-empty v-else-if="!currentItem || !classroom" description="没有找到当前课堂，请返回学习清单重新进入。" />

    <section v-else class="classroom-layout">
      <aside class="classroom-outline panel-like">
        <div class="classroom-outline-head">
          <span>学习项</span>
          <strong>{{ currentItem.title }}</strong>
          <p>{{ currentItem.stage }} / {{ currentItem.item_type }} / {{ currentItem.difficulty }}</p>
        </div>

        <div class="classroom-meter">
          <span>完成闸门</span>
          <strong>{{ completedGateCount }}/4</strong>
          <el-progress :percentage="gateProgress" :stroke-width="10" />
        </div>

        <nav class="classroom-section-nav" aria-label="课堂闸门">
          <button
            v-for="gate in gates"
            :key="gate.key"
            type="button"
            :class="{ active: activeGate === gate.key, viewed: gate.done }"
            @click="handleGateSelect(gate.key)"
          >
            <span>{{ gate.title }}</span>
            <small>{{ gate.done ? '已通过' : '待完成' }}</small>
          </button>
        </nav>
      </aside>

      <main class="classroom-main panel-like">
        <header class="classroom-main-head">
          <div>
            <span>{{ activeGateMeta.kind }}</span>
            <h3>{{ activeGateMeta.title }}</h3>
          </div>
          <el-tag :type="activeGateMeta.done ? 'success' : 'warning'" effect="plain">
            {{ activeGateMeta.done ? '已通过' : '待完成' }}
          </el-tag>
        </header>

        <section v-if="activeGate === 'ppt'" class="classroom-task-card">
          <div class="task-copy">
            <h4>生成并学习课堂 PPT</h4>
            <p>参考 OpenMAIC 的 slides、quizzes、interactive practice、PBL reflection 组织方式，为当前学习项生成可下载课件和后续任务。</p>
          </div>
          <el-input v-model="pptInstruction" type="textarea" :rows="3" placeholder="可选：补充 PPT 风格、重点、案例或公式要求" />
          <div class="classroom-action-row">
            <el-button type="primary" :loading="generatingPpt" @click="handleGeneratePpt">生成 PPT 课件</el-button>
            <el-button v-if="pptResource" @click="downloadPpt">下载 PPT</el-button>
          </div>
          <section v-if="pptPackage" class="slide-player">
            <div class="slide-stage">
              <div class="slide-canvas">
                <div class="slide-count">Slide {{ activeSlideIndex + 1 }} / {{ slideList.length }}</div>
                <h4>{{ currentSlide?.title }}</h4>
                <ul>
                  <li v-for="bullet in currentSlide?.bullets || []" :key="bullet">{{ bullet }}</li>
                </ul>
              </div>
              <div class="slide-notes">
                <span>AI Teacher Notes</span>
                <p>{{ currentSlide?.speaker_notes || '围绕当前页讲解核心概念、应用场景和易错点。' }}</p>
              </div>
            </div>

            <div class="slide-controls">
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
              <el-button
                type="success"
                :disabled="!allSlidesViewed || classroom?.slides_completed"
                @click="handleCompleteSlides"
              >
                {{ classroom?.slides_completed ? '课件学习已完成' : `完成课件学习 ${slidesVisitedCount}/${slideList.length}` }}
              </el-button>
            </div>
          </section>
        </section>

        <section v-else-if="activeGate === 'quiz'" class="classroom-task-card">
          <div class="task-copy">
            <h4>回答课堂例题</h4>
            <p>例题来自 PPT 生成结果，必须达到 70 分以上才能进入完成条件。</p>
          </div>
          <el-alert v-if="!classroom?.slides_completed" title="请先翻完动态课件并点击完成课件学习" type="warning" :closable="false" />
          <div v-else class="quiz-list">
            <label v-for="question in quizQuestions" :key="question.id">
              <span>{{ question.id }}. {{ question.prompt }}</span>
              <el-input v-model="quizAnswers[question.id]" placeholder="填写你的答案" />
            </label>
          </div>
          <div class="classroom-action-row">
            <el-button type="primary" :disabled="!classroom?.slides_completed" :loading="submittingQuiz" @click="handleSubmitQuiz">提交例题</el-button>
          </div>
          <p v-if="latestQuizFeedback" class="task-feedback">{{ latestQuizFeedback }}</p>
        </section>

        <section v-else-if="activeGate === 'practice'" class="classroom-task-card">
          <div class="task-copy">
            <h4>完成实操任务</h4>
            <p>{{ practiceSpec?.title || '生成 PPT 后会在这里显示实操任务。' }}</p>
          </div>
          <div v-if="practiceSpec" class="classroom-point-list">
            <div v-for="step in practiceSteps" :key="step"><span>{{ step }}</span></div>
          </div>
          <el-input v-model="practiceForm.artifact_url" placeholder="产物链接或文件路径，可选" />
          <el-input v-model="practiceForm.key_result" type="textarea" :rows="3" placeholder="关键结果，例如指标、截图描述、运行结果" />
          <el-input v-model="practiceForm.report" type="textarea" :rows="7" placeholder="实操报告：说明你做了什么、如何验证、遇到什么问题、结果是否达到标准" />
          <div class="classroom-action-row">
            <el-button type="primary" :disabled="!pptPackage" :loading="submittingPractice" @click="handleSubmitPractice">提交实操</el-button>
          </div>
          <p v-if="latestPracticeFeedback" class="task-feedback">{{ latestPracticeFeedback }}</p>
        </section>

        <section v-else class="classroom-task-card">
          <div class="task-copy">
            <h4>提交学习复盘</h4>
            <p>复盘必须具体到知识点、证据和下一步行动，系统会用它更新后续学习路径。</p>
          </div>
          <div v-if="reflectionPrompts.length" class="classroom-prompts">
            <div v-for="prompt in reflectionPrompts" :key="prompt">{{ prompt }}</div>
          </div>
          <el-input v-model="reflectionForm.reflection" type="textarea" :rows="8" placeholder="写下本节学到的内容、完成证据、仍然薄弱的知识点" />
          <el-input v-model="unresolvedQuestionsText" type="textarea" :rows="3" placeholder="未解决问题，每行一个" />
          <el-input v-model="reflectionForm.next_action" placeholder="下一步行动" />
          <div class="classroom-action-row">
            <el-button type="primary" :disabled="!pptPackage" :loading="submittingReflection" @click="handleSubmitReflection">提交复盘</el-button>
          </div>
          <p v-if="latestReflectionFeedback" class="task-feedback">{{ latestReflectionFeedback }}</p>
        </section>
      </main>

      <aside class="classroom-inspector panel-like">
        <div class="inspector-block">
          <span>课堂状态</span>
          <strong>{{ classroom.status }}</strong>
          <p>四个闸门全部通过后，学习项才会自动写回完成状态。</p>
        </div>
        <div class="inspector-block">
          <span>完成标准</span>
          <p>{{ currentItem.completion_criteria }}</p>
        </div>
        <div class="inspector-block">
          <span>最近反馈</span>
          <p>{{ latestFeedback || '还没有提交记录。' }}</p>
        </div>
        <div class="inspector-block">
          <span>知识点</span>
          <div class="classroom-tags">
            <el-tag v-for="point in currentItem.knowledge_points" :key="point" effect="plain">{{ point }}</el-tag>
          </div>
        </div>
      </aside>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  completeClassroomSlides,
  downloadClassroomResource,
  generateClassroomPpt,
  getCurrentSyllabus,
  getOrCreateClassroomSession,
  submitClassroomPractice,
  submitClassroomQuiz,
  submitClassroomReflection,
  type ClassroomResourceRead,
  type ClassroomSessionRead,
  type ClassroomSubmissionRead,
  type SyllabusVersionRead
} from '../services/apiClient'

type GateKey = 'ppt' | 'quiz' | 'practice' | 'reflection'

const props = defineProps<{ projectId: number | null; itemId: number | null }>()
const router = useRouter()
const loading = ref(false)
const generatingPpt = ref(false)
const submittingQuiz = ref(false)
const submittingPractice = ref(false)
const submittingReflection = ref(false)
const syllabus = ref<SyllabusVersionRead | null>(null)
const classroom = ref<ClassroomSessionRead | null>(null)
const activeGate = ref<GateKey>('ppt')
const activeSlideIndex = ref(0)
const visitedSlideIndices = ref<Set<number>>(new Set([0]))
const pptInstruction = ref('')
const unresolvedQuestionsText = ref('')
const quizAnswers = reactive<Record<string, string>>({})
const practiceForm = reactive({ report: '', artifact_url: '', key_result: '' })
const reflectionForm = reactive({ reflection: '', next_action: '' })

const currentItem = computed(() => syllabus.value?.items.find((item) => item.id === props.itemId) || null)
const pptResource = computed<ClassroomResourceRead | null>(() => {
  if (!classroom.value?.ppt_resource_id) return null
  return classroom.value.resources.find((resource) => resource.id === classroom.value?.ppt_resource_id) || null
})
const pptPackage = computed<Record<string, any> | null>(() => pptResource.value?.content_data || null)
const slideList = computed<any[]>(() => pptPackage.value?.slides || [])
const quizQuestions = computed<any[]>(() => pptPackage.value?.quiz || [])
const currentSlide = computed(() => slideList.value[activeSlideIndex.value] || null)
const slidesVisitedCount = computed(() => visitedSlideIndices.value.size)
const allSlidesViewed = computed(() => Boolean(slideList.value.length) && slidesVisitedCount.value >= slideList.value.length)
const practiceSpec = computed(() => pptPackage.value?.practice || null)
const practiceSteps = computed<string[]>(() => practiceSpec.value?.steps || [])
const reflectionPrompts = computed<string[]>(() => pptPackage.value?.reflection_prompts || [])
const gates = computed(() => [
  { key: 'ppt' as GateKey, title: '课件学习', kind: '动态课件', done: Boolean(classroom.value?.slides_completed) },
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

onMounted(loadClassroom)
watch(() => [props.projectId, props.itemId] as const, () => loadClassroom())

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
  } finally {
    loading.value = false
  }
}

async function handleGeneratePpt() {
  if (!classroom.value) return
  generatingPpt.value = true
  try {
    const { data } = await generateClassroomPpt(classroom.value.id, pptInstruction.value)
    classroom.value = data
    hydrateQuizAnswers()
    syncVisitedSlidesFromSession()
    ElMessage.success('PPT 课件已生成')
  } finally {
    generatingPpt.value = false
  }
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
    ElMessage.warning('请先翻完动态课件并完成课件学习')
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
      ElMessage.success('课堂已完成，学习进度已自动更新')
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
    const url = URL.createObjectURL(data)
    const link = document.createElement('a')
    link.href = url
    link.download = `${pptResource.value?.title || 'classroom'}.pptx`
    link.click()
    URL.revokeObjectURL(url)
  })
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
