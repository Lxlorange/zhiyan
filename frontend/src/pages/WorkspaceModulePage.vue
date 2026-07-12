<template>
  <div class="page workspace-module-page">
    <section class="workspace-hero">
      <div>
        <p class="eyebrow">{{ currentMeta.eyebrow }}</p>
        <h2>{{ currentMeta.title }}</h2>
        <p>{{ currentMeta.description }}</p>
      </div>
      <el-button :loading="loading" @click="loadOverview">刷新数据</el-button>
    </section>

    <section v-if="loading" class="panel-like workspace-loading">正在加载模块数据...</section>

    <template v-else>
      <section class="workspace-metrics">
        <article v-for="metric in metrics" :key="metric.label" class="metric-card">
          <span>{{ metric.label }}</span>
          <strong>{{ metric.value }}</strong>
        </article>
      </section>

      <section v-if="mode === 'profile'" class="workspace-grid two">
        <article class="panel-like workspace-panel">
          <header>
            <strong>当前画像条目</strong>
            <el-button size="small" @click="openProfileEntry()">新增条目</el-button>
          </header>
          <div v-if="profileEntries.length" class="profile-entry-grid editable">
            <div v-for="entry in profileEntries" :key="entry.key" :class="{ muted: !entry.is_enabled }">
              <span>{{ entry.label }}</span>
              <strong>{{ asText(entry.value) }}</strong>
              <small>{{ entry.source }} · 置信度 {{ entry.confidence }}% · {{ entry.is_enabled ? '参与推荐' : '已停用' }}</small>
              <el-button size="small" @click="openProfileEntry(entry)">编辑</el-button>
            </div>
          </div>
          <el-empty v-else description="还没有画像。请先通过对话式画像或课堂复盘积累画像。" />
        </article>

        <article class="panel-like workspace-panel">
          <header><strong>画像建议</strong><span>Personalization</span></header>
          <div class="workspace-list">
            <p v-for="item in overview?.profile.recommendations || []" :key="item">{{ item }}</p>
          </div>
        </article>

        <article class="panel-like workspace-panel wide">
          <header><strong>对话式更新画像</strong><span>ProfileAgent</span></header>
          <el-input
            v-model="profileMessage"
            type="textarea"
            :rows="4"
            placeholder="例如：我是电子信息专业，机器学习基础一般，更喜欢图解和代码案例，每天能学 45 分钟。"
          />
          <div class="classroom-action-row">
            <el-button type="primary" :loading="updatingProfile" :disabled="!profileMessage.trim()" @click="handleUpdateProfile">
              更新画像
            </el-button>
          </div>
        </article>

        <article class="panel-like workspace-panel wide">
          <header><strong>版本记录</strong><span>Version History</span></header>
          <el-timeline>
            <el-timeline-item
              v-for="version in overview?.profile.versions || []"
              :key="version.id"
              :timestamp="formatDate(version.created_at)"
            >
              <strong>Revision {{ version.revision }}</strong>
              <p>{{ version.update_reason }}</p>
            </el-timeline-item>
          </el-timeline>
        </article>
      </section>

      <section v-else-if="mode === 'resources'" class="workspace-grid two">
        <article class="panel-like workspace-panel">
          <header><strong>课程知识库检索</strong><span>Knowledge Base</span></header>
          <div class="knowledge-search-row">
            <el-input v-model="knowledgeQuery" placeholder="搜索知识点、实验、资料来源" @keyup.enter="handleSearchKnowledge" />
            <el-button type="primary" :loading="searchingKnowledge" :disabled="!knowledgeQuery.trim()" @click="handleSearchKnowledge">
              检索
            </el-button>
          </div>
          <div class="knowledge-hit-list">
            <div v-for="hit in knowledgeHits" :key="`${hit.document_title}-${hit.content.slice(0, 16)}`">
              <strong>{{ hit.knowledge_point }} · {{ hit.document_title }}</strong>
              <p>{{ hit.content }}</p>
              <small>{{ hit.document_type }} · {{ hit.source_uri }}</small>
            </div>
            <el-empty v-if="knowledgeQuery && !knowledgeHits.length && !searchingKnowledge" description="没有检索到资料片段，请换一个知识点或关键词。" />
          </div>
        </article>

        <article class="panel-like workspace-panel">
          <header><strong>课程知识点总览</strong><span>{{ knowledgePoints.length }} points</span></header>
          <div class="knowledge-point-scroll">
            <button v-for="point in knowledgePoints" :key="point.id" type="button" @click="searchByPoint(point.name)">
              <strong>{{ point.name }}</strong>
              <span>{{ point.chapter }} · {{ point.difficulty }}</span>
              <small>{{ point.description }}</small>
            </button>
          </div>
        </article>

        <article class="panel-like workspace-panel">
          <header><strong>生成资源</strong><span>{{ overview?.resources.length || 0 }} items</span></header>
          <div class="resource-list">
            <div v-for="resource in overview?.resources || []" :key="resource.id" class="resource-card">
              <span>{{ resource.resource_type }}</span>
              <strong>{{ resource.title }}</strong>
              <p>{{ resource.source }}</p>
              <small>{{ formatDate(resource.created_at) }}</small>
            </div>
          </div>
          <el-empty v-if="!overview?.resources.length" description="还没有生成资源。请先从学习清单进入课堂生成 PPT、图解、演示或语音稿。" />
        </article>

        <article class="panel-like workspace-panel">
          <header><strong>Agent 生成轨迹</strong><span>Trace</span></header>
          <div class="agent-trace-list">
            <div v-for="task in overview?.agent_tasks || []" :key="`${task.agent}-${task.output_summary}-${task.latency_ms}`">
              <el-tag :type="task.status === 'completed' || task.status === 'done' ? 'success' : task.status === 'failed' ? 'danger' : 'warning'" size="small">
                {{ task.status }}
              </el-tag>
              <strong>{{ task.agent }}</strong>
              <p>{{ task.output_summary }}</p>
              <small>{{ task.input_summary }}</small>
            </div>
          </div>
        </article>
      </section>

      <section v-else-if="mode === 'assessment'" class="workspace-grid two">
        <article class="panel-like workspace-panel">
          <header><strong>最近提交</strong><span>Evidence</span></header>
          <div class="submission-list">
            <div v-for="submission in overview?.submissions || []" :key="submission.id">
              <strong>{{ submission.submission_type }} · {{ submission.score }} 分</strong>
              <el-tag :type="submission.passed ? 'success' : 'warning'" size="small">
                {{ submission.passed ? '通过' : '待改进' }}
              </el-tag>
              <p>{{ submission.feedback }}</p>
              <small>{{ formatDate(submission.created_at) }}</small>
            </div>
          </div>
        </article>
        <article class="panel-like workspace-panel">
          <header><strong>动态优化建议</strong><span>Next Action</span></header>
          <div class="workspace-list">
            <p v-for="item in assessmentSuggestions" :key="item">{{ item }}</p>
          </div>
        </article>
      </section>

      <section v-else-if="mode === 'tutor'" class="workspace-grid two">
        <article class="panel-like workspace-panel">
          <header><strong>智能辅导入口</strong><span>Tutor Flow</span></header>
          <div class="workspace-list">
            <p>从项目学习清单进入任意课堂，在课堂左侧追问中持续对话。</p>
            <p>课堂上下文会自动携带课件、例题、实操、复盘和画像建议。</p>
            <p>辅导回答会进入课堂提交记录，后续用于评估和画像更新。</p>
          </div>
        </article>
        <article class="panel-like workspace-panel">
          <header><strong>最近 Agent 回答</strong><span>DialogueAgent</span></header>
          <div class="workspace-list">
            <p v-for="task in tutorTasks" :key="`${task.agent}-${task.output_summary}`">{{ task.output_summary }}</p>
          </div>
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
                    <p v-for="question in run.output_data.defense_questions" :key="JSON.stringify(question)">
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
          <el-select v-model="profileEntryForm.key" filterable>
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
import { ElMessage } from 'element-plus'
import {
  createLiterature,
  getWorkspaceOverview,
  listKnowledgePoints,
  searchKnowledge,
  runResearchTool,
  updateLiterature,
  updateProfileEntry,
  updateProfileByDialogue,
  type KnowledgePointRead,
  type KnowledgeSearchHit,
  type ProfileEntryRead,
  type LiteraturePaperRead,
  type WorkspaceOverviewResponse
} from '../services/apiClient'

