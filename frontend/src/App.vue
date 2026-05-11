<template>
  <!-- 未登录：显示登录/注册页 -->
  <div v-if="!token" class="auth-page">
    <div class="auth-card">
      <div class="auth-logo">🤖</div>
      <h1 class="auth-title">智扫通客服</h1>
      <p class="auth-sub">扫地机器人智能服务平台</p>

      <div class="auth-tabs">
        <button :class="['tab-btn', authMode === 'login' && 'active']" @click="authMode = 'login'">登录</button>
        <button :class="['tab-btn', authMode === 'register' && 'active']" @click="authMode = 'register'">注册</button>
      </div>

      <form class="auth-form" @submit.prevent="submitAuth">
        <div class="field">
          <label>用户名</label>
          <input v-model="authForm.username" placeholder="请输入用户名" autocomplete="username" />
        </div>
        <div class="field">
          <label>密码</label>
          <input v-model="authForm.password" type="password" placeholder="请输入密码（至少6位）" autocomplete="current-password" />
        </div>
        <p v-if="authError" class="auth-error">{{ authError }}</p>
        <button type="submit" class="auth-submit" :disabled="authLoading">
          {{ authLoading ? '请稍候...' : (authMode === 'login' ? '登录' : '注册') }}
        </button>
      </form>
    </div>
  </div>

  <!-- 已登录：聊天主界面 -->
  <div v-else class="chat-app">
    <!-- 侧边栏 -->
    <aside class="sidebar">
      <div class="logo">
        <span class="logo-icon">🤖</span>
        <span class="logo-text">智扫通</span>
      </div>
      <p class="sidebar-desc">扫地机器人智能客服</p>
      <div class="sidebar-tips">
        <p class="tip-title">可以问我：</p>
        <ul>
          <li>机器人故障排查</li>
          <li>维护保养建议</li>
          <li>选购指南咨询</li>
          <li>当前天气是否适合使用</li>
        </ul>
      </div>
      <div class="sidebar-user">
        <span class="user-icon">👤</span>
        <span class="user-name">{{ username }}</span>
      </div>
      <button class="new-chat-btn" @click="clearChat">+ 新对话</button>
      <button class="logout-btn" @click="logout">退出登录</button>
    </aside>

    <!-- 主区域 -->
    <main class="chat-main">
      <header class="chat-header">
        <div class="header-left">
          <span class="status-dot"></span>
          <span>智能客服在线</span>
        </div>
        <span class="model-tag">DeepSeek · ReAct</span>
      </header>

      <!-- 消息列表 -->
      <div class="message-list" ref="messageListRef">
        <div v-if="messages.length === 0" class="empty-hint">
          <p>👋 你好，{{ username }}！我是智扫通机器人客服，有什么可以帮到你？</p>
        </div>

        <template v-for="(msg, idx) in messages" :key="idx">
          <!-- 思考/工具调用过程 -->
          <div v-if="msg.type === 'thought'" class="thought-block">
            <div class="thought-header" @click="msg.collapsed = !msg.collapsed">
              <span class="thought-icon">⚙️</span>
              <span>{{ msg.collapsed ? '展开推理过程' : '收起推理过程' }}</span>
              <span class="thought-arrow">{{ msg.collapsed ? '▶' : '▼' }}</span>
            </div>
            <div v-if="!msg.collapsed" class="thought-body">
              <div v-for="(step, si) in msg.steps" :key="si" :class="['thought-step', step.kind]">
                <span class="step-label">{{ stepLabel(step.kind) }}</span>
                <span class="step-content">{{ step.text }}</span>
              </div>
            </div>
          </div>

          <!-- 用户消息 -->
          <div v-else-if="msg.type === 'user'" class="bubble-row user">
            <div class="bubble user-bubble">{{ msg.text }}</div>
            <div class="avatar user-avatar">{{ username[0]?.toUpperCase() }}</div>
          </div>

          <!-- AI 回答 -->
          <div v-else-if="msg.type === 'assistant'" class="bubble-row assistant">
            <div class="avatar bot-avatar">🤖</div>
            <div class="bubble bot-bubble">
              <span class="md-body" v-html="marked.parse(msg.text || '')"></span>
              <span v-if="msg.streaming" class="cursor">|</span>
            </div>
          </div>
        </template>

        <!-- 加载中 -->
        <div v-if="loading && !streamingMsg" class="thinking-row">
          <div class="avatar bot-avatar">🤖</div>
          <div class="thinking-dots"><span></span><span></span><span></span></div>
        </div>
      </div>

      <!-- 输入区 -->
      <div class="input-area">
        <textarea
          ref="inputRef"
          v-model="inputText"
          placeholder="输入问题，Enter 发送，Shift+Enter 换行..."
          rows="1"
          @keydown.enter.exact.prevent="sendMessage"
          @input="autoResize"
          :disabled="loading"
        ></textarea>
        <button class="send-btn" @click="sendMessage" :disabled="loading || !inputText.trim()">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="22" y1="2" x2="11" y2="13"/>
            <polygon points="22 2 15 22 11 13 2 9 22 2"/>
          </svg>
        </button>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted } from 'vue'
