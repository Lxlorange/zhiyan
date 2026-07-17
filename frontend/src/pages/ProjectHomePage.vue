<template>
  <div class="page project-home-page">
    <section v-if="isOverview" class="page-hero project-overview-hero">
      <div>
        <h2>Learning Projects</h2>
      </div>
      <div class="project-overview-actions">
        <el-button :loading="loading" @click="loadProjects">刷新</el-button>
        <el-button type="primary" @click="router.push({ name: 'directions' })">新建项目</el-button>
      </div>
    </section>

    <section v-else class="project-detail-nav">
      <el-button @click="router.push({ name: 'projects' })">返回项目总览</el-button>
    </section>

    <el-empty v-if="!loading && projects.length === 0" description="暂无项目，请先在探索方向页构建项目。" />

    <section v-else-if="isOverview" class="project-overview-page">
      <div class="project-filter-strip">
        <button
          v-for="tag in projectTags"
          :key="tag"
          class="project-filter-chip"
          :class="{ active: selectedTag === tag }"
          type="button"
          @click="selectedTag = selectedTag === tag ? '' : tag"
        >
          {{ tag }}
        </button>
      </div>

      <div v-if="selectedProjects.length" class="project-batch-bar">
        <span>已选择 {{ selectedProjects.length }} 个项目</span>
        <div>
          <el-button size="small" @click="batchAction('pause')">批量暂停</el-button>
          <el-button size="small" @click="batchAction('archive')">批量归档</el-button>
          <el-button size="small" type="danger" @click="batchAction('delete')">批量删除</el-button>
          <el-button size="small" type="primary" @click="batchAction('restore')">批量恢复</el-button>
        </div>
      </div>

      <el-collapse v-model="openGroups" class="project-status-collapse">
        <el-collapse-item
          v-for="group in groupedProjects"
          :key="group.key"
          :name="group.key"
          :disabled="group.projects.length === 0"
        >
          <template #title>
            <div class="project-group-title">
              <strong>{{ group.label }}</strong>
              <span>{{ group.projects.length }}</span>
            </div>
          </template>

          <div v-if="group.projects.length" class="project-card-grid">
            <article
              v-for="project in group.projects"
              :key="project.id"
              class="project-overview-card"
              :class="{ deleted: project.status === 'deleted' }"
            >
              <el-checkbox
                class="project-select-checkbox"
                :model-value="selectedIds.includes(project.id)"
                @click.stop="toggleSelected(project.id, !selectedIds.includes(project.id))"
              />
              <button class="project-card-main" type="button" @click="openProject(project)">
                <span class="project-card-tag">{{ projectTag(project) }}</span>
                <strong>{{ project.title }}</strong>
                <small>{{ project.current_stage }} / {{ project.progress }}%</small>
                <el-progress :percentage="project.progress" :stroke-width="8" :show-text="false" />
              </button>
              <div class="project-card-controls">
                <el-tag :type="statusType(project.status)" effect="light">{{ statusLabel(project.status) }}</el-tag>
                <el-dropdown trigger="click" @command="handleProjectCommandToken">
                  <el-button size="small">管理</el-button>
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item :command="`pause:${project.id}`" :disabled="!canPause(project)">暂停项目</el-dropdown-item>
                      <el-dropdown-item :command="`resume:${project.id}`" :disabled="!canResume(project)">继续项目</el-dropdown-item>
                      <el-dropdown-item :command="`restore:${project.id}`" :disabled="project.status !== 'deleted'">恢复删除</el-dropdown-item>
                      <el-dropdown-item :command="`copy:${project.id}`" :disabled="project.status === 'deleted'">复制项目</el-dropdown-item>
                      <el-dropdown-item :command="`archive:${project.id}`" divided :disabled="!canArchive(project)">归档项目</el-dropdown-item>
                      <el-dropdown-item :command="`delete:${project.id}`" divided :disabled="project.status === 'deleted'">删除项目</el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
              </div>
            </article>
          </div>
          <el-empty v-else description="暂无项目" />
        </el-collapse-item>
      </el-collapse>
    </section>

    <article v-else-if="activeProject" class="project-detail-panel panel-like">
      <div class="project-detail-head">
        <div>
          <span>{{ projectTag(activeProject) }}</span>
          <h3>{{ activeProject.title }}</h3>
        </div>
        <div class="project-head-actions">
          <el-tag :type="statusType(activeProject.status)">{{ statusLabel(activeProject.status) }}</el-tag>
          <el-button type="primary" @click="emit('openSyllabus', activeProject.id)">学习清单</el-button>
          <el-dropdown trigger="click" @command="handleProjectCommandToken">
            <el-button>管理项目</el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item :command="`pause:${activeProject.id}`" :disabled="!canPause(activeProject)">暂停项目</el-dropdown-item>
                <el-dropdown-item :command="`resume:${activeProject.id}`" :disabled="!canResume(activeProject)">继续项目</el-dropdown-item>
                <el-dropdown-item :command="`copy:${activeProject.id}`">复制项目</el-dropdown-item>
                <el-dropdown-item :command="`archive:${activeProject.id}`" divided :disabled="!canArchive(activeProject)">归档项目</el-dropdown-item>
                <el-dropdown-item :command="`delete:${activeProject.id}`" divided>删除项目</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </div>

      <p class="project-goal">{{ activeProject.learning_goal }}</p>

      <section class="project-next-learning">
        <div>
          <span>今日继续</span>
          <strong>{{ activeProject.next_step || '从学习清单继续推进下一项课堂' }}</strong>
          <p>{{ nextLearningHint }}</p>
        </div>
      </section>

      <div class="project-dashboard-grid">
        <div>
          <span>整体进度</span>
          <strong>{{ activeProject.progress }}%</strong>
          <el-progress :percentage="activeProject.progress" :stroke-width="10" />
        </div>
        <div class="project-config-card">
          <span>学习配置</span>
          <template v-if="editingSchedule">
            <div class="project-config-form">
              <el-input v-model="scheduleForm.recommended_period" placeholder="预计周期，例如 2周" />
              <el-input-number v-model="scheduleForm.daily_minutes" :min="10" :max="300" :step="10" />
              <el-checkbox-group
                v-model="scheduleForm.study_weekdays"
                class="project-weekday-grid"
                @change="handleScheduleWeekdaysChange"
              >
                <el-checkbox-button v-for="day in weekdayOptions" :key="day.value" :label="day.value">
                  {{ day.label }}
                </el-checkbox-button>
              </el-checkbox-group>
              <el-checkbox v-model="scheduleForm.study_weekends" @change="handleScheduleWeekendChange">周末也学习</el-checkbox>
            </div>
            <div class="project-config-actions">
              <el-button size="small" @click="cancelScheduleEdit">取消</el-button>
              <el-button size="small" type="primary" :loading="savingSchedule" @click="saveScheduleConfig">保存</el-button>
            </div>
          </template>
          <template v-else>
            <div class="project-config-summary">
              <strong>{{ activeProject.recommended_period }}</strong>
              <span>{{ activeProject.daily_minutes }} 分钟/天</span>
              <small>{{ studyDaysLabel(activeProject) }}</small>
            </div>
            <button class="project-config-edit" type="button" @click="startScheduleEdit(activeProject)">修改</button>
          </template>
        </div>
      </div>

      <section class="project-section">
        <div class="section-title">
          <span>Knowledge Scope</span>
          <h4>关联知识点</h4>
        </div>
        <div class="tags">
          <el-tag v-for="point in activeProject.related_knowledge_points.slice(0, 10)" :key="point" effect="plain">
            {{ point }}
          </el-tag>
        </div>
      </section>

      <section v-if="researchTrainingEnabled" class="project-section research-training-section">
        <div class="section-title">
          <span>Research Training</span>
          <h4>四级论文阅读清单</h4>
        </div>
        <p>{{ researchTraining.review_cycle || '按周期提交论文复盘总结与下一步计划。' }}</p>
        <div class="research-reading-spine">
          <article v-for="group in researchReadingGroups" :key="group.level">
            <header>
              <span>{{ group.label }}</span>
              <strong>{{ group.items.length }} 篇</strong>
            </header>
            <ol>
              <li v-for="paper in group.items" :key="`${paper.order}-${paper.title}`">
                <a v-if="paperLink(paper)" :href="paperLink(paper)" target="_blank" rel="noreferrer">
                  {{ paper.order }}. {{ paper.title }}
                </a>
                <strong v-else>{{ paper.order }}. {{ paper.title }}</strong>
                <small>{{ [paper.venue, paper.year].filter(Boolean).join(' · ') }}</small>
                <p>{{ paper.why_read || paper.summary }}</p>
              </li>
            </ol>
          </article>
        </div>
        <div class="research-rubric-row">
          <el-tag v-for="item in researchRubric" :key="item" effect="plain">{{ item }}</el-tag>
        </div>
      </section>

      <section class="project-section">
        <div class="section-title">
          <span>Personalization</span>
          <h4>个性化提醒</h4>
        </div>
        <div class="project-insight-grid">
          <div>
            <span>当前薄弱点</span>
            <p>{{ activeProject.current_weak_points.length ? activeProject.current_weak_points.join(' / ') : '课堂复盘后会自动更新。' }}</p>
          </div>
          <div>
            <span>产出清单</span>
            <p>{{ activeProject.output_checklist.length ? activeProject.output_checklist.slice(0, 4).join(' / ') : '学习清单生成后会补充项目产出。' }}</p>
          </div>
          <div>
            <span>推荐策略</span>
            <p>{{ activeProject.personalization_strategy.length ? activeProject.personalization_strategy.slice(0, 3).join(' / ') : '根据画像偏好生成讲解、图解、实操和练习。' }}</p>
          </div>
          <div>
            <span>资源积累</span>
            <p>已生成 {{ activeProject.generated_resource_count }} 个资源，完成 {{ activeProject.completed_item_count }} 个学习项。</p>
          </div>
        </div>
      </section>

    </article>

    <el-empty v-else-if="!loading" description="项目不存在或已删除">
      <el-button type="primary" @click="router.push({ name: 'projects' })">返回项目总览</el-button>
    </el-empty>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  archiveLearningProject,
  copyLearningProject,
  deleteLearningProject,
  listLearningProjects,
  pauseLearningProject,
  restoreLearningProject,
  resumeLearningProject,
  updateLearningProject,
  type LearningProjectRead
} from '../services/apiClient'

