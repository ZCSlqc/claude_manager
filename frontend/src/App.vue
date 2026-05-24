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
          <SelectedCard
            v-if="selectedProject"
            :project="selectedProject"
            :sending="sending"
            @open-modal="openModalFromSelected"
            @open-log="openLogModal"
            @retry="handleRetry"
            @delete="handleDelete"
          />
          <div v-else class="left-bottom-empty">
            <div class="empty-icon">⬡</div>
            <div>选择 User 和 Project 后<br>在此显示详情</div>
          </div>
        </div>
      </div>

      <!-- Right Panel: all project cards -->
      <ProjectGrid
        :projects="allProjects"
        :selected-project-id="modalProject?.project_id || ''"
        @select="handleSelect"
        @context="handleSelectByCard"
        @open-reply="openReplyPreview"
      />
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
      @preview="openReplyPreview"
    />

    <!-- Log Modal -->
    <LogModal
      v-if="showLogModal"
      :project-id="logProjectId"
      @close="showLogModal = false"
    />

    <!-- Reply Preview Modal -->
    <ReplyPreviewModal
      :content="modalProject?.claude_output || '—'"
      :visible="showReplyPreview"
      @close="showReplyPreview = false"
    />

    <!-- Toast -->
    <Toast
      :msg="toast?.msg || ''"
      :type="toast?.type || 'error'"
      :visible="!!toast"
    />

    <!-- Confirm Dialog -->
    <ConfirmDialog
      :message="confirmDialog?.message || ''"
      :label="confirmDialog?.label || '确定'"
      :cancel-label="confirmDialog?.cancelLabel || '取消'"
      :visible="!!confirmDialog"
      @confirm="confirmDialog?.onConfirm(); confirmDialog = null"
      @cancel="confirmDialog = null"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import * as api from './api/index.js'
import SendForm from './components/SendForm.vue'
import ProjectGrid from './components/ProjectGrid.vue'
import SelectedCard from './components/SelectedCard.vue'
import DetailModal from './components/DetailModal.vue'
import LogModal from './components/LogModal.vue'
import ReplyPreviewModal from './components/ReplyPreviewModal.vue'
import Toast from './components/Toast.vue'
import ConfirmDialog from './components/ConfirmDialog.vue'

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
const showReplyPreview = ref(false)

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
function showToast(msg, type = 'error') {
  toast.value = { msg, type }
  setTimeout(() => { toast.value = null }, 2000)
}

function showConfirm(message, onConfirm) {
  confirmDialog.value = { message, onConfirm, label: '确定', cancelLabel: '取消' }
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
  modalProject.value = { ...p }
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
function openReplyPreview(proj) {
  showReplyPreview.value = true
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
    await refreshProjects()
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

/* Global Button Styles */
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

.btn-primary {
  background: var(--purple);
  color: white;
}
.btn-primary:hover:not(:disabled) {
  background: #6d28d9;
}
.btn-primary:active:not(:disabled) {
  background: #5b21b6;
}

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

.btn-copy {
  padding: 4px 12px;
  font-size: 12px;
  font-weight: 500;
  font-family: var(--font);
  border-radius: 8px;
  cursor: pointer;
  border: 1px solid var(--border);
  background: var(--bg-card);
  color: var(--text);
  transition: all 0.15s;
}
.btn-copy:hover {
  background: var(--purple);
  color: white;
  border-color: var(--purple);
}

.btn-close {
  background: none;
  border: none;
  color: var(--text-dim);
  font-size: 18px;
  cursor: pointer;
  padding: 0 4px;
}
.btn-close:hover {
  color: var(--text);
}

.detail-copy {
  background: transparent;
  border: 1px solid var(--border);
  border-radius: 8px;
  color: var(--text-dim);
  font-size: 12px;
  font-weight: 500;
  padding: 2px 10px;
  cursor: pointer;
  transition: all 0.2s;
}
.detail-copy:hover {
  color: var(--purple);
}

.modal-close {
  background: none;
  border: none;
  color: var(--text-dim);
  font-size: 18px;
  cursor: pointer;
  padding: 0 4px;
}
.modal-close:hover { color: var(--text); }

.btn-send {
  width: 100%;
  padding: 10px;
  min-height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 8px;
  background: linear-gradient(135deg, var(--purple), #6d28d9);
  color: white;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: box-shadow 0.2s, transform 0.2s;
  letter-spacing: 0.3px;
  margin-top: -6px;
}
.btn-send:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}
.btn-send:not(:disabled):hover {
  box-shadow: 0 4px 16px rgba(124, 58, 237, 0.4);
  transform: translateY(-1px);
}
.btn-send:not(:disabled):active {
  transform: translateY(0);
}

.small-arrow {
  flex-shrink: 0;
  width: 32px;
  height: 38px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--bg3);
  color: var(--text-dim);
  font-size: 9px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
  line-height: 1;
}
.small-arrow:hover {
  background: var(--purple);
  color: white;
  border-color: var(--purple);
}
.small-arrow:active {
  transform: scale(0.95);
}

/* Scrollbar */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--purple); }
</style>
