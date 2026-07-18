<template>
  <div class="page knowledge-star-map-page">
    <KnowledgeSphereGraph
      v-model:query="knowledgeQuery"
      v-model:project-id="projectId"
      :graph="knowledgeLinkGraph"
      :loading="loadingKnowledgeLinks"
      :project-options="projects"
      :selected-node-id="selectedKnowledgeNode?.id || null"
      @search="loadKnowledgeLinks"
      @select-node="selectKnowledgeNode"
    />
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import KnowledgeSphereGraph from '../components/KnowledgeSphereGraph.vue'
import {
  getKnowledgeLinkGraph,
  listLearningProjects,
  type KnowledgeLinkGraphResponse,
  type KnowledgeLinkNode,
  type LearningProjectRead
} from '../services/apiClient'

const knowledgeQuery = ref('')
const projectId = ref<number | null>(null)
const projects = ref<LearningProjectRead[]>([])
const knowledgeLinkGraph = ref<KnowledgeLinkGraphResponse | null>(null)
const selectedKnowledgeNode = ref<KnowledgeLinkNode | null>(null)
const loadingKnowledgeLinks = ref(false)

onMounted(async () => {
  await Promise.all([loadProjects(), loadKnowledgeLinks()])
})

watch(projectId, () => {
  void loadKnowledgeLinks()
})

async function loadProjects() {
  const { data } = await listLearningProjects()
  projects.value = data
}

async function loadKnowledgeLinks() {
  loadingKnowledgeLinks.value = true
  try {
    const { data } = await getKnowledgeLinkGraph({
      project_id: projectId.value,
      query: knowledgeQuery.value.trim(),
      limit: 180
    })
    knowledgeLinkGraph.value = data
    if (selectedKnowledgeNode.value && !data.nodes.some((node) => node.id === selectedKnowledgeNode.value?.id)) {
      selectedKnowledgeNode.value = null
    }
  } finally {
    loadingKnowledgeLinks.value = false
  }
}

function selectKnowledgeNode(node: KnowledgeLinkNode | null) {
  selectedKnowledgeNode.value = node
  if (node?.layer === 'knowledge_base') {
    knowledgeQuery.value = node.label
  }
}
</script>
