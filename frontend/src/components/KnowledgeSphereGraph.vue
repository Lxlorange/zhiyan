<template>
  <section class="knowledge-sphere-panel">
    <header class="knowledge-sphere-toolbar">
      <div class="knowledge-sphere-toolbar__title">
        <strong>知识漏斗 DAG</strong>
        <span>{{ graphStats }}</span>
      </div>
      <div class="knowledge-sphere-toolbar__controls">
        <el-select
          :model-value="projectId"
          clearable
          placeholder="全部项目与资料"
          class="knowledge-sphere-select"
          @update:model-value="updateProjectId"
        >
          <el-option
            v-for="project in projectOptions"
            :key="project.id"
            :label="project.title"
            :value="project.id"
          />
        </el-select>
        <el-input
          :model-value="query"
          class="knowledge-sphere-search"
          placeholder="搜索知识点、项目目标或资料片段"
          clearable
          @update:model-value="updateQuery"
          @keyup.enter="emit('search')"
        />
        <div class="knowledge-sphere-segments" role="group" aria-label="知识漏斗 DAG 视图">
          <button
            v-for="option in viewOptions"
            :key="option.value"
            type="button"
            :class="{ active: viewMode === option.value }"
            @click="viewMode = option.value"
          >
            {{ option.label }}
          </button>
        </div>
        <el-button :loading="loading" type="primary" @click="emit('search')">刷新图谱</el-button>
      </div>
    </header>

    <div class="knowledge-sphere-layout">
      <div class="knowledge-sphere-stage">
        <div ref="canvasHost" class="knowledge-sphere-canvas" @pointerleave="clearHover" />

        <div class="knowledge-sphere-overlay">
          <div class="knowledge-sphere-badge">
            <strong>RAG 知识 DAG</strong>
            <span>节点来自知识库与平台基础数据，边表示“先学什么再学什么”；孤立节点像 Obsidian 图谱一样分散在外围。</span>
          </div>

          <div v-if="hoveredNode" class="knowledge-sphere-tooltip" :style="tooltipStyle">
            <strong>{{ hoveredNode.label }}</strong>
            <span>{{ nodeSubtitle(hoveredNode) }}</span>
            <small v-if="hoveredNode.meta?.path">路径第 {{ hoveredNode.meta.path.order }} 步</small>
          </div>

          <div class="knowledge-sphere-legend">
            <span><i class="project" />项目目标</span>
            <span><i class="document" />上传资料</span>
            <span><i class="knowledge_base" />RAG 知识点</span>
            <span><i class="platform" />平台功能介绍</span>
            <span><i class="path" />学习路径</span>
          </div>

          <div class="knowledge-sphere-actions">
            <button type="button" @click="toggleRotation">
              {{ autoRotate ? '暂停旋转' : '恢复旋转' }}
            </button>
            <button type="button" :disabled="!activeSuggestion?.steps.length" @click="playPath">
              播放路径
            </button>
            <button type="button" @click="resetCamera">重置视角</button>
          </div>
        </div>
      </div>

      <aside class="knowledge-sphere-sidebar">
        <div class="knowledge-sphere-card knowledge-sphere-current">
          <strong>当前节点</strong>
          <template v-if="selectedNode">
            <span>{{ nodeSubtitle(selectedNode) }}</span>
            <h3>{{ selectedNode.label }}</h3>
            <p>{{ selectedDescription }}</p>
            <div class="knowledge-sphere-meta">
              <small v-for="(item, key) in selectedMeta" :key="key">
                {{ key }}: {{ item }}
              </small>
            </div>
            <div v-if="selectedEvidence.length" class="knowledge-sphere-evidence">
              <strong>掌握证据</strong>
              <p v-for="item in selectedEvidence" :key="item">{{ item }}</p>
            </div>
            <el-button size="small" @click="clearSelection">取消选择</el-button>
          </template>
          <template v-else>
            <span>点击节点可查看来源、前置关系、掌握证据和它在学习路径中的位置。</span>
          </template>
        </div>

        <div class="knowledge-sphere-card">
          <div class="knowledge-sphere-card-head">
            <strong>DAG 输出：个性化学习路径</strong>
            <span>{{ activeSuggestion?.project_title || '全部知识库' }}</span>
          </div>
          <p v-if="activeSuggestion?.strategy" class="knowledge-sphere-strategy">
            {{ activeSuggestion.strategy }}
          </p>
          <div v-if="activeSuggestion?.dynamic_signals?.length" class="knowledge-sphere-signals">
            <small v-for="signal in activeSuggestion.dynamic_signals" :key="signal">{{ signal }}</small>
          </div>
          <template v-if="activeSuggestion?.steps.length">
            <ol class="knowledge-sphere-path">
              <li
                v-for="step in activeSuggestion.steps"
                :key="step.id"
                :class="{ active: selectedNode?.id === step.id }"
                @click="handleStepClick(step.id)"
              >
                <b>{{ step.order || '?' }}</b>
                <span>{{ step.label }}</span>
                <em>{{ step.phase || step.layer }} · {{ step.estimated_minutes || 35 }} 分钟</em>
                <small>{{ step.reason }}</small>
              </li>
            </ol>
          </template>
          <template v-else>
            <span>当前暂无可展示路径。上传资料、建立项目知识点或补充学习画像后，系统会重新计算路径。</span>
          </template>
        </div>

        <div class="knowledge-sphere-card knowledge-sphere-map">
          <strong>图谱范围</strong>
          <div class="knowledge-sphere-stat-grid">
            <span><b>{{ graph?.nodes.length || 0 }}</b>节点</span>
            <span><b>{{ graph?.edges.length || 0 }}</b>关系</span>
            <span><b>{{ graph?.meta?.document_count || 0 }}</b>资料</span>
            <span><b>{{ graph?.meta?.isolated_count || 0 }}</b>孤立点</span>
          </div>
          <div class="knowledge-sphere-subjects">
            <span
              v-for="item in chapterStats"
              :key="item.subject"
              :style="{ '--subject-color': item.color }"
            >
              {{ item.subject }} {{ item.count }}
            </span>
          </div>
          <p>{{ graph?.attribution || '知识漏斗由当前用户上传知识库、项目知识点、平台功能介绍与学习画像动态聚合生成。' }}</p>
        </div>
      </aside>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { CSS2DObject, CSS2DRenderer } from 'three/examples/jsm/renderers/CSS2DRenderer.js'