import { marked } from 'marked'

marked.setOptions({ breaks: true, gfm: true })

const BACKEND = 'http://localhost:8000'

// ── 认证状态 ─────────────────────────────────────────────────────────────────
const token    = ref(localStorage.getItem('token') || '')
const username = ref(localStorage.getItem('username') || '')
const authMode  = ref('login')
const authForm  = ref({ username: '', password: '' })
const authError = ref('')
const authLoading = ref(false)

async function submitAuth() {
  authError.value = ''
  authLoading.value = true
  const url = `${BACKEND}/auth/${authMode.value}`
  try {
    const resp = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(authForm.value),
    })
    const data = await resp.json()
    if (!resp.ok) throw new Error(data.detail || '操作失败')
    token.value    = data.token
    username.value = data.username
    localStorage.setItem('token', data.token)
    localStorage.setItem('username', data.username)
    authForm.value = { username: '', password: '' }
  } catch (e) {
    authError.value = e.message
  } finally {
    authLoading.value = false
  }
}

function logout() {
  token.value = ''
  username.value = ''
  localStorage.removeItem('token')
  localStorage.removeItem('username')
  messages.value = []
}

// ── 聊天状态 ─────────────────────────────────────────────────────────────────
const messages     = ref([])
const inputText    = ref('')
const loading      = ref(false)
const streamingMsg = ref(null)
const messageListRef = ref(null)
const inputRef       = ref(null)

function stepLabel(kind) {
  return { think: '💭 思考', tool_call: '🔧 调用工具', tool_result: '📦 工具结果' }[kind] ?? kind
}

function scrollBottom() {
  nextTick(() => {
    if (messageListRef.value)
      messageListRef.value.scrollTop = messageListRef.value.scrollHeight
  })
}

function autoResize() {
  const el = inputRef.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 160) + 'px'
}

function clearChat() {
  messages.value = []
  inputText.value = ''
  fetch(`${BACKEND}/chat/clear`, {
    method: 'POST',
    headers: { 'Authorization': `Bearer ${token.value}` },
  })
}

