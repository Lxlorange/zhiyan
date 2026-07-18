<template>
  <section class="knowledge-sphere-panel">
    <header class="knowledge-sphere-toolbar">
      <div class="knowledge-sphere-toolbar__title">
        <strong>知识漏斗</strong>
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
        <div class="knowledge-sphere-segments" role="group" aria-label="知识漏斗视图">
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
        <el-button :loading="loading" type="primary" @click="emit('search')">刷新漏斗</el-button>
      </div>
    </header>

    <div class="knowledge-sphere-layout">
      <div class="knowledge-sphere-stage">
        <div ref="canvasHost" class="knowledge-sphere-canvas" @pointerleave="clearHover" />

        <div class="knowledge-sphere-overlay">
          <div class="knowledge-sphere-badge">
            <strong>知识漏斗</strong>
            <span>把上传资料、项目目标和练习证据汇入上层，沿先修关系筛分并收束为下一步学习路径</span>
          </div>

          <div class="knowledge-sphere-rulers" aria-hidden="true">
            <span>资料汇入</span>
            <span>概念筛分</span>
            <span>路径收束</span>
          </div>

          <div v-if="hoveredNode" class="knowledge-sphere-tooltip" :style="tooltipStyle">
            <strong>{{ hoveredNode.label }}</strong>
            <span>{{ nodeSubtitle(hoveredNode) }}</span>
            <small v-if="hoveredNode.meta?.path">路径第 {{ hoveredNode.meta.path.order }} 步</small>
          </div>

          <div class="knowledge-sphere-legend">
            <span><i class="project" />项目目标</span>
            <span><i class="document" />上传资料</span>
            <span><i class="knowledge_base" />知识点</span>
            <span><i class="path" />漏斗输出</span>
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
            <span>点击漏斗中的节点，可查看来源、前置关系、掌握证据和它在学习路径中的位置。</span>
          </template>
        </div>

        <div class="knowledge-sphere-card">
          <div class="knowledge-sphere-card-head">
            <strong>漏斗输出：个性化学习路径</strong>
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
          <strong>漏斗范围</strong>
          <div class="knowledge-sphere-stat-grid">
            <span><b>{{ graph?.nodes.length || 0 }}</b>节点</span>
            <span><b>{{ graph?.edges.length || 0 }}</b>关系</span>
            <span><b>{{ graph?.meta?.document_count || 0 }}</b>资料</span>
            <span><b>{{ activeSuggestion?.steps.length || 0 }}</b>路径步</span>
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
          <p>{{ graph?.attribution || '知识漏斗由当前用户上传知识库、项目知识点与学习画像动态聚合生成。' }}</p>
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
  { label: '资料', value: 'documents' }
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
let funnelLayer: any = null
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
  funnelLayer = new THREE.Group()
  rootLayer.add(funnelLayer, orbitLayer, linkLayer, pathLayer, nodeLayer)
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
  buildFunnelFrame()
}

