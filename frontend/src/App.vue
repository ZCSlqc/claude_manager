<template>
  <div id="app-vue">
    <header class="header">
      <h1>⬡ Claude Manager</h1>
    </header>

    <div class="main">
      <!-- Left Panel: form top, detail bottom -->
      <div class="left-panel">
        <!-- Top: SendForm -->
        <div class="left-top">
          <SendForm ref="formRef" :users="users" :sending="sending" @send="handleSend" @select-project="handleSelectByDir" />
        </div>

        <!-- Bottom: selected project detail -->
        <div class="left-bottom">
          <div v-if="selectedProject" class="selected-card">
            <div class="card-header">
              <img class="card-avatar" :src="avatarUrl(selectedProject.session_avatar_id || 1, 'session')" :width="20" :height="20" />
              <span :class="['card-status', getThumbStatusClass(selectedProject)]">{{ getThumbStatusLabel(selectedProject) }}</span>
            </div>
            <div class="card-path" :title="selectedProject.folder_name">{{ selectedProject.folder_name }}</div>
            <div class="card-preview">
              <div v-if="selectedProject.user_input" class="card-input">
                <div class="card-label">Message</div>
                <div class="card-text">{{ selectedProject.user_input }}</div>
              </div>
              <div class="card-reply" v-if="getModalReplyText(selectedProject) || selectedProject._loading">
                <div class="card-label">Reply</div>
                <div class="card-text" :class="{ 'card-loading-text': selectedProject._loading }">
                  {{ selectedProject._loading ? '等待 Claude 回复...' : getModalReplyText(selectedProject) }}
                </div>
              </div>
            </div>
            <div class="card-actions">
              <button class="btn btn-default" @click="openModalFromSelected">详情</button>
              <button class="btn btn-default" @click="handleRetry"
                :disabled="sending || getThumbStatusClass(selectedProject) !== 'failed'">
                重试
              </button>
              <button class="btn btn-delete" @click="handleDelete">删除</button>
            </div>
          </div>
          <div v-else class="left-bottom-empty">
            <div class="empty-icon">⬡</div>
            <div>选择对接人和项目后<br>在此显示详情</div>
          </div>
        </div>
      </div>

      <!-- Right Panel: all project cards -->
      <div class="right-panel">
        <div v-if="allProjects.length === 0" class="empty-state">
          <div class="icon">⬡</div>
          <div>暂无项目</div>
        </div>
        <div v-else class="project-grid">
          <ProjectCard v-for="p in allProjects" :key="p.project_id"
            :project="p"
            :selected="modalProject?.project_id === p.project_id"
            @select="handleSelect" />
        </div>
      </div>
    </div>

    <!-- Detail Modal -->
    <div v-if="modalProject" class="modal-overlay" @click.self="closeModal">
      <div class="modal">
        <div class="modal-header">
          <div class="modal-header-left">
            <div class="modal-user-row">
              <div class="modal-avatar-block modal-avatar-user">
                <img class="modal-avatar-img"
                  :src="avatarUrl(getUserAvatarId(modalProject.user_id), 'user')"
                  :width="60" :height="60" :title="modalUserName" />
              </div>
              <span class="modal-avatar-label">{{ modalUserName }}</span>
              <span class="modal-arrow">→</span>
              <div class="modal-avatar-block modal-avatar-project">
                <img class="modal-avatar-img"
                  :src="avatarUrl(modalProject.session_avatar_id, 'session')"
                  :width="60" :height="60" :title="modalProject.folder_name" />
              </div>
              <span class="modal-avatar-label">{{ modalProject.folder_name }}</span>
            </div>
          </div>
          <div class="modal-header-right">
            <span v-if="modalProject.retries > 0" class="retries-badge">({{ modalProject.retries }}次重试)</span>
            <span class="status-badge modal-status-header" :class="modalStatusClass">{{ modalStatusLabel }}</span>
            <button class="btn-close" @click="closeModal">✕</button>
          </div>
        </div>

        <div class="modal-body">
          <div class="detail-panels">
            <div class="detail-panel detail-panel-left">
              <div class="detail-label">Message</div>
              <div class="detail-text">{{ modalProject.user_input || '—' }}</div>
            </div>
            <div class="detail-panel detail-panel-right">
              <div class="detail-label">Reply</div>
              <div v-if="modalReplyText" class="detail-text reply">{{ modalReplyText }}</div>
              <div v-if="modalProject.error" class="detail-text error">{{ modalProject.error }}</div>
              <div v-if="!modalReplyText && !modalProject.error" class="detail-text">—</div>
            </div>
          </div>

          <div class="detail-meta">
            <div>
              <span>创建: {{ modalDateStr(modalProject.created_at) }}</span>
              <span v-if="modalTurns != null"> &nbsp; 轮次: {{ modalTurns }}</span>
            </div>
            <div>
              <span>更新: {{ modalDateStr(modalProject.updated_at) }}</span>
              <span> &nbsp; 用时: {{ modalFormattedDuration }}</span>
            </div>
          </div>
        </div>

        <div class="modal-footer">
          <div class="modal-footer-left" v-if="modalTotalTokens > 0">总token: {{ modalTotalTokens >= 1000000 ? Math.floor(modalTotalTokens / 1000000) + 'M' : fmtToken(modalTotalTokens) }}</div>
          <div class="modal-footer-right">
            <button class="btn-continue" @click="handleRetry"
              :disabled="sending || modalStatusClass !== 'failed'">
              {{ sending ? '发送中...' : '重试 ▶' }}
            </button>
            <button class="btn-delete" @click="handleDelete">删除</button>
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- Confirm Dialog -->
  <div v-if="confirmDialog" class="confirm-overlay" @click.self="confirmDialog = null">
    <div class="confirm-dialog">
      <p class="confirm-message">{{ confirmDialog.message }}</p>
      <div class="confirm-actions">
        <button class="btn btn-delete" @click="confirmDialog.onConfirm(); confirmDialog = null">{{ confirmDialog.label }}</button>
        <button class="btn btn-default" @click="confirmDialog = null">{{ confirmDialog.cancelLabel || '取消' }}</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch, reactive } from 'vue'
