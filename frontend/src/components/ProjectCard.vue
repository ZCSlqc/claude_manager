<template>
  <div
    class="project-thumb"
    :class="{ active: selected, running: isRunning(project) }"
    @contextmenu.prevent="$emit('select', project)"
    @click="$emit('context', project)">
    <div class="thumb-top">
      <img class="thumb-avatar" :src="thumbAvatar" :width="60" :height="60" :title="project.folder_name" style="image-rendering: pixelated" />
      <div class="thumb-right">
        <span :class="['thumb-status', thumbStatusClass(project)]">{{ thumbStatusLabel(project) }}</span>
        <div :class="['thumb-reply', { 'thumb-reply-running': !project.is_finished }]" :title="thumbReplyTitle(project)">{{ thumbReplyText(project) }}</div>
      </div>
    </div>
    <div class="thumb-bottom" :title="project.folder_name">{{ thumbPath(project) }}</div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { avatarUrl } from '../utils/avatar.js'

const props = defineProps({
  project: { type: Object, required: true },
  selected: { type: Boolean, default: false },
})

defineEmits(['select', 'context', 'open-reply'])

function isRunning(p) {
  return !p.is_finished
}

const thumbAvatar = computed(() => {
  return avatarUrl(props.project.session_avatar_id ?? 1, 'session')
})

function thumbPath(p) {
  return p.folder_name
}

function thumbStatusLabel(p) {
  if (!p.is_finished) return '活跃'
  if (p.status === 0) return '完成'
  return '失败'
}

function thumbStatusClass(p) {
  if (!p.is_finished) return 'running'
  if (p.status === 0) return 'active'
  return 'failed'
}

function extractReplyText(project) {
  return project.claude_output || ''
}

function thumbReplyText(p) {
  if (!p.is_finished) return '等待 Claude 回复...'
  const text = extractReplyText(p)
  if (!text) return ''
  return text.length > 24 ? text.substring(0, 24) + '…' : text
}

function thumbReplyTitle(p) {
  if (!p.is_finished) return '等待 Claude 回复...'
  return extractReplyText(p)
}
</script>

<style scoped>
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
.project-thumb.active {
  border-color: var(--purple);
  box-shadow: 0 0 8px var(--purple-glow);
}
.thumb-top { padding: 3px 8px; display: flex; gap: 8px; align-items: flex-start; flex: 1; }
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
  margin-top: auto;
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
</style>