const props = defineProps<{
  selectedProjectId: number | null
}>()

const emit = defineEmits<{
  openSyllabus: [projectId: number]
}>()

type ProjectGroup = {
  key: string
  label: string
  projects: LearningProjectRead[]
}

const projects = ref<LearningProjectRead[]>([])
const loading = ref(false)
const savingSchedule = ref(false)
const router = useRouter()
const selectedTag = ref('')
const selectedIds = ref<number[]>([])
const openGroups = ref(['active'])
const editingSchedule = ref(false)
const scheduleForm = ref({
  recommended_period: '',
  daily_minutes: 40,
  study_weekends: false,
  study_weekdays: [0, 1, 2, 3, 4]
})
let syncingScheduleWeekendFields = false
const weekdayOptions = [
  { label: '周一', value: 0 },
  { label: '周二', value: 1 },
  { label: '周三', value: 2 },
  { label: '周四', value: 3 },
  { label: '周五', value: 4 },
  { label: '周六', value: 5 },
  { label: '周日', value: 6 }
]

const isOverview = computed(() => props.selectedProjectId === null)
const activeProject = computed(() => (
  projects.value.find((project) => project.id === props.selectedProjectId && project.status !== 'deleted') || null
))
const selectedProjects = computed(() => projects.value.filter((project) => selectedIds.value.includes(project.id)))
const projectTags = computed(() => Array.from(new Set(projects.value.map(projectTag).filter(Boolean))))
const visibleProjects = computed(() => (
  selectedTag.value ? projects.value.filter((project) => projectTag(project) === selectedTag.value) : projects.value
))
const groupedProjects = computed<ProjectGroup[]>(() => {
  const activeStatuses = new Set([
    'draft',
    'learning',
    'syllabus_generating',
    'syllabus_ready',
    'daily_plan_ready',
    'resources_generating',
    'resources_ready',
    'resources_failed',
    'needs_replan'
  ])
  return [
    {
      key: 'active',
      label: '进行中',
      projects: visibleProjects.value.filter((project) => activeStatuses.has(project.status))
    },
    {
      key: 'paused',
      label: '暂停',
      projects: visibleProjects.value.filter((project) => project.status === 'paused')
    },
    {
      key: 'archived',
      label: '归档',
      projects: visibleProjects.value.filter((project) => project.status === 'archived')
    },
    {
      key: 'deleted',
      label: '已删除',
      projects: visibleProjects.value.filter((project) => project.status === 'deleted')
    }
  ]
})
const researchTraining = computed<Record<string, any>>(() => activeProject.value?.research_training || {})
const researchTrainingEnabled = computed(() => Boolean(researchTraining.value.enabled))
const researchReadingGroups = computed(() => {
  const labels: Record<string, string> = {
    foundation: '基础论文/教程',
    classic: '领域经典论文',
    seminal: '开山论文',
    frontier: '科研前沿论文'
  }
  const readings = Array.isArray(researchTraining.value.reading_list) ? researchTraining.value.reading_list : []
  return ['foundation', 'classic', 'seminal', 'frontier']
    .map((level) => ({
      level,
      label: labels[level],
      items: readings
        .filter((item: Record<string, any>) => item.level === level)
        .sort((left: Record<string, any>, right: Record<string, any>) => Number(left.order || 0) - Number(right.order || 0))
    }))
    .filter((group) => group.items.length)
})
const researchRubric = computed(() => {
  const rubric = Array.isArray(researchTraining.value.review_rubric) ? researchTraining.value.review_rubric : []
  return rubric.length ? rubric : ['详实程度', '关联度', '工作量', '规划性', '批判性思考']
})
const nextLearningHint = computed(() => {
  const project = activeProject.value
  if (!project) return ''
  if (project.today_recommendations.length) return project.today_recommendations.slice(0, 2).join('；')
  if (project.current_weak_points.length) return `建议先补齐：${project.current_weak_points.slice(0, 3).join(' / ')}`
  return '系统会根据学习清单、每日计划和课堂完成情况推荐下一步。'
})

