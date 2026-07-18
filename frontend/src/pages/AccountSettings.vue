<template>
  <div class="page settings-page system-settings-page">
    <section class="page-hero">
      <p class="eyebrow">System Settings</p>
      <h2>系统设置</h2>
      <p>配置当前账号的模型服务、API Key 和个人资料。保存模型后，项目规划、学习清单、课堂生成、RAG 问答和科研工具会优先使用这里的配置。</p>
    </section>

    <section class="system-settings-layout">
      <article class="panel-like system-settings-panel model-settings-panel">
        <header>
          <div>
            <span>Model Provider</span>
            <strong>模型与 API Key</strong>
          </div>
          <el-tag v-if="modelForm.api_key_configured" effect="plain" type="success">
            已配置 · ****{{ modelForm.api_key_tail }}
          </el-tag>
          <el-tag v-else effect="plain" type="warning">未配置 Key</el-tag>
        </header>

        <div class="provider-option-grid">
          <button
            v-for="provider in providerOptions"
            :key="provider.id"
            type="button"
            :class="{ active: modelForm.provider === provider.id }"
            @click="selectProvider(provider.id)"
          >
            <span>{{ provider.name }}</span>
            <strong>{{ provider.models.join(' / ') }}</strong>
            <small>{{ provider.description }}</small>
          </button>
        </div>

        <el-form label-position="top" class="compact-form">
          <div class="settings-form-row">
            <el-form-item label="模型">
              <el-select v-model="modelForm.model" placeholder="选择模型">
                <el-option v-for="model in activeProviderModels" :key="model" :label="model" :value="model" />
              </el-select>
            </el-form-item>
            <el-form-item label="Base URL">
              <el-input v-model.trim="modelForm.base_url" placeholder="https://.../v1" />
            </el-form-item>
          </div>

          <el-form-item label="API Key">
            <el-input
              v-model="modelForm.api_key"
              :type="showApiKey ? 'text' : 'password'"
              autocomplete="off"
              placeholder="保存后不会回显完整 Key；留空表示沿用已保存 Key"
              show-password
            />
          </el-form-item>

          <div class="settings-action-row">
            <el-button type="primary" :loading="savingModel" @click="handleSaveModel">保存模型配置</el-button>
            <el-button :loading="testingModel" :disabled="!modelForm.api_key_configured && !modelForm.api_key.trim()" @click="handleVerifyModel">
              测试连接
            </el-button>
            <el-checkbox v-model="showApiKey">显示输入内容</el-checkbox>
          </div>
        </el-form>
      </article>

      <aside class="panel-like system-settings-panel task-center-note">
        <header>
          <div>
            <span>Task Center</span>
            <strong>任务中心有什么用</strong>
          </div>
        </header>
        <p>
          任务中心不是学生每天都要操作的页面，它用于排查生成链路：项目规划、学习清单、课堂资源、可视化和评估由多个 Agent 串联完成，失败时需要看到是哪一步失败、输入摘要和输出摘要。
        </p>
        <p>
          因此它保留在系统菜单中，作为调试和透明度入口；教师看板是班级管理视角，当前学生端不需要，已从前端删除。
        </p>
        <el-button @click="router.push({ name: 'agents' })">打开任务中心</el-button>
      </aside>

      <article class="panel-like system-settings-panel account-settings-panel">
        <header>
          <div>
            <span>Profile</span>
            <strong>个人资料</strong>
          </div>
        </header>

        <el-form label-position="top">
          <div class="settings-form-row">
            <el-form-item label="姓名">
              <el-input v-model.trim="form.full_name" placeholder="请输入展示姓名" />
            </el-form-item>
            <el-form-item label="邮箱">
              <el-input v-model.trim="form.email" placeholder="name@example.com" />
            </el-form-item>
          </div>

          <el-form-item label="头像">
            <div class="avatar-upload-field">
              <el-avatar :src="form.avatar_url || undefined" :size="68">{{ avatarText }}</el-avatar>
              <div class="avatar-upload-copy">
                <strong>{{ form.avatar_url ? '已设置头像' : '还没有头像' }}</strong>
                <span>支持 JPG、PNG、WebP，单张不超过 5MB。</span>
                <el-upload
                  action="#"
                  :auto-upload="false"
                  :show-file-list="false"
                  accept="image/jpeg,image/png,image/webp"
                  :before-upload="handleAvatarBeforeUpload"
                  :on-change="handleAvatarChange"
                >
                  <el-button :loading="uploadingAvatar">上传头像</el-button>
                </el-upload>
              </div>
            </div>
          </el-form-item>

          <div class="settings-form-row">
            <el-form-item label="学校">
              <el-input v-model.trim="form.school" placeholder="例如：南京大学" />
            </el-form-item>
            <el-form-item label="专业">
              <el-input v-model.trim="form.major" placeholder="例如：人工智能" />
            </el-form-item>
          </div>

          <el-form-item label="个人简介">
            <el-input
              v-model="form.bio"
              type="textarea"
              :rows="5"
              resize="vertical"
              placeholder="可以写你的研究兴趣、当前课程、学习目标或项目经历。"
            />
          </el-form-item>

          <div class="settings-action-row">
            <el-button type="primary" :loading="saving" @click="handleSave">保存个人资料</el-button>
          </div>
        </el-form>
      </article>

      <aside class="panel-like system-settings-panel account-preview-panel">
        <header>
          <div>
            <span>Preview</span>
            <strong>信息预览</strong>
          </div>
        </header>

        <div class="profile-preview">
          <el-avatar :src="form.avatar_url || undefined" :size="72">{{ avatarText }}</el-avatar>
          <div>
            <h3>{{ form.full_name || user?.username || '未登录用户' }}</h3>
            <p>{{ user?.username || '-' }} / {{ form.email || '-' }}</p>
            <p>{{ form.school || '未填写学校' }} / {{ form.major || '未填写专业' }}</p>
            <small>{{ currentModelSummary }}</small>
          </div>
        </div>
      </aside>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import type { UploadFile, UploadRawFile } from 'element-plus'
