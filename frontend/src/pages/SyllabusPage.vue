<template>
  <div class="page syllabus-page">
    <section class="page-hero syllabus-hero">
      <div>
        <h2>{{ selectedProject?.title || '项目学习清单' }}</h2>
      </div>
      <div class="syllabus-hero-actions">
        <el-select
          v-model="selectedProjectId"
          class="project-select"
          placeholder="选择学习项目"
          :loading="loadingProjects"
          @change="handleProjectChange"
        >
          <el-option v-for="project in projects" :key="project.id" :label="project.title" :value="project.id" />
        </el-select>
        <el-tag v-if="generationState !== 'idle'" :type="generationState === 'failed' ? 'danger' : 'warning'">
          {{ generationLabel }}
        </el-tag>
      </div>
    </section>

    <el-empty v-if="!selectedProjectId && !loadingProjects" description="请先从项目主页选择一个项目进入学习清单。" />

    <section v-else class="syllabus-layout">
      <aside class="syllabus-overview panel-like">
        <div class="syllabus-project-card">
          <span>当前项目</span>
          <strong>{{ selectedProject?.title || '未选择项目' }}</strong>
          <p>{{ selectedProject?.learning_goal || '从项目主页进入后，会在这里显示对应项目的学习目标。' }}</p>
        </div>

        <div class="syllabus-progress">
          <span>学习进度</span>
          <strong>{{ completedCount }}/{{ activeItems.length }}</strong>
          <el-progress :percentage="progressPercent" :stroke-width="10" />
        </div>

        <div class="syllabus-meta-list">
          <div>
            <span>当前版本</span>
            <strong>{{ syllabus ? `v${syllabus.version_no}` : '未生成' }}</strong>
          </div>
          <div>
            <span>知识库</span>
            <strong>{{ syllabus?.knowledge_base_version || selectedProject?.related_course || '-' }}</strong>
          </div>
          <div>
            <span>预计学习</span>
            <strong>{{ totalMinutes }} 分钟</strong>
          </div>
        </div>
      </aside>

      <main class="syllabus-content">
        <section v-if="loadingSyllabus" class="panel-like syllabus-loading">正在加载学习清单...</section>

        <section v-else-if="!syllabus" class="panel-like syllabus-empty">
          <h3>{{ generationState === 'failed' ? '学习清单生成失败' : '学习清单正在准备' }}</h3>
          <p>{{ generationMessage || '系统会在后台基于项目目标、知识库资料和用户画像自动生成阶段化目录。' }}</p>
          <div v-if="generationState !== 'failed'" class="generation-steps">
            <div v-for="step in generationSteps" :key="step.name" :class="{ active: step.active }">
              <span>{{ step.name }}</span>
              <strong>{{ step.text }}</strong>
            </div>
          </div>
          <div v-else class="syllabus-empty-actions">
            <el-button type="primary" @click="selectedProjectId && ensureAndLoadSyllabus(selectedProjectId)">重新生成</el-button>
            <el-button @click="router.push({ name: 'projects' })">返回项目主页</el-button>
          </div>
        </section>

        <template v-else>
          <section class="panel-like syllabus-summary compact-context">
            <div>
              <span>SyllabusAgent</span>
              <h3>清单生成说明</h3>
            </div>
            <p>{{ syllabus.generation_reason }}</p>
          </section>

          <section class="syllabus-directory panel-like syllabus-directory-modern">
            <div class="directory-head">
              <div>
                <span>Course Outline</span>
                <h3>目录总览</h3>
              </div>
              <el-tag type="success">{{ progressPercent }}% 已完成</el-tag>
            </div>

            <el-collapse v-model="expandedStages" class="syllabus-stage-collapse">
              <el-collapse-item
                v-for="stage in groupedStages"
                :key="stage.stage"
                :name="stage.stage"
              >
                <template #title>
                  <div class="syllabus-stage-title">
                    <strong>阶段 {{ stage.index + 1 }} · {{ stage.stage }}</strong>
                    <span>{{ stage.items.length }} 项</span>
                  </div>
                </template>

                <div class="syllabus-outline-list">
                  <article
                    v-for="item in stage.items"
                    :key="item.id"
                    class="syllabus-outline-item"
                    :class="{ active: selectedItem?.id === item.id }"
                  >
                    <button type="button" class="syllabus-outline-main" @click="selectItem(item)">
                      <span>{{ item.item_type }} / {{ item.difficulty }} / {{ item.estimated_minutes }} 分钟</span>
                      <strong>{{ item.title }}</strong>
                      <small>{{ item.objective }}</small>
                    </button>
                    <div class="syllabus-outline-actions">
                      <el-tag :type="statusType(item.status)" effect="plain">{{ statusLabel(item.status) }}</el-tag>
                      <el-button type="primary" size="small" @click="handleStartLearning(item)">
                        {{ ['completed', 'mastered'].includes(item.status) ? '继续学习' : '开始学习' }}
                      </el-button>
                      <el-button
                        size="small"
                        :loading="statusUpdatingId === item.id"
                        :disabled="item.status === 'skipped'"
                        @click="handleStatus(item.id, 'skipped')"
                      >
                        暂时跳过
                      </el-button>
                      <el-button
                        type="danger"
                        plain
                        size="small"
                        :loading="statusUpdatingId === item.id"
                        :disabled="item.is_locked"
                        @click="handleDeleteItem(item)"
                      >
                        删除课程
                      </el-button>
                    </div>
                  </article>
                </div>
              </el-collapse-item>
            </el-collapse>
          </section>

          <section v-if="selectedItem" class="syllabus-selected-panel panel-like">
            <div class="syllabus-selected-head">
              <div>
                <span>{{ selectedStage ? `阶段 ${selectedStage.index + 1} · ${selectedStage.stage}` : '当前课程' }}</span>
                <h3>{{ selectedItem.title }}</h3>
              </div>
              <el-tag :type="statusType(selectedItem.status)">{{ statusLabel(selectedItem.status) }}</el-tag>
            </div>

            <p class="syllabus-selected-objective">{{ selectedItem.objective }}</p>

            <div class="syllabus-info-grid">
              <div>
                <span>推荐原因</span>
                <p>{{ selectedItem.recommendation_reason }}</p>
              </div>
              <div>
                <span>完成标准</span>
                <p>{{ selectedItem.completion_criteria }}</p>
              </div>
              <div>
                <span>评估方式</span>
                <p>{{ selectedItem.assessment_method }}</p>
              </div>
              <div>
                <span>预计时长</span>
                <p>{{ selectedItem.estimated_minutes }} 分钟</p>
              </div>
            </div>

            <div class="syllabus-resource-block">
              <span>课堂资源</span>
              <div class="syllabus-link-grid">
                <button
                  v-for="resource in resourceLinks(selectedItem)"
                  :key="`${selectedItem.id}-${resource}`"
                  type="button"
                  @click="handleStartLearning(selectedItem)"
                >
                  {{ resource }}
                </button>
              </div>
            </div>

            <div class="syllabus-tags">
              <el-tag v-for="point in selectedItem.knowledge_points" :key="point" effect="plain">{{ point }}</el-tag>
            </div>

            <div v-if="selectedItem.related_documents.length" class="syllabus-doc-links">
              <span>资料来源</span>
              <template v-for="doc in selectedItem.related_documents" :key="doc">
                <a v-if="isExternalLink(doc)" :href="doc" target="_blank" rel="noreferrer">{{ doc }}</a>
                <small v-else>{{ doc }}</small>
              </template>
            </div>

            <div class="syllabus-status-actions">
              <el-button type="primary" @click="handleStartLearning(selectedItem)">
                {{ ['completed', 'mastered'].includes(selectedItem.status) ? '继续学习' : '开始学习' }}
              </el-button>
              <el-button
                :loading="statusUpdatingId === selectedItem.id"
                :disabled="selectedItem.status === 'skipped'"
                @click="handleStatus(selectedItem.id, 'skipped')"
              >
                暂时跳过
              </el-button>
              <el-button
                type="danger"
                plain
                :loading="statusUpdatingId === selectedItem.id"
                :disabled="selectedItem.is_locked"
                @click="handleDeleteItem(selectedItem)"
              >
                删除课程
              </el-button>
            </div>
          </section>
        </template>
      </main>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  deleteSyllabusItem,
  ensureSyllabus,
  getCurrentSyllabus,
  listLearningProjects,
  updateSyllabusItemStatus,
  type LearningProjectRead,
  type SyllabusItemRead,
  type SyllabusVersionRead
} from '../services/apiClient'

