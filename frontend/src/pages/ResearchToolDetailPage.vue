<template>
  <div class="methods-page workspace-module-page research-tool-detail-page">
    <section class="methods-page-hero research-tool-detail-hero">
      <div class="methods-page-hero-copy">
        <p class="methods-eyebrow eyebrow">METHOD GUIDE</p>
        <h1>{{ current.title }}</h1>
        <p>{{ current.description }}</p>
      </div>
      <el-button class="methods-ghost-btn" @click="router.push({ name: 'methods' })">返回工具箱</el-button>
    </section>

    <template v-if="tool === 'topic'">
      <section class="topic-detail-grid topic-decision-grid">
        <article class="panel-like topic-hero-card topic-decision-card">
          <header><strong>选题雷达</strong><span>Decision</span></header>
          <div class="research-tool-inline-form">
            <el-input v-model="question" :placeholder="current.placeholder" />
            <div class="research-tool-action-row">
              <el-button type="primary" :loading="running" @click="askAgent">{{ current.actionLabel }}</el-button>
              <el-button @click="fillExample">填充示例</el-button>
            </div>
          </div>
          <div class="topic-decision-meta">
            <section>
              <small>方向</small>
              <strong>{{ current.title }}</strong>
            </section>
            <section>
              <small>动作</small>
              <strong>{{ current.actionLabel }}</strong>
            </section>
          </div>
          <ol class="topic-path-list">
            <li v-for="(item, i) in current.steps" :key="item">
              <span>{{ i + 1 }}</span>
              <p>{{ item }}</p>
            </li>
          </ol>
        </article>
        <article class="panel-like topic-focus-card topic-brief-card">
          <header><strong>可行切口</strong><span>Brief</span></header>
          <div class="topic-brief-highlight">
            <strong>{{ outputTitle }}</strong>
            <p>{{ outputText }}</p>
          </div>
          <div class="research-tool-result">
            <strong>建议清单</strong>
            <ul class="research-tool-result-list">
              <li v-for="item in outputBullets" :key="item">{{ item }}</li>
            </ul>
          </div>
        </article>
      </section>
    </template>

    <template v-else-if="tool === 'literature-search'">
      <section class="literature-detail-shell-grid">
        <article class="panel-like literature-input-rail">
          <header><strong>检索输入</strong><span>Search</span></header>
          <div class="literature-input-stack">
            <label>
              <span>论文标题</span>
              <el-input v-model="question" :placeholder="current.placeholder" />
            </label>
            <label>
              <span>补充提示</span>
              <el-input v-model="extraNote" type="textarea" :rows="4" placeholder="可补充研究方向、关键词或来源偏好" />
            </label>
          </div>
          <div class="research-tool-action-row">
            <el-button type="primary" :loading="running" @click="askAgent">自动抓取信息</el-button>
            <el-button @click="fillExample">填充示例</el-button>
          </div>
        </article>
        <article class="panel-like literature-output-canvas">
          <header><strong>抓取结果</strong><span>Metadata</span></header>
          <div class="literature-output-hero">
            <div class="research-tool-result">
              <strong>{{ outputTitle }}</strong>
              <p>{{ outputText }}</p>
            </div>
            <ul class="literature-output-grid">
              <li v-for="item in outputBullets" :key="item">{{ item }}</li>
            </ul>
          </div>
          <div class="research-tool-result">
            <strong>下一步建议</strong>
            <ul class="research-tool-result-list">
              <li v-for="item in nextActions" :key="item">{{ item }}</li>
            </ul>
          </div>
        </article>
      </section>
    </template>

    <template v-else-if="tool === 'question-answer'">
      <section class="qa-split-shell">
        <article class="panel-like qa-dialogue-panel">
          <header><strong>学术问答</strong><span>Dialogue</span></header>
          <div class="research-tool-inline-form">
            <el-input v-model="question" type="textarea" :rows="4" :placeholder="current.placeholder" />
            <el-input v-model="extraNote" placeholder="可补充关键词、论文名或希望追问的角度" />
            <div class="research-tool-action-row">
              <el-button type="primary" :loading="running" @click="askAgent">{{ current.actionLabel }}</el-button>
              <el-button @click="fillExample">填充示例</el-button>
            </div>
          </div>
          <div class="qa-bubbles">
            <div class="qa-user">
              <span>用户问题</span>
              <p>{{ question }}</p>
            </div>
            <div class="qa-assistant">
              <span>回答</span>
              <p>{{ outputText }}</p>
            </div>
          </div>
        </article>
        <article class="panel-like qa-question-panel">
          <header><strong>追问建议</strong><span>Next</span></header>
          <ul class="research-tool-result-list">
            <li v-for="item in outputBullets" :key="item">{{ item }}</li>
          </ul>
          <div class="research-tool-result">
            <strong>可继续追问</strong>
            <p>{{ nextActions.join(' · ') }}</p>
          </div>
        </article>
      </section>
    </template>

    <template v-else-if="tool === 'research'">
      <section class="research-roadmap-shell research-workflow-shell">
        <article class="panel-like roadmap-main-card research-stage-card">
          <header><strong>研究流程</strong><span>Workflow</span></header>
          <div class="research-tool-inline-form">
            <el-input v-model="question" type="textarea" :rows="4" :placeholder="current.placeholder" />
            <div class="research-tool-action-row">
              <el-button type="primary" :loading="running" @click="askAgent">{{ current.actionLabel }}</el-button>
              <el-button @click="fillExample">填充示例</el-button>
            </div>
          </div>
          <div class="research-stage-bar">
            <span v-for="(item, i) in current.steps" :key="item">{{ i + 1 }}</span>
          </div>
          <ol class="roadmap-list">
            <li v-for="(item, i) in current.steps" :key="item">
              <strong>{{ i + 1 }}</strong>
              <p>{{ item }}</p>
            </li>
          </ol>
        </article>
        <article class="panel-like roadmap-note-card research-output-card">
          <header><strong>阶段产出</strong><span>Output</span></header>
          <div class="research-tool-result">
            <strong>{{ outputTitle }}</strong>
            <p>{{ outputText }}</p>
          </div>
          <div class="research-tool-result research-tool-result-accent">
            <strong>研究提醒</strong>
            <p>这一步的目标是把研究问题转化为可执行的路线，而不是直接下结论。</p>
          </div>
          <div class="research-tool-result">
            <strong>后续动作</strong>
            <ul class="research-tool-result-list">
              <li v-for="item in nextActions" :key="item">{{ item }}</li>
            </ul>
          </div>
        </article>
      </section>
    </template>

    <template v-else-if="tool === 'writing'">
      <section class="writing-detail-shell writing-atelier-shell">
        <article class="panel-like writing-outline-card writing-atelier-card">
          <header><strong>写作骨架</strong><span>Outline</span></header>
          <div class="research-tool-inline-form">
            <el-input v-model="question" type="textarea" :rows="4" :placeholder="current.placeholder" />
            <div class="research-tool-action-row">
              <el-button type="primary" :loading="running" @click="askAgent">{{ current.actionLabel }}</el-button>
              <el-button @click="fillExample">填充示例</el-button>
            </div>
          </div>
          <div class="writing-outline-hero">
            <strong>{{ current.outputTitle }}</strong>
            <p>{{ current.outputText }}</p>
          </div>
          <ul class="writing-outline-list">
            <li v-for="item in current.steps" :key="item">{{ item }}</li>
          </ul>
        </article>
        <article class="panel-like writing-result-card writing-voice-card">
          <header><strong>写作建议</strong><span>Output</span></header>
          <div class="research-tool-result">
            <strong>{{ outputTitle }}</strong>
            <p>{{ outputText }}</p>
          </div>
          <div class="writing-chip-row">
            <span v-for="item in outputBullets" :key="item">{{ item }}</span>
          </div>
          <div class="research-tool-result">
            <strong>提纲要点</strong>
            <ul class="research-tool-result-list">
              <li v-for="item in outputBullets" :key="item">{{ item }}</li>
            </ul>
          </div>
        </article>
      </section>
    </template>

    <template v-else>
      <section class="insight-radar-shell">
        <article class="panel-like insight-radar-card">
          <header><strong>前沿洞察</strong><span>Radar</span></header>
          <div class="research-tool-inline-form">
            <el-input v-model="question" :placeholder="current.placeholder" />
            <div class="research-tool-action-row">
              <el-button type="primary" :loading="running" @click="askAgent">{{ current.actionLabel }}</el-button>
              <el-button @click="fillExample">填充示例</el-button>
            </div>
          </div>
          <div class="insight-radar-grid">
            <section v-for="item in current.steps" :key="item">
              <strong>{{ item }}</strong>
              <p>{{ outputText }}</p>
            </section>
          </div>
        </article>
        <article class="panel-like insight-action-card">
          <header><strong>行动建议</strong><span>Next</span></header>
          <ul class="research-tool-result-list">
            <li v-for="item in nextActions" :key="item">{{ item }}</li>
          </ul>
        </article>
      </section>
    </template>

    <section class="research-tool-link-grid">
      <article v-for="link in current.links" :key="link.label" class="panel-like research-tool-link-card">
        <strong>{{ link.label }}</strong>
        <p>{{ link.hint }}</p>
        <el-button size="small" type="primary" @click="router.push(link.to)">打开</el-button>
      </article>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter, type RouteLocationRaw } from 'vue-router'
