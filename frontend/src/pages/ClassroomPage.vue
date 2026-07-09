<template>
  <div class="page classroom-page">
    <section class="page-hero classroom-hero">
      <div>
        <p class="eyebrow">AI Classroom</p>
        <h2>{{ currentItem?.title || '课堂学习' }}</h2>
        <p>{{ currentItem?.objective || '从学习清单进入课堂后，系统会围绕当前学习项组织学习板块并记录学习行为。' }}</p>
      </div>
      <div class="classroom-hero-actions">
        <el-button @click="goBackToSyllabus">返回学习清单</el-button>
        <el-tag v-if="currentItem" :type="statusType(currentItem.status)">{{ statusLabel(currentItem.status) }}</el-tag>
      </div>
    </section>

    <el-empty v-if="!projectId || !itemId" description="缺少课堂参数，请从项目学习清单进入课堂。" />

    <section v-else-if="loading" class="panel-like classroom-loading">正在加载课堂...</section>

    <el-empty v-else-if="!currentItem" description="没有找到当前学习项，请返回学习清单重新进入。" />

    <section v-else class="classroom-layout">
      <aside class="classroom-outline panel-like">
        <div class="classroom-outline-head">
          <span>当前学习项</span>
          <strong>{{ currentItem.title }}</strong>
          <p>{{ currentItem.stage }} / {{ currentItem.item_type }} / {{ currentItem.difficulty }}</p>
        </div>

        <div class="classroom-meter">
          <span>课堂浏览进度</span>
          <strong>{{ viewedSections.size }}/{{ learningSections.length }}</strong>
          <el-progress :percentage="classroomProgress" :stroke-width="10" />
        </div>

        <nav class="classroom-section-nav" aria-label="课堂板块">
          <button
            v-for="section in learningSections"
            :key="section.key"
            type="button"
            :class="{ active: activeSectionKey === section.key, viewed: viewedSections.has(section.key) }"
            @click="openSection(section.key)"
          >
            <span>{{ section.title }}</span>
            <small>{{ section.kind }}</small>
          </button>
        </nav>
      </aside>

      <main class="classroom-main panel-like">
        <header class="classroom-main-head">
          <div>
            <span>{{ activeSection.kind }}</span>
            <h3>{{ activeSection.title }}</h3>
          </div>
          <el-tag type="success" effect="plain" v-if="viewedSections.has(activeSection.key)">已浏览</el-tag>
        </header>

        <article class="classroom-content-card">
          <p>{{ activeSection.summary }}</p>

          <div v-if="activeSection.points.length" class="classroom-point-list">
            <div v-for="point in activeSection.points" :key="point">
              <span>{{ point }}</span>
            </div>
          </div>

          <div v-if="activeSection.resources.length" class="classroom-resource-grid">
            <a
              v-for="resource in activeSection.resources"
              :key="resource.label"
              :href="resource.href"
              target="_blank"
              rel="noreferrer"
            >
              <strong>{{ resource.label }}</strong>
              <small>{{ resource.type }}</small>
            </a>
          </div>
        </article>

        <section class="classroom-prompts">
          <div v-for="prompt in guidancePrompts" :key="prompt">
            {{ prompt }}
          </div>
        </section>
      </main>

      <aside class="classroom-inspector panel-like">
        <div class="inspector-block">
          <span>自动进度</span>
          <strong>{{ projectProgressPercent }}%</strong>
          <p>完成课堂关键板块后，系统会自动写回学习项状态并刷新项目进度。</p>
        </div>

        <div class="inspector-block">
          <span>完成标准</span>
          <p>{{ currentItem.completion_criteria }}</p>
        </div>

        <div class="inspector-block">
          <span>评估方式</span>
          <p>{{ currentItem.assessment_method }}</p>
        </div>

        <div class="inspector-block">
          <span>知识点</span>
          <div class="classroom-tags">
            <el-tag v-for="point in currentItem.knowledge_points" :key="point" effect="plain">{{ point }}</el-tag>
          </div>
        </div>
      </aside>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  getCurrentSyllabus,
  updateSyllabusItemStatus,
  type SyllabusItemRead,
  type SyllabusVersionRead
} from '../services/apiClient'

type ClassroomSection = {
  key: string
  title: string
  kind: string
  summary: string
  points: string[]
  resources: Array<{ label: string; type: string; href: string }>
}

const props = defineProps<{
  projectId: number | null
  itemId: number | null
}>()

const router = useRouter()
const loading = ref(false)
const syllabus = ref<SyllabusVersionRead | null>(null)
const activeSectionKey = ref('summary')
const viewedSections = ref<Set<string>>(new Set())
const statusUpdating = ref(false)

const emptySection: ClassroomSection = {
  key: 'empty',
  title: 'Classroom Content',
  kind: 'Learning',
  summary: '',
  points: [],
  resources: []
}

