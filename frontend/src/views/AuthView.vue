<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { registerAccount } from '../api/auth'
import { errorMessage } from '../api/client'
import { useAuthStore } from '../stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const registering = computed(() => route.name === 'register')
const form = reactive({ username: '', email: '', password: '', confirm: '' })
const busy = ref(false)
const error = ref('')
watch(registering, () => { error.value = ''; form.password = ''; form.confirm = '' })
async function submit() {
  error.value = ''
  if (registering.value && form.password !== form.confirm) { error.value = '两次输入的密码不一致。'; return }
  busy.value = true
  try {
    if (registering.value) {
      await registerAccount({ username: form.username.trim(), email: form.email.trim(), password: form.password })
    }
    await auth.login({ username: form.username.trim(), password: form.password })
    form.password = ''; form.confirm = ''
    await router.replace('/')
  } catch (cause) { error.value = errorMessage(cause) }
  finally { busy.value = false }
}
</script>

<template>
  <main class="auth-page">
    <section class="auth-story"><div class="brand"><span class="brand-mark">F</span> FocusNest</div><span class="eyebrow">A SPACE FOR YOURSELF</span><h1>把注意力，<br>留给重要的事。</h1><p>从一个属于你的空间开始，<br>让每天的记录与思考有所归处。</p><span class="auth-note">个人工作台 · 从容开始</span></section>
    <section class="auth-card">
      <span class="eyebrow">{{ registering ? 'CREATE YOUR SPACE' : 'WELCOME BACK' }}</span>
      <h2>{{ registering ? '创建你的账号' : '欢迎回来' }}</h2>
      <p class="muted">{{ registering ? '建立一个只属于你的私人工作台。' : '登录，继续你的专注旅程。' }}</p>
      <form @submit.prevent="submit">
        <label for="identity">{{ registering ? '用户名' : '用户名或邮箱' }}</label>
        <input id="identity" v-model="form.username" :disabled="busy" required :maxlength="registering ? 32 : 254" :minlength="registering ? 3 : 1" :pattern="registering ? '[a-zA-Z0-9_]+' : undefined" autocomplete="username" :placeholder="registering ? '3–32 位字母、数字或下划线' : '输入用户名或邮箱'">
        <template v-if="registering"><label for="email">邮箱</label><input id="email" v-model="form.email" :disabled="busy" type="email" required maxlength="254" autocomplete="email" placeholder="you@example.com"></template>
        <label for="password">密码</label><input id="password" v-model="form.password" :disabled="busy" type="password" required :minlength="registering ? 10 : 1" maxlength="128" :autocomplete="registering ? 'new-password' : 'current-password'" :placeholder="registering ? '至少 10 位，最多 128 位' : '输入密码'">
        <template v-if="registering"><label for="confirm">确认密码</label><input id="confirm" v-model="form.confirm" :disabled="busy" type="password" required maxlength="128" autocomplete="new-password" placeholder="再次输入密码"></template>
        <p v-if="error" role="alert" class="form-error">{{ error }}</p>
        <button class="primary-button" type="submit" :disabled="busy">{{ busy ? '请稍候…' : registering ? '创建账号并登录' : '登录工作台' }}</button>
      </form>
      <p class="auth-switch">{{ registering ? '已有账号？' : '还没有账号？' }} <RouterLink :to="registering ? '/login' : '/register'">{{ registering ? '前往登录' : '创建账号' }}</RouterLink></p>
    </section>
  </main>
</template>
