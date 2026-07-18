<template>
  <div class="page knowledge-upload-page">
    <section class="page-hero knowledge-upload-hero">
      <div>
        <h2>知识库</h2>
      </div>
      <div class="knowledge-upload-actions">
        <el-button :loading="loading" @click="loadAll">刷新</el-button>
      </div>
    </section>

    <section class="knowledge-upload-layout">
      <article class="panel-like knowledge-upload-panel">
        <header>
          <strong>上传资料</strong>
          <span>支持 zip / pptx / ppt / pdf / docx / doc / md / txt</span>
        </header>

        <div class="knowledge-storage-meter">
          <div>
            <strong>{{ formatMb(storageUsage?.used_mb || 0) }} / {{ storageUsage?.quota_mb || 1024 }} MB</strong>
            <span>知识库空间 · 单次上传不超过 {{ MAX_UPLOAD_MB }} MB</span>
          </div>
          <el-progress :percentage="storageUsage?.used_percent || 0" :stroke-width="10" :show-text="false" />
        </div>

        <el-form label-position="top" class="knowledge-upload-form">
          <div class="knowledge-upload-grid">
            <el-form-item label="课程代码">
              <el-input v-model="uploadForm.course_code" placeholder="可选：例如 CS101" />
            </el-form-item>
            <el-form-item label="课程名称">
              <el-input v-model="uploadForm.course_title" placeholder="可选：例如 机器学习课程资料" />
            </el-form-item>
            <div class="knowledge-upload-confirm">
              <el-button
                type="primary"
                :loading="uploading"
                :disabled="!selectedUploadFile"
                @click="handleUploadConfirm"
              >
                开始分析
              </el-button>
              <el-button :disabled="uploading || !selectedUploadFile" @click="clearSelectedUpload">重新选择</el-button>
            </div>
          </div>
          <div class="knowledge-upload-options">
            <label class="knowledge-upload-option-card">
              <el-checkbox v-model="uploadForm.use_ocr">启用 OCR</el-checkbox>
            </label>
            <label class="knowledge-upload-option-card">
              <el-checkbox v-model="uploadForm.rebuild_course">导入前清空同课程资料</el-checkbox>
            </label>
          </div>
        </el-form>

        <el-upload
          class="knowledge-upload-drop"
          drag
          :auto-upload="false"
          :show-file-list="true"
          :limit="1"
          v-model:file-list="selectedUploadFiles"
          :disabled="uploading"
          :on-change="handleUploadSelect"
          :on-exceed="handleUploadExceed"
          :on-remove="handleUploadRemove"
        >
          <div class="knowledge-upload-drop-inner">
            <strong>{{ selectedUploadFile ? selectedUploadFile.name : '拖拽或点击选择资料包' }}</strong>
            <span>选择文件后，可先补充课程代码和名称，再点击开始分析。</span>
          </div>
        </el-upload>
      </article>

      <article class="panel-like knowledge-upload-panel">
        <header>
          <strong>上传记录</strong>
          <span>{{ jobs.length }} 条</span>
        </header>

        <el-table :data="jobs" v-loading="loadingJobs" class="knowledge-table" row-key="id">
          <el-table-column prop="source_name" label="文件" min-width="180" show-overflow-tooltip />
          <el-table-column prop="course_code" label="课程" width="150" show-overflow-tooltip />
          <el-table-column label="状态" width="110">
            <template #default="{ row }">
              <el-tag :type="jobStatusType(row.status)">{{ jobStatusLabel(row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="进度" min-width="210">
            <template #default="{ row }">
              <div class="knowledge-import-progress">
                <el-progress
                  :percentage="jobProgressPercent(row)"
                  :stroke-width="8"
                  :show-text="false"
                  :status="jobProgressStatus(row)"
                />
                <span>{{ jobProgressStage(row) }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="结果" width="150">
            <template #default="{ row }">
              {{ row.parsed_files }}/{{ row.total_files }} 文件 · {{ row.total_chunks }} 片段
            </template>
          </el-table-column>
          <el-table-column prop="created_at" label="时间" width="180">
            <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="110" fixed="right">
            <template #default="{ row }">
              <el-button link type="danger" @click="handleDeleteJob(row)">删除记录</el-button>
            </template>
          </el-table-column>
        </el-table>
      </article>
    </section>

    <section class="knowledge-content-layout">
      <article class="panel-like knowledge-upload-panel">
        <header class="knowledge-panel-toolbar">
          <div>
            <strong>已入库内容</strong>
            <span>{{ documents.length }} 个文档</span>
          </div>
          <div class="knowledge-filter-row">
            <el-input v-model="documentQuery" clearable placeholder="搜索文件名、标题、摘要" @keyup.enter="loadDocuments" />
            <el-button type="primary" :loading="loadingDocuments" @click="loadDocuments">搜索</el-button>
          </div>
        </header>

        <el-table
          :data="documents"
          v-loading="loadingDocuments"
          class="knowledge-table"
          row-key="id"
        >
          <el-table-column prop="title" label="文档" min-width="220" show-overflow-tooltip />
          <el-table-column prop="doc_type" label="类型" width="90" />
          <el-table-column prop="course_code" label="课程" width="150" show-overflow-tooltip />
          <el-table-column label="内容" width="110">
            <template #default="{ row }">{{ row.chunk_count }} 片段</template>
          </el-table-column>
          <el-table-column prop="summary" label="摘要" min-width="260" show-overflow-tooltip />
          <el-table-column label="操作" width="120" fixed="right">
            <template #default="{ row }">
              <el-button link type="danger" @click.stop="handleDeleteDocument(row)">删除文档</el-button>
            </template>
          </el-table-column>
        </el-table>
      </article>
    </section>

    <section class="panel-like knowledge-upload-panel knowledge-rag-panel">
      <header>
        <strong>知识库 RAG 问答</strong>
        <span>基于已上传资料、项目上下文和知识点证据回答</span>
      </header>
      <div class="rag-scope-row">
        <el-select v-model="ragProjectId" clearable placeholder="全部项目资料">
          <el-option
            v-for="project in projects"
            :key="project.id"
            :label="project.title"
            :value="project.id"
          />
        </el-select>
        <el-select v-model="ragKnowledgePoints" multiple collapse-tags collapse-tags-tooltip clearable placeholder="限定知识点">
          <el-option v-for="point in knowledgePoints" :key="point.id" :label="point.name" :value="point.name" />
        </el-select>
      </div>
      <el-input
        v-model="ragQuestion"
        type="textarea"
        :rows="4"
        placeholder="围绕已上传资料、课堂 PPT、笔记或知识点提问"
      />
      <div class="classroom-action-row">
        <el-button type="primary" :loading="generatingRag" :disabled="!ragQuestion.trim()" @click="handleRagAsk">
          基于知识库回答
        </el-button>
      </div>
      <div v-if="ragAnswer" class="rag-answer">
        <strong>回答</strong>
        <p>{{ ragAnswer }}</p>
        <div v-if="ragResponse?.related_points.length" class="rag-tags">
          <el-tag v-for="point in ragResponse.related_points" :key="point" size="small" @click="searchByPoint(point)">
            {{ point }}
          </el-tag>
        </div>
        <small>
          {{ ragResponse?.used_llm ? '由后端 RAG 结合大模型生成' : '由后端 RAG 检索结果生成' }}
          · 置信度 {{ ragResponse?.confidence || 'medium' }}
        </small>
        <div v-if="ragResponse?.citations.length" class="citation-list">
          <div v-for="(citation, index) in ragResponse.citations" :key="citation.id" class="citation-card">
            <span>来源 {{ index + 1 }} · {{ citation.source_type }}</span>
            <strong>{{ citation.title }}</strong>
            <p>{{ citation.content }}</p>
            <small>{{ renderCitationMeta(citation) }}</small>
            <div class="citation-actions">
              <el-button size="small" @click="locateCitation(citation)">定位片段</el-button>
              <el-button v-if="citation.review_url" size="small" @click="openCitationReview(citation)">回看材料</el-button>
            </div>
          </div>
        </div>
        <div v-if="ragResponse?.follow_up_questions.length" class="follow-up-list">
          <button v-for="question in ragResponse.follow_up_questions" :key="question" type="button" @click="ragQuestion = question">
            {{ question }}
          </button>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { UploadFile, UploadUserFile } from 'element-plus'
import {
  askDatabase,
  deleteKnowledgeDocument,
  deleteKnowledgeImportJob,
  getKnowledgeStorageUsage,
  importKnowledgePackage,
  listKnowledgePoints,
  listKnowledgeDocuments,
  listKnowledgeImportJobs,
  listLearningProjects,
  type DatabaseAskResponse,
  type DatabaseCitation,
  type KnowledgeDocumentRead,
  type KnowledgeImportJobRead,
  type KnowledgePointRead,
  type KnowledgeStorageUsageRead,
  type LearningProjectRead
} from '../services/apiClient'

const MAX_UPLOAD_MB = 100
const MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024

const uploadForm = reactive({
  course_code: '',
  course_title: '',
  use_ocr: false,
  rebuild_course: false
})
const selectedUploadFile = ref<File | null>(null)
const selectedUploadFiles = ref<UploadUserFile[]>([])
const jobs = ref<KnowledgeImportJobRead[]>([])
const documents = ref<KnowledgeDocumentRead[]>([])
const storageUsage = ref<KnowledgeStorageUsageRead | null>(null)
const projects = ref<LearningProjectRead[]>([])
const knowledgePoints = ref<KnowledgePointRead[]>([])
const documentQuery = ref('')
const ragQuestion = ref('')
const ragAnswer = ref('')
const ragResponse = ref<DatabaseAskResponse | null>(null)
const ragProjectId = ref<number | null>(null)
const ragKnowledgePoints = ref<string[]>([])
const loading = ref(false)
const uploading = ref(false)
const loadingJobs = ref(false)
const loadingDocuments = ref(false)
const generatingRag = ref(false)
let importPollTimer: ReturnType<typeof window.setInterval> | null = null

onMounted(loadAll)
onBeforeUnmount(stopImportPolling)

async function loadAll() {
  loading.value = true
  try {
    await Promise.all([loadStorageUsage(), loadJobs(), loadDocuments(), loadProjects(), loadKnowledgePoints()])
    updateImportPolling()
  } finally {
    loading.value = false
  }
}

async function loadStorageUsage() {
  const { data } = await getKnowledgeStorageUsage()
  storageUsage.value = data
}

async function loadJobs() {
  loadingJobs.value = true
  try {
    const { data } = await listKnowledgeImportJobs(50)
    jobs.value = data
    updateImportPolling()
  } finally {
    loadingJobs.value = false
  }
}

async function loadDocuments() {
  loadingDocuments.value = true
  try {
    const { data } = await listKnowledgeDocuments({
      query: documentQuery.value.trim(),
      limit: 100
    })
    documents.value = data
  } finally {
    loadingDocuments.value = false
  }
}

async function loadProjects() {
  const { data } = await listLearningProjects()
  projects.value = data
}

async function loadKnowledgePoints() {
  const { data } = await listKnowledgePoints()
  knowledgePoints.value = data
}

function handleUploadSelect(uploadFile: UploadFile, uploadFiles: UploadUserFile[]) {
  const raw = uploadFile?.raw as File | undefined
  if (!raw) return
  if (!validateUploadFile(raw)) {
    selectedUploadFile.value = null
    selectedUploadFiles.value = []
    return
  }
  selectedUploadFile.value = raw
  selectedUploadFiles.value = uploadFiles.slice(-1)
}

function handleUploadExceed(files: File[]) {
  const raw = files[0]
  if (!raw) return
  if (!validateUploadFile(raw)) {
    clearSelectedUpload()
    return
  }
  selectedUploadFile.value = raw
  selectedUploadFiles.value = [
    {
      name: raw.name,
      percentage: 0,
      raw,
      size: raw.size,
      status: 'ready',
      uid: Date.now()
    } as UploadUserFile
  ]
}

function handleUploadRemove(_uploadFile: UploadFile, uploadFiles: UploadUserFile[]) {
  selectedUploadFiles.value = uploadFiles
  selectedUploadFile.value = (uploadFiles[0]?.raw as File | undefined) || null
}

function clearSelectedUpload() {
  selectedUploadFile.value = null
  selectedUploadFiles.value = []
}

async function handleUploadConfirm() {
  const raw = selectedUploadFile.value || (selectedUploadFiles.value[0]?.raw as File | undefined) || null
  if (!raw) {
    ElMessage.warning('请先选择一个需要分析的资料文件。')
    return
  }
  if (!validateUploadFile(raw)) return
  uploading.value = true
  try {
    const { data } = await importKnowledgePackage(raw, {
      course_code: uploadForm.course_code.trim(),
      course_title: uploadForm.course_title.trim(),
      use_ocr: uploadForm.use_ocr,
      rebuild_course: uploadForm.rebuild_course
    })
    ElMessage.success('资料已提交，后台正在解析')
    clearSelectedUpload()
    jobs.value = [data, ...jobs.value.filter((job) => job.id !== data.id)]
    updateImportPolling()
    await Promise.all([loadStorageUsage(), loadDocuments()])
  } finally {
    uploading.value = false
    void loadStorageUsage()
  }
}

function updateImportPolling() {
  const hasActiveImport = jobs.value.some((job) => isActiveImportStatus(job.status))
  if (!hasActiveImport) {
    stopImportPolling()
    return
  }
  if (importPollTimer) return
  importPollTimer = window.setInterval(() => {
    void refreshImportJobsInBackground()
  }, 2000)
}

function stopImportPolling() {
  if (!importPollTimer) return
  window.clearInterval(importPollTimer)
  importPollTimer = null
}

async function refreshImportJobsInBackground() {
  try {
    const { data } = await listKnowledgeImportJobs(50)
    const hadActiveImport = jobs.value.some((job) => isActiveImportStatus(job.status))
    jobs.value = data
    const hasActiveImport = data.some((job) => isActiveImportStatus(job.status))
    if (!hasActiveImport) {
      stopImportPolling()
      if (hadActiveImport) {
        await Promise.all([loadStorageUsage(), loadDocuments(), loadKnowledgePoints()])
      }
    }
  } catch {
    stopImportPolling()
  }
}

function validateUploadFile(file: File) {
  if (file.size > MAX_UPLOAD_BYTES) {
    ElMessage.error(`单次上传文件不能超过 ${MAX_UPLOAD_MB} MB，请压缩或拆分后再上传。`)
    return false
  }
  const remainingBytes = storageUsage.value?.remaining_bytes
  if (remainingBytes !== undefined && file.size > remainingBytes) {
    ElMessage.error('知识库空间不足，请先删除无用上传记录释放空间。')
    return false
  }
  return true
}

async function handleDeleteDocument(row: KnowledgeDocumentRead) {
  try {
    await ElMessageBox.confirm(`确认删除文档“${row.title}”？对应内容片段会一起删除。`, '删除文档', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning'
    })
  } catch {
    return
  }
  await deleteKnowledgeDocument(row.id)
  ElMessage.success('文档已删除')
  await loadDocuments()
}

async function handleDeleteJob(row: KnowledgeImportJobRead) {
  if (isActiveImportStatus(row.status)) {
    ElMessage.warning('该资料仍在后台解析中，完成或失败后再删除。')
    return
  }
  try {
    await ElMessageBox.confirm(`确认删除上传记录“${row.source_name}”？该记录导入的文档片段和占用空间会一起清理。`, '清理知识库空间', {
      confirmButtonText: '删除并清理',
      cancelButtonText: '取消',
      type: 'warning'
    })
  } catch {
    return
  }
  await deleteKnowledgeImportJob(row.id)
  ElMessage.success('上传记录已删除')
  await Promise.all([loadJobs(), loadStorageUsage()])
}

async function handleRagAsk() {
  generatingRag.value = true
  try {
    const { data } = await askDatabase({
      question: ragQuestion.value,
      project_id: ragProjectId.value,
      knowledge_points: ragKnowledgePoints.value,
      limit: 8
    })
    ragResponse.value = data
    ragAnswer.value = data.answer
  } finally {
    generatingRag.value = false
  }
}

function searchByPoint(point: string) {
  documentQuery.value = point
  void loadDocuments()
}

async function locateCitation(citation: DatabaseCitation) {
  documentQuery.value = citation.knowledge_point || citation.title
  await loadDocuments()
  ElMessage.success('已定位到知识库来源，可在文档列表中继续查看。')
}

function renderCitationMeta(citation: DatabaseCitation) {
  return [
    citation.knowledge_point || citation.document_type,
    citation.section_title,
    citation.page_no ? `第 ${citation.page_no} 页` : '',
    citation.slide_no ? `第 ${citation.slide_no} 页` : ''
  ].filter(Boolean).join(' · ')
}

function openCitationReview(citation: DatabaseCitation) {
  if (citation.review_url.startsWith('/api/classroom-resources/')) {
    window.open(citation.review_url, '_blank')
    return
  }
  void locateCitation(citation)
}

function jobStatusLabel(status: string) {
  const labels: Record<string, string> = {
    queued: '排队中',
    running: '解析中',
    completed: '已完成',
    partial_failed: '部分失败',
    failed: '失败'
  }
  return labels[status] || status
}

function jobStatusType(status: string): 'success' | 'warning' | 'danger' | 'info' {
  if (status === 'completed') return 'success'
  if (status === 'partial_failed' || status === 'running' || status === 'queued') return 'warning'
  if (status === 'failed') return 'danger'
  return 'info'
}

function isActiveImportStatus(status: string) {
  return status === 'queued' || status === 'running'
}

function jobProgressPercent(job: KnowledgeImportJobRead) {
  const raw = Number(job.options?.progress_percent)
  if (Number.isFinite(raw)) return Math.max(0, Math.min(100, Math.round(raw)))
  if (job.status === 'completed' || job.status === 'partial_failed' || job.status === 'failed') return 100
  return job.status === 'queued' ? 5 : 20
}

function jobProgressStage(job: KnowledgeImportJobRead) {
  const stage = typeof job.options?.progress_stage === 'string' ? job.options.progress_stage : ''
  if (stage) return stage
  if (job.status === 'queued') return '等待后台解析'
  if (job.status === 'running') return '正在清洗资料并生成知识点'
  if (job.status === 'completed') return '导入完成'
  if (job.status === 'partial_failed') return '部分文件导入失败'
  if (job.status === 'failed') return job.error_message || '导入失败'
  return job.status
}

function jobProgressStatus(job: KnowledgeImportJobRead): 'success' | 'exception' | 'warning' | undefined {
  if (job.status === 'completed') return 'success'
  if (job.status === 'failed') return 'exception'
  if (job.status === 'partial_failed') return 'warning'
  return undefined
}

function formatDate(value: string) {
  return value ? new Date(value).toLocaleString() : '-'
}

function formatMb(value: number) {
  return Number(value || 0).toFixed(value >= 10 ? 0 : 2)
}
</script>
