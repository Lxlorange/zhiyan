<template>
  <div class="page direction-planner-page direction-planner-page--agent">
    <section :class="['planner-agent-shell', { 'has-output': hasConversation }]">
      <Transition name="panel-swap">
        <section v-if="hasConversation" class="agent-output-panel">
          <div class="agent-output-head">
            <div>
              <span>智研规划 Agent</span>
              <strong>{{ plan?.title || '正在生成项目计划' }}</strong>
            </div>
            <div class="agent-output-actions">
              <el-tag :type="plan?.status === 'built' ? 'success' : planning || adjusting ? 'warning' : 'primary'">
                {{ statusText }}
              </el-tag>
              <el-button
                v-if="plan"
                type="primary"
                :loading="building"
                :disabled="plan.status === 'built'"
                @click="handleBuildProject"
              >
                {{ plan.status === 'built' ? '已构建' : '构建项目' }}
              </el-button>
            </div>
          </div>

          <div class="agent-dialogue-list">
            <article v-for="message in visibleMessages" :key="message.created_at" :class="['agent-bubble', message.role]">
              <span>{{ message.role === 'user' ? '你' : '规划 Agent' }}</span>
              <p>{{ message.content }}</p>
            </article>
            <article v-if="streamText" class="agent-bubble assistant is-streaming">
              <span>规划 Agent</span>
              <p>{{ streamText }}</p>
            </article>
          </div>

          <template v-if="plan">
            <div class="agent-plan-grid">
              <section class="agent-plan-section agent-plan-section--wide">
                <div class="agent-section-head">
                  <span>目标拆解</span>
                </div>
                <ol>
                  <li v-for="item in asList(plan.plan_data.target_breakdown)" :key="item">{{ item }}</li>
                </ol>
              </section>

              <section class="agent-plan-section">
                <div class="agent-section-head">
                  <span>推进阶段</span>
                </div>
                <div class="agent-card-list">
                  <article v-for="item in asList(plan.plan_data.milestones)" :key="item">{{ item }}</article>
                </div>
              </section>

              <section class="agent-plan-section">
                <div class="agent-section-head">
                  <span>预期产出</span>
                </div>
                <div class="agent-card-list">
                  <article v-for="item in asList(plan.plan_data.expected_outputs)" :key="item">{{ item }}</article>
                </div>
              </section>

              <section class="agent-plan-section agent-plan-section--wide">
                <div class="agent-section-head">
                  <span>推荐资源</span>
                </div>
                <div class="agent-resource-list">
                  <a
                    v-for="item in resourceLinks"
                    :key="`${item.title}-${item.href}`"
                    :href="item.href"
                    target="_blank"
                    rel="noreferrer"
                    class="agent-resource-link"
                  >
                    <strong>{{ item.title }}</strong>
                    <small>{{ item.source || '打开资源' }}</small>
                  </a>
                </div>
              </section>

              <section v-if="asList(plan.plan_data.next_questions).length" class="agent-plan-section">
                <div class="agent-section-head">
                  <span>待确认问题</span>
                </div>
                <ol>
                  <li v-for="item in asList(plan.plan_data.next_questions)" :key="item">{{ item }}</li>
                </ol>
              </section>

              <section v-if="asList(plan.plan_data.risk_notes).length" class="agent-plan-section agent-risk-section">
                <div class="agent-section-head">
                  <span>风险边界</span>
                </div>
                <p v-for="item in asList(plan.plan_data.risk_notes)" :key="item">{{ item }}</p>
              </section>
            </div>
          </template>
        </section>
      </Transition>

      <section class="agent-composer-panel">
        <div class="agent-composer-head">
          <strong>智研规划 Agent</strong>
          <el-tag v-if="hasConversation" size="small" :type="plan ? 'primary' : 'warning'">{{ statusText }}</el-tag>
        </div>

        <div class="agent-composer-textarea">
          <el-input
            v-model="composerText"
            type="textarea"
            :rows="hasConversation ? 4 : 7"
            resize="none"
            :disabled="planning || adjusting || plan?.status === 'built'"
            :placeholder="composerPlaceholder"
            aria-label="项目规划对话输入"
            @keydown.ctrl.enter.prevent="handlePrimaryAction"
            @keydown.meta.enter.prevent="handlePrimaryAction"
          />
        </div>

        <div class="agent-composer-meta">
          <el-select
            v-model="form.learning_type"
            class="agent-learning-type"
            placeholder="学习类型"
            :disabled="hasConversation || planning || adjusting"
            clearable
          >
            <el-option label="课程项目" value="course_project" />
            <el-option label="科研项目" value="research_project" />
            <el-option label="课程知识" value="course_knowledge" />
          </el-select>

          <el-upload
            class="agent-upload"
            action="#"
            :auto-upload="false"
            :limit="6"
            :file-list="referenceFiles"
            :on-change="handleReferenceChange"
            :on-remove="handleReferenceRemove"
            accept=".txt,.md,.csv,.json,.py,.java,.ts,.js,.html,.css,.pdf,.doc,.docx"
          >
            <el-button>上传参考资料</el-button>
          </el-upload>

          <div class="agent-composer-spacer"></div>

          <el-button
            type="primary"
            size="large"
            :loading="planning || adjusting"
            :disabled="plan?.status === 'built'"
            @click="handlePrimaryAction"
          >
            {{ plan ? '发送调整' : '生成项目计划' }}
          </el-button>
        </div>

        <div v-if="referenceSummaries.length" class="agent-reference-strip">
          <span v-for="item in referenceSummaries" :key="item">{{ item }}</span>
        </div>
      </section>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import type { UploadFile, UploadUserFile } from 'element-plus'
