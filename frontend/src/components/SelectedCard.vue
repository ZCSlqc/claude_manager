<template>
  <div class="selected-card">
    <div class="card-header">
      <img class="card-avatar" :src="avatarUrl(project.session_avatar_id || 1, 'session')" :width="20" :height="20" />
      <span :class="['card-status', statusClass]">{{ statusLabel }}</span>
    </div>
    <div class="card-path" :title="project.folder_name">{{ project.folder_name }}</div>
    <div class="card-preview">
      <div v-if="project.user_input" class="card-input">
        <div class="card-label">Message</div>
        <div class="card-text">{{ project.user_input }}</div>
      </div>
      <div class="card-reply" v-if="replyText || !project.is_finished">
        <div class="card-label">Reply</div>
        <div class="card-text" :class="{ 'card-reply-text': !project.is_finished, 'card-text': project.is_finished }">
          {{ !project.is_finished ? '等待 Claude 回复...' : replyText }}
        </div>
      </div>
    </div>
    <div class="card-actions card-actions-center">
      <button class="btn btn-default" @click="$emit('open-modal')">{{ project?.folder_name ? '详情' : '' }}</button>
      <button class="btn btn-default" @click="$emit('open-log')">{{ project?.folder_name ? '日志' : '' }}</button>
      <button class="btn btn-continue" @click="$emit('retry')"
        :disabled="sending || !canRetry(project)">
        重试
      </button>
      <button class="btn btn-delete" @click="$emit('delete')">{{ project?.folder_name ? '删除' : '' }}</button>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { avatarUrl } from '../utils/avatar.js'

const props = defineProps({
  project: { type: Object, required: true },
  sending: { type: Boolean, default: false },
})

defineEmits(['open-modal', 'open-log', 'retry', 'delete'])

const statusLabel = computed(() => {
  if (!props.project) return '—'
  if (!props.project.is_finished) return '活跃'
  if (props.project.status === 0) return '完成'
  return '失败'
})

const statusClass = computed(() => {
  if (!props.project) return 'failed'
  if (!props.project.is_finished) return 'running'
  if (props.project.status === 0) return 'active'
  return 'failed'
})

const replyText = computed(() => props.project?.claude_output || '')

function canRetry(p) {
  if (!p) return false
  return p.is_finished === 1 && p.status > 0
}
</script>

<style scoped>
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
.card-actions {
  display: flex;
  gap: 6px;
  margin-top: 4px;
  justify-content: center;
}
</style>
