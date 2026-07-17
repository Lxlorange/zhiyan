<template>
  <div class="page workspace-module-page">
    <section class="workspace-hero">
      <div>
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
        <article class="panel-like workspace-panel wide workspace-insight-strip">
          <div>
            <span>画像完整度</span>
            <strong>{{ enabledProfileEntries.length }} / {{ profileEntryOptions.length }}</strong>
            <small>启用条目会参与推荐、出题和资源生成。</small>
          </div>
          <div>
            <span>平均置信度</span>
            <strong>{{ profileConfidenceAverage }}%</strong>
            <small>低置信度条目建议人工确认或重新描述。</small>
          </div>
          <div>
            <span>当前版本</span>
            <strong>Revision {{ overview?.profile.current_revision || 0 }}</strong>
            <small>每次手动或对话更新都会形成记录。</small>
          </div>
        </article>
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
        <article class="panel-like workspace-panel wide workspace-insight-strip">
          <div v-for="card in databaseHealthCards" :key="card.label">
            <span>{{ card.label }}</span>
            <strong>{{ card.value }}</strong>
            <small>{{ card.hint }}</small>
          </div>
        </article>
        <article class="panel-like workspace-panel">
          <header><strong>资料上传与数据库沉淀</strong><span>Knowledge Deposit</span></header>
          <div class="deposit-summary">
            <div>
              <strong>{{ overview?.resources.length || 0 }}</strong>
              <span>生成资源</span>
            </div>
            <div>
              <strong>{{ overview?.literature.length || 0 }}</strong>
              <span>文献笔记</span>
            </div>
            <div>
              <strong>{{ knowledgePoints.length }}</strong>
              <span>知识点</span>
            </div>
          </div>
          <el-upload
            class="deposit-upload"
            drag
            :auto-upload="false"
            :show-file-list="false"
            :on-change="handleKnowledgeUpload"
          >
            <strong>上传课程资料 / 论文 / 笔记</strong>
            <small>资料会进入知识库，后续用于 RAG 问答、知识图谱和题目生成。</small>
          </el-upload>
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

        <article class="panel-like workspace-panel knowledge-graph-panel">
          <header><strong>3D 知识图谱</strong><span>{{ knowledgeGraphNodes.length }} nodes</span></header>
          <div class="knowledge-graph-stage">
            <button
              v-for="node in knowledgeGraphNodes"
              :key="node.id"
              type="button"
              class="knowledge-node"
              :style="node.style"
              @click="searchByPoint(node.name)"
            >
              <strong>{{ node.name }}</strong>
              <span>{{ node.chapter }}</span>
            </button>
            <i
              v-for="edge in knowledgeGraphEdges"
              :key="edge.id"
              class="knowledge-edge"
              :style="edge.style"
            />
          </div>
          <small class="graph-hint">节点按章节和先修关系组织，点击节点可联动检索资料片段。</small>
        </article>

        <article class="panel-like workspace-panel">
          <header><strong>数据库 RAG 问答</strong><span>Retrieval QA</span></header>
          <div class="rag-scope-row">
            <el-select v-model="ragProjectId" clearable placeholder="全部项目资料">
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
            placeholder="围绕已上传资料、课堂 PPT、笔记或知识点提问，例如：召回率为什么比准确率更适合跌倒检测？"
          />
          <div class="classroom-action-row">
            <el-button type="primary" :loading="generatingRag" :disabled="!ragQuestion.trim()" @click="handleRagAsk">
              基于数据库回答
            </el-button>
          </div>
          <div v-if="ragAnswer" class="rag-answer">
            <strong>回答</strong>
            <p>{{ ragAnswer }}</p>
            <div v-if="ragResponse?.related_points.length" class="rag-tags">
              <el-tag v-for="point in ragResponse.related_points" :key="point" size="small" @click="searchByPoint(point)">
                {{ point }}
              </el-tag>
            </div>
            <small>
              {{ ragResponse?.used_llm ? '由后端 RAG 结合大模型生成' : '由后端 RAG 检索结果生成' }}
              · 置信度 {{ ragResponse?.confidence || 'medium' }}
            </small>
            <div v-if="ragResponse?.citations.length" class="citation-list">
              <div v-for="(citation, index) in ragResponse.citations" :key="citation.id" class="citation-card">
                <span>来源 {{ index + 1 }} · {{ citation.source_type }}</span>
                <strong>{{ citation.title }}</strong>
                <p>{{ citation.content }}</p>
                <small>{{ citation.knowledge_point || citation.document_type }} {{ citation.section_title ? `· ${citation.section_title}` : '' }} {{ citation.page_no ? `· 第 ${citation.page_no} 页` : '' }} {{ citation.slide_no ? `· 第 ${citation.slide_no} 页` : '' }}</small>
                <div class="citation-actions">
                  <el-button size="small" @click="locateCitation(citation)">定位片段</el-button>
                  <el-button v-if="citation.review_url" size="small" @click="openCitationReview(citation)">回看材料</el-button>
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
          <header><strong>沉淀内容</strong><span>{{ overview?.resources.length || 0 }} items</span></header>
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
              <span>{{ point.chapter }} · {{ point.difficulty }}</span>
              <small>{{ point.description }}</small>
            </button>
          </div>
        </article>
      </section>

      <section v-else-if="mode === 'assessment'" class="workspace-grid two">
        <article class="panel-like workspace-panel wide workspace-insight-strip">
          <div>
            <span>薄弱点候选</span>
            <strong>{{ weakPointOptions.length }}</strong>
            <small>来自画像条目和知识库知识点。</small>
          </div>
          <div>
            <span>已选薄弱点</span>
            <strong>{{ selectedWeakPoints.length }}</strong>
            <small>每个薄弱点会按题型生成练习。</small>
          </div>
          <div>
            <span>资料范围</span>
            <strong>{{ exerciseProjectId ? '项目内' : '全部' }}</strong>
            <small>可限定项目资料，减少题目跑偏。</small>
          </div>
        </article>
        <article class="panel-like workspace-panel">
          <header><strong>选择薄弱点</strong><span>Weak Points</span></header>
          <div class="exercise-control-grid">
            <el-select v-model="exerciseProjectId" clearable placeholder="全部项目资料">
              <el-option
                v-for="project in overview?.projects || []"
                :key="project.id"
                :label="project.title"
                :value="project.id"
              />
            </el-select>
            <el-segmented
              v-model="exerciseDifficulty"
              :options="[
                { label: '基础', value: 'easy' },
                { label: '适中', value: 'medium' },
                { label: '进阶', value: 'hard' }
              ]"
            />
            <el-input-number v-model="exerciseCountPerPoint" :min="1" :max="3" controls-position="right" />
          </div>
          <el-checkbox-group v-model="selectedWeakPoints" class="weak-point-picker">
            <el-checkbox-button v-for="point in weakPointOptions" :key="point" :label="point" />
          </el-checkbox-group>
          <header class="sub-header"><strong>题型</strong><span>Question Types</span></header>
          <el-checkbox-group v-model="selectedQuestionTypes" class="question-type-picker">
            <el-checkbox label="choice">选择题</el-checkbox>
            <el-checkbox label="judgement">判断题</el-checkbox>
            <el-checkbox label="short">简答题</el-checkbox>
          </el-checkbox-group>
          <div class="classroom-action-row">
            <el-button type="primary" :loading="generatingExercises" :disabled="!selectedWeakPoints.length" @click="handleGenerateExercises">
              智能生成练习题
            </el-button>
          </div>
        </article>
        <article class="panel-like workspace-panel">
          <header><strong>生成结果</strong><span>{{ generatedQuestions.length }} questions</span></header>
          <div v-if="exerciseSourceSummary" class="exercise-source-summary">
            <span>{{ exerciseUsedLlm ? '模型生成' : '规则生成' }}</span>
            <p>{{ exerciseSourceSummary }}</p>
          </div>
          <div class="exercise-list">
            <div v-for="question in generatedQuestions" :key="question.id">
              <div class="exercise-card-head">
                <el-tag size="small">{{ questionTypeLabel(question.type) }}</el-tag>
                <span>{{ question.difficulty }}</span>
              </div>
              <strong>{{ question.prompt }}</strong>
              <ol v-if="question.options?.length">
                <li v-for="option in question.options" :key="option">{{ option }}</li>
              </ol>
              <small>关联薄弱点：{{ question.point }} · 参考答案：{{ question.answer }}</small>
              <p v-if="question.explanation" class="exercise-explanation">{{ question.explanation }}</p>
              <small v-if="question.source_title" class="exercise-source">依据：{{ question.source_title }} {{ question.source_excerpt ? `· ${question.source_excerpt}` : '' }}</small>
            </div>
          </div>
          <el-empty v-if="!generatedQuestions.length" description="请选择薄弱点和题型后生成针对性练习。" />
        </article>
        <article class="panel-like workspace-panel">
          <header><strong>最近练习证据</strong><span>Evidence</span></header>
          <div class="workspace-list">
            <p v-for="item in assessmentSuggestions" :key="item">{{ item }}</p>
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
  askDatabase,
  createLiterature,
  generatePracticeQuestions,
  getWorkspaceOverview,
  importKnowledgePackage,
  listKnowledgePoints,
  searchKnowledge,
  runResearchTool,
  updateLiterature,
  updateProfileEntry,
  updateProfileByDialogue,
  type DatabaseAskResponse,
  type DatabaseCitation,
  type KnowledgePointRead,
  type KnowledgeSearchHit,
  type PracticeQuestionRead,
  type ProfileEntryRead,
  type LiteraturePaperRead,
  type WorkspaceOverviewResponse
} from '../services/apiClient'

