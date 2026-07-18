<template>
  <div class="page practice-paper-page">
    <section class="practice-paper-hero">
      <div>
        <span>Practice Papers</span>
        <h2>练习试卷</h2>
      </div>
      <div class="practice-paper-actions">
        <el-button type="primary" @click="router.push({ name: 'practice-paper-create' })">新建试卷</el-button>
        <el-button @click="loadPapers">刷新</el-button>
      </div>
    </section>

    <section class="practice-paper-stats">
      <article>
        <span>试卷</span>
        <strong>{{ papers.length }}</strong>
      </article>
      <article>
        <span>已作答</span>
        <strong>{{ attemptedCount }}</strong>
      </article>
      <article>
        <span>平均最高分</span>
        <strong>{{ averageBestScore }}</strong>
      </article>
    </section>

    <section v-loading="loading" class="practice-paper-list">
      <article v-for="paper in papers" :key="paper.id" class="practice-paper-row" @click="openPaper(paper.id)">
        <div class="practice-paper-main">
          <span>{{ difficultyLabel(paper.difficulty) }} · {{ paper.total_questions }} 题</span>
          <strong>{{ paper.title }}</strong>
          <p>{{ paper.description || paper.knowledge_points.slice(0, 5).join(' / ') }}</p>
          <div class="practice-paper-tags">
            <el-tag v-for="point in paper.knowledge_points.slice(0, 6)" :key="point" size="small" effect="plain">{{ point }}</el-tag>
          </div>
        </div>
        <div class="practice-paper-score">
          <span>{{ statusLabel(paper.status) }}</span>
          <strong>{{ paper.best_score || '-' }}</strong>
          <small>最高分</small>
        </div>
        <div class="practice-paper-row-actions" @click.stop>
          <el-button size="small" type="primary" @click="openPaper(paper.id)">{{ paper.attempt_count ? '继续练习' : '开始做题' }}</el-button>
          <el-button size="small" type="danger" text @click="handleDelete(paper.id)">删除</el-button>
        </div>
      </article>

      <el-empty v-if="!loading && !papers.length" description="还没有试卷。点击新建试卷，从知识图谱节点生成练习。" />
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { deletePracticePaper, listPracticePapers, type PracticePaperRead } from '../services/apiClient'

const router = useRouter()
const loading = ref(false)
const papers = ref<PracticePaperRead[]>([])

const attemptedCount = computed(() => papers.value.filter((paper) => paper.attempt_count > 0).length)
const averageBestScore = computed(() => {
  const scored = papers.value.filter((paper) => paper.best_score > 0)
  if (!scored.length) return '-'
  return Math.round(scored.reduce((sum, paper) => sum + paper.best_score, 0) / scored.length)
})

onMounted(loadPapers)

async function loadPapers() {
  loading.value = true
  try {
    const { data } = await listPracticePapers()
    papers.value = data
  } finally {
    loading.value = false
  }
}

function openPaper(paperId: number) {
  void router.push({ name: 'practice-paper-detail', params: { paperId } })
}

async function handleDelete(paperId: number) {
  await ElMessageBox.confirm('删除后该试卷不会出现在历史列表中。', '删除试卷', {
    confirmButtonText: '删除',
    cancelButtonText: '取消',
    type: 'warning'
  })
  await deletePracticePaper(paperId)
  ElMessage.success('试卷已删除')
  await loadPapers()
}

function difficultyLabel(value: string) {
  const labels: Record<string, string> = { easy: '基础', medium: '适中', hard: '进阶' }
  return labels[value] || value
}

function statusLabel(value: string) {
  const labels: Record<string, string> = {
    ready: '待作答',
    reviewing: '待复习',
    completed: '已完成',
    draft: '草稿'
  }
  return labels[value] || value
}
</script>
