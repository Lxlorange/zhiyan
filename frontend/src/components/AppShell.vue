<template>
  <el-container class="app-shell" :class="{ 'sidebar-collapsed': sidebarCollapsed }">
    <AppSidebar
      :active-page="activePage"
      :collapsed="sidebarCollapsed"
      @toggle-collapse="sidebarCollapsed = !sidebarCollapsed"
      @navigate="emit('navigate', $event)"
    />

    <el-container class="content-shell">
      <AppTopbar
        :title="title"
        :subtitle="subtitle"
        :user="user"
        @navigate="emit('navigate', $event)"
        @logout="emit('logout')"
      />
      <el-main class="app-main">
        <slot />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import AppSidebar from './AppSidebar.vue'
import AppTopbar from './AppTopbar.vue'
import type { User } from '../services/apiClient'

defineProps<{
  activePage: string
  title: string
  subtitle: string
  user: User | null
}>()

const emit = defineEmits<{
  navigate: [page: string]
  logout: []
}>()

const sidebarCollapsed = ref(false)
</script>