onMounted(loadProjects)

watch(
  () => props.selectedProjectId,
  async () => {
    selectedIds.value = []
    editingSchedule.value = false
    if (!projects.value.length) await loadProjects()
  }
)

async function loadProjects() {
  loading.value = true
  try {
    const { data } = await listLearningProjects({ includeDeleted: true })
    projects.value = data
    selectedIds.value = selectedIds.value.filter((id) => data.some((project) => project.id === id))
  } finally {
    loading.value = false
  }
}

async function openProject(project: LearningProjectRead) {
  if (project.status === 'deleted') return
  await router.push({ name: 'project-detail', params: { projectId: project.id } })
}

function toggleSelected(projectId: number, checked: boolean) {
  selectedIds.value = checked
    ? Array.from(new Set([...selectedIds.value, projectId]))
    : selectedIds.value.filter((id) => id !== projectId)
}

function startScheduleEdit(project: LearningProjectRead) {
  const weekdays = project.study_weekdays?.length ? project.study_weekdays : [0, 1, 2, 3, 4]
  scheduleForm.value = {
    recommended_period: project.recommended_period,
    daily_minutes: project.daily_minutes,
    study_weekends: weekdays.some((day) => Number(day) >= 5),
    study_weekdays: normalizeWeekdaySelection(weekdays)
  }
  editingSchedule.value = true
}