import * as api from './api/index.js'
import SendForm from './components/SendForm.vue'
import ProjectCard from './components/ProjectCard.vue'
import { avatarUrl } from './utils/avatar.js'

// ── State ──
const projects = ref([])
const users = ref([])
const userMap = ref({})
const sending = ref(false)
const selectedProject = ref(null)
const modalProject = ref(null)
const formRef = ref(null)
const confirmDialog = ref(null) // { message, onConfirm, label }
const currentUserId = ref('') // 跟踪当前表单选中的 user_id
const loadingProjects = reactive(new Set()) // 存储 "user_id:folder_name" 复合 key
let pollTimer = null

function setLoadingKey(dir, uid) {
  return `${uid}:${dir}`
}

// ── Computed ──
const sortedProjects = computed(() => {
  return [...projects.value].sort((a, b) => (b.updated_at || 0) - (a.updated_at || 0))
})
const allProjects = sortedProjects

const modalUserName = computed(() => {
  if (!modalProject.value) return ''
  return Object.entries(userMap.value).find(([uid]) => uid === modalProject.value.user_id)?.[1]?.name || '?'
})
const modalShortPath = computed(() => {
  if (!modalProject.value) return ''
  return modalProject.value.folder_name?.split('/').filter(Boolean).slice(-2).join('/') || '—'
})
const modalReplyText = computed(() => {
  if (!modalProject.value) return ''
  return getModalReplyText(modalProject.value)
})
const modalStatusLabel = computed(() => {
  return getThumbStatusLabel(modalProject.value)
})
const modalStatusClass = computed(() => {
  return getThumbStatusClass(modalProject.value)
})
const modalTurns = computed(() => {
  if (!modalProject.value) return null
  try {
    const cr = typeof modalProject.value.claude_result === 'string'
      ? JSON.parse(modalProject.value.claude_result)
      : modalProject.value.claude_result
    return cr.num_turns ?? null
  } catch { return null }
})
const modalDuration = computed(() => {
  if (!modalProject.value) return null
  try {
    const cr = typeof modalProject.value.claude_result === 'string'
      ? JSON.parse(modalProject.value.claude_result)
      : modalProject.value.claude_result
    return cr.duration_ms ?? null
  } catch { return null }
})
const modalCost = computed(() => {
  if (!modalProject.value) return null
  try {
    const cr = typeof modalProject.value.claude_result === 'string'
      ? JSON.parse(modalProject.value.claude_result)
      : modalProject.value.claude_result
    return cr.cost_usd ?? null
  } catch { return null }
})
const modalTotalTokens = computed(() => {
  if (!modalProject.value) return 0
  return (modalProject.value.total_inputTokens || 0) + (modalProject.value.total_outputTokens || 0)
})
const modalFormattedDuration = computed(() => {
  if (modalDuration.value == null) return '—'
  const s = Math.round(modalDuration.value / 1000)
  const h = String(Math.floor(s / 3600)).padStart(2, '0')
  const m = String(Math.floor((s % 3600) / 60)).padStart(2, '0')
  const sec = String(s % 60).padStart(2, '0')
  return `${h}:${m}:${sec}`
})

