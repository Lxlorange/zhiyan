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
              <el-input v-model="uploadForm.course_code" placeholder="必填：例如 CS101" @blur="uploadForm.course_code = normalizeCourseCode(uploadForm.course_code)" />
            </el-form-item>
            <el-form-item label="课程名称">
              <el-input v-model="uploadForm.course_title" placeholder="必填：例如 机器学习课程资料" />
            </el-form-item>
            <div class="knowledge-upload-confirm">
              <el-button
                type="primary"
                :loading="uploading"
                :disabled="!canStartAnalysis"
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
            <span>选好文件后直接点开始分析即可。</span>
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
          <el-table-column label="课程代码" width="130" show-overflow-tooltip>
            <template #default="{ row }">{{ row.course_code || '-' }}</template>
          </el-table-column>
          <el-table-column label="课程名称" min-width="180" show-overflow-tooltip>
            <template #default="{ row }">{{ row.course_title || '-' }}</template>
          </el-table-column>
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

      <article class="panel-like knowledge-upload-panel knowledge-documents-panel">
        <header>
          <strong>文档列表</strong>
          <span>{{ documents.length }} 份资料</span>
        </header>

        <div class="knowledge-filter-row">
          <el-input
            v-model="documentQuery"
            clearable
            placeholder="搜索课程代码、文件名、摘要"
            @keyup.enter="loadDocuments"
            @clear="loadDocuments"
          />
          <el-button :loading="loadingDocuments" @click="loadDocuments">搜索</el-button>
        </div>

        <div class="knowledge-document-workbench">
          <el-table
            :data="documents"
            v-loading="loadingDocuments"
            class="knowledge-table"
            row-key="id"
            highlight-current-row
            @row-click="selectDocument"
          >
            <el-table-column prop="title" label="名称" min-width="220" show-overflow-tooltip />
            <el-table-column label="课程代码" width="130" show-overflow-tooltip>
              <template #default="{ row }">{{ row.course_code || '-' }}</template>
            </el-table-column>
            <el-table-column prop="doc_type" label="类型" width="100" />
            <el-table-column label="片段" width="90">
              <template #default="{ row }">{{ row.chunk_count || 0 }}</template>
            </el-table-column>
            <el-table-column prop="created_at" label="入库时间" width="180">
              <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="100" fixed="right">
              <template #default="{ row }">
                <el-button link type="danger" @click.stop="handleDeleteDocument(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>

          <section class="knowledge-chunk-panel">
            <header>
              <strong>{{ selectedDocument?.title || '选择文档查看切片' }}</strong>
              <span v-if="selectedDocument">{{ selectedDocument.chunk_count }} 个片段</span>
            </header>
            <div v-if="selectedDocument" v-loading="loadingChunks" class="knowledge-chunk-list">
              <article v-for="chunk in documentChunks" :key="chunk.id">
                <div>
                  <strong>{{ chunk.knowledge_point || chunk.section_title || `片段 ${chunk.chunk_index + 1}` }}</strong>
                  <span>
                    {{ chunkLocationLabel(chunk) }}
                    <template v-if="chunk.token_count"> · {{ chunk.token_count }} tokens</template>
                  </span>
                </div>
                <p>{{ chunk.content }}</p>
                <div v-if="chunk.keywords?.length" class="knowledge-chunk-tags">
                  <el-tag v-for="keyword in chunk.keywords" :key="keyword" size="small" effect="plain">{{ keyword }}</el-tag>
                </div>
              </article>
              <el-empty v-if="!loadingChunks && !documentChunks.length" description="该文档暂无可预览片段" />
            </div>
            <el-empty v-else description="从左侧选择一份已入库资料" />
          </section>
        </div>
      </article>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { UploadFile, UploadUserFile } from 'element-plus'
import {
  deleteKnowledgeImportJob,
  deleteKnowledgeDocument,
  getKnowledgeStorageUsage,
  importKnowledgePackage,
  listKnowledgeDocumentChunks,
  listKnowledgeDocuments,
  listKnowledgeImportJobs,
  type KnowledgeChunkRead,
  type KnowledgeDocumentRead,
  type KnowledgeImportJobRead,
  type KnowledgeStorageUsageRead
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
const selectedDocument = ref<KnowledgeDocumentRead | null>(null)
const documentChunks = ref<KnowledgeChunkRead[]>([])
const documentQuery = ref('')
const storageUsage = ref<KnowledgeStorageUsageRead | null>(null)
const loading = ref(false)
const uploading = ref(false)
const loadingJobs = ref(false)
const loadingDocuments = ref(false)
const loadingChunks = ref(false)
let importPollTimer: ReturnType<typeof window.setInterval> | null = null

const normalizedCourseCode = computed(() => normalizeCourseCode(uploadForm.course_code))
const normalizedCourseTitle = computed(() => uploadForm.course_title.trim())
const canStartAnalysis = computed(() => {
  return Boolean(selectedUploadFile.value && normalizedCourseCode.value && normalizedCourseTitle.value && !uploading.value && !courseNameConflict.value)
})
const courseNameConflict = computed(() => {
  const code = normalizedCourseCode.value
  const title = normalizedCourseTitle.value
  if (!code || !title) return ''
  const fromJobs = jobs.value.find((job) => normalizeCourseCode(job.course_code || '') === code && (job.course_title || '').trim())
  const fromDocuments = documents.value.find((document) => normalizeCourseCode(document.course_code || '') === code && (document.title || '').trim())
  const existingTitle = String(fromJobs?.course_title || fromDocuments?.title || '').trim()
  return existingTitle && existingTitle !== title ? existingTitle : ''
})

onMounted(loadAll)
onBeforeUnmount(stopImportPolling)

async function loadAll() {
  loading.value = true
  try {
    await Promise.all([loadStorageUsage(), loadJobs(), loadDocuments()])
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
      limit: 80
    })
    documents.value = data
    if (selectedDocument.value && !data.some((document) => document.id === selectedDocument.value?.id)) {
      selectedDocument.value = null
      documentChunks.value = []
    }
  } finally {
    loadingDocuments.value = false
  }
}

