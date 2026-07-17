<template>
  <div class="methods-page workspace-module-page">
    <section class="methods-page-hero page-hero">
      <div class="methods-page-hero-copy">
        <p class="methods-eyebrow eyebrow">METHODS</p>
        <h1>科研方法</h1>
        <p>围绕实验设计、论文复现、选题评估和学术规范，集中常用科研动作与方法资源。</p>
      </div>
      <el-button class="methods-ghost-btn" :loading="reloading" @click="reload">
        <el-icon><Refresh /></el-icon>
        刷新数据
      </el-button>
    </section>

    <section class="methods-main-layout">
      <aside class="methods-sidebar">
        <section class="methods-panel methods-panel-compact panel-like">
          <div class="methods-panel-head">
            <strong>工具入口</strong>
            <span>按任务切换</span>
          </div>
          <div class="methods-tool-list">
            <button
              v-for="tool in toolGroups"
              :key="tool.label"
              type="button"
              class="methods-tool-chip"
              :class="{ active: activeTool === tool.label }"
              @click="handleToolSelect(tool.label)"
            >
              <span class="methods-tool-copy">
                <strong>{{ tool.label }}</strong>
                <span>{{ tool.description }}</span>
              </span>
              <span class="methods-tool-state" aria-hidden="true">{{ activeTool === tool.label ? '●' : '○' }}</span>
            </button>
          </div>
        </section>

        <section class="methods-panel methods-panel-compact methods-nav-panel panel-like">
          <div class="methods-panel-head">
            <strong>方法导航</strong>
            <span>{{ points.length }} 个知识点</span>
          </div>
          <div class="methods-nav-scroll">
            <div v-if="points.length" class="methods-nav-list">
              <button
                v-for="point in points"
                :key="point.id"
                type="button"
                class="methods-nav-item"
                :class="{ active: selectedPointId === point.id }"
                @click="handlePointSelect(point)"
              >
                <strong>{{ point.name }}</strong>
                <span>{{ point.chapter }} / {{ point.difficulty }}</span>
                <small>{{ point.description }}</small>
              </button>
            </div>
            <el-empty v-else description="暂无方法数据" :image-size="64" />
          </div>
        </section>
      </aside>

      <main class="methods-content">
        <section class="methods-panel methods-panel-hero panel-like">
          <div class="methods-panel-head methods-workbench-head">
            <div>
              <span>A3 SMART WORKBENCH</span>
              <strong>方法台</strong>
            </div>
            <span class="methods-panel-caption">把研究问题拆成方法、材料、验证和产出</span>
          </div>

          <div class="methods-focus-card" aria-live="polite">
            <div>
              <span>当前聚焦</span>
              <strong>{{ focusedTitle }}</strong>
            </div>
            <p>{{ focusedDescription }}</p>
            <span class="methods-focus-status">已同步到检索框</span>
          </div>

          <div class="methods-course-grid">
            <button
              v-for="card in courseCards"
              :key="card.title"
              type="button"
              class="methods-course-card"
              :class="{ active: focusedTitle === card.title }"
              :style="{ '--card-tint': card.tint }"
              @click="handleCourseCard(card)"
            >
              <span class="methods-course-icon" aria-hidden="true">
                <el-icon><component :is="card.icon" /></el-icon>
              </span>
              <span class="methods-course-copy">
                <strong>{{ card.title }}</strong>
                <span>{{ card.subtitle }}</span>
              </span>
              <span class="methods-card-action">
                <span>{{ card.routeName ? '打开页面' : '立即检索' }}</span>
                <el-icon aria-hidden="true"><ArrowRight /></el-icon>
              </span>
            </button>
          </div>
        </section>

        <section class="methods-bottom-grid">
          <article class="methods-panel methods-panel-search panel-like">
            <div class="methods-panel-head">
              <strong>参考检索</strong>
              <span class="methods-result-count">{{ hits.length }} 条结果</span>
            </div>
            <div class="methods-search-row">
              <el-input
                v-model="query"
                clearable
                placeholder="输入研究问题、方法名、指标或论文关键词"
                @keyup.enter="runSearch"
              />
              <el-button type="primary" :loading="searching" @click="runSearch">检索</el-button>
            </div>
            <div class="methods-search-results">
              <article v-for="hit in hits" :key="`${hit.document_title}-${hit.section_title}`" class="methods-search-hit">
                <div class="methods-search-hit-head">
                  <strong>{{ hit.knowledge_point }}</strong>
                  <span>{{ hit.document_type }}</span>
                </div>
                <p>{{ hit.content }}</p>
                <small>{{ hit.document_title }} · {{ hit.source_uri }}</small>
              </article>
              <el-empty v-if="!searching && query && !hits.length" description="没有检索到内容，请更换关键词" :image-size="72" />
            </div>
            <el-button class="methods-panel-link" text @click="jumpToLibrary">
              进入文献知识库
              <el-icon aria-hidden="true"><ArrowRight /></el-icon>
            </el-button>
          </article>

          <article class="methods-panel methods-panel-assist panel-like">
            <div class="methods-panel-head">
              <strong>{{ activeTool }}</strong>
              <el-button text @click="jumpToWriting">进入论文写作</el-button>
            </div>
            <div class="methods-assist-stack">
              <button
                v-for="(item, index) in activeAssistItems"
                :key="item.title"
                type="button"
                class="methods-assist-card"
                :class="{ active: focusedTitle === item.title }"
                @click="handleAssistItem(item)"
              >
                <span class="methods-assist-index">{{ String(index + 1).padStart(2, '0') }}</span>
                <span>
                  <strong>{{ item.title }}</strong>
                  <p>{{ item.description }}</p>
                </span>
                <el-icon aria-hidden="true"><ArrowRight /></el-icon>
              </button>
            </div>
          </article>
        </section>
      </main>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import type { Component } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  Aim,
  ArrowRight,
  Collection,
  DataAnalysis,
  DocumentChecked,
  EditPen,
  Promotion,
  Refresh,
  Search,
  TrendCharts
} from '@element-plus/icons-vue'
import {
  listKnowledgePoints,
  searchKnowledge as apiSearchKnowledge,
  type KnowledgePointRead,
  type KnowledgeSearchHit
} from '../services/apiClient'