function cancelScheduleEdit() {
  editingSchedule.value = false
}

function handleScheduleWeekendChange(value: string | number | boolean) {
  const enabled = Boolean(value)
  syncingScheduleWeekendFields = true
  scheduleForm.value.study_weekends = enabled
  const weekdays = new Set(scheduleForm.value.study_weekdays.map((day) => Number(day)))
  if (enabled) {
    weekdays.add(5)
    weekdays.add(6)
  } else {
    weekdays.delete(5)
    weekdays.delete(6)
  }
  scheduleForm.value.study_weekdays = normalizeWeekdaySelection([...weekdays])
  syncingScheduleWeekendFields = false
}

function handleScheduleWeekdaysChange(value: Array<number | string>) {
  if (syncingScheduleWeekendFields) return
  const normalized = normalizeWeekdaySelection(value)
  scheduleForm.value.study_weekdays = normalized
  scheduleForm.value.study_weekends = normalized.some((day) => day >= 5)
}

async function saveScheduleConfig() {
  const project = activeProject.value
  if (!project) return
  savingSchedule.value = true
  try {
    const payload = {
      recommended_period: scheduleForm.value.recommended_period.trim(),
      daily_minutes: scheduleForm.value.daily_minutes,
      study_weekends: scheduleForm.value.study_weekdays.some((day) => Number(day) >= 5),
      study_weekdays: normalizeWeekdaySelection(scheduleForm.value.study_weekdays)
    }
    const { data } = await updateLearningProject(project.id, payload)
    projects.value = projects.value.map((item) => (item.id === project.id ? data : item))
    editingSchedule.value = false
    ElMessage.success('学习配置已同步到每日计划')
  } finally {
    savingSchedule.value = false
  }
}

