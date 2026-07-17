<template>
  <div class="page daily-plan-page todo-plan-page">
    <section class="page-hero daily-plan-hero todo-plan-hero">
      <div>
        <p class="eyebrow">Learning Todo</p>
        <h2>{{ selectedProject?.title || '每日学习 TODO' }}</h2>
      </div>
      <div class="daily-plan-hero-actions">
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
          {{ activePlan ? '重新排期' : '生成 TODO 计划' }}
        </el-button>
      </div>
    </section>

    <el-empty v-if="!loadingProjects && !projects.length" description="暂无学习项目，请先在探索方向页构建项目。" />

    <section v-else class="todo-plan-shell">
      <aside class="todo-plan-sidebar panel-like">
        <section class="daily-plan-project">
          <span>当前项目</span>
          <strong>{{ selectedProject?.title || '未选择项目' }}</strong>
          <p>{{ selectedProject?.learning_goal || '选择项目后显示学习目标。' }}</p>
        </section>

        <section class="todo-plan-gauge" v-if="activePlan">
          <el-progress type="dashboard" :percentage="planProgress" :stroke-width="12" />
          <div>
            <strong>{{ completedCount }}/{{ actionableCount }}</strong>
            <span>已完成 TODO</span>
          </div>
        </section>

        <el-form label-position="top" class="daily-plan-form">
          <el-form-item label="开始日期">
            <el-date-picker v-model="form.start_date" type="date" value-format="YYYY-MM-DD" />
          </el-form-item>
          <el-form-item label="每日学习时长">
            <el-input-number v-model="form.daily_minutes" :min="10" :max="300" :step="10" />
          </el-form-item>
          <el-form-item label="学习日">
            <el-checkbox-group v-model="form.study_weekdays" class="weekday-grid">
              <el-checkbox-button v-for="day in weekdayOptions" :key="day.value" :label="day.value">
                {{ day.label }}
              </el-checkbox-button>
            </el-checkbox-group>
          </el-form-item>
          <el-checkbox v-model="form.study_weekends">周末也学习</el-checkbox>
        </el-form>

        <section v-if="activePlan" class="todo-plan-meta">
          <div><span>今日</span><strong>{{ todayItems.length }}</strong></div>
          <div><span>逾期</span><strong>{{ overdueItems.length }}</strong></div>
          <div><span>后续</span><strong>{{ upcomingItems.length }}</strong></div>
          <div><span>总时长</span><strong>{{ totalMinutes }} 分钟</strong></div>
        </section>

        <section v-if="activePlan && activeTask" class="todo-active-task">
          <span>当前任务</span>
          <strong>{{ activeTask.title }}</strong>
          <p>{{ activeTaskGateText(activeTask) }}</p>
          <el-button type="primary" :disabled="!activeTask.can_start" @click="handleStartLearning(activeTask)">
            {{ activeTask.can_start ? '进入课堂' : '等待解锁' }}
          </el-button>
        </section>
      </aside>

      <main class="todo-plan-board panel-like">
        <header class="todo-board-head">
          <div>
            <span>{{ activePlan?.generation_reason || '按学习清单顺序自动排期' }}</span>
            <h3>{{ activeFilterMeta.label }}</h3>
          </div>
          <el-tag v-if="activePlan" effect="plain">{{ activePlan.daily_minutes }} 分钟/天</el-tag>
        </header>

        <div class="todo-filter-bar" v-if="activePlan">
          <button
            v-for="filter in todoFilters"
            :key="filter.key"
            type="button"
            :class="{ active: activeFilter === filter.key }"
            @click="activeFilter = filter.key"
          >
            <span>{{ filter.label }}</span>
            <strong>{{ filter.count }}</strong>
          </button>
        </div>

        <div v-if="loadingPlans" class="daily-plan-loading">正在加载 TODO 计划...</div>
        <div v-else-if="!activePlan" class="daily-plan-empty-state todo-empty-state">
          <strong>当前项目还没有 TODO 计划</strong>
          <p>系统会按学习清单顺序、每日学习时长和学习日自动排期。课程不能在计划页直接删除，如需删课请到学习清单中调整。</p>
          <el-button type="primary" :loading="generating" :disabled="!selectedProjectId" @click="handleGeneratePlan">
            生成 TODO 计划
          </el-button>
        </div>

        <TransitionGroup v-else name="panel-swap" tag="section" class="todo-task-list">
          <article
            v-for="item in filteredItems"
            :key="item.id"
            class="todo-task-card"
            :class="[
              item.status,
              {
                overdue: item.is_overdue,
                today: item.is_today,
                done: isDone(item),
                removed: item.status === 'removed'
              }
            ]"
          >
            <div class="todo-status-mark" :class="{ done: isDone(item), overdue: item.is_overdue }">
              <span></span>
            </div>

            <div class="todo-task-main">
              <div class="todo-task-line">
                <el-tag :type="statusTagType(item.status)" effect="plain">{{ statusLabel(item.status) }}</el-tag>
                <span>{{ formatDayTitle(toDateInput(item.planned_date)) }}</span>
                <span>{{ item.estimated_minutes }} 分钟</span>
              </div>
              <h4>{{ item.title }}</h4>
              <p>{{ item.learning_focus }}</p>
              <div class="todo-task-gate" :class="{ locked: !item.can_start && !isDone(item), ready: item.can_start && !isDone(item) }">
                <strong>{{ taskGateLabel(item) }}</strong>
                <span>{{ taskGateDescription(item) }}</span>
              </div>
              <div class="tags">
                <el-tag v-for="resource in item.resource_types" :key="resource" effect="plain">{{ resource }}</el-tag>
              </div>
            </div>

            <div class="todo-task-actions">
              <el-date-picker
                v-model="moveDates[item.id]"
                type="date"
                value-format="YYYY-MM-DD"
                placeholder="调整日期"
                :disabled="item.status === 'removed'"
              />
              <el-button :loading="movingItemId === item.id" :disabled="item.status === 'removed'" @click="handleShiftItem(item, 'previous')">
                提前
              </el-button>
              <el-button :loading="movingItemId === item.id" :disabled="item.status === 'removed'" @click="handleShiftItem(item, 'next')">
                顺延
              </el-button>
              <el-button :loading="movingItemId === item.id" :disabled="item.status === 'removed' || !moveDates[item.id]" @click="handleMoveItem(item)">
                移动
              </el-button>
              <el-button type="primary" :disabled="!item.can_start || item.status === 'removed'" @click="handleStartLearning(item)">
                开始学习
              </el-button>
            </div>
          </article>
        </TransitionGroup>
      </main>

      <aside class="todo-plan-timeline panel-like" v-if="activePlan">
        <header class="daily-plan-days-head">
          <span>计划队列</span>
          <strong>{{ groupedDays.length }} 天</strong>
        </header>
        <div class="todo-day-list">
          <button
            v-for="day in groupedDays"
            :key="day.date"
            type="button"
            :class="{ active: activeDate === day.date, today: day.date === todayString }"
            @click="focusDay(day.date)"
          >
            <span>{{ formatDayTitle(day.date) }}</span>
            <strong>{{ day.items.length }} 项 / {{ day.minutes }} 分钟</strong>
            <small>{{ day.items.map((item) => item.title).join(' / ') }}</small>
          </button>
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
  shiftDailyPlanItem,
  type DailyPlanItemRead,
  type DailyPlanRead,
  type LearningProjectRead
} from '../services/apiClient'

