<template>
  <el-container class="app-shell">
    <el-aside width="272px" class="app-sidebar">
      <div class="brand">
        <div class="brand-mark">AI</div>
        <div>
          <h1>智研星链</h1>
          <p>A3 学习多智能体</p>
        </div>
      </div>

      <el-menu
        class="tree-menu"
        :default-active="activePage"
        :default-openeds="['learn', 'process', 'workspace', 'system']"
        @select="(key: string) => emit('navigate', key)"
      >
        <el-sub-menu index="learn">
          <template #title><span>学习项目</span></template>
          <el-menu-item index="directions">探索方向</el-menu-item>
          <el-menu-item index="projects">学习项目</el-menu-item>
          <el-menu-item index="path">学习清单</el-menu-item>
        </el-sub-menu>
        <el-sub-menu index="process">
          <template #title><span>学习过程</span></template>
          <el-menu-item index="profile">学习画像</el-menu-item>
          <el-menu-item index="resources">资源中心</el-menu-item>
          <el-menu-item index="tutor">智能辅导</el-menu-item>
          <el-menu-item index="assessment">练习评估</el-menu-item>
        </el-sub-menu>
        <el-sub-menu index="workspace">
          <template #title><span>工作台</span></template>
          <el-menu-item index="workflow">完整链路</el-menu-item>
          <el-menu-item index="teacher">教师驾驶舱</el-menu-item>
        </el-sub-menu>
        <el-sub-menu index="system">
          <template #title><span>系统</span></template>
          <el-menu-item index="settings">账号设置</el-menu-item>
        </el-sub-menu>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="app-topbar">
        <div>
          <strong>{{ activeTitle }}</strong>
          <span>{{ activeSubtitle }}</span>
        </div>
        <div class="topbar-actions">
          <el-button disabled>语言</el-button>
          <el-button disabled>Light</el-button>
          <el-dropdown trigger="click" @command="handleUserCommand">
            <button class="user-card" type="button">
              <el-avatar :src="user?.avatar_url || undefined">{{ avatarText }}</el-avatar>
              <span>
                <strong>{{ user?.full_name || user?.username || '未登录' }}</strong>
                <small>{{ user ? `${user.username} · ${user.role}` : 'Guest' }}</small>
              </span>
            </button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="settings">账号设置</el-dropdown-item>
                <el-dropdown-item command="logout" divided>退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>
      <el-main class="app-main">
        <slot />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { User } from '../api'

const props = defineProps<{
  activePage: string
  user: User | null
}>()

const emit = defineEmits<{
  navigate: [page: string]
  logout: []
}>()

const meta: Record<string, { title: string; subtitle: string }> = {
  directions: { title: '探索方向', subtitle: '从科研方向生成可持续学习项目' },
  projects: { title: '学习项目', subtitle: '管理方向、目标、阶段和项目首页' },
  path: { title: '学习清单', subtitle: '个性化路径规划与版本管理' },
  profile: { title: '学习画像', subtitle: '画像构建与知识短板诊断' },
  resources: { title: '资源中心', subtitle: '多 Agent 个性化资源生成' },
  tutor: { title: '智能辅导', subtitle: '围绕当前课堂的即时答疑' },
  assessment: { title: '练习评估', subtitle: '练习反馈与画像更新' },
  workflow: { title: '完整链路', subtitle: '调试画像到评估的旧链路' },
  teacher: { title: '教师驾驶舱', subtitle: '班级统计与教学建议' },
  settings: { title: '账号设置', subtitle: '管理头像、姓名、学校专业与简介' }
}

const activeTitle = computed(() => meta[props.activePage]?.title || '智研星链')
const activeSubtitle = computed(() => meta[props.activePage]?.subtitle || '')
const avatarText = computed(() => (props.user?.full_name || props.user?.username || 'U').slice(0, 1).toUpperCase())

function handleUserCommand(command: string) {
  if (command === 'settings') emit('navigate', 'settings')
  if (command === 'logout') emit('logout')
}
</script>