import {
  getModelSettings,
  saveAuth,
  uploadCurrentUserAvatar,
  updateCurrentUser,
  updateModelSettings,
  verifyModelSettings,
  type ModelProviderOption,
  type User,
  type UserModelSettingsRead
} from '../services/apiClient'

const props = defineProps<{ user: User | null }>()
const emit = defineEmits<{ saved: [user: User] }>()
const router = useRouter()

const saving = ref(false)
const savingModel = ref(false)
const testingModel = ref(false)
const uploadingAvatar = ref(false)
const showApiKey = ref(false)
const providerOptions = ref<ModelProviderOption[]>([])

const form = reactive({
  full_name: '',
  email: '',
  avatar_url: '',
  school: '',
  major: '',
  bio: ''
})

const modelForm = reactive({
  provider: 'qwen',
  model: 'qwen-plus',
  base_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
  api_key: '',
  api_key_configured: false,
  api_key_tail: ''
})

const avatarText = computed(() => (form.full_name || props.user?.username || 'U').slice(0, 1).toUpperCase())
const activeProvider = computed(() => providerOptions.value.find((provider) => provider.id === modelForm.provider) || providerOptions.value[0] || null)
const activeProviderModels = computed(() => activeProvider.value?.models || [modelForm.model])
const currentModelSummary = computed(() => {
  const provider = activeProvider.value?.name || modelForm.provider
  return `${provider} / ${modelForm.model}`
})

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

onMounted(loadModelSettings)

async function loadModelSettings() {
  const { data } = await getModelSettings()
  applyModelSettings(data)
}

function applyModelSettings(data: UserModelSettingsRead) {
  providerOptions.value = data.provider_options
  modelForm.provider = data.provider
  modelForm.model = data.model
  modelForm.base_url = data.base_url
  modelForm.api_key = ''
  modelForm.api_key_configured = data.api_key_configured
  modelForm.api_key_tail = data.api_key_tail
}

function selectProvider(providerId: string) {
  const provider = providerOptions.value.find((item) => item.id === providerId)
  if (!provider) return
  modelForm.provider = provider.id
  modelForm.base_url = provider.base_url
  if (!provider.models.includes(modelForm.model)) modelForm.model = provider.models[0] || ''
}

async function handleSaveModel() {
  savingModel.value = true
  try {
    const payload = {
      provider: modelForm.provider,
      model: modelForm.model,
      base_url: modelForm.base_url,
      api_key: modelForm.api_key.trim() ? modelForm.api_key : null
    }
    const { data } = await updateModelSettings(payload)
    applyModelSettings(data)
    ElMessage.success('模型配置已保存')
  } finally {
    savingModel.value = false
  }
}

async function handleVerifyModel() {
  if (modelForm.api_key.trim()) await handleSaveModel()
  testingModel.value = true
  try {
    const { data } = await verifyModelSettings()
    ElMessage.success(data.message || '模型连接测试通过')
  } finally {
    testingModel.value = false
  }
}

async function handleSave() {
  saving.value = true
  try {
    const { data } = await updateCurrentUser(form)
    const token = localStorage.getItem('access_token') || ''
    saveAuth({ access_token: token, token_type: 'bearer', user: data })
    emit('saved', data)
    ElMessage.success('个人资料已保存')
  } finally {
    saving.value = false
  }
}

function handleAvatarBeforeUpload(file: UploadRawFile) {
  if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) {
    ElMessage.warning('头像仅支持 JPG、PNG 或 WebP 图片')
    return false
  }
  if (file.size > 5 * 1024 * 1024) {
    ElMessage.warning('头像图片不能超过 5MB')
    return false
  }
  return true
}

async function handleAvatarChange(uploadFile: UploadFile) {
  const raw = uploadFile.raw
  if (!raw || !handleAvatarBeforeUpload(raw)) return
  uploadingAvatar.value = true
  try {
    const { data } = await uploadCurrentUserAvatar(raw)
    form.avatar_url = data.avatar_url || ''
    const token = localStorage.getItem('access_token') || ''
    saveAuth({ access_token: token, token_type: 'bearer', user: data })
    emit('saved', data)
    ElMessage.success('头像已更新')
  } finally {
    uploadingAvatar.value = false
  }
}
</script>
