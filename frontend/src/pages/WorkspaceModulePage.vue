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
        <article class="panel-like workspace-panel wide">
          <header>
            <strong>当前画像条目</strong>
            <el-button size="small" @click="openProfileEntry()">新增条目</el-button>
          </header>
          <div v-if="profileEntries.length" class="profile-entry-grid editable">
            <div v-for="entry in profileEntries" :key="entry.key" :class="{ muted: !entry.is_enabled }">
              <span>{{ entry.label }}</span>
              <div class="profile-entry-value">
                <small v-for="part in displayParts(entry.value)" :key="part">{{ part }}</small>
              </div>
              <small>{{ entry.source }} · 置信度 {{ entry.confidence }}% · {{ entry.is_enabled ? '参与推荐' : '已停用' }}</small>
              <div class="profile-entry-actions">
                <el-button size="small" @click="openProfileEntry(entry)">编辑</el-button>
                <el-button size="small" type="danger" plain @click="handleDeleteProfileEntry(entry)">删除</el-button>
              </div>
            </div>
          </div>
          <el-empty v-else description="还没有画像条目。可以手动新增，也可以通过学习、问答、笔记和复盘由 AI 自动沉淀。" />
        </article>
      </section>

      <section v-else-if="mode === 'literature'" class="workspace-grid two">
        <article class="panel-like workspace-panel">
          <header>
            <strong>新增文献</strong>
            <span>Personal Library</span>
          </header>
          <el-form label-position="top" class="compact-form">
            <el-form-item label="标题">
              <el-input v-model="literatureForm.title" placeholder="论文或资料标题" />
            </el-form-item>
            <el-form-item label="作者">
              <el-input v-model="literatureForm.authors" placeholder="多个作者用逗号分隔" />
            </el-form-item>
            <div class="form-row">
              <el-form-item label="来源">
                <el-input v-model="literatureForm.venue" placeholder="期刊、会议、课程资料" />
              </el-form-item>
              <el-form-item label="年份">
                <el-input v-model="literatureForm.year" placeholder="2026" />
              </el-form-item>
            </div>
            <el-form-item label="摘要 / 笔记">
              <el-input v-model="literatureForm.abstract" type="textarea" :rows="5" />
            </el-form-item>
            <el-button type="primary" :loading="savingLiterature" :disabled="!literatureForm.title.trim()" @click="handleCreateLiterature">
              保存文献
            </el-button>
          </el-form>
        </article>

        <article class="panel-like workspace-panel">
          <header><strong>文献列表</strong><span>{{ overview?.literature.length || 0 }} items</span></header>
          <div class="literature-list">
            <div v-for="paper in overview?.literature || []" :key="paper.id">
              <strong>{{ paper.title }}</strong>
              <p>{{ paper.abstract || paper.citation_text }}</p>
              <small>{{ readingStatusLabel(paper.reading_status) }} · {{ paper.source_uri || paper.citation_text }}</small>
              <div class="literature-actions">
                <el-select :model-value="paper.reading_status" size="small" @change="(status: string) => handleUpdateLiteratureStatus(paper.id, status)">
                  <el-option label="未读" value="unread" />
                  <el-option label="精读中" value="reading" />
                  <el-option label="已读" value="read" />
                  <el-option label="已引用" value="cited" />
                </el-select>
                <el-button size="small" @click="usePaperForTool(paper)">用于精读</el-button>
              </div>
            </div>
          </div>
        </article>
      </section>

      <section v-else class="research-workflow-grid">
        <article class="panel-like workspace-panel research-tool-catalog">
          <header><strong>{{ toolTitle }}</strong><span>ResearchToolAgent</span></header>
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
              <el-input v-model="toolForm.input_text" type="textarea" :rows="8" :placeholder="selectedTool?.placeholder || '粘贴论文段落、实验方案、综述提纲或引用信息'" />
            </el-form-item>
            <el-form-item label="补充要求">
              <el-input v-model="toolForm.extra_requirement" placeholder="例如：围绕我的研究方向，输出可直接用于课程论文的结构化结果" />
            </el-form-item>
            <el-button type="primary" :loading="runningTool" :disabled="!toolForm.input_text.trim()" @click="handleRunTool">
              运行科研工具
            </el-button>
          </el-form>
        </article>

        <article class="panel-like workspace-panel">
          <header><strong>最近结果</strong><span>History</span></header>
          <div class="tool-run-list">
            <div v-for="run in visibleToolRuns" :key="run.id">
              <strong>{{ run.title }}</strong>
              <el-collapse>
                <el-collapse-item title="查看生成结果" :name="String(run.id)">
                  <p v-if="run.output_data.revised_text">{{ run.output_data.revised_text }}</p>
                  <p v-if="run.output_data.final_topic"><strong>最终选题：</strong>{{ run.output_data.final_topic }}</p>
                  <ul>
                    <li v-for="item in compactOutput(run.output_data)" :key="item">{{ item }}</li>
                  </ul>
                  <div v-if="Array.isArray(run.output_data.defense_questions) && run.output_data.defense_questions.length" class="workspace-list">
                    <p v-for="(question, index) in run.output_data.defense_questions" :key="`defense-${run.id}-${index}`">
                      {{ renderDefenseQuestion(question) }}
                    </p>
                  </div>
                </el-collapse-item>
              </el-collapse>
            </div>
          </div>
        </article>
      </section>
    </template>

    <el-drawer v-model="profileDrawerVisible" title="编辑画像条目" size="420px">
      <el-form label-position="top" class="compact-form">
        <el-form-item label="画像维度">
          <el-select v-model="profileEntryForm.key" filterable :disabled="Boolean(profileEntryForm.editingKey)">
            <el-option v-for="entry in profileEntryOptions" :key="entry.key" :label="entry.label" :value="entry.key" />
          </el-select>
        </el-form-item>
        <el-form-item label="条目内容">
          <el-input v-model="profileEntryForm.value" type="textarea" :rows="5" placeholder="例如：更适合图解 + 代码案例；薄弱点是矩阵运算和实验评价。" />
        </el-form-item>
        <el-form-item label="置信度">
          <el-slider v-model="profileEntryForm.confidence" :min="0" :max="100" />
        </el-form-item>
        <el-form-item label="是否影响个性化推荐">
          <el-switch v-model="profileEntryForm.is_enabled" active-text="启用" inactive-text="停用" />
        </el-form-item>
        <el-form-item label="更新原因">
          <el-input v-model="profileEntryForm.update_reason" />
        </el-form-item>
        <div class="drawer-actions">
          <el-button @click="profileDrawerVisible = false">取消</el-button>
          <el-button type="primary" :loading="savingProfileEntry" @click="handleSaveProfileEntry">保存条目</el-button>
        </div>
      </el-form>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  createLiterature,
  deleteProfileEntry,
  getWorkspaceOverview,
  listKnowledgePoints,
  runResearchTool,
  updateLiterature,
  updateProfileEntry,
  type KnowledgePointRead,
  type ProfileEntryRead,
  type LiteraturePaperRead,
  type WorkspaceOverviewResponse
} from '../services/apiClient'