const props = defineProps<{
  projectId: number | null
}>()

const projects = ref<LearningProjectRead[]>([])
const selectedProjectId = ref<number | null>(props.projectId)
const syllabus = ref<SyllabusVersionRead | null>(null)
const router = useRouter()
const route = useRoute()
const loadingProjects = ref(false)
const loadingSyllabus = ref(false)
const generationState = ref<'idle' | 'started' | 'generating' | 'ready' | 'failed'>('idle')
const generationMessage = ref('')
const statusUpdatingId = ref<number | null>(null)
const selectedItemId = ref<number | null>(normalizeItemId(route.query.itemId))
const expandedStages = ref<string[]>([])
const pollTimer = ref<number | null>(null)

const selectedProject = computed(() => projects.value.find((project) => project.id === selectedProjectId.value) || null)
const activeItems = computed(() =>
  (syllabus.value?.items || []).filter((item) => !['deleted', 'merged', 'split', 'skipped'].includes(item.status))
)
const completedCount = computed(
  () => activeItems.value.filter((item) => ['completed', 'mastered'].includes(item.status)).length
)
const totalMinutes = computed(() => activeItems.value.reduce((sum, item) => sum + item.estimated_minutes, 0))
const progressPercent = computed(() => {
  if (!activeItems.value.length) return 0
  return Math.round((completedCount.value / activeItems.value.length) * 100)
})
const generationLabel = computed(() => {
  if (generationState.value === 'failed') return '生成失败'
  if (generationState.value === 'ready') return '已生成'
  return '后台生成中'
})
const generationSteps = computed(() => [
  { name: 'SyllabusAgent', text: '拆解阶段、知识点和学习项', active: ['started', 'generating'].includes(generationState.value) },
  { name: 'KnowledgeBaseAgent', text: '绑定课程知识库和资料来源', active: generationState.value === 'generating' },
  { name: 'PlannerAgent', text: '计算预计时长和推荐顺序', active: generationState.value === 'generating' },
  { name: 'SafetyAgent', text: '检查来源、边界和生成质量', active: generationState.value === 'generating' }
])
const groupedStages = computed(() => {
  const groups = new Map<string, SyllabusItemRead[]>()
  for (const item of activeItems.value) {
    const stage = item.stage || '未分组'
    groups.set(stage, [...(groups.get(stage) || []), item])
  }
  return Array.from(groups.entries()).map(([stage, items], index) => ({
    stage,
    items: items.sort((a, b) => a.user_order - b.user_order),
    index
  }))
})

