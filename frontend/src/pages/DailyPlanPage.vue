<template>
  <div class="page daily-plan-page todo-plan-page todo-workspace-page">
    <section class="todo-workspace-topbar panel-like">
      <div class="todo-workspace-title">
        <span>学习计划工作台</span>
        <strong>{{ selectedProject?.title || '每日学习工作台' }}</strong>
      </div>
      <div class="todo-workspace-actions">
        <el-select
          v-model="selectedProjectId"
          class="project-select"
          placeholder="选择学习项目"
          :loading="loadingProjects"
          @change="handleProjectChange"
        >
          <el-option v-for="project in projects" :key="project.id" :label="project.title" :value="project.id" />
        </el-select>
        <el-button type="primary" :loading="generating" :disabled="!selectedProjectId" @click="handleGeneratePlan">
          {{ activePlan ? '重新排期' : '生成计划' }}
        </el-button>
        <el-button :disabled="!selectedProjectId" @click="openSyllabus">
          管理清单
        </el-button>
      </div>
    </section>

    <el-empty v-if="!loadingProjects && !projects.length" description="暂无学习项目，请先在探索方向页构建项目。" />

    <section v-else class="todo-workspace-shell">
      <aside class="todo-issueboard panel-like">
        <header class="todo-issueboard-head">
          <div>
            <span>计划路线</span>
            <strong>{{ completedCount }}/{{ actionableCount }}</strong>
          </div>
          <div class="todo-issue-progress"><span :style="{ width: `${planProgress}%` }" /></div>
        </header>

        <section class="todo-plan-settings">
          <div class="todo-settings-row">
            <label>
              <span>开始日期</span>
              <el-date-picker v-model="form.start_date" type="date" value-format="YYYY-MM-DD" />
            </label>
            <label>
              <span>每日分钟</span>
              <el-input-number v-model="form.daily_minutes" :min="10" :max="300" :step="10" />
            </label>
          </div>
          <el-checkbox-group
            v-model="form.study_weekdays"
            class="todo-weekday-grid"
            @change="handleWeekdaysChange"
          >
            <el-checkbox-button v-for="day in weekdayOptions" :key="day.value" :label="day.value">
              {{ day.label }}
            </el-checkbox-button>
          </el-checkbox-group>
          <el-checkbox v-model="form.study_weekends" @change="handleWeekendsChange">周末也学习</el-checkbox>
        </section>

        <div v-if="loadingPlans" class="daily-plan-loading">正在加载计划...</div>
        <section v-else-if="!activePlan" class="todo-plan-create">
          <strong>还没有每日计划</strong>
          <p>生成后系统会按学习清单顺序、每日时长和可学习日自动排期。</p>
          <el-button type="primary" :loading="generating" :disabled="!selectedProjectId" @click="handleGeneratePlan">生成计划</el-button>
        </section>

        <div v-else class="todo-issue-list">
          <button
            v-for="day in visibleGroupedDays"
            :key="day.date"
            type="button"
            :class="{ active: activeDate === day.date, today: day.date === todayString }"
            @click="focusDay(day.date)"
          >
            <div>
              <span>{{ formatDayTitle(day.date) }}</span>
              <strong>{{ day.items.length }} 项 / {{ day.minutes }} 分钟</strong>
            </div>
            <small>{{ day.items.map((item) => item.title).join(' / ') }}</small>
          </button>
        </div>
      </aside>

      <main class="todo-focus-panel panel-like">
        <header class="todo-focus-head">
          <div>
            <span>{{ activeDate ? '选中日期' : '今日重点' }}</span>
            <h2>{{ activeDate ? formatDayTitle(activeDate) : todayFocusTitle }}</h2>
          </div>
          <el-tag v-if="activePlan" effect="plain">{{ activePlan.daily_minutes }} 分钟/天</el-tag>
        </header>

        <section v-if="activePlan" class="todo-focus-metrics">
          <button type="button" :class="{ active: activeFilter === 'today' && !activeDate }" @click="setFilter('today')">
            <span>今天</span><strong>{{ todayItems.length }}</strong>
          </button>
          <button type="button" :class="{ active: activeFilter === 'overdue' && !activeDate }" @click="setFilter('overdue')">
            <span>逾期</span><strong>{{ overdueItems.length }}</strong>
          </button>
          <button type="button" :class="{ active: activeFilter === 'upcoming' && !activeDate }" @click="setFilter('upcoming')">
            <span>后续</span><strong>{{ upcomingItems.length }}</strong>
          </button>
          <button type="button" :class="{ active: activeFilter === 'done' && !activeDate }" @click="setFilter('done')">
            <span>完成</span><strong>{{ completedItems.length }}</strong>
          </button>
        </section>

        <section v-if="activeTask" class="todo-current-card">
          <div class="todo-current-main">
            <span>当前任务</span>
            <h3>{{ activeTask.title }}</h3>
            <p>{{ activeTask.learning_focus }}</p>
            <div class="todo-task-gate" :class="{ locked: !activeTask.can_start && !isDone(activeTask), ready: activeTask.can_start && !isDone(activeTask) }">
              <strong>{{ taskGateLabel(activeTask) }}</strong>
              <span>{{ taskGateDescription(activeTask) }}</span>
            </div>
          </div>
          <div class="todo-current-actions">
            <el-button type="primary" :disabled="!activeTask.can_start" @click="handleStartLearning(activeTask)">
              {{ activeTask.can_start ? '进入课堂' : '等待解锁' }}
            </el-button>
            <el-button :loading="movingItemId === activeTask.id" @click="handleShiftItem(activeTask, 'next')">顺延</el-button>
          </div>
        </section>

        <section v-if="activePlan" class="todo-task-stack">
          <article
            v-for="item in visibleFilteredItems"
            :key="item.id"
            class="todo-work-card"
            :class="{ active: item.id === activeItemId, done: isDone(item), overdue: item.is_overdue }"
            @click="activeItemId = item.id"
          >
            <div class="todo-work-status">
              <span :class="{ done: isDone(item), ready: item.can_start && !isDone(item), locked: !item.can_start && !isDone(item) }" />
            </div>
            <div class="todo-work-body">
              <div class="todo-task-line">
                <el-tag :type="statusTagType(item.status)" effect="plain">{{ statusLabel(item.status) }}</el-tag>
                <span>{{ formatDayTitle(toDateInput(item.planned_date)) }}</span>
                <span>{{ item.estimated_minutes }} 分钟</span>
              </div>
              <h4>{{ item.title }}</h4>
              <p>{{ item.learning_focus }}</p>
              <div class="tags">
                <el-tag v-for="resource in item.resource_types" :key="resource" effect="plain">{{ resource }}</el-tag>
              </div>
            </div>
            <div class="todo-work-actions" @click.stop>
              <el-date-picker v-model="moveDates[item.id]" type="date" value-format="YYYY-MM-DD" placeholder="调整日期" />
              <el-button :loading="movingItemId === item.id" @click="handleShiftItem(item, 'previous')">提前</el-button>
              <el-button :loading="movingItemId === item.id" @click="handleShiftItem(item, 'next')">顺延</el-button>
              <el-button :loading="movingItemId === item.id" :disabled="!moveDates[item.id]" @click="handleMoveItem(item)">移动</el-button>
              <el-button @click="openSyllabusItem(item)">管理课程</el-button>
              <el-button type="primary" :disabled="!item.can_start" @click="handleStartLearning(item)">开始</el-button>
            </div>
          </article>
          <div v-if="filteredItems.length > visibleTaskLimit" class="todo-load-more">
            <span>已显示 {{ visibleFilteredItems.length }}/{{ filteredItems.length }}</span>
            <el-button @click="visibleTaskLimit += 20">显示更多</el-button>
          </div>
        </section>
      </main>

      <aside class="todo-coach-panel panel-like">
        <header>
          <div>
            <span>计划教练</span>
            <strong>复盘与画像提取</strong>
          </div>
          <el-tag v-if="latestProfileRevision" effect="plain">画像 v{{ latestProfileRevision }}</el-tag>
        </header>

        <div class="todo-coach-messages">
          <article v-for="message in coachMessages" :key="message.id" :class="message.role">
            <span>{{ message.role === 'user' ? '我' : '计划教练' }}</span>
            <p>{{ message.content }}</p>
          </article>
          <div v-if="coachLoading" class="todo-coach-thinking"><span></span><span></span><span></span></div>
        </div>

        <section v-if="profileSignals.length" class="todo-profile-signals">
          <span>本次提取</span>
          <div>
            <small v-for="signal in profileSignals" :key="signal">{{ signal }}</small>
          </div>
        </section>

        <div class="todo-coach-prompts">
          <button v-for="prompt in coachPromptChips" :key="prompt" type="button" @click="coachInput = prompt">
            {{ prompt }}
          </button>
        </div>

        <div class="todo-coach-input">
          <el-input
            v-model="coachInput"
            type="textarea"
            :rows="3"
            placeholder="告诉我今天学得怎么样、哪里卡住、要不要调整节奏..."
            @keydown.enter.exact.prevent="handleCoachSend"
          />
          <el-button type="primary" :loading="coachLoading" :disabled="!activePlan || !coachInput.trim()" @click="handleCoachSend">发送</el-button>
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
  generateDailyPlan,
  listDailyPlans,
  listLearningProjects,
  moveDailyPlanItem,
  sendDailyPlanCoachMessage,
  shiftDailyPlanItem,
  type DailyPlanItemRead,
  type DailyPlanRead,
  type LearningProjectRead
} from '../services/apiClient'