async function handleProjectCommandToken(command: string | number | object) {
  if (typeof command !== 'string') return
  const [action, rawProjectId] = command.split(':')
  const projectId = Number(rawProjectId)
  const project = projects.value.find((item) => item.id === projectId)
  if (!project) return
  if (action === 'pause') await mutateProject(project.id, () => pauseLearningProject(project.id), '项目已暂停')
  if (action === 'resume') await mutateProject(project.id, () => resumeLearningProject(project.id), '项目已恢复')
  if (action === 'restore') await mutateProject(project.id, () => restoreLearningProject(project.id), '项目已恢复')
  if (action === 'copy') await copyProject(project.id)
  if (action === 'archive') await archiveProject(project)
  if (action === 'delete') await deleteProject(project)
}

async function batchAction(action: 'pause' | 'archive' | 'delete' | 'restore') {
  const targets = selectedProjects.value.filter((project) => {
    if (action === 'restore') return project.status === 'deleted'
    if (action === 'pause') return canPause(project)
    if (action === 'archive') return canArchive(project)
    return project.status !== 'deleted'
  })
  if (!targets.length) {
    ElMessage.warning('当前选择中没有可操作的项目')
    return
  }
  if (action === 'delete') {
    await ElMessageBox.confirm(`确认删除选中的 ${targets.length} 个项目？删除后可在“已删除”分组恢复。`, '批量删除', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
      confirmButtonClass: 'el-button--danger'
    })
  }
  if (action === 'archive') {
    await ElMessageBox.confirm(`确认归档选中的 ${targets.length} 个项目？`, '批量归档', {
      confirmButtonText: '归档',
      cancelButtonText: '取消',
      type: 'warning'
    })
  }

  for (const project of targets) {
    if (action === 'pause') await mutateProject(project.id, () => pauseLearningProject(project.id), '', false)
    if (action === 'archive') await mutateProject(project.id, () => archiveLearningProject(project.id), '', false)
    if (action === 'restore') await mutateProject(project.id, () => restoreLearningProject(project.id), '', false)
    if (action === 'delete') {
      await deleteLearningProject(project.id)
      updateProjectStatus(project.id, 'deleted', '项目已删除')
    }
  }
  selectedIds.value = []
  ElMessage.success('批量操作已完成')
}

