<template>
  <div class="page">
    <section class="page-hero placeholder-hero">
      <p class="eyebrow">Module</p>
      <h2>{{ title }}</h2>
      <p>{{ description }}</p>
    </section>

    <el-card shadow="never" class="panel placeholder-panel">
      <template #header>
        <div class="card-header">
          <div>
            <strong>模块规划</strong>
            <span>Next implementation</span>
          </div>
        </div>
      </template>

      <div class="placeholder-grid">
        <article v-for="item in highlights" :key="item" class="placeholder-item">
          <span></span>
          <strong>{{ item }}</strong>
          <p>后续会在该模块内接入对应的前后端 API、状态管理和数据持久化。</p>
        </article>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  title: string
  description: string
  highlights: string[]
}>()
</script>
