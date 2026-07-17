<template>
  <div class="page dashboard-module-page">
    <section class="workspace-hero">
      <div>
        <h2>{{ mode === 'agents' ? '多智能体任务中心' : '教师驾驶舱' }}</h2>
      </div>
      <el-button :loading="loading" @click="loadData">刷新</el-button>
    </section>

    <section v-if="loading" class="panel-like workspace-loading">正在加载数据...</section>

    <template v-else-if="mode === 'agents'">
      <section class="agent-pipeline panel-like">
        <article v-for="agent in agentCatalog" :key="agent.name">
          <span>{{ agent.phase }}</span>
          <strong>{{ agent.name }}</strong>
          <p>{{ agent.role }}</p>
        </article>
      </section>

      <section class="workspace-grid two">
        <article class="panel-like workspace-panel">
          <header><strong>最近任务轨迹</strong><span>{{ overview?.agent_tasks.length || 0 }} tasks</span></header>
          <div class="agent-trace-list rich">
            <div v-for="task in overview?.agent_tasks || []" :key="`${task.agent}-${task.input_summary}-${task.output_summary}`">
              <el-tag :type="statusType(task.status)" size="small">{{ task.status }}</el-tag>
              <strong>{{ task.agent }}</strong>
              <p>{{ task.output_summary }}</p>
              <small>{{ task.input_summary }}</small>
            </div>
          </div>
        </article>

        <article class="panel-like workspace-panel">
          <header><strong>流程覆盖</strong><span>Orchestration</span></header>
          <div class="agent-route-list">
            <span>方向学习</span>
            <strong>DirectionAgent → ProfileAgent → SyllabusAgent → PlannerAgent → SafetyAgent</strong>
            <span>AI 课堂</span>
            <strong>ClassroomAgent → VisualizationAgent → ExerciseAgent → MemoryAgent</strong>
            <span>科研工具</span>
            <strong>PaperAgent / WritingAgent / CitationAgent → SafetyAgent</strong>
          </div>
        </article>
      </section>
    </template>

    <template v-else>
      <section class="workspace-metrics">
        <article v-for="metric in teacher?.metrics || []" :key="metric.label" class="metric-card">
          <span>{{ metric.label }}</span>
          <strong>{{ metric.value }}</strong>
          <small>{{ metric.trend }}</small>
        </article>
      </section>

      <section class="workspace-grid two">
        <article class="panel-like workspace-panel">
          <header><strong>高频知识短板</strong><span>Weak Points</span></header>
          <div class="distribution-list">
            <div v-for="(value, key) in teacher?.weak_point_distribution || {}" :key="key">
              <span>{{ key }}</span>
              <el-progress :percentage="Math.min(100, value * 10)" :stroke-width="8" />
            </div>
          </div>
        </article>

        <article class="panel-like workspace-panel">
          <header><strong>资源使用统计</strong><span>Resources</span></header>
          <div class="distribution-list">
            <div v-for="(value, key) in teacher?.resource_type_distribution || {}" :key="key">
              <span>{{ key }}</span>
              <el-progress :percentage="Math.min(100, value * 10)" :stroke-width="8" />
            </div>
          </div>
        </article>

        <article class="panel-like workspace-panel">
          <header><strong>高风险学生</strong><span>Risk</span></header>
          <div class="workspace-list">
            <p v-for="student in teacher?.at_risk_students || []" :key="student.session_id">
              {{ student.title }} · Revision {{ student.profile_revision }} · {{ student.weak_points.join(' / ') }}
            </p>
          </div>
        </article>

        <article class="panel-like workspace-panel">
          <header><strong>教学建议</strong><span>Action</span></header>
          <div class="workspace-list">
            <p v-for="item in teacher?.teaching_suggestions || []" :key="item">{{ item }}</p>
          </div>
        </article>
      </section>
    </template>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import {
  getTeacherDashboard,
  getWorkspaceOverview,
  type TeacherDashboardResponse,
  type WorkspaceOverviewResponse
} from '../services/apiClient'

type Mode = 'agents' | 'teacher'

const props = defineProps<{ mode: Mode }>()
const loading = ref(false)
const overview = ref<WorkspaceOverviewResponse | null>(null)
const teacher = ref<TeacherDashboardResponse | null>(null)

const agentCatalog = [
  { phase: '方向', name: 'DirectionAgent', role: '识别科研方向、目标类型和澄清问题。' },
  { phase: '画像', name: 'ProfileAgent', role: '抽取画像条目、证据和置信度。' },
  { phase: '路径', name: 'SyllabusAgent', role: '生成个性化学习清单并绑定知识库来源。' },
  { phase: '计划', name: 'PlannerAgent', role: '根据时长和日程生成每日计划。' },
  { phase: '课堂', name: 'ClassroomAgent', role: '组织课件、例题、实操、图解和复盘。' },
  { phase: '演示', name: 'VisualizationAgent', role: '生成 Mermaid 图解和互动 HTML 演示。' },
  { phase: '评估', name: 'EvaluationAgent', role: '评估答题、实操和复盘证据。' },
  { phase: '记忆', name: 'MemoryAgent', role: '写回学习记录、画像版本和个人知识库。' },
  { phase: '安全', name: 'SafetyAgent', role: '检查来源、幻觉、引用和学术边界。' }
]

onMounted(loadData)
watch(() => props.mode, loadData)

async function loadData() {
  loading.value = true
  try {
    if (props.mode === 'agents') {
      const { data } = await getWorkspaceOverview()
      overview.value = data
    } else {
      const { data } = await getTeacherDashboard()
      teacher.value = data
    }
  } finally {
    loading.value = false
  }
}

function statusType(status: string): 'success' | 'danger' | 'warning' | 'info' {
  if (['completed', 'done'].includes(status)) return 'success'
  if (status === 'failed') return 'danger'
  if (status === 'skipped') return 'info'
  return 'warning'
}
</script>