import type {
  KnowledgeLinkEdge,
  KnowledgeLinkGraphResponse,
  KnowledgeLinkNode,
  KnowledgePathSuggestion
} from '../services/apiClient'

type ViewMode = 'all' | 'path' | 'documents'
type GraphEntry = {
  mesh: any
  halo?: any
  label?: any
  node: KnowledgeLinkNode
  position: any
  baseColor: number
}

const props = defineProps<{
  graph: KnowledgeLinkGraphResponse | null
  loading?: boolean
  query: string
  projectId: number | null
  projectOptions: Array<{ id: number; title: string }>
  selectedNodeId?: string | null
}>()

const emit = defineEmits<{
  (event: 'update:query', value: string): void
  (event: 'update:projectId', value: number | null): void
  (event: 'search'): void
  (event: 'select-node', node: KnowledgeLinkNode | null): void
}>()

const canvasHost = ref<HTMLDivElement | null>(null)
const hoveredNode = ref<KnowledgeLinkNode | null>(null)
const selectedNode = ref<KnowledgeLinkNode | null>(null)
const tooltipStyle = ref<Record<string, string>>({})
const viewMode = ref<ViewMode>('all')
const autoRotate = ref(true)

const viewOptions: Array<{ label: string; value: ViewMode }> = [
  { label: '全域', value: 'all' },
  { label: '路径', value: 'path' },
  { label: '证据', value: 'documents' }
]

let renderer: any = null
let labelRenderer: any = null
let camera: any = null
let scene: any = null
let controls: any = null
let frame = 0
let rootLayer: any = null
let nodeLayer: any = null
let linkLayer: any = null
let pathLayer: any = null
let orbitLayer: any = null
let guideLayer: any = null
let animationFrame = 0
let pathTimer = 0
let raycaster: any = null
let pointer = new THREE.Vector2()
let resizeObserver: ResizeObserver | null = null

const nodeMap = new Map<string, GraphEntry>()

const activeSuggestion = computed<KnowledgePathSuggestion | null>(() => {
  if (!props.graph?.path_suggestions.length) return null
  if (!props.projectId) return props.graph.path_suggestions[0]
  return props.graph.path_suggestions.find((item) => item.project_id === props.projectId) || props.graph.path_suggestions[0]
})

const pathNodeIds = computed(() => new Set((activeSuggestion.value?.steps || []).map((step) => step.id)))

const graphStats = computed(() => {
  const nodes = props.graph?.nodes.length || 0
  const edges = props.graph?.edges.length || 0
  const documents = props.graph?.meta?.document_count || 0
  const points = props.graph?.meta?.knowledge_point_count || 0
  return `${nodes} 节点 · ${edges} 关系 · ${documents} 资料 · ${points} 知识点`
})

const chapterStats = computed(() => {
  const subjects = props.graph?.meta?.chapter_subjects || props.graph?.meta?.document_types || {}
  return Object.entries(subjects)
    .map(([subject, count]) => ({ subject, count: Number(count), color: cssSubjectColor(subject) }))
    .sort((left, right) => right.count - left.count)
    .slice(0, 8)
})

const selectedDescription = computed(() => {
  if (!selectedNode.value) return ''
  const meta = selectedNode.value.meta || {}
  return (
    selectedNode.value.description ||
    String(meta.cluster_summary || '') ||
    String(meta.assessment_prompt || '') ||
    '暂无描述'
  )
})

const selectedEvidence = computed<string[]>(() => {
  const meta = selectedNode.value?.meta || {}
  const evidence = Array.isArray(meta.evidence) ? meta.evidence : []
  return evidence.map((item) => String(item)).filter(Boolean).slice(0, 3)
})

const selectedMeta = computed<Record<string, string>>(() => {
  if (!selectedNode.value) return {}
  const meta = selectedNode.value.meta || {}
  const entries: Array<[string, unknown]> = []
  if (selectedNode.value.layer === 'document') {
    entries.push(['type', selectedNode.value.category], ['chunks', meta.chunk_count], ['points', meta.point_count], ['course', meta.course_code])
  } else if (selectedNode.value.layer === 'knowledge_base') {
    entries.push(['chapter', meta.chapter], ['chunks', meta.chunk_count], ['documents', meta.document_count], ['difficulty', meta.difficulty])
  } else {
    entries.push(['status', meta.status], ['subject', meta.subject], ['goal', meta.goal_type])
  }
  if (meta.path) {
    entries.push(['path', `第 ${meta.path.order} 步 · ${meta.path.phase}`], ['time', `${meta.path.estimated_minutes || 35} 分钟`])
  }
  entries.push(['degree', meta.degree], ['level', meta.dag_level])
  return Object.fromEntries(
    entries
      .filter(([, value]) => value !== null && value !== undefined && value !== '')
      .slice(0, 8)
      .map(([key, value]) => [key, formatMeta(value)])
  )
})

watch(
  () => props.graph,
  async () => {
    await nextTick()
    rebuildGraph()
  },
  { deep: true }
)

watch(
  () => props.selectedNodeId,
  (id) => {
    if (!id || !props.graph) {
      selectedNode.value = null
      highlightSelected()
      return
    }
    selectedNode.value = props.graph.nodes.find((item) => item.id === id) || null
    highlightSelected()
    if (selectedNode.value) focusNode(selectedNode.value.id)
  }
)

watch([viewMode, pathNodeIds], () => {
  applyViewMode()
  rebuildPathLayer()
})

onMounted(async () => {
  await nextTick()
  initScene()
  rebuildGraph()
  renderFrame()
})

onBeforeUnmount(() => {
  if (animationFrame) cancelAnimationFrame(animationFrame)
  if (pathTimer) window.clearInterval(pathTimer)
  resizeObserver?.disconnect()
  controls?.dispose()
  renderer?.dispose()
  if (canvasHost.value) {
    canvasHost.value.removeEventListener('pointermove', handlePointerMove)
    canvasHost.value.removeEventListener('click', handlePointerClick)
  }
  disposeGraph()
})

