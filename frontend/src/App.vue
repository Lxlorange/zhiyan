<template>
  <AppLayout
    :active-page="activePage"
    :user="user"
    @navigate="activePage = $event"
    @logout="handleLogout"
  >
    <DirectionPage v-if="activePage === 'directions'" />
    <SettingsPage
      v-else-if="activePage === 'settings'"
      :user="user"
      @saved="handleUserSaved"
    />
    <PlaceholderPage
      v-else
      :title="currentMeta.title"
      :description="currentMeta.description"
    />
  </AppLayout>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import AppLayout from './components/AppLayout.vue'
import DirectionPage from './pages/DirectionPage.vue'
import SettingsPage from './pages/SettingsPage.vue'
import PlaceholderPage from './pages/PlaceholderPage.vue'
import { clearAuth, getCurrentUser, readStoredUser, type User } from './api'

const activePage = ref('directions')
const user = ref<User | null>(readStoredUser())

const pageMeta: Record<string, { title: string; description: string }> = {
  projects: { title: '学习项目', description: '这里将集中管理研究方向、项目首页、清单版本和学习进度。' },
  path: { title: '学习清单', description: '这里将承载个性化学习清单、路径调整、每日计划和版本管理。' },
  profile: { title: '学习画像', description: '这里将维护后台画像条目、画像版本和知识短板。' },
  resources: { title: '资源中心', description: '这里将展示多 Agent 生成的文档、题库、案例、视频脚本和拓展阅读。' },
  tutor: { title: '智能辅导', description: '这里将提供围绕课堂内容的连续对话式辅导。' },
  assessment: { title: '练习评估', description: '这里将展示答题记录、评分反馈和画像更新。' },
  workflow: { title: '完整链路', description: '完整链路作为调试入口保留，不再放在顶栏作为主操作。' },
  teacher: { title: '教师驾驶舱', description: '这里将面向教师展示班级进度、风险学生和教学建议。' }
}

const currentMeta = computed(() => pageMeta[activePage.value] || pageMeta.projects)

onMounted(async () => {
  try {
    const { data } = await getCurrentUser()
    user.value = data
  } catch {
    user.value = null
  }
})

function handleUserSaved(nextUser: User) {
  user.value = nextUser
}

function handleLogout() {
  clearAuth()
  user.value = null
  ElMessage.success('已退出登录')
}
</script>
