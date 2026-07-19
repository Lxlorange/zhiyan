<template>
  <div class="page workspace-module-page">
    <section class="workspace-hero">
      <div>
        <span>{{ currentMeta.eyebrow }}</span>
        <h2>{{ currentMeta.title }}</h2>
        <p>{{ currentMeta.description }}</p>
      </div>
      <el-button :loading="loading" @click="refreshWorkspace">刷新数据</el-button>
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
        <article class="panel-like workspace-panel wide">
          <header>
            <strong>学习画像条目</strong>
            <span>{{ profileEntries.length }} entries</span>
          </header>
          <div class="profile-entry-list">
            <div v-for="entry in profileEntries" :key="entry.key" class="profile-entry-card">
              <div class="profile-entry-head">
                <div><strong>{{ entry.label }}</strong><small>{{ entry.key }}</small></div>
                <div class="profile-entry-actions">
                  <el-button text size="small" @click="openEditDialog(entry)">编辑</el-button>
                  <el-button text size="small" type="danger" @click="handleDeleteEntry(entry)">删除</el-button>
                </div>
              </div>
              <p>{{ entry.value }}</p>
              <small v-if="entry.source">来源: {{ entry.source }} · {{ entry.confidence }}% 置信</small>
            </div>
            <div v-if="!profileEntries.length" class="profile-empty">暂无画像条目</div>
            <el-button type="primary" size="small" @click="openNewDialog">+ 新增条目</el-button>
          </div>
        </article>
        <article class="panel-like workspace-panel">
          <header><strong>编辑条目</strong><span>{{ editMode === 'new' ? '新增' : '修改' }}</span></header>
          <el-form label-position="top" class="compact-form">
            <el-form-item label="条目键名">
              <el-select v-if="editMode === 'new'" v-model="editForm.key" filterable allow-create placeholder="选择或输入键名" style="width:100%">
                <el-option v-for="(label, key) in profileKeyLabels" :key="key" :label="label" :value="key" />
              </el-select>
              <el-input v-else :model-value="editForm.key" disabled />
            </el-form-item>
            <el-form-item label="条目内容">
              <el-input v-model="editForm.value" type="textarea" :rows="5" placeholder="输入画像条目内容" />
            </el-form-item>
            <el-form-item label="置信度">
              <el-slider v-model="editForm.confidence" :min="0" :max="100" :step="5" />
            </el-form-item>
            <div class="form-row">
              <el-button @click="resetEditForm">取消</el-button>
              <el-button type="primary" :loading="savingProfile" :disabled="!editForm.key.trim() || !editForm.value.trim()" @click="handleSaveEntry">保存</el-button>
            </div>
          </el-form>
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
          <header class="literature-panel-header">
            <div>
              <strong>文献列表</strong>
              <span>{{ literatureItems.length }} items</span>
            </div>
            <div class="literature-panel-actions">
              <el-input
                v-model="literatureQuery"
                clearable
                placeholder="搜索标题、作者、摘要、来源、笔记"
                @clear="handleResetLiteratureQuery"
                @keyup.enter="handleSearchLiterature"
              >
                <template #append>
                  <el-button :icon="Search" :loading="literatureLoading" @click="handleSearchLiterature">搜索</el-button>
                </template>
              </el-input>
              <el-button :icon="RefreshLeft" text @click="handleResetLiteratureQuery">重置</el-button>
            </div>
          </header>

          <div class="literature-list">
            <div v-if="literatureLoading" class="literature-empty">正在加载文献列表...</div>
            <template v-else>
              <article v-for="paper in literatureItems" :key="paper.id" class="literature-item">
                <div class="literature-item-head">
                  <div>
                    <strong>{{ paper.title }}</strong>
                    <p>{{ literatureMetaLine(paper) }}</p>
                  </div>
                  <el-button :icon="Delete" text type="danger" @click="handleDeleteLiterature(paper)">
                    删除
                  </el-button>
                </div>
                <p>{{ paper.abstract || paper.notes || paper.citation_text }}</p>
                <small>{{ readingStatusLabel(paper.reading_status) }} · {{ paper.source_uri || paper.citation_text }}</small>
              </article>
              <div v-if="!literatureItems.length" class="literature-empty">
                暂无匹配文献
              </div>
            </template>
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
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Delete, Edit, Plus, RefreshLeft, Search } from '@element-plus/icons-vue'
import {
  createLiterature,
  deleteLiterature,
  deleteProfileEntry,
  getWorkspaceOverview,
  listLiterature,
  runResearchTool,
  suggestLiteratureMetadata,
  updateProfileEntry,
  type LiteraturePaperRead,
  type ProfileEntryRead,
  type ProfileCenterResponse,
  type WorkspaceOverviewResponse
} from '../services/apiClient'