type Mode = 'profile' | 'resources' | 'assessment' | 'literature' | 'writing' | 'methods'
type ToolType = 'polish' | 'format' | 'citation' | 'review' | 'method' | 'experiment' | 'reproduce' | 'topic' | 'defense' | 'paper_reading'
type GeneratedQuestion = PracticeQuestionRead

const props = defineProps<{ mode: Mode }>()
const router = useRouter()
const loading = ref(false)
const savingLiterature = ref(false)
const runningTool = ref(false)
const updatingProfile = ref(false)
const searchingKnowledge = ref(false)
const generatingRag = ref(false)
const generatingExercises = ref(false)
const savingProfileEntry = ref(false)
const overview = ref<WorkspaceOverviewResponse | null>(null)
const profileMessage = ref('')
const knowledgeQuery = ref('')
const ragQuestion = ref('')
const ragAnswer = ref('')
const ragResponse = ref<DatabaseAskResponse | null>(null)
const ragProjectId = ref<number | null>(null)
const ragKnowledgePoints = ref<string[]>([])
const knowledgeHits = ref<KnowledgeSearchHit[]>([])
const knowledgePoints = ref<KnowledgePointRead[]>([])
const profileDrawerVisible = ref(false)
const selectedWeakPoints = ref<string[]>([])
const selectedQuestionTypes = ref(['choice', 'judgement'])
const generatedQuestions = ref<GeneratedQuestion[]>([])
const exerciseProjectId = ref<number | null>(null)
const exerciseDifficulty = ref<'easy' | 'medium' | 'hard'>('medium')
const exerciseCountPerPoint = ref(1)
const exerciseSourceSummary = ref('')
const exerciseUsedLlm = ref(false)
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
  profile: { eyebrow: 'Profile', title: '学习画像', description: '沉淀学生近期学习行为、薄弱点、资源偏好和画像版本，用于后续个性化推荐。' },
  resources: { eyebrow: 'Knowledge Database', title: '数据库', description: '集中管理上传资料、学习笔记、课堂生成 PPT 和知识点关系，并提供基于资料库的 RAG 问答。' },
  assessment: { eyebrow: 'Exercise Generator', title: '练习题目生成', description: '根据学习画像中的薄弱点生成选择题、判断题和简答题，形成针对性训练。' },
  literature: { eyebrow: 'Literature', title: '文献知识库', description: '保存论文、资料、摘要、引用文本和阅读状态。' },
  writing: { eyebrow: 'Writing', title: '论文写作', description: '提供选题凝练、综述写作、论文润色、引用规范和模拟答辩。' },
  methods: { eyebrow: 'Methods', title: '科研方法', description: '围绕实验设计、论文复现、评估指标和学术规范生成学习建议。' }
}
const currentMeta = computed(() => metaMap[props.mode])
const metrics = computed(() => {
  const data = overview.value?.metrics || {}
  return [
    { label: '项目', value: data.projects || 0 },
    { label: '沉淀资源', value: data.resources || 0 },
    { label: '智能体记录', value: data.agent_tasks || 0 },
    { label: '练习证据', value: data.submissions || 0 },
    { label: '文献', value: data.literature || 0 }
  ]
})
const profileEntries = computed(() => overview.value?.profile.entries || [])
const enabledProfileEntries = computed(() => profileEntries.value.filter((entry) => entry.is_enabled))
const profileConfidenceAverage = computed(() => {
  if (!profileEntries.value.length) return 0
  const total = profileEntries.value.reduce((sum, entry) => sum + Number(entry.confidence || 0), 0)
  return Math.round(total / profileEntries.value.length)
})
const databaseHealthCards = computed(() => [
  { label: '课堂资源', value: overview.value?.resources.length || 0, hint: '可用于回看和问答' },
  { label: '文献笔记', value: overview.value?.literature.length || 0, hint: '支撑科研写作' },
  { label: '知识点', value: knowledgePoints.value.length, hint: '驱动检索和出题' },
  { label: '命中片段', value: knowledgeHits.value.length, hint: '当前检索结果' }
])
const weakPointOptions = computed(() => {
  const entry = profileEntries.value.find((item) => item.key === 'weak_points')
  const raw = entry?.value
  const values = Array.isArray(raw) ? raw : String(raw || '').split(/[、,，/]/)
  const fallback = knowledgePoints.value.slice(0, 6).map((item) => item.name)
  return Array.from(new Set([...values, ...fallback].map((item) => String(item).trim()).filter(Boolean))).slice(0, 10)
})
const knowledgeGraphNodes = computed(() => {
  const points = knowledgePoints.value.slice(0, 12)
  const radiusX = 38
  const radiusY = 30
  return points.map((point, index) => {
    const angle = (index / Math.max(1, points.length)) * Math.PI * 2
    const depth = Math.sin(angle)
    const x = 50 + Math.cos(angle) * radiusX
    const y = 50 + Math.sin(angle) * radiusY
    const scale = 0.86 + (depth + 1) * 0.12
    return {
      id: point.id,
      name: point.name,
      chapter: point.chapter,
      style: {
        left: `${x}%`,
        top: `${y}%`,
        transform: `translate(-50%, -50%) scale(${scale}) translateZ(${Math.round(depth * 42)}px)`,
        zIndex: String(20 + Math.round(depth * 10))
      }
    }
  })
})
const knowledgeGraphEdges = computed(() => {
  const nodes = knowledgeGraphNodes.value
  return nodes.slice(0, Math.max(0, nodes.length - 1)).map((node, index) => {
    const next = nodes[index + 1]
    const x1 = Number(String(node.style.left).replace('%', ''))
    const y1 = Number(String(node.style.top).replace('%', ''))
    const x2 = Number(String(next.style.left).replace('%', ''))
    const y2 = Number(String(next.style.top).replace('%', ''))
    const length = Math.hypot(x2 - x1, y2 - y1)
    const angle = Math.atan2(y2 - y1, x2 - x1) * 180 / Math.PI
    return {
      id: `${node.id}-${next.id}`,
      style: {
        left: `${x1}%`,
        top: `${y1}%`,
        width: `${length}%`,
        transform: `rotate(${angle}deg)`
      }
    }
  })
})
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
    if (!selectedWeakPoints.value.length) selectedWeakPoints.value = weakPointOptions.value.slice(0, 2)
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