function buildFunnelFrame() {
  if (!funnelLayer) return
  disposeGroup(funnelLayer)

  const topY = 270
  const midY = 20
  const bottomY = -270
  const topRadius = 300
  const midRadius = 176
  const bottomRadius = 58

  const wallMaterial = new THREE.MeshBasicMaterial({
    color: 0xc4daeb,
    transparent: true,
    opacity: 0.045,
    side: THREE.DoubleSide,
    wireframe: true
  })
  const upperWall = new THREE.Mesh(
    new THREE.CylinderGeometry(topRadius, midRadius, topY - midY, 96, 8, true),
    wallMaterial
  )
  upperWall.position.y = (topY + midY) / 2
  const lowerWall = new THREE.Mesh(
    new THREE.CylinderGeometry(midRadius, bottomRadius, midY - bottomY, 96, 8, true),
    wallMaterial.clone()
  )
  lowerWall.position.y = (midY + bottomY) / 2
  funnelLayer.add(upperWall, lowerWall)

  addFunnelRing(topY, topRadius, 0xffefd6, 0.58)
  addFunnelRing(midY, midRadius, 0xcadab2, 0.36)
  addFunnelRing(bottomY, bottomRadius, 0xdc8b5e, 0.72)

  for (let index = 0; index < 24; index += 1) {
    const angle = (index / 24) * Math.PI * 2
    const top = polarPoint(topRadius, topY, angle)
    const mid = polarPoint(midRadius, midY, angle + 0.08)
    const bottom = polarPoint(bottomRadius, bottomY, angle + 0.14)
    const line = new THREE.Line(
      new THREE.BufferGeometry().setFromPoints([top, mid, bottom]),
      new THREE.LineBasicMaterial({
        color: index % 3 === 0 ? 0xf0cebb : 0x9fb4c5,
        transparent: true,
        opacity: index % 3 === 0 ? 0.22 : 0.12
      })
    )
    funnelLayer.add(line)
  }

  ;[-160, -70, 70, 170].forEach((y, index) => {
    const radius = funnelRadiusAtY(y)
    const geometry = new THREE.BufferGeometry().setFromPoints(
      Array.from({ length: 144 }, (_, pointIndex) => {
        const angle = (pointIndex / 143) * Math.PI * 2
        const wobble = Math.sin(angle * 4 + index) * 6
        return polarPoint(radius + wobble, y, angle)
      })
    )
    const ring = new THREE.Line(
      geometry,
      new THREE.LineBasicMaterial({
        color: 0xffffff,
        transparent: true,
        opacity: 0.1
      })
    )
    funnelLayer.add(ring)
  })

  const outputGlow = new THREE.Mesh(
    new THREE.TorusGeometry(bottomRadius + 14, 5, 12, 96),
    new THREE.MeshBasicMaterial({
      color: 0xdc8b5e,
      transparent: true,
      opacity: 0.42
    })
  )
  outputGlow.position.y = bottomY - 2
  outputGlow.rotation.x = Math.PI / 2
  funnelLayer.add(outputGlow)
}

function addFunnelRing(y: number, radius: number, color: number, opacity: number) {
  const ring = new THREE.Mesh(
    new THREE.TorusGeometry(radius, y < -200 ? 2.8 : 1.6, 10, 120),
    new THREE.MeshBasicMaterial({ color, transparent: true, opacity })
  )
  ring.position.y = y
  ring.rotation.x = Math.PI / 2
  funnelLayer?.add(ring)
}

function polarPoint(radius: number, y: number, angle: number) {
  return new THREE.Vector3(Math.cos(angle) * radius, y, Math.sin(angle) * radius)
}

function funnelRadiusAtY(y: number) {
  const topY = 270
  const bottomY = -270
  const topRadius = 300
  const bottomRadius = 58
  const t = Math.max(0, Math.min(1, (topY - y) / (topY - bottomY)))
  return topRadius + (bottomRadius - topRadius) * Math.pow(t, 0.92)
}

function rebuildGraph() {
  if (!scene || !nodeLayer || !linkLayer || !orbitLayer || !props.graph) return
  disposeGraph()
  buildFunnelFrame()
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
      emissiveIntensity: isPathNode(node.id) ? 0.78 : 0.34,
      roughness: 0.28,
      metalness: node.layer === 'project' ? 0.28 : 0.08,
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
  const levels = [
    { y: 226, radius: 282, opacity: 0.18 },
    { y: 84, radius: 220, opacity: 0.12 },
    { y: -72, radius: 146, opacity: 0.11 },
    { y: -228, radius: 74, opacity: 0.18 }
  ]
  levels.forEach(({ y, radius, opacity }) => {
    const geometry = new THREE.BufferGeometry().setFromPoints(
      Array.from({ length: 160 }, (_, pointIndex) => {
        const angle = (pointIndex / 159) * Math.PI * 2
        return new THREE.Vector3(Math.cos(angle) * radius, y, Math.sin(angle) * radius)
      })
    )
    const line = new THREE.Line(
      geometry,
      new THREE.LineBasicMaterial({
        color: 0xffffff,
        transparent: true,
        opacity
      })
    )
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
    const line = new THREE.Line(
      new THREE.BufferGeometry().setFromPoints(points),
      new THREE.LineBasicMaterial({
        color: edgeColor(edge),
        transparent: true,
        opacity: isPathEdge ? 0.48 : edge.relation === 'prerequisite' ? 0.28 : 0.15
      })
    )
    line.userData.relation = edge.relation
    linkLayer.add(line)
  })
}

