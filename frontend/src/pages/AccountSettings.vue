<template>
  <div class="page settings-page">
    <section class="page-hero">
      <p class="eyebrow">Account Settings</p>
      <h2>账号设置</h2>
      <p>
        维护学生端基础身份信息。头像、姓名、学校和专业会展示在平台顶栏，
        后续也会作为个性化画像和资源生成的稳定上下文。
      </p>
    </section>

    <div class="settings-grid">
      <el-card shadow="never" class="panel">
        <template #header>
          <div class="card-header">
            <div>
              <strong>个人资料</strong>
              <span>Profile</span>
            </div>
          </div>
        </template>

        <el-form label-position="top">
          <el-row :gutter="16">
            <el-col :md="12" :sm="24">
              <el-form-item label="姓名">
                <el-input v-model.trim="form.full_name" placeholder="请输入展示姓名" />
              </el-form-item>
            </el-col>
            <el-col :md="12" :sm="24">
              <el-form-item label="邮箱">
                <el-input v-model.trim="form.email" placeholder="name@example.com" />
              </el-form-item>
            </el-col>
          </el-row>

          <el-form-item label="头像 URL">
            <el-input v-model.trim="form.avatar_url" placeholder="https://..." />
          </el-form-item>

          <el-row :gutter="16">
            <el-col :md="12" :sm="24">
              <el-form-item label="学校">
                <el-input v-model.trim="form.school" placeholder="例如：南京大学" />
              </el-form-item>
            </el-col>
            <el-col :md="12" :sm="24">
              <el-form-item label="专业">
                <el-input v-model.trim="form.major" placeholder="例如：人工智能" />
              </el-form-item>
            </el-col>
          </el-row>

          <el-form-item label="个人简介">
            <el-input
              v-model="form.bio"
              type="textarea"
              :rows="5"
              resize="vertical"
              placeholder="可以写你的研究兴趣、当前课程、学习目标或项目经历。"
            />
          </el-form-item>

          <div class="form-actions">
            <el-button type="primary" size="large" :loading="saving" @click="handleSave">
              保存账号信息
            </el-button>
          </div>
        </el-form>
      </el-card>

      <el-card shadow="never" class="panel account-preview-panel">
        <template #header>
          <div class="card-header">
            <div>
              <strong>信息预览</strong>
              <span>Preview</span>
            </div>
          </div>
        </template>

        <div class="profile-preview">
          <el-avatar :src="form.avatar_url || undefined" :size="72">{{ avatarText }}</el-avatar>
          <div>
            <h3>{{ form.full_name || user?.username || '未登录用户' }}</h3>
            <p>{{ user?.username || '-' }} / {{ form.email || '-' }}</p>
            <p>{{ form.school || '未填写学校' }} / {{ form.major || '未填写专业' }}</p>
          </div>
        </div>

        <el-divider />

        <div class="settings-note">
          <strong>预留入口</strong>
          <p>语言切换和 Light / Dark 主题切换当前只做占位，后续接入 i18n 与主题变量。</p>
        </div>
      </el-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { saveAuth, updateCurrentUser, type User } from '../services/apiClient'

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
