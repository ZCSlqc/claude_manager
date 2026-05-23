<template>
  <div
    class="project-thumb"
    :class="{ active: selected, loading: project._loading }"
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

const thumbAvatar = computed(() => {
  if (props.project._loading) {
    return props.project.session_avatar_id
      ? avatarUrl(props.project.session_avatar_id, 'session')
      : avatarUrl(1, 'session')
  }
  return avatarUrl(props.project.session_avatar_id, 'session')
})

function thumbPath(p) {
  return p.folder_name
}

function thumbStatusLabel(p) {
  if (p._loading) return '活跃'
  if (p.is_finished === 0) return '活跃'
  if (p.status === 0) return '完成'
  const labels = { 1: 'API 错误', 2: '轮次超限', 3: 'JSON 报错', 4: '进程异常', 5: '系统异常' }
  return labels[p.status] || '未知'
}

function thumbStatusClass(p) {
  if (p._loading || p.is_finished === 0) return 'running'
  if (p.status === 0) return 'active'
  return 'failed'
}

function extractReplyText(project) {
  if (!project.claude_result) return ''
  try {
    const cr = typeof project.claude_result === 'string'
      ? JSON.parse(project.claude_result)
      : project.claude_result
    return cr.result || cr.output || ''
  } catch { return '' }
}

function thumbReplyText(p) {
  if (p._loading) return '等待 Claude 回复...'
  const text = extractReplyText(p)
  if (!text) return ''
  return text.length > 24 ? text.substring(0, 24) + '…' : text
}

function thumbReplyTitle(p) {
  if (p._loading) return '等待 Claude 回复...'
  return extractReplyText(p)
}
</script>
