<template>
  <main class="auth-page">
    <section class="auth-hero">
      <h1>智研星链</h1>
      <p>从一个学习或科研方向开始，生成可执行的课程、计划和资料。</p>
    </section>

    <section class="auth-panel">
      <div class="auth-panel-head">
        <div>
          <p class="eyebrow">{{ mode === 'login' ? 'Sign In' : 'Create Account' }}</p>
          <h2>{{ mode === 'login' ? '登录学习工作台' : '创建学生账号' }}</h2>
        </div>
        <el-segmented
          v-model="mode"
          :options="[
            { label: '登录', value: 'login' },
            { label: '注册', value: 'register' }
          ]"
        />
      </div>

      <el-form v-if="mode === 'login'" label-position="top" class="auth-form" @submit.prevent>
        <el-form-item label="用户名或邮箱">
          <el-input v-model="loginForm.username" autocomplete="username" placeholder="请输入用户名或邮箱" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input
            v-model="loginForm.password"
            autocomplete="current-password"
            placeholder="请输入密码"
            show-password
            type="password"
            @keyup.enter="handleLogin"
          />
        </el-form-item>
        <el-button type="primary" size="large" :loading="loading" @click="handleLogin">登录</el-button>
      </el-form>

      <el-form v-else label-position="top" class="auth-form" @submit.prevent>
        <el-form-item label="用户名">
          <el-input v-model="registerForm.username" autocomplete="username" placeholder="3-32 位用户名" />
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input v-model="registerForm.email" autocomplete="email" placeholder="用于登录和账号识别" />
        </el-form-item>
        <el-form-item label="姓名">
          <el-input v-model="registerForm.full_name" autocomplete="name" placeholder="可显示在右上角" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input
            v-model="registerForm.password"
            autocomplete="new-password"
            placeholder="至少 8 位"
            show-password
            type="password"
            @keyup.enter="handleRegister"
          />
        </el-form-item>
        <el-button type="primary" size="large" :loading="loading" @click="handleRegister">注册并登录</el-button>
      </el-form>
    </section>
  </main>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { loginUser, registerUser, saveAuth, type User } from '../services/apiClient'

const emit = defineEmits<{
  authenticated: [user: User]
}>()

const mode = ref<'login' | 'register'>('login')
const loading = ref(false)
const loginForm = reactive({
  username: '',
  password: ''
})
const registerForm = reactive({
  username: '',
  email: '',
  full_name: '',
  password: ''
})

async function handleLogin() {
  if (!loginForm.username.trim() || !loginForm.password) {
    ElMessage.warning('请输入用户名和密码')
    return
  }
  loading.value = true
  try {
    const { data } = await loginUser(loginForm.username.trim(), loginForm.password)
    saveAuth(data)
    emit('authenticated', data.user)
    ElMessage.success('登录成功')
  } finally {
    loading.value = false
  }
}

async function handleRegister() {
  if (!registerForm.username.trim() || !registerForm.email.trim() || !registerForm.password) {
    ElMessage.warning('请完整填写用户名、邮箱和密码')
    return
  }
  loading.value = true
  try {
    const { data } = await registerUser({
      username: registerForm.username.trim(),
      email: registerForm.email.trim(),
      full_name: registerForm.full_name.trim(),
      password: registerForm.password
    })
    saveAuth(data)
    emit('authenticated', data.user)
    ElMessage.success('注册成功')
  } finally {
    loading.value = false
  }
}
</script>
