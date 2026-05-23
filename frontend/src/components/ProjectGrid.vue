<template>
  <div class="right-panel">
    <div v-if="projects.length === 0" class="empty-state">
      <div class="icon">⬡</div>
      <div>暂无项目</div>
    </div>
    <div v-else class="project-grid">
      <ProjectCard v-for="p in projects" :key="p.project_id"
        :project="p"
        :selected="selectedProjectId === p.project_id"
        @select="$emit('select', p)"
        @context="$emit('context', p)"
        @open-reply="$emit('open-reply', p)" />
    </div>
  </div>
</template>

<script setup>
import ProjectCard from './ProjectCard.vue'

defineProps({
  projects: { type: Array, required: true },
  selectedProjectId: { type: String, default: '' },
})

defineEmits(['select', 'context', 'open-reply'])
</script>

<style scoped>
.right-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.project-grid {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
  gap: 10px;
  align-content: start;
}
.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: var(--text-dim);
  font-size: 13px;
  gap: 12px;
}
.empty-state .icon { font-size: 48px; opacity: 0.3; }
</style>