const selectedItem = computed(() => {
  const selected = activeItems.value.find((item) => item.id === selectedItemId.value)
  return selected || activeItems.value[0] || null
})
const selectedStage = computed(() => groupedStages.value.find((stage) => stage.items.some((item) => item.id === selectedItem.value?.id)) || null)

onMounted(loadProjects)
onBeforeUnmount(clearPollTimer)

watch(
  () => props.projectId,
  (nextProjectId) => {
    selectedProjectId.value = nextProjectId
    if (nextProjectId) ensureAndLoadSyllabus(nextProjectId)
  }
)

watch(
  () => route.query.itemId,
  (itemId) => {
    selectedItemId.value = normalizeItemId(itemId)
    expandSelectedStage()
  }
)

watch(groupedStages, () => {
  if (!expandedStages.value.length) expandedStages.value = groupedStages.value.map((stage) => stage.stage)
  if (!selectedItemId.value && activeItems.value.length) selectedItemId.value = activeItems.value[0].id
  expandSelectedStage()
})

async function loadProjects() {
  loadingProjects.value = true
  try {
    const { data } = await listLearningProjects()
    projects.value = data
    if (!selectedProjectId.value && data.length) selectedProjectId.value = data[0].id
    if (selectedProjectId.value) await ensureAndLoadSyllabus(selectedProjectId.value)
  } finally {
    loadingProjects.value = false
  }
}

async function handleProjectChange(projectId: number | string) {
  selectedProjectId.value = Number(projectId)
  await router.push({ name: 'project-syllabus', params: { projectId: Number(projectId) } })
  await ensureAndLoadSyllabus(Number(projectId))
}

