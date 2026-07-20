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
            </div>
          </div>

          <div class="agent-dialogue-list">
            <article v-for="message in visibleMessages" :key="message.created_at" :class="['agent-bubble', message.role]">
              <span>{{ message.role === 'user' ? '你' : '规划 Agent' }}</span>
              <p>{{ message.content }}</p>
              <div v-if="message.role === 'user' && messageAttachments(message).length" class="agent-message-attachments">
                <span v-for="item in messageAttachments(message)" :key="item.uid" class="agent-file-chip">
                  <i aria-hidden="true"></i>
                  {{ item.name }}
                </span>
              </div>
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
                <ul class="agent-resource-list">
                  <li v-for="item in verifiedResourceLinks" :key="`${item.title}-${item.href}`">
                    <a
                      :href="item.href"
                      target="_blank"
                      rel="noreferrer"
                      class="agent-resource-link"
                    >
                      <strong>{{ item.title }}</strong>
                      <small>{{ item.source || '打开资源' }}</small>
                    </a>
                  </li>
                </ul>
                <p v-if="!verifiedResourceLinks.length" class="agent-empty-resources">未检索到可打开的真实资源链接。</p>
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
            accept=".txt,.md,.csv,.json,.py,.java,.ts,.js,.html,.css,.pdf"
          >
            <el-button :loading="parsingAttachments > 0">上传参考资料</el-button>
          </el-upload>

          <div class="agent-composer-spacer"></div>

          <el-button
            v-if="plan"
            class="agent-build-button"
            size="large"
            :loading="building"
            :disabled="plan.status === 'built' || planning || adjusting"
            @click="handleBuildProject"
          >
            {{ plan.status === 'built' ? '已构建' : '构建项目' }}
          </el-button>

          <el-button
            type="primary"
            size="large"
            :loading="planning || adjusting || parsingAttachments > 0"
            :disabled="plan?.status === 'built' || parsingAttachments > 0"
            @click="handlePrimaryAction"
          >
            {{ parsingAttachments > 0 ? '解析资料中' : plan ? '发送调整' : '生成项目计划' }}
          </el-button>
        </div>

        <div v-if="referenceMaterials.length" class="agent-reference-strip">
          <span v-for="item in referenceMaterials" :key="item.uid" class="agent-file-chip">
            <i aria-hidden="true"></i>
            {{ item.name }}
          </span>
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
  parseProjectPlanAttachment,
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
  parser: string
  pageCount?: number | null
}

type ResourceLink = {
  title: string
  href: string
  source?: string
  verified?: boolean
}