type TodoFilter = 'today' | 'overdue' | 'upcoming' | 'done' | 'all'

const props = defineProps<{ projectId: number | null }>()
const router = useRouter()

const projects = ref<LearningProjectRead[]>([])
const plans = ref<DailyPlanRead[]>([])
const selectedProjectId = ref<number | null>(props.projectId)
const activePlanId = ref<number | null>(null)
const activeFilter = ref<TodoFilter>('today')
const activeDate = ref('')
const loadingProjects = ref(false)
const loadingPlans = ref(false)
const generating = ref(false)
const movingItemId = ref<number | null>(null)
const moveDates = reactive<Record<number, string>>({})
const form = reactive({
  start_date: toDateInput(new Date()),
  daily_minutes: 40,
  study_weekends: false,
  study_weekdays: [0, 1, 2, 3, 4]
})

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
  const ordered = sortTodoItems(actionableItems.value.filter((item) => !isDone(item)))
  return ordered.find((item) => item.can_start) || ordered[0] || null
})
const totalMinutes = computed(() => actionableItems.value.reduce((sum, item) => sum + item.estimated_minutes, 0))
const completedCount = computed(() => completedItems.value.length)
const actionableCount = computed(() => actionableItems.value.length)
const planProgress = computed(() => actionableCount.value ? Math.round((completedCount.value / actionableCount.value) * 100) : 0)

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

