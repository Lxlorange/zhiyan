<template>
  <div class="page practice-paper-create-page">
    <section class="practice-create-head">
      <el-button @click="router.push({ name: 'assessment' })">返回试卷</el-button>
      <div>
        <span>New Paper</span>
        <h2>从知识节点生成试卷</h2>
      </div>
      <el-button type="primary" :loading="creating" :disabled="!canCreate" @click="handleCreate">生成并保存</el-button>
    </section>

    <section class="practice-create-layout">
      <aside class="practice-node-pool">
        <div class="practice-node-toolbar">
          <el-input v-model="query" placeholder="搜索知识点、项目节点、资料节点" clearable @keyup.enter="loadNodes" />
          <el-button :loading="loadingNodes" @click="loadNodes">检索</el-button>
        </div>
        <div class="practice-node-groups" v-loading="loadingNodes">
          <section v-for="group in nodeGroups" :key="group.layer">
            <header>
              <strong>{{ group.title }}</strong>
              <span>{{ group.nodes.length }}</span>
            </header>
            <button
              v-for="node in group.nodes"
              :key="node.id"
              type="button"
              class="practice-node-option"
              :class="{ selected: selectedMap.has(node.id) }"
              @click="toggleNode(node)"
            >
              <strong>{{ node.label }}</strong>
              <span>{{ node.category || node.layer }}</span>
              <small>{{ node.description }}</small>
            </button>
          </section>
        </div>
      </aside>

      <main class="practice-paper-config">
        <article class="practice-config-card">
          <header>
            <strong>试卷信息</strong>
            <span>{{ selectedNodes.length }} 个节点</span>
          </header>
          <el-form label-position="top">
            <el-form-item label="试卷标题">
              <el-input v-model="form.title" placeholder="例如：语义分割基础概念检测" />
            </el-form-item>
            <el-form-item label="说明">
              <el-input v-model="form.description" type="textarea" :rows="3" placeholder="写给自己的练习目标，可留空。" />
            </el-form-item>
            <div class="practice-config-grid">
              <el-form-item label="难度">
                <el-segmented v-model="form.difficulty" :options="difficultyOptions" />
              </el-form-item>
              <el-form-item label="题数">
                <el-input-number v-model="form.question_count" :min="1" :max="30" controls-position="right" />
              </el-form-item>
            </div>
            <el-form-item label="题型">
              <el-checkbox-group v-model="form.question_types" class="practice-type-picker">
                <el-checkbox-button label="choice">单选</el-checkbox-button>
                <el-checkbox-button label="multiple">多选</el-checkbox-button>
                <el-checkbox-button label="judgement">判断</el-checkbox-button>
                <el-checkbox-button label="short">简答</el-checkbox-button>
              </el-checkbox-group>
            </el-form-item>
          </el-form>
        </article>

        <article class="practice-config-card selected-node-card">
          <header>
            <strong>已选知识节点</strong>
            <el-button size="small" @click="selectedNodes = []">清空</el-button>
          </header>
          <div class="selected-node-list">
            <button v-for="node in selectedNodes" :key="node.id" type="button" @click="toggleNode(node)">
              <strong>{{ node.label }}</strong>
              <span>{{ node.layer }} · {{ node.category }}</span>
            </button>
          </div>
          <el-empty v-if="!selectedNodes.length" description="从左侧知识点池勾选若干节点。" />
        </article>
      </main>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  createPracticePaper,
  listPracticeKnowledgeNodes,
  type PracticeKnowledgeNodeRead
} from '../services/apiClient'

const router = useRouter()
const loadingNodes = ref(false)
const creating = ref(false)
const query = ref('')
const nodes = ref<PracticeKnowledgeNodeRead[]>([])
const selectedNodes = ref<PracticeKnowledgeNodeRead[]>([])

const form = reactive({
  title: '',
  description: '',
  difficulty: 'medium' as 'easy' | 'medium' | 'hard',
  question_count: 8,
  question_types: ['choice'] as string[]
})

const difficultyOptions = [
  { label: '基础', value: 'easy' },
  { label: '适中', value: 'medium' },
  { label: '进阶', value: 'hard' }
]

const selectedMap = computed(() => new Map(selectedNodes.value.map((node) => [node.id, node])))
const canCreate = computed(() => form.title.trim() && selectedNodes.value.length && form.question_types.length)
const nodeGroups = computed(() => {
  const groups = [
    { layer: 'project', title: '学习项目知识', nodes: nodes.value.filter((node) => node.layer === 'project') },
    { layer: 'knowledge_base', title: '知识库知识', nodes: nodes.value.filter((node) => node.layer === 'knowledge_base') },
    { layer: 'taxonomy', title: '先修知识', nodes: nodes.value.filter((node) => node.layer === 'taxonomy') }
  ]
  return groups.filter((group) => group.nodes.length)
})

onMounted(loadNodes)

async function loadNodes() {
  loadingNodes.value = true
  try {
    const { data } = await listPracticeKnowledgeNodes({ query: query.value, limit: 160 })
    nodes.value = data
  } finally {
    loadingNodes.value = false
  }
}

function toggleNode(node: PracticeKnowledgeNodeRead) {
  if (selectedMap.value.has(node.id)) {
    selectedNodes.value = selectedNodes.value.filter((item) => item.id !== node.id)
    return
  }
  selectedNodes.value = [...selectedNodes.value, node].slice(0, 20)
}

async function handleCreate() {
  if (!canCreate.value) return
  creating.value = true
  try {
    const { data } = await createPracticePaper({
      title: form.title.trim(),
      description: form.description.trim(),
      selected_nodes: selectedNodes.value.map((node) => ({ ...node })),
      question_types: form.question_types,
      difficulty: form.difficulty,
      question_count: form.question_count
    })
    ElMessage.success('试卷已生成并保存')
    await router.push({ name: 'practice-paper-detail', params: { paperId: data.id } })
  } finally {
    creating.value = false
  }
}
</script>