function updateProjectId(value: number | string | null | undefined) {
  emit('update:projectId', value === null || value === undefined || value === '' ? null : Number(value))
}

function updateQuery(value: string | number | null | undefined) {
  emit('update:query', String(value ?? ''))
}

function initScene() {
  const host = canvasHost.value
  if (!host) return

  scene = new THREE.Scene()
  scene.fog = new THREE.Fog(0x060a14, 620, 1500)

  camera = new THREE.PerspectiveCamera(42, host.clientWidth / Math.max(1, host.clientHeight), 0.1, 4000)
  camera.position.set(0, 150, 900)

  renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2))
  renderer.setSize(host.clientWidth, host.clientHeight)
  renderer.outputColorSpace = THREE.SRGBColorSpace
  renderer.toneMapping = THREE.ACESFilmicToneMapping
  host.innerHTML = ''
  host.appendChild(renderer.domElement)

  labelRenderer = new CSS2DRenderer()
  labelRenderer.setSize(host.clientWidth, host.clientHeight)
  labelRenderer.domElement.className = 'knowledge-sphere-label-layer'
  host.appendChild(labelRenderer.domElement)

  controls = new OrbitControls(camera, renderer.domElement)
  controls.enableDamping = true
  controls.enablePan = false
  controls.minDistance = 360
  controls.maxDistance = 1180
  controls.autoRotate = autoRotate.value
  controls.autoRotateSpeed = 0.42

  const ambient = new THREE.AmbientLight(0xffffff, 1.35)
  const key = new THREE.DirectionalLight(0xffefd6, 2.2)
  key.position.set(220, 260, 260)
  const fill = new THREE.DirectionalLight(0xc4daeb, 1.1)
  fill.position.set(-260, -120, 180)
  scene.add(ambient, key, fill)

  rootLayer = new THREE.Group()
  nodeLayer = new THREE.Group()
  linkLayer = new THREE.Group()
  pathLayer = new THREE.Group()
  orbitLayer = new THREE.Group()
  guideLayer = new THREE.Group()
  rootLayer.add(guideLayer, orbitLayer, linkLayer, pathLayer, nodeLayer)
  scene.add(rootLayer)
  raycaster = new THREE.Raycaster()

  addCoreObjects()

  resizeObserver = new ResizeObserver(() => resizeRenderer())
  resizeObserver.observe(host)

  host.addEventListener('pointermove', handlePointerMove)
  host.addEventListener('click', handlePointerClick)
}

function addCoreObjects() {
  if (!scene) return
  buildGraphGuides()
}

function buildGraphGuides() {
  if (!guideLayer) return
  disposeGroup(guideLayer)
  const levels = [-220, -110, 0, 110, 220]
  levels.forEach((x, index) => {
    const geometry = new THREE.BufferGeometry().setFromPoints([
      new THREE.Vector3(x, -260, -260),
      new THREE.Vector3(x, -260, 260),
      new THREE.Vector3(x, 260, 260),
      new THREE.Vector3(x, 260, -260),
      new THREE.Vector3(x, -260, -260)
    ])
    const line = new THREE.Line(
      geometry,
      new THREE.LineBasicMaterial({
        color: index === 0 ? 0xffefd6 : 0xffffff,
        transparent: true,
        opacity: index === 0 ? 0.16 : 0.08
      })
    )
    guideLayer.add(line)
  })

  const axis = new THREE.Line(
    new THREE.BufferGeometry().setFromPoints([
      new THREE.Vector3(-320, 0, 0),
      new THREE.Vector3(320, 0, 0)
    ]),
    new THREE.LineBasicMaterial({ color: 0xdc8b5e, transparent: true, opacity: 0.34 })
  )
  guideLayer.add(axis)
}

function rebuildGraph() {
  if (!scene || !nodeLayer || !linkLayer || !orbitLayer || !props.graph) return
  disposeGraph()
  buildGraphGuides()
  drawAgeRings()

  const orderedNodes = [...props.graph.nodes].sort((left, right) => layerOrder(left.layer) - layerOrder(right.layer))
  const layerCounters = new Map<string, number>()
  orderedNodes.forEach((node) => {
    const index = layerCounters.get(node.layer) || 0
    layerCounters.set(node.layer, index + 1)
    const position = positionForNode(node, index)
    const color = nodeColor(node)
    const material = new THREE.MeshStandardMaterial({
      color,
      emissive: color,
      emissiveIntensity: isPathNode(node.id) ? 0.68 : 0.22,
      roughness: 0.18,
      metalness: 0.12,
      transparent: true,
      opacity: nodeOpacity(node)
    })

    const mesh = new THREE.Mesh(new THREE.SphereGeometry(nodeRadius(node), 28, 16), material)
    mesh.position.copy(position)
    mesh.userData.nodeId = node.id
    mesh.userData.layer = node.layer
    nodeLayer?.add(mesh)

    const halo = createHalo(node, color)
    if (halo) {
      halo.position.copy(position)
      nodeLayer?.add(halo)
    }

    const label = createNodeLabel(node)
    if (label) {
      label.position.copy(position.clone().add(new THREE.Vector3(0, nodeRadius(node) + 10, 0)))
      nodeLayer?.add(label)
    }

    nodeMap.set(node.id, { mesh, halo, label, node, position, baseColor: color })
  })

  drawEdges(props.graph.edges)
  rebuildPathLayer()
  applyViewMode()
  highlightSelected()
}

function drawAgeRings() {
  if (!orbitLayer) return
  const connectedCount = props.graph?.nodes.filter((node) => !node.meta?.is_isolated).length || 0
  const radius = connectedCount ? 330 : 210
  ;[0, 1, 2].forEach((index) => {
    const y = (index - 1) * 135
    const geometry = new THREE.BufferGeometry().setFromPoints(
      Array.from({ length: 160 }, (_, pointIndex) => {
        const angle = (pointIndex / 159) * Math.PI * 2
        return new THREE.Vector3(Math.cos(angle) * radius * 0.58, y, Math.sin(angle) * radius)
      })
    )
    const line = new THREE.Line(
      geometry,
      new THREE.LineBasicMaterial({
        color: index === 1 ? 0xc4daeb : 0xffffff,
        transparent: true,
        opacity: index === 1 ? 0.14 : 0.08
      })
    )
    line.rotation.z = Math.PI / 2
    orbitLayer.add(line)
  })
}

