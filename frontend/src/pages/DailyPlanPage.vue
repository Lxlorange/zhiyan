<template>
  <div class="page daily-plan-page todo-plan-page todo-workspace-page">
    <section class="todo-workspace-topbar panel-like">
      <div class="todo-workspace-title">
        <span>每日学习计划</span>
        <strong>{{ projectCount }} 个项目 · {{ totalCount }} 项任务</strong>
      </div>
      <div class="todo-workspace-actions">
        <el-button type="primary" :loading="generating" @click="handleGenerateAllPlans">生成所有计划</el-button>
        <el-button :loading="loadingPlans" @click="handleRefreshAll">刷新</el-button>
      </div>
    </section>
    <el-empty v-if="!loadingProjects && !projects.length" description="暂无学习项目，请先在探索方向页构建项目。" />
    <section v-else class="todo-workspace-shell">
      <aside class="todo-issueboard panel-like">
        <div v-if="loadingPlans" class="daily-plan-loading">正在加载计划...</div>
        <div v-else-if="plans.length === 0" class="todo-plan-create">
          <strong>还没有每日计划</strong>
          <p>点击"生成所有计划"自动为每个项目生成排期。</p>
          <el-button type="primary" :loading="generating" @click="handleGenerateAllPlans">生成所有计划</el-button>
        </div>
        <div v-else class="todo-issue-list">
          <button v-for="day in dateDays" :key="day.date" type="button"
            :class="{ active: activeDate === day.date, today: day.date === todayString }"
            @click="focusDay(day.date)">
            <div>
              <span>{{ formatDayTitle(day.date) }}</span>
              <strong>{{ day.items.length }} 项 / {{ day.totalMinutes }} 分钟</strong>
            </div>
            <small>{{ day.projectLabels.join('、') }}</small>
          </button>
        </div>
        <section class="todo-coach-panel">
          <header>
            <span>AI 学习教练</span>
            <strong v-if="coachPlanProjectId">{{ getProjectName(coachPlanProjectId) }}</strong>
          </header>
          <div class="todo-coach-messages" ref="coachScrollRef">
            <article v-for="msg in coachMessages" :key="msg.id" :class="msg.role === 'user' ? 'user' : 'assistant'">
              <span v-if="msg.role === 'user'">我</span>
              <p>{{ msg.content }}</p>
            </article>
            <div v-if="coachLoading" class="todo-coach-thinking"><span>·</span><span>·</span><span>·</span></div>
          </div>
          <div class="todo-coach-input">
            <el-input v-model="coachInput" placeholder="跟教练聊聊学习进展…"
              :disabled="!coachPlanId" @keyup.enter="handleCoachSend" />
            <el-button :disabled="!coachInput.trim() || !coachPlanId" @click="handleCoachSend">发送</el-button>
          </div>
        </section>
      </aside>
      <main class="todo-focus-panel panel-like">
        <section class="todo-focus-filter-bar">
          <el-radio-group v-model="activeFilter" size="small">
            <el-radio-button value="todo">待学习</el-radio-button>
            <el-radio-button value="done">已完成</el-radio-button>
            <el-radio-button value="all">全部</el-radio-button>
          </el-radio-group>
          <span class="todo-focus-filter-hint">{{ activeDate ? formatDayTitle(activeDate) : (activeFilter === 'todo' ? '待学习' : activeFilter === 'done' ? '已完成' : '全部') }}</span>
        </section>
        <div v-if="visibleDateGroups.length === 0" class="todo-empty-prompt" style="margin: 2em auto;">
          <strong>{{ activeDate ? '该日期暂无匹配任务' : (activeFilter === 'todo' ? '所有任务已完成！' : '暂无匹配任务') }}</strong>
        </div>
        <div v-else class="todo-groups-stack">
          <div v-for="group in visibleDateGroups" :key="group.date" class="todo-date-group">
            <div class="todo-date-head">
              <span>{{ formatDayTitle(group.date) }}</span>
              <span class="todo-date-badge">{{ group.items.length }} 项</span>
            </div>
            <div v-for="(item, idx) in group.items" :key="item.id" class="todo-item-card">
              <div class="todo-item-tags">
                <el-tag size="small" effect="plain">{{ getProjectName(item.project_id) }}</el-tag>
                <el-tag size="small" :type="statusTagType(item.status)">{{ statusLabel(item.status) }}</el-tag>
                <span class="todo-item-time">{{ item.estimated_minutes }} 分钟</span>
              </div>
              <div class="todo-item-title">{{ item.title }}</div>
              <div v-if="item.learning_focus" class="todo-item-focus">{{ item.learning_focus }}</div>
              <div class="todo-item-actions">
                <el-button-group>
                  <el-button size="small" :disabled="isFirstInGroup(item, group.items)" @click="handleReorderItem(item.id, 'up')">↑</el-button>
                  <el-button size="small" :disabled="isLastInGroup(item, group.items)" @click="handleReorderItem(item.id, 'down')">↓</el-button>
                </el-button-group>
                <el-date-picker v-model="moveDates[item.id]" type="date" value-format="YYYY-MM-DD" size="small" placeholder="移动日期" @change="handleMoveDate(item.id, $event)" />
                <el-button size="small" @click="openSyllabus(item)">课程</el-button>
                <el-button size="small" type="primary" :disabled="!item.can_start || isDone(item)" @click="startItem(item)">{{ taskGateLabel(item) }}</el-button>
              </div>
            </div>
          </div>
        </div>
      </main>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  generateDailyPlan,
  listDailyPlans,
  listLearningProjects,
  moveDailyPlanItem,
  reorderDailyPlanItem,
  sendDailyPlanCoachMessage,
  shiftDailyPlanItem,
  type DailyPlanItemRead,
  type DailyPlanRead,
  type LearningProjectRead
} from '../services/apiClient'