// ── Helpers ──
function getUserAvatarId(userId) {
  const u = userMap.value[userId]
  return u?.user_avatar_id ?? 1
}
function getModalReplyText(p) {
  if (!p?.claude_result) return ''
  try {
    const cr = typeof p.claude_result === 'string' ? JSON.parse(p.claude_result) : p.claude_result
    return cr.result || cr.output || ''
  } catch { return '' }
}
function getThumbStatusLabel(p) {
  if (!p) return '—'
  if (p._loading || p.is_finished === 0) return '活跃'
  if (p.status === 0) return '完成'
  const labels = { 1: 'API', 2: '超限', 3: '超时', 4: 'JSON', 5: '异常' }
  return labels[p.status] || '未知'
}
function getThumbStatusClass(p) {
  if (!p) return 'failed'
  if (p._loading || p.is_finished === 0) return 'running'
  if (p.status === 0) return 'active'
  return 'failed'
}
function modalDateStr(ts) {
  return new Date(ts * 1000).toLocaleString()
}
function fmtToken(n) {
  if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M'
  if (n >= 1000) return (n / 1000).toFixed(1) + 'K'
  return String(n)
}
function fmtDuration(ms) {
  if (ms == null) return null
  const s = Math.floor(ms / 1000)
  const m = Math.floor(s / 60)
  const sec = s % 60
  if (m > 0) return `${m}分${sec}秒`
  return `${sec}秒`
}

// ── Actions ──
async function fetchAll() {
  try {
    projects.value = await api.getProjects()
  } catch (e) {
    console.error('fetchAll error:', e)
  }
}

async function refreshProjects() {
  try {
    const data = await api.getProjects()
    // Merge: backend projects inherit _loading if their composite key is still tracked
    const merged = data.map(b => ({
      ...b,
      _loading: loadingProjects.value.has(setLoadingKey(b.folder_name, b.user_id)) ? true : undefined,
    }))
    // Keep temp cards whose user_id:folder_name does NOT match any backend project
    const apiKeys = new Set(data.map(p => setLoadingKey(p.folder_name, p.user_id)))
    for (const p of projects.value) {
      const key = setLoadingKey(p.folder_name, p.user_id)
      if (p._loading && !apiKeys.has(key)) {
        merged.push(p)
      }
    }
    projects.value = merged
  } catch (e) {
    console.error('refreshProjects error:', e)
  }
}
function setProjectLoading(dir, message, uid) {
  const key = `${uid}:${dir}`
  loadingProjects.value.add(key)
  projects.value = projects.value.map(p => {
    if (p.folder_name === dir && p.user_id === uid) {
      return { ...p, _loading: true, is_finished: 0, status: 0, user_input: message, claude_result: null, updated_at: Date.now() }
    }
    return p
  })
}

function handleSelect(p) {
  // 右侧卡片点击 → 只打开 Modal 弹窗，不动左侧概览卡片
  modalProject.value = { ...p }
}
function handleSelectByDir(dir) {
  // form.dir 已在 pickDir 中设置，watch 会自动触发，这里不需要额外操作
}

