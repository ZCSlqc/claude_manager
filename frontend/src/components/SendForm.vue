<template>
  <!-- 上半部分：选择 + 输入 -->
  <div class="form-section">
    <!-- User 选择 -->
    <div class="form-group">
      <label>User</label>
      <div class="with-arrow">
        <input v-model="form.user" placeholder="选择或输入 User" />
        <button class="small-arrow" @click.stop="showDD = showDD === 'user' ? '' : 'user'"
          :title="users.length + ' 个 User'">▼</button>
      </div>
      <div class="dropdown" v-if="showDD === 'user' && users.length > 0">
        <div class="dd-item" v-for="u in users" :key="u.name"
          @click.stop="pickUser(u.name)">{{ u.name }}</div>
      </div>
    </div>

    <!-- 项目目录 -->
    <div class="form-group">
      <label>Project</label>
      <div class="with-arrow">
        <input v-model="form.dir" placeholder="选择或输入 Project" :disabled="!form.user" />
        <button class="small-arrow" @click.stop="showDirDD"
          :title="(availableDirs.length) + ' 个项目'">▼</button>
      </div>
      <div class="dropdown" v-if="showDD === 'dir' && form.user">
        <div class="dd-item" v-for="d in availableDirs" :key="d"
          @click.stop="pickDir(d)">{{ d }}</div>
      </div>
    </div>

    <!-- 消息输入 -->
    <div class="form-group">
      <label>Message</label>
      <textarea v-model="form.message" placeholder="Enter a message... (Ctrl+Enter)"
        @keydown.ctrl.enter="$emit('send')" :disabled="sending"></textarea>
    </div>

    <button class="btn-send" @click="$emit('send')" :disabled="sending || !canSend">
      {{ sending ? '发送中...' : '发送 ▶' }}
    </button>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import * as api from '../api/index.js'

const props = defineProps({
  users: { type: Array, default: () => [] },
  sending: { type: Boolean, default: false },
})

const emit = defineEmits(['send', 'select-project'])

function loadPrefs() {
  try {
    const u = localStorage.getItem('pref_user')
    const d = localStorage.getItem('pref_dir')
    return { user: u || '', dir: d || '', message: '' }
  } catch { return { user: '', dir: '', message: '' } }
}

const form = ref(loadPrefs())
const showDD = ref('')
const projectDirs = ref([])
const userIdMap = ref({}) // name -> user_id

const availableDirs = computed(() => projectDirs.value)

const canSend = computed(() => {
  return form.value.user && form.value.dir && form.value.message.trim() && !props.sending
})

async function loadUserProjects() {
  if (!form.value.user) {
    projectDirs.value = []
    return
  }
  try {
    // 直接从 props 里找 user_id，用最新的 users 数据
    const name = form.value.user
    let uid = userIdMap.value[name]
    if (!uid) {
      const u = props.users.find(u => u.name === name)
      if (!u) return
      uid = u.user_id
      userIdMap.value[name] = uid
    }
    const pData = await api.getProjects(uid)
    projectDirs.value = (Array.isArray(pData) ? pData : (pData.code || [])).map(p => p.folder_name)
  } catch (e) {
    console.error('loadUserProjects error:', e)
  }
}

function onUserInput() {
  loadUserProjects()
}

function pickUser(name) {
  form.value.user = name
  form.value.dir = ''
  projectDirs.value = []
  showDD.value = ''
  try { localStorage.setItem('pref_user', name) } catch {}
  setTimeout(() => { loadUserProjects() }, 10)
}

function showDirDD() {
  showDD.value = showDD.value === 'dir' ? '' : 'dir'
}

function pickDir(d) {
  form.value.dir = d
  showDD.value = ''
  try { localStorage.setItem('pref_dir', d) } catch {}
  emit('select-project', d)
}

// 点击输入框外关闭下拉
document.addEventListener('click', (e) => {
  if (!e.target.closest('.form-group') && showDD.value) {
    showDD.value = ''
  }
}, true)

defineExpose({ form, canSend })
</script>

<style scoped>
.form-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.form-group {
  position: relative;
}

.form-group label {
  display: block;
  font-size: 10px;
  font-weight: 600;
  color: var(--text-dim);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 6px;
}

.with-arrow {
  display: flex;
  gap: 6px;
  position: relative;
}

.with-arrow input {
  flex: 1;
}

.form-group input,
.form-group textarea {
  width: 100%;
  padding: 9px 12px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--bg-card);
  color: var(--text);
  font-size: 13px;
  font-family: inherit;
  outline: none;
  transition: all 0.2s;
}

.form-group input:focus,
.form-group textarea:focus {
  border-color: var(--purple);
  box-shadow: 0 0 0 2px rgba(124, 58, 237, 0.15);
}

.form-group input:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.form-group textarea {
  min-height: 72px;
  resize: vertical;
  line-height: 1.5;
}

.small-arrow {
  flex-shrink: 0;
  width: 32px;
  height: 38px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--bg3);
  color: var(--text-dim);
  font-size: 9px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
  line-height: 1;
}

.small-arrow:hover {
  background: var(--purple);
  color: white;
  border-color: var(--purple);
  transform: scale(1.05);
}

.small-arrow:active {
  transform: scale(0.95);
}

.dropdown {
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  z-index: 100;
  margin-top: 4px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 10px;
  max-height: 180px;
  overflow-y: auto;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
}

.dropdown::-webkit-scrollbar {
  width: 4px;
}

.dropdown::-webkit-scrollbar-thumb {
  background: var(--border);
  border-radius: 2px;
}

.dd-item {
  padding: 8px 12px;
  font-size: 12px;
  color: var(--text);
  cursor: pointer;
  transition: background 0.1s;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.dd-item:hover {
  background: var(--bg-hover);
}

.btn-send {
  width: 100%;
  padding: 10px;
  min-height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 10px;
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
</style>