async function sendMessage() {
  const text = inputText.value.trim()
  if (!text || loading.value) return

  messages.value.push({ type: 'user', text })
  inputText.value = ''
  await nextTick()
  if (inputRef.value) inputRef.value.style.height = 'auto'
  scrollBottom()

  loading.value = true
  const thoughtMsg   = { type: 'thought', steps: [], collapsed: false }
  const assistantMsg = { type: 'assistant', text: '', streaming: true }
  messages.value.push(thoughtMsg, assistantMsg)
  streamingMsg.value = assistantMsg

  try {
    const resp = await fetch(`${BACKEND}/chat/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token.value}`,
      },
      body: JSON.stringify({ message: text }),
    })

    if (resp.status === 401) {
      logout()
      return
    }

    const reader  = resp.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })

      // SSE 协议以 \n\n 分隔完整消息，只处理已完整到达的部分
      const parts = buffer.split('\n\n')
      buffer = parts.pop()   // 最后一段可能不完整，留到下次

      for (const part of parts) {
        for (const line of part.split('\n')) {
          if (!line.startsWith('data:')) continue
          const data = line.slice(5).trim()
          if (!data || data === '[DONE]') continue
          let event
          try { event = JSON.parse(data) } catch { continue }

          if (event.type === 'think')             thoughtMsg.steps.push({ kind: 'think',       text: event.content })
          else if (event.type === 'tool_call')    thoughtMsg.steps.push({ kind: 'tool_call',   text: `${event.name}  ${JSON.stringify(event.args)}` })
          else if (event.type === 'tool_result')  thoughtMsg.steps.push({ kind: 'tool_result', text: event.content })
          else if (event.type === 'token')        assistantMsg.text += event.content

          scrollBottom()
        }
      }
    }
  } catch {
    assistantMsg.text = '请求失败，请检查后端服务是否启动。'
  } finally {
    assistantMsg.streaming = false
    streamingMsg.value = null
    loading.value = false
    if (thoughtMsg.steps.length === 0) {
      const idx = messages.value.indexOf(thoughtMsg)
      if (idx !== -1) messages.value.splice(idx, 1)
    } else {
      thoughtMsg.collapsed = true
    }
    scrollBottom()
  }
}

onMounted(() => inputRef.value?.focus())
</script>