async function handleSend() {
  if (sending.value) return
  const { user, dir, message } = formRef.value.form
  if (!message.trim() || !user || !dir) return

  sending.value = true

  // 如果项目已存在，设置 loading 状态并保留 user_input
  let project = currentUserId.value
    ? projects.value.find(p => p.folder_name === dir && p.user_id === currentUserId.value)
    : projects.value.find(p => p.folder_name === dir)
  if (project) {
    setProjectLoading(dir, message, currentUserId.value)
    selectedProject.value = projects.value.find(p => p.folder_name === dir && p.user_id === currentUserId.value)
  } else {
    // 新建项目：预置 user_input + loading 状态
    // session_avatar_id 用和后端一致的 int.from_bytes(...) 算法
    function toBigint(s) {
      return BigInt('0x' + [...s].map(c => c.charCodeAt(0).toString(16).padStart(2, '0')).join(''))
    }
    const uid = currentUserId.value
    const newProject = {
      _loading: true, folder_name: dir, user_input: message,
      is_finished: 0, status: 0, user_id: uid,
      session_avatar_id: Number(toBigint(dir) % 100n) + 1,
    }
    loadingProjects.value.add(setLoadingKey(dir, uid))
    projects.value.push(newProject)
    selectedProject.value = newProject
  }

  const prevMsg = message
  formRef.value.form.message = ''

  // 停止旧的轮询
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null }

  try {
    const { state, project_id } = await api.sendChat(user, dir, prevMsg)

    if (state === 'success') {
      sending.value = false  // 立即解锁按钮

      // 后端只返回 project_id，前端立即开始轮询
      // 每 3 秒轮询一次，直到项目完成
      pollTimer = setInterval(async () => {
        await refreshProjects()
        // 优先按 project_id 匹配，若 temp 项目没有 project_id 则按 user_id:folder_name 匹配
        const updated = projects.value.find(
          p => p.project_id === project_id
            || (!p.project_id && p.folder_name === dir && p.user_id === currentUserId.value)
        )
        if (updated && updated.is_finished === 1) {
          clearInterval(pollTimer)
          pollTimer = null
          loadingProjects.value.delete(setLoadingKey(updated.folder_name, updated.user_id))
          projects.value = projects.value.map(p => ({ ...p, _loading: false }))
          selectedProject.value = { ...updated }
        } else if (updated) {
          // 仍在运行中，更新左侧概览卡片
          selectedProject.value = { ...updated }
        }
      }, 3000)
      // 立即刷新一次
      await refreshProjects()
      const immediate = projects.value.find(
        p => p.project_id === project_id
          || (!p.project_id && p.folder_name === dir && p.user_id === currentUserId.value)
      )
      if (immediate && immediate.is_finished === 1) {
        clearInterval(pollTimer)
        pollTimer = null
        loadingProjects.value.delete(setLoadingKey(immediate.folder_name, immediate.user_id))
        projects.value = projects.value.map(p => ({ ...p, _loading: false }))
        selectedProject.value = { ...immediate }
      } else if (immediate) {
        selectedProject.value = { ...immediate }
      }
    } else {
      // 状态不是 success，直接解锁
      sending.value = false
    }
  } catch (err) {
    projects.value = projects.value.map(p => {
      const matchDir = currentUserId.value ? (p.folder_name === dir && p.user_id === currentUserId.value) : p.folder_name === dir
      if (matchDir) {
        loadingProjects.value.delete(setLoadingKey(dir, currentUserId.value))
        return { ...p, _loading: false, is_finished: 1, status: 5 }
      }
      return p
    })
    sending.value = false
    if (err.status === 409) alert(err.error || 'session 使用中')
    else alert('发送失败: ' + (err.detail || err.message || JSON.stringify(err)))
    await refreshProjects()
  }
}

function _targetProject() {
  return selectedProject.value || modalProject.value
}

function showConfirm(message, onConfirm) {
  confirmDialog.value = { message, onConfirm, label: '确定', cancelLabel: '取消' }
}

async function handleDelete() {
  const proj = _targetProject()
  if (!proj?.project_id) return
  showConfirm('确定要删除这个项目吗？', async () => {
    try {
      await api.deleteProject(proj.project_id)
      await refreshProjects()
      selectedProject.value = null
      modalProject.value = null
    } catch (e) {
      alert('删除失败: ' + e.message)
    }
  })
}

