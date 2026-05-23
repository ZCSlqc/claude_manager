<template>
  <div
    class="project-thumb"
    :class="{ active: selected, running: isRunning(project) }"
    @click="$emit('select', project)">
    <div class="thumb-top">
      <img class="thumb-avatar" :src="thumbAvatar" :width="60" :height="60" :title="project.folder_name" />
      <div class="thumb-right">
        <span :class="['thumb-status', thumbStatusClass(project)]">{{ thumbStatusLabel(project) }}</span>
        <div class="thumb-reply" :title="thumbReplyTitle(project)">{{ thumbReplyText(project) }}</div>
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

defineEmits(['select'])

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
