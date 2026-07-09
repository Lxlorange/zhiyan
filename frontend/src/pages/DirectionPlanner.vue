<template>
  <div class="page direction-planner-page">
    <section class="planner-intro">
      <div>
        <p class="eyebrow">Project Planning</p>
        <h2>从学习目标生成项目计划</h2>
        <p>
          先描述你想学习或研究的目标。系统会流式生成可微调的项目计划，你可以继续用自然语言调整，
          满意后再构建为正式学习项目。
        </p>
      </div>
      <div class="planner-intro-rail" aria-label="项目规划流程">
        <span>目标理解</span>
        <span>知识拆解</span>
        <span>资源规划</span>
        <span>构建项目</span>
      </div>
    </section>

    <section class="planner-workbench">
      <aside class="planner-chat-card">
        <div class="planner-column-head">
          <div>
            <strong>对话输入</strong>
            <span>左侧持续描述、澄清和微调目标</span>
          </div>
          <el-tag type="info">Chat</el-tag>
        </div>

        <el-form label-position="top" class="planner-form planner-chat-form">
          <el-form-item label="学习类型">
            <el-select v-model="form.learning_type" class="learning-type-select" placeholder="学习类型" clearable>
              <el-option label="课程项目" value="course_project" />
              <el-option label="科研项目" value="research_project" />
              <el-option label="课程知识" value="course_knowledge" />
            </el-select>
          </el-form-item>

          <el-form-item label="学习目标" required>
            <el-input
              v-model="form.learning_goal"
              type="textarea"
              :rows="6"
              resize="vertical"
              placeholder="例如：我想用 3 周学习 WiFi CSI 跌倒检测，最后完成一个 Python demo 和课程项目报告。"
            />
          </el-form-item>

          <el-form-item label="补充要求">
            <el-input
              v-model="form.extra_requirements"
              type="textarea"
              :rows="4"
              resize="vertical"
              placeholder="可写学习周期、课程要求、已有基础、希望生成的资源类型、最终产出形式等。"
            />
          </el-form-item>

          <div class="form-actions">
            <el-button type="primary" size="large" :loading="planning" @click="handleCreatePlan">
              生成项目计划
            </el-button>
            <el-button size="large" @click="resetForm">清空</el-button>
          </div>
        </el-form>

        <section v-if="plan || streamText || planning" class="chat-section planner-chat-thread">
          <h4>指令记录</h4>
          <div class="chat-log">
            <template v-if="instructionMessages.length">
              <article
                v-for="message in instructionMessages"
                :key="message.created_at"
                class="user"
              >
                <span>你</span>
                <p>{{ message.content }}</p>
              </article>
            </template>
            <template v-else>
              <article class="user">
                <span>你</span>
                <p>{{ form.learning_goal }}</p>
              </article>
            </template>
            <article class="assistant status-message">
              <span>状态</span>
              <p>{{ assistantStatusText }}</p>
            </article>
          </div>
          <el-input
            v-model="adjustMessage"
            type="textarea"
            :rows="3"
            resize="none"
            :disabled="!plan || plan.status === 'built'"
            placeholder="例如：把计划调整成 14 天，增加可视化演示和更多代码实践。"
          />
          <div class="drawer-actions">
            <el-button :loading="adjusting" :disabled="!plan || plan.status === 'built'" @click="handleAdjust">
              发送调整
            </el-button>
          </div>
        </section>
      </aside>

      <article class="planner-document-card">
        <div class="planner-document-head">
          <div>
            <span>Generated Document</span>
            <h3>{{ plan?.title || '项目计划文档' }}</h3>
          </div>
          <el-tag :type="plan?.status === 'built' ? 'success' : 'primary'">
            {{ plan?.status === 'built' ? '已构建' : adjusting ? '流式调整中' : planning ? '流式生成中' : '待生成' }}
          </el-tag>
        </div>

        <section v-if="!plan && !streamText && !planning" class="document-empty">
          <strong>等待生成项目计划</strong>
          <p>左侧输入学习目标后，右侧会以文档形式持续生成目标拆解、推进阶段、资源计划和风险边界。</p>
        </section>

        <template v-else>
          <section class="stream-card document-summary">
            <div class="stream-card-head">
              <span>计划摘要</span>
            </div>
            <p class="stream-output">{{ streamText || plan?.plan_data.summary || '等待模型输出...' }}</p>
          </section>

          <template v-if="plan">
            <section class="plan-section">
              <h4>目标拆解</h4>
              <ol>
                <li v-for="item in asList(plan.plan_data.target_breakdown)" :key="item">{{ item }}</li>
              </ol>
            </section>

            <section class="plan-section">
              <h4>推进阶段</h4>
              <div class="milestone-list">
                <article v-for="item in asList(plan.plan_data.milestones)" :key="item">{{ item }}</article>
              </div>
            </section>

            <section class="plan-section">
              <h4>推荐资源</h4>
              <div class="tags">
                <el-tag v-for="item in asList(plan.plan_data.resource_plan)" :key="item">{{ item }}</el-tag>
              </div>
            </section>

            <section class="plan-section">
              <h4>预期产出</h4>
              <div class="milestone-list">
                <article v-for="item in asList(plan.plan_data.expected_outputs)" :key="item">{{ item }}</article>
              </div>
            </section>

            <section v-if="asList(plan.plan_data.next_questions).length" class="plan-section">
              <h4>待确认问题</h4>
              <ol>
                <li v-for="item in asList(plan.plan_data.next_questions)" :key="item">{{ item }}</li>
              </ol>
            </section>

            <section v-if="asList(plan.plan_data.risk_notes).length" class="plan-section risk-section">
              <h4>风险与边界</h4>
              <p v-for="item in asList(plan.plan_data.risk_notes)" :key="item">{{ item }}</p>
            </section>

            <div class="document-actions">
              <el-button type="primary" :loading="building" :disabled="plan.status === 'built'" @click="handleBuildProject">
                构建项目
              </el-button>
            </div>
          </template>
        </template>
      </article>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  buildProjectPlan,
  streamAdjustProjectPlan,
  streamProjectPlan,
  type LearningProjectRead,
  type ProjectPlanRead
} from '../services/apiClient'

