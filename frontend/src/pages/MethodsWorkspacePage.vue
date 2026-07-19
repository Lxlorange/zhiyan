<template>
  <div class="methods-page workspace-module-page">
    <section class="methods-page-hero">
      <div class="methods-page-hero-copy">
        <p class="methods-eyebrow eyebrow">METHODS</p>
        <h1>科研工具箱</h1>
        <p>围绕选题、检索、问答、深度研究、写作和洞察提供 6 个轻工具入口，适合从灵感收敛到方案推进的完整路径。</p>
      </div>
      <el-button class="methods-ghost-btn" :loading="reloading" @click="reload">
        <el-icon><Refresh /></el-icon>
        刷新
      </el-button>
    </section>

    <section class="methods-guide-strip panel-like">
      <article>
        <strong>使用方式</strong>
        <p>先选择一个工具，再在详情页输入内容并执行操作，最后根据结果跳转到关联工具。</p>
      </article>
      <article>
        <strong>推荐流程</strong>
        <p>选题 -> 文献检索 -> 学术问答 -> 深度研究 -> 辅助写作 -> 前沿洞察，支持从想法到输出的连续推进。</p>
      </article>
      <article>
        <strong>页面说明</strong>
        <p>每个工具都保留了输入区、执行按钮和结果区，确保不仅能看，还能直接操作。</p>
      </article>
    </section>

    <section class="methods-toolbox-grid">
      <button
        v-for="tool in toolbox"
        :key="tool.key"
        type="button"
        class="methods-toolbox-card panel-like"
        @click="openTool(tool)"
      >
        <div class="methods-toolbox-head">
          <span class="methods-toolbox-badge">{{ tool.badge }}</span>
          <el-icon class="methods-toolbox-icon"><component :is="tool.icon" /></el-icon>
        </div>
        <strong>{{ tool.title }}</strong>
        <p>{{ tool.description }}</p>
        <span class="methods-toolbox-action">点击进入 · {{ tool.action }}</span>
      </button>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Aim, DocumentChecked, EditPen, Refresh, Search, TrendCharts } from '@element-plus/icons-vue'

const router = useRouter()
const reloading = ref(false)

const toolbox = [
  {
    key: 'topic',
    badge: '选题',
    title: 'AI选题',
    description: '收敛研究方向、问题定义与风险提示，帮助确定下一步切口。',
    action: '查看指引',
    icon: Aim,
    route: { name: 'research-tool-detail', params: { tool: 'topic' } },
  },
  {
    key: 'literature-search',
    badge: '文献',
    title: '文献检索',
    description: '输入论文标题后自动补全作者、来源和摘要信息。',
    action: '打开文献库',
    icon: Search,
    route: { name: 'research-tool-detail', params: { tool: 'literature-search' } },
  },
  {
    key: 'question-answer',
    badge: '问答',
    title: '学术问答',
    description: '围绕论文、方法和概念提供轻量问答与检索式提示。',
    action: '查看指引',
    icon: DocumentChecked,
    route: { name: 'research-tool-detail', params: { tool: 'question-answer' } },
  },
  {
    key: 'research',
    badge: '研究',
    title: '深度研究',
    description: '将一个研究问题拆分为调研、验证、整理和输出四步。',
    action: '查看指引',
    icon: TrendCharts,
    route: { name: 'research-tool-detail', params: { tool: 'research' } },
  },
  {
    key: 'writing',
    badge: '写作',
    title: '辅助写作',
    description: '整理提纲、段落顺序和论证关系，降低写作组织成本。',
    action: '查看指引',
    icon: EditPen,
    route: { name: 'research-tool-detail', params: { tool: 'writing' } },
  },
  {
    key: 'insight',
    badge: '分析',
    title: '前沿洞察',
    description: '快速提炼领域热点、机会点和风险提示，适合作为选题辅助。',
    action: '查看指引',
    icon: TrendCharts,
    route: { name: 'research-tool-detail', params: { tool: 'insight' } },
  },
] as const

function openTool(tool: (typeof toolbox)[number]) {
  void router.push(tool.route)
}

async function reload() {
  reloading.value = true
  try {
    ElMessage.success('工具箱已刷新')
  } finally {
    reloading.value = false
  }
}
</script>