type Mode = 'profile' | 'resources' | 'tutor' | 'assessment' | 'literature' | 'writing' | 'methods'
type ToolType = 'polish' | 'format' | 'citation' | 'review' | 'method' | 'experiment' | 'reproduce' | 'topic' | 'defense' | 'paper_reading'

const props = defineProps<{ mode: Mode }>()
const router = useRouter()
const loading = ref(false)
const savingLiterature = ref(false)
const runningTool = ref(false)
const updatingProfile = ref(false)
const searchingKnowledge = ref(false)
const savingProfileEntry = ref(false)
const overview = ref<WorkspaceOverviewResponse | null>(null)
const profileMessage = ref('')
const knowledgeQuery = ref('')
const knowledgeHits = ref<KnowledgeSearchHit[]>([])
const knowledgePoints = ref<KnowledgePointRead[]>([])
const profileDrawerVisible = ref(false)
const literatureForm = reactive({ title: '', authors: '', venue: '', year: '', abstract: '' })
const toolForm = reactive({
  tool_type: 'polish' as ToolType,
  input_text: '',
  extra_requirement: ''
})
const profileEntryForm = reactive({
  key: 'knowledge_base',
  value: '',
  confidence: 90,
  is_enabled: true,
  update_reason: '用户手动编辑画像条目'
})

