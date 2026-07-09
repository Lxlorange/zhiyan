<template>
  <LoginPage
    v-if="!checkingAuth && (!user || currentPage === 'signin')"
    @authenticated="handleAuthenticated"
  />

  <main v-else-if="checkingAuth" class="auth-loading">
    <span class="auth-loading-dot" aria-hidden="true" />
    <span>正在确认登录状态...</span>
  </main>

  <AppShell
    v-else
    :active-page="currentPage"
    :title="currentMeta.title"
    :subtitle="currentMeta.subtitle"
    :user="user"
    @navigate="handleNavigate"
    @logout="handleLogout"
  >
    <RouterView v-slot="{ Component, route }">
      <component
        :is="Component"
        v-if="Component"
        :key="route.fullPath"
        v-bind="routeProps"
        @project-built="handleProjectBuilt"
        @open-syllabus="handleOpenSyllabus"
        @saved="handleUserSaved"
      />
    </RouterView>
  </AppShell>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { RouterView, useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import AppShell from './components/AppShell.vue'
import LoginPage from './pages/LoginPage.vue'
import { pageMeta, pageRouteNames } from './router'
import { clearAuth, getCurrentUser, readStoredUser, type LearningProjectRead, type User } from './services/apiClient'

const route = useRoute()
const router = useRouter()

const user = ref<User | null>(readStoredUser())
const checkingAuth = ref(Boolean(user.value))
const selectedProjectId = computed(() => normalizeProjectId(route.params.projectId))
const selectedItemId = computed(() => normalizeProjectId(route.params.itemId))
const currentPage = computed(() => String(route.meta.page || 'directions'))
const currentMeta = computed(() => pageMeta[currentPage.value] || pageMeta.directions)
const routeProps = computed(() => {
  if (currentPage.value === 'projects') return { selectedProjectId: selectedProjectId.value }
  if (currentPage.value === 'syllabus') return { projectId: selectedProjectId.value }
  if (currentPage.value === 'classroom') return { projectId: selectedProjectId.value, itemId: selectedItemId.value }
  if (currentPage.value === 'settings') return { user: user.value }
  if (!['directions', 'projects', 'syllabus', 'classroom', 'settings', 'signin'].includes(currentPage.value)) {
    return {
      title: currentMeta.value.title,
      description: currentMeta.value.description,
      highlights: currentMeta.value.highlights
    }
  }
  return {}
})

onMounted(async () => {
  if (!user.value) {
    checkingAuth.value = false
    if (currentPage.value !== 'signin') await router.replace({ name: 'signin', query: { from: route.fullPath } })
    return
  }

  try {
    const { data } = await getCurrentUser()
    user.value = data
  } catch {
    clearAuth()
    user.value = null
    if (currentPage.value !== 'signin') await router.replace({ name: 'signin', query: { from: route.fullPath } })
  } finally {
    checkingAuth.value = false
  }
})

watch(
  () => [user.value, currentPage.value, route.fullPath] as const,
  async ([nextUser, nextPage]) => {
    if (checkingAuth.value) return
    if (!nextUser && nextPage !== 'signin') {
      await router.replace({ name: 'signin', query: { from: route.fullPath } })
    }
    if (nextUser && nextPage === 'signin') {
      await router.replace(resolvePostLoginRoute())
    }
  }
)

function normalizeProjectId(value: unknown): number | null {
  const raw = Array.isArray(value) ? value[0] : value
  const id = Number(raw)
  return Number.isFinite(id) && id > 0 ? id : null
}

function resolvePostLoginRoute() {
  const from = typeof route.query.from === 'string' ? route.query.from : ''
  if (from && from.startsWith('/') && !from.startsWith('/signin')) return from
  return { name: 'directions' }
}

async function handleAuthenticated(nextUser: User) {
  user.value = nextUser
  await router.replace(resolvePostLoginRoute())
}

function handleUserSaved(nextUser: User) {
  user.value = nextUser
}

async function handleNavigate(page: string) {
  const routeName = pageRouteNames[page]
  if (!routeName) return
  await router.push({ name: routeName })
}

async function handleProjectBuilt(project: LearningProjectRead) {
  await router.push({ name: 'project-detail', params: { projectId: project.id } })
}

async function handleOpenSyllabus(projectId: number) {
  await router.push({ name: 'project-syllabus', params: { projectId } })
}

async function handleLogout() {
  clearAuth()
  user.value = null
  await router.replace({ name: 'signin' })
  ElMessage.success('已退出登录')
}
</script>