type Mode = 'profile' | 'literature' | 'methods'
type ToolType = 'topic' | 'paper_reading' | 'review' | 'polish' | 'format' | 'citation' | 'method' | 'experiment' | 'reproduce' | 'defense'

const props = defineProps<{ mode: Mode }>()

const loading = ref(false)
const savingLiterature = ref(false)
const suggestingLiterature = ref(false)
const runningTool = ref(false)
const literatureLoading = ref(false)
const overview = ref<WorkspaceOverviewResponse | null>(null)
const literatureItems = ref<LiteraturePaperRead[]>([])
const literatureQuery = ref('')
const literatureSuggestionTip = ref('')
const literatureSummaryRef = ref<HTMLElement | null>(null)

const literatureForm = reactive({
  title: '',
  authors: '',
  venue: '',
  year: '',
  source_uri: '',
  abstract: ''
})

const profileEntries = computed<ProfileEntryRead[]>(() => overview.value?.profile.entries || [])
const profileKeyLabels: Record<string, string> = {
  knowledge_base: '知识基础',
  learning_goal: '学习目标',
  cognitive_style: '认知风格',
  weak_points: '易错点',
  practice_level: '实践能力',
  resource_preference: '资源偏好',
  learning_pace: '学习节奏',
  interest_direction: '兴趣方向',
  current_research_direction: '当前科研方向',
  mastery: '掌握度分布',
  question_habit: '提问习惯',
  output_goal: '产出目标',
  academic_writing: '学术写作能力',
  literature_reading: '文献阅读能力',
  coding_practice: '代码实践能力',
  experiment_design: '实验设计能力'
}
const editMode = ref<'new' | 'edit'>('new')
const editForm = reactive({ key: '', value: '', confidence: 70 })
const savingProfile = ref(false)

function openNewDialog() {
  editMode.value = 'new'
  editForm.key = ''
  editForm.value = ''
  editForm.confidence = 70
}

function openEditDialog(entry: ProfileEntryRead) {
  editMode.value = 'edit'
  editForm.key = entry.key
  editForm.value = String(entry.value ?? '')
  editForm.confidence = entry.confidence
}

function resetEditForm() {
  editMode.value = 'new'
  editForm.key = ''
  editForm.value = ''
  editForm.confidence = 70
}

async function handleSaveEntry() {
  if (!editForm.key.trim() || !editForm.value.trim()) return
  savingProfile.value = true
  try {
    const { data } = await updateProfileEntry({
      key: editForm.key.trim(),
      value: editForm.value.trim(),
      confidence: editForm.confidence,
      source: 'manual',
      update_reason: editMode.value === 'new' ? '用户手动新增画像条目' : '用户手动编辑画像条目'
    })
    overview.value = { ...overview.value!, profile: data }
    resetEditForm()
    ElMessage.success(editMode.value === 'new' ? '画像条目已创建' : '画像条目已更新')
  } finally {
    savingProfile.value = false
  }
}

