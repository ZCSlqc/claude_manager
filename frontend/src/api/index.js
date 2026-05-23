const API = ''

export async function getHealth() {
  return (await fetch(`${API}/health`)).json()
}

export async function getUsers() {
  return (await fetch(`${API}/users`)).json()
}

export async function getProjects(user_id) {
  const url = user_id ? `${API}/projects?user_id=${user_id}` : `${API}/projects`
  return (await fetch(url)).json()
}

export async function getProject(id) {
  return (await fetch(`${API}/projects/${id}`)).json()
}

export async function sendChat(user, dir, message) {
  const r = await fetch(`${API}/api/claude`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user, dir, message }),
  })
  if (!r.ok) {
    const body = await r.json().catch(() => ({}))
    throw { status: r.status, ...body }
  }
  return r.json()
}

export async function retryProject(id) {
  return (await fetch(`${API}/api/retry/${id}`)).json()
}

export async function updateProject(id, fields) {
  return (await fetch(`${API}/projects/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(fields),
  })).json()
}

export async function deleteProject(id) {
  return (await fetch(`${API}/projects/${id}`, { method: 'DELETE' })).json()
}

export async function getClaudeLog(projectId) {
  return (await fetch(`${API}/api/claude-log/${projectId}`)).json()
}

export async function deleteUser(userId) {
  return (await fetch(`${API}/users/${userId}`, { method: 'DELETE' })).json()
}