type TodoFilter = 'today' | 'overdue' | 'upcoming' | 'done' | 'all'
type CoachMessage = { id: string; role: 'user' | 'assistant'; content: string }

const props = defineProps<{ projectId: number | null }>()
const router = useRouter()

const projects = ref<LearningProjectRead[]>([])
const plans = ref<DailyPlanRead[]>([])
const selectedProjectId = ref<number | null>(props.projectId)
const activePlanId = ref<number | null>(null)
const activeFilter = ref<TodoFilter>('today')
const activeDate = ref('')
const activeItemId = ref<number | null>(null)
const visibleTaskLimit = ref(20)
const loadingProjects = ref(false)
const loadingPlans = ref(false)
const generating = ref(false)
const movingItemId = ref<number | null>(null)
const coachLoading = ref(false)
const coachInput = ref('')
const coachMessages = ref<CoachMessage[]>([])
const latestProfileRevision = ref<number | null>(null)
const extractedSignals = ref<Record<string, any>>({})
const moveDates = reactive<Record<number, string>>({})
const form = reactive({
  start_date: toDateInput(new Date()),
  daily_minutes: 40,
  study_weekends: false,
  study_weekdays: [0, 1, 2, 3, 4]
})
let syncingWeekendFields = false

const weekdayOptions = [
  { label: '周一', value: 0 },
  { label: '周二', value: 1 },
  { label: '周三', value: 2 },
  { label: '周四', value: 3 },
  { label: '周五', value: 4 },
  { label: '周六', value: 5 },
  { label: '周日', value: 6 }
]

