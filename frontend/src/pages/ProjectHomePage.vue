<template>
  <div class="page project-home-page">
    <section class="page-hero">
      <div>
        <p class="eyebrow">Projects</p>
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
          <el-tag>{{ activeProject.status }}</el-tag>
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
import { listLearningProjects, type LearningProjectRead } from '../services/apiClient'

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
</script>