async function handleKnowledgeUpload(uploadFile: any) {
  const raw = uploadFile?.raw as File | undefined
  if (!raw) return
  try {
    await importKnowledgePackage(raw, {
      course_code: 'USER-DEPOSIT',
      course_title: '用户资料沉淀库',
      use_ocr: true,
      rebuild_course: false
    })
    ElMessage.success('资料已提交解析，解析完成后会进入数据库沉淀。')
    await loadOverview()
  } catch {
    ElMessage.warning('资料上传未完成，请检查后端模型 Key 或文件格式后重试。')
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

async function handleGenerateExercises() {
  if (!selectedWeakPoints.value.length) return
  generatingExercises.value = true
  try {
    const { data } = await generatePracticeQuestions({
      weak_points: selectedWeakPoints.value,
      question_types: selectedQuestionTypes.value.length ? selectedQuestionTypes.value : ['choice'],
      project_id: exerciseProjectId.value,
      difficulty: exerciseDifficulty.value,
      count_per_point: exerciseCountPerPoint.value
    })
    generatedQuestions.value = data.questions
    exerciseSourceSummary.value = data.source_summary
    exerciseUsedLlm.value = data.used_llm
    ElMessage.success(data.used_llm ? '练习题已结合画像和资料库生成' : '已生成基础练习题，可配置 QWEN_API_KEY 启用模型生成')
  } finally {
    generatingExercises.value = false
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

function locateCitation(citation: DatabaseCitation) {
  knowledgeQuery.value = citation.knowledge_point || citation.title
  const focused = citationToKnowledgeHit(citation)
  knowledgeHits.value = [
    focused,
    ...knowledgeHits.value.filter((hit) => hit.content !== focused.content)
  ].slice(0, 8)
  ElMessage.success('已定位到答案来源片段，可以在资料检索区继续复习。')
}

function openCitationReview(citation: DatabaseCitation) {
  locateCitation(citation)
  if (citation.review_url.startsWith('/api/classroom-resources/')) {
    window.open(citation.review_url, '_blank')
    return
  }
  ElMessage.info('知识库片段已在当前页面定位。')
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

function questionTypeLabel(type: string) {
  const labels: Record<string, string> = {
    choice: '选择题',
    judgement: '判断题',
    short: '简答题'
  }
  return labels[type] || type
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