const todayString = computed(() => toDateInput(new Date()))
const selectedProject = computed(() => projects.value.find((project) => project.id === selectedProjectId.value) || null)
const activePlan = computed(() => plans.value.find((plan) => plan.id === activePlanId.value) || null)
const allItems = computed(() => activePlan.value?.items || [])
const actionableItems = computed(() => allItems.value.filter((item) => item.status !== 'removed'))
const completedItems = computed(() => actionableItems.value.filter(isDone))
const todayItems = computed(() => actionableItems.value.filter((item) => toDateInput(item.planned_date) === todayString.value && !isDone(item)))
const overdueItems = computed(() => actionableItems.value.filter((item) => toDateInput(item.planned_date) < todayString.value && !isDone(item)))
const upcomingItems = computed(() => actionableItems.value.filter((item) => toDateInput(item.planned_date) > todayString.value && !isDone(item)))
const activeTask = computed(() => {
  if (activeItemId.value) {
    const selected = actionableItems.value.find((item) => item.id === activeItemId.value)
    if (selected && !isDone(selected)) return selected
  }
  const ordered = sortTodoItems(actionableItems.value.filter((item) => !isDone(item)))
  return ordered.find((item) => item.can_start) || ordered[0] || null
})
const completedCount = computed(() => completedItems.value.length)
const actionableCount = computed(() => actionableItems.value.length)
const planProgress = computed(() => actionableCount.value ? Math.round((completedCount.value / actionableCount.value) * 100) : 0)
const todayFocusTitle = computed(() => {
  if (todayItems.value.length) return '今天的学习任务'
  if (overdueItems.value.length) return '先处理逾期任务'
  if (upcomingItems.value.length) return '下一批学习任务'
  return '计划已完成'
})
const groupedDays = computed(() => {
  const groups = new Map<string, DailyPlanItemRead[]>()
  for (const item of actionableItems.value) {
    const date = toDateInput(item.planned_date)
    groups.set(date, [...(groups.get(date) || []), item])
  }
  return Array.from(groups.entries())
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([date, items]) => ({
      date,
      items: items.sort((left, right) => left.user_order - right.user_order),
      minutes: items.reduce((sum, item) => sum + item.estimated_minutes, 0)
    }))
})
const visibleGroupedDays = computed(() => groupedDays.value.slice(0, 60))
const filteredItems = computed(() => {
  const byDate = activeDate.value ? actionableItems.value.filter((item) => toDateInput(item.planned_date) === activeDate.value) : null
  if (byDate) return sortTodoItems(byDate)
  if (activeFilter.value === 'today') return sortTodoItems(todayItems.value)
  if (activeFilter.value === 'overdue') return sortTodoItems(overdueItems.value)
  if (activeFilter.value === 'upcoming') return sortTodoItems(upcomingItems.value)
  if (activeFilter.value === 'done') return sortTodoItems(completedItems.value)
  return sortTodoItems(actionableItems.value)
})
const visibleFilteredItems = computed(() => filteredItems.value.slice(0, visibleTaskLimit.value))
const coachPromptChips = computed(() => {
  const title = activeTask.value?.title || '今天的任务'
  return [
    `我今天完成了「${title}」，帮我总结并更新画像`,
    `我卡在「${title}」，帮我降低明天的学习阻力`,
    '我今天时间不够，帮我判断应该顺延哪一项'
  ]
})
const profileSignals = computed(() => {
  const signals: string[] = []
  const weak = Array.isArray(extractedSignals.value.weak_points) ? extractedSignals.value.weak_points : []
  const preference = Array.isArray(extractedSignals.value.resource_preference) ? extractedSignals.value.resource_preference : []
  const pace = extractedSignals.value.learning_pace
  signals.push(...weak.slice(0, 3).map((item) => `短板：${item}`))
  signals.push(...preference.slice(0, 2).map((item) => `偏好：${item}`))
  if (pace) signals.push(`节奏：${pace}`)
  return signals.slice(0, 6)
})

