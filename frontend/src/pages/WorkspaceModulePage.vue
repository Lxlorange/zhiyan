<template>
  <div class="page workspace-module-page">
    <section class="workspace-hero">
      <div>
        <h2>{{ currentMeta.title }}</h2>
        <p>{{ currentMeta.description }}</p>
      </div>
      <el-button :loading="loading" @click="loadOverview">鍒锋柊鏁版嵁</el-button>
    </section>

    <section v-if="loading" class="panel-like workspace-loading">姝ｅ湪鍔犺浇妯″潡鏁版嵁...</section>

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
            <strong>褰撳墠鐢诲儚鏉＄洰</strong>
            <el-button size="small" @click="openProfileEntry()">鏂板鏉＄洰</el-button>
          </header>
          <div v-if="profileEntries.length" class="profile-entry-grid editable">
            <div v-for="entry in profileEntries" :key="entry.key" :class="{ muted: !entry.is_enabled }">
              <span>{{ entry.label }}</span>
              <strong>{{ asText(entry.value) }}</strong>
              <small>{{ entry.source }} 路 缃俊搴?{{ entry.confidence }}% 路 {{ entry.is_enabled ? '鍙備笌鎺ㄨ崘' : '宸插仠鐢? }}</small>
              <div class="profile-entry-actions">
                <el-button size="small" @click="openProfileEntry(entry)">缂栬緫</el-button>
                <el-button size="small" type="danger" plain @click="handleDeleteProfileEntry(entry)">鍒犻櫎</el-button>
              </div>
            </div>
          </div>
          <el-empty v-else description="还没有画像条目。可以手动新增，也可以通过学习、问答、笔记和复盘由 AI 自动沉淀。" />
        </article>
      </section>

      <section v-else-if="mode === 'resources'" class="workspace-grid two">
        <article class="panel-like workspace-panel">
          <header><strong>鏁版嵁搴撴矇娣€</strong><span>Knowledge Deposit</span></header>
          <div class="deposit-summary">
            <div>
              <strong>{{ overview?.resources.length || 0 }}</strong>
              <span>鐢熸垚璧勬簮</span>
            </div>
            <div>
              <strong>{{ overview?.literature.length || 0 }}</strong>
              <span>鏂囩尞绗旇</span>
            </div>
            <div>
              <strong>{{ knowledgePoints.length }}</strong>
              <span>鐭ヨ瘑鐐?/span>
            </div>
          </div>
          <div class="deposit-upload-redirect">
            <strong>璧勬枡涓婁紶宸茬Щ鍒扮嫭绔嬮〉闈?/strong>
            <small>涓婁紶銆佽В鏋愯褰曞拰鏂囨。鍒犻櫎绠＄悊缁熶竴鍦ㄧ煡璇嗗簱涓婁紶椤甸潰瀹屾垚銆?/small>
            <el-button type="primary" @click="router.push({ name: 'knowledge-upload' })">鎵撳紑鐭ヨ瘑搴撲笂浼?/el-button>
          </div>
          <div class="knowledge-search-row">
            <el-input v-model="knowledgeQuery" placeholder="搜索知识点、实验、资料来源" @keyup.enter="handleSearchKnowledge" />
            <el-button type="primary" :loading="searchingKnowledge" :disabled="!knowledgeQuery.trim()" @click="handleSearchKnowledge">
              妫€绱?
            </el-button>
          </div>
          <div class="knowledge-hit-list">
            <div v-for="hit in knowledgeHits" :key="`${hit.document_title}-${hit.content.slice(0, 16)}`">
              <strong>{{ hit.knowledge_point }} 路 {{ hit.document_title }}</strong>
              <p>{{ hit.content }}</p>
              <small>{{ hit.document_type }} 路 {{ hit.source_uri }}</small>
            </div>
            <el-empty v-if="knowledgeQuery && !knowledgeHits.length && !searchingKnowledge" description="没有检索到资料片段，请换一个知识点或关键词。" />
          </div>
        </article>

        <KnowledgeSphereGraph
          v-model:query="knowledgeQuery"
          v-model:project-id="ragProjectId"
          :graph="knowledgeLinkGraph"
          :loading="loadingKnowledgeLinks"
          :project-options="overview?.projects || []"
          :selected-node-id="selectedKnowledgeNode?.id || null"
          @search="handleSearchKnowledge"
          @select-node="selectKnowledgeNode"
        />
        <article class="panel-like workspace-panel">
          <header><strong>鏁版嵁搴?RAG 闂瓟</strong><span>Retrieval QA</span></header>
          <div class="rag-scope-row">
            <el-select v-model="ragProjectId" clearable placeholder="鍏ㄩ儴椤圭洰璧勬枡">
              <el-option
                v-for="project in overview?.projects || []"
                :key="project.id"
                :label="project.title"
                :value="project.id"
              />
            </el-select>
            <el-select v-model="ragKnowledgePoints" multiple collapse-tags collapse-tags-tooltip clearable placeholder="限定知识点">
              <el-option v-for="point in knowledgePoints" :key="point.id" :label="point.name" :value="point.name" />
            </el-select>
          </div>
          <el-input
            v-model="ragQuestion"
            type="textarea"
            :rows="4"
            placeholder="围绕已上传资料、课堂 PPT、笔记或知识点提问"
          />
          <div class="classroom-action-row">
            <el-button type="primary" :loading="generatingRag" :disabled="!ragQuestion.trim()" @click="handleRagAsk">
              鍩轰簬鏁版嵁搴撳洖绛?
            </el-button>
          </div>
          <div v-if="ragAnswer" class="rag-answer">
            <strong>鍥炵瓟</strong>
            <p>{{ ragAnswer }}</p>
            <div v-if="ragResponse?.related_points.length" class="rag-tags">
              <el-tag v-for="point in ragResponse.related_points" :key="point" size="small" @click="searchByPoint(point)">
                {{ point }}
              </el-tag>
            </div>
            <small>
              {{ ragResponse?.used_llm ? '由后端 RAG 结合大模型生成' : '由后端 RAG 检索结果生成' }}
              路 缃俊搴?{{ ragResponse?.confidence || 'medium' }}
            </small>
            <div v-if="ragResponse?.citations.length" class="citation-list">
              <div v-for="(citation, index) in ragResponse.citations" :key="citation.id" class="citation-card">
                <span>鏉ユ簮 {{ index + 1 }} 路 {{ citation.source_type }}</span>
                <strong>{{ citation.title }}</strong>
                <p>{{ citation.content }}</p>
                <small>{{ renderCitationMeta(citation) }}</small>
                <div class="citation-actions">
                  <el-button size="small" @click="locateCitation(citation)">瀹氫綅鐗囨</el-button>
                  <el-button v-if="citation.review_url" size="small" @click="openCitationReview(citation)">鍥炵湅鏉愭枡</el-button>
                </div>
              </div>
            </div>
            <div v-if="ragResponse?.follow_up_questions.length" class="follow-up-list">
              <button v-for="question in ragResponse.follow_up_questions" :key="question" type="button" @click="ragQuestion = question">
                {{ question }}
              </button>
            </div>
          </div>
        </article>

        <article class="panel-like workspace-panel">
          <header><strong>娌夋穩鍐呭</strong><span>{{ overview?.resources.length || 0 }} items</span></header>
          <div class="resource-list">
            <div v-for="resource in overview?.resources || []" :key="resource.id" class="resource-card">
              <span>{{ resource.resource_type }}</span>
              <strong>{{ resource.title }}</strong>
              <p>{{ resource.source }}</p>
              <small>{{ formatDate(resource.created_at) }}</small>
            </div>
          </div>
          <el-empty v-if="!overview?.resources.length" description="还没有沉淀内容。可以先上传资料，或从学习清单进入课堂生成 PPT、图解、演示和笔记。" />
        </article>

        <article class="panel-like workspace-panel">
          <header><strong>知识点索引</strong><span>{{ knowledgePoints.length }} points</span></header>
          <div class="knowledge-point-scroll compact">
            <button v-for="point in knowledgePoints" :key="point.id" type="button" @click="searchByPoint(point.name)">
              <strong>{{ point.name }}</strong>
              <span>{{ point.chapter }} 路 {{ point.difficulty }}</span>
              <small>{{ point.description }}</small>
            </button>
          </div>
        </article>
      </section>

      <section v-else-if="mode === 'literature'" class="workspace-grid two">
        <article class="panel-like workspace-panel">
          <header>
            <strong>鏂板鏂囩尞</strong>
            <span>Personal Library</span>
          </header>
          <el-form label-position="top" class="compact-form">
            <el-form-item label="鏍囬">
              <el-input v-model="literatureForm.title" placeholder="论文或资料标题" />
            </el-form-item>
            <el-form-item label="作者">
              <el-input v-model="literatureForm.authors" placeholder="澶氫釜浣滆€呯敤閫楀彿鍒嗛殧" />
            </el-form-item>
            <div class="form-row">
              <el-form-item label="鏉ユ簮">
                <el-input v-model="literatureForm.venue" placeholder="期刊、会议、课程资料" />
              </el-form-item>
              <el-form-item label="骞翠唤">
                <el-input v-model="literatureForm.year" placeholder="2026" />
              </el-form-item>
            </div>
            <el-form-item label="鎽樿 / 绗旇">
              <el-input v-model="literatureForm.abstract" type="textarea" :rows="5" />
            </el-form-item>
            <el-button type="primary" :loading="savingLiterature" :disabled="!literatureForm.title.trim()" @click="handleCreateLiterature">
              淇濆瓨鏂囩尞
            </el-button>
          </el-form>
        </article>

        <article class="panel-like workspace-panel">
          <header><strong>鏂囩尞鍒楄〃</strong><span>{{ overview?.literature.length || 0 }} items</span></header>
          <div class="literature-list">
            <div v-for="paper in overview?.literature || []" :key="paper.id">
              <strong>{{ paper.title }}</strong>
              <p>{{ paper.abstract || paper.citation_text }}</p>
              <small>{{ readingStatusLabel(paper.reading_status) }} 路 {{ paper.source_uri || paper.citation_text }}</small>
              <div class="literature-actions">
                <el-select :model-value="paper.reading_status" size="small" @change="(status: string) => handleUpdateLiteratureStatus(paper.id, status)">
                  <el-option label="鏈" value="unread" />
                  <el-option label="精读中" value="reading" />
                  <el-option label="宸茶" value="read" />
                  <el-option label="已引用" value="cited" />
                </el-select>
                <el-button size="small" @click="usePaperForTool(paper)">鐢ㄤ簬绮捐</el-button>
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
          <header><strong>{{ selectedTool?.label || '绉戠爺宸ュ叿' }}</strong><span>{{ selectedTool?.agent || 'ResearchToolAgent' }}</span></header>
          <el-form label-position="top" class="compact-form">
            <el-form-item label="杈撳叆鍐呭">
              <el-input v-model="toolForm.input_text" type="textarea" :rows="8" :placeholder="selectedTool?.placeholder || '绮樿创璁烘枃娈佃惤銆佸疄楠屾柟妗堛€佺患杩版彁绾叉垨寮曠敤淇℃伅'" />
            </el-form-item>
            <el-form-item label="琛ュ厖瑕佹眰">
              <el-input v-model="toolForm.extra_requirement" placeholder="例如：围绕我的研究方向，输出可直接用于课程论文的结构化结果" />
            </el-form-item>
            <el-button type="primary" :loading="runningTool" :disabled="!toolForm.input_text.trim()" @click="handleRunTool">
              杩愯绉戠爺宸ュ叿
            </el-button>
          </el-form>
        </article>

        <article class="panel-like workspace-panel">
          <header><strong>鏈€杩戠粨鏋?/strong><span>History</span></header>
          <div class="tool-run-list">
            <div v-for="run in visibleToolRuns" :key="run.id">
              <strong>{{ run.title }}</strong>
              <el-collapse>
                <el-collapse-item title="鏌ョ湅鐢熸垚缁撴灉" :name="String(run.id)">
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

    <el-drawer v-model="profileDrawerVisible" title="缂栬緫鐢诲儚鏉＄洰" size="420px">
      <el-form label-position="top" class="compact-form">
        <el-form-item label="鐢诲儚缁村害">
          <el-select v-model="profileEntryForm.key" filterable :disabled="Boolean(profileEntryForm.editingKey)">
            <el-option v-for="entry in profileEntryOptions" :key="entry.key" :label="entry.label" :value="entry.key" />
          </el-select>
        </el-form-item>
        <el-form-item label="鏉＄洰鍐呭">
          <el-input v-model="profileEntryForm.value" type="textarea" :rows="5" placeholder="例如：更适合图解 + 代码案例；薄弱点是矩阵运算和实验评价。" />
        </el-form-item>
        <el-form-item label="置信度">
          <el-slider v-model="profileEntryForm.confidence" :min="0" :max="100" />
        </el-form-item>
        <el-form-item label="鏄惁褰卞搷涓€у寲鎺ㄨ崘">
          <el-switch v-model="profileEntryForm.is_enabled" active-text="鍚敤" inactive-text="鍋滅敤" />
        </el-form-item>
        <el-form-item label="鏇存柊鍘熷洜">
          <el-input v-model="profileEntryForm.update_reason" />
        </el-form-item>
        <div class="drawer-actions">
          <el-button @click="profileDrawerVisible = false">鍙栨秷</el-button>
          <el-button type="primary" :loading="savingProfileEntry" @click="handleSaveProfileEntry">淇濆瓨鏉＄洰</el-button>
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
  askDatabase,
  createLiterature,
  deleteProfileEntry,
  getKnowledgeLinkGraph,
  getWorkspaceOverview,
  listKnowledgePoints,
  searchKnowledge,
  runResearchTool,
  updateLiterature,
  updateProfileEntry,
  type DatabaseAskResponse,
  type DatabaseCitation,
  type KnowledgePointRead,
  type KnowledgeLinkGraphResponse,
  type KnowledgeLinkNode,
  type KnowledgeSearchHit,
  type ProfileEntryRead,
  type LiteraturePaperRead,
  type WorkspaceOverviewResponse
} from '../services/apiClient'
import KnowledgeSphereGraph from '../components/KnowledgeSphereGraph.vue'

type Mode = 'profile' | 'resources' | 'literature' | 'writing' | 'methods'
type ToolType = 'polish' | 'format' | 'citation' | 'review' | 'method' | 'experiment' | 'reproduce' | 'topic' | 'defense' | 'paper_reading'

const props = defineProps<{ mode: Mode }>()
const router = useRouter()
const loading = ref(false)
const savingLiterature = ref(false)
const runningTool = ref(false)
const searchingKnowledge = ref(false)
const generatingRag = ref(false)
const savingProfileEntry = ref(false)
const overview = ref<WorkspaceOverviewResponse | null>(null)
const knowledgeQuery = ref('')
const ragQuestion = ref('')
const ragAnswer = ref('')
const ragResponse = ref<DatabaseAskResponse | null>(null)
const ragProjectId = ref<number | null>(null)
const ragKnowledgePoints = ref<string[]>([])
const knowledgeHits = ref<KnowledgeSearchHit[]>([])
const knowledgePoints = ref<KnowledgePointRead[]>([])
const knowledgeLinkGraph = ref<KnowledgeLinkGraphResponse | null>(null)
const selectedKnowledgeNode = ref<KnowledgeLinkNode | null>(null)
const loadingKnowledgeLinks = ref(false)
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
  update_reason: '鐢ㄦ埛鎵嬪姩缂栬緫鐢诲儚鏉＄洰'
})