type Mode = 'profile' | 'literature' | 'writing' | 'methods'
type ToolType = 'polish' | 'format' | 'citation' | 'review' | 'method' | 'experiment' | 'reproduce' | 'topic' | 'defense' | 'paper_reading'

const props = defineProps<{ mode: Mode }>()
const router = useRouter()
const loading = ref(false)
const savingLiterature = ref(false)
const runningTool = ref(false)
const savingProfileEntry = ref(false)
const overview = ref<WorkspaceOverviewResponse | null>(null)
const knowledgePoints = ref<KnowledgePointRead[]>([])
const profileDrawerVisible = ref(false)
const literatureForm = reactive({ title: '', authors: '', venue: '', year: '', abstract: '' })
const toolForm = reactive({
  tool_type: 'polish' as ToolType,
  input_text: '',
  extra_requirement: ''
})
const profileEntryForm = reactive({
  editingKey: '',
  key: 'knowledge_base',
  value: '',
  confidence: 90,
  is_enabled: true,
  update_reason: '用户手动编辑画像条目'
})

const metaMap: Record<Mode, { eyebrow: string; title: string; description: string }> = {
  profile: { eyebrow: 'Profile', title: '学习画像', description: '沉淀学生近期学习行为、薄弱点、资源偏好和画像版本，用于后续个性化推荐。' },
  literature: { eyebrow: 'Literature', title: '文献知识库', description: '保存论文、资料、摘要、引用文本和阅读状态。' },
  writing: { eyebrow: 'Writing', title: '论文写作', description: '提供选题凝练、综述写作、论文润色、引用规范和模拟答辩。' },
  methods: { eyebrow: 'Methods', title: '科研方法', description: '围绕实验设计、论文复现、评价指标和学术规范生成学习建议。' }
}
const currentMeta = computed(() => metaMap[props.mode])
type WorkspaceMetric = { label: string; value: string | number; hint?: string }

