<template>
  <div v-if="visible" class="confirm-overlay" @click.self="$emit('cancel')">
    <div class="confirm-dialog">
      <p class="confirm-message">{{ message }}</p>
      <div class="confirm-actions">
        <button class="btn btn-delete" @click="$emit('confirm')">{{ label }}</button>
        <button class="btn btn-default" @click="$emit('cancel')">{{ cancelLabel }}</button>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  message: { type: String, default: '' },
  label: { type: String, default: '确定' },
  cancelLabel: { type: String, default: '取消' },
  visible: { type: Boolean, default: false },
})

defineEmits(['confirm', 'cancel'])
</script>

<style scoped>
.confirm-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 200;
  backdrop-filter: blur(4px);
}
.confirm-dialog {
  background: var(--bg2);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 24px;
  min-width: 300px;
  box-shadow: 0 0 40px var(--purple-glow);
}
.confirm-message {
  color: var(--text);
  font-size: 14px;
  margin-bottom: 20px;
}
.confirm-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 6px 16px;
  font-size: 13px;
  font-weight: 500;
  font-family: var(--font);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.15s;
  border: none;
  letter-spacing: 0.2px;
}
.btn:disabled { opacity: 0.35; cursor: not-allowed; }
.btn-default {
  background: var(--bg-card);
  border: 1px solid var(--border);
  color: var(--text);
}
.btn-default:hover:not(:disabled) {
  background: var(--bg-hover);
  border-color: var(--purple);
}
.btn-delete {
  background: #7f1d1d;
  color: white;
}
.btn-delete:hover:not(:disabled) {
  background: #991b1b;
}
</style>