function rebuildPathLayer() {
  if (!pathLayer) return
  disposeGroup(pathLayer)
  const steps = activeSuggestion.value?.steps || []
  const pathEntries = steps.map((step) => nodeMap.get(step.id)).filter(Boolean) as GraphEntry[]
  if (!pathEntries.length) return

  const entryPoint = new THREE.Vector3(0, 286, 0)
  const outputPoint = new THREE.Vector3(0, -318, 0)
  const guidePoints = [
    entryPoint,
    ...pathEntries.map((entry) => entry.position),
    outputPoint
  ]

  for (let index = 0; index < guidePoints.length - 1; index += 1) {
    const current = guidePoints[index]
    const next = guidePoints[index + 1]
    const curve = new THREE.CatmullRomCurve3(curvedPoints(current, next, index === 0 ? 24 : 42))
    const tube = new THREE.Mesh(
      new THREE.TubeGeometry(curve, 42, index === guidePoints.length - 2 ? 3.8 : 2.4, 8, false),
      new THREE.MeshBasicMaterial({
        color: index === guidePoints.length - 2 ? 0xffefd6 : 0xdc8b5e,
        transparent: true,
        opacity: viewMode.value === 'documents' ? 0.18 : 0.62
      })
    )
    pathLayer.add(tube)
  }

  const output = new THREE.Mesh(
    new THREE.SphereGeometry(14, 28, 16),
    new THREE.MeshStandardMaterial({
      color: 0xffefd6,
      emissive: 0xdc8b5e,
      emissiveIntensity: 1.1,
      transparent: true,
      opacity: 0.92
    })
  )
  output.position.copy(outputPoint)
  pathLayer.add(output)
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
  if (node.layer === 'project') return projectPosition(node, index)
  if (node.layer === 'document') return documentPosition(node, index)
  if (node.layer === 'knowledge_base') return knowledgeBasePosition(node, index)
  return knowledgeBasePosition(node, index)
}

function projectPosition(node: KnowledgeLinkNode, index: number) {
  const count = Math.max(1, props.graph?.nodes.filter((item) => item.layer === 'project').length || 1)
  const angle = (index / count) * Math.PI * 2 + 0.34
  const radius = 190 + (hashString(node.id) % 70)
  return new THREE.Vector3(Math.cos(angle) * radius, 218 + ((index % 3) - 1) * 24, Math.sin(angle) * radius)
}

function documentPosition(node: KnowledgeLinkNode, index: number) {
  const count = Math.max(1, props.graph?.nodes.filter((item) => item.layer === 'document').length || 1)
  const hash = hashString(node.id)
  const angle = (index / count) * Math.PI * 2 + ((hash % 17) / 17) * 0.2
  const y = 124 + ((hash % 130) - 65)
  const radius = funnelRadiusAtY(y) - 18 - (hash % 54)
  return new THREE.Vector3(Math.cos(angle) * radius, y, Math.sin(angle) * radius)
}