const metrics = computed<WorkspaceMetric[]>(() => {
  const data = overview.value?.metrics || {}
  if (props.mode === 'profile') {
    return [
      { label: '画像完整度', value: `${enabledProfileEntries.value.length}/${profileEntryOptions.length}`, hint: '已启用画像维度' },
      { label: '画像条目', value: profileEntries.value.length, hint: '可人工修正' },
      { label: '平均置信度', value: `${profileConfidenceAverage.value}%`, hint: '低置信条目需复盘' },
      { label: '当前版本', value: `v${overview.value?.profile.current_revision || 0}`, hint: '学习记录驱动更新' }
    ]
  }
  if (props.mode === 'literature') {
    return [
      { label: '文献', value: data.literature || 0, hint: '论文与资料条目' },
      { label: '精读中', value: literatureStatusCount('reading'), hint: '正在处理' },
      { label: '已读', value: literatureStatusCount('read'), hint: '可进入引用' },
      { label: '已引用', value: literatureStatusCount('cited'), hint: '写作输出证据' }
    ]
  }
  if (props.mode === 'writing') {
    return [
      { label: '写作记录', value: filteredToolRunCount(['topic', 'paper_reading', 'review', 'polish', 'format', 'citation', 'defense']), hint: '论文工具产出' },
      { label: '文献', value: data.literature || 0, hint: '可用于精读与引用' },
      { label: '画像版本', value: `v${overview.value?.profile.current_revision || 0}`, hint: '写作个性化依据' }
    ]
  }
  if (props.mode === 'methods') {
    return [
      { label: '方法记录', value: filteredToolRunCount(['method', 'experiment', 'reproduce', 'defense']), hint: '科研工具产出' },
      { label: '练习证据', value: data.submissions || 0, hint: '能力评估依据' },
      { label: '知识点', value: knowledgePoints.value.length, hint: '方法训练范围' }
    ]
  }
  return []
})
const profileEntries = computed(() => overview.value?.profile.entries || [])
const enabledProfileEntries = computed(() => profileEntries.value.filter((entry) => entry.is_enabled))
const profileConfidenceAverage = computed(() => {
  if (!profileEntries.value.length) return 0
  const total = profileEntries.value.reduce((sum, entry) => sum + Number(entry.confidence || 0), 0)
  return Math.round(total / profileEntries.value.length)
})
const toolOptions = [
  { label: '选题凝练', value: 'topic' as ToolType, agent: 'TopicAgent', description: '把宽泛方向压缩成具体题目、研究问题、边界和预期贡献。', placeholder: '输入你的科研兴趣、课程要求、已有资料和期望产出，AI 会形成具体选题。' },
  { label: '论文精读', value: 'paper_reading' as ToolType, agent: 'PaperAgent', description: '输出论文摘要、方法、创新点、局限性和可引用要点。', placeholder: '粘贴论文标题、摘要、链接或你的阅读笔记。' },
  { label: '综述提纲', value: 'review' as ToolType, agent: 'ReviewAgent', description: '拆解研究脉络、方法对比、挑战和章节草稿。', placeholder: '输入研究方向或文献列表，生成综述结构。' },
  { label: '论文润色', value: 'polish' as ToolType, agent: 'WritingAgent', description: '保留原意，优化学术表达、逻辑衔接和措辞边界。', placeholder: '粘贴需要润色的论文段落。' },
  { label: '格式规范', value: 'format' as ToolType, agent: 'FormatAgent', description: '检查标题层级、图表编号、摘要关键词和课程报告格式。', placeholder: '粘贴论文结构或全文片段。' },
  { label: '引用检查', value: 'citation' as ToolType, agent: 'CitationAgent', description: '生成 GB/T 7714、APA、IEEE 建议并提醒缺失来源。', placeholder: '粘贴参考文献、URL、DOI 或引用段落。' },
  { label: '科研方法', value: 'method' as ToolType, agent: 'MethodAgent', description: '解释研究设计、变量控制、指标选择和学术规范。', placeholder: '输入你的研究问题或方法疑问。' },
  { label: '实验助手', value: 'experiment' as ToolType, agent: 'ExperimentAgent', description: '生成技术路线、数据采集、指标、变量、图表规范和阶段计划。', placeholder: '输入你的选题、数据条件和实验目标，生成完整实验方案。' },
  { label: '论文复现', value: 'reproduce' as ToolType, agent: 'ReproduceAgent', description: '拆解复现步骤、代码骨架、数据准备和验收证据。', placeholder: '输入论文或开源项目链接，生成复现计划。' },
  { label: '模拟答辩', value: 'defense' as ToolType, agent: 'DefenseAgent', description: '生成开题、中期、答辩问题、追问、评分和修改建议。', placeholder: '粘贴你的题目、摘要或论文初稿，生成模拟答辩。' }
]
const toolTitle = computed(() => props.mode === 'methods' ? '科研方法工具' : '论文写作工具')
const visibleToolOptions = computed(() => {
  if (props.mode === 'methods') return toolOptions.filter((item) => ['method', 'experiment', 'reproduce', 'defense'].includes(item.value))
  return toolOptions.filter((item) => ['topic', 'paper_reading', 'review', 'polish', 'format', 'citation', 'defense'].includes(item.value))
})
const selectedTool = computed(() => toolOptions.find((item) => item.value === toolForm.tool_type))
const visibleToolRuns = computed(() => {
  const runs = overview.value?.tool_runs || []
  if (props.mode === 'methods') return runs.filter((run) => ['method', 'experiment', 'reproduce', 'defense'].includes(run.tool_type))
  return runs.filter((run) => ['topic', 'paper_reading', 'review', 'polish', 'format', 'citation', 'defense'].includes(run.tool_type))
})
function filteredToolRunCount(types: ToolType[]) {
  return (overview.value?.tool_runs || []).filter((run) => types.includes(run.tool_type as ToolType)).length
}