const currentItem = computed(() => syllabus.value?.items.find((item) => item.id === props.itemId) || null)
const activeItems = computed(() =>
  (syllabus.value?.items || []).filter((item) => !['deleted', 'merged', 'split', 'skipped'].includes(item.status))
)
const completedCount = computed(
  () => activeItems.value.filter((item) => ['completed', 'mastered'].includes(item.status)).length
)
const projectProgressPercent = computed(() => {
  if (!activeItems.value.length) return 0
  return Math.round((completedCount.value / activeItems.value.length) * 100)
})
const learningSections = computed<ClassroomSection[]>(() => buildSections(currentItem.value))
const activeSection = computed<ClassroomSection>(() => {
  return learningSections.value.find((section) => section.key === activeSectionKey.value) || emptySection
})
const classroomProgress = computed(() => {
  if (!learningSections.value.length) return 0
  return Math.round((viewedSections.value.size / learningSections.value.length) * 100)
})
const guidancePrompts = computed(() => {
  const item = currentItem.value
  if (!item) return []
  const point = item.knowledge_points[0] || item.title
  return [
    '用一句话复述 "' + point + '" 解决的核心问题。',
    '找出本节和项目目标之间的直接关系。',
    '记录一个仍然不确定的点，后续进入智能辅导或练习评估时继续追问。'
  ]
})

onMounted(loadClassroom)

watch(
  () => [props.projectId, props.itemId] as const,
  () => loadClassroom()
)

async function loadClassroom() {
  if (!props.projectId || !props.itemId) return
  loading.value = true
  viewedSections.value = new Set()
  activeSectionKey.value = 'summary'
  try {
    const { data } = await getCurrentSyllabus(props.projectId)
    const item = data.items.find((candidate) => candidate.id === props.itemId)
    if (item && item.status === 'pending') {
      syllabus.value = data
      await updateStatus('in_progress', '进入课堂自动开始学习')
    } else {
      syllabus.value = data
    }
    markSectionViewed(activeSectionKey.value)
  } finally {
    loading.value = false
  }
}

function openSection(key: string) {
  activeSectionKey.value = key
  markSectionViewed(key)
}

function markSectionViewed(key: string) {
  if (!learningSections.value.some((section) => section.key === key)) return
  viewedSections.value = new Set([...viewedSections.value, key])
  void completeWhenReady()
}

async function completeWhenReady() {
  const item = currentItem.value
  if (!item || statusUpdating.value) return
  if (['completed', 'mastered'].includes(item.status)) return
  if (!learningSections.value.length || viewedSections.value.size < learningSections.value.length) return
  await updateStatus('completed', '课堂关键板块已浏览完成，系统自动更新学习进度')
  ElMessage.success('本节学习进度已自动更新')
}

async function updateStatus(status: string, reason: string) {
  if (!props.itemId) return
  statusUpdating.value = true
  try {
    const { data } = await updateSyllabusItemStatus(props.itemId, status, reason)
    syllabus.value = data
  } finally {
    statusUpdating.value = false
  }
}

async function goBackToSyllabus() {
  if (!props.projectId) return
  await router.push({ name: 'project-syllabus', params: { projectId: props.projectId } })
}

function buildSections(item: SyllabusItemRead | null): ClassroomSection[] {
  if (!item) return []
  const documents = item.related_documents.length
    ? item.related_documents.map((doc) => ({
        label: doc,
        type: '资料来源',
        href: /^https?:\/\//i.test(doc) ? doc : `#${encodeURIComponent(doc)}`
      }))
    : []
  return [
    {
      key: 'summary',
      title: '基础总结',
      kind: '讲解',
      summary: item.objective,
      points: [item.recommendation_reason],
      resources: []
    },
    {
      key: 'knowledge',
      title: '关键知识点',
      kind: '知识图谱',
      summary: '本节会优先围绕这些知识点建立概念关系，再进入例题、实践或复现任务。',
      points: item.knowledge_points.length ? item.knowledge_points : [item.title],
      resources: documents
    },
    {
      key: 'practice',
      title: '例题与练习',
      kind: '评估',
      summary: item.assessment_method || item.completion_criteria,
      points: [item.completion_criteria],
      resources: item.recommended_resource_types.map((label) => ({ label, type: '资源类型', href: '#practice' }))
    },
    {
      key: 'demo',
      title: '可视化与实操',
      kind: '多模态',
      summary: '把当前知识项转换为可观察、可操作、可复现的学习材料，适合后续接入视频、动画、代码 Demo 或实验材料。',
      points: item.classroom_types.length ? item.classroom_types : ['讲解文档', '可视化演示', '复现 Demo'],
      resources: item.classroom_types.map((label) => ({ label, type: '课堂形态', href: '#demo' }))
    },
    {
      key: 'review',
      title: '复盘与下一步',
      kind: '路径调整',
      summary: '完成本节后，系统会把学习行为写回项目进度，后续可用于每日计划、补救学习项和资源推荐。',
      points: [item.completion_criteria, item.assessment_method].filter(Boolean),
      resources: []
    }
  ]
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
</script>
