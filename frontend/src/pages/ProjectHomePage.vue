<template>
  <div class="page project-home-page">
    <section class="page-hero">
      <div>
        <h2>项目主页</h2>
      </div>
      <el-button type="primary" :loading="loading" @click="loadProjects">刷新项目</el-button>
    </section>

    <el-empty v-if="!loading && projects.length === 0" description="暂无项目，请先在探索方向页构建项目。" />

    <section v-else class="project-home-layout">
      <aside class="project-list-panel panel-like">
        <div class="project-list-head">
          <span>Learning Projects</span>
          <strong>{{ projects.length }} 个项目</strong>
        </div>
        <button
          v-for="project in projects"
          :key="project.id"
          class="project-list-item"
          :class="{ active: project.id === activeProjectId }"
          type="button"
          @click="handleSelectProject(project.id)"
        >
          <span>{{ project.subject || project.goal_type }}</span>
          <strong>{{ project.title }}</strong>
          <small>{{ project.current_stage }} / {{ project.progress }}%</small>
        </button>
      </aside>

      <article v-if="activeProject" class="project-detail-panel panel-like">
        <div class="project-detail-head">
          <div>
            <span>{{ activeProject.subject }} / {{ activeProject.goal_type }}</span>
            <h3>{{ activeProject.title }}</h3>
          </div>
          <div class="project-head-actions">
            <el-tag>{{ statusLabel(activeProject.status) }}</el-tag>
            <el-dropdown trigger="click" @command="handleProjectCommand">
              <el-button>管理项目</el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="pause" :disabled="activeProject.status === 'paused'">暂停项目</el-dropdown-item>
                  <el-dropdown-item command="resume" :disabled="activeProject.status !== 'paused'">恢复项目</el-dropdown-item>
                  <el-dropdown-item command="copy">复制项目</el-dropdown-item>
                  <el-dropdown-item command="archive" divided>归档项目</el-dropdown-item>
                  <el-dropdown-item command="delete" divided>删除项目</el-dropdown-item>
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
          <div class="project-next-actions">
            <el-button @click="router.push({ name: 'project-daily-plan', params: { projectId: activeProject.id } })">
              今日计划
            </el-button>
            <el-button type="primary" @click="emit('openSyllabus', activeProject.id)">
              继续学习
            </el-button>
          </div>
        </section>

        <div class="project-dashboard-grid">
          <div>
            <span>整体进度</span>
            <strong>{{ activeProject.progress }}%</strong>
            <el-progress :percentage="activeProject.progress" :stroke-width="10" />
          </div>
          <div>
            <span>预计周期</span>
            <strong>{{ activeProject.recommended_period }}</strong>
          </div>
          <div>
            <span>每日学习</span>
            <strong>{{ activeProject.daily_minutes }} 分钟</strong>
            <small>{{ studyDaysLabel(activeProject) }}</small>
          </div>
          <div>
            <span>当前阶段</span>
            <strong>{{ activeProject.current_stage }}</strong>
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

        <section class="project-section">
          <div class="section-title">
            <span>Next Step</span>
            <h4>下一步</h4>
          </div>
          <p>{{ activeProject.next_step || '打开学习清单，按目录继续学习。' }}</p>
        </section>

        <div class="project-card-actions">
          <el-button size="large" @click="router.push({ name: 'project-daily-plan', params: { projectId: activeProject.id } })">
            打开每日计划
          </el-button>
          <el-button type="primary" size="large" @click="emit('openSyllabus', activeProject.id)">
            打开学习清单
          </el-button>
        </div>
      </article>
    </section>
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
  resumeLearningProject,
  type LearningProjectRead
} from '../services/apiClient'

const props = defineProps<{
  selectedProjectId: number | null
}>()

const emit = defineEmits<{
  openSyllabus: [projectId: number]
}>()

const projects = ref<LearningProjectRead[]>([])
const loading = ref(false)
const router = useRouter()
const activeProjectId = ref<number | null>(props.selectedProjectId)
const activeProject = computed(() => projects.value.find((project) => project.id === activeProjectId.value) || null)
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
  (nextProjectId) => {
    if (nextProjectId) activeProjectId.value = nextProjectId
  }
)

async function loadProjects() {
  loading.value = true
  try {
    const { data } = await listLearningProjects()
    projects.value = data
    if (!activeProjectId.value && data.length) {
      activeProjectId.value = data[0].id
      await router.replace({ name: 'project-detail', params: { projectId: data[0].id } })
    }
  } finally {
    loading.value = false
  }
}

async function handleSelectProject(projectId: number) {
  activeProjectId.value = projectId
  await router.push({ name: 'project-detail', params: { projectId } })
}

async function handleProjectCommand(command: string | number | object) {
  if (!activeProject.value || typeof command !== 'string') return
  if (command === 'pause') await mutateProject(activeProject.value.id, () => pauseLearningProject(activeProject.value!.id), '项目已暂停')
  if (command === 'resume') await mutateProject(activeProject.value.id, () => resumeLearningProject(activeProject.value!.id), '项目已恢复')
  if (command === 'copy') await copyProject(activeProject.value.id)
  if (command === 'archive') await archiveProject(activeProject.value)
  if (command === 'delete') await deleteProject(activeProject.value)
}

async function mutateProject(projectId: number, action: () => Promise<{ data: LearningProjectRead }>, message: string) {
  const { data } = await action()
  projects.value = projects.value.map((project) => (project.id === projectId ? data : project))
  ElMessage.success(message)
}

async function copyProject(projectId: number) {
  const { data } = await copyLearningProject(projectId)
  projects.value = [data, ...projects.value]
  activeProjectId.value = data.id
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
  await ElMessageBox.confirm(`确认删除“${project.title}”？项目会从主页隐藏，已生成的学习记录会保留用于审计。`, '删除项目', {
    confirmButtonText: '删除',
    cancelButtonText: '取消',
    type: 'warning',
    confirmButtonClass: 'el-button--danger'
  })
  await deleteLearningProject(project.id)
  projects.value = projects.value.filter((item) => item.id !== project.id)
  const nextProject = projects.value[0] || null
  activeProjectId.value = nextProject?.id || null
  if (nextProject) await router.push({ name: 'project-detail', params: { projectId: nextProject.id } })
  else await router.push({ name: 'projects' })
  ElMessage.success('项目已删除')
}

function statusLabel(status: string) {
  const labels: Record<string, string> = {
    draft: '草稿',
    learning: '学习中',
    paused: '已暂停',
    archived: '已归档',
    syllabus_generating: '清单生成中',
    syllabus_ready: '清单已就绪',
    daily_plan_ready: '计划已就绪',
    resources_generating: '资源生成中',
    resources_ready: '资源已就绪',
    needs_replan: '待重规划'
  }
  return labels[status] || status
}

function studyDaysLabel(project: LearningProjectRead) {
  const labels = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
  const days = (project.study_weekdays?.length ? project.study_weekdays : [0, 1, 2, 3, 4])
    .filter((day) => day >= 0 && day <= 6)
    .sort((left, right) => left - right)
    .map((day) => labels[day])
  return days.length ? days.join(' / ') : '周一 / 周二 / 周三 / 周四 / 周五'
}
</script>