type TodoFilter = 'todo' | 'done' | 'all'
type CoachMessage = { id: string; role: 'user' | 'assistant'; content: string }

const router = useRouter()
const projects = ref<LearningProjectRead[]>([])
const plans = ref<DailyPlanRead[]>([])
const activeFilter = ref<TodoFilter>('todo')
const activeDate = ref('')
const loadingProjects = ref(false)
const loadingPlans = ref(false)
const generating = ref(false)
const coachLoading = ref(false)
const coachInput = ref('')
const coachMessages = ref<CoachMessage[]>([])
const extractedSignals = ref<Record<string, any>>({})
const latestProfileRevision = ref<number | null>(null)
const moveDates = reactive<Record<number, string>>({})
const coachPlanId = ref<number | null>(null)
const coachPlanProjectId = ref<number | null>(null)
const coachScrollRef = ref<HTMLElement | null>(null)

const todayString = computed(() => toDateInput(new Date()))

const projectMap = computed(() => {
  const map = new Map<number, LearningProjectRead>()
  for (const p of projects.value) map.set(p.id, p)
  return map
})

function getProjectName(projectId: number): string {
  return projectMap.value.get(projectId)?.title || `项目${projectId}`
}

const allItems = computed(() => {
  const items: DailyPlanItemRead[] = []
  for (const plan of plans.value) {
    for (const item of plan.items) {
      if (item.status !== 'removed' && item.status !== 'deleted') items.push(item)
    }
  }
  return items
})

const projectCount = computed(() => projects.value.length)
const totalCount = computed(() => allItems.value.length)
const todoItems = computed(() => allItems.value.filter((item) => !isDone(item)))
const doneItems = computed(() => allItems.value.filter((item) => isDone(item)))

const dateDays = computed(() => {
  const groups = new Map<string, DailyPlanItemRead[]>()
  for (const item of allItems.value) {
    const date = toDateInput(item.planned_date)
    if (!date) continue
    if (!groups.has(date)) groups.set(date, [])
    groups.get(date)!.push(item)
  }
  return [...groups.entries()].sort(([a], [b]) => a.localeCompare(b)).map(([date, items]) => {
    const projectIds = new Set(items.map((item) => item.project_id))
    const projectLabels = [...projectIds].map((pid) => getProjectName(pid))
    const totalMinutes = items.reduce((sum, i) => sum + (i.estimated_minutes || 0), 0)
    return { date, items, projectLabels, totalMinutes }
  })
})