async function selectDocument(row: KnowledgeDocumentRead) {
  selectedDocument.value = row
  loadingChunks.value = true
  try {
    const { data } = await listKnowledgeDocumentChunks(row.id, 120)
    documentChunks.value = data
  } finally {
    loadingChunks.value = false
  }
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
  if (!validateCourseForm()) return
  if (!validateUploadFile(raw)) return

  uploading.value = true
  try {
    const { data } = await importKnowledgePackage(raw, {
      course_code: normalizedCourseCode.value,
      course_title: normalizedCourseTitle.value,
      use_ocr: uploadForm.use_ocr,
      rebuild_course: uploadForm.rebuild_course
    })
    ElMessage.success('资料已提交，后台正在解析')
    clearSelectedUpload()
    jobs.value = [data, ...jobs.value.filter((job) => job.id !== data.id)]
    updateImportPolling()
    await Promise.all([loadStorageUsage(), loadJobs(), loadDocuments()])
  } finally {
    uploading.value = false
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
        await loadStorageUsage()
        await loadDocuments()
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

function validateCourseForm() {
  uploadForm.course_code = normalizedCourseCode.value
  if (!normalizedCourseCode.value) {
    ElMessage.warning('请填写课程代码。')
    return false
  }
  if (!normalizedCourseTitle.value) {
    ElMessage.warning('请填写课程名称。')
    return false
  }
  if (courseNameConflict.value) {
    ElMessage.warning(`课程代码 ${normalizedCourseCode.value} 已绑定“${courseNameConflict.value}”，请使用原课程名称或更换课程代码。`)
    return false
  }
  return true
}

function normalizeCourseCode(value: string) {
  return String(value || '').trim().toUpperCase()
}

async function handleDeleteJob(row: KnowledgeImportJobRead) {
  if (isActiveImportStatus(row.status)) {
    ElMessage.warning('该资料仍在后台解析中，完成或失败后再删除。')
    return
  }
  try {
    await ElMessageBox.confirm(`确认删除上传记录“${row.source_name}”吗？`, '清理知识库空间', {
      confirmButtonText: '删除并清理',
      cancelButtonText: '取消',
      type: 'warning'
    })
  } catch {
    return
  }
  await deleteKnowledgeImportJob(row.id)
  ElMessage.success('上传记录已删除')
  await Promise.all([loadJobs(), loadStorageUsage(), loadDocuments()])
}

async function handleDeleteDocument(row: KnowledgeDocumentRead) {
  try {
    await ElMessageBox.confirm(`确认删除文档“${row.title}”吗？`, '删除知识库文档', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning'
    })
  } catch {
    return
  }
  await deleteKnowledgeDocument(row.id)
  ElMessage.success('文档已删除')
  if (selectedDocument.value?.id === row.id) {
    selectedDocument.value = null
    documentChunks.value = []
  }
  await Promise.all([loadDocuments(), loadStorageUsage()])
}

function isActiveImportStatus(status: string) {
  return ['pending', 'running', 'queued', 'parsing', 'extracting', 'indexing'].includes(status)
}

function jobStatusLabel(status: string) {
  return {
    pending: '等待中',
    running: '解析中',
    queued: '排队中',
    completed: '完成',
    failed: '失败',
    parsing: '解析中',
    extracting: '抽取中',
    indexing: '入库中'
  }[status] || status
}

function jobStatusType(status: string) {
  if (status === 'completed') return 'success'
  if (status === 'failed') return 'danger'
  if (status === 'running' || status === 'parsing' || status === 'extracting' || status === 'indexing') return 'warning'
  return 'info'
}

function jobProgressPercent(job: KnowledgeImportJobRead) {
  if (job.status === 'completed') return 100
  if (job.status === 'failed') return 100
  if (job.total_files <= 0) return 0
  return Math.max(0, Math.min(100, Math.round((job.parsed_files / job.total_files) * 100)))
}

function jobProgressStage(job: KnowledgeImportJobRead) {
  if (job.error_message) return job.error_message
  return {
    pending: '等待队列',
    running: '正在解析',
    queued: '等待执行',
    completed: '已完成',
    failed: '解析失败',
    parsing: '切片与抽取',
    extracting: '清洗摘要',
    indexing: '写入知识库'
  }[job.status] || '处理中'
}

function jobProgressStatus(job: KnowledgeImportJobRead) {
  if (job.status === 'failed') return 'exception'
  if (job.status === 'completed') return 'success'
  return undefined
}

function formatMb(value: number) {
  return Number(value || 0).toFixed(1)
}

function formatDate(value: string) {
  if (!value) return '-'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString()
}

function chunkLocationLabel(chunk: KnowledgeChunkRead) {
  const parts = [`#${chunk.chunk_index + 1}`]
  if (chunk.page_no) parts.push(`第 ${chunk.page_no} 页`)
  if (chunk.slide_no) parts.push(`第 ${chunk.slide_no} 张`)
  if (chunk.section_title) parts.push(chunk.section_title)
  return parts.join(' · ')
}
</script>
