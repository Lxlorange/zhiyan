<template>
  <div class="methods-page workspace-module-page research-tool-detail-page">
    <section class="methods-page-hero research-tool-detail-hero">
      <div class="methods-page-hero-copy">
        <p class="methods-eyebrow eyebrow">METHOD DETAIL</p>
        <h1>{{ current.title }}</h1>
        <p>{{ current.description }}</p>
      </div>
      <el-button class="methods-ghost-btn" @click="router.push({ name: 'methods' })">返回工具箱</el-button>
    </section>

    <section v-if="key === 'topic'" class="research-tool-layout research-tool-layout-topic">
      <article class="panel-like research-tool-card">
        <header><strong>问题拆解</strong><span>Roadmap</span></header>
        <div class="roadmap-list">
          <div v-for="step in roadmap" :key="step.title" class="roadmap-item">
            <strong>{{ step.title }}</strong>
            <p>{{ step.desc }}</p>
          </div>
        </div>
      </article>
      <aside class="panel-like research-tool-card research-tool-assistant">
        <header><strong>Agent 建议</strong><span>Next step</span></header>
        <el-input v-model="question" type="textarea" :rows="4" placeholder="告诉我你的研究方向，我来帮你收敛选题" />
        <div class="research-tool-action-row">
          <el-button type="primary" :loading="running" @click="askAgent">生成建议</el-button>
          <el-button @click="fillExample">填充示例</el-button>
        </div>
        <div class="research-tool-answer">
          <strong>{{ answerTitle }}</strong>
          <p>{{ answerText }}</p>
        </div>
      </aside>
    </section>

    <section v-else-if="key === 'experiment'" class="research-tool-layout research-tool-layout-experiment">
      <article class="panel-like research-tool-card">
        <header><strong>实验矩阵</strong><span>Matrix</span></header>
        <div class="experiment-matrix">
          <div class="matrix-head">变量</div>
          <div class="matrix-head">控制方式</div>
          <div class="matrix-head">指标</div>
          <div v-for="row in experimentMatrix" :key="row.variable" class="matrix-row">
            <strong>{{ row.variable }}</strong>
            <span>{{ row.control }}</span>
            <span>{{ row.metric }}</span>
          </div>
        </div>
      </article>
      <aside class="panel-like research-tool-card research-tool-assistant">
        <header><strong>Agent 建议</strong><span>Plan</span></header>
        <el-input v-model="question" type="textarea" :rows="4" placeholder="输入实验问题，生成下一步操作建议" />
        <div class="research-tool-action-row">
          <el-button type="primary" :loading="running" @click="askAgent">生成建议</el-button>
          <el-button @click="fillExample">填充示例</el-button>
        </div>
        <ul class="research-tool-result-list">
          <li v-for="item in answerBullets" :key="item">{{ item }}</li>
        </ul>
      </aside>
    </section>

    <section v-else class="research-tool-layout research-tool-layout-reproduce">
      <article class="panel-like research-tool-card">
        <header><strong>复现时间线</strong><span>Timeline</span></header>
        <ol class="timeline-list">
          <li v-for="step in timeline" :key="step">{{ step }}</li>
        </ol>
      </article>
      <aside class="panel-like research-tool-card research-tool-assistant">
        <header><strong>Agent 建议</strong><span>Checklist</span></header>
        <el-input v-model="question" type="textarea" :rows="4" placeholder="输入论文名或方法名，得到复现清单" />
        <div class="research-tool-action-row">
          <el-button type="primary" :loading="running" @click="askAgent">生成建议</el-button>
          <el-button @click="fillExample">填充示例</el-button>
        </div>
        <div class="research-tool-answer">
          <strong>{{ answerTitle }}</strong>
          <p>{{ answerText }}</p>
        </div>
      </aside>
    </section>

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
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { runResearchTool } from '../services/apiClient'

const router = useRouter()
const route = useRoute()
const running = ref(false)
const question = ref('')
const answerTitle = ref('等待建议')
const answerText = ref('输入问题后，系统会给出下一步动作。')
const answerBullets = ref<string[]>([])

const configs = {
  topic: {
    title: '选题规划',
    description: '把方向收敛成问题、创新点和风险清单。',
    example: '乡村旅游与地方产业振兴',
    assistantPrompt: '帮我把这个研究方向收敛成3个可执行选题，并给出创新点和风险提醒。',
    roadmap: [
      { title: '方向收敛', desc: '先把宽方向缩成一个明确问题。' },
      { title: '创新判断', desc: '检查是否有可展示的差异化贡献。' },
      { title: '风险确认', desc: '看看数据、时间和实现难度。' }
    ],
    links: [
      { label: '打开文献知识库', hint: '找参考论文', to: { name: 'literature' } },
      { label: '打开练习试卷', hint: '用题目辅助收敛方向', to: { name: 'assessment' } }
    ]
  },
  experiment: {
    title: '实验设计',
    description: '整理变量、对照组和指标，生成可执行计划。',
    example: '设计一个用户满意度实验',
    assistantPrompt: '请给我一个包含变量、对照组、评价指标和流程的实验设计建议。',
    experimentMatrix: [
      { variable: '自变量', control: '控制实验条件', metric: '结果变化' },
      { variable: '因变量', control: '统一采集方式', metric: '满意度/准确率' },
      { variable: '控制变量', control: '保持环境一致', metric: '干扰最小化' }
    ],
    links: [
      { label: '打开知识上传', hint: '把材料整理进知识库', to: { name: 'knowledge-upload' } },
      { label: '打开文献知识库', hint: '先看类似实验', to: { name: 'literature' } }
    ]
  },
  reproduce: {
    title: '论文复现',
    description: '拆解路径、验证步骤和代码入口。',
    example: '基于Transformer的文本分类复现',
    assistantPrompt: '请输出这个论文的复现步骤、优先查看的模块和验证清单。',
    timeline: ['准备数据', '定位代码入口', '确认参数', '跑通基线', '核对结果'],
    links: [
      { label: '打开文献知识库', hint: '确认原论文信息', to: { name: 'literature' } },
      { label: '打开练习试卷', hint: '用试卷帮助拆解步骤', to: { name: 'assessment' } }
    ]
  }
} as const

const key = computed(() => String(route.params.tool || 'topic') as keyof typeof configs)
const current = computed(() => configs[key.value] || configs.topic)

const roadmap = computed(() => (current.value as { roadmap?: Array<{ title: string; desc: string }> }).roadmap || [])
const experimentMatrix = computed(() => (current.value as { experimentMatrix?: Array<{ variable: string; control: string; metric: string }> }).experimentMatrix || [])
const timeline = computed(() => (current.value as { timeline?: string[] }).timeline || [])

watch(
  current,
  () => {
    question.value = current.value.example
    answerTitle.value = '等待建议'
    answerText.value = '输入问题后，系统会给出下一步动作。'
    answerBullets.value = []
  },
  { immediate: true }
)

async function askAgent() {
  const value = question.value.trim()
  if (!value) {
    ElMessage.warning('请输入内容')
    return
  }
  running.value = true
  try {
    await runResearchTool({
      tool_type: key.value === 'experiment' ? 'experiment' : key.value === 'reproduce' ? 'reproduce' : 'topic',
      input_text: value,
      extra_requirement: current.value.assistantPrompt
    })
    answerTitle.value = '下一步建议'
    answerText.value = current.value.assistantPrompt
    answerBullets.value = [
      '先整理输入内容',
      '再选择一个可执行方向',
      '最后用右侧跳转页继续推进'
    ]
  } finally {
    running.value = false
  }
}

function fillExample() {
  question.value = current.value.example
}
</script>
