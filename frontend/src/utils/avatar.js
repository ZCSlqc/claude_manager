export function avatarUrl(id, type = 'session') {
  const num = String(id || 1).padStart(3, '0')
  return `/src/assets/avatars/${type}/avatar_${num}.png`
}
