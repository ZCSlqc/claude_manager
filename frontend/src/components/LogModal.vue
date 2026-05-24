<template>
  <div v-if="visible" class="modal-overlay" @click.self="close">
    <div class="modal-log">
      <div class="modal-log-header">
        <span>日志{{ logFile ? ` — ${logFile}` : '' }}</span>
        <div class="modal-log-right">
          <button class="btn-copy" @click="refreshLog">刷新</button>
          <button class="btn-copy" @click="copyLog">复制</button>
          <button class="btn-close" @click="close">✕</button>
        </div>
      </div>
      <div class="modal-log-body" ref="logBodyRef">
        <pre v-if="content">{{ content }}</pre>
        <div v-else class="log-empty">暂无日志</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick } from 'vue'
import * as api from '../api/index.js'

const props = defineProps({
  projectId: { type: String, required: true },
})

const emit = defineEmits(['close'])

const visible = ref(true)
const content = ref('')
const logFile = ref('')
const logBodyRef = ref(null)
let pollTimer = null

function startPolling() {
  pollTimer = setInterval(loadLog, 5000)
}
function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

async function loadLog() {
  try {
    const res = await api.getClaudeLog(props.projectId)
    content.value = res.detail?.log_content || ''
    logFile.value = res.detail?.log_file || ''
    // 加载完后自动滚动到底部
    nextTick(() => {
      if (logBodyRef.value) {
        logBodyRef.value.scrollTop = logBodyRef.value.scrollHeight
      }
    })
    // 首次加载成功后开始自动轮询
    startPolling()
  } catch (e) {
    console.error('loadLog error:', e)
  }
}

function close() {
  stopPolling()
  visible.value = false
  emit('close')
}

function copyLog() {
  navigator.clipboard.writeText(content.value)
}
function refreshLog() {
  loadLog()
}

loadLog()
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 150;
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