const emit = defineEmits<{
  projectBuilt: [project: LearningProjectRead]
}>()

const form = reactive({
  learning_type: '',
  learning_goal: '',
  extra_requirements: ''
})

const planning = ref(false)
const adjusting = ref(false)
const building = ref(false)
const adjustMessage = ref('')
const plan = ref<ProjectPlanRead | null>(null)
const streamText = ref('')
const adjustmentStreamText = ref('')
const instructionMessages = computed(() => {
  if (!plan.value) return []
  return plan.value.messages.filter((message) => message.role === 'user')
})
const assistantStatusText = computed(() => {
  if (adjusting.value) return '正在根据最新指令更新右侧项目计划文档。'
  if (planning.value) return '正在生成右侧项目计划文档。'
  if (plan.value?.status === 'built') return '项目已构建，可以在项目主页继续学习。'
  if (plan.value) return '项目计划已生成，可继续输入调整要求。'
  return '正在理解目标并准备生成项目计划。'
})

async function handleCreatePlan() {
  if (!form.learning_goal.trim()) {
    ElMessage.warning('学习目标是必填项')
    return
  }

  planning.value = true
  plan.value = null
  streamText.value = ''
  try {
    await streamProjectPlan(
      {
        learning_type: form.learning_type,
        learning_goal: form.learning_goal.trim(),
        extra_requirements: form.extra_requirements.trim()
      },
      {
        onToken: (content) => {
          streamText.value += content
        },
        onPlan: (nextPlan) => {
          plan.value = nextPlan
          streamText.value = ''
        },
        onDone: () => {
          ElMessage.success('项目计划已生成')
        }
      }
    )
  } finally {
    planning.value = false
  }
}

async function handleAdjust() {
  if (!plan.value || !adjustMessage.value.trim()) {
    ElMessage.warning('请输入调整要求')
    return
  }

  adjusting.value = true
  const message = adjustMessage.value.trim()
  adjustmentStreamText.value = ''
  plan.value.messages = [
    ...plan.value.messages,
    {
      role: 'user',
      content: message,
      created_at: new Date().toISOString()
    }
  ]
  adjustMessage.value = ''
  try {
    await streamAdjustProjectPlan(plan.value.id, message, {
      onToken: (content) => {
        adjustmentStreamText.value += content
        streamText.value = adjustmentStreamText.value
      },
      onPlan: (nextPlan) => {
        plan.value = nextPlan
        streamText.value = ''
      },
      onDone: () => {
        adjustmentStreamText.value = ''
        ElMessage.success('计划已更新')
      }
    })
  } finally {
    adjusting.value = false
  }
}

async function handleBuildProject() {
  if (!plan.value) return
  building.value = true
  try {
    const { data } = await buildProjectPlan(plan.value.id)
    plan.value = data.plan
    ElMessage.success(`项目已构建：${data.project.title}`)
    emit('projectBuilt', data.project)
  } finally {
    building.value = false
  }
}

function resetForm() {
  form.learning_type = ''
  form.learning_goal = ''
  form.extra_requirements = ''
  plan.value = null
  adjustMessage.value = ''
  streamText.value = ''
  adjustmentStreamText.value = ''
}

function asList(value: unknown): string[] {
  return Array.isArray(value) ? value.map(String).filter(Boolean) : []
}
</script>