import {
  buildProjectPlan,
  streamAdjustProjectPlan,
  streamProjectPlan,
  type LearningProjectRead,
  type ProjectPlanMessage,
  type ProjectPlanRead
} from '../services/apiClient'

type ReferenceMaterial = {
  uid: string
  name: string
  size: number
  content: string
  readable: boolean
}

type ResourceLink = {
  title: string
  href: string
  source?: string
}

const emit = defineEmits<{
  projectBuilt: [project: LearningProjectRead]
}>()

const router = useRouter()

const form = reactive({
  learning_type: '',
  learning_goal: ''
})

const planning = ref(false)
const adjusting = ref(false)
const building = ref(false)
const plan = ref<ProjectPlanRead | null>(null)
const streamText = ref('')
const adjustmentStreamText = ref('')
const composerText = ref('')
const referenceFiles = ref<UploadUserFile[]>([])
const referenceMaterials = ref<ReferenceMaterial[]>([])

const hasConversation = computed(() => Boolean(plan.value || streamText.value || planning.value || adjusting.value))
const composerPlaceholder = computed(() => {
  if (plan.value?.status === 'built') return '项目已构建，请到项目主页继续学习。'
  if (plan.value) return '继续告诉规划 Agent 你想怎样调整，例如压缩周期、增加实验、补充论文阅读或改变最终产出。'
  return '例如：我想围绕一个科研方向完成选题、文献阅读、实验路线和课程论文，并希望系统帮我生成可执行的学习项目。'
})
const statusText = computed(() => {
  if (adjusting.value) return '调整中'
  if (planning.value) return '生成中'
  if (plan.value?.status === 'built') return '已构建'
  if (plan.value) return '可调整'
  return '待生成'
})
const visibleMessages = computed<ProjectPlanMessage[]>(() => {
  if (!plan.value) {
    const goal = form.learning_goal || composerText.value
    return goal
      ? [{ role: 'user', content: goal, created_at: 'draft-message' }]
      : []
  }
  return plan.value.messages.slice(-6)
})
const referenceSummaries = computed(() =>
  referenceMaterials.value.map((item) =>
    item.readable
      ? `${item.name} · 已读取 ${Math.min(item.content.length, MAX_REFERENCE_CHARS)} 字`
      : `${item.name} · 已附加文件名`
  )
)
const resourceLinks = computed<ResourceLink[]>(() => {
  if (!plan.value) return []
  const data = plan.value.plan_data || {}
  const candidates = [
    ...asArray(data.recommended_resources),
    ...asArray(data.resources),
    ...asArray(data.references),
    ...asArray(data.resource_plan)
  ]
  const links = candidates.map(toResourceLink).filter(Boolean) as ResourceLink[]
  return links.length
    ? dedupeLinks(links)
    : [
        {
          title: `${plan.value.title} 相关资源检索`,
          href: searchHref(plan.value.learning_goal),
          source: '检索入口'
        }
      ]
})

