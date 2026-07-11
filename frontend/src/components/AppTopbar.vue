<template>
  <header class="app-topbar">
    <div class="topbar-title">
      <strong>{{ title }}</strong>
      <span>{{ subtitle }}</span>
    </div>

    <div class="topbar-actions">
      <el-button class="ghost-button" @click="notifyComingSoon('语言切换')">中文</el-button>
      <el-button class="ghost-button" @click="notifyComingSoon('Light / Dark')">Light</el-button>

      <el-dropdown trigger="click" @command="handleCommand">
        <button class="user-card" type="button">
          <el-avatar :src="user?.avatar_url || undefined" :size="36">{{ avatarText }}</el-avatar>
          <span class="user-copy">
            <strong>{{ displayName }}</strong>
            <small>{{ userMeta }}</small>
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
  </header>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { ElMessage } from 'element-plus'
import type { User } from '../services/apiClient'

const props = defineProps<{
  title: string
  subtitle: string
  user: User | null
}>()

const emit = defineEmits<{
  navigate: [page: string]
  logout: []
}>()

const displayName = computed(() => props.user?.full_name || props.user?.username || '未登录用户')
const avatarText = computed(() => displayName.value.slice(0, 1).toUpperCase())
const userMeta = computed(() => {
  if (!props.user) return 'Guest'
  const profile = [props.user.school, props.user.major].filter(Boolean).join(' / ')
  return profile || `${props.user.username} / ${props.user.role}`
})

function handleCommand(command: string) {
  if (command === 'settings') emit('navigate', 'settings')
  if (command === 'logout') emit('logout')
}

function notifyComingSoon(feature: string) {
  ElMessage.info(`${feature} 已预留入口，当前版本先保持中文浅色界面。`)
}
</script>