import { ElMessage } from 'element-plus'
import { runResearchTool } from '../services/apiClient'

type ToolKey = 'topic' | 'literature-search' | 'question-answer' | 'research' | 'writing' | 'insight'
type ToolConfig = {
  title: string
  description: string
  placeholder: string
  example: string
  inputLabel: string
  actionLabel: string
  steps: string[]
  outputTitle: string
  outputText: string
  outputBullets: string[]
  links: { label: string; hint: string; to: RouteLocationRaw }[]
  toolType: 'topic' | 'experiment' | 'reproduce'
}

const router = useRouter()
const route = useRoute()
const running = ref(false)
const question = ref('')
const extraNote = ref('')
const outputTitle = ref('')
const outputText = ref('')
const outputBullets = ref<string[]>([])
const nextActions = ref<string[]>([])

const configs: Record<ToolKey, ToolConfig> = {
  topic: {
    title: 'AI选题',
    description: '收敛研究方向、问题定义与风险提示，帮助确定下一步切口。',
    placeholder: '例如：乡村旅游与地方产业振兴',
    example: '乡村旅游与地方产业振兴',
    inputLabel: '输入方向',
    actionLabel: '生成选题建议',
    steps: ['梳理方向', '收敛问题', '给出创新点', '提示风险'],
    outputTitle: '选题建议',
    outputText: '基于输入方向输出可执行的研究切口。',
    outputBullets: ['关注真实问题', '检查数据可得性', '预估研究难度', '确认创新点'],
    links: [
      { label: '文献检索', hint: '先查看参考论文和来源', to: { name: 'research-tool-detail', params: { tool: 'literature-search' } } },
      { label: '前沿洞察', hint: '查看热点方向和机会点', to: { name: 'research-tool-detail', params: { tool: 'insight' } } },
    ],
    toolType: 'topic',
  },
  'literature-search': {
    title: '文献检索',
    description: '输入论文标题，自动补全作者、来源和摘要信息。',
    placeholder: '例如：乡村振兴背景下的旅游发展路径',
    example: '乡村振兴背景下的旅游发展路径',
    inputLabel: '输入论文标题',
    actionLabel: '自动抓取信息',
    steps: ['输入标题', '检索来源', '补全作者', '提取摘要'],
    outputTitle: '文献信息',
    outputText: '用于快速补全论文元数据并保存到知识库。',
    outputBullets: ['作者', '来源', '年份', '摘要'],
    links: [
      { label: '学术问答', hint: '围绕论文继续提问', to: { name: 'research-tool-detail', params: { tool: 'question-answer' } } },
      { label: '辅助写作', hint: '将文献转为写作素材', to: { name: 'research-tool-detail', params: { tool: 'writing' } } },
    ],
    toolType: 'topic',
  },
  'question-answer': {
    title: '学术问答',
    description: '围绕论文、方法和概念提供轻量问答与检索式提示。',
    placeholder: '例如：什么是研究假设检验？',
    example: '什么是研究假设检验？',
    inputLabel: '输入学术问题',
    actionLabel: '生成问答',
    steps: ['识别问题', '补充背景', '给出答案', '建议延伸阅读'],
    outputTitle: '学术问答',
    outputText: '给出简明回答和可继续追问的方向。',
    outputBullets: ['概念解释', '关键步骤', '常见误区', '延伸问题'],
    links: [
      { label: '文献检索', hint: '寻找支撑论文', to: { name: 'research-tool-detail', params: { tool: 'literature-search' } } },
      { label: '前沿洞察', hint: '查看领域位置', to: { name: 'research-tool-detail', params: { tool: 'insight' } } },
    ],
    toolType: 'reproduce',
  },
  research: {
    title: '深度研究',
    description: '将研究问题拆分为调研、验证、整理和输出四个阶段。',
    placeholder: '例如：研究乡村旅游与地方产业振兴的关系',
    example: '研究乡村旅游与地方产业振兴的关系',
    inputLabel: '输入研究问题',
    actionLabel: '生成研究路线',
    steps: ['调研背景', '确认变量', '设计验证', '整理输出'],
    outputTitle: '深度研究路线',
    outputText: '把问题拆成可跟踪的研究任务。',
    outputBullets: ['背景调研', '证据收集', '验证方案', '结果整理'],
    links: [
      { label: 'AI选题', hint: '回到问题定义', to: { name: 'research-tool-detail', params: { tool: 'topic' } } },
      { label: '辅助写作', hint: '转为写作提纲', to: { name: 'research-tool-detail', params: { tool: 'writing' } } },
    ],
    toolType: 'topic',
  },
  writing: {
    title: '辅助写作',
    description: '整理提纲、段落顺序和论证关系，降低写作组织成本。',
    placeholder: '例如：帮我整理一段论文引言提纲',
    example: '帮我整理一段论文引言提纲',
    inputLabel: '输入写作需求',
    actionLabel: '生成提纲',
    steps: ['明确观点', '分段组织', '补充论据', '收束结论'],
    outputTitle: '写作提纲',
    outputText: '为论文、报告或综述提供结构草案。',
    outputBullets: ['标题', '段落顺序', '论据提示', '结论收束'],
    links: [
      { label: '文献检索', hint: '先整理参考素材', to: { name: 'research-tool-detail', params: { tool: 'literature-search' } } },
      { label: '前沿洞察', hint: '补充最新方向', to: { name: 'research-tool-detail', params: { tool: 'insight' } } },
    ],
    toolType: 'topic',
  },
  insight: {
    title: '前沿洞察',
    description: '快速提炼领域热点、机会点和风险提示，适合作为选题辅助。',
    placeholder: '例如：乡村旅游领域最近的研究热点',
    example: '乡村旅游领域最近的研究热点',
    inputLabel: '输入领域方向',
    actionLabel: '生成洞察',
    steps: ['识别热点', '提炼机会', '提示风险', '推荐下一步'],
    outputTitle: '前沿洞察',
    outputText: '为选题和研究路线提供方向感。',
    outputBullets: ['热点', '机会', '风险', '可行动作'],
    links: [
      { label: 'AI选题', hint: '把洞察转成选题', to: { name: 'research-tool-detail', params: { tool: 'topic' } } },
      { label: '文献检索', hint: '补充证据来源', to: { name: 'research-tool-detail', params: { tool: 'literature-search' } } },
    ],
    toolType: 'topic',
  },
}

