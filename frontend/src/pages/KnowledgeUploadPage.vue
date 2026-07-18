<template>
  <div class="page knowledge-upload-page">
    <section class="page-hero knowledge-upload-hero">
      <div>
        <h2>知识库上传</h2>
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

        <el-form label-position="top" class="knowledge-upload-form">
          <div class="knowledge-upload-grid">
            <el-form-item label="课程代码">
              <el-input v-model="uploadForm.course_code" placeholder="例如 USER-COURSEWARE" />
            </el-form-item>
            <el-form-item label="课程名称">
              <el-input v-model="uploadForm.course_title" placeholder="例如 我的课程资料库" />
            </el-form-item>
          </div>
          <div class="knowledge-upload-options">
            <el-checkbox v-model="uploadForm.use_ocr">启用 OCR</el-checkbox>
            <el-checkbox v-model="uploadForm.rebuild_course">导入前清空同课程资料</el-checkbox>
          </div>
        </el-form>

        <el-upload
          class="knowledge-upload-drop"
          drag
          :auto-upload="false"
          :show-file-list="false"
          :disabled="uploading"
          :on-change="handleUpload"
        >
          <div class="knowledge-upload-drop-inner">
            <strong>{{ uploading ? '正在解析资料...' : '拖拽或点击上传资料包' }}</strong>
            <span>上传后只做解析入库和普通管理，不触发学习内容生成。</span>
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
          highlight-current-row
          @current-change="handleSelectDocument"
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

      <aside class="panel-like knowledge-upload-panel knowledge-chunk-panel">
        <header>
          <strong>{{ selectedDocument?.title || '内容预览' }}</strong>
          <span>{{ chunks.length }} 个片段</span>
        </header>

        <el-empty v-if="!selectedDocument" description="选择左侧文档查看解析内容。" />
        <div v-else class="knowledge-chunk-list" v-loading="loadingChunks">
          <article v-for="chunk in chunks" :key="chunk.id">
            <div>
              <strong>#{{ chunk.chunk_index }} · {{ chunk.knowledge_point }}</strong>
              <span>{{ chunk.section_title || locationLabel(chunk) }}</span>
            </div>
            <p>{{ chunk.content }}</p>
            <div class="knowledge-chunk-tags">
              <el-tag v-for="keyword in chunk.keywords" :key="keyword" effect="plain">{{ keyword }}</el-tag>
            </div>
          </article>
        </div>
      </aside>
    </section>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  deleteKnowledgeDocument,
  deleteKnowledgeImportJob,
  importKnowledgePackage,
  listKnowledgeDocumentChunks,
  listKnowledgeDocuments,
  listKnowledgeImportJobs,
  type KnowledgeChunkRead,
  type KnowledgeDocumentRead,
  type KnowledgeImportJobRead
} from '../services/apiClient'

const uploadForm = reactive({
  course_code: 'USER-COURSEWARE',
  course_title: '用户课程资料库',
  use_ocr: false,
  rebuild_course: false
})
const jobs = ref<KnowledgeImportJobRead[]>([])
const documents = ref<KnowledgeDocumentRead[]>([])
const chunks = ref<KnowledgeChunkRead[]>([])
const selectedDocument = ref<KnowledgeDocumentRead | null>(null)
const documentQuery = ref('')
const loading = ref(false)
const uploading = ref(false)
const loadingJobs = ref(false)
const loadingDocuments = ref(false)
const loadingChunks = ref(false)

onMounted(loadAll)

async function loadAll() {
  loading.value = true
  try {
    await Promise.all([loadJobs(), loadDocuments()])
  } finally {
    loading.value = false
  }
}

async function loadJobs() {
  loadingJobs.value = true
  try {
    const { data } = await listKnowledgeImportJobs(50)
    jobs.value = data
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
    if (selectedDocument.value && !data.some((item) => item.id === selectedDocument.value?.id)) {
      selectedDocument.value = null
      chunks.value = []
    }
  } finally {
    loadingDocuments.value = false
  }
}

async function handleUpload(uploadFile: any) {
  const raw = uploadFile?.raw as File | undefined
  if (!raw) return
  uploading.value = true
  try {
    await importKnowledgePackage(raw, {
      course_code: uploadForm.course_code.trim() || 'USER-COURSEWARE',
      course_title: uploadForm.course_title.trim() || '用户课程资料库',
      use_ocr: uploadForm.use_ocr,
      rebuild_course: uploadForm.rebuild_course
    })
    ElMessage.success('资料已解析入库')
    await loadAll()
  } finally {
    uploading.value = false
  }
}

async function handleSelectDocument(row: KnowledgeDocumentRead | null) {
  if (!row) return
  selectedDocument.value = row
  loadingChunks.value = true
  try {
    const { data } = await listKnowledgeDocumentChunks(row.id, 120)
    chunks.value = data
  } finally {
    loadingChunks.value = false
  }
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
  if (selectedDocument.value?.id === row.id) {
    selectedDocument.value = null
    chunks.value = []
  }
  await loadDocuments()
}

async function handleDeleteJob(row: KnowledgeImportJobRead) {
  try {
    await ElMessageBox.confirm(`确认删除上传记录“${row.source_name}”？这不会删除已入库文档。`, '删除上传记录', {
      confirmButtonText: '删除记录',
      cancelButtonText: '取消',
      type: 'warning'
    })
  } catch {
    return
  }
  await deleteKnowledgeImportJob(row.id)
  ElMessage.success('上传记录已删除')
  await loadJobs()
}

function jobStatusLabel(status: string) {
  const labels: Record<string, string> = {
    running: '解析中',
    completed: '已完成',
    partial_failed: '部分失败',
    failed: '失败'
  }
  return labels[status] || status
}

function jobStatusType(status: string): 'success' | 'warning' | 'danger' | 'info' {
  if (status === 'completed') return 'success'
  if (status === 'partial_failed' || status === 'running') return 'warning'
  if (status === 'failed') return 'danger'
  return 'info'
}

function formatDate(value: string) {
  return value ? new Date(value).toLocaleString() : '-'
}

function locationLabel(chunk: KnowledgeChunkRead) {
  if (chunk.page_no) return `第 ${chunk.page_no} 页`
  if (chunk.slide_no) return `第 ${chunk.slide_no} 页`
  return '正文片段'
}
</script>