const metaMap: Record<Mode, { eyebrow: string; title: string; description: string }> = {
  profile: { eyebrow: 'Profile', title: '学习画像', description: '沉淀学生近期学习行为、薄弱点、资源偏好和画像版本，用于后续个性化推荐。' },
  resources: { eyebrow: 'Knowledge Database', title: '数据库', description: '集中管理上传资料、学习笔记、课堂生成 PPT 和知识点关系，并提供基于资料库的 RAG 问答。' },
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
      {
        label: '画像完整度',
        value: `${enabledProfileEntries.value.length}/${profileEntryOptions.length}`,
        hint: '已启用画像维度'
      },
      {
        label: '画像条目',
        value: profileEntries.value.length,
        hint: '可人工修正'
      },
      {
        label: '平均置信度',
        value: `${profileConfidenceAverage.value}%`,
        hint: '低置信条目需复盘'
      },
      {
        label: '当前版本',
        value: `v${overview.value?.profile.current_revision || 0}`,
        hint: '学习记录驱动更新'
      }
    ]
  }
  if (props.mode === 'resources') {
    return [
      { label: '项目知识', value: data.projects || 0, hint: '图谱合并来源' },
      { label: '沉淀资源', value: data.resources || 0, hint: '课堂与笔记材料' },
      { label: '知识点', value: knowledgePoints.value.length, hint: '检索与出题索引' },
      { label: '命中片段', value: knowledgeHits.value.length, hint: '当前检索结果' }
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
const toolTitle = computed(() => props.mode === 'methods' ? '绉戠爺鏂规硶宸ュ叿' : '璁烘枃鍐欎綔宸ュ叿')
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
  { key: 'knowledge_base', label: '鐭ヨ瘑鍩虹' },
  { key: 'learning_goal', label: '瀛︿範鐩爣' },
  { key: 'cognitive_style', label: '璁ょ煡椋庢牸' },
  { key: 'weak_points', label: '易错点' },
  { key: 'practice_level', label: '瀹炶返鑳藉姏' },
  { key: 'resource_preference', label: '璧勬簮鍋忓ソ' },
  { key: 'learning_pace', label: '瀛︿範鑺傚' },
  { key: 'interest_direction', label: '鍏磋叮鏂瑰悜' },
  { key: 'current_research_direction', label: '褰撳墠绉戠爺鏂瑰悜' },
  { key: 'academic_writing', label: '瀛︽湳鍐欎綔鑳藉姏' },
  { key: 'literature_reading', label: '鏂囩尞闃呰鑳藉姏' },
  { key: 'coding_practice', label: '浠ｇ爜瀹炶返鑳藉姏' },
  { key: 'experiment_design', label: '瀹為獙璁捐鑳藉姏' }
]

onMounted(async () => {
  await Promise.all([loadOverview(), loadKnowledgePoints()])
  if (props.mode === 'resources') await loadKnowledgeLinks()
})
watch(() => props.mode, () => {
  toolForm.tool_type = props.mode === 'methods' ? 'experiment' : 'topic'
  if (props.mode === 'resources') void loadKnowledgeLinks()
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

async function loadKnowledgeLinks() {
  if (props.mode !== 'resources') return
  loadingKnowledgeLinks.value = true
  try {
    const { data } = await getKnowledgeLinkGraph({
      project_id: ragProjectId.value,
      query: knowledgeQuery.value.trim(),
      limit: 160
    })
    knowledgeLinkGraph.value = data
    if (selectedKnowledgeNode.value && !data.nodes.some((node) => node.id === selectedKnowledgeNode.value?.id)) {
      selectedKnowledgeNode.value = null
    }
  } finally {
    loadingKnowledgeLinks.value = false
  }
}

async function handleRagAsk() {
  generatingRag.value = true
  try {
    const { data } = await askDatabase({
      question: ragQuestion.value,
      project_id: ragProjectId.value,
      knowledge_points: ragKnowledgePoints.value,
      limit: 8
    })
    ragResponse.value = data
    ragAnswer.value = data.answer
    knowledgeHits.value = data.citations.map(citationToKnowledgeHit)
    await loadKnowledgeLinks()
  } finally {
    generatingRag.value = false
  }
}

function citationToKnowledgeHit(citation: DatabaseCitation): KnowledgeSearchHit {
  return {
    chunk_id: citation.id.startsWith('chunk:') ? Number(citation.id.replace('chunk:', '')) : null,
    document_title: citation.title,
    document_type: citation.document_type,
    knowledge_point: citation.knowledge_point,
    content: citation.content,
    source_uri: citation.source_uri,
    keywords: citation.knowledge_point ? [citation.knowledge_point] : [],
    page_no: citation.page_no,
    slide_no: citation.slide_no,
    section_title: citation.section_title,
    distance: citation.score,
    keyword_hit: null
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
  ElMessage.success('鏂囩尞闃呰鐘舵€佸凡鏇存柊')
  await loadOverview()
}

function usePaperForTool(paper: LiteraturePaperRead) {
  const draft = {
    tool_type: 'paper_reading' as ToolType,
    input_text: [
      `标题：${paper.title}`,
      `浣滆€咃細${paper.authors.join(', ')}`,
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
    confirmButtonText: '鍒犻櫎',
    cancelButtonText: '鍙栨秷',
    type: 'warning'
  })
  const { data } = await deleteProfileEntry(entry.key)
  if (overview.value) overview.value.profile = data
  ElMessage.success('画像条目已删除')
}

async function handleSearchKnowledge() {
  searchingKnowledge.value = true
  try {
    const { data } = await searchKnowledge(knowledgeQuery.value, 8)
    knowledgeHits.value = data
    await loadKnowledgeLinks()
  } finally {
    searchingKnowledge.value = false
  }
}

function searchByPoint(point: string) {
  knowledgeQuery.value = point
  void handleSearchKnowledge()
}

function selectKnowledgeNode(node: KnowledgeLinkNode | null) {
  selectedKnowledgeNode.value = node
  if (node?.layer === 'knowledge_base') {
    knowledgeQuery.value = node.label
  }
}

function locateCitation(citation: DatabaseCitation) {
  knowledgeQuery.value = citation.knowledge_point || citation.title
  const focused = citationToKnowledgeHit(citation)
  knowledgeHits.value = [
    focused,
    ...knowledgeHits.value.filter((hit) => hit.content !== focused.content)
  ].slice(0, 8)
  ElMessage.success('已定位到答案来源片段，可以在资料检索区继续复习。')
}

function renderCitationMeta(citation: DatabaseCitation) {
  return [
    citation.knowledge_point || citation.document_type,
    citation.section_title,
    citation.page_no ? `第 ${citation.page_no} 页` : '',
    citation.slide_no ? `第 ${citation.slide_no} 页` : ''
  ].filter(Boolean).join(' · ')
}

function openCitationReview(citation: DatabaseCitation) {
  locateCitation(citation)
  if (citation.review_url.startsWith('/api/classroom-resources/')) {
    window.open(citation.review_url, '_blank')
    return
  }
  ElMessage.info('知识库片段已在当前页面定位。')
}

async function handleRunTool() {
  runningTool.value = true
  try {
    const { data } = await runResearchTool({
      tool_type: toolForm.tool_type,
      input_text: toolForm.input_text,
      extra_requirement: toolForm.extra_requirement
    })
    ElMessage.success(`宸茬敓鎴愶細${data.title}`)
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
    unread: '鏈',
    reading: '精读中',
    read: '宸茶',
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
  const stage = value.stage || value.type || '绛旇京'
  const question = value.question || value.prompt || JSON.stringify(value)
  const followUp = value.follow_up || value.followup || value.follow_up_question
  return followUp ? `${stage}：${question} 追问：${followUp}` : `${stage}：${question}`
}

function formatDate(value: string) {
  return new Date(value).toLocaleString()
}
</script>