onMounted(loadProjects)

watch(
  () => props.projectId,
  async (projectId) => {
    selectedProjectId.value = projectId
    if (projectId) await loadPlans(projectId)
  }
)

watch(selectedProject, (project) => {
  if (project) form.daily_minutes = project.daily_minutes || 40
})

async function loadProjects() {
  loadingProjects.value = true
  try {
    const { data } = await listLearningProjects()
    projects.value = data
    if (!selectedProjectId.value && data.length) selectedProjectId.value = data[0].id
    if (selectedProjectId.value) await loadPlans(selectedProjectId.value)
  } finally {
    loadingProjects.value = false
  }
}

function handleWeekendsChange(value: string | number | boolean) {
  const enabled = Boolean(value)
  syncingWeekendFields = true
  form.study_weekends = enabled
  form.study_weekdays = normalizeWeekdaySelection(form.study_weekdays, enabled)
  syncingWeekendFields = false
}

function handleWeekdaysChange(value: Array<number | string>) {
  if (syncingWeekendFields) return
  const hasWeekend = value.some((day) => Number(day) >= 5)
  syncingWeekendFields = true
  form.study_weekends = hasWeekend
  form.study_weekdays = normalizeWeekdaySelection(value, hasWeekend)
  syncingWeekendFields = false
}

async function loadPlans(projectId: number) {
  loadingPlans.value = true
  try {
    const { data } = await listDailyPlans(projectId, 1)
    plans.value = data
    const current = data.find((plan) => plan.status === 'active') || data[0] || null
    activePlanId.value = current?.id || null
    hydrateFormFromPlan(current)
    setInitialFocus(current)
    seedCoachMessages()
  } finally {
    loadingPlans.value = false
  }
}

