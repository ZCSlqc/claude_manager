import { ref, computed } from 'vue'
import * as api from '../api/index.js'

export function useProjects() {
  const projects = ref([])

  const sortedProjects = computed(() => {
    return [...projects.value].sort((a, b) => (b.updated_at || 0) - (a.updated_at || 0))
  })

  async function fetchAll() {
    try {
      projects.value = await api.getProjects()
    } catch (e) {
      console.error('fetchProjects error:', e)
    }
  }

  // 合并 loading 状态: 后端数据覆盖，但保留 _loading 标记
  async function refreshKeepLoading() {
    try {
      const data = await api.getProjects()
      const merged = data.map(b => {
        const front = projects.value.find(f => f.project_id === b.project_id)
        if (front && front._loading) {
          return { ...b, _loading: true, session_avatar_id: front.session_avatar_id || b.session_avatar_id }
        }
        return b
      })
      projects.value = merged
    } catch (e) {
      console.error('refreshKeepLoading error:', e)
    }
  }

  function setProjectLoading(folderName) {
    const project = projects.value.find(p => p.folder_name === folderName)
    if (project) {
      project._loading = true
      project.is_finished = 0
      project.status = 0
      project.user_input = ''
      project.claude_result = null
      project.updated_at = Date.now()
    }
  }

  function clearLoading(folderName) {
    const project = projects.value.find(p => p.folder_name === folderName)
    if (project) {
      project._loading = false
    }
  }

  return {
    projects,
    sortedProjects,
    fetchAll,
    refreshKeepLoading,
    setProjectLoading,
    clearLoading,
  }
}