type ToolLabel = '实验助手' | '论文复现' | '选题规划' | '模拟答辩'
type AssistItem = { title: string; description: string; routeName?: string }
type CourseCard = {
  title: string
  subtitle: string
  query: string
  icon: Component
  tint: string
  routeName?: string
}

const router = useRouter()
const query = ref('科研方法')
const searching = ref(false)
const reloading = ref(false)
const hits = ref<KnowledgeSearchHit[]>([])
const points = ref<KnowledgePointRead[]>([])
const activeTool = ref<ToolLabel>('实验助手')
const selectedPointId = ref<number | null>(null)
const focusedTitle = ref('实验设计')
const focusedDescription = ref('明确自变量、因变量、对照组和评价指标。')

const toolGroups: Array<{ label: ToolLabel; description: string }> = [
  { label: '实验助手', description: '变量、对照、指标、流程' },
  { label: '论文复现', description: '步骤、代码、数据、验证' },
  { label: '选题规划', description: '问题、边界、贡献、风险' },
  { label: '模拟答辩', description: '追问、评分、修改建议' }
]

const courseCards: CourseCard[] = [
  { title: '投稿与发表', subtitle: '论文与成果输出', query: '投稿与发表', icon: Promotion, tint: '#fbfaf6', routeName: 'writing' },
  { title: '选题策划', subtitle: '研究问题与边界', query: '选题策划', icon: Aim, tint: '#fbfaf6' },
  { title: '方法智能体', subtitle: '方法设计与检查', query: '研究方法设计', icon: DataAnalysis, tint: '#fbfaf6' },
  { title: '智能选题测评', subtitle: '主题筛选与评估', query: '选题测评', icon: Search, tint: '#fbfaf6', routeName: 'assessment' },
  { title: '基础选题测评', subtitle: '题目可行性预检', query: '选题可行性', icon: DocumentChecked, tint: '#fbfaf6' },
  { title: '学术前沿', subtitle: '方向与趋势', query: '学术前沿', icon: TrendCharts, tint: '#fbfaf6', routeName: 'literature' },
  { title: '科研数据资源库', subtitle: '数据集与来源', query: '科研数据资源', icon: Collection, tint: '#fbfaf6', routeName: 'literature' },
  { title: '审稿与修改', subtitle: '审稿意见处理', query: '审稿与修改', icon: EditPen, tint: '#fbfaf6', routeName: 'writing' }
]

