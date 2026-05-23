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
              <div class="card-reply" v-if="getModalReplyText(selectedProject) || !selectedProject.is_finished">
                <div class="card-label">Reply</div>
                <div class="card-text" :class="{ 'card-reply-text': !selectedProject.is_finished, 'card-text': selectedProject.is_finished }">
                  {{ !selectedProject.is_finished ? '等待 Claude 回复...' : getModalReplyText(selectedProject) }}
                </div>
              </div>
            </div>
            <div class="card-actions card-actions-center">
              <button class="btn btn-default" @click="openModalFromSelected">详情</button>
              <button class="btn btn-default" @click="openLogModal">日志</button>
              <button class="btn btn-continue" @click="handleRetry"
                :disabled="sending || !canRetry(selectedProject)">
                重试
              </button>
              <button class="btn btn-delete" @click="handleDelete">删除</button>
            </div>
          </div>
          <div v-else class="left-bottom-empty">
            <div class="empty-icon">⬡</div>
            <div>选择 User 和 Project 后<br>在此显示详情</div>
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
            @select="handleSelect"
            @context="handleSelectByCard" />
        </div>
      </div>
    </div>

    <!-- Detail Modal -->
    <DetailModal
      v-if="modalProject"
      :project="modalProject"
      :sending="sending"
      :user-map="userMap"
      :total-tokens="modalTotalTokens"
      @close="closeModal"
      @retry="handleRetry"
      @delete="handleDelete"
      @log="openLogModal"
      @delete-user="handleDeleteUser"
    />

    <!-- Log Modal -->
    <LogModal
      v-if="showLogModal"
      :project-id="logProjectId"
      @close="showLogModal = false"
    />
  </div>

  <!-- Toast -->
  <div v-if="toast" :class="['toast', toast.type]">
    <span>{{ toast.msg }}</span>
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
import { ref, computed, onMounted, watch } from 'vue'
import * as api from './api/index.js'
import SendForm from './components/SendForm.vue'
import ProjectCard from './components/ProjectCard.vue'
import DetailModal from './components/DetailModal.vue'
import LogModal from './components/LogModal.vue'
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
const toast = ref(null) // { msg, type }
const currentUserId = ref('') // 跟踪当前表单选中的 user_id
const showLogModal = ref(false)
const logProjectId = ref('')

// ── Computed ──
const sortedProjects = computed(() => {
  return [...projects.value].sort((a, b) => (b.updated_at || 0) - (a.updated_at || 0))
})
const allProjects = sortedProjects

const modalTotalTokens = computed(() => {
  if (!modalProject.value) return 0
  return (modalProject.value.total_inputTokens || 0) + (modalProject.value.total_outputTokens || 0)
})

// ── Helpers ──
function getModalReplyText(p) {
  if (!p?.claude_output) return ''
  return p.claude_output
}
function getThumbStatusLabel(p) {
  if (!p) return '—'
  if (!p.is_finished) return '活跃'
  if (p.status === 0) return '完成'
  return '失败'
}
function getThumbStatusClass(p) {
  if (!p) return 'failed'
  if (!p.is_finished) return 'running'
  if (p.status === 0) return 'active'
  return 'failed'
}
function canRetry(p) {
  if (!p) return false
  return p.is_finished === 1 && p.status > 0
}

// ── Actions ──
async function fetchAll() {
  try {
    const pData = await api.getProjects()
    projects.value = Array.isArray(pData) ? pData : (pData.code || [])
  } catch (e) {
    console.error('fetchAll error:', e)
  }
}

async function refreshProjects() {
  try {
    const pData = await api.getProjects()
    projects.value = Array.isArray(pData) ? pData : (pData.code || [])
  } catch (e) {
    console.error('refreshProjects error:', e)
  }
}

function handleSelect(p) {
  // 右侧卡片点击 → 只打开 Modal 弹窗，不动左侧概览卡片
  modalProject.value = { ...p }
}
function handleSelectByDir(dir) {
  // form.dir 已在 pickDir 中设置，watch 会自动触发，这里不需要额外操作
}
function handleSelectByCard(p) {
  // 双击右侧卡片 → 更新左侧用户/项目卡片
  const u = Object.entries(userMap.value).find(([uid]) => uid === p.user_id)?.[1]
  if (u) {
    formRef.value.form.user = u.name
    formRef.value.form.dir = p.folder_name
  }
}

async function handleSend() {
  if (sending.value) return
  const { user, dir, message } = formRef.value.form
  if (!message.trim() || !user || !dir) return

  sending.value = true
  formRef.value.form.message = ''

  try {
    const res = await api.sendChat(user, dir, message)
    const project_id = res.detail?.project_id || res.project_id

    if (res.success !== false) {
      sending.value = false
    }

    // 立即刷新一次
    await refreshProjects()

    // 找到新创建的项目并赋给 selectedProject
    const newProj = projects.value.find(p => p.project_id === project_id)
    if (newProj) {
      selectedProject.value = { ...newProj }
    }
  } catch (err) {
    sending.value = false
    if (err.status === 409) {
      showToast(err.error || 'session 使用中', 'error')
    } else {
      showToast('发送失败: ' + (err.detail || err.message || JSON.stringify(err)), 'error')
    }
    await refreshProjects()
  }
}

function _targetProject() {
  return selectedProject.value || modalProject.value
}

