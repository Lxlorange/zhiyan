<template>
  <aside class="app-sidebar" :class="{ 'is-collapsed': collapsed }">
    <div class="brand">
      <div class="brand-mark">AI</div>
      <div class="brand-copy">
        <h1>智研星链</h1>
        <p>A3 多智能体学习平台</p>
      </div>
      <button
        class="sidebar-collapse-btn"
        type="button"
        :aria-label="collapsed ? '展开侧边栏' : '收起侧边栏'"
        @click="emit('toggle-collapse')"
      >
        <span aria-hidden="true">{{ collapsed ? '>' : '<' }}</span>
      </button>
    </div>

    <el-menu
      class="tree-menu"
      :collapse="collapsed"
      :collapse-transition="false"
      :default-active="activePage"
      :default-openeds="['learning', 'classroom', 'system']"
      @select="(key: string) => emit('navigate', key)"
    >
      <el-sub-menu index="learning">
        <template #title>
          <span class="nav-glyph nav-glyph-learning" aria-hidden="true"></span>
          <span class="nav-label">学习项目</span>
        </template>
        <el-menu-item index="directions">探索方向</el-menu-item>
        <el-menu-item index="projects">项目主页</el-menu-item>
        <el-menu-item index="daily-plan">每日计划</el-menu-item>
      </el-sub-menu>

      <el-sub-menu index="classroom">
        <template #title>
          <span class="nav-glyph nav-glyph-classroom" aria-hidden="true"></span>
          <span class="nav-label">学习过程</span>
        </template>
        <el-menu-item index="profile">学习画像</el-menu-item>
        <el-menu-item index="resources">数据库</el-menu-item>
        <el-menu-item index="assessment">练习题目生成</el-menu-item>
      </el-sub-menu>

      <el-sub-menu index="system">
        <template #title>
          <span class="nav-glyph nav-glyph-system" aria-hidden="true"></span>
          <span class="nav-label">系统</span>
        </template>
        <el-menu-item index="agents">任务中心</el-menu-item>
        <el-menu-item index="settings">账号设置</el-menu-item>
      </el-sub-menu>
    </el-menu>
  </aside>
</template>

<script setup lang="ts">
defineProps<{
  activePage: string
  collapsed: boolean
}>()

const emit = defineEmits<{
  navigate: [page: string]
  'toggle-collapse': []
}>()
</script>
