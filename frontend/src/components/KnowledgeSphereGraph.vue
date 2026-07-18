<template>
  <section class="knowledge-sphere-panel">
    <div
      ref="canvasHost"
      class="knowledge-sphere-stage"
      @pointerdown="handlePointerDown"
      @pointermove="handlePointerMove"
      @pointerup="handlePointerUp"
      @pointercancel="handlePointerCancel"
      @pointerleave="handlePointerLeave"
      @wheel="handleWheel"
    >
      <canvas ref="canvasRef" class="knowledge-sphere-canvas" />

      <div class="knowledge-sphere-overlay">
        <div v-if="categoryChips.length" class="knowledge-sphere-legend" aria-label="知识分类图例">
          <button
            v-for="item in categoryChips"
            :key="item.key"
            type="button"
            :class="{ off: !activeCategories.has(item.key) }"
            :aria-pressed="activeCategories.has(item.key)"
            @click.stop="toggleCategory(item.key)"
          >
            <i :style="{ background: item.color }" />
            <span>{{ item.label }}</span>
            <b>{{ item.count }}</b>
          </button>
        </div>

        <article
          v-if="selectedNode"
          class="knowledge-sphere-popover"
          :style="selectedPanelStyle"
          @pointerdown.stop
        >
          <button type="button" class="knowledge-sphere-popover__close" @click.stop="clearSelection">×</button>
          <div class="knowledge-sphere-popover__tags">
            <small v-for="tag in selectedTags" :key="tag">{{ tag }}</small>
          </div>
          <h3>{{ selectedNode.label }}</h3>
          <p>{{ selectedDescription }}</p>
          <strong>需要 {{ selectedPrerequisites.length }} 个前置节点</strong>
          <div class="knowledge-sphere-popover__parents">
            <span v-for="node in selectedPrerequisites" :key="node.id">{{ node.label }}</span>
            <em v-if="!selectedPrerequisites.length">无直系父节点</em>
          </div>
        </article>

        <span v-if="loading" class="knowledge-sphere-loading">更新中</span>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'
import type {
  KnowledgeLinkEdge,
  KnowledgeLinkGraphResponse,
  KnowledgeLinkNode
} from '../services/apiClient'

