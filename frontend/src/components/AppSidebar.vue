<template>
  <aside class="app-sidebar">
    <div class="brand">
      <div class="brand-mark">AI</div>
      <div class="brand-copy">
        <h1>智研星链</h1>
        <p>A3 多智能体学习平台</p>
      </div>
    </div>

    <el-menu
      class="tree-menu"
      :default-active="activePage"
      :default-openeds="['learning', 'classroom', 'research', 'system']"
      @select="(key: string) => emit('navigate', key)"
    >
      <el-sub-menu index="learning">
        <template #title>
          <span>学习项目</span>
        </template>
        <el-menu-item index="directions">探索方向</el-menu-item>
        <el-menu-item index="projects">项目主页</el-menu-item>
        <el-menu-item index="daily-plan">每日计划</el-menu-item>
      </el-sub-menu>

      <el-sub-menu index="classroom">
        <template #title>
          <span>学习过程</span>
        </template>
        <el-menu-item index="profile">学习画像</el-menu-item>
        <el-menu-item index="resources">资源中心</el-menu-item>
        <el-menu-item index="tutor">智能辅导</el-menu-item>
        <el-menu-item index="assessment">练习评估</el-menu-item>
      </el-sub-menu>

      <el-sub-menu index="research">
        <template #title>
          <span>科研工具</span>
        </template>
        <el-menu-item index="literature">文献知识库</el-menu-item>
        <el-menu-item index="writing">论文写作</el-menu-item>
        <el-menu-item index="methods">科研方法</el-menu-item>
      </el-sub-menu>

      <el-sub-menu index="system">
        <template #title>
          <span>系统</span>
        </template>
        <el-menu-item index="settings">账号设置</el-menu-item>
      </el-sub-menu>
    </el-menu>
  </aside>
</template>

<script setup lang="ts">
defineProps<{
  activePage: string
}>()

const emit = defineEmits<{
  navigate: [page: string]
}>()
</script>
