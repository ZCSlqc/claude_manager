<template>
  <div v-if="visible" class="modal-overlay" @click.self="$emit('close')">
    <div class="modal-log">
      <div class="modal-log-header">
        <span>Reply 预览</span>
        <div class="modal-log-right">
          <button class="btn-copy" @click="copyReply">复制</button>
          <button class="btn-close" @click="$emit('close')">✕</button>
        </div>
      </div>
      <div class="modal-log-body">
        <pre v-if="content">{{ content }}</pre>
        <div v-else class="log-empty">—</div>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  content: { type: String, default: '' },
  visible: { type: Boolean, default: false },
})

defineEmits(['close'])

function copyReply() {
  if (content) {
    navigator.clipboard.writeText(content)
  }
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
.modal-log {
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
.modal-log-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 24px;
  border-bottom: 1px solid var(--border);
  font-size: 14px;
  color: var(--text);
  flex-shrink: 0;
}
.modal-log-right {
  display: flex;
  align-items: center;
  gap: 8px;
}
.modal-log-body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 16px 24px;
}
.modal-log-body pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-all;
  font-size: 12px;
  line-height: 1.5;
  color: var(--text);
  font-family: var(--font);
}
.log-empty {
  color: var(--text-dim);
  font-size: 13px;
  text-align: center;
  margin-top: 40px;
}
</style>