function literatureStatusCount(status: string) {
  return (overview.value?.literature || []).filter((paper) => paper.reading_status === status).length
}

const profileEntryOptions = [
  { key: 'knowledge_base', label: '知识基础' },
  { key: 'learning_goal', label: '学习目标' },
  { key: 'cognitive_style', label: '认知风格' },
  { key: 'weak_points', label: '易错点' },
  { key: 'practice_level', label: '实践能力' },
  { key: 'resource_preference', label: '资源偏好' },
  { key: 'learning_pace', label: '学习节奏' },
  { key: 'interest_direction', label: '兴趣方向' },
  { key: 'current_research_direction', label: '当前科研方向' },
  { key: 'academic_writing', label: '学术写作能力' },
  { key: 'literature_reading', label: '文献阅读能力' },
  { key: 'coding_practice', label: '代码实践能力' },
  { key: 'experiment_design', label: '实验设计能力' }
]

onMounted(async () => {
  await Promise.all([loadOverview(), loadKnowledgePoints()])
})
watch(() => props.mode, () => {
  toolForm.tool_type = props.mode === 'methods' ? 'experiment' : 'topic'
})

async function loadOverview() {
  loading.value = true
  try {
    const { data } = await getWorkspaceOverview()
    overview.value = data
    hydratePendingToolDraft()
  } finally {
    loading.value = false
  }
}