function drawEdges(edges: KnowledgeLinkEdge[]) {
  if (!linkLayer) return
  edges.slice(0, 560).forEach((edge) => {
    const source = nodeMap.get(edge.source)
    const target = nodeMap.get(edge.target)
    if (!source || !target) return
    const isPathEdge = isPathNode(edge.source) && isPathNode(edge.target)
    const points = curvedPoints(source.position, target.position, edge.relation === 'prerequisite' ? 30 : 14)
    const opacity = isPathEdge ? 0.62 : edge.relation === 'prerequisite' ? 0.38 : 0.12
    const line = new THREE.Line(
      new THREE.BufferGeometry().setFromPoints(points),
      new THREE.LineBasicMaterial({
        color: edgeColor(edge),
        transparent: true,
        opacity
      })
    )
    line.userData.relation = edge.relation
    linkLayer.add(line)
    if (edge.relation === 'prerequisite') {
      const arrow = createArrowHead(points[points.length - 2], points[points.length - 1], edgeColor(edge), opacity + 0.16)
      linkLayer.add(arrow)
    }
  })
}

function createArrowHead(from: any, to: any, color: number, opacity: number) {
  const direction = to.clone().sub(from).normalize()
  const arrow = new THREE.Mesh(
    new THREE.ConeGeometry(5.5, 14, 18),
    new THREE.MeshBasicMaterial({ color, transparent: true, opacity: Math.min(0.82, opacity) })
  )
  arrow.position.copy(to.clone().sub(direction.multiplyScalar(12)))
  arrow.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), direction)
  return arrow
}

function rebuildPathLayer() {
  if (!pathLayer) return
  disposeGroup(pathLayer)
  const steps = activeSuggestion.value?.steps || []
  const pathEntries = steps.map((step) => nodeMap.get(step.id)).filter(Boolean) as GraphEntry[]
  if (!pathEntries.length) return

  const guidePoints = pathEntries.map((entry) => entry.position)

  for (let index = 0; index < guidePoints.length - 1; index += 1) {
    const current = guidePoints[index]
    const next = guidePoints[index + 1]
    const curve = new THREE.CatmullRomCurve3(curvedPoints(current, next, index === 0 ? 24 : 42))
    const tube = new THREE.Mesh(
      new THREE.TubeGeometry(curve, 42, 2.8, 8, false),
      new THREE.MeshBasicMaterial({
        color: 0xffefd6,
        transparent: true,
        opacity: viewMode.value === 'documents' ? 0.18 : 0.62
      })
    )
    pathLayer.add(tube)
  }
}

function disposeGraph() {
  nodeMap.forEach(({ mesh, halo, label }) => {
    mesh.geometry.dispose()
    ;(mesh.material as any).dispose()
    if (halo) {
      halo.geometry.dispose()
      ;(halo.material as any).dispose()
    }
    label?.element.remove()
  })
  nodeMap.clear()
  if (nodeLayer) disposeGroup(nodeLayer)
  if (linkLayer) disposeGroup(linkLayer)
  if (pathLayer) disposeGroup(pathLayer)
  if (orbitLayer) disposeGroup(orbitLayer)
  if (guideLayer) disposeGroup(guideLayer)
}

function disposeGroup(group: any) {
  group.children.forEach((child: any) => {
    if (child instanceof THREE.Line || child instanceof THREE.Mesh) {
      child.geometry.dispose()
      const material = child.material
      if (Array.isArray(material)) material.forEach((item) => item.dispose())
      else material.dispose()
    }
    if (child instanceof CSS2DObject) child.element.remove()
  })
  group.clear()
}

function positionForNode(node: KnowledgeLinkNode, index: number) {
  if (node.meta?.is_isolated) return isolatedPosition(node, index)
  if (node.layer === 'project') return projectPosition(node, index)
  if (node.layer === 'document') return documentPosition(node, index)
  if (node.layer === 'platform') return platformPosition(node, index)
  if (node.layer === 'knowledge_base') return knowledgeBasePosition(node, index)
  return knowledgeBasePosition(node, index)
}

function projectPosition(node: KnowledgeLinkNode, index: number) {
  const count = Math.max(1, props.graph?.nodes.filter((item) => item.layer === 'project' && !item.meta?.is_isolated).length || 1)
  const angle = (index / count) * Math.PI * 2 + 0.34
  const radius = 210 + (hashString(node.id) % 40)
  return new THREE.Vector3(-310, Math.cos(angle) * radius * 0.55, Math.sin(angle) * radius)
}

function documentPosition(node: KnowledgeLinkNode, index: number) {
  const count = Math.max(1, props.graph?.nodes.filter((item) => item.layer === 'document' && !item.meta?.is_isolated).length || 1)
  const hash = hashString(node.id)
  const angle = (index / count) * Math.PI * 2 + ((hash % 17) / 17) * 0.34
  const radius = 188 + (hash % 74)
  return new THREE.Vector3(-150, Math.cos(angle) * radius * 0.66, Math.sin(angle) * radius)
}

function platformPosition(node: KnowledgeLinkNode, index: number) {
  const level = Math.max(0, Number(node.meta?.dag_level || 0))
  const x = -310 + Math.min(5, level) * 118
  const count = Math.max(1, props.graph?.nodes.filter((item) => item.layer === 'platform' && Number(item.meta?.dag_level || 0) === level).length || 1)
  const localIndex = props.graph?.nodes.filter((item) => item.layer === 'platform' && Number(item.meta?.dag_level || 0) === level).findIndex((item) => item.id === node.id) ?? index
  const angle = (localIndex / count) * Math.PI * 2 + 0.2
  const radius = 84 + (hashString(node.id) % 28)
  return new THREE.Vector3(x, Math.cos(angle) * radius, Math.sin(angle) * radius)
}

function knowledgeBasePosition(node: KnowledgeLinkNode, index: number) {
  const hash = hashString(`${node.category}:${node.id}`)
  const categoryAngle = ((hashString(node.category || 'kb') % 360) / 360) * Math.PI * 2
  const difficulty = String(node.meta?.difficulty || '').toLowerCase()
  const level = Math.max(0, Number(node.meta?.dag_level || 0))
  const path = node.meta?.path as Record<string, unknown> | undefined
  if (path?.order) {
    const order = Math.max(1, Number(path.order || 1))
    const steps = Math.max(1, activeSuggestion.value?.steps.length || 1)
    const t = steps <= 1 ? 0 : Math.min(1, (order - 1) / Math.max(1, steps - 1))
    const x = -120 + t * 420
    const pathAngle = categoryAngle + order * 0.68
    const radius = 92 + (hash % 54)
    return new THREE.Vector3(x, Math.cos(pathAngle) * radius, Math.sin(pathAngle) * radius)
  }
  const x = -90 + Math.min(5, level) * 105
  const levelNodes = props.graph?.nodes.filter(
    (item) => item.layer === 'knowledge_base' && !item.meta?.is_isolated && Number(item.meta?.dag_level || 0) === level
  ) || []
  const localIndex = Math.max(0, levelNodes.findIndex((item) => item.id === node.id))
  const angle = categoryAngle + localIndex * 0.78
  const difficultyOffset = difficulty.includes('hard') || difficulty.includes('困难') ? -42 : difficulty.includes('easy') || difficulty.includes('基础') ? 42 : 0
  const radius = 118 + (hash % 110)
  return new THREE.Vector3(x, Math.cos(angle) * radius + difficultyOffset, Math.sin(angle) * radius)
}

function isolatedPosition(node: KnowledgeLinkNode, index: number) {
  const isolatedNodes = props.graph?.nodes.filter((item) => item.meta?.is_isolated) || []
  const localIndex = Math.max(0, isolatedNodes.findIndex((item) => item.id === node.id))
  const count = Math.max(1, isolatedNodes.length)
  const hash = hashString(node.id)
  const angle = (localIndex / count) * Math.PI * 2 + ((hash % 23) / 23) * 0.38
  const ring = 320 + (localIndex % 4) * 38
  const x = 420 + (localIndex % 3) * 58
  return new THREE.Vector3(x, Math.cos(angle) * ring * 0.72, Math.sin(angle) * ring)
}

function nodeRadius(node: KnowledgeLinkNode) {
  const weight = Math.max(1, Number(node.weight || 1))
  const pathBoost = isPathNode(node.id) ? 4 : 0
  if (node.layer === 'project') return 18 + pathBoost
  if (node.layer === 'document') return 12 + Math.min(10, Math.log(weight + 1) * 2.6) + pathBoost
  if (node.layer === 'platform') return 10 + pathBoost
  if (node.layer === 'knowledge_base') return 9 + Math.min(11, Math.log(weight + 1) * 3) + pathBoost
  return 6 + Math.min(9, Math.log(weight + 1) * 3.2) + pathBoost
}

function createHalo(node: KnowledgeLinkNode, color: number) {
  if (!isPathNode(node.id) && node.layer !== 'project' && node.layer !== 'document' && node.layer !== 'platform') return null
  const radius = nodeRadius(node) + (node.layer === 'project' ? 8 : 6)
  const halo = new THREE.Mesh(
    new THREE.TorusGeometry(radius, 1.2, 8, 48),
    new THREE.MeshBasicMaterial({
      color: isPathNode(node.id) ? 0xdc8b5e : color,
      transparent: true,
      opacity: isPathNode(node.id) ? 0.9 : 0.38
    })
  )
  halo.rotation.x = Math.PI / 2
  return halo
}

function createNodeLabel(node: KnowledgeLinkNode) {
  const isImportant = node.layer === 'project' || node.layer === 'document' || node.layer === 'platform' || isPathNode(node.id)
  if (!isImportant) return null
  const label = document.createElement('span')
  label.className = `knowledge-sphere-label ${node.layer === 'project' ? 'is-project' : node.layer === 'document' ? 'is-document' : node.layer === 'platform' ? 'is-platform' : 'is-path'}`
  label.textContent = node.meta?.path?.order ? `${node.meta.path.order}. ${node.label}` : node.label
  return new CSS2DObject(label)
}

function nodeColor(node: KnowledgeLinkNode) {
  if (node.layer === 'project') return 0xdc8b5e
  if (node.layer === 'document') return 0xfadfa7
  if (node.layer === 'platform') return 0xcadab2
  if (node.layer === 'knowledge_base') return 0xc4daeb
  return subjectColor(String(node.category || 'knowledge'))
}

function subjectColor(subject: string) {
  const colors: Record<string, number> = {
    Science: 0xc4daeb,
    Mathematics: 0xcadab2,
    English: 0xf0cebb,
    History: 0xfadfa7,
    Computing: 0xdc8b5e,
    'Life Skills': 0xcadab2,
    'Learning to Learn': 0xffefd6,
    'Personal & Social Development': 0xf0cebb
  }
  return colors[subject] || 0xc4daeb
}

function cssSubjectColor(subject: string) {
  return `#${subjectColor(subject).toString(16).padStart(6, '0')}`
}

function edgeColor(edge: KnowledgeLinkEdge) {
  if (edge.relation === 'prerequisite') return edge.strength === 'hard' ? 0xdc8b5e : 0xfadfa7
  if (edge.relation === 'evidence') return 0xc4daeb
  if (edge.relation === 'focuses') return 0xcadab2
  return 0xf0cebb
}

function nodeOpacity(node: KnowledgeLinkNode) {
  if (viewMode.value === 'all') return 0.96
  if (viewMode.value === 'path') return isPathNode(node.id) || node.layer === 'project' ? 1 : 0.18
  return node.layer === 'document' || node.layer === 'knowledge_base' || isPathNode(node.id) ? 0.96 : 0.22
}

function applyViewMode() {
  nodeMap.forEach(({ mesh, halo, label, node }) => {
    const material = mesh.material as any
    material.opacity = nodeOpacity(node)
    material.emissiveIntensity = isPathNode(node.id) ? 0.82 : viewMode.value === 'path' ? 0.18 : 0.34
    mesh.visible = viewMode.value !== 'documents' || node.layer !== 'project' || isPathNode(node.id)
    if (halo) halo.visible = viewMode.value !== 'documents' || node.layer === 'document' || node.layer === 'platform' || isPathNode(node.id)
    if (label) label.visible = viewMode.value !== 'documents' || node.layer === 'document' || node.layer === 'platform' || isPathNode(node.id)
  })
}