async function mutateProject(
  projectId: number,
  action: () => Promise<{ data: LearningProjectRead }>,
  message: string,
  showMessage = true
) {
  const { data } = await action()
  projects.value = projects.value.map((project) => (project.id === projectId ? data : project))
  if (showMessage && message) ElMessage.success(message)
}

async function copyProject(projectId: number) {
  const { data } = await copyLearningProject(projectId)
  projects.value = [data, ...projects.value]
  await router.push({ name: 'project-detail', params: { projectId: data.id } })
  ElMessage.success('项目副本已创建')
}

async function archiveProject(project: LearningProjectRead) {
  await ElMessageBox.confirm(`确认归档“${project.title}”？归档后仍会保留历史数据。`, '归档项目', {
    confirmButtonText: '归档',
    cancelButtonText: '取消',
    type: 'warning'
  })
  await mutateProject(project.id, () => archiveLearningProject(project.id), '项目已归档')
}

async function deleteProject(project: LearningProjectRead) {
  await ElMessageBox.confirm(`确认删除“${project.title}”？删除后可在项目总览的“已删除”分组恢复。`, '删除项目', {
    confirmButtonText: '删除',
    cancelButtonText: '取消',
    type: 'warning',
    confirmButtonClass: 'el-button--danger'
  })
  await deleteLearningProject(project.id)
  updateProjectStatus(project.id, 'deleted', '项目已删除')
  if (props.selectedProjectId === project.id) await router.push({ name: 'projects' })
  ElMessage.success('项目已删除')
}

function updateProjectStatus(projectId: number, status: string, currentStage: string) {
  projects.value = projects.value.map((project) => (
    project.id === projectId
      ? { ...project, status, current_stage: currentStage }
      : project
  ))
}

function canPause(project: LearningProjectRead) {
  return !['paused', 'deleted', 'archived'].includes(project.status)
}

function canResume(project: LearningProjectRead) {
  return ['paused', 'archived'].includes(project.status)
}

function canArchive(project: LearningProjectRead) {
  return !['archived', 'deleted'].includes(project.status)
}

function projectTag(project: LearningProjectRead) {
  return project.subject || project.related_course || project.goal_type || '未分类'
}

function statusLabel(status: string) {
  const labels: Record<string, string> = {
    draft: '草稿',
    learning: '学习中',
    paused: '已暂停',
    archived: '已归档',
    deleted: '已删除',
    syllabus_generating: '清单生成中',
    syllabus_ready: '清单已就绪',
    daily_plan_ready: '计划已就绪',
    resources_generating: '资源生成中',
    resources_ready: '资源已就绪',
    resources_failed: '资源生成失败',
    needs_replan: '待重规划'
  }
  return labels[status] || status
}

function statusType(status: string): 'success' | 'warning' | 'info' | 'primary' | 'danger' {
  if (['learning', 'syllabus_ready', 'daily_plan_ready', 'resources_ready'].includes(status)) return 'success'
  if (['paused', 'needs_replan', 'resources_failed'].includes(status)) return 'warning'
  if (status === 'deleted') return 'danger'
  if (status === 'archived') return 'info'
  return 'primary'
}

function studyDaysLabel(project: LearningProjectRead) {
  const labels = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
  const days = (project.study_weekdays?.length ? project.study_weekdays : [0, 1, 2, 3, 4])
    .filter((day) => day >= 0 && day <= 6)
    .sort((left, right) => left - right)
    .map((day) => labels[day])
  return days.length ? days.join(' / ') : '周一 / 周二 / 周三 / 周四 / 周五'
}

function normalizeWeekdaySelection(values: Array<number | string>) {
  const normalized = new Set(
    values
      .map((value) => Number(value))
      .filter((value) => Number.isInteger(value) && value >= 0 && value <= 6)
  )
  if (!normalized.size) return [0, 1, 2, 3, 4]
  return [...normalized].sort((left, right) => left - right)
}

function paperLink(paper: Record<string, any>) {
  return paper.arxiv_url || paper.doi_url || paper.source_url || ''
}
</script>