const metaMap: Record<Mode, { eyebrow: string; title: string; description: string }> = {
  profile: { eyebrow: 'Profile', title: '学习画像', description: '后台化维护画像条目、版本和个性化调用建议。' },
  resources: { eyebrow: 'Resources', title: '资源中心', description: '集中查看课堂 PPT、互动演示、语音稿和多智能体生成记录。' },
  tutor: { eyebrow: 'Tutor', title: '智能辅导', description: '课堂内持续追问，回答会进入学习证据。' },
  assessment: { eyebrow: 'Assessment', title: '练习评估', description: '汇总课堂测验、实操和复盘反馈，形成下一步优化建议。' },
  literature: { eyebrow: 'Literature', title: '文献知识库', description: '保存论文、资料、摘要、引用文本和阅读状态。' },
  writing: { eyebrow: 'Writing', title: '论文写作', description: '提供选题凝练、综述写作、论文润色、引用规范和模拟答辩。' },
  methods: { eyebrow: 'Methods', title: '科研方法', description: '围绕实验设计、论文复现、评估指标和学术规范生成学习建议。' }
}
const currentMeta = computed(() => metaMap[props.mode])
const metrics = computed(() => {
  const data = overview.value?.metrics || {}
  return [
    { label: '项目', value: data.projects || 0 },
    { label: '资源', value: data.resources || 0 },
    { label: 'Agent任务', value: data.agent_tasks || 0 },
    { label: '提交记录', value: data.submissions || 0 },
    { label: '文献', value: data.literature || 0 }
  ]
})
const profileEntries = computed(() => overview.value?.profile.entries || [])
const tutorTasks = computed(() => (overview.value?.agent_tasks || []).filter((task) => task.agent.includes('Dialogue')).slice(0, 8))
const assessmentSuggestions = computed(() => {
  const failed = (overview.value?.submissions || []).filter((item) => !item.passed).slice(0, 4)
  if (!failed.length) return ['最近提交整体通过，可以继续推进下一项课堂。', '建议保持复盘习惯，用证据更新画像。']
  return failed.map((item) => `${item.submission_type} 需要改进：${item.feedback}`)
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
  if (!knowledgeQuery.value && data.length) {
    knowledgeQuery.value = data[0].name
    await handleSearchKnowledge()
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

async function handleSearchKnowledge() {
  searchingKnowledge.value = true
  try {
    const { data } = await searchKnowledge(knowledgeQuery.value, 8)
    knowledgeHits.value = data
  } finally {
    searchingKnowledge.value = false
  }
}

function searchByPoint(point: string) {
  knowledgeQuery.value = point
  void handleSearchKnowledge()
}

async function handleUpdateProfile() {
  updatingProfile.value = true
  try {
    const { data } = await updateProfileByDialogue(profileMessage.value)
    ElMessage.success(`画像已更新到 Revision ${data.revision}`)
    profileMessage.value = ''
    await loadOverview()
  } finally {
    updatingProfile.value = false
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

function asText(value: unknown) {
  if (Array.isArray(value)) return value.join(' / ')
  if (typeof value === 'object' && value) return JSON.stringify(value)
  return String(value || '')
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
  ].map((item) => typeof item === 'string' ? item : JSON.stringify(item)).slice(0, 14)
}

function renderDefenseQuestion(value: Record<string, any>) {
  const stage = value.stage || value.type || '答辩'
  const question = value.question || value.prompt || JSON.stringify(value)
  const followUp = value.follow_up || value.followup || value.follow_up_question
  return followUp ? `${stage}：${question} 追问：${followUp}` : `${stage}：${question}`
}

function formatDate(value: string) {
  return new Date(value).toLocaleString()
}
</script>
