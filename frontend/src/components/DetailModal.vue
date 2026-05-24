<template>
  <div v-if="project" class="modal-overlay" @click.self="emit('close')">
    <div class="modal-container">
      <div class="modal-inner">
        <div class="modal-header">
          <div class="modal-header-left">
            <div class="modal-user-row">
              <div class="modal-avatar-block modal-avatar-user">
                <img class="modal-avatar-img"
                  :src="avatarUrl(getUserAvatarId(project.user_id), 'user')"
                  :width="60" :height="60" :title="userName" />
              </div>
              <span class="modal-avatar-label">{{ userName }}</span>
              <span class="modal-arrow">→</span>
              <div class="modal-avatar-block modal-avatar-project">
                <img class="modal-avatar-img"
                  :src="avatarUrl(project.session_avatar_id, 'session')"
                  :width="60" :height="60" :title="project.folder_name" />
              </div>
              <span class="modal-avatar-label">{{ project.folder_name }}</span>
            </div>
          </div>
          <div class="modal-header-right">
            <span class="detail-status" :class="statusClass">{{ statusLabel }}</span>
            <span v-if="project.retries > 0" class="detail-retries">({{ project.retries }}次重试)</span>
            <button class="modal-close" @click="emit('close')">✕</button>
          </div>
        </div>

        <div class="modal-body">
          <div class="modal-meta-line">
            <span>Session: {{ project.session_id || '—' }}</span>
          </div>
          <div class="detail-panels">
            <div class="detail-panel detail-panel-left" :class="{ failed: project.status && project.status > 0 }">
              <div class="detail-label-row">
                <span class="detail-label">Message</span>
                <button v-if="project.user_input" class="detail-copy" title="复制消息" @click="copyMessage">复制</button>
              </div>
              <div class="detail-text">{{ project.user_input || '—' }}</div>
            </div>
            <div class="detail-panel detail-panel-right" :class="{ failed: project.status && project.status > 0 }">
              <div class="detail-label-row">
                <div class="detail-label-group">
                  <span class="detail-label">Reply</span>
                  <div class="detail-label-actions">
                    <button v-if="project.is_finished && replyText" class="detail-copy" title="预览回复" @click="emit('preview', project)">预览</button>
                    <button v-if="project.is_finished && replyText" class="detail-copy" title="复制回复" @click="copyReply">复制</button>
                  </div>
                </div>
              </div>
              <div v-if="!project.is_finished" :class="['detail-text', 'reply', 'reply-running']">等待 Claude 回复...</div>
              <div v-else-if="replyText" :class="['detail-text', 'reply']">{{ replyText }}</div>
              <div v-else-if="project.error" class="detail-text error">{{ project.error }}</div>
              <div v-else class="detail-text">—</div>
            </div>
          </div>

          <div class="detail-meta">
            <div>
              <span>创建: {{ dateStr(project.created_at) }}</span>
              <span style="margin-left: 24px;" v-if="turns != null">轮次: {{ turns }}</span>
            </div>
            <div>
              <span>更新: {{ dateStr(project.updated_at) }}</span>
              <span style="margin-left: 24px;" v-if="formattedDuration !== '—'">用时: {{ formattedDuration }}</span>
            </div>
          </div>
        </div>

        <div class="modal-footer">
          <div class="modal-footer-left" v-if="totalTokens > 0">总token: {{ totalTokens >= 1000000 ? Math.floor(totalTokens / 1000000) + 'M' : fmtToken(totalTokens) }}</div>
          <div class="modal-footer-right">
            <button class="btn btn-default modal-btn-log" @click="emit('log', project)">日志</button>
            <button class="btn-continue" @click="emit('retry', project)"
              :disabled="sending">
              {{ sending ? '发送中...' : '重试 ▶' }}
            </button>
            <button class="btn-delete" @click="emit('delete', project)">删除项目</button>
            <button class="btn-delete-all" @click="emit('delete-user', project)">删除用户</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { avatarUrl } from '../utils/avatar.js'

const props = defineProps({
  project: { type: Object, required: true },
  sending: { type: Boolean, default: false },
  userMap: { type: Object, default: () => ({}) },
  totalTokens: { type: Number, default: 0 },
})

const emit = defineEmits(['close', 'retry', 'delete', 'delete-user', 'log'])

function getUserAvatarId(userId) {
  const u = props.userMap[userId]
  return u?.user_avatar_id ?? 1
}

const userName = computed(() => {
  if (!props.project) return ''
  return Object.entries(props.userMap).find(([uid]) => uid === props.project.user_id)?.[1]?.name || '?'
})