function showToast(msg, type = 'error') {
  toast.value = { msg, type }
  setTimeout(() => { toast.value = null }, 2000)
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
      const result = await api.retryProject(proj.project_id)
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
function openLogModal(e, proj) {
  const p = proj || selectedProject.value
  if (p) {
    logProjectId.value = p.project_id
    showLogModal.value = true
  }
}
function handleDeleteUser(proj) {
  const uid = proj?.user_id
  if (!uid) return
  const userName = Object.entries(userMap.value).find(([u]) => u === uid)?.[1]?.name || '?'
  showConfirm(`确定要删除用户 "${userName}" 及其所有项目吗？`, async () => {
    try {
      await api.deleteUser(uid)
      await refreshProjects()
      selectedProject.value = null
      modalProject.value = null
    } catch (e) {
      alert('删除用户失败: ' + e.message)
    }
  })
}

// ── Init ──
onMounted(async () => {
  try {
    const uData = await api.getUsers()
    users.value = Array.isArray(uData) ? uData : (uData.code || [])
    for (const u of users.value) {
      userMap.value[u.user_id] = { name: u.name, user_avatar_id: u.user_avatar_id }
    }
    await fetchAll()
    // 恢复 localStorage 缓存的 user/dir，更新左侧卡片
    const cachedUser = localStorage.getItem('pref_user')
    const cachedDir = localStorage.getItem('pref_dir')
    if (cachedUser && cachedDir) {
      formRef.value.form.user = cachedUser
      formRef.value.form.dir = cachedDir
      currentUserId.value = Object.entries(userMap.value).find(([uid, u]) => u.name === cachedUser)?.[0] || ''
      if (currentUserId.value) {
        const p = projects.value.find(p => p.folder_name === cachedDir && p.user_id === currentUserId.value)
        selectedProject.value = p ? { ...p } : null
      }
    }
  } catch (e) {
    console.error('onMounted error:', e)
  }
  // 每 3s 轮询，更新左侧卡片和 modal
  setInterval(async () => {
    await refreshProjects()
    if (selectedProject.value) {
      const updated = projects.value.find(p => p.project_id === selectedProject.value.project_id)
      if (updated) selectedProject.value = { ...updated }
    }
    if (modalProject.value) {
      const updated = projects.value.find(p => p.project_id === modalProject.value.project_id)
      if (updated) modalProject.value = { ...updated }
    }
  }, 3000)
})

// 仅当 user/dir 变化时更新左侧卡片，message 变化不触发
watch(
  () => [formRef.value?.form.user, formRef.value?.form.dir],
  ([user, dir]) => {
    if (user && dir) {
      currentUserId.value = Object.entries(userMap.value).find(([uid, u]) => u.name === user)?.[0] || ''
      if (currentUserId.value) {
        const p = projects.value.find(p => p.folder_name === dir && p.user_id === currentUserId.value)
        selectedProject.value = p ? { ...p } : null
      } else {
        selectedProject.value = null
      }
    } else {
      currentUserId.value = ''
      selectedProject.value = null
    }
  }
)
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
.card-reply-text { font-size: 12px; color: var(--warning); word-break: break-word; }
.card-reply { margin-top: 6px; padding-top: 6px; border-top: 1px solid var(--border); }
.card-actions { display: flex; gap: 6px; margin-top: 4px; justify-content: center; }
.card-actions-center { display: flex; gap: 6px; margin-top: 4px; justify-content: center; }
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
.thumb-reply-running {
  color: var(--warning);
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
/* Toast */
.toast {
  position: fixed;
  top: 12px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 300;
  padding: 10px 24px;
  border-radius: 10px;
  font-size: 13px;
  font-weight: 500;
  color: white;
  background: var(--error);
  border: 1px solid var(--border);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4);
  animation: toastIn 0.2s ease-out;
}
@keyframes toastIn {
  from { opacity: 0; transform: translateX(-50%) translateY(-8px); }
  to { opacity: 1; transform: translateX(-50%) translateY(0); }
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
  border-bottom: 1px solid var(--border);
  padding-bottom: 16px;
}
.modal-header-right { display: flex; align-items: center; gap: 8px; }
.modal-header-left { flex: 1; }
.modal-user-row { display: flex; align-items: center; gap: 4px; }
.modal-meta-line {
  font-size: 11px;
  color: var(--text-dim);
  margin-top: 2px;
}
.modal-meta-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--text);
}
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
  padding: 0;
  margin-top: -10px;
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
  padding: 18px;
}
.detail-panel.failed {
  background: rgba(239, 68, 68, 0.05);
  border-color: rgba(239, 68, 68, 0.3);
}
.detail-panel-left { flex: 1; }
.detail-panel-right { flex: 2; }
.detail-label {
  font-size: 15px;
  text-transform: uppercase;
  color: var(--text-dim);
  margin-bottom: 8px;
  letter-spacing: 0.5px;
}
.detail-text {
  font-size: 15px;
  color: var(--text);
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}
.detail-text.reply {
  height: 12em;
  overflow-y: auto;
}
.reply-running {
  color: var(--warning);
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
.btn-continue:hover:not(:disabled) {
  background: #6d28d9;
}
.btn-continue:active:not(:disabled) {
  background: #5b21b6;
}
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
.btn-delete-all {
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
.btn-delete-all:hover:not(:disabled) {
  background: #991b1b;
}

/* Scrollbar */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--purple); }
</style>