async function handleProjectChange(projectId: number | string) {
  selectedProjectId.value = Number(projectId)
  await router.push({ name: 'project-daily-plan', params: { projectId: Number(projectId) } })
  await loadPlans(Number(projectId))
}

async function handleGeneratePlan() {
  if (!selectedProjectId.value) return
  generating.value = true
  try {
    const { data } = await generateDailyPlan(selectedProjectId.value, {
      start_date: toBackendDate(form.start_date),
      daily_minutes: form.daily_minutes,
      study_weekends: form.study_weekends,
      study_weekdays: normalizeWeekdaySelection(form.study_weekdays, form.study_weekends),
      title: selectedProject.value ? `${selectedProject.value.title} 每日学习计划` : ''
    })
    plans.value = [data, ...plans.value.filter((plan) => plan.id !== data.id)]
    activePlanId.value = data.id
    hydrateMoveDates()
    setInitialFocus(data)
    seedCoachMessages()
    ElMessage.success('每日学习计划已生成')
  } finally {
    generating.value = false
  }
}

async function handleCoachSend() {
  if (!activePlan.value || !coachInput.value.trim()) return
  const content = coachInput.value.trim()
  coachInput.value = ''
  coachMessages.value.push({ id: `u-${Date.now()}`, role: 'user', content })
  coachLoading.value = true
  try {
    const { data } = await sendDailyPlanCoachMessage(activePlan.value.id, {
      message: content,
      active_item_id: activeTask.value?.id || null
    })
    replacePlan(data.plan)
    latestProfileRevision.value = data.profile_revision || null
    extractedSignals.value = data.extracted_profile_signals || {}
    coachMessages.value.push({ id: `a-${Date.now()}`, role: 'assistant', content: data.answer })
  } finally {
    coachLoading.value = false
  }
}

async function handleMoveItem(item: DailyPlanItemRead) {
  const target = moveDates[item.id]
  if (!target) return
  movingItemId.value = item.id
  try {
    const { data } = await moveDailyPlanItem(item.id, toBackendDate(target))
    replacePlan(data)
    activeDate.value = target
    ElMessage.success('任务日期已调整')
  } finally {
    movingItemId.value = null
  }
}

async function handleShiftItem(item: DailyPlanItemRead, direction: 'next' | 'previous') {
  movingItemId.value = item.id
  try {
    const { data } = await shiftDailyPlanItem(item.id, direction)
    replacePlan(data)
    ElMessage.success(direction === 'next' ? '已顺延到下一个学习日' : '已提前到上一个学习日')
  } finally {
    movingItemId.value = null
  }
}

async function handleStartLearning(item: DailyPlanItemRead) {
  if (!item.syllabus_item_id) return
  await router.push({
    name: 'project-classroom',
    params: { projectId: item.project_id, itemId: item.syllabus_item_id }
  })
}

async function openSyllabus() {
  if (!selectedProjectId.value) return
  await router.push({ name: 'project-syllabus', params: { projectId: selectedProjectId.value } })
}

async function openSyllabusItem(item: DailyPlanItemRead) {
  if (!item.syllabus_item_id) return
  await router.push({
    name: 'project-syllabus',
    params: { projectId: item.project_id },
    hash: `#item-${item.syllabus_item_id}`
  })
}

function setFilter(filter: TodoFilter) {
  activeFilter.value = filter
  activeDate.value = ''
  visibleTaskLimit.value = 20
}

function focusDay(date: string) {
  activeDate.value = date
  visibleTaskLimit.value = 20
  const first = actionableItems.value.find((item) => toDateInput(item.planned_date) === date && !isDone(item))
  activeItemId.value = first?.id || null
}

function replacePlan(plan: DailyPlanRead) {
  plans.value = plans.value.map((item) => (item.id === plan.id ? plan : item))
  if (!plans.value.find((item) => item.id === plan.id)) plans.value.unshift(plan)
  activePlanId.value = plan.id
  hydrateMoveDates()
}