<style scoped>
/* ── 认证页 ── */
.auth-page {
  min-height: 100vh;
  background: linear-gradient(135deg, #e0f2fe 0%, #f0f4f8 60%, #ede9fe 100%);
  display: flex;
  align-items: center;
  justify-content: center;
}
.auth-card {
  background: #fff;
  border-radius: 20px;
  padding: 44px 40px 36px;
  width: 360px;
  box-shadow: 0 8px 40px rgba(59,130,246,.12);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
}
.auth-logo { font-size: 44px; }
.auth-title { font-size: 22px; font-weight: 700; color: #1e40af; margin-top: 4px; }
.auth-sub   { font-size: 13px; color: #94a3b8; margin-bottom: 8px; }
.auth-tabs  { display: flex; width: 100%; background: #f1f5f9; border-radius: 10px; padding: 4px; margin: 10px 0; }
.tab-btn {
  flex: 1; padding: 8px; border: none; background: transparent;
  border-radius: 8px; cursor: pointer; font-size: 14px; color: #64748b; transition: all .2s;
}
.tab-btn.active { background: #fff; color: #3b82f6; font-weight: 600; box-shadow: 0 1px 4px rgba(0,0,0,.08); }
.auth-form { width: 100%; display: flex; flex-direction: column; gap: 14px; }
.field { display: flex; flex-direction: column; gap: 5px; }
.field label { font-size: 13px; color: #64748b; font-weight: 500; }
.field input {
  border: 1px solid #e2e8f0; border-radius: 10px; padding: 10px 14px;
  font-size: 14px; outline: none; transition: border-color .2s;
}
.field input:focus { border-color: #93c5fd; }
.auth-error { color: #ef4444; font-size: 13px; text-align: center; }
.auth-submit {
  background: #3b82f6; color: #fff; border: none; border-radius: 10px;
  padding: 12px; font-size: 15px; font-weight: 600; cursor: pointer;
  transition: background .2s; margin-top: 4px;
}
.auth-submit:hover:not(:disabled) { background: #2563eb; }
.auth-submit:disabled { background: #bfdbfe; cursor: not-allowed; }

/* ── 布局 ── */
.chat-app { display: flex; height: 100vh; overflow: hidden; }

/* ── 侧边栏 ── */
.sidebar {
  width: 220px; flex-shrink: 0;
  background: #ffffff; border-right: 1px solid #e2e8f0;
  display: flex; flex-direction: column;
  padding: 24px 16px; gap: 16px;
}
.logo { display: flex; align-items: center; gap: 8px; font-size: 20px; font-weight: 700; color: #3b82f6; }
.logo-icon { font-size: 24px; }
.sidebar-desc { font-size: 12px; color: #94a3b8; }
.sidebar-tips { background: #f8fafc; border-radius: 10px; padding: 12px; font-size: 13px; }
.tip-title { font-weight: 600; color: #64748b; margin-bottom: 8px; }
.sidebar-tips ul { padding-left: 16px; color: #64748b; line-height: 1.8; }
.sidebar-user {
  display: flex; align-items: center; gap: 8px;
  background: #eff6ff; border-radius: 10px; padding: 10px 12px;
  font-size: 13px; color: #3b82f6; font-weight: 500;
}
.new-chat-btn {
  background: #eff6ff; color: #3b82f6; border: 1px solid #bfdbfe;
  border-radius: 8px; padding: 9px; font-size: 14px; cursor: pointer; transition: background .2s;
}
.new-chat-btn:hover { background: #dbeafe; }
.logout-btn {
  background: #fff; color: #94a3b8; border: 1px solid #e2e8f0;
  border-radius: 8px; padding: 9px; font-size: 13px; cursor: pointer; transition: all .2s;
}
.logout-btn:hover { color: #ef4444; border-color: #fca5a5; background: #fff5f5; }

/* ── 主区域 ── */
.chat-main { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
.chat-header {
  padding: 14px 24px; background: #ffffff; border-bottom: 1px solid #e2e8f0;
  display: flex; align-items: center; justify-content: space-between;
  font-size: 14px; color: #475569;
}
.header-left { display: flex; align-items: center; gap: 8px; }
.status-dot { width: 8px; height: 8px; background: #22c55e; border-radius: 50%; box-shadow: 0 0 0 2px #bbf7d0; }
.model-tag { font-size: 12px; background: #f1f5f9; color: #64748b; padding: 3px 10px; border-radius: 20px; }

/* ── 消息列表 ── */
.message-list {
  flex: 1; overflow-y: auto; padding: 24px 10%;
  display: flex; flex-direction: column; gap: 16px; scroll-behavior: smooth;
}
.empty-hint { text-align: center; color: #94a3b8; margin-top: 80px; font-size: 15px; }

/* ── 气泡 ── */
.bubble-row { display: flex; align-items: flex-end; gap: 10px; }
.bubble-row.user { flex-direction: row-reverse; }
.avatar { width: 36px; height: 36px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 14px; flex-shrink: 0; }
.user-avatar { background: #3b82f6; color: #fff; font-weight: 600; font-size: 13px; }
.bot-avatar  { background: #e0f2fe; font-size: 18px; }
.bubble { max-width: 70%; padding: 12px 16px; border-radius: 16px; font-size: 14px; line-height: 1.7; word-break: break-word; }
.user-bubble { background: #3b82f6; color: #fff; border-bottom-right-radius: 4px; }
.bot-bubble  { background: #ffffff; color: #334155; border-bottom-left-radius: 4px; box-shadow: 0 1px 4px rgba(0,0,0,.06); }
.cursor { display: inline-block; animation: blink .9s step-end infinite; font-weight: 200; color: #94a3b8; }
@keyframes blink { 0%,100%{opacity:1} 50%{opacity:0} }

/* ── 思考块 ── */
.thought-block { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; overflow: hidden; font-size: 13px; }
.thought-header { display: flex; align-items: center; gap: 6px; padding: 9px 14px; cursor: pointer; color: #64748b; user-select: none; background: #f1f5f9; }
.thought-header:hover { background: #e9eef5; }
.thought-arrow { margin-left: auto; font-size: 11px; }
.thought-body { padding: 10px 14px; display: flex; flex-direction: column; gap: 6px; }
.thought-step { display: flex; gap: 8px; padding: 6px 10px; border-radius: 8px; font-size: 12.5px; line-height: 1.5; }
.thought-step.think       { background: #fefce8; color: #713f12; }
.thought-step.tool_call   { background: #eff6ff; color: #1e40af; }
.thought-step.tool_result { background: #f0fdf4; color: #14532d; }
.step-label { font-weight: 600; flex-shrink: 0; }
.step-content { word-break: break-all; }

/* ── Markdown 渲染 ── */
.md-body { display: block; }
.md-body :deep(p)  { margin: 0 0 6px; }
.md-body :deep(p:last-child) { margin-bottom: 0; }
.md-body :deep(h1),.md-body :deep(h2),.md-body :deep(h3) { font-size: 14px; font-weight: 700; margin: 10px 0 4px; color: #1e40af; }
.md-body :deep(ul),.md-body :deep(ol) { padding-left: 18px; margin: 4px 0 6px; }
.md-body :deep(li) { margin: 2px 0; }
.md-body :deep(strong) { font-weight: 700; color: #1e293b; }
.md-body :deep(em) { font-style: italic; color: #475569; }
.md-body :deep(code) { background: #f1f5f9; border-radius: 4px; padding: 1px 5px; font-size: 12.5px; color: #0f172a; }
.md-body :deep(pre) { background: #f1f5f9; border-radius: 8px; padding: 10px 12px; overflow-x: auto; font-size: 12.5px; margin: 6px 0; }
.md-body :deep(blockquote) { border-left: 3px solid #bfdbfe; padding-left: 10px; color: #64748b; margin: 6px 0; }
.md-body :deep(hr) { border: none; border-top: 1px solid #e2e8f0; margin: 8px 0; }

.thinking-row { display: flex; align-items: center; gap: 10px; }
.thinking-dots { display: flex; gap: 5px; background: #ffffff; padding: 12px 18px; border-radius: 16px; border-bottom-left-radius: 4px; box-shadow: 0 1px 4px rgba(0,0,0,.06); }
.thinking-dots span { width: 7px; height: 7px; background: #94a3b8; border-radius: 50%; animation: bounce 1.2s ease-in-out infinite; }
.thinking-dots span:nth-child(2) { animation-delay: .2s; }
.thinking-dots span:nth-child(3) { animation-delay: .4s; }
@keyframes bounce { 0%,80%,100%{transform:scale(.8);opacity:.5} 40%{transform:scale(1.1);opacity:1} }

/* ── 输入区 ── */
.input-area { padding: 16px 10%; background: #ffffff; border-top: 1px solid #e2e8f0; display: flex; align-items: flex-end; gap: 10px; }
.input-area textarea { flex: 1; resize: none; border: 1px solid #e2e8f0; border-radius: 12px; padding: 11px 14px; font-size: 14px; color: #334155; font-family: inherit; outline: none; line-height: 1.6; transition: border-color .2s; overflow-y: auto; }
.input-area textarea:focus { border-color: #93c5fd; }
.input-area textarea:disabled { background: #f8fafc; }
.send-btn { width: 42px; height: 42px; border-radius: 10px; background: #3b82f6; border: none; cursor: pointer; display: flex; align-items: center; justify-content: center; flex-shrink: 0; transition: background .2s, transform .1s; }
.send-btn:hover:not(:disabled) { background: #2563eb; }
.send-btn:active:not(:disabled) { transform: scale(.94); }
.send-btn:disabled { background: #bfdbfe; cursor: not-allowed; }
.send-btn svg { width: 18px; height: 18px; stroke: #fff; }
</style>