type Vec3 = {
  x: number
  y: number
  z: number
}
type WorldNode = Vec3 & {
  index: number
  node: KnowledgeLinkNode
  color: string
  rgb: [number, number, number]
  radius: number
  categoryKey: string
  appear: number
  countWeight: number
  driftSeed: number
}
type WorldEdge = {
  index: number
  source: number
  target: number
  edge: KnowledgeLinkEdge
  path: boolean
}
type ProjectedNode = {
  sx: number
  sy: number
  pf: number
  radius: number
  visible: boolean
}
type CategoryChip = {
  key: string
  label: string
  color: string
  count: number
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

const FOV = 1400
const WORLD_HEIGHT = 980
const SPIN_SPEED = 0.00018
const MAX_DRAW_EDGES = 900
const palette = ['#dc8b5e', '#2f7fa3', '#6f8f49', '#b99126', '#b76577', '#5f6fb0', '#a05a34', '#4f8b78']

const canvasHost = ref<HTMLDivElement | null>(null)
const canvasRef = ref<HTMLCanvasElement | null>(null)
const selectedNode = ref<KnowledgeLinkNode | null>(null)
const autoRotate = ref(true)
const activeCategories = shallowRef<Set<string>>(new Set())
const categoryChips = ref<CategoryChip[]>([])
const selectedPanelStyle = ref<Record<string, string>>({})

let context: CanvasRenderingContext2D | null = null
let resizeObserver: ResizeObserver | null = null
let animationFrame = 0
let dpr = 1
let width = 0
let height = 0
let reduceMotion = false
let startedAt = 0
let lastFrameAt = 0
let grow = 0
let driftTime = 0
let rotY = 0.58
let tilt = -0.32
let zoom = 1
let rotYTarget: number | null = null
let tiltTarget: number | null = null
let zoomTarget: number | null = null
let dragging = false
let moved = false
let lastPointerX = 0
let lastPointerY = 0
let pinchDistance = 0
let hoverIndex = -1

const pointers = new Map<number, [number, number]>()
const worldNodes: WorldNode[] = []
const projectedNodes: ProjectedNode[] = []
const worldEdges: WorldEdge[] = []
const nodeIndexById = new Map<string, number>()
const directPre = new Map<string, string[]>()
let lineageNodes = new Set<string>()
let lineageEdges = new Set<number>()

const pathNodeIds = computed(() => new Set((props.graph?.path_suggestions[0]?.steps || []).map((step) => step.id)))

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

const selectedTags = computed<string[]>(() => {
  if (!selectedNode.value) return []
  const node = selectedNode.value
  const meta = node.meta || {}
  const tags = Array.isArray(meta.tags) ? meta.tags.map((item) => String(item)).filter(Boolean) : []
  return [categoryLabel(categoryKey(node)), ...tags]
    .filter((item, index, array) => item && array.indexOf(item) === index)
    .slice(0, 7)
})

const selectedPrerequisites = computed(() => relatedNodes(selectedNode.value?.id || '', directPre))

watch(
  () => props.graph,
  async () => {
    await nextTick()
    restartGrowth()
    rebuildWorldGraph()
  },
  { deep: true }
)

watch(
  () => props.selectedNodeId,
  (id) => {
    if (!id || !props.graph) {
      selectedNode.value = null
      buildLineage('')
      return
    }
    selectedNode.value = props.graph.nodes.find((item) => item.id === id) || null
    buildLineage(selectedNode.value?.id || '')
    if (selectedNode.value) focusNode(selectedNode.value.id)
  }
)

watch(pathNodeIds, () => {
  rebuildWorldGraph()
})

onMounted(async () => {
  await nextTick()
  reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  context = canvasRef.value?.getContext('2d') || null
  resizeCanvas()
  rebuildWorldGraph()
  startedAt = performance.now()
  lastFrameAt = startedAt
  animationFrame = requestAnimationFrame(frame)
  resizeObserver = new ResizeObserver(() => resizeCanvas())
  if (canvasHost.value) resizeObserver.observe(canvasHost.value)
})

onBeforeUnmount(() => {
  if (animationFrame) cancelAnimationFrame(animationFrame)
  resizeObserver?.disconnect()
})

function restartGrowth() {
  startedAt = performance.now()
  lastFrameAt = startedAt
  grow = reduceMotion ? 1 : 0
}

function rebuildWorldGraph() {
  worldNodes.length = 0
  projectedNodes.length = 0
  worldEdges.length = 0
  nodeIndexById.clear()
  directPre.clear()

  const graph = props.graph
  if (!graph) {
    categoryChips.value = []
    return
  }

  const categories = buildCategoryChips(graph.nodes)
  categoryChips.value = categories
  syncActiveCategories(categories.map((item) => item.key))

  const levels = graph.nodes.map((node) => Math.max(0, Number(node.meta?.dag_level || 0)))
  const maxLevel = Math.max(1, ...levels)
  const layerLocalIndex = new Map<string, number>()
  const levelBuckets = buildLevelBuckets(graph.nodes)
  const isolatedNodes = graph.nodes.filter((node) => node.meta?.is_isolated)

  const ordered = [...graph.nodes].sort((left, right) => {
    const levelDelta = Number(left.meta?.dag_level || 0) - Number(right.meta?.dag_level || 0)
    if (levelDelta !== 0) return levelDelta
    return hashString(left.id) - hashString(right.id)
  })

  ordered.forEach((node) => {
    const key = `${node.layer}:${node.meta?.dag_level || 0}:${node.category || ''}`
    const index = layerLocalIndex.get(key) || 0
    layerLocalIndex.set(key, index + 1)
    const position = positionForNode(node, index, maxLevel, levelBuckets, isolatedNodes)
    const color = nodeColor(node)
    const worldNode: WorldNode = {
      index: worldNodes.length,
      node,
      color,
      rgb: hexToRgb(color),
      radius: nodeRadius(node),
      categoryKey: categoryKey(node),
      appear: Math.min(1, Math.max(0, position.y / WORLD_HEIGHT)),
      countWeight: Math.max(1, Number(node.weight || 1)),
      driftSeed: hashString(`${node.id}:drift`) % 10000,
      ...position
    }
    nodeIndexById.set(node.id, worldNode.index)
    worldNodes.push(worldNode)
    projectedNodes.push({ sx: 0, sy: 0, pf: 1, radius: worldNode.radius, visible: false })
  })

  relaxFunnelForces(graph, maxLevel)

  graph.edges.slice(0, MAX_DRAW_EDGES).forEach((edge, index) => {
    const source = nodeIndexById.get(edge.source)
    const target = nodeIndexById.get(edge.target)
    if (source === undefined || target === undefined) return
    const path = pathNodeIds.value.has(edge.source) && pathNodeIds.value.has(edge.target)
    worldEdges.push({ index, source, target, edge, path })
    if (edge.relation === 'prerequisite') {
      pushRelation(directPre, edge.target, edge.source)
    }
  })

  buildLineage(selectedNode.value?.id || props.selectedNodeId || '')
}

function relaxFunnelForces(graph: KnowledgeLinkGraphResponse, maxLevel: number) {
  if (worldNodes.length < 3) return
  const velocity = worldNodes.map(() => ({ x: 0, y: 0, z: 0 }))
  const springs = graph.edges
    .slice(0, MAX_DRAW_EDGES)
    .map((edge) => ({
      edge,
      source: nodeIndexById.get(edge.source),
      target: nodeIndexById.get(edge.target)
    }))
    .filter((item): item is { edge: KnowledgeLinkEdge; source: number; target: number } => (
      item.source !== undefined && item.target !== undefined
    ))

  for (let pass = 0; pass < 72; pass += 1) {
    const cooling = 1 - pass / 84
    for (let left = 0; left < worldNodes.length; left += 1) {
      for (let right = left + 1; right < worldNodes.length; right += 1) {
        const a = worldNodes[left]
        const b = worldNodes[right]
        const dx = b.x - a.x
        const dy = (b.y - a.y) * 0.44
        const dz = b.z - a.z
        const distSq = Math.max(90, dx * dx + dy * dy + dz * dz)
        const force = Math.min(1.85, 1450 / distSq) * cooling
        const invDist = 1 / Math.sqrt(distSq)
        velocity[left].x -= dx * invDist * force
        velocity[left].z -= dz * invDist * force
        velocity[left].y -= dy * invDist * force * 0.22
        velocity[right].x += dx * invDist * force
        velocity[right].z += dz * invDist * force
        velocity[right].y += dy * invDist * force * 0.22
      }
    }

    springs.forEach(({ edge, source, target }) => {
      const a = worldNodes[source]
      const b = worldNodes[target]
      const dx = b.x - a.x
      const dy = b.y - a.y
      const dz = b.z - a.z
      const dist = Math.max(1, Math.hypot(dx, dy * 0.55, dz))
      const ideal = edge.relation === 'evidence' ? 210 : edge.relation === 'prerequisite' ? 150 : 180
      const force = (dist - ideal) * (edge.relation === 'prerequisite' ? 0.0036 : 0.0025) * cooling
      velocity[source].x += dx / dist * force
      velocity[source].z += dz / dist * force
      velocity[target].x -= dx / dist * force
      velocity[target].z -= dz / dist * force
      if (edge.relation === 'prerequisite') {
        const targetGap = Math.max(70, WORLD_HEIGHT / (maxLevel + 2))
        const desiredY = Math.min(WORLD_HEIGHT * 0.96, a.y + targetGap)
        const yPull = (desiredY - b.y) * 0.0018 * cooling
        velocity[source].y -= yPull * 0.38
        velocity[target].y += yPull
      }
    })

    worldNodes.forEach((node, index) => {
      const anchorX = node.x
      const anchorY = node.y
      const anchorZ = node.z
      const v = velocity[index]
      node.x += clamp(v.x, -8, 8)
      node.y = clamp(node.y + clamp(v.y, -5, 5), WORLD_HEIGHT * 0.05, WORLD_HEIGHT * 0.97)
      node.z += clamp(v.z, -8, 8)
      node.x += (anchorX - node.x) * 0.022
      node.y += (anchorY - node.y) * 0.052
      node.z += (anchorZ - node.z) * 0.022
      constrainToFunnel(node)
      v.x *= 0.68
      v.y *= 0.64
      v.z *= 0.68
    })
  }
}

function constrainToFunnel(node: WorldNode) {
  const yNorm = Math.min(0.98, Math.max(0.02, node.y / WORLD_HEIGHT))
  const maxRadius = 118 + (1 - yNorm) * 468
  const minRadius = node.node.layer === 'project' ? 18 : 22
  const radius = Math.hypot(node.x, node.z)
  if (radius > maxRadius) {
    const scale = maxRadius / radius
    node.x *= scale
    node.z *= scale
  } else if (radius < minRadius && node.node.layer !== 'project') {
    const angle = Math.atan2(node.z, node.x) || (node.driftSeed * 0.01)
    node.x = Math.cos(angle) * minRadius
    node.z = Math.sin(angle) * minRadius
  }
}

function buildCategoryChips(nodes: KnowledgeLinkNode[]): CategoryChip[] {
  const counts = new Map<string, number>()
  nodes.forEach((node) => {
    const key = categoryKey(node)
    counts.set(key, (counts.get(key) || 0) + 1)
  })
  return Array.from(counts.entries())
    .map(([key, count]) => ({ key, label: categoryLabel(key), color: categoryColor(key), count }))
    .sort((left, right) => right.count - left.count || left.label.localeCompare(right.label))
    .slice(0, 10)
}

function buildLevelBuckets(nodes: KnowledgeLinkNode[]) {
  const buckets = new Map<number, KnowledgeLinkNode[]>()
  nodes.forEach((node) => {
    if (node.meta?.is_isolated) return
    const level = Math.max(0, Number(node.meta?.dag_level || 0))
    const list = buckets.get(level) || []
    list.push(node)
    buckets.set(level, list)
  })
  return buckets
}

function syncActiveCategories(keys: string[]) {
  const current = activeCategories.value
  if (!current.size) {
    activeCategories.value = new Set(keys)
    return
  }
  const next = new Set<string>()
  keys.forEach((key) => {
    if (current.has(key)) next.add(key)
  })
  activeCategories.value = next.size ? next : new Set(keys)
  clearSelectionIfHidden()
}

function toggleCategory(key: string) {
  const next = new Set(activeCategories.value)
  if (next.has(key)) next.delete(key)
  else next.add(key)
  activeCategories.value = next
  clearSelectionIfHidden()
}

function clearSelectionIfHidden() {
  if (!selectedNode.value) return
  if (!activeCategories.value.has(categoryKey(selectedNode.value))) clearSelection()
}

function positionForNode(
  node: KnowledgeLinkNode,
  index: number,
  maxLevel: number,
  levelBuckets: Map<number, KnowledgeLinkNode[]>,
  isolatedNodes: KnowledgeLinkNode[]
): Vec3 {
  if (node.meta?.is_isolated) return isolatedPosition(node, isolatedNodes)

  const path = node.meta?.path as Record<string, unknown> | undefined
  if (path?.order) return pathPosition(node, path)

  if (node.layer === 'document') return evidencePosition(node, index)
  if (node.layer === 'project') return targetPosition(node, index)

  const level = Math.max(0, Number(node.meta?.dag_level || 0))
  const yNorm = Math.min(0.9, Math.max(0.08, (level + 0.28) / (maxLevel + 1)))
  const y = yNorm * WORLD_HEIGHT
  const bucket = levelBuckets.get(level) || [node]
  const localIndex = Math.max(0, bucket.findIndex((item) => item.id === node.id))
  const count = Math.max(1, bucket.length)
  const baseAngle = (localIndex / count) * Math.PI * 2
  const categoryOffset = (hashString(categoryKey(node)) % 360) / 360 * Math.PI * 2
  const angle = baseAngle + categoryOffset * 0.33 + (hashString(node.id) % 17) * 0.018
  const funnelRadius = 72 + (1 - yNorm) * 438
  const jitter = (hashString(`${node.id}:r`) % 44) - 22
  const radius = funnelRadius + jitter
  return {
    x: Math.cos(angle) * radius,
    y,
    z: Math.sin(angle) * radius
  }
}

function pathPosition(node: KnowledgeLinkNode, path: Record<string, unknown>): Vec3 {
  const order = Math.max(1, Number(path.order || 1))
  const total = Math.max(1, props.graph?.path_suggestions[0]?.steps.length || 1)
  const t = total <= 1 ? 0.5 : (order - 1) / Math.max(1, total - 1)
  const y = (0.12 + t * 0.78) * WORLD_HEIGHT
  const angle = order * 1.22 + (hashString(node.id) % 19) * 0.03
  const radius = 28 + (order % 4) * 9 + (1 - t) * 88
  return {
    x: Math.cos(angle) * radius,
    y,
    z: Math.sin(angle) * radius
  }
}

function evidencePosition(node: KnowledgeLinkNode, index: number): Vec3 {
  const angle = index * 2.399 + (hashString(node.id) % 91) * 0.01
  const radius = 395 + (hashString(`${node.id}:doc`) % 78)
  return {
    x: Math.cos(angle) * radius,
    y: WORLD_HEIGHT * (0.04 + (index % 4) * 0.025),
    z: Math.sin(angle) * radius
  }
}

function targetPosition(node: KnowledgeLinkNode, index: number): Vec3 {
  const angle = index * 2.1 + 0.6
  const radius = 72 + (hashString(node.id) % 32)
  return {
    x: Math.cos(angle) * radius,
    y: WORLD_HEIGHT * 0.95,
    z: Math.sin(angle) * radius
  }
}

function isolatedPosition(node: KnowledgeLinkNode, isolatedNodes: KnowledgeLinkNode[]): Vec3 {
  const localIndex = Math.max(0, isolatedNodes.findIndex((item) => item.id === node.id))
  const angle = localIndex * 2.399963 + (hashString(node.id) % 37) * 0.04
  const ring = 96 + (localIndex % 5) * 26
  return {
    x: 600 + Math.cos(angle) * ring * 0.72,
    y: WORLD_HEIGHT * (0.18 + ((localIndex * 7) % 61) / 100),
    z: Math.sin(angle) * ring
  }
}

function frame(ts: number) {
  animationFrame = requestAnimationFrame(frame)
  if (!context) return

  if (!reduceMotion) grow = Math.min(1.02, ((ts - startedAt) / 2800) * 1.02)
  else grow = 1

  const dt = Math.min(64, ts - lastFrameAt)
  lastFrameAt = ts
  driftTime = ts * 0.001
  if (autoRotate.value && hoverIndex < 0 && !selectedNode.value && !dragging && !reduceMotion) {
    rotY += SPIN_SPEED * dt
  }
  updateCameraTween()
  draw()
}

function updateCameraTween() {
  if (rotYTarget === null) return
  const delta = normalizedAngle(rotYTarget - rotY)
  rotY += delta * 0.12
  if (tiltTarget !== null) tilt += (tiltTarget - tilt) * 0.12
  if (zoomTarget !== null) zoom += (zoomTarget - zoom) * 0.12
  if (Math.abs(delta) < 0.008) {
    rotYTarget = null
    tiltTarget = null
    zoomTarget = null
  }
}

function draw() {
  if (!context || !width || !height) return
  const ctx = context
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
  ctx.clearRect(0, 0, width, height)
  drawBackground(ctx)
  projectNodes()
  if (selectedNode.value) updateSelectedPanelPosition(selectedNode.value.id)
  drawFunnelGuides(ctx)
  drawEdges(ctx)
  drawNodes(ctx)
}

function drawBackground(ctx: CanvasRenderingContext2D) {
  ctx.fillStyle = '#fff7ed'
  ctx.fillRect(0, 0, width, height)

  ctx.save()
  ctx.globalAlpha = 0.18
  ctx.strokeStyle = '#ead8c3'
  ctx.lineWidth = 1
  for (let x = 0; x < width; x += 64) {
    ctx.beginPath()
    ctx.moveTo(x, 0)
    ctx.lineTo(x, height)
    ctx.stroke()
  }
  for (let y = 0; y < height; y += 64) {
    ctx.beginPath()
    ctx.moveTo(0, y)
    ctx.lineTo(width, y)
    ctx.stroke()
  }
  ctx.restore()
}

function drawFunnelGuides(ctx: CanvasRenderingContext2D) {
  if (!worldNodes.length) return
  ctx.save()
  ctx.lineWidth = 1
  const levels = [0.1, 0.32, 0.54, 0.76, 0.94]
  levels.forEach((level, index) => {
    const y = level * WORLD_HEIGHT
    const radius = 72 + (1 - level) * 438
    const points: Array<{ x: number; y: number }> = []
    for (let i = 0; i <= 96; i += 1) {
      const angle = (i / 96) * Math.PI * 2
      const projected = projectPoint({ x: Math.cos(angle) * radius, y, z: Math.sin(angle) * radius })
      points.push({ x: projected.sx, y: projected.sy })
    }
    ctx.strokeStyle = index === 0 ? 'rgba(15,118,110,0.28)' : 'rgba(120,113,108,0.14)'
    ctx.beginPath()
    points.forEach((point, pointIndex) => {
      if (pointIndex === 0) ctx.moveTo(point.x, point.y)
      else ctx.lineTo(point.x, point.y)
    })
    ctx.stroke()
  })

  const axisStart = projectPoint({ x: 0, y: 0, z: 0 })
  const axisEnd = projectPoint({ x: 0, y: WORLD_HEIGHT, z: 0 })
  ctx.strokeStyle = 'rgba(120,113,108,0.18)'
  ctx.setLineDash([6, 8])
  ctx.beginPath()
  ctx.moveTo(axisStart.sx, axisStart.sy)
  ctx.lineTo(axisEnd.sx, axisEnd.sy)
  ctx.stroke()
  ctx.restore()
}

function drawEdges(ctx: CanvasRenderingContext2D) {
  const hasSelection = !!selectedNode.value
  const visibleEdges = worldEdges
    .filter((edge) => {
      const source = worldNodes[edge.source]
      const target = worldNodes[edge.target]
      return isNodeVisible(source) && isNodeVisible(target)
    })
    .sort((left, right) => {
      const leftDepth = projectedNodes[left.source].pf + projectedNodes[left.target].pf
      const rightDepth = projectedNodes[right.source].pf + projectedNodes[right.target].pf
      return leftDepth - rightDepth
    })

  ctx.save()
  visibleEdges.forEach((worldEdge) => {
    const source = projectedNodes[worldEdge.source]
    const target = projectedNodes[worldEdge.target]
    if (!source.visible || !target.visible) return

    const inLineage = lineageEdges.has(worldEdge.index)
    const sourceNode = worldNodes[worldEdge.source]
    const alpha = edgeAlpha(worldEdge, hasSelection, inLineage)
    if (alpha <= 0.01) return
    const rgb = inLineage ? sourceNode.rgb : edgeRgb(worldEdge.edge)
    const depth = Math.max(0.35, Math.min(1.15, (source.pf + target.pf) / 2))

    const pulse = reduceMotion ? 0 : Math.sin(driftTime * 1.6 + worldEdge.index * 0.37) * 0.16
    ctx.strokeStyle = `rgba(${rgb[0]}, ${rgb[1]}, ${rgb[2]}, ${Math.max(0, alpha * depth + pulse * alpha)})`
    ctx.lineWidth = inLineage || worldEdge.path ? 1.55 : worldEdge.edge.relation === 'prerequisite' ? 0.9 : 0.64
    ctx.beginPath()
    ctx.moveTo(source.sx, source.sy)
    const midX = (source.sx + target.sx) / 2
    const midY = (source.sy + target.sy) / 2
    const dx = target.sx - source.sx
    const dy = target.sy - source.sy
    const length = Math.max(1, Math.hypot(dx, dy))
    const curve = Math.min(26, length * 0.12) * (worldEdge.index % 2 ? 1 : -1)
    ctx.quadraticCurveTo(midX - dy / length * curve, midY + dx / length * curve, target.sx, target.sy)
    ctx.stroke()

    if (worldEdge.edge.relation === 'prerequisite') {
      drawArrow(ctx, source, target, `rgba(${rgb[0]}, ${rgb[1]}, ${rgb[2]}, ${Math.min(0.72, alpha * 1.25)})`)
    }
  })
  ctx.restore()
}

function drawNodes(ctx: CanvasRenderingContext2D) {
  const hasSelection = !!selectedNode.value
  const order = worldNodes
    .map((node) => node.index)
    .sort((left, right) => projectedNodes[left].pf - projectedNodes[right].pf)

  ctx.save()
  order.forEach((index) => {
    const worldNode = worldNodes[index]
    const projected = projectedNodes[index]
    if (!projected.visible || !isNodeVisible(worldNode)) return

    const node = worldNode.node
    const selected = selectedNode.value?.id === node.id
    const hovered = hoverIndex === index
    const lineage = lineageNodes.has(node.id)
    const path = pathNodeIds.value.has(node.id)
    let dim = 1
    if (hasSelection && !selected && !lineage && !path) dim = 0.14

    const r = projected.radius * (selected ? 1.55 : hovered ? 1.36 : path ? 1.18 : 1)
    const alpha = Math.min(1, dim * (0.62 + 0.38 * Math.min(1, projected.pf * projected.pf)))
    const [red, green, blue] = worldNode.rgb

    ctx.shadowBlur = selected || hovered || lineage || path ? 12 : 4
    ctx.shadowColor = `rgba(${red}, ${green}, ${blue}, ${0.26 * alpha})`
    ctx.fillStyle = `rgba(${red}, ${green}, ${blue}, ${alpha})`
    ctx.beginPath()
    ctx.arc(projected.sx, projected.sy, r, 0, Math.PI * 2)
    ctx.fill()

    ctx.shadowBlur = 0
    ctx.strokeStyle = selected || hovered || lineage || path ? '#17312c' : `rgba(23, 32, 51, ${0.2 * dim})`
    ctx.lineWidth = selected || hovered ? 1.3 : lineage || path ? 0.95 : 0.55
    ctx.beginPath()
    ctx.arc(projected.sx, projected.sy, r, 0, Math.PI * 2)
    ctx.stroke()

    if (selected || hovered) {
      ctx.strokeStyle = selected ? '#dc8b5e' : '#172033'
      ctx.lineWidth = 1.15
      ctx.beginPath()
      ctx.arc(projected.sx, projected.sy, r + 2.8, 0, Math.PI * 2)
      ctx.stroke()
    }
  })
  ctx.restore()
}

function drawArrow(ctx: CanvasRenderingContext2D, source: ProjectedNode, target: ProjectedNode, color: string) {
  const dx = target.sx - source.sx
  const dy = target.sy - source.sy
  const length = Math.hypot(dx, dy)
  if (length < 12) return
  const ux = dx / length
  const uy = dy / length
  const endX = target.sx - ux * Math.max(8, target.radius * 1.15)
  const endY = target.sy - uy * Math.max(8, target.radius * 1.15)
  const size = Math.max(3.2, Math.min(5.2, target.radius * 0.78))
  ctx.fillStyle = color
  ctx.beginPath()
  ctx.moveTo(endX, endY)
  ctx.lineTo(endX - ux * size - uy * size * 0.62, endY - uy * size + ux * size * 0.62)
  ctx.lineTo(endX - ux * size + uy * size * 0.62, endY - uy * size - ux * size * 0.62)
  ctx.closePath()
  ctx.fill()
}

function projectNodes() {
  worldNodes.forEach((node) => {
    const livePoint = dynamicPoint(node)
    const projected = projectPoint(livePoint)
    const scaleBoost = Math.min(1.24, Math.max(0.8, zoom))
    const breathe = reduceMotion ? 1 : 1 + Math.sin(driftTime * 1.8 + node.driftSeed * 0.01) * 0.055
    const radius = (0.9 + Math.sqrt(node.countWeight) * node.radius * 0.22) * projected.pf * scaleBoost * breathe
    projectedNodes[node.index] = {
      sx: projected.sx,
      sy: projected.sy,
      pf: projected.pf,
      radius: Math.max(1.5, Math.min(5.2, radius)),
      visible: node.appear <= grow || reduceMotion
    }
  })
}

function dynamicPoint(node: WorldNode): Vec3 {
  if (reduceMotion) return node
  const seed = node.driftSeed * 0.01
  const layerFloat = node.node.layer === 'project' ? 0.35 : node.node.layer === 'document' ? 0.72 : 1
  const categoryFloat = 0.72 + (hashString(node.categoryKey) % 28) / 100
  const strength = (lineageNodes.has(node.node.id) || pathNodeIds.value.has(node.node.id) ? 13 : 8) * layerFloat
  return {
    x: node.x + Math.sin(driftTime * 0.74 * categoryFloat + seed) * strength,
    y: node.y + Math.sin(driftTime * 0.48 + seed * 1.7) * strength * 0.42,
    z: node.z + Math.cos(driftTime * 0.62 * categoryFloat + seed * 1.31) * strength
  }
}

function projectPoint(point: Vec3) {
  const centeredY = WORLD_HEIGHT / 2 - point.y
  const cosY = Math.cos(rotY)
  const sinY = Math.sin(rotY)
  const cosTilt = Math.cos(tilt)
  const sinTilt = Math.sin(tilt)
  const worldScale = Math.min(width / 1520, height / 1260) * zoom
  const centerX = width * 0.5
  const centerY = height * 0.53

  const x = point.x * cosY + point.z * sinY
  const z = -point.x * sinY + point.z * cosY
  const y2 = centeredY * cosTilt - z * sinTilt
  const z2 = centeredY * sinTilt + z * cosTilt
  const pf = FOV / (FOV + z2 * worldScale * 1.6)

  return {
    sx: centerX + x * worldScale * pf,
    sy: centerY - y2 * worldScale * pf,
    pf
  }
}

function isNodeVisible(worldNode: WorldNode) {
  if (!activeCategories.value.has(worldNode.categoryKey)) return false
  return true
}

function edgeAlpha(edge: WorldEdge, hasSelection: boolean, inLineage: boolean) {
  if (hasSelection) return inLineage ? 0.72 : edge.path ? 0.3 : 0.035
  if (edge.path) return 0.58
  if (edge.edge.relation === 'prerequisite') return edge.edge.strength === 'hard' ? 0.16 : 0.1
  if (edge.edge.relation === 'evidence') return 0.07
  return 0.08
}

function pickNode(x: number, y: number) {
  let best = -1
  let bestDistance = 18 * 18
  for (let index = 0; index < worldNodes.length; index += 1) {
    const node = worldNodes[index]
    const projected = projectedNodes[index]
    if (!projected.visible || !isNodeVisible(node)) continue
    const dx = projected.sx - x
    const dy = projected.sy - y
    const distance = dx * dx + dy * dy
    const threshold = Math.max(8, projected.radius + 6)
    if (distance < threshold * threshold && distance < bestDistance) {
      best = index
      bestDistance = distance
    }
  }
  return best
}

function handlePointerDown(event: PointerEvent) {
  if (!canvasHost.value) return
  if (event.target !== canvasRef.value) return
  pointers.set(event.pointerId, [event.clientX, event.clientY])
  canvasHost.value.setPointerCapture(event.pointerId)
  dragging = true
  moved = false
  lastPointerX = event.clientX
  lastPointerY = event.clientY
}

function handlePointerMove(event: PointerEvent) {
  if (!canvasHost.value) return
  if (event.target !== canvasRef.value && !pointers.has(event.pointerId)) return
  if (pointers.has(event.pointerId)) pointers.set(event.pointerId, [event.clientX, event.clientY])

  if (pointers.size === 2) {
    const [first, second] = Array.from(pointers.values())
    const distance = Math.hypot(first[0] - second[0], first[1] - second[1])
    if (pinchDistance) zoom = clamp(zoom * distance / pinchDistance, 0.54, 3.8)
    pinchDistance = distance
    dragging = false
    moved = true
    return
  }

  if (dragging) {
    const dx = event.clientX - lastPointerX
    const dy = event.clientY - lastPointerY
    if (Math.abs(dx) + Math.abs(dy) > 3) moved = true
    rotY += dx * 0.0055
    tilt = clamp(tilt - dy * 0.003, -1.08, 0.18)
    lastPointerX = event.clientX
    lastPointerY = event.clientY
    return
  }

  updateHover(event)
}

function handlePointerUp(event: PointerEvent) {
  if (!pointers.has(event.pointerId)) return
  pointers.delete(event.pointerId)
  if (pointers.size < 2) pinchDistance = 0
  if (!moved) selectFromPointer(event)
  dragging = false
}

function handlePointerCancel(event: PointerEvent) {
  if (!pointers.has(event.pointerId)) return
  pointers.delete(event.pointerId)
  dragging = false
  pinchDistance = 0
}

function handlePointerLeave() {
  dragging = false
  pointers.clear()
  pinchDistance = 0
  clearHover()
}

function handleWheel(event: WheelEvent) {
  if (event.target !== canvasRef.value) return
  event.preventDefault()
  zoom = clamp(zoom * Math.exp(-event.deltaY * 0.0015), 0.54, 3.8)
}

function updateHover(event: PointerEvent) {
  if (!canvasHost.value) return
  const rect = canvasHost.value.getBoundingClientRect()
  const index = pickNode(event.clientX - rect.left, event.clientY - rect.top)
  hoverIndex = index
  if (index < 0) {
    clearHover()
    return
  }
  canvasHost.value.style.cursor = 'pointer'
}

function selectFromPointer(event: PointerEvent) {
  if (!canvasHost.value) return
  const rect = canvasHost.value.getBoundingClientRect()
  const index = pickNode(event.clientX - rect.left, event.clientY - rect.top)
  if (index < 0) {
    clearSelection()
    return
  }
  selectNode(worldNodes[index].node.id, true)
}

function clearHover() {
  hoverIndex = -1
  if (canvasHost.value) canvasHost.value.style.cursor = 'grab'
}

function clearSelection() {
  selectedNode.value = null
  emit('select-node', null)
  buildLineage('')
  selectedPanelStyle.value = {}
}

function selectNode(nodeId: string, shouldEmit: boolean) {
  const node = props.graph?.nodes.find((item) => item.id === nodeId) || null
  if (!node) return
  selectedNode.value = node
  buildLineage(node.id)
  focusNode(node.id)
  updateSelectedPanelPosition(node.id)
  if (shouldEmit) emit('select-node', node)
}

function buildLineage(nodeId: string) {
  lineageNodes = new Set<string>()
  lineageEdges = new Set<number>()
  if (!nodeId) return
  const queue = [nodeId]
  lineageNodes.add(nodeId)
  while (queue.length) {
    const current = queue.shift()
    if (!current) continue
    for (const edge of worldEdges) {
      if (edge.edge.relation !== 'prerequisite') continue
      if (edge.edge.target !== current) continue
      lineageEdges.add(edge.index)
      if (!lineageNodes.has(edge.edge.source)) {
        lineageNodes.add(edge.edge.source)
        queue.push(edge.edge.source)
      }
    }
  }
}

function focusNode(nodeId: string) {
  const index = nodeIndexById.get(nodeId)
  if (index === undefined) return
  const node = worldNodes[index]
  let best = rotY
  let bestDepth = Infinity
  for (const candidate of [Math.atan2(-node.x, node.z), Math.atan2(-node.x, node.z) + Math.PI]) {
    const z = -node.x * Math.sin(candidate) + node.z * Math.cos(candidate)
    if (z < bestDepth) {
      bestDepth = z
      best = candidate
    }
  }
  rotYTarget = best
  tiltTarget = -0.2
  zoomTarget = Math.max(1.45, zoom)
}

function updateSelectedPanelPosition(nodeId: string) {
  const index = nodeIndexById.get(nodeId)
  const projected = index === undefined ? null : projectedNodes[index]
  if (!projected || !projected.visible) {
    selectedPanelStyle.value = { left: '24px', top: '24px' }
    return
  }
  const panelWidth = Math.min(360, Math.max(280, width - 32))
  const left = projected.sx > width - panelWidth - 40 ? projected.sx - panelWidth - 24 : projected.sx + 24
  const top = projected.sy > height - 260 ? projected.sy - 224 : projected.sy + 22
  selectedPanelStyle.value = {
    left: `${clamp(left, 16, Math.max(16, width - panelWidth - 16))}px`,
    top: `${clamp(top, 16, Math.max(16, height - 236))}px`,
    width: `${panelWidth}px`
  }
}

function relatedNodes(nodeId: string, source: Map<string, string[]>) {
  const ids = source.get(nodeId) || []
  return ids
    .map((id) => props.graph?.nodes.find((node) => node.id === id) || null)
    .filter((node): node is KnowledgeLinkNode => Boolean(node))
    .slice(0, 8)
}

function pushRelation(map: Map<string, string[]>, key: string, value: string) {
  const list = map.get(key) || []
  if (!list.includes(value)) list.push(value)
  map.set(key, list)
}

function resizeCanvas() {
  const host = canvasHost.value
  const canvas = canvasRef.value
  if (!host || !canvas) return
  dpr = Math.min(window.devicePixelRatio || 1, 2)
  width = Math.max(1, host.clientWidth)
  height = Math.max(1, host.clientHeight)
  canvas.width = Math.floor(width * dpr)
  canvas.height = Math.floor(height * dpr)
  canvas.style.width = `${width}px`
  canvas.style.height = `${height}px`
  context = canvas.getContext('2d')
}

function nodeRadius(node: KnowledgeLinkNode) {
  const weight = Math.max(1, Number(node.weight || 1))
  const pathBoost = pathNodeIds.value.has(node.id) ? 0.8 : 0
  if (node.layer === 'project') return 2.8 + pathBoost
  if (node.layer === 'document') return 1.8 + Math.min(1.1, Math.log(weight + 1) * 0.24)
  if (node.layer === 'platform') return 1.8 + pathBoost
  if (node.layer === 'knowledge_base') return 2.1 + Math.min(1.4, Math.log(weight + 1) * 0.28) + pathBoost
  return 1.7 + Math.min(1.2, Math.log(weight + 1) * 0.26)
}

function nodeColor(node: KnowledgeLinkNode) {
  if (pathNodeIds.value.has(node.id)) return '#dc8b5e'
  if (node.layer === 'project') return '#dc8b5e'
  if (node.layer === 'document') return '#b99126'
  if (node.layer === 'platform') return '#6f8f49'
  return categoryColor(categoryKey(node))
}

function categoryKey(node: KnowledgeLinkNode) {
  if (node.layer === 'platform') return '平台功能介绍'
  return String(node.category || node.meta?.subject || node.layer || '知识点')
}

function categoryLabel(key: string) {
  return key.replace(/^知识库[:：]/, '') || '知识点'
}

function categoryColor(key: string) {
  if (key === '平台功能介绍') return '#6f8f49'
  if (key.includes('文献') || key.includes('论文')) return '#2f7fa3'
  if (key.includes('项目')) return '#dc8b5e'
  if (key.includes('资料') || key.includes('pdf') || key.includes('document')) return '#b99126'
  return palette[hashString(key) % palette.length]
}

function edgeRgb(edge: KnowledgeLinkEdge): [number, number, number] {
  if (edge.relation === 'prerequisite') return edge.strength === 'hard' ? [154, 85, 43] : [104, 104, 104]
  if (edge.relation === 'evidence') return [93, 121, 141]
  return [103, 127, 74]
}

function hexToRgb(color: string): [number, number, number] {
  const value = color.replace('#', '')
  const numeric = Number.parseInt(value.length === 3 ? value.split('').map((char) => char + char).join('') : value, 16)
  return [(numeric >> 16) & 255, (numeric >> 8) & 255, numeric & 255]
}

function hashString(value: string) {
  let hash = 0
  for (let i = 0; i < value.length; i += 1) {
    hash = (hash * 31 + value.charCodeAt(i)) >>> 0
  }
  return hash
}

function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value))
}