const tool = computed(() => String(route.params.tool || 'topic') as ToolKey)
const current = computed(() => configs[tool.value] || configs.topic)

watch(
  current,
  () => {
    question.value = current.value.example
    extraNote.value = ''
    outputTitle.value = current.value.outputTitle
    outputText.value = current.value.outputText
    outputBullets.value = [...current.value.outputBullets]
    nextActions.value = current.value.links.map((i) => i.label)
  },
  { immediate: true },
)

async function askAgent() {
  const value = question.value.trim()
  if (!value) {
    ElMessage.warning('请输入内容')
    return
  }
  running.value = true
  try {
    const { data } = await runResearchTool({
      tool_type: current.value.toolType,
      input_text: extraNote.value.trim() ? `${value}\n${extraNote.value.trim()}` : value,
      extra_requirement: current.value.description,
    })
    const output = data.output_data || {}
    outputTitle.value = output.title || current.value.outputTitle
    outputText.value = output.final_topic || output.revised_text || output.summary || current.value.outputText
    outputBullets.value = Array.isArray(output.plan_chain) && output.plan_chain.length ? output.plan_chain : current.value.outputBullets
    nextActions.value = Array.isArray(output.next_actions) && output.next_actions.length ? output.next_actions : current.value.links.map((i) => i.label)
  } finally {
    running.value = false
  }
}

function fillExample() {
  question.value = current.value.example
  extraNote.value = ''
}
</script>