async function handleRetry() {
  const proj = _targetProject()
  if (sending.value || !proj?.project_id) return
  showConfirm('确定要重试吗？', async () => {
    sending.value = true
    try {
      api.heartbeat(proj.project_id).catch(() => {})
      const result = await api.continueProject(proj.project_id)
      await refreshProjects()
      const updated = projects.value.find(p => p.project_id === result.project_id)
      if (updated) {
        selectedProject.value = { ...updated }
        modalProject.value = { ...updated }
      }
    } catch (err) {
      if (err.status === 409) alert(err.error || 'session 使用中')
      else alert('重试失败: ' + (err.detail || err.message || JSON.stringify(err)))
      await refreshProjects()
    } finally {
      sending.value = false
    }
  })
}

function openModalFromSelected() {
  if (selectedProject.value) modalProject.value = { ...selectedProject.value }
}
function closeModal() {
  modalProject.value = null
}

// ── Init ──
onMounted(async () => {
  try {
    users.value = await api.getUsers()
    for (const u of users.value) {
      userMap.value[u.user_id] = { name: u.name, user_avatar_id: u.user_avatar_id }
    }
    await fetchAll()
  } catch (e) {
    console.error('onMounted error:', e)
  }
})

// 清理轮询
window.addEventListener('beforeunload', () => {
  if (pollTimer) clearInterval(pollTimer)
})

// 表单 user/dir 变化时只更新左侧概览卡片，不自动弹出详情弹窗
watch([() => formRef.value?.form.user, () => formRef.value?.form.dir], ([user, dir]) => {
  if (user && dir) {
    // 先确认 user 存在
    currentUserId.value = Object.entries(userMap.value).find(([uid, u]) => u.name === user)?.[0] || ''
  } else {
    currentUserId.value = ''
    selectedProject.value = null
    modalProject.value = null
  }
  if (user && dir && currentUserId.value) {
    const p = projects.value.find(p => p.folder_name === dir && p.user_id === currentUserId.value)
    if (p) {
      selectedProject.value = { ...p }
    } else {
      selectedProject.value = null
    }
  } else {
    selectedProject.value = null
  }
}, { deep: true })
</script>

<style>
* { margin: 0; padding: 0; box-sizing: border-box; }

:root {
  --bg: #0a0a1a;
  --bg2: #111128;
  --bg3: #1a1a3e;
  --bg-card: #16163a;
  --bg-hover: #1e1e50;
  --border: #2a2a5a;
  --purple: #7c3aed;
  --purple-light: #a78bfa;
  --purple-glow: rgba(124, 58, 237, 0.3);
  --text: #e2e8f0;
  --text-dim: #94a3b8;
  --success: #22c55e;
  --error: #ef4444;
  --warning: #f59e0b;
  --font: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
}

body {
  background: var(--bg);
  color: var(--text);
  font-family: var(--font);
  overflow: hidden;
  height: 100vh;
}

body::before {
  content: '';
  position: fixed;
  inset: 0;
  background-image:
    linear-gradient(rgba(124, 58, 237, 0.05) 1px, transparent 1px),
    linear-gradient(90deg, rgba(124, 58, 237, 0.05) 1px, transparent 1px);
  background-size: 32px 32px;
  pointer-events: none;
  z-index: 0;
}

#app-vue {
  display: flex;
  flex-direction: column;
  height: 100vh;
  position: relative;
  z-index: 1;
}

/* Header */
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  height: 48px;
  background: var(--bg2);
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}
.header h1 { font-size: 15px; font-weight: 600; color: var(--purple-light); }

/* Main layout */
.main {
  display: flex;
  flex: 1;
  overflow: hidden;
}

/* Left panel */
.left-panel {
  width: 320px;
  min-width: 320px;
  display: flex;
  flex-direction: column;
  border-right: 1px solid var(--border);
  background: var(--bg2);
  overflow: hidden;
}
.left-top { padding: 14px 14px 12px; border-bottom: 1px solid var(--border); }
.left-bottom {
  flex: 1;
  overflow-y: auto;
  padding: 14px;
}
.left-bottom::-webkit-scrollbar { width: 4px; }
.left-bottom::-webkit-scrollbar-thumb { background: var(--border); border-radius: 2px; }