const visibleDateGroups = computed(() => {
  const groups = new Map<string, DailyPlanItemRead[]>()
  const source = activeFilter.value === 'done' ? doneItems.value
    : activeFilter.value === 'todo' ? todoItems.value : allItems.value
  const filtered = activeDate.value
    ? source.filter((item) => toDateInput(item.planned_date) === activeDate.value) : source
  for (const item of filtered) {
    const date = toDateInput(item.planned_date)
    if (!date) continue
    if (!groups.has(date)) groups.set(date, [])
    groups.get(date)!.push(item)
  }
  return [...groups.entries()].sort(([a], [b]) => a.localeCompare(b)).map(([date, items]) => ({
    date,
    items: [...items].sort((a, b) => a.user_order - b.user_order)
  }))
})

async function loadData() {
  loadingProjects.value = true
  loadingPlans.value = true
  try {
    const { data: projectList } = await listLearningProjects()
    projects.value = projectList
    const planList: DailyPlanRead[] = []
    for (const project of projectList) {
      try {
        const { data: projectPlans } = await listDailyPlans(project.id, 1)
        if (projectPlans.length > 0) planList.push(projectPlans[0])
      } catch { /* no plans */ }
    }
    plans.value = planList
    if (planList.length > 0) {
      coachPlanId.value = planList[0].id
      coachPlanProjectId.value = planList[0].project_id
    }
    seedCoachMessages()
    hydrateMoveDates()
  } finally {
    loadingProjects.value = false
    loadingPlans.value = false
  }
}

async function handleGenerateAllPlans() {
  generating.value = true
  try {
    const existingProjectIds = new Set(plans.value.map((p) => p.project_id))
    const pendingProjects = projects.value.filter((p) => !existingProjectIds.has(p.id))
    if (pendingProjects.length === 0) {
      ElMessage.info('所有项目已有每日计划')
      return
    }
    const newPlans: DailyPlanRead[] = []
    for (const project of pendingProjects) {
      try {
        const { data } = await generateDailyPlan(project.id, {
          start_date: toBackendDate(toDateInput(new Date())),
          daily_minutes: 40,
          study_weekends: false,
          study_weekdays: [0, 1, 2, 3, 4],
          title: `${project.title} 每日学习计划`
        })
        newPlans.push(data)
      } catch { /* skip */ }
    }
    plans.value = [...plans.value, ...newPlans]
    if (!coachPlanId.value && newPlans.length > 0) {
      coachPlanId.value = newPlans[0].id
      coachPlanProjectId.value = newPlans[0].project_id
    }
    seedCoachMessages()
    hydrateMoveDates()
    ElMessage.success(`已为 ${newPlans.length} 个项目生成计划`)
  } finally { generating.value = false }
}

async function handleRefreshAll() {
  await loadData()
  ElMessage.success('已刷新')
}

async function handleShiftItem(itemId: number, direction: 'previous' | 'next') {
  try {
    const { data } = await shiftDailyPlanItem(itemId, direction)
    plans.value = plans.value.map((p) => (p.id === data.id ? data : p))
    hydrateMoveDates()
    ElMessage.success(direction === 'next' ? '已顺延' : '已提前')
  } finally {}
}

async function handleReorderItem(itemId: number, direction: 'up' | 'down') {
  try {
    await reorderDailyPlanItem(itemId, direction)
    await loadData()
    hydrateMoveDates()
    ElMessage.success('学习顺序已调整')
  } finally {}
}

async function handleMoveDate(itemId: number, plannedDate: string) {
  if (!plannedDate) return
  try {
    const { data } = await moveDailyPlanItem(itemId, toBackendDate(plannedDate))
    plans.value = plans.value.map((p) => (p.id === data.id ? data : p))
    activeDate.value = plannedDate
    hydrateMoveDates()
    ElMessage.success('任务日期已调整')
  } finally {}
}