function normalizedAngle(value: number) {
  return ((value + Math.PI) % (Math.PI * 2) + Math.PI * 2) % (Math.PI * 2) - Math.PI
}
</script>

<style scoped>
.knowledge-sphere-panel {
  position: relative;
  display: block;
  grid-column: 1 / -1;
  width: 100%;
  height: 100%;
  min-height: calc(100dvh - 64px);
}

.knowledge-sphere-legend button,
.knowledge-sphere-popover__close {
  border: 0;
  border-radius: 7px;
  background: transparent;
  color: var(--study-soft, #596273);
  cursor: pointer;
  font-size: 12px;
  transition: background 180ms ease, color 180ms ease, transform 180ms ease;
}

.knowledge-sphere-stage {
  position: relative;
  width: 100%;
  height: 100%;
  min-height: calc(100dvh - 64px);
  overflow: hidden;
  background: var(--study-paper, #fff7ed);
  cursor: grab;
  touch-action: none;
}

.knowledge-sphere-stage:active {
  cursor: grabbing;
}

.knowledge-sphere-canvas {
  position: absolute;
  inset: 0;
  display: block;
}

.knowledge-sphere-overlay {
  position: absolute;
  inset: 0;
  pointer-events: none;
}

.knowledge-sphere-popover {
  position: absolute;
  z-index: 5;
  display: grid;
  gap: 10px;
  max-width: calc(100% - 32px);
  padding: 16px;
  border: 1px solid rgba(120, 113, 108, 0.18);
  border-radius: 8px;
  background: color-mix(in srgb, var(--study-surface, #fffaf2) 92%, white);
  box-shadow: 0 18px 44px rgba(80, 64, 45, 0.16);
  color: var(--study-ink, #172033);
  pointer-events: auto;
  backdrop-filter: blur(16px);
}

.knowledge-sphere-popover__close {
  position: absolute;
  top: 8px;
  right: 8px;
  width: 26px;
  height: 26px;
  color: var(--study-muted, #6d6472);
  font-size: 18px;
  line-height: 1;
}

.knowledge-sphere-popover__close:hover {
  background: rgba(120, 113, 108, 0.1);
  color: var(--study-ink, #172033);
}

.knowledge-sphere-popover__tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding-right: 24px;
}

.knowledge-sphere-popover__tags small {
  display: inline-flex;
  max-width: 100%;
  padding: 3px 6px;
  border-radius: 8px;
  background: rgba(15, 118, 110, 0.08);
  color: var(--study-muted, #6d6472);
  font-size: 11px;
  line-height: 1.35;
}

.knowledge-sphere-popover h3 {
  margin: 0;
  color: var(--study-ink, #172033);
  font-size: 20px;
  line-height: 1.28;
  letter-spacing: 0;
  text-wrap: balance;
}

.knowledge-sphere-popover p {
  margin: 0;
  color: var(--study-soft, #4c4139);
  font-size: 13px;
  line-height: 1.65;
}

.knowledge-sphere-popover > strong {
  color: var(--study-ink, #172033);
  font-size: 15px;
  font-weight: 720;
}

.knowledge-sphere-popover__parents {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
}

.knowledge-sphere-popover__parents span,
.knowledge-sphere-popover__parents em {
  display: inline-flex;
  padding: 6px 8px;
  border-radius: 8px;
  background: color-mix(in srgb, var(--study-paper, #fff7ed) 74%, white);
  color: var(--study-soft, #4c4139);
  font-size: 12px;
  font-style: normal;
}

.knowledge-sphere-legend {
  position: absolute;
  right: 18px;
  bottom: 18px;
  left: 18px;
  z-index: 4;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  max-height: 112px;
  padding: 10px;
  overflow: auto;
  border: 1px solid rgba(120, 113, 108, 0.16);
  border-radius: 8px;
  background: color-mix(in srgb, var(--study-surface, #fffaf2) 88%, white);
  box-shadow: 0 14px 34px rgba(80, 64, 45, 0.1);
  pointer-events: auto;
  backdrop-filter: blur(14px);
}

.knowledge-sphere-legend button {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 6px 8px;
  background: rgba(255, 255, 255, 0.54);
  color: var(--study-soft, #383c44);
}

.knowledge-sphere-legend button:hover {
  background: rgba(15, 118, 110, 0.08);
  color: var(--study-ink, #172033);
  transform: translateY(-1px);
}

.knowledge-sphere-legend button.off {
  opacity: 0.38;
}

.knowledge-sphere-legend i {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  box-shadow: 0 0 0 1px rgba(23, 32, 51, 0.16);
}

.knowledge-sphere-legend b {
  color: var(--study-muted, #8d4d2f);
  font-variant-numeric: tabular-nums;
}

.knowledge-sphere-loading {
  position: absolute;
  top: 18px;
  right: 18px;
  padding: 7px 10px;
  border-radius: 8px;
  background: color-mix(in srgb, var(--study-surface, #fffaf2) 88%, white);
  color: var(--study-muted, #6d6472);
  font-size: 12px;
}

@media (max-width: 720px) {
  .knowledge-sphere-panel,
  .knowledge-sphere-stage {
    min-height: calc(100dvh - 64px);
  }

  .knowledge-sphere-legend {
    right: 12px;
    bottom: 12px;
    left: 12px;
    max-height: 88px;
  }
}
</style>
