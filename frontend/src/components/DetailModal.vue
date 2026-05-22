<template>
  <div v-if="visible" class="modal-overlay" @click.self="$emit('close')">
    <div class="modal">
      <div class="modal-header">
        <div>
          <div class="modal-title">
            <img class="modal-avatar" :src="avatarUrl(project.session_avatar_id, 'session')" :width="24" :height="24" />
            <span>{{ shortPath }}</span>
            <span :class="['thumb-status', statusClass]" style="margin-left:8px">{{ statusLabel }}</span>
            <span v-if="project.retries > 0" style="margin-left:4px;color:var(--red)">({{ project.retries }}次重试)</span>
          </div>
          <div class="modal-subtitle">
            {{ userName }} | {{ project.folder_name }} | SID: {{ sid }}
          </div>
        </div>
        <button class="btn-close" @click="$emit('close')">✕</button>
      </div>

      <div class="modal-body">
        <div class="detail-section">
          <div class="detail-label">原始消息</div>
          <div class="detail-text">{{ project.user_input || '—' }}</div>
        </div>

        <div class="detail-section" v-if="replyText || project.error">
          <div class="detail-label">回复内容</div>
          <div class="detail-text reply" v-if="replyText">{{ replyText }}</div>
          <div class="detail-text error" v-if="project.error">{{ project.error }}</div>
        </div>

        <div class="detail-meta">
          <div v-if="turns">轮次: {{ turns }}</div>
          <div v-if="cost != null">费用: ${{ cost?.toFixed(4) }}</div>
          <div v-if="project.is_finished === 0">状态: 活跃中 (PID: {{ project.subprocess_pid || '—' }})</div>
          <div v-if="project.created_at">创建: {{ dateStr(project.created_at) }}</div>
          <div v-if="project.session_id">Session: {{ project.session_id }}</div>
        </div>
      </div>

      <div class="modal-footer">
        <button class="btn-continue" @click="$emit('retry')"
          :disabled="sending || statusClass !== 'failed'"
          title="发送 Continue. 重试">
          {{ sending ? '发送中...' : '重试 ▶' }}
        </button>
        <button class="btn-delete" @click="$emit('delete')">🗑 删除</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { avatarUrl } from '../utils/avatar.js'

const props = defineProps({
  project: { type: Object, required: true },
  visible: { type: Boolean, default: false },
  sending: { type: Boolean, default: false },
  userName: { type: String, default: '' },
})

defineEmits(['close', 'retry', 'delete'])

const shortPath = computed(() => {
  if (!props.project.folder_name) return '—'
  return props.project.folder_name.split('/').filter(Boolean).slice(-2).join('/')
})

const statusLabel = computed(() => {
  const p = props.project
  if (p.is_finished === 0) return '活跃'
  if (p.status === 0) return '完成'
  const labels = { 1: 'API', 2: '超限', 3: '超时', 4: 'JSON', 5: '异常' }
  return labels[p.status] || '未知'
})

const statusClass = computed(() => {
  const p = props.project
  if (p.is_finished === 0) return 'active'
  if (p.status === 0) return 'active'
  return 'failed'
})

const sid = computed(() => {
  if (!props.project.session_id) return '—'
  return props.project.session_id.substring(0, 16) + '...'
})

const replyText = computed(() => {
  if (!props.project.claude_result) return ''
  try {
    const cr = typeof props.project.claude_result === 'string'
      ? JSON.parse(props.project.claude_result)
      : props.project.claude_result
    return cr.result || cr.output || ''
  } catch { return '' }
})

const turns = computed(() => {
  if (!props.project.claude_result) return null
  try {
    const cr = typeof props.project.claude_result === 'string'
      ? JSON.parse(props.project.claude_result)
      : props.project.claude_result
    return cr.num_turns ?? null
  } catch { return null }
})

const cost = computed(() => {
  if (!props.project.claude_result) return null
  try {
    const cr = typeof props.project.claude_result === 'string'
      ? JSON.parse(props.project.claude_result)
      : props.project.claude_result
    return cr.total_cost_usd ?? null
  } catch { return null }
})

function dateStr(ts) {
  return new Date(ts * 1000).toLocaleString('zh-CN')
}
</script>
