export function avatarUrl(id, type = 'session') {
  const num = String(id || 1).padStart(3, '0')
  return `/avatar/${type}/${num}.png`
}