function highlightSelected() {
  const selectedId = props.selectedNodeId || selectedNode.value?.id || ''
  const neighborhood = selectedId ? connectedNodeIds(selectedId) : new Set<string>()
  nodeMap.forEach(({ mesh, halo, node }) => {
    const material = mesh.material as any
    const active = node.id === selectedId
    const neighbor = neighborhood.has(node.id)
    const path = isPathNode(node.id)
    mesh.scale.setScalar(active ? 1.44 : neighbor ? 1.18 : path ? 1.12 : 1)
    material.opacity = selectedId && !active && !neighbor && !path ? 0.22 : nodeOpacity(node)
    material.emissiveIntensity = active ? 1.08 : neighbor ? 0.72 : path ? 0.82 : 0.28
    if (halo) halo.scale.setScalar(active ? 1.18 : 1)
  })
}

function connectedNodeIds(nodeId: string) {
  const result = new Set<string>([nodeId])
  for (const edge of props.graph?.edges || []) {
    if (edge.source === nodeId) result.add(edge.target)
    if (edge.target === nodeId) result.add(edge.source)
  }
  return result
}

function isPathNode(nodeId: string) {
  return pathNodeIds.value.has(nodeId)
}

function resizeRenderer() {
  if (!renderer || !camera || !canvasHost.value) return
  const { clientWidth, clientHeight } = canvasHost.value
  if (!clientWidth || !clientHeight) return
  renderer.setSize(clientWidth, clientHeight)
  labelRenderer?.setSize(clientWidth, clientHeight)
  camera.aspect = clientWidth / clientHeight
  camera.updateProjectionMatrix()
}

function renderFrame() {
  animationFrame = requestAnimationFrame(renderFrame)
  frame += 0.01
  if (controls) {
    controls.autoRotate = autoRotate.value
    controls.update()
  }
  if (rootLayer) rootLayer.rotation.y = Math.sin(frame * 0.18) * 0.08
  nodeMap.forEach(({ halo }, nodeId) => {
    if (halo) {
      halo.rotation.z += 0.01
      const pulse = isPathNode(nodeId) ? 1 + Math.sin(frame * 4 + hashString(nodeId)) * 0.06 : 1
      halo.scale.setScalar(pulse)
    }
  })
  if (scene && camera && renderer) {
    renderer.render(scene, camera)
    labelRenderer?.render(scene, camera)
  }
}

function handlePointerMove(event: PointerEvent) {
  if (!canvasHost.value || !camera || !raycaster) return
  const rect = canvasHost.value.getBoundingClientRect()
  pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1
  pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1
  raycaster.setFromCamera(pointer, camera)
  const intersects = raycaster.intersectObjects(nodeLayer?.children.filter((item: any) => item instanceof THREE.Mesh && item.userData.nodeId) || [])
  const hit = intersects[0]?.object as any
  if (!hit) {
    clearHover()
    return
  }
  const nodeId = String(hit.userData.nodeId || '')
  const entry = nodeMap.get(nodeId)
  if (!entry) return
  hoveredNode.value = entry.node
  tooltipStyle.value = {
    left: `${event.offsetX + 14}px`,
    top: `${event.offsetY + 14}px`
  }
  canvasHost.value.style.cursor = 'pointer'
}

function handlePointerClick(event: MouseEvent) {
  if (!canvasHost.value || !camera || !raycaster) return
  const rect = canvasHost.value.getBoundingClientRect()
  pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1
  pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1
  raycaster.setFromCamera(pointer, camera)
  const intersects = raycaster.intersectObjects(nodeLayer?.children.filter((item: any) => item instanceof THREE.Mesh && item.userData.nodeId) || [])
  const hit = intersects[0]?.object as any
  if (!hit) return
  const nodeId = String(hit.userData.nodeId || '')
  const entry = nodeMap.get(nodeId)
  if (!entry) return
  selectedNode.value = entry.node
  emit('select-node', entry.node)
  highlightSelected()
  focusNode(nodeId)
}

function clearHover() {
  hoveredNode.value = null
  if (canvasHost.value) canvasHost.value.style.cursor = 'default'
}

function clearSelection() {
  selectedNode.value = null
  emit('select-node', null)
  highlightSelected()
}

function handleStepClick(nodeId: string) {
  const node = props.graph?.nodes.find((item) => item.id === nodeId) || null
  if (!node) return
  selectedNode.value = node
  emit('select-node', node)
  highlightSelected()
  focusNode(nodeId)
}

function focusNode(nodeId: string) {
  const entry = nodeMap.get(nodeId)
  if (!entry || !controls || !camera) return
  controls.target.copy(entry.position)
  const direction = entry.position.clone().normalize()
  if (direction.lengthSq() < 0.1) direction.set(0.2, 0.2, 1)
  camera.position.copy(entry.position.clone().add(direction.multiplyScalar(360)).add(new THREE.Vector3(0, 80, 160)))
  camera.lookAt(entry.position)
  controls.update()
}

function resetCamera() {
  if (!camera || !controls) return
  camera.position.set(0, 150, 900)
  controls.target.set(0, 4, 0)
  controls.update()
}

function toggleRotation() {
  autoRotate.value = !autoRotate.value
}

function playPath() {
  const steps = activeSuggestion.value?.steps || []
  if (!steps.length) return
  if (pathTimer) window.clearInterval(pathTimer)
  viewMode.value = 'path'
  let index = 0
  handleStepClick(steps[index].id)
  pathTimer = window.setInterval(() => {
    index += 1
    if (index >= steps.length) {
      window.clearInterval(pathTimer)
      pathTimer = 0
      return
    }
    handleStepClick(steps[index].id)
  }, 1600)
}

function curvedPoints(source: any, target: any, lift: number) {
  const middle = source.clone().lerp(target, 0.5)
  const outward = new THREE.Vector3(middle.x, 0, middle.z).normalize().multiplyScalar(lift)
  return [source, source.clone().lerp(target, 0.35).add(outward), target.clone().lerp(source, 0.35).add(outward), target]
}