/* Selected card */
.selected-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 12px;
  transition: border-color 0.2s;
}
.selected-card:hover {
  border-color: rgba(124, 58, 237, 0.3);
}
.card-header { display: flex; align-items: center; justify-content: space-between; }
.card-avatar { border-radius: 0; }
.card-status {
  font-size: 10px;
  padding: 2px 8px;
  border-radius: 10px;
  font-weight: 600;
}
.card-status.active { background: rgba(34, 197, 94, 0.12); color: var(--success); }
.card-status.running { background: rgba(245, 158, 11, 0.12); color: var(--warning); }
.card-status.failed { background: rgba(239, 68, 68, 0.12); color: var(--error); }
.card-path {
  font-size: 11px;
  color: var(--purple-light);
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.card-preview {
  font-size: 12px;
  color: var(--text);
  line-height: 1.6;
  max-height: 200px;
  overflow-y: auto;
}
.card-preview::-webkit-scrollbar { width: 4px; }
.card-preview::-webkit-scrollbar-thumb { background: var(--border); border-radius: 2px; }
.card-label {
  font-size: 10px;
  font-weight: 600;
  color: var(--text-dim);
  text-transform: uppercase;
  letter-spacing: 0.4px;
  margin-bottom: 3px;
}
.card-text { font-size: 12px; color: var(--text); word-break: break-word; }
.card-reply { margin-top: 6px; padding-top: 6px; border-top: 1px solid var(--border); }
.card-loading-text { color: var(--warning); }
.card-actions { display: flex; gap: 6px; margin-top: 4px; }
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 6px 16px;
  font-size: 13px;
  font-weight: 500;
  font-family: var(--font);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.15s;
  border: none;
  letter-spacing: 0.2px;
}
.btn:disabled { opacity: 0.35; cursor: not-allowed; }
.btn-default {
  background: var(--bg-card);
  border: 1px solid var(--border);
  color: var(--text);
}
.btn-default:hover:not(:disabled) {
  background: var(--bg-hover);
  border-color: var(--purple);
}
.btn-delete {
  background: #7f1d1d;
  color: white;
}
.btn-delete:hover:not(:disabled) {
  background: #991b1b;
}

/* Left bottom empty */
.left-bottom-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: var(--text-dim);
  font-size: 12px;
  text-align: center;
  line-height: 1.6;
}
.left-bottom-empty .empty-icon {
  font-size: 36px;
  color: var(--purple-dim);
  opacity: 0.4;
}

/* Right panel */
.right-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.project-grid {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
  gap: 10px;
  align-content: start;
}
.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: var(--text-dim);
  font-size: 13px;
  gap: 12px;
}
.empty-state .icon { font-size: 48px; opacity: 0.3; }

/* Project card */
.project-thumb {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-width: 0;
}
.project-thumb:hover {
  background: var(--bg-hover);
}
.project-thumb:hover {
  border-color: var(--purple);
  box-shadow: 0 0 8px var(--purple-glow);
  transform: translateY(-2px);
}
.project-thumb:active {
  transform: translateY(0);
}
.thumb-top { padding: 3px 8px; display: flex; gap: 8px; align-items: flex-start; }
.thumb-avatar { border-radius: 4px; flex-shrink: 0; }
.thumb-right {
  flex: 1;
  min-width: 0;
  max-width: 76px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  align-items: flex-end;
}
.thumb-status {
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 10px;
  font-weight: 600;
}
.thumb-status.active { background: rgba(34, 197, 94, 0.15); color: var(--success); }
.thumb-status.running { background: rgba(245, 158, 11, 0.15); color: var(--warning); }
.thumb-status.failed { background: rgba(239, 68, 68, 0.15); color: var(--error); }
.thumb-reply {
  font-size: 8px;
  color: var(--text);
  line-height: 1.2;
  display: -webkit-box;
  -webkit-line-clamp: 6;
  -webkit-box-orient: vertical;
  overflow: hidden;
  min-height: 12px;
  word-break: break-all;
}
.thumb-bottom {
  padding: 4px 8px 8px;
  font-size: 9px;
  color: var(--text-dim);
  text-align: center;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  background: rgba(255, 255, 255, 0.04);
  border-radius: 4px;
}
.project-thumb.loading-pulse {
  animation: pulse 1.5s ease-in-out infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}

