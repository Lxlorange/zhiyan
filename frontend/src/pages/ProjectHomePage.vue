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
            <span>Next Step</span>
            <h4>下一步</h4>
          </div>
          <p>{{ activeProject.next_step || '打开学习清单，按目录继续学习。' }}</p>
        </section>

        <div class="project-card-actions">
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
