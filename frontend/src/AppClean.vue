<template>
  <LoginPage v-if="!checkingAuth && !user" @authenticated="handleAuthenticated" />

  <main v-else-if="checkingAuth" class="auth-loading">
    <span class="auth-loading-dot" aria-hidden="true" />
    <span>正在确认登录状态...</span>
  </main>

  <AppShell
    v-else
    :active-page="activePage"
    :title="currentMeta.title"
    :subtitle="currentMeta.subtitle"
    :user="user"
    @navigate="activePage = $event"
    @logout="handleLogout"
  >
    <DirectionPlanner v-if="activePage === 'directions'" @project-built="handleProjectBuilt" />
    <ProjectHomePage
      v-else-if="activePage === 'projects'"
      :selected-project-id="selectedProjectId"
      @open-syllabus="handleOpenSyllabus"
    />
    <SyllabusPage v-else-if="activePage === 'syllabus'" :project-id="selectedProjectId" />
    <AccountSettings
      v-else-if="activePage === 'settings'"
      :user="user"
      @saved="handleUserSaved"
    />
    <ModulePlaceholder
      v-else
      :title="currentMeta.title"
      :description="currentMeta.description"
      :highlights="currentMeta.highlights"
    />
  </AppShell>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import AppShell from './components/AppShell.vue'
import AccountSettings from './pages/AccountSettings.vue'
import DirectionPlanner from './pages/DirectionPlanner.vue'
import LoginPage from './pages/LoginPage.vue'
import ModulePlaceholder from './pages/ModulePlaceholder.vue'
import ProjectHomePage from './pages/ProjectHomePage.vue'
import SyllabusPage from './pages/SyllabusPage.vue'
import { clearAuth, getCurrentUser, readStoredUser, type LearningProjectRead, type User } from './services/apiClient'

interface PageMeta {
  title: string
  subtitle: string
  description: string
  highlights: string[]
}

const pageMeta: Record<string, PageMeta> = {
  directions: {
    title: '探索方向',
    subtitle: '从科研方向生成可持续学习项目',
    description: '围绕一个科研或课程方向完成目标澄清、知识点拆解、资源清单和学习项目初始化。',
    highlights: ['方向理解', '知识点拆解', '学习项目建议']
  },
  projects: {
    title: '项目主页',
    subtitle: '管理方向、目标、阶段和项目进展',
    description: '这里将承载已保存的学习项目、当前阶段、待学习课堂和关键产出。',
    highlights: ['项目进度', '阶段产出', '课堂入口']
  },
  syllabus: {
    title: '学习清单',
    subtitle: '个性化路径规划与学习清单调整',
    description: '这里将展示推荐学习清单，支持拖拽调整、保存版本和生成后续课堂。',
    highlights: ['路径规划', '清单编辑', '版本保存']
  },
  'daily-plan': {
    title: '每日计划',
    subtitle: '按日承接学习任务和预生成课堂内容',
    description: '这里将把学习清单拆成每日计划，并支持后台提前生成第二天要学的资料。',
    highlights: ['每日安排', '预生成内容', '继续学习']
  },
  profile: {
    title: '学习画像',
    subtitle: '维护画像条目、画像版本和知识短板',
    description: '画像不再打断主流程，而是作为后台条目持续积累，用于个性化生成内容。',
    highlights: ['画像条目', '知识短板', '版本追踪']
  },
  resources: {
    title: '资源中心',
    subtitle: '多 Agent 个性化资源生成与管理',
    description: '这里将集中管理文档、题库、思维导图、视频脚本、实操案例等资源。',
    highlights: ['资源卡片', '多模态内容', '生成记录']
  },
  tutor: {
    title: '智能辅导',
    subtitle: '围绕当前课堂的连续对话式辅导',
    description: '这里将支持课堂内持续对话、例题讲解、可视化演示和引导式提问。',
    highlights: ['持续对话', '例题讲解', '引导追问']
  },
  assessment: {
    title: '练习评估',
    subtitle: '练习反馈、掌握度评估和画像更新',
    description: '这里将记录答题、评分、薄弱点更新和后续资源推荐策略。',
    highlights: ['答题记录', '掌握度评估', '画像更新']
  },
  literature: {
    title: '文献知识库',
    subtitle: '管理论文、笔记、引用和个人知识库',
    description: '这里将支持论文上传、引用管理、阅读笔记和文献关系整理。',
    highlights: ['文献管理', '引用格式', '知识库']
  },
  writing: {
    title: '论文写作',
    subtitle: '论文修改、格式规范、综述和引用辅助',
    description: '这里将提供论文润色、结构诊断、格式规范和综述写作辅助。',
    highlights: ['论文修改', '格式检查', '综述辅助']
  },
  methods: {
    title: '科研方法',
    subtitle: '学习实验设计、复现、评估和学术规范',
    description: '这里将沉淀科研方法课，包括如何复现论文、设计实验和评价结果。',
    highlights: ['实验设计', '论文复现', '学术规范']
  },
  settings: {
    title: '账号设置',
    subtitle: '管理头像、姓名、学校专业和简介',
    description: '这里维护学生基础信息，供顶栏展示和后续个性化画像使用。',
    highlights: ['基础信息', '头像资料', '身份上下文']
  }
}

const activePage = ref('directions')
const user = ref<User | null>(readStoredUser())
const checkingAuth = ref(Boolean(user.value))
const selectedProjectId = ref<number | null>(null)
const currentMeta = computed(() => pageMeta[activePage.value] || pageMeta.directions)

onMounted(async () => {
  if (!user.value) return
  try {
    const { data } = await getCurrentUser()
    user.value = data
  } catch {
    clearAuth()
    user.value = null
  } finally {
    checkingAuth.value = false
  }
})

function handleAuthenticated(nextUser: User) {
  user.value = nextUser
  activePage.value = 'directions'
}

function handleUserSaved(nextUser: User) {
  user.value = nextUser
}

function handleProjectBuilt(project: LearningProjectRead) {
  selectedProjectId.value = project.id
  activePage.value = 'projects'
}

function handleOpenSyllabus(projectId: number) {
  selectedProjectId.value = projectId
  activePage.value = 'syllabus'
}

function handleLogout() {
  clearAuth()
  user.value = null
  activePage.value = 'directions'
  selectedProjectId.value = null
  ElMessage.success('已退出登录')
}
</script>
