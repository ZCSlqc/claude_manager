<template>
  <div v-if="project" class="modal-overlay" @click.self="emit('close')">
    <div class="modal">
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
          <span class="thumb-status" :class="statusClass">{{ statusLabel }}</span>
          <span v-if="project.retries > 0" class="retries-badge">({{ project.retries }}次重试)</span>
          <button class="btn-close" @click="emit('close')">✕</button>
        </div>
      </div>

      <div class="modal-body">
        <div class="modal-meta-line">
          <span>Session: {{ project.session_id || '—' }}</span>
        </div>
        <div class="detail-panels">
          <div class="detail-panel detail-panel-left" :class="{ failed: project.status && project.status > 0 }">
            <div class="detail-label">Message</div>
            <div class="detail-text">{{ project.user_input || '—' }}</div>
          </div>
          <div class="detail-panel detail-panel-right" :class="{ failed: project.status && project.status > 0 }">
            <div class="detail-label">Reply</div>
            <div v-if="!project.is_finished" :class="['detail-text', 'reply', 'reply-running']">等待 Claude 回复...</div>
            <div v-else-if="replyText" :class="['detail-text', 'reply']">{{ replyText }}</div>
            <div v-if="project.error && !replyText" class="detail-text error">{{ project.error }}</div>
            <div v-if="!replyText && !project.is_finished && !project.error" class="detail-text">—</div>
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