function layerOrder(layer: string) {
  if (layer === 'project') return 0
  if (layer === 'document') return 1
  if (layer === 'knowledge_base') return 2
  return 2
}

function nodeSubtitle(node: KnowledgeLinkNode) {
  if (node.layer === 'project') return `项目 · ${node.category || '学习目标'}`
  if (node.layer === 'document') return `上传资料 · ${node.category || 'document'}`
  if (node.layer === 'platform') return `基础节点 · 平台功能介绍`
  if (node.layer === 'knowledge_base') return `RAG 知识点 · ${node.category || '知识库'}`
  const meta = node.meta || {}
  const age = formatAge(meta.age_range)
  return `${meta.subject || '知识'} · ${meta.domain || node.category || 'domain'}${age ? ` · ${age}` : ''}`
}

function hashString(value: string) {
  let hash = 0
  for (let i = 0; i < value.length; i += 1) {
    hash = (hash * 31 + value.charCodeAt(i)) >>> 0
  }
  return hash
}

function formatAge(value: unknown): string {
  if (!Array.isArray(value)) return ''
  const [start, end] = value
  if (!start && !end) return ''
  return `${start || '?'}-${end || '?'} 岁`
}

function formatMeta(value: unknown): string {
  if (Array.isArray(value)) return value.map((item) => String(item)).slice(0, 4).join(' / ')
  if (typeof value === 'number') return Number.isInteger(value) ? String(value) : value.toFixed(2)
  if (typeof value === 'object' && value) {
    return Object.entries(value as Record<string, unknown>)
      .filter(([, item]) => item !== null && item !== undefined && item !== '')
      .map(([key, item]) => `${key.replace(/_/g, ' ')}: ${formatMeta(item)}`)
      .slice(0, 4)
      .join(' / ')
  }
  return String(value)
}
</script>

<style scoped>
.knowledge-sphere-panel {
  display: grid;
  gap: 16px;
  grid-column: 1 / -1;
}

.knowledge-sphere-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  align-items: center;
  justify-content: space-between;
}

.knowledge-sphere-toolbar__title {
  display: grid;
  gap: 4px;
}

.knowledge-sphere-toolbar__title strong {
  font-size: 28px;
  color: var(--study-ink);
  letter-spacing: 0;
}

.knowledge-sphere-toolbar__title span {
  color: var(--study-muted);
  font-size: 12px;
}

.knowledge-sphere-toolbar__controls {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}

.knowledge-sphere-select {
  width: 190px;
}

.knowledge-sphere-search {
  width: min(380px, 42vw);
}

.knowledge-sphere-segments {
  display: inline-flex;
  padding: 3px;
  border: 1px solid rgba(220, 139, 94, 0.22);
  border-radius: 10px;
  background: #ffefd6;
}

.knowledge-sphere-segments button,
.knowledge-sphere-actions button {
  border: 0;
  border-radius: 7px;
  background: transparent;
  color: #596273;
  cursor: pointer;
  font-size: 12px;
  transition: background 180ms ease, color 180ms ease, transform 180ms ease;
}

.knowledge-sphere-segments button {
  padding: 7px 10px;
}

.knowledge-sphere-segments button.active {
  background: #dc8b5e;
  color: #fff;
}

.knowledge-sphere-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.9fr) minmax(340px, 0.72fr);
  gap: 16px;
}

.knowledge-sphere-stage {
  position: relative;
  min-height: 760px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 8px;
  overflow: hidden;
  background:
    radial-gradient(circle at 42% 45%, rgba(196, 218, 235, 0.18), transparent 28%),
    radial-gradient(circle at 75% 52%, rgba(202, 218, 178, 0.12), transparent 24%),
    radial-gradient(circle at 22% 28%, rgba(220, 139, 94, 0.12), transparent 18%),
    linear-gradient(135deg, #070a13 0%, #0b1020 54%, #060811 100%);
  box-shadow: 0 32px 90px rgba(9, 12, 24, 0.28);
}

.knowledge-sphere-stage::after {
  position: absolute;
  inset: 0;
  pointer-events: none;
  content: '';
  background-image:
    linear-gradient(rgba(255, 255, 255, 0.035) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.035) 1px, transparent 1px);
  background-size: 34px 34px;
  mask-image: radial-gradient(ellipse at 54% 52%, black 0%, transparent 76%);
}

.knowledge-sphere-canvas {
  position: absolute;
  inset: 0;
}

:deep(.knowledge-sphere-label-layer) {
  position: absolute;
  inset: 0;
  pointer-events: none;
}

:deep(.knowledge-sphere-label) {
  display: block;
  max-width: 150px;
  padding: 5px 8px;
  border: 1px solid rgba(255, 255, 255, 0.16);
  border-radius: 6px;
  background: rgba(6, 10, 20, 0.82);
  color: #fff;
  font-size: 11px;
  line-height: 1.3;
  text-align: center;
  box-shadow: 0 8px 20px rgba(15, 23, 42, 0.22);
  backdrop-filter: blur(10px);
}

:deep(.knowledge-sphere-label.is-project) {
  background: rgba(15, 118, 110, 0.86);
}

:deep(.knowledge-sphere-label.is-document) {
  background: rgba(138, 87, 0, 0.84);
}

:deep(.knowledge-sphere-label.is-platform) {
  background: rgba(85, 107, 63, 0.86);
}

:deep(.knowledge-sphere-label.is-path) {
  border-color: rgba(245, 158, 11, 0.65);
}

.knowledge-sphere-overlay {
  position: absolute;
  inset: 0;
  pointer-events: none;
}

.knowledge-sphere-badge,
.knowledge-sphere-legend,
.knowledge-sphere-actions,
.knowledge-sphere-tooltip {
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(8, 12, 24, 0.78);
  box-shadow: 0 16px 36px rgba(0, 0, 0, 0.22);
  backdrop-filter: blur(14px);
}

.knowledge-sphere-badge {
  position: absolute;
  top: 16px;
  left: 16px;
  display: grid;
  max-width: 430px;
  gap: 6px;
  padding: 14px 16px;
  border-radius: 8px;
  color: #f8fafc;
  font-size: 12px;
}

.knowledge-sphere-badge strong {
  font-size: 16px;
}