/* Modal */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
  backdrop-filter: blur(4px);
}

/* Confirm dialog */
.confirm-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 200;
  backdrop-filter: blur(4px);
}
.confirm-dialog {
  background: var(--bg2);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 24px;
  min-width: 300px;
  box-shadow: 0 0 40px var(--purple-glow);
}
.confirm-message {
  color: var(--text);
  font-size: 14px;
  margin-bottom: 20px;
}
.confirm-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}
.modal {
  background: var(--bg2);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 32px;
  min-width: 560px;
  max-width: 700px;
  width: 90vw;
  box-shadow: 0 0 60px var(--purple-glow);
}
.modal-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
  position: relative;
}
.modal-header-left { flex: 1; }
.modal-header-right { display: flex; align-items: flex-end; gap: 8px; }
.modal-user-row { display: flex; align-items: center; gap: 4px; }
.modal-avatar-block {
  flex-shrink: 0;
  border-radius: 8px;
  background: transparent;
}
.modal-avatar-img {
  border-radius: 6px;
  border: 2px solid transparent;
}
.modal-avatar-label {
  font-size: 12px;
  color: var(--text);
  white-space: nowrap;
}
.modal-avatar-user .modal-avatar-img { border-color: rgba(124, 58, 237, 0.5); }
.modal-avatar-project .modal-avatar-img { border-color: rgba(34, 197, 94, 0.5); }
.status-badge {
  font-size: 12px;
  padding: 4px 12px;
  border-radius: 12px;
  font-weight: 600;
}
.status-badge.modal-status-header {
  font-size: 11px;
  padding: 3px 10px;
  border-radius: 10px;
  font-weight: 600;
  margin-left: 4px;
  align-self: flex-end;
  margin-bottom: 2px;
}
.status-badge.active { background: rgba(34, 197, 94, 0.15); color: var(--success); }
.status-badge.running { background: rgba(245, 158, 11, 0.15); color: var(--warning); }
.status-badge.failed { background: rgba(239, 68, 68, 0.15); color: var(--error); }
.retries-badge { font-size: 11px; color: var(--text-dim); }
.btn-close {
  position: static;
  background: none;
  border: none;
  color: var(--text-dim);
  font-size: 18px;
  cursor: pointer;
  padding: 4px 0 0 4px;
}
.btn-close:hover { color: var(--text); }
.modal-body {
  margin-bottom: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.detail-panels { display: flex; gap: 16px; margin-bottom: 16px; }
.detail-panel {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 12px;
}
.detail-panel-left { flex: 1; }
.detail-panel-right { flex: 2; }
.detail-label {
  font-size: 10px;
  text-transform: uppercase;
  color: var(--text-dim);
  margin-bottom: 6px;
  letter-spacing: 0.5px;
}
.detail-text {
  font-size: 13px;
  color: var(--text);
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}
.detail-text.reply {
  height: 12em;
  overflow-y: auto;
}
.detail-text.error { color: var(--error); }
.detail-meta {
  display: grid;
  grid-template-columns: 1fr;
  gap: 4px 0;
  font-size: 12px;
  color: var(--text-dim);
}
.modal-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-top: 1px solid var(--border);
  padding-top: 12px;
}
.modal-footer-left { flex: 1; color: var(--text-dim); font-size: 12px; }
.token-total {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 6px 12px;
}
.token-label { font-size: 10px; color: var(--text-dim); display: block; }
.token-value { font-size: 14px; color: var(--text); font-weight: 600; }
.modal-footer-right { display: flex; gap: 8px; }
.btn-continue {
  padding: 6px 16px;
  font-size: 13px;
  font-weight: 500;
  font-family: var(--font);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.15s;
  border: none;
  background: var(--purple);
  color: white;
  letter-spacing: 0.2px;
}
.btn-continue:disabled { opacity: 0.35; cursor: not-allowed; }
.btn-delete {
  background: #7f1d1d;
  color: white;
  padding: 6px 16px;
  font-size: 13px;
  font-weight: 500;
  font-family: var(--font);
  border: none;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.15s;
  letter-spacing: 0.2px;
}
.btn-delete:hover:not(:disabled) {
  background: #991b1b;
}

/* Scrollbar */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--purple); }
</style>