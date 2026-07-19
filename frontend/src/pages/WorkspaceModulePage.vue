<template>
  <div class="page workspace-module-page">
    <section class="workspace-hero">
      <div>
        <span>{{ currentMeta.eyebrow }}</span>
        <h2>{{ currentMeta.title }}</h2>
        <p>{{ currentMeta.description }}</p>
      </div>
      <el-button :loading="loading" @click="loadOverview">刷新数据</el-button>
    </section>

    <section v-if="loading" class="panel-like workspace-loading">正在加载模块数据...</section>

    <template v-else>
      <section v-if="metrics.length" class="workspace-metrics compact-stat-row">
        <article v-for="metric in metrics" :key="metric.label" class="metric-card">
          <span>{{ metric.label }}</span>
          <strong>{{ metric.value }}</strong>
          <small v-if="metric.hint">{{ metric.hint }}</small>
        </article>
      </section>

      <section v-if="mode === 'profile'" class="workspace-grid two">
        <article class="panel-like workspace-panel">
          <header><strong>学习画像</strong><span>Profile</span></header>
          <p>这里保留可编辑的学习画像条目，作为个性化推荐的基础数据。</p>
        </article>
      </section>

      <section v-else-if="mode === 'literature'" class="workspace-grid two">
        <article class="panel-like workspace-panel">
          <header><strong>文献知识库</strong><span>Literature</span></header>
          <el-form label-position="top" class="compact-form">
            <el-form-item label="论文标题">
              <el-input v-model="literatureForm.title" placeholder="输入论文名称后再点击自动抓取信息" />
            </el-form-item>
            <div class="form-row">
              <el-form-item label="作者">
                <el-input v-model="literatureForm.authors" placeholder="多个作者用逗号分隔" />
              </el-form-item>
              <el-form-item label="来源">
                <el-input v-model="literatureForm.venue" placeholder="期刊 / 会议 / 课程资料" />
              </el-form-item>
            </div>
            <div class="form-row">
              <el-form-item label="年份">
                <el-input v-model="literatureForm.year" placeholder="2026" />
              </el-form-item>
              <el-form-item label="来源链接">
                <el-input v-model="literatureForm.source_uri" placeholder="自动抓取或手动填写" />
              </el-form-item>
            </div>
            <el-form-item label="摘要 / 备注">
              <el-input v-model="literatureForm.abstract" type="textarea" :rows="5" />
            </el-form-item>
            <div class="form-row">
              <el-button type="primary" :loading="savingLiterature" :disabled="!literatureForm.title.trim()" @click="handleCreateLiterature">
                保存文献
              </el-button>
              <el-button :loading="suggestingLiterature" :disabled="!literatureForm.title.trim()" @click="handleSuggestLiterature">
                自动抓取信息
              </el-button>
            </div>
            <p v-if="literatureSuggestionTip" class="literature-suggestion-tip">{{ literatureSuggestionTip }}</p>
            <div ref="literatureSummaryRef" v-if="literatureForm.abstract.trim()" class="literature-summary-card">
              <strong>抓取摘要</strong>
              <p>{{ literatureForm.abstract }}</p>
            </div>
          </el-form>
        </article>

        <article class="panel-like workspace-panel">
          <header><strong>文献列表</strong><span>{{ overview?.literature.length || 0 }} items</span></header>
          <div class="literature-list">
            <div v-for="paper in overview?.literature || []" :key="paper.id">
              <strong>{{ paper.title }}</strong>
              <p>{{ paper.abstract || paper.citation_text }}</p>
              <small>{{ readingStatusLabel(paper.reading_status) }} · {{ paper.source_uri || paper.citation_text }}</small>
            </div>
          </div>
        </article>
      </section>

      <section v-else class="research-workflow-grid">
        <article class="panel-like workspace-panel research-tool-catalog">
          <header><strong>科研方法工具</strong><span>Light tools</span></header>
          <button
            v-for="item in visibleToolOptions"
            :key="item.value"
            type="button"
            :class="{ active: toolForm.tool_type === item.value }"
            @click="toolForm.tool_type = item.value"
          >
            <strong>{{ item.label }}</strong>
            <span>{{ item.description }}</span>
          </button>
        </article>

        <article class="panel-like workspace-panel research-tool-runner">
          <header><strong>{{ selectedTool?.label || '科研工具' }}</strong><span>{{ selectedTool?.agent || 'ResearchToolAgent' }}</span></header>
          <el-form label-position="top" class="compact-form">
            <el-form-item label="输入内容">
              <el-input v-model="toolForm.input_text" type="textarea" :rows="8" :placeholder="selectedTool?.placeholder || '粘贴论文片段、实验方案或研究问题'" />
            </el-form-item>
            <el-form-item label="补充要求">
              <el-input v-model="toolForm.extra_requirement" placeholder="例如：输出更适合课程汇报的版本" />
            </el-form-item>
            <el-button type="primary" :loading="runningTool" :disabled="!toolForm.input_text.trim()" @click="handleRunTool">
              运行工具
            </el-button>
          </el-form>
        </article>

        <article class="panel-like workspace-panel">
          <header><strong>最近结果</strong><span>History</span></header>
          <div class="tool-run-list">
            <div v-for="run in visibleToolRuns" :key="run.id">
              <strong>{{ run.title }}</strong>
              <p>{{ run.input_text }}</p>
            </div>
          </div>
        </article>
      </section>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  createLiterature,
  getWorkspaceOverview,
  runResearchTool,
  suggestLiteratureMetadata,
  type WorkspaceOverviewResponse
} from '../services/apiClient'

type Mode = 'profile' | 'literature' | 'methods'
type ToolType = 'topic' | 'paper_reading' | 'review' | 'polish' | 'format' | 'citation' | 'method' | 'experiment' | 'reproduce' | 'defense'

const props = defineProps<{ mode: Mode }>()
const loading = ref(false)
const savingLiterature = ref(false)
const suggestingLiterature = ref(false)
const runningTool = ref(false)
const overview = ref<WorkspaceOverviewResponse | null>(null)
const literatureForm = reactive({ title: '', authors: '', venue: '', year: '', source_uri: '', abstract: '' })
const literatureSuggestionTip = ref('')
const literatureSummaryRef = ref<HTMLElement | null>(null)
const toolForm = reactive({ tool_type: 'method' as ToolType, input_text: '', extra_requirement: '' })

const metaMap: Record<Mode, { eyebrow: string; title: string; description: string }> = {
  profile: { eyebrow: 'Profile', title: '学习画像', description: '维护学习画像条目，支持个性化推荐。' },
  literature: { eyebrow: 'Literature', title: '文献知识库', description: '输入论文标题后可自动抓取作者、来源和摘要。' },
  methods: { eyebrow: 'Methods', title: '科研方法', description: '保留轻量方法工具，删除难理解的复杂导航。' }
}
const currentMeta = computed(() => metaMap[props.mode])

const metrics = computed(() => {
  const data = overview.value?.metrics || {}
  if (props.mode === 'literature') {
    return [
      { label: '文献数', value: data.literature || 0, hint: '已保存的文献条目' },
      { label: '工具结果', value: data.tool_runs || 0, hint: '方法工具生成记录' }
    ]
  }
  if (props.mode === 'methods') {
    return [
      { label: '方法结果', value: data.tool_runs || 0, hint: '当前方法工具结果数' },
      { label: '知识点', value: overview.value?.resources.length || 0, hint: '可参考资源数' }
    ]
  }
  return [{ label: '画像条目', value: overview.value?.profile.entries.length || 0, hint: '可编辑画像字段' }]
})

