<template>
  <div class="page">
    <section class="page-hero">
      <p class="eyebrow">Account Settings</p>
      <h2>账号设置</h2>
    </section>

    <el-row :gutter="20">
      <el-col :lg="14" :md="24">
        <el-card shadow="never" class="panel">
          <template #header>
            <div class="card-header">
              <strong>个人资料</strong>
              <span>Profile</span>
            </div>
          </template>
          <el-form label-position="top">
            <el-form-item label="姓名">
              <el-input v-model="form.full_name" />
            </el-form-item>
            <el-form-item label="邮箱">
              <el-input v-model="form.email" />
            </el-form-item>
            <el-form-item label="头像 URL">
              <el-input v-model="form.avatar_url" placeholder="https://..." />
            </el-form-item>
            <el-form-item label="学校">
              <el-input v-model="form.school" />
            </el-form-item>
            <el-form-item label="专业">
              <el-input v-model="form.major" />
            </el-form-item>
            <el-form-item label="个人简介">
              <el-input v-model="form.bio" type="textarea" :rows="4" />
            </el-form-item>
            <el-button type="primary" :loading="saving" @click="handleSave">保存账号信息</el-button>
          </el-form>
        </el-card>
      </el-col>

      <el-col :lg="10" :md="24">
        <el-card shadow="never" class="panel">
          <template #header>
            <div class="card-header">
              <strong>信息预览</strong>
              <span>Preview</span>
            </div>
          </template>
          <div class="profile-preview">
            <el-avatar :src="form.avatar_url || undefined" :size="64">{{ avatarText }}</el-avatar>
            <div>
              <h3>{{ form.full_name || props.user?.username || '未登录' }}</h3>
              <p>{{ props.user?.username || '-' }} / {{ form.email || '-' }}</p>
              <p>{{ form.school || '未填写学校' }} · {{ form.major || '未填写专业' }}</p>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { saveAuth, updateCurrentUser, type User } from '../api'
import { ref } from 'vue'

const props = defineProps<{ user: User | null }>()
const emit = defineEmits<{ saved: [user: User] }>()

const saving = ref(false)
const form = reactive({
  full_name: '',
  email: '',
  avatar_url: '',
  school: '',
  major: '',
  bio: ''
})

const avatarText = computed(() => (form.full_name || props.user?.username || 'U').slice(0, 1).toUpperCase())

watch(
  () => props.user,
  (user) => {
    if (!user) return
    form.full_name = user.full_name || ''
    form.email = user.email || ''
    form.avatar_url = user.avatar_url || ''
    form.school = user.school || ''
    form.major = user.major || ''
    form.bio = user.bio || ''
  },
  { immediate: true }
)

async function handleSave() {
  saving.value = true
  try {
    const { data } = await updateCurrentUser(form)
    const token = localStorage.getItem('access_token') || ''
    saveAuth({ access_token: token, token_type: 'bearer', user: data })
    emit('saved', data)
    ElMessage.success('账号信息已保存')
  } finally {
    saving.value = false
  }
}
</script>