const MAX_REFERENCE_CHARS = 12000
const TEXT_FILE_PATTERN = /\.(txt|md|csv|json|py|java|ts|js|html|css)$/i
const URL_PATTERN = /(https?:\/\/[^\s"'<>，。；、]+)/i

async function handlePrimaryAction() {
  if (plan.value) {
    await handleAdjust()
    return
  }
  await handleCreatePlan()
}

async function handleCreatePlan() {
  const message = composerText.value.trim()
  if (!message) {
    ElMessage.warning('请先输入学习目标或科研方向')
    return
  }

  planning.value = true
  form.learning_goal = message
  plan.value = null
  streamText.value = ''
  try {
    await streamProjectPlan(
      {
        learning_type: form.learning_type,
        learning_goal: message,
        extra_requirements: buildReferenceContext()
      },
      {
        onToken: (content) => {
          streamText.value += content
        },
        onPlan: (nextPlan) => {
          plan.value = nextPlan
          streamText.value = ''
          composerText.value = ''
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
  if (!plan.value) return
  const message = composerText.value.trim()
  if (!message) {
    ElMessage.warning('请输入调整要求')
    return
  }

  adjusting.value = true
  adjustmentStreamText.value = ''
  plan.value.messages = [
    ...plan.value.messages,
    {
      role: 'user',
      content: message,
      created_at: new Date().toISOString()
    }
  ]
  composerText.value = ''
  try {
    await streamAdjustProjectPlan(plan.value.id, appendReferenceContext(message), {
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
    router.push({ name: 'project-detail', params: { projectId: data.project.id } })
  } finally {
    building.value = false
  }
}

function handleReferenceChange(uploadFile: UploadFile, uploadFiles: UploadUserFile[]) {
  referenceFiles.value = uploadFiles
  const raw = uploadFile.raw
  if (!raw) return

  if (!TEXT_FILE_PATTERN.test(raw.name)) {
    upsertReference({
      uid: String(uploadFile.uid),
      name: raw.name,
      size: raw.size,
      content: '',
      readable: false
    })
    ElMessage.info('已记录文件名。当前版本会读取 txt/md/csv/json/代码等文本资料内容。')
    return
  }

  const reader = new FileReader()
  reader.onload = () => {
    upsertReference({
      uid: String(uploadFile.uid),
      name: raw.name,
      size: raw.size,
      content: String(reader.result || '').slice(0, MAX_REFERENCE_CHARS),
      readable: true
    })
  }
  reader.onerror = () => {
    ElMessage.error(`参考资料读取失败：${raw.name}`)
  }
  reader.readAsText(raw)
}

function handleReferenceRemove(uploadFile: UploadFile, uploadFiles: UploadUserFile[]) {
  referenceFiles.value = uploadFiles
  referenceMaterials.value = referenceMaterials.value.filter((item) => item.uid !== String(uploadFile.uid))
}

function upsertReference(next: ReferenceMaterial) {
  referenceMaterials.value = [
    ...referenceMaterials.value.filter((item) => item.uid !== next.uid),
    next
  ]
}

function buildReferenceContext(): string {
  if (!referenceMaterials.value.length) return ''
  return [
    '用户上传了以下参考资料。请优先基于资料内容与资料来源规划项目；若资料只有文件名，请把它作为待补充来源，不要虚构其中内容。',
    ...referenceMaterials.value.map((item, index) => {
      const header = `资料 ${index + 1}：${item.name}，大小 ${formatBytes(item.size)}`
      return item.readable ? `${header}\n${item.content}` : `${header}\n未读取到正文，仅可作为资料线索。`
    })
  ].join('\n\n')
}

function appendReferenceContext(message: string): string {
  const context = buildReferenceContext()
  return context ? `${message}\n\n${context}` : message
}

function asList(value: unknown): string[] {
  return Array.isArray(value) ? value.map((item) => {
    if (typeof item === 'string') return item
    if (item && typeof item === 'object') {
      const record = item as Record<string, unknown>
      return String(record.title || record.name || record.summary || record.reason || JSON.stringify(record))
    }
    return String(item)
  }).filter(Boolean) : []
}

function asArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : []
}

function toResourceLink(value: unknown): ResourceLink | null {
  if (typeof value === 'string') {
    const url = value.match(URL_PATTERN)?.[1]
    const title = value.replace(URL_PATTERN, '').replace(/[：:,-]+$/, '').trim() || value
    return {
      title,
      href: url || searchHref(value),
      source: url ? getHost(url) : '检索'
    }
  }
  if (!value || typeof value !== 'object') return null
  const record = value as Record<string, unknown>
  const title = String(record.title || record.name || record.label || record.source || '推荐资源')
  const rawHref = String(record.url || record.href || record.link || record.source_uri || '')
  const href = rawHref.match(URL_PATTERN)?.[1] || rawHref
  return {
    title,
    href: href || searchHref(title),
    source: String(record.source || record.publisher || record.reason || (href ? getHost(href) : '检索'))
  }
}

function dedupeLinks(links: ResourceLink[]): ResourceLink[] {
  const seen = new Set<string>()
  return links.filter((item) => {
    const key = `${item.title}-${item.href}`
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
}

function searchHref(query: string): string {
  return `https://www.bing.com/search?q=${encodeURIComponent(query)}`
}

function getHost(url: string): string {
  try {
    return new URL(url).host
  } catch {
    return '打开资源'
  }
}

function formatBytes(size: number): string {
  if (!Number.isFinite(size) || size <= 0) return '未知'
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / 1024 / 1024).toFixed(1)} MB`
}
</script>