const visibleToolOptions = [
  { label: '选题', value: 'topic' as ToolType, agent: 'TopicAgent', description: '把宽泛方向收紧成问题。', placeholder: '输入研究方向或题目' },
  { label: '方法', value: 'method' as ToolType, agent: 'MethodAgent', description: '解释研究设计与步骤。', placeholder: '输入研究问题或方法困惑' },
  { label: '复现', value: 'reproduce' as ToolType, agent: 'ReproduceAgent', description: '整理复现步骤和验证项。', placeholder: '输入论文或项目链接' },
  { label: '答辩', value: 'defense' as ToolType, agent: 'DefenseAgent', description: '生成追问和修改建议。', placeholder: '输入题目或摘要' }
]
const selectedTool = computed(() => visibleToolOptions.find((item) => item.value === toolForm.tool_type))
const visibleToolRuns = computed(() => (overview.value?.tool_runs || []).filter((run) => run.tool_type === toolForm.tool_type))

async function loadOverview() {
  loading.value = true
  try {
    const { data } = await getWorkspaceOverview()
    overview.value = data
  } finally {
    loading.value = false
  }
}

async function handleSuggestLiterature() {
  const title = literatureForm.title.trim()
  if (!title) {
    ElMessage.warning('请先输入论文标题')
    return
  }
  suggestingLiterature.value = true
  literatureSuggestionTip.value = ''
  try {
    const { data } = await suggestLiteratureMetadata({ title })
    literatureForm.title = data.title || title
    literatureForm.authors = data.authors.join('，')
    literatureForm.venue = data.venue
    literatureForm.year = data.year
    literatureForm.source_uri = data.source_uri
    literatureForm.abstract = data.abstract
    literatureSuggestionTip.value = data.reason
      ? `已从 ${data.source_name || '外部来源'} 抓取到信息：${data.reason}`
      : `已从 ${data.source_name || '外部来源'} 抓取到信息`
    await nextTick()
    literatureSummaryRef.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    ElMessage.success('已自动补全文献信息')
  } catch {
    literatureSuggestionTip.value = buildLiteratureSuggestionFailureMessage()
  } finally {
    suggestingLiterature.value = false
  }
}

async function handleCreateLiterature() {
  savingLiterature.value = true
  try {
    await createLiterature({
      title: literatureForm.title,
      authors: splitList(literatureForm.authors),
      venue: literatureForm.venue,
      year: literatureForm.year,
      source_uri: literatureForm.source_uri,
      abstract: literatureForm.abstract,
      keywords: splitList(literatureForm.abstract).slice(0, 6),
      reading_status: 'reading'
    })
    Object.assign(literatureForm, { title: '', authors: '', venue: '', year: '', source_uri: '', abstract: '' })
    literatureSuggestionTip.value = ''
    ElMessage.success('文献已保存')
    await loadOverview()
  } finally {
    savingLiterature.value = false
  }
}

async function handleRunTool() {
  runningTool.value = true
  try {
    const { data } = await runResearchTool({
      tool_type: toolForm.tool_type,
      input_text: toolForm.input_text,
      extra_requirement: toolForm.extra_requirement
    })
    ElMessage.success(`已生成：${data.title}`)
    toolForm.input_text = ''
    toolForm.extra_requirement = ''
    await loadOverview()
  } finally {
    runningTool.value = false
  }
}

function readingStatusLabel(status: string) {
  return { unread: '未读', reading: '精读中', read: '已读', cited: '已引用' }[status] || status
}

function splitList(value: string) {
  return value.split(/[,，\n]/).map((item) => item.trim()).filter(Boolean)
}

function buildLiteratureSuggestionFailureMessage() {
  const title = literatureForm.title.trim()
  if (!title) return '请先输入论文标题。'
  if (/doi/i.test(title)) return 'DOI 没有匹配到结果，可以改用英文题名再试。'
  if (/[\u4e00-\u9fa5]/.test(title)) return '中文题名没有抓到结果，建议补充英文题名或 DOI。'
  return '没有抓到匹配结果，可能是题名不完整或外部来源暂时不可用。'
}

onMounted(() => {
  void loadOverview()
})
</script>