const assistItems: Record<ToolLabel, AssistItem[]> = {
  实验助手: [
    { title: '实验设计', description: '明确自变量、因变量、对照组和评价指标。' },
    { title: '变量控制', description: '拆出干扰因素、随机化和重复验证。' },
    { title: '流程清单', description: '按步骤生成执行和记录模板。' }
  ],
  论文复现: [
    { title: '复现步骤', description: '拆解论文方法、数据和实验条件。', routeName: 'literature' },
    { title: '代码入口', description: '定位论文实现中的关键模块。' },
    { title: '验证项', description: '整理与原文对齐的检查清单。' }
  ],
  选题规划: [
    { title: '问题定义', description: '将宽泛方向压缩成可执行题目。' },
    { title: '创新点', description: '识别贡献边界和可发表点。' },
    { title: '风险评估', description: '预估数据、时间和技术风险。', routeName: 'assessment' }
  ],
  模拟答辩: [
    { title: '追问模拟', description: '生成评审可能关注的问题。', routeName: 'assessment' },
    { title: '评分维度', description: '围绕结构、数据、论证和表达检查。', routeName: 'assessment' },
    { title: '修改建议', description: '输出可执行的迭代建议。', routeName: 'writing' }
  ]
}

const activeAssistItems = computed(() => assistItems[activeTool.value])

function updateFocus(title: string, description: string) {
  focusedTitle.value = title
  focusedDescription.value = description
}

function handleToolSelect(label: ToolLabel) {
  activeTool.value = label
  const firstItem = activeAssistItems.value[0]
  updateFocus(firstItem.title, firstItem.description)
  query.value = firstItem.title
}

async function handlePointSelect(point: KnowledgePointRead) {
  selectedPointId.value = point.id
  query.value = point.name
  updateFocus(point.name, point.description || `${point.chapter} / ${point.difficulty}`)
  await runSearch()
}

async function handleCourseCard(card: CourseCard) {
  query.value = card.query
  updateFocus(card.title, card.subtitle)
  if (card.routeName) {
    await router.push({ name: card.routeName })
    return
  }
  await runSearch()
}

async function handleAssistItem(item: AssistItem) {
  query.value = item.title
  updateFocus(item.title, item.description)
  if (item.routeName) {
    await router.push({ name: item.routeName })
    return
  }
  await runSearch()
}

async function jumpToLibrary() {
  await router.push({ name: 'literature' })
}

async function jumpToWriting() {
  await router.push({ name: 'writing' })
}

async function loadPoints() {
  try {
    const { data } = await listKnowledgePoints()
    points.value = data.slice(0, 12)
    if (selectedPointId.value === null && points.value.length) {
      const firstPoint = points.value[0]
      selectedPointId.value = firstPoint.id
      updateFocus(firstPoint.name, firstPoint.description || firstPoint.chapter)
    }
  } catch {
    ElMessage.error('方法导航加载失败')
  }
}

async function runSearch() {
  const keyword = query.value.trim()
  if (!keyword) {
    ElMessage.warning('请输入检索关键词')
    return
  }
  searching.value = true
  try {
    const { data } = await apiSearchKnowledge(keyword)
    hits.value = data
  } catch {
    ElMessage.error('检索失败，请稍后重试')
  } finally {
    searching.value = false
  }
}

async function reload() {
  reloading.value = true
  try {
    await Promise.all([loadPoints(), runSearch()])
  } finally {
    reloading.value = false
  }
}

onMounted(() => {
  void reload()
})
</script>