async function loadKnowledgePoints() {
  const { data } = await listKnowledgePoints()
  knowledgePoints.value = data
}

async function handleCreateLiterature() {
  savingLiterature.value = true
  try {
    await createLiterature({
      title: literatureForm.title,
      authors: splitList(literatureForm.authors),
      venue: literatureForm.venue,
      year: literatureForm.year,
      abstract: literatureForm.abstract,
      keywords: splitList(literatureForm.abstract).slice(0, 6),
      reading_status: 'reading'
    })
    Object.assign(literatureForm, { title: '', authors: '', venue: '', year: '', abstract: '' })
    ElMessage.success('文献已保存')
    await loadOverview()
  } finally {
    savingLiterature.value = false
  }
}

async function handleUpdateLiteratureStatus(paperId: number, status: string) {
  await updateLiterature(paperId, { reading_status: status })
  ElMessage.success('文献阅读状态已更新')
  await loadOverview()
}

function usePaperForTool(paper: LiteraturePaperRead) {
  const draft = {
    tool_type: 'paper_reading' as ToolType,
    input_text: [
      `标题：${paper.title}`,
      `作者：${paper.authors.join(', ')}`,
      `来源：${paper.venue} ${paper.year}`,
      `链接/来源：${paper.source_uri}`,
      `摘要：${paper.abstract}`,
      `笔记：${paper.notes}`
    ].filter(Boolean).join('\n'),
    extra_requirement: '请按论文精读助手要求输出研究问题、方法概述、创新点、局限性和推荐阅读顺序。'
  }
  sessionStorage.setItem('research_tool_draft', JSON.stringify(draft))
  void router.push({ name: 'writing' })
}

function openProfileEntry(entry?: ProfileEntryRead) {
  profileEntryForm.editingKey = entry?.key || ''
  profileEntryForm.key = entry?.key || 'knowledge_base'
  profileEntryForm.value = asText(entry?.value || '')
  profileEntryForm.confidence = entry?.confidence || 90
  profileEntryForm.is_enabled = entry?.is_enabled ?? true
  profileEntryForm.update_reason = entry ? `手动修正画像条目：${entry.label}` : '用户手动新增画像条目'
  profileDrawerVisible.value = true
}

async function handleSaveProfileEntry() {
  savingProfileEntry.value = true
  try {
    const normalizedValue = normalizeProfileEntryValue(profileEntryForm.key, profileEntryForm.value)
    const { data } = await updateProfileEntry({
      key: profileEntryForm.key,
      value: normalizedValue,
      confidence: profileEntryForm.confidence,
      source: 'manual',
      is_confirmed: true,
      is_enabled: profileEntryForm.is_enabled,
      update_reason: profileEntryForm.update_reason
    })
    if (overview.value) overview.value.profile = data
    profileDrawerVisible.value = false
    ElMessage.success('画像条目已保存')
  } finally {
    savingProfileEntry.value = false
  }
}

