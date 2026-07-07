<template>
  <el-container class="layout">
    <el-aside class="sidebar" width="244px">
      <div class="brand">
        <div class="brand-mark">AI</div>
        <div>
          <h1>智研星链</h1>
          <p>A3 学习多智能体平台</p>
        </div>
      </div>
      <el-menu default-active="workflow" class="nav">
        <el-menu-item index="workflow">演示闭环</el-menu-item>
        <el-menu-item index="profile">学习画像</el-menu-item>
        <el-menu-item index="resources">资源生成</el-menu-item>
        <el-menu-item index="dashboard">教师驾驶舱</el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="topbar">
        <div>
          <strong>《人工智能与 AI4S 实践》</strong>
          <span>WiFi CSI 跌倒检测学习单元</span>
        </div>
        <el-button type="primary" :loading="loading" @click="handleRun">运行智能体流程</el-button>
      </el-header>

      <el-main class="main">
        <section class="hero">
          <div>
            <p class="eyebrow">Personalized Learning Agent System</p>
            <h2>从对话画像到个性化资源生成</h2>
            <p>
              以 A3 赛题核心链路为主线，展示画像 Agent、诊断 Agent、路径规划 Agent、
              资源生成 Agent 和校验 Agent 的协作结果。
            </p>
          </div>
          <el-input
            v-model="studentMessage"
            type="textarea"
            :rows="5"
            resize="none"
            placeholder="输入学生背景、目标和困惑"
          />
        </section>

        <el-row :gutter="16" class="metrics">
          <el-col :span="6" v-for="metric in metrics" :key="metric.label">
            <div class="metric">
              <span>{{ metric.label }}</span>
              <strong>{{ metric.value }}</strong>
            </div>
          </el-col>
        </el-row>

        <el-row :gutter="16">
          <el-col :span="10">
            <el-card class="panel" shadow="never">
              <template #header>学生画像</template>
              <div v-if="workflow" class="profile-grid">
                <div v-for="item in profileItems" :key="item.label">
                  <span>{{ item.label }}</span>
                  <p>{{ item.value }}</p>
                </div>
              </div>
              <el-empty v-else description="运行流程后生成画像" />
            </el-card>
          </el-col>

          <el-col :span="14">
            <el-card class="panel" shadow="never">
              <template #header>个性化学习路径</template>
              <el-timeline v-if="workflow">
                <el-timeline-item v-for="step in workflow.path" :key="step.id" :timestamp="`${step.estimated_minutes} 分钟`">
                  <strong>{{ step.title }}</strong>
                  <p>{{ step.reason }}</p>
                </el-timeline-item>
              </el-timeline>
              <el-empty v-else description="等待路径规划 Agent 输出" />
            </el-card>
          </el-col>
        </el-row>

        <el-card class="panel" shadow="never">
          <template #header>多智能体资源生成</template>
          <div class="resource-grid" v-if="workflow">
            <article class="resource-card" v-for="resource in workflow.resources" :key="resource.id">
              <el-tag>{{ resource.type }}</el-tag>
              <h3>{{ resource.title }}</h3>
              <p>{{ resource.content }}</p>
              <div class="tags">
                <el-tag size="small" type="info" v-for="point in resource.knowledge_points" :key="point">
                  {{ point }}
                </el-tag>
              </div>
              <small>来源：{{ resource.sources.join('、') }}</small>
            </article>
          </div>
          <el-empty v-else description="等待资源生成 Agent 输出" />
        </el-card>

        <el-row :gutter="16">
          <el-col :span="12">
            <el-card class="panel" shadow="never">
              <template #header>智能辅导</template>
              <el-input v-model="question" placeholder="输入学习问题" class="question-input" />
              <el-button :loading="tutorLoading" @click="handleAskTutor">提问</el-button>
              <div v-if="tutorAnswer" class="answer">
                <p>{{ tutorAnswer.answer }}</p>
                <el-alert :closable="false" type="success" :title="tutorAnswer.follow_up_exercise" />
              </div>
            </el-card>
          </el-col>

          <el-col :span="12">
            <el-card class="panel" shadow="never">
              <template #header>智能体协作轨迹</template>
              <el-table v-if="workflow" :data="workflow.agent_trace" size="small">
                <el-table-column prop="agent" label="Agent" width="170" />
                <el-table-column prop="summary" label="输出摘要" />
                <el-table-column prop="latency_ms" label="耗时(ms)" width="100" />
              </el-table>
              <el-empty v-else description="等待工作流执行" />
            </el-card>
          </el-col>
        </el-row>
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { askTutor, runDemoWorkflow, type DemoWorkflowResponse, type TutorResponse } from './api'

const studentMessage = ref(
  '我是计算机专业大二学生，Python 基础一般，想做 WiFi CSI 跌倒检测课程项目，但不太理解召回率、混淆矩阵和数据集划分。'
)
const question = ref('为什么跌倒检测更看重召回率而不是准确率？')
const workflow = ref<DemoWorkflowResponse>()
const tutorAnswer = ref<TutorResponse>()
const loading = ref(false)
const tutorLoading = ref(false)

const metrics = computed(() => [
  { label: '画像维度', value: workflow.value ? '8' : '-' },
  { label: '薄弱点', value: workflow.value?.weak_points.length ?? '-' },
  { label: '学习节点', value: workflow.value?.path.length ?? '-' },
  { label: '资源类型', value: workflow.value?.resources.length ?? '-' }
])

const profileItems = computed(() => {
  if (!workflow.value) return []
  const profile = workflow.value.profile
  return [
    { label: '知识基础', value: profile.knowledge_base },
    { label: '学习目标', value: profile.learning_goal },
    { label: '认知风格', value: profile.cognitive_style },
    { label: '实践能力', value: profile.practice_level },
    { label: '学习节奏', value: profile.learning_pace },
    { label: '兴趣方向', value: profile.interest_direction }
  ]
})

async function handleRun() {
  loading.value = true
  try {
    const { data } = await runDemoWorkflow(studentMessage.value)
    workflow.value = data
    ElMessage.success('智能体流程已完成')
  } catch {
    ElMessage.error('后端服务未启动或接口异常')
  } finally {
    loading.value = false
  }
}

async function handleAskTutor() {
  tutorLoading.value = true
  try {
    const { data } = await askTutor(question.value, workflow.value?.profile)
    tutorAnswer.value = data
  } catch {
    ElMessage.error('智能辅导接口调用失败')
  } finally {
    tutorLoading.value = false
  }
}
</script>