const filteredItems = computed(() => {
  const byDate = activeDate.value ? actionableItems.value.filter((item) => toDateInput(item.planned_date) === activeDate.value) : null
  if (byDate) return sortTodoItems(byDate)
  if (activeFilter.value === 'today') return sortTodoItems(todayItems.value)
  if (activeFilter.value === 'overdue') return sortTodoItems(overdueItems.value)
  if (activeFilter.value === 'upcoming') return sortTodoItems(upcomingItems.value)
  if (activeFilter.value === 'done') return sortTodoItems(completedItems.value)
  return sortTodoItems(actionableItems.value)
})

const todoFilters = computed(() => [
  { key: 'today' as TodoFilter, label: '今日待办', count: todayItems.value.length },
  { key: 'overdue' as TodoFilter, label: '逾期', count: overdueItems.value.length },
  { key: 'upcoming' as TodoFilter, label: '后续', count: upcomingItems.value.length },
  { key: 'done' as TodoFilter, label: '已完成', count: completedItems.value.length },
  { key: 'all' as TodoFilter, label: '全部', count: actionableItems.value.length }
])
const activeFilterMeta = computed(() => {
  if (activeDate.value) return { label: formatDayTitle(activeDate.value) }
  return todoFilters.value.find((filter) => filter.key === activeFilter.value) || todoFilters.value[0]
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

watch(activeFilter, () => {
  activeDate.value = ''
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

async function loadPlans(projectId: number) {
  loadingPlans.value = true
  try {
    const { data } = await listDailyPlans(projectId)
    plans.value = data
    const current = data.find((plan) => plan.status === 'active') || data[0] || null
    activePlanId.value = current?.id || null
    hydrateFormFromPlan(current)
    activeFilter.value = firstUsefulFilter(current)
    activeDate.value = ''
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
      study_weekdays: form.study_weekdays,
      title: selectedProject.value ? `${selectedProject.value.title} 每日 TODO 计划` : ''
    })
    plans.value = [data, ...plans.value.filter((plan) => plan.id !== data.id)]
    activePlanId.value = data.id
    hydrateMoveDates()
    activeFilter.value = firstUsefulFilter(data)
    activeDate.value = ''
    ElMessage.success('每日 TODO 计划已生成')
  } finally {
    generating.value = false
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
    ElMessage.success('TODO 日期已调整')
  } finally {
    movingItemId.value = null
  }
}

async function handleShiftItem(item: DailyPlanItemRead, direction: 'next' | 'previous') {
  movingItemId.value = item.id
  try {
    const { data } = await shiftDailyPlanItem(item.id, direction)
    replacePlan(data)
    hydrateMoveDates()
    ElMessage.success(direction === 'next' ? 'TODO 已顺延到下一个学习日' : 'TODO 已提前到上一个学习日')
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

function focusDay(date: string) {
  activeDate.value = date
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
  form.study_weekends = plan.study_weekends
  form.study_weekdays = plan.study_weekdays.length ? plan.study_weekdays : [0, 1, 2, 3, 4]
  hydrateMoveDates()
}

function hydrateMoveDates() {
  for (const item of allItems.value) {
    moveDates[item.id] = toDateInput(item.planned_date)
  }
}

function firstUsefulFilter(plan: DailyPlanRead | null): TodoFilter {
  if (!plan?.items.length) return 'today'
  const today = toDateInput(new Date())
  const active = plan.items.filter((item) => item.status !== 'removed' && !isDone(item))
  if (active.some((item) => toDateInput(item.planned_date) === today)) return 'today'
  if (active.some((item) => toDateInput(item.planned_date) < today)) return 'overdue'
  return 'upcoming'
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
    removed: '已从清单移除',
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
  if (item.is_overdue) return '需先处理前置任务'
  return '排队中'
}

function taskGateDescription(item: DailyPlanItemRead) {
  if (isDone(item)) return '该学习项已通过课堂、练习、实操或复盘要求。'
  if (item.status === 'removed') return '课程删除请在学习清单处理，计划页不直接删除课程。'
  if (item.can_start) return '进入课堂后需完成课件、例题、实操和复盘，系统会自动更新进度。'
  if (item.is_overdue) return 'OpenMAIC 式任务流会阻止跳过未完成前置任务，请先完成更早的学习项。'
  return '系统会按日期、顺序和学习清单进度自动解锁。'
}

function activeTaskGateText(item: DailyPlanItemRead) {
  if (item.can_start) return `计划 ${formatDayTitle(toDateInput(item.planned_date))}，预计 ${item.estimated_minutes} 分钟。`
  return taskGateDescription(item)
}
</script>
