<template>
  <div class="page daily-plan-page">
    <section class="page-hero daily-plan-hero">
      <div>
        <p class="eyebrow">Daily Plan</p>
        <h2>{{ selectedProject?.title || '每日计划' }}</h2>
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
          {{ activePlan ? '重新排期' : '生成每日计划' }}
        </el-button>
      </div>
    </section>

    <el-empty v-if="!loadingProjects && !projects.length" description="暂无学习项目，请先在探索方向页构建项目。" />

    <section v-else class="daily-plan-layout">
      <aside class="daily-plan-settings panel-like">
        <div class="daily-plan-project">
          <span>当前项目</span>
          <strong>{{ selectedProject?.title || '未选择项目' }}</strong>
          <p>{{ selectedProject?.learning_goal || '选择项目后显示学习目标。' }}</p>
        </div>

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

        <div v-if="activePlan" class="daily-plan-stats">
          <div>
            <span>计划状态</span>
            <strong>{{ activePlan.status }}</strong>
          </div>
          <div>
            <span>学习项</span>
            <strong>{{ visibleItems.length }}</strong>
          </div>
          <div>
            <span>总时长</span>
            <strong>{{ totalMinutes }} 分钟</strong>
          </div>
        </div>
      </aside>

      <aside class="daily-plan-days panel-like">
        <div class="daily-plan-days-head">
          <span>日期</span>
          <strong>{{ groupedDays.length }} 天</strong>
        </div>
        <div v-if="loadingPlans" class="daily-plan-loading">正在加载计划...</div>
        <el-empty v-else-if="!activePlan" description="当前项目还没有每日计划。" />
        <div v-else class="daily-plan-day-list">
          <button
            v-for="day in groupedDays"
            :key="day.date"
            type="button"
            :class="{ active: selectedDate === day.date }"
            @click="selectedDate = day.date"
          >
            <span>{{ formatDayTitle(day.date) }}</span>
            <strong>{{ day.items.length }} 项 / {{ day.minutes }} 分钟</strong>
          </button>
        </div>
      </aside>

      <main class="daily-plan-detail panel-like">
        <header class="daily-plan-detail-head">
          <div>
            <span>当天任务</span>
            <h3>{{ selectedDate ? formatDayTitle(selectedDate) : '未选择日期' }}</h3>
          </div>
          <el-tag v-if="selectedDay">{{ selectedDayMinutes }} 分钟</el-tag>
        </header>

        <el-empty v-if="!activePlan" description="生成每日计划后，这里会展示按日期排好的学习项。" />
        <el-empty v-else-if="!selectedDay" description="请选择一个日期。" />

        <TransitionGroup v-else name="panel-swap" tag="div" class="daily-task-list">
          <article
            v-for="item in selectedDayItems"
            :key="item.id"
            class="daily-task-card"
            :class="{ removed: item.status === 'removed' }"
          >
            <div class="daily-task-main">
              <span>{{ statusLabel(item.status) }} / {{ item.estimated_minutes }} 分钟</span>
              <h4>{{ item.title }}</h4>
              <p>{{ item.learning_focus }}</p>
              <div class="tags">
                <el-tag v-for="resource in item.resource_types" :key="resource" effect="plain">{{ resource }}</el-tag>
              </div>
            </div>

            <div class="daily-task-actions">
              <el-date-picker
                v-model="moveDates[item.id]"
                type="date"
                value-format="YYYY-MM-DD"
                placeholder="调整日期"
                :disabled="item.status === 'removed'"
              />
              <el-button
                :loading="movingItemId === item.id"
                :disabled="item.status === 'removed' || !moveDates[item.id]"
                @click="handleMoveItem(item)"
              >
                移动
              </el-button>
              <el-button
                type="primary"
                :disabled="item.status === 'removed' || !item.syllabus_item_id"
                @click="handleStartLearning(item)"
              >
                开始学习
              </el-button>
            </div>
          </article>
        </TransitionGroup>
      </main>
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
  type DailyPlanItemRead,
  type DailyPlanRead,
  type LearningProjectRead
} from '../services/apiClient'

const props = defineProps<{ projectId: number | null }>()
const router = useRouter()

const projects = ref<LearningProjectRead[]>([])
const plans = ref<DailyPlanRead[]>([])
const selectedProjectId = ref<number | null>(props.projectId)
const activePlanId = ref<number | null>(null)
const selectedDate = ref('')
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

const selectedProject = computed(() => projects.value.find((project) => project.id === selectedProjectId.value) || null)
const activePlan = computed(() => plans.value.find((plan) => plan.id === activePlanId.value) || null)
const visibleItems = computed(() => activePlan.value?.items || [])
const totalMinutes = computed(() => visibleItems.value.reduce((sum, item) => sum + item.estimated_minutes, 0))
const groupedDays = computed(() => {
  const groups = new Map<string, DailyPlanItemRead[]>()
  for (const item of visibleItems.value) {
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
const selectedDay = computed(() => groupedDays.value.find((day) => day.date === selectedDate.value) || null)
const selectedDayItems = computed(() => selectedDay.value?.items || [])
const selectedDayMinutes = computed(() => selectedDay.value?.minutes || 0)

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

async function loadPlans(projectId: number) {
  loadingPlans.value = true
  try {
    const { data } = await listDailyPlans(projectId)
    plans.value = data
    const current = data.find((plan) => plan.status === 'active') || data[0] || null
    activePlanId.value = current?.id || null
    hydrateFormFromPlan(current)
    selectedDate.value = firstUsefulDate(current)
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
      title: selectedProject.value ? `${selectedProject.value.title} 每日学习计划` : ''
    })
    plans.value = [data, ...plans.value.filter((plan) => plan.id !== data.id)]
    activePlanId.value = data.id
    selectedDate.value = firstUsefulDate(data)
    hydrateMoveDates()
    ElMessage.success('每日计划已生成')
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
    selectedDate.value = target
    hydrateMoveDates()
    ElMessage.success('计划日期已调整')
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

function replacePlan(plan: DailyPlanRead) {
  plans.value = plans.value.map((item) => (item.id === plan.id ? plan : item))
  if (!plans.value.find((item) => item.id === plan.id)) plans.value.unshift(plan)
  activePlanId.value = plan.id
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
  for (const item of visibleItems.value) {
    moveDates[item.id] = toDateInput(item.planned_date)
  }
}

function firstUsefulDate(plan: DailyPlanRead | null) {
  if (!plan?.items.length) return ''
  const today = toDateInput(new Date())
  const dates = Array.from(new Set(plan.items.map((item) => toDateInput(item.planned_date)))).sort()
  return dates.find((date) => date >= today) || dates[0] || ''
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
    removed: '已从清单移除'
  }
  return labels[status] || status
}
</script>