function getStatusLabel() {
  if (!props.project) return '—'
  if (!props.project.is_finished) return '活跃'
  if (props.project.status === 0) return '完成'
  return '失败'
}

function getStatusClass() {
  if (!props.project) return 'failed'
  if (!props.project.is_finished) return 'running'
  if (props.project.status === 0) return 'active'
  return 'failed'
}

const statusLabel = computed(getStatusLabel)
const statusClass = computed(getStatusClass)

const replyText = computed(() => props.project?.claude_output || '')

function copyReply() {
  if (replyText.value) {
    navigator.clipboard.writeText(replyText.value)
  }
}
function copyMessage() {
  if (props.project?.user_input) {
    navigator.clipboard.writeText(props.project.user_input)
  }
}

function parseModalData(prop) {
  if (!props.project) return null
  try {
    const cr = typeof props.project.claude_result === 'string'
      ? JSON.parse(props.project.claude_result)
      : props.project.claude_result
    return cr[prop] ?? null
  } catch { return null }
}

const turns = computed(() => parseModalData('num_turns'))
const duration = computed(() => parseModalData('duration_ms'))

const formattedDuration = computed(() => {
  if (duration.value == null) return '—'
  const s = Math.round(duration.value / 1000)
  const h = String(Math.floor(s / 3600)).padStart(2, '0')
  const m = String(Math.floor((s % 3600) / 60)).padStart(2, '0')
  const sec = String(s % 60).padStart(2, '0')
  return `${h}:${m}:${sec}`
})

function dateStr(ts) {
  return new Date(ts * 1000).toLocaleString()
}

function fmtToken(n) {
  if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M'
  if (n >= 1000) return (n / 1000).toFixed(1) + 'K'
  return String(n)
}
</script>

<style scoped>
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
.modal-container {
  background: var(--bg2);
  border: 1px solid var(--border);
  border-radius: 12px;
  width: 80vw;
  max-width: 900px;
  height: 60vh;
  min-height: 500px;
  max-height: 500px;
  display: flex;
  flex-direction: column;
  box-shadow: 0 0 60px var(--purple-glow);
}
.modal-inner {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
}
.modal-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 24px;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}
.modal-header-right { display: flex; align-items: center; gap: 8px; }
.modal-header-left { flex: 1; }
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
.modal-avatar-user .modal-avatar-img { border-color: rgba(124, 58, 237, 0.5); }
.modal-avatar-project .modal-avatar-img { border-color: rgba(34, 197, 94, 0.5); }
.modal-avatar-label {
  font-size: 12px;
  color: var(--text);
  white-space: nowrap;
}
.modal-body {
  padding: 24px;
  overflow-y: auto;
  flex: 1;
  min-height: 0;
}
.detail-panels { display: flex; gap: 16px; margin: 16px 0; }
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
.detail-label-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}
.detail-label-group {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
}
.detail-label-actions {
  display: flex;
  gap: 6px;
  flex-shrink: 0;
  margin-left: auto;
}
.detail-label {
  font-size: 15px;
  text-transform: uppercase;
  color: var(--text-dim);
  letter-spacing: 0.5px;
}
.detail-text {
  font-size: 15px;
  color: var(--text);
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
  height: 12em;
  overflow-y: auto;
  flex-shrink: 0;
}
.detail-text.reply {
  height: 12em;
  overflow-y: auto;
}
.reply-running {
  color: var(--warning);
}
.detail-text.error { color: var(--error); }
.detail-status {
  font-size: 12px;
  padding: 4px 12px;
  border-radius: 12px;
  font-weight: 600;
}
.detail-status.active { background: rgba(34, 197, 94, 0.15); color: var(--success); }
.detail-status.running { background: rgba(245, 158, 11, 0.15); color: var(--warning); }
.detail-status.failed { background: rgba(239, 68, 68, 0.15); color: var(--error); }
.detail-retries { font-size: 11px; color: var(--text-dim); }
.modal-meta-line {
  font-size: 11px;
  color: var(--text-dim);
  margin-bottom: 4px;
}
.detail-panels {
  gap: 8px;
  margin-bottom: 8px;
}
.detail-panel {
  padding: 8px;
}
.detail-label-row {
  margin-bottom: 4px;
}
.detail-meta {
  display: grid;
  grid-template-columns: 1fr;
  gap: 2px 0;
  font-size: 12px;
  color: var(--text-dim);
}
.modal-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 24px;
  border-top: 1px solid var(--border);
  flex-shrink: 0;
}
.modal-footer-left { flex: 1; color: var(--text-dim); font-size: 12px; }
.modal-footer-right { display: flex; gap: 8px; }
</style>