async function handleDeleteEntry(entry: ProfileEntryRead) {
  try {
    await ElMessageBox.confirm(`确定删除「${entry.label}」条目吗？`, '确认删除', { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' })
    const { data } = await deleteProfileEntry(entry.key)
    overview.value = { ...overview.value!, profile: data }
    ElMessage.success('画像条目已删除')
  } catch {
    // cancelled
  }
}

const toolForm = reactive({
  tool_type: 'method' as ToolType,
  input_text: '',
  extra_requirement: ''
})

const metaMap: Record<Mode, { eyebrow: string; title: string; description: string }> = {
  profile: {
    eyebrow: 'Profile',
    title: '学习画像',
    description: '维护学习画像条目，支撑个性化推荐。'
  },
  literature: {
    eyebrow: 'Literature',
    title: '文献知识库',
    description: '输入论文标题后可自动抓取作者、来源和摘要。'
  },
  methods: {
    eyebrow: 'Methods',
    title: '科研方法',
    description: '保留轻量方法工具，帮助快速生成研究辅助内容。'
  }
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
  { label: '答辩', value: 'defense' as ToolType, agent: 'DefenseAgent', description: '生成追问与修改建议。', placeholder: '输入题目或摘要' }
]

const selectedTool = computed(() => visibleToolOptions.find((item) => item.value === toolForm.tool_type))
const visibleToolRuns = computed(() => (overview.value?.tool_runs || []).filter((run) => run.tool_type === toolForm.tool_type))

async function loadOverview() {
  const { data } = await getWorkspaceOverview()
  overview.value = data
}

async function loadLiterature(query = literatureQuery.value) {
  if (props.mode !== 'literature') {
    literatureItems.value = []
    return
  }
  literatureLoading.value = true
  try {
    const { data } = await listLiterature(query.trim())
    literatureItems.value = data
  } finally {
    literatureLoading.value = false
  }
}

async function refreshWorkspace() {
  loading.value = true
  try {
    await loadOverview()
    if (props.mode === 'literature') {
      await loadLiterature()
    }
  } finally {
    loading.value = false
  }
}

async function handleSearchLiterature() {
  literatureQuery.value = literatureQuery.value.trim()
  await loadLiterature(literatureQuery.value)
}

async function handleResetLiteratureQuery() {
  literatureQuery.value = ''
  await loadLiterature('')
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
    await refreshWorkspace()
  } finally {
    savingLiterature.value = false
  }
}

async function handleDeleteLiterature(paper: LiteraturePaperRead) {
  try {
    await ElMessageBox.confirm(`确认删除文献“${paper.title}”吗？`, '删除文献', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning'
    })
  } catch {
    return
  }

  await deleteLiterature(paper.id)
  ElMessage.success('已删除文献')
  await refreshWorkspace()
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

function literatureMetaLine(paper: LiteraturePaperRead) {
  const authors = paper.authors.length ? paper.authors.join('，') : '未填写作者'
  const year = paper.year || '未填写年份'
  const venue = paper.venue || '未填写来源'
  return `${authors} · ${year} · ${venue}`
}

function buildLiteratureSuggestionFailureMessage() {
  const title = literatureForm.title.trim()
  if (!title) return '请先输入论文标题。'
  if (/doi/i.test(title)) return 'DOI 没有匹配到结果，可以改用英文题名再试。'
  if (/[\u4e00-\u9fa5]/.test(title)) return '中文题名没有抓到结果，建议补充英文题名或 DOI。'
  return '没有抓到匹配结果，可能是题名不完整或外部源暂时不可用。'
}

watch(
  () => props.mode,
  () => {
    void refreshWorkspace()
  }
)

onMounted(() => {
  void refreshWorkspace()
})
</script>

<style scoped>
.literature-panel-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.literature-panel-header > div:first-child {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.literature-panel-actions {
  display: flex;
  flex: 1;
  justify-content: flex-end;
  align-items: flex-start;
  gap: 8px;
  flex-wrap: wrap;
}

.literature-panel-actions :deep(.el-input) {
  min-width: 280px;
  flex: 1 1 280px;
}

.literature-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-top: 16px;
}

.literature-item {
  padding-top: 12px;
  border-top: 1px solid var(--el-border-color-lighter);
}

.literature-item:first-child {
  border-top: 0;
  padding-top: 0;
}

.literature-item-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.literature-item-head p {
  margin: 4px 0 0;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  line-height: 1.45;
}

.literature-item > p {
  margin: 8px 0 6px;
  color: var(--el-text-color-primary);
  line-height: 1.65;
}

.literature-empty {
  padding: 16px 0;
  color: var(--el-text-color-secondary);
}
.profile-entry-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 12px;
}

.profile-entry-card {
  padding: 12px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  background: var(--el-bg-color-page);
}

.profile-entry-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 8px;
  margin-bottom: 6px;
}

.profile-entry-head div:first-child {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.profile-entry-head div:first-child small {
  color: var(--el-text-color-secondary);
  font-size: 11px;
}

.profile-entry-actions {
  display: flex;
  gap: 4px;
  flex-shrink: 0;
}

.profile-entry-card p {
  margin: 4px 0;
  color: var(--el-text-color-primary);
  font-size: 13px;
  line-height: 1.55;
  white-space: pre-wrap;
}

.profile-entry-card small {
  color: var(--el-text-color-secondary);
  font-size: 11px;
}

.profile-empty {
  padding: 20px;
  text-align: center;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.workspace-panel-wide {
  grid-column: 1 / -1;
}
</style>
