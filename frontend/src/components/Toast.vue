<template>
  <div v-if="visible" :class="['toast', type]">
    <span>{{ msg }}</span>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  msg: { type: String, default: '' },
  type: { type: String, default: 'error' },
  visible: { type: Boolean, default: false },
})

const styleVars = computed(() => ({
  '--error': '#ef4444',
}))
</script>

<style scoped>
.toast {
  position: fixed;
  top: 12px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 300;
  padding: 10px 24px;
  border-radius: 10px;
  font-size: 13px;
  font-weight: 500;
  color: white;
  background: v-bind('props.type === "error" ? "#ef4444" : "#ef4444"');
  border: 1px solid var(--border);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4);
  animation: toastIn 0.2s ease-out;
}
@keyframes toastIn {
  from { opacity: 0; transform: translateX(-50%) translateY(-8px); }
  to { opacity: 1; transform: translateX(-50%) translateY(0); }
}
</style>