async function handleDeleteProfileEntry(entry: ProfileEntryRead) {
  await ElMessageBox.confirm(`删除「${entry.label}」后，它不会再参与项目规划和课堂生成。`, '删除画像条目', {
    confirmButtonText: '删除',
    cancelButtonText: '取消',
    type: 'warning'
  })
  const { data } = await deleteProfileEntry(entry.key)
  if (overview.value) overview.value.profile = data
  ElMessage.success('画像条目已删除')
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

function asText(value: unknown) {
  if (Array.isArray(value)) return value.join(' / ')
  if (typeof value === 'object' && value) return displayParts(value).join(' / ')
  return String(value || '')
}

function displayParts(value: unknown): string[] {
  if (value === null || value === undefined || value === '') return ['暂无内容']
  if (Array.isArray(value)) {
    const parts = value.flatMap((item) => displayParts(item))
    return parts.length ? parts : ['暂无内容']
  }
  if (typeof value === 'object') {
    const entries = Object.entries(value as Record<string, unknown>)
      .filter(([, entryValue]) => entryValue !== null && entryValue !== undefined && entryValue !== '')
      .map(([key, entryValue]) => `${readableKey(key)}：${displayParts(entryValue).join('、')}`)
    return entries.length ? entries : ['暂无内容']
  }
  return [String(value)]
}

function splitList(value: string) {
  return value.split(/[,，;；\n]/).map((item) => item.trim()).filter(Boolean)
}

function normalizeProfileEntryValue(key: string, value: string) {
  if (['weak_points', 'resource_preference'].includes(key)) return splitList(value)
  return value
}

function readingStatusLabel(status: string) {
  const labels: Record<string, string> = {
    unread: '未读',
    reading: '精读中',
    read: '已读',
    cited: '已引用'
  }
  return labels[status] || status
}

function hydratePendingToolDraft() {
  if (props.mode !== 'writing') return
  const raw = sessionStorage.getItem('research_tool_draft')
  if (!raw) return
  sessionStorage.removeItem('research_tool_draft')
  const draft = JSON.parse(raw) as { tool_type?: ToolType; input_text?: string; extra_requirement?: string }
  toolForm.tool_type = draft.tool_type || 'paper_reading'
  toolForm.input_text = draft.input_text || ''
  toolForm.extra_requirement = draft.extra_requirement || ''
  ElMessage.success('已载入文献精读草稿')
}

function compactOutput(data: Record<string, any>) {
  return [
    ...(data.topic_options || []),
    ...(data.diagnosis || []),
    ...(data.structure_suggestions || []),
    ...(data.citation_suggestions || []),
    ...(data.method_steps || []),
    ...(data.experiment_plan || []),
    ...(data.scoring_rubric || []),
    ...(data.source_notes || []),
    ...(data.safety_notes || []),
    ...(data.next_actions || [])
  ].flatMap((item) => displayParts(item)).slice(0, 14)
}

function renderDefenseQuestion(value: Record<string, any>) {
  const stage = value.stage || value.type || '答辩'
  const question = value.question || value.prompt || displayParts(value).join('；')
  const followUp = value.follow_up || value.followup || value.follow_up_question
  return followUp ? `${stage}：${question} 追问：${followUp}` : `${stage}：${question}`
}

function readableKey(key: string) {
  const labels: Record<string, string> = {
    knowledge_base: '知识基础',
    learning_goal: '学习目标',
    cognitive_style: '认知风格',
    weak_points: '薄弱点',
    practice_level: '实践能力',
    resource_preference: '资源偏好',
    learning_pace: '学习节奏',
    interest_direction: '兴趣方向',
    current_research_direction: '当前科研方向',
    academic_writing: '学术写作',
    literature_reading: '文献阅读',
    coding_practice: '代码实践',
    experiment_design: '实验设计',
    reason: '原因',
    title: '标题',
    summary: '摘要',
    action: '行动',
    score: '评分',
    question: '问题',
    follow_up: '追问'
  }
  return labels[key] || key.replace(/_/g, ' ')
}

function formatDate(value: string) {
  return new Date(value).toLocaleString()
}
</script>
