<template>
  <div class="methods-page workspace-module-page">
    <section class="methods-page-hero">
      <div class="methods-page-hero-copy">
        <p class="methods-eyebrow eyebrow">METHODS</p>
        <h1>科研工具箱</h1>
        <p>每个工具都可以点进去直接使用，优先复用已有页面，不够的再补通用详情页。</p>
      </div>
      <el-button class="methods-ghost-btn" :loading="reloading" @click="reload">
        <el-icon><Refresh /></el-icon>
        刷新数据
      </el-button>
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
        <span class="methods-toolbox-action">点击使用 · {{ tool.action }}</span>
      </button>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Aim, ArrowRight, Collection, DocumentChecked, Refresh, Search, TrendCharts } from '@element-plus/icons-vue'

type ToolKey = 'literature' | 'topic' | 'experiment' | 'reproduce' | 'assessment' | 'knowledge'

const router = useRouter()
const reloading = ref(false)

const toolbox = [
  {
    key: 'literature' as ToolKey,
    badge: '文献',
    title: '文献知识库',
    description: '输入论文标题后自动抓取作者、来源和摘要，直接保存到文献库。',
    action: '打开文献页',
    icon: Collection,
    route: { name: 'literature' }
  },
  {
    key: 'topic' as ToolKey,
    badge: '选题',
    title: '选题规划',
    description: '把研究方向收敛成清晰的问题、创新点和风险清单。',
    action: '进入方法详情',
    icon: Aim,
    route: { name: 'research-tool-detail', params: { tool: 'topic' } }
  },
  {
    key: 'experiment' as ToolKey,
    badge: '实验',
    title: '实验设计',
    description: '整理变量、对照组、指标和流程，输出可执行步骤。',
    action: '进入方法详情',
    icon: TrendCharts,
    route: { name: 'research-tool-detail', params: { tool: 'experiment' } }
  },
  {
    key: 'reproduce' as ToolKey,
    badge: '复现',
    title: '论文复现',
    description: '用于拆解论文复现路径、验证步骤和代码入口。',
    action: '进入方法详情',
    icon: DocumentChecked,
    route: { name: 'research-tool-detail', params: { tool: 'reproduce' } }
  },
  {
    key: 'assessment' as ToolKey,
    badge: '测评',
    title: '练习试卷',
    description: '直接进入已有试卷页面，用于题目生成和作答查看。',
    action: '打开试卷页',
    icon: Search,
    route: { name: 'assessment' }
  }
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