function hydrateFormFromPlan(plan: DailyPlanRead | null) {
  if (!plan) return
  form.start_date = toDateInput(plan.start_date)
  form.daily_minutes = plan.daily_minutes
  syncingWeekendFields = true
  form.study_weekdays = normalizeWeekdaySelection(plan.study_weekdays.length ? plan.study_weekdays : [0, 1, 2, 3, 4], plan.study_weekends)
  form.study_weekends = plan.study_weekends || form.study_weekdays.some((day) => day >= 5)
  syncingWeekendFields = false
  hydrateMoveDates()
}

function hydrateMoveDates() {
  for (const item of allItems.value) {
    moveDates[item.id] = toDateInput(item.planned_date)
  }
}

function setInitialFocus(plan: DailyPlanRead | null) {
  activeDate.value = ''
  if (!plan?.items.length) {
    activeFilter.value = 'today'
    activeItemId.value = null
    return
  }
  const active = plan.items.filter((item) => item.status !== 'removed' && !isDone(item))
  if (active.some((item) => toDateInput(item.planned_date) === todayString.value)) activeFilter.value = 'today'
  else if (active.some((item) => toDateInput(item.planned_date) < todayString.value)) activeFilter.value = 'overdue'
  else activeFilter.value = 'upcoming'
  const next = sortTodoItems(active).find((item) => item.can_start) || sortTodoItems(active)[0]
  activeItemId.value = next?.id || null
}

function seedCoachMessages() {
  coachMessages.value = [
    {
      id: `seed-${activePlanId.value || 0}`,
      role: 'assistant',
      content: activePlan.value
        ? '我会根据你的每日复盘提取学习节奏、偏好、短板和掌握度，用于后续课堂个性化生成。'
        : '生成每日计划后，我可以帮你复盘、调整节奏并更新学习画像。'
    }
  ]
  extractedSignals.value = {}
  latestProfileRevision.value = null
}

function sortTodoItems(items: DailyPlanItemRead[]) {
  return [...items].sort((left, right) => {
    const dateOrder = toDateInput(left.planned_date).localeCompare(toDateInput(right.planned_date))
    if (dateOrder !== 0) return dateOrder
    return left.user_order - right.user_order
  })
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

function normalizeWeekdaySelection(values: Array<number | string>, studyWeekends = false) {
  const normalized = new Set(
    values
      .map((value) => Number(value))
      .filter((value) => Number.isInteger(value) && value >= 0 && value <= 6)
  )
  if (studyWeekends) {
    normalized.add(5)
    normalized.add(6)
  } else {
    normalized.delete(5)
    normalized.delete(6)
  }
  if (!normalized.size) return [0, 1, 2, 3, 4]
  return [...normalized].sort((left, right) => left - right)
}

function formatDayTitle(value: string) {
  const date = new Date(toBackendDate(value))
  const week = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'][date.getDay()]
  return `${value} ${week}`
}

function statusLabel(status: string) {
  const labels: Record<string, string> = {
    pending: '待学习',
    in_progress: '学习中',
    completed: '已完成',
    mastered: '已掌握',
    removed: '已移除',
    deleted: '已删除',
    skipped: '已跳过'
  }
  return labels[status] || status
}

function statusTagType(status: string) {
  const types: Record<string, 'success' | 'warning' | 'info' | 'danger'> = {
    pending: 'warning',
    in_progress: 'info',
    completed: 'success',
    mastered: 'success',
    removed: 'danger',
    deleted: 'danger',
    skipped: 'danger'
  }
  return types[status] || 'info'
}

function taskGateLabel(item: DailyPlanItemRead) {
  if (isDone(item)) return '已完成'
  if (item.status === 'removed') return '已从学习清单移除'
  if (item.can_start) return '可开始'
  if (item.is_overdue) return '需处理前置任务'
  return '排队中'
}

function taskGateDescription(item: DailyPlanItemRead) {
  if (isDone(item)) return '该学习项已通过课堂、练习、实操或复盘要求。'
  if (item.status === 'removed') return '课程删除请在学习清单处理，计划页不直接删除课程。'
  if (item.can_start) return '进入课堂后需完成课件、例题、实操和复盘，系统会自动更新进度。'
  if (item.is_overdue) return '请先完成更早的未完成学习项，避免跳过关键前置内容。'
  return '系统会按日期、顺序和学习清单进度自动解锁。'
}
</script>