type DisplayPlanMessage = ProjectPlanMessage & {
  attachments?: ReferenceMaterial[]
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
const displayedUserMessages = ref<Record<string, DisplayPlanMessage>>({})
const parsingAttachments = ref(0)

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
const visibleMessages = computed<DisplayPlanMessage[]>(() => {
  if (!plan.value) {
    const goal = form.learning_goal || composerText.value
    return goal
      ? [{ role: 'user', content: goal, created_at: 'draft-message', attachments: referenceMaterials.value }]
      : []
  }
  return plan.value.messages.slice(-6).map((message) => sanitizePlanMessage(message))
})
const resourceLinks = computed<ResourceLink[]>(() => {
  if (!plan.value) return []
  const data = plan.value.plan_data || {}
  const candidates = [
    ...asArray(data.recommended_resources),
    ...asArray(data.resources),
    ...asArray(data.references)
  ]
  const links = candidates.map(toResourceLink).filter(Boolean) as ResourceLink[]
  return dedupeLinks(links)
})
const verifiedResourceLinks = computed(() => resourceLinks.value.filter((item) => item.href))

const MAX_PROJECT_CONTEXT_CHARS = 60000
const URL_PATTERN = /(https?:\/\/[^\s"'<>，。；、]+)/i

async function handlePrimaryAction() {
  if (plan.value) {
    await handleAdjust()
    return
  }
  await handleCreatePlan()
}

async function handleCreatePlan() {
  if (parsingAttachments.value > 0) {
    ElMessage.warning('参考资料仍在解析中，请等待解析完成后再生成项目计划。')
    return
  }

  const message = composerText.value.trim()
  if (!message) {
    ElMessage.warning('请先输入学习目标或科研方向')
    return
  }

  let referenceContext = ''
  try {
    referenceContext = buildReferenceContext()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : String(error))
    return
  }

  planning.value = true
  form.learning_goal = message
  plan.value = null
  streamText.value = ''
  try {
    const createdAt = new Date().toISOString()
    const displayMessage: DisplayPlanMessage = {
      role: 'user',
      content: message,
      created_at: createdAt,
      attachments: [...referenceMaterials.value]
    }
    await streamProjectPlan(
      {
        learning_type: form.learning_type,
        learning_goal: message,
        extra_requirements: referenceContext
      },
      {
        onToken: (content) => {
          streamText.value += content
        },
        onPlan: (nextPlan) => {
          plan.value = withSanitizedMessages(nextPlan, displayMessage)
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
  if (parsingAttachments.value > 0) {
    ElMessage.warning('参考资料仍在解析中，请等待解析完成后再调整项目计划。')
    return
  }

  const message = composerText.value.trim()
  if (!message) {
    ElMessage.warning('请输入调整要求')
    return
  }

  let payload = ''
  try {
    payload = appendReferenceContext(message)
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : String(error))
    return
  }

  adjusting.value = true
  adjustmentStreamText.value = ''
  const createdAt = new Date().toISOString()
  const displayMessage: DisplayPlanMessage = {
    role: 'user',
    content: message,
    created_at: createdAt,
    attachments: [...referenceMaterials.value]
  }
  plan.value.messages = [
    ...plan.value.messages,
    displayMessage
  ]
  composerText.value = ''
  try {
    await streamAdjustProjectPlan(plan.value.id, payload, {
      onToken: (content) => {
        adjustmentStreamText.value += content
        streamText.value = adjustmentStreamText.value
      },
      onPlan: (nextPlan) => {
        plan.value = withSanitizedMessages(nextPlan, displayMessage)
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

async function handleReferenceChange(uploadFile: UploadFile, uploadFiles: UploadUserFile[]) {
  referenceFiles.value = uploadFiles
  const raw = uploadFile.raw
  if (!raw) return

  parsingAttachments.value += 1
  try {
    const { data } = await parseProjectPlanAttachment(raw)
    upsertReference({
      uid: String(uploadFile.uid),
      name: data.filename,
      size: data.size,
      content: data.text,
      parser: data.parser,
      pageCount: data.page_count
    })
    ElMessage.success(`参考资料已解析：${data.filename}`)
  } catch {
    referenceFiles.value = uploadFiles.filter((file) => file.uid !== uploadFile.uid)
    referenceMaterials.value = referenceMaterials.value.filter((item) => item.uid !== String(uploadFile.uid))
  } finally {
    parsingAttachments.value = Math.max(0, parsingAttachments.value - 1)
  }
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
  const context = [
    '用户上传了以下已解析参考资料。请优先基于资料正文与资料来源规划项目；不得虚构资料中不存在的内容。',
    ...referenceMaterials.value.map((item, index) => {
      const pageInfo = item.pageCount ? `，页数 ${item.pageCount}` : ''
      const header = `资料 ${index + 1}：${item.name}，类型 ${item.parser}，大小 ${formatBytes(item.size)}${pageInfo}`
      return `${header}\n${item.content}`
    })
  ].join('\n\n')
  ensureProjectContextSize(context)
  return context
}

function appendReferenceContext(message: string): string {
  const context = buildReferenceContext()
  const payload = context ? `${message}\n\n${context}` : message
  ensureProjectContextSize(payload)
  return payload
}

function withSanitizedMessages(nextPlan: ProjectPlanRead, displayMessage: DisplayPlanMessage): ProjectPlanRead {
  displayedUserMessages.value[displayMessage.content] = displayMessage
  const messages = nextPlan.messages.map((message) => sanitizePlanMessage(message))
  return { ...nextPlan, messages }
}

function sanitizePlanMessage(message: ProjectPlanMessage): DisplayPlanMessage {
  if (message.role !== 'user') return message
  const displayContent = stripHiddenReferenceContext(message.content)
  const firstLine = displayContent.split('\n')[0]?.replace(/^学习目标[:：]\s*/, '').trim() || displayContent.trim()
  const displayed = displayedUserMessages.value[firstLine] || displayedUserMessages.value[message.content]
  if (displayed) {
    return {
      ...message,
      content: displayed.content,
      attachments: displayed.attachments
    }
  }
  return {
    ...message,
    content: displayContent,
    attachments: displayContent !== message.content ? [...referenceMaterials.value] : (message as DisplayPlanMessage).attachments
  }
}

function messageAttachments(message: DisplayPlanMessage): ReferenceMaterial[] {
  return message.attachments || []
}

function stripHiddenReferenceContext(content: string): string {
  let result = content
  const compactMarker = '\n\n用户上传了以下已解析参考资料。'
  if (result.includes(compactMarker)) result = result.split(compactMarker)[0]
  result = result.replace(/\n补充要求[:：]\s*用户上传了以下已解析参考资料[\s\S]*$/m, '')
  result = result.replace(/^学习目标[:：]\s*/m, '')
  return result.trim()
}

function ensureProjectContextSize(value: string) {
  if (value.length > MAX_PROJECT_CONTEXT_CHARS) {
    throw new Error(
      `参考资料上下文过长：${value.length} 字，当前上限 ${MAX_PROJECT_CONTEXT_CHARS} 字。请删除部分附件、拆分资料或只上传节选后的 md/txt。`
    )
  }
}

function asList(value: unknown): string[] {
  return Array.isArray(value) ? value.map((item) => {
    if (typeof item === 'string') return item
    if (item && typeof item === 'object') {
      const record = item as Record<string, unknown>
      return String(record.title || record.name || record.summary || record.reason || readableRecord(record))
    }
    return String(item)
  }).filter(Boolean) : []
}

function readableRecord(record: Record<string, unknown>): string {
  return Object.entries(record)
    .filter(([, value]) => value !== null && value !== undefined && value !== '')
    .map(([key, value]) => `${key.replace(/_/g, ' ')}：${Array.isArray(value) ? value.join('、') : String(value)}`)
    .slice(0, 5)
    .join('；')
}

function asArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : []
}

function toResourceLink(value: unknown): ResourceLink | null {
  if (typeof value === 'string') {
    const url = value.match(URL_PATTERN)?.[1]
    if (!url) return null
    const title = value.replace(URL_PATTERN, '').replace(/[：:,-]+$/, '').trim() || value
    return {
      title,
      href: url,
      source: getHost(url),
      verified: true
    }
  }
  if (!value || typeof value !== 'object') return null
  const record = value as Record<string, unknown>
  const title = String(record.title || record.name || record.label || record.source || '推荐资源')
  const rawHref = String(record.url || record.href || record.link || record.source_uri || '')
  const href = rawHref.match(URL_PATTERN)?.[1] || rawHref
  if (!/^https?:\/\//i.test(href)) return null
  return {
    title,
    href,
    source: String(record.source || record.publisher || getHost(href)),
    verified: true
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