.knowledge-sphere-tooltip {
  position: absolute;
  z-index: 3;
  display: grid;
  min-width: 190px;
  max-width: 280px;
  gap: 3px;
  padding: 10px 12px;
  border-radius: 12px;
  color: #f8fafc;
}

.knowledge-sphere-tooltip strong,
.knowledge-sphere-tooltip span,
.knowledge-sphere-tooltip small {
  display: block;
}

.knowledge-sphere-tooltip span,
.knowledge-sphere-tooltip small {
  color: #cbd5e1;
  font-size: 12px;
}

.knowledge-sphere-legend {
  position: absolute;
  left: 16px;
  right: 16px;
  bottom: 16px;
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  padding: 10px 12px;
  border-radius: 8px;
}

.knowledge-sphere-legend span {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: #d7dde8;
  font-size: 12px;
}

.knowledge-sphere-legend i {
  width: 10px;
  height: 10px;
  border-radius: 999px;
  display: inline-block;
}

.knowledge-sphere-legend i.project {
  background: #dc8b5e;
}

.knowledge-sphere-legend i.knowledge_base {
  background: #c4daeb;
}

.knowledge-sphere-legend i.document {
  background: #fadfa7;
}

.knowledge-sphere-legend i.platform {
  background: #cadab2;
}

.knowledge-sphere-legend i.path {
  background: #fadfa7;
}

.knowledge-sphere-actions {
  position: absolute;
  top: 16px;
  right: 16px;
  display: flex;
  gap: 6px;
  padding: 5px;
  border-radius: 8px;
  pointer-events: auto;
}

.knowledge-sphere-actions button {
  padding: 7px 9px;
}

.knowledge-sphere-actions button:hover {
  background: rgba(255, 255, 255, 0.12);
  color: #fff;
  transform: translateY(-1px);
}

.knowledge-sphere-actions button:disabled {
  cursor: not-allowed;
  opacity: 0.45;
}

.knowledge-sphere-sidebar {
  display: grid;
  gap: 14px;
  align-content: start;
}

.knowledge-sphere-card {
  display: grid;
  gap: 10px;
  padding: 16px;
  border: 1px solid rgba(220, 139, 94, 0.16);
  border-radius: 14px;
  background: #ffefd6;
}

.knowledge-sphere-card strong {
  color: var(--study-ink);
}

.knowledge-sphere-card-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
}

.knowledge-sphere-card-head span,
.knowledge-sphere-current > span {
  color: var(--study-muted);
  font-size: 12px;
}

.knowledge-sphere-card h3 {
  margin: 0;
  color: var(--study-ink);
  font-size: 18px;
  line-height: 1.3;
  text-wrap: balance;
}

.knowledge-sphere-card p {
  margin: 0;
  color: var(--study-soft);
  line-height: 1.65;
}

.knowledge-sphere-meta,
.knowledge-sphere-signals,
.knowledge-sphere-subjects {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.knowledge-sphere-meta small,
.knowledge-sphere-signals small {
  padding: 6px 8px;
  border-radius: 8px;
  background: #f0cebb;
  color: #4c4139;
}

.knowledge-sphere-evidence {
  display: grid;
  gap: 6px;
  padding-top: 4px;
}

.knowledge-sphere-evidence strong {
  font-size: 13px;
}

.knowledge-sphere-evidence p {
  padding-left: 10px;
  border-left: 2px solid #dc8b5e;
  font-size: 13px;
}

.knowledge-sphere-strategy {
  font-size: 13px;
}

.knowledge-sphere-path {
  max-height: 410px;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 8px;
  overflow: auto;
  list-style: none;
}

.knowledge-sphere-path li {
  position: relative;
  display: grid;
  grid-template-columns: 28px minmax(0, 1fr);
  gap: 2px 10px;
  padding: 10px 10px;
  border-radius: 11px;
  background: color-mix(in srgb, #ffefd6 74%, #ffffff);
  cursor: pointer;
  transition: transform 160ms ease, background 160ms ease, box-shadow 160ms ease;
}

.knowledge-sphere-path li:hover,
.knowledge-sphere-path li.active {
  background: #fadfa7;
  box-shadow: 0 10px 24px rgba(220, 139, 94, 0.12);
  transform: translateY(-1px);
}

.knowledge-sphere-path b {
  grid-row: 1 / span 3;
  display: grid;
  width: 26px;
  height: 26px;
  place-items: center;
  border-radius: 8px;
  background: #dc8b5e;
  color: #fff;
  font-size: 12px;
}

.knowledge-sphere-path span {
  min-width: 0;
  color: var(--study-ink);
  font-weight: 650;
}

.knowledge-sphere-path em {
  color: #8d4d2f;
  font-size: 12px;
  font-style: normal;
}

.knowledge-sphere-path small {
  color: var(--study-muted);
  line-height: 1.45;
}

.knowledge-sphere-stat-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.knowledge-sphere-stat-grid span {
  display: grid;
  gap: 2px;
  padding: 10px;
  border-radius: 10px;
  background: #f0cebb;
  color: #4c4139;
  font-size: 12px;
}

.knowledge-sphere-stat-grid b {
  color: #172033;
  font-size: 19px;
  font-variant-numeric: tabular-nums;
}

.knowledge-sphere-subjects span {
  padding: 5px 7px;
  border-left: 3px solid var(--subject-color);
  border-radius: 7px;
  background: color-mix(in srgb, #c4daeb 48%, #ffffff);
  color: #4c4139;
  font-size: 12px;
}

.knowledge-sphere-map p {
  font-size: 12px;
}

@media (max-width: 1180px) {
  .knowledge-sphere-layout {
    grid-template-columns: minmax(0, 1fr);
  }

  .knowledge-sphere-stage {
    min-height: 620px;
  }
}

@media (max-width: 720px) {
  .knowledge-sphere-toolbar__controls,
  .knowledge-sphere-search,
  .knowledge-sphere-select {
    width: 100%;
  }

  .knowledge-sphere-stage {
    min-height: 540px;
  }

  .knowledge-sphere-actions {
    top: auto;
    right: 12px;
    bottom: 66px;
  }

  .knowledge-sphere-badge {
    right: 12px;
    max-width: none;
  }
}
</style>