async function startItem(item: DailyPlanItemRead) {
  if (!item.syllabus_item_id) return
  await router.push({
    name: 'project-classroom',
    params: { projectId: item.project_id, itemId: item.syllabus_item_id }
  })
}

async function openSyllabus(item: DailyPlanItemRead) {
  if (!item.syllabus_item_id) return
  await router.push({
    name: 'project-syllabus',
    params: { projectId: item.project_id },
    query: { itemId: String(item.syllabus_item_id) }
  })
}

async function handleCoachSend() {
  if (!coachPlanId.value || !coachInput.value.trim()) return
  const content = coachInput.value.trim()
  coachInput.value = ''
  coachMessages.value.push({ id: `u-${Date.now()}`, role: 'user', content })
  coachLoading.value = true
  try {
    const { data } = await sendDailyPlanCoachMessage(coachPlanId.value, { message: content })
    plans.value = plans.value.map((p) => (p.id === data.plan.id ? data.plan : p))
    latestProfileRevision.value = data.profile_revision || null
    extractedSignals.value = data.extracted_profile_signals || {}
    coachMessages.value.push({ id: `a-${Date.now()}`, role: 'assistant', content: data.answer })
    nextTick(scrollCoach)
  } finally { coachLoading.value = false }
}

function scrollCoach() {
  if (coachScrollRef.value) coachScrollRef.value.scrollTop = coachScrollRef.value.scrollHeight
}

function seedCoachMessages() {
  coachMessages.value = [{ id: `seed-${coachPlanId.value || 0}`, role: 'assistant', content: plans.value.length > 0 ? '我是你的跨项目学习教练。我可以帮你分析学习节奏、调整排期，并根据你的表现更新学习画像。' : '生成每日计划后，我可以帮你复盘、调整节奏并更新学习画像。' }]
  extractedSignals.value = {}
  latestProfileRevision.value = null
}

function focusDay(date: string) {
  activeDate.value = activeDate.value === date ? '' : date
}

function hydrateMoveDates() {
  for (const item of allItems.value) {
    moveDates[item.id] = toDateInput(item.planned_date)
  }
}

function isDone(item: DailyPlanItemRead) {
  return item.status === 'completed' || item.status === 'mastered'
}

function toDateInput(value: string | Date) {
  const date = value instanceof Date ? value : new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function toBackendDate(value: string) {
  return `${value}T00:00:00`
}

function formatDayTitle(value: string) {
  const date = new Date(toBackendDate(value))
  const week = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'][date.getDay()]
  return `${value} ${week}`
}

function statusLabel(status: string) {
  const labels: Record<string, string> = { pending: '待学习', in_progress: '学习中', completed: '已完成', mastered: '已掌握', removed: '已移除', deleted: '已删除', skipped: '已跳过' }
  return labels[status] || status
}

function statusTagType(status: string): 'success' | 'warning' | 'info' | 'danger' {
  const types: Record<string, 'success' | 'warning' | 'info' | 'danger'> = { pending: 'warning', in_progress: 'info', completed: 'success', mastered: 'success', removed: 'danger', deleted: 'danger', skipped: 'danger' }
  return types[status] || 'info'
}

function taskGateLabel(item: DailyPlanItemRead) {
  if (isDone(item)) return '已完成'
  if (item.status === 'removed') return '已移除'
  if (item.can_start) return '开始学习'
  if (item.is_overdue) return '需处理前置'
  return '排队中'
}

function isFirstInGroup(item: DailyPlanItemRead, items: DailyPlanItemRead[]) {
  return items.length < 2 || items[0].id === item.id
}
function isLastInGroup(item: DailyPlanItemRead, items: DailyPlanItemRead[]) {
  return items.length < 2 || items[items.length - 1].id === item.id
}

onMounted(() => { loadData() })
</script>
