<template>
  <div class="page practice-paper-detail-page">
    <section class="practice-detail-head">
      <el-button @click="router.push({ name: 'assessment' })">返回试卷</el-button>
      <div v-if="paper">
        <span>{{ paper.total_questions }} 题 · {{ difficultyLabel(paper.difficulty) }}</span>
        <h2>{{ paper.title }}</h2>
      </div>
      <el-button v-if="paper && !latestAttempt" type="primary" :loading="submitting" @click="handleSubmit">提交试卷</el-button>
      <el-button v-else-if="paper" type="primary" plain @click="resetAnswers">重新作答</el-button>
    </section>

    <section v-if="paper" class="practice-detail-layout">
      <aside class="practice-paper-outline">
        <strong>题目导航</strong>
        <button
          v-for="question in paper.questions"
          :key="question.id"
          type="button"
          :class="{ answered: hasAnswer(question), wrong: latestResult(question)?.is_correct === false, correct: latestResult(question)?.is_correct === true }"
          @click="scrollToQuestion(question.question_id)"
        >
          <span>{{ question.order_index }}</span>
          <small>{{ question.point }}</small>
        </button>
        <div v-if="latestAttempt" class="practice-score-panel">
          <span>本次得分</span>
          <strong>{{ latestAttempt.score }}</strong>
          <p>{{ latestAttempt.summary }}</p>
        </div>
      </aside>

      <main class="practice-question-flow">
        <article
          v-for="question in paper.questions"
          :id="`question-${question.question_id}`"
          :key="question.id"
          class="practice-question-card"
        >
          <header>
            <span>{{ question.order_index }} / {{ paper.questions.length }}</span>
            <el-tag effect="plain">{{ question.point }}</el-tag>
            <el-tag type="info" effect="plain">{{ questionTypeLabel(question.type) }}</el-tag>
          </header>
          <h3>{{ question.prompt }}</h3>

          <el-radio-group
            v-if="question.type === 'choice' || question.type === 'judgement'"
            v-model="answers[question.question_id]"
            :disabled="Boolean(latestAttempt)"
            class="practice-answer-options"
          >
            <el-radio v-for="option in renderedOptions(question)" :key="option" :label="option">{{ option }}</el-radio>
          </el-radio-group>

          <el-checkbox-group
            v-else-if="question.type === 'multiple'"
            :model-value="answerArray(question.question_id)"
            :disabled="Boolean(latestAttempt)"
            class="practice-answer-options"
            @update:model-value="updateMultipleAnswer(question.question_id, $event)"
          >
            <el-checkbox v-for="option in question.options" :key="option" :label="option">{{ option }}</el-checkbox>
          </el-checkbox-group>

          <el-input
            v-else
            v-model="answers[question.question_id]"
            type="textarea"
            :rows="4"
            :disabled="Boolean(latestAttempt)"
            placeholder="写下你的答案"
          />

          <section v-if="latestResult(question)" class="practice-answer-review" :class="{ correct: latestResult(question)?.is_correct }">
            <header>
              <strong>{{ latestResult(question)?.is_correct ? '回答正确' : '需要复习' }}</strong>
              <span>参考答案：{{ latestResult(question)?.correct_answer }}</span>
            </header>
            <p>{{ latestResult(question)?.explanation }}</p>
            <small>{{ latestResult(question)?.remediation }}</small>
          </section>

          <footer v-if="question.source_title || question.source_excerpt">
            <span>{{ question.source_title }}</span>
            <p>{{ question.source_excerpt }}</p>
          </footer>
        </article>
      </main>
    </section>

    <section v-else v-loading="loading" class="panel-like workspace-loading">正在加载试卷...</section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  getPracticePaper,
  submitPracticePaper,
  type PracticePaperAttemptRead,
  type PracticePaperQuestionRead,
  type PracticePaperRead
} from '../services/apiClient'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const submitting = ref(false)
const reviewVisible = ref(true)
const paper = ref<PracticePaperRead | null>(null)
const submittedAttempt = ref<PracticePaperAttemptRead | null>(null)
const answers = reactive<Record<string, any>>({})

const paperId = computed(() => Number(route.params.paperId))
const latestAttempt = computed(() => reviewVisible.value ? (submittedAttempt.value || paper.value?.attempts?.[0] || null) : null)
const resultMap = computed(() => new Map((latestAttempt.value?.results || []).map((result) => [result.question_id, result])))

onMounted(loadPaper)

async function loadPaper() {
  loading.value = true
  try {
    const { data } = await getPracticePaper(paperId.value)
    paper.value = data
    submittedAttempt.value = null
    reviewVisible.value = true
    Object.keys(answers).forEach((key) => delete answers[key])
  } finally {
    loading.value = false
  }
}

async function handleSubmit() {
  if (!paper.value) return
  const missing = paper.value.questions.filter((question) => !hasAnswer(question))
  if (missing.length) {
    ElMessage.warning(`还有 ${missing.length} 道题未作答`)
    return
  }
  submitting.value = true
  try {
    const { data } = await submitPracticePaper(paper.value.id, { ...answers })
    paper.value = data.paper
    submittedAttempt.value = data.attempt
    reviewVisible.value = true
    ElMessage.success(`提交完成，得分 ${data.attempt.score}`)
  } finally {
    submitting.value = false
  }
}

function resetAnswers() {
  submittedAttempt.value = null
  reviewVisible.value = false
  Object.keys(answers).forEach((key) => delete answers[key])
}

function renderedOptions(question: PracticePaperQuestionRead) {
  if (question.type === 'judgement' && !question.options.length) return ['正确', '错误']
  return question.options
}

function answerArray(questionId: string) {
  const value = answers[questionId]
  return Array.isArray(value) ? value : []
}

function updateMultipleAnswer(questionId: string, value: unknown) {
  answers[questionId] = Array.isArray(value) ? value : []
}

function hasAnswer(question: PracticePaperQuestionRead) {
  const value = answers[question.question_id]
  if (Array.isArray(value)) return value.length > 0
  if (value !== undefined && value !== null && value !== '') return true
  return Boolean(latestAttempt.value?.answers?.[question.question_id])
}

function latestResult(question: PracticePaperQuestionRead) {
  return resultMap.value.get(question.question_id)
}

function scrollToQuestion(questionId: string) {
  document.getElementById(`question-${questionId}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

function questionTypeLabel(value: string) {
  const labels: Record<string, string> = { choice: '单选', multiple: '多选', judgement: '判断', short: '简答' }
  return labels[value] || value
}

function difficultyLabel(value: string) {
  const labels: Record<string, string> = { easy: '基础', medium: '适中', hard: '进阶' }
  return labels[value] || value
}
</script>
