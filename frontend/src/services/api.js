async function request(path, options = {}) {
  const headers = { ...options.headers }
  if (!(options.body instanceof FormData)) headers['Content-Type'] = 'application/json'
  const response = await fetch(`/api${path}`, {
    headers,
    credentials: 'include',
    ...options,
  })
  const text = await response.text()
  const body = text ? JSON.parse(text) : null
  if (!response.ok) throw new Error(body?.detail || `Request failed (${response.status})`)
  return body
}

const repositoryPath = name => `/repositories/${encodeURIComponent(name)}`

export const api = request
export const register = data => request('/auth/register', { method: 'POST', body: JSON.stringify(data) })
export const login = data => request('/auth/login', { method: 'POST', body: JSON.stringify(data) })
export const logout = () => request('/auth/logout', { method: 'POST' })
export const getCurrentUser = () => request('/auth/me')
export const getDashboard = () => request('/dashboard')
export const getRepositories = () => request('/repositories')
export const createRepository = data => request('/repositories', { method: 'POST', body: JSON.stringify(data) })
export const importRepository = ({ name, description, files }) => {
  const form = new FormData()
  form.append('name', name)
  form.append('description', description || '')
  files.forEach(file => form.append('files', file, file.webkitRelativePath || file.name))
  return request('/repositories/import', { method: 'POST', body: form })
}
export const deleteRepository = name => request(repositoryPath(name), { method: 'DELETE' })
export const getRepository = name => request(repositoryPath(name))
export const getStatus = name => request(`${repositoryPath(name)}/status`)
export const getFiles = (name, path = '') => request(`${repositoryPath(name)}/files?${new URLSearchParams({ path })}`)
export const addFile = (name, paths = ['.']) => request(`${repositoryPath(name)}/add`, { method: 'POST', body: JSON.stringify({ paths }) })
export const getDiff = name => request(`${repositoryPath(name)}/diff`)
export const getStagedDiff = name => request(`${repositoryPath(name)}/diff?staged=true`)
export const commit = (name, message, author) => request(`${repositoryPath(name)}/commit`, { method: 'POST', body: JSON.stringify({ message, author }) })
export const getCommits = name => request(`${repositoryPath(name)}/commits`)
export const getCommit = (name, id) => request(`${repositoryPath(name)}/commits/${encodeURIComponent(id)}`)
export const getRemote = name => request(`${repositoryPath(name)}/remote`)
export const addRemote = (name, remoteName, location) => request(`${repositoryPath(name)}/remote`, { method: 'POST', body: JSON.stringify({ name: remoteName, location }) })
export const push = (name, remote = 'origin') => request(`${repositoryPath(name)}/push?remote=${encodeURIComponent(remote)}`, { method: 'POST' })
export const pull = (name, remote = 'origin') => request(`${repositoryPath(name)}/pull?remote=${encodeURIComponent(remote)}`, { method: 'POST' })