function knowledgeBasePosition(node: KnowledgeLinkNode, index: number) {
  const hash = hashString(`${node.category}:${node.id}`)
  const categoryAngle = ((hashString(node.category || 'kb') % 360) / 360) * Math.PI * 2
  const angle = categoryAngle + index * 0.23
  const difficulty = String(node.meta?.difficulty || '').toLowerCase()
  const path = node.meta?.path as Record<string, unknown> | undefined
  if (path?.order) {
    const order = Math.max(1, Number(path.order || 1))
    const steps = Math.max(1, activeSuggestion.value?.steps.length || 1)
    const t = steps <= 1 ? 0.86 : Math.min(1, (order - 1) / Math.max(1, steps - 1))
    const y = 120 - t * 360
    const radius = Math.max(42, funnelRadiusAtY(y) * (0.62 - t * 0.28))
    const pathAngle = categoryAngle + order * 0.62
    return new THREE.Vector3(Math.cos(pathAngle) * radius, y, Math.sin(pathAngle) * radius)
  }
  const baseY = difficulty.includes('hard') || difficulty.includes('困难') ? -84 : difficulty.includes('easy') || difficulty.includes('基础') ? 82 : 0
  const y = baseY + ((hash % 96) - 48)
  const radius = Math.max(70, funnelRadiusAtY(y) - 50 - (hash % 78))
  return new THREE.Vector3(Math.cos(angle) * radius, y, Math.sin(angle) * radius)
}

function nodeRadius(node: KnowledgeLinkNode) {
  const weight = Math.max(1, Number(node.weight || 1))
  const pathBoost = isPathNode(node.id) ? 4 : 0
  if (node.layer === 'project') return 18 + pathBoost
  if (node.layer === 'document') return 12 + Math.min(10, Math.log(weight + 1) * 2.6) + pathBoost
  if (node.layer === 'knowledge_base') return 9 + Math.min(11, Math.log(weight + 1) * 3) + pathBoost
  return 6 + Math.min(9, Math.log(weight + 1) * 3.2) + pathBoost
}

function createHalo(node: KnowledgeLinkNode, color: number) {
  if (!isPathNode(node.id) && node.layer !== 'project' && node.layer !== 'document') return null
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
  const isImportant = node.layer === 'project' || node.layer === 'document' || isPathNode(node.id)
  if (!isImportant) return null
  const label = document.createElement('span')
  label.className = `knowledge-sphere-label ${node.layer === 'project' ? 'is-project' : node.layer === 'document' ? 'is-document' : 'is-path'}`
  label.textContent = node.meta?.path?.order ? `${node.meta.path.order}. ${node.label}` : node.label
  return new CSS2DObject(label)
}

function nodeColor(node: KnowledgeLinkNode) {
  if (node.layer === 'project') return 0xdc8b5e
  if (node.layer === 'document') return 0xfadfa7
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
  if (edge.relation === 'aligns') return 0xcadab2
  if (edge.relation === 'maps_to') return 0xc4daeb
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
    if (halo) halo.visible = viewMode.value !== 'documents' || node.layer === 'document' || isPathNode(node.id)
    if (label) label.visible = viewMode.value !== 'documents' || node.layer === 'document' || isPathNode(node.id)
  })
}

function highlightSelected() {
  const selectedId = props.selectedNodeId || selectedNode.value?.id || ''
  nodeMap.forEach(({ mesh, halo, node }) => {
    const material = mesh.material as any
    const active = node.id === selectedId
    const path = isPathNode(node.id)
    mesh.scale.setScalar(active ? 1.38 : path ? 1.12 : 1)
    material.emissiveIntensity = active ? 1.08 : path ? 0.82 : 0.34
    if (halo) halo.scale.setScalar(active ? 1.18 : 1)
  })
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
  if (node.layer === 'knowledge_base') return `知识点 · ${node.category || '知识库'}`
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
    radial-gradient(circle at 52% 24%, rgba(196, 218, 235, 0.16), transparent 26%),
    radial-gradient(circle at 53% 77%, rgba(220, 139, 94, 0.16), transparent 22%),
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

.knowledge-sphere-rulers {
  position: absolute;
  top: 120px;
  bottom: 116px;
  left: 16px;
  display: grid;
  align-content: space-between;
  color: rgba(255, 255, 255, 0.5);
  font-size: 12px;
  pointer-events: none;
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