async function loadSyllabus(projectId: number) {
  loadingSyllabus.value = true
  try {
    const { data } = await getCurrentSyllabus(projectId)
    syllabus.value = data
    generationState.value = 'ready'
    generationMessage.value = '学习清单已生成'
    syncSelectionAfterSyllabusLoad()
  } finally {
    loadingSyllabus.value = false
  }
}

async function ensureAndLoadSyllabus(projectId: number) {
  clearPollTimer()
  loadingSyllabus.value = true
  try {
    const { data } = await ensureSyllabus(projectId, '为当前学习项目生成目录总览式学习清单')
    generationState.value = data.state
    generationMessage.value = data.message
    if (data.syllabus) {
      syllabus.value = data.syllabus
      generationState.value = 'ready'
      syncSelectionAfterSyllabusLoad()
      return
    }
    syllabus.value = null
    if (data.state === 'failed') {
      ElMessage.error(data.message)
      return
    }
    startPolling(projectId)
  } finally {
    loadingSyllabus.value = false
  }
}

function startPolling(projectId: number) {
  pollTimer.value = window.setInterval(async () => {
    try {
      const { data } = await ensureSyllabus(projectId, '为当前学习项目生成目录总览式学习清单')
      generationState.value = data.state
      generationMessage.value = data.message
      if (data.syllabus) {
        syllabus.value = data.syllabus
        generationState.value = 'ready'
        syncSelectionAfterSyllabusLoad()
        clearPollTimer()
      }
      if (data.state === 'failed') {
        clearPollTimer()
        ElMessage.error(data.message)
      }
    } catch {
      clearPollTimer()
    }
  }, 5000)
}

function clearPollTimer() {
  if (pollTimer.value) {
    window.clearInterval(pollTimer.value)
    pollTimer.value = null
  }
}


function normalizeItemId(value: unknown): number | null {
  const raw = Array.isArray(value) ? value[0] : value
  const id = Number(raw)
  return Number.isFinite(id) && id > 0 ? id : null
}

function syncSelectionAfterSyllabusLoad() {
  if (!activeItems.value.length) {
    selectedItemId.value = null
    expandedStages.value = []
    return
  }
  if (!selectedItem.value) selectedItemId.value = activeItems.value[0].id
  if (!expandedStages.value.length) expandedStages.value = groupedStages.value.map((stage) => stage.stage)
  expandSelectedStage()
}

function expandSelectedStage() {
  const stage = selectedStage.value?.stage
  if (stage && !expandedStages.value.includes(stage)) expandedStages.value = [...expandedStages.value, stage]
}

async function selectItem(item: SyllabusItemRead) {
  selectedItemId.value = item.id
  expandSelectedStage()
  await router.replace({
    name: 'project-syllabus',
    params: { projectId: item.project_id },
    query: { itemId: String(item.id) }
  })
}

async function handleStartLearning(item: SyllabusItemRead) {
  await router.push({
    name: 'project-classroom',
    params: { projectId: item.project_id, itemId: item.id }
  })
}

async function handleStatus(itemId: number, status: string) {
  statusUpdatingId.value = itemId
  try {
    const { data } = await updateSyllabusItemStatus(itemId, status, '用户在学习清单页面更新学习状态')
    syllabus.value = data
    ElMessage.success('学习状态已更新')
  } finally {
    statusUpdatingId.value = null
  }
}

async function handleDeleteItem(item: SyllabusItemRead) {
  try {
    await ElMessageBox.confirm(`确认从学习清单删除“${item.title}”？每日计划中对应任务会标记为已移除。`, '删除课程', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning'
    })
  } catch {
    return
  }
  statusUpdatingId.value = item.id
  try {
    await deleteSyllabusItem(item.id)
    if (selectedProjectId.value) await loadSyllabus(selectedProjectId.value)
    ElMessage.success('课程已从学习清单删除')
  } finally {
    statusUpdatingId.value = null
  }
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

function resourceLinks(item: SyllabusItemRead) {
  const resources = [...item.recommended_resource_types, ...item.classroom_types]
  return Array.from(new Set(resources.length ? resources : ['讲解文档', '例题互动', '可视化演示', '语音讲解', '复现 Demo', '练习评估']))
}

function isExternalLink(doc: string) {
  return /^https?:\/\//i.test(doc)
}
</script>
