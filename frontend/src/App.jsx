import { useEffect, useState } from 'react'
import {
  Bell, BookOpen, Check, ChevronDown, CircleDot, Code2, FileCode2,
  Folder, GitBranch, GitCommitHorizontal, GitPullRequest, LayoutDashboard,
  Menu, Plus, RefreshCw, Search, Settings2, Sparkles, Star, X, Zap, LogOut
} from 'lucide-react'
import {
  addFile, commit, createRepository, deleteRepository, getCommit,
  getCommits, getCurrentUser, getDashboard, getDiff, getFiles,
  getRepositories, getRepository, getStagedDiff, importRepository,
  login, logout, register
} from './services/api'
import './App.css'

function Button({ children, primary = false, onClick, disabled = false }) {
  return <button className={`button ${primary ? 'button-primary' : ''}`} disabled={disabled} onClick={onClick}>{children}</button>
}

function formatTime(value) {
  return value ? new Date(value).toLocaleString() : 'No commits yet'
}

function AuthScreen({ mode, setMode, onAuthenticated, initialError = '' }) {
  const [form, setForm] = useState({ username: '', name: '', email: '', password: '', confirm_password: '' })
  const [error, setError] = useState(initialError)
  const [busy, setBusy] = useState(false)

  const update = event => setForm({ ...form, [event.target.name]: event.target.value })

  const submit = async event => {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      const result = mode === 'login'
        ? await login({ identifier: form.username, password: form.password })
        : await register(form)
      onAuthenticated(result.user)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="auth-page">
      <section className="auth-panel">
        <div className="brand-mark auth-mark"><span /><span /></div>
        <h1>AIVCSHub</h1>
        <p>{mode === 'login' ? 'Sign in to your repositories.' : 'Create your personal AIVCS workspace.'}</p>
        <form onSubmit={submit}>
          {mode === 'register' && <>
            <label>Username<input name="username" value={form.username} onChange={update} required minLength="3" /></label>
            <label>Name<input name="name" value={form.name} onChange={update} required /></label>
            <label>Email<input name="email" type="email" value={form.email} onChange={update} required /></label>
          </>}
          {mode === 'login' && <label>Username or email<input name="username" value={form.username} onChange={update} required /></label>}
          <label>Password<input name="password" type="password" value={form.password} onChange={update} required minLength="8" /></label>
          {mode === 'register' && <label>Confirm password<input name="confirm_password" type="password" value={form.confirm_password} onChange={update} required minLength="8" /></label>}
          {error && <div className="api-notice">{error}</div>}
          <Button primary disabled={busy}>{busy ? 'Please wait...' : mode === 'login' ? 'Login' : 'Create account'}</Button>
        </form>
        <button className="text-button" onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError('') }}>
          {mode === 'login' ? 'Create an account' : 'Already have an account? Login'}
        </button>
      </section>
    </main>
  )
}

function CreateRepository({ onClose, onCreated }) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [files, setFiles] = useState([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const submit = async () => {
    setBusy(true)
    setError('')
    try {
      const repository = files.length
        ? await importRepository({ name, description, files })
        : await createRepository({ name, description })
      onCreated(repository)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="modal-backdrop">
      <section className="modal">
        <button className="modal-close" onClick={onClose}><X size={17} /></button>
        <div className="modal-icon"><Sparkles size={19} /></div>
        <h2>Create a new repository</h2>
        <p>A home for your code, ideas, and AIVCS history.</p>
        <div className="modal-body">
          <label>Repository name<input value={name} onChange={e => setName(e.target.value)} placeholder="my-project" /></label>
          <label>Description <span className="optional">(optional)</span><input value={description} onChange={e => setDescription(e.target.value)} placeholder="What is this repository about?" /></label>
          <label>Project folder
            <input type="file" webkitdirectory="true" directory="true" multiple onChange={e => setFiles(Array.from(e.target.files || []))} />
            <small>{files.length ? `${files.length} files selected` : 'Optional complete folder import'}</small>
          </label>
          {error && <div className="api-notice">{error}</div>}
          <Button primary disabled={!name.trim() || busy} onClick={submit}>
            {busy ? 'Creating...' : files.length ? 'Import project' : 'Create repository'}
          </Button>
        </div>
      </section>
    </div>
  )
}

function Metric({ icon: Icon, tone = 'purple', label, value, note = '' }) {
  return (
    <div className="metric">
      {Icon && <span className={`metric-icon ${tone}`}><Icon size={17} /></span>}
      <small>{label}</small>
      <strong>{value}</strong>
      {note && <em>{note}</em>}
    </div>
  )
}

function Dashboard({ user, dashboard, repositories, onOpen, onNew, onDelete, onRefresh }) {
  return <>
    <div className="page-header">
      <div>
        <div className="eyebrow">AIVCSHub</div>
        <h1>Good morning, {user.name || user.username}</h1>
        <p>Here's what's happening across your workspace.</p>
      </div>
      <Button primary onClick={onNew}><Plus size={16} />New repository</Button>
    </div>

    <section className="metrics">
      <Metric icon={GitCommitHorizontal} tone="purple" label="Commits" value={dashboard?.commits ?? 0} />
      <Metric icon={Code2} tone="blue" label="Repositories" value={dashboard?.repositories ?? 0} />
      <Metric icon={Folder} tone="amber" label="Tracked files" value={dashboard?.tracked_files ?? 0} />
    </section>

    <div className="content-grid">
      <section className="panel repo-panel">
        <div className="panel-heading">
          <div><h2>Your repositories</h2><p>Active projects in your workspace</p></div>
          <div>
            <Button onClick={onRefresh}><RefreshCw size={14} />Refresh</Button>
          </div>
        </div>
        {repositories.length ? (
          <div className="repo-cards">
            {repositories.map(repository => (
              <div className="repo-card" key={repository.name}>
                <button className="repo-card-link" onClick={() => onOpen(repository.name)}>
                  <div className="repo-card-top">
                    <span className="repo-dot blue" />
                    <strong>{repository.name}</strong>
                    <span className="private-badge">{repository.clean ? 'Clean' : 'Changed'}</span>
                  </div>
                  <p>{repository.description || 'No description'}</p>
                  <div className="repo-card-meta">
                    <span><GitBranch size={13} />{repository.branch}</span>
                    <span><GitCommitHorizontal size={13} />{repository.stats.commits}</span>
                    <span>{repository.stats.files} files</span>
                  </div>
                  <small>{repository.latest_commit ? repository.latest_commit.message : 'No commits yet'}</small>
                </button>
                <button className="more-button" onClick={() => onDelete(repository.name)}>Delete</button>
              </div>
            ))}
          </div>
        ) : (
          <p className="empty-state">No repositories yet. Create or import your first repository.</p>
        )}
      </section>

      <ActivityPanel repositories={repositories} />
    </div>

    <ActivityChart repositories={repositories} />
  </>
}

function ActivityPanel({ repositories }) {
  const recent = repositories
    .filter(repo => repo.latest_commit)
    .slice(0, 4)

  return (
    <section className="panel activity-panel">
      <div className="panel-heading">
        <div><h2>Recent activity</h2><p>Latest updates from your workspace</p></div>
      </div>
      <div className="activity-list">
        {recent.length ? recent.map(repo => (
          <div className="activity-item" key={repo.name}>
            <span className="activity-icon purple"><GitCommitHorizontal size={15} /></span>
            <div>
              <p>Latest commit in <strong>{repo.name}</strong></p>
              <small>{repo.latest_commit.message}</small>
            </div>
          </div>
        )) : (
          <div className="activity-item">
            <span className="activity-icon blue"><Code2 size={15} /></span>
            <div><p>No commits yet</p><small>Create your first commit to see activity here.</small></div>
          </div>
        )}
      </div>
    </section>
  )
}

function ActivityChart() {
  return (
    <section className="panel activity-chart">
      <div className="panel-heading">
        <div><h2>Contribution activity</h2><p>Activity from your AIVCS workspace</p></div>
      </div>
      <div className="chart">
        <div className="chart-y"><span>40</span><span>30</span><span>20</span><span>10</span><span>0</span></div>
        <div className="chart-area">
          <div className="grid-lines" />
          <svg viewBox="0 0 800 155" preserveAspectRatio="none">
            <path d="M0 135 C40 132 55 110 90 118 S145 98 178 108 S220 77 260 88 S310 80 342 100 S388 55 428 76 S475 65 512 82 S560 45 600 65 S650 60 688 72 S740 25 800 40" fill="none" stroke="#8b78f6" strokeWidth="2.5" />
            <path d="M0 135 C40 132 55 110 90 118 S145 98 178 108 S220 77 260 88 S310 80 342 100 S388 55 428 76 S475 65 512 82 S560 45 600 65 S650 60 688 72 S740 25 800 40 V155 H0Z" fill="url(#fade)" opacity=".35" />
            <defs><linearGradient id="fade" x1="0" x2="0" y1="0" y2="1"><stop stopColor="#8173e8" /><stop offset="1" stopColor="#8173e8" stopOpacity="0" /></linearGradient></defs>
          </svg>
          <div className="chart-months"><span>Oct</span><span>Dec</span><span>Feb</span><span>Apr</span><span>Jun</span><span>Aug</span><span>Sep</span></div>
        </div>
      </div>
    </section>
  )
}

function RepositoryPage({ repository, onRefresh, onDelete }) {
  const [tab, setTab] = useState('overview')
  const [path, setPath] = useState('')
  const [browser, setBrowser] = useState(null)
  const [content, setContent] = useState('')
  const [diff, setDiff] = useState('')
  const [message, setMessage] = useState('')
  const [commits, setCommits] = useState([])
  const [selectedCommit, setSelectedCommit] = useState(null)
  const [error, setError] = useState('')
  const name = repository.name

  const refreshFiles = async nextPath => {
    setPath(nextPath)
    setContent('')
    setBrowser(await getFiles(name, nextPath))
  }

  useEffect(() => {
    if (tab === 'files') refreshFiles('')
  }, [name, tab])

  const run = async action => {
    setError('')
    try {
      await action()
      await onRefresh()
    } catch (err) {
      setError(err.message)
    }
  }

  const open = async entry => {
    if (entry.directory) return refreshFiles(entry.path)
    const file = await getFiles(name, entry.path)
    setPath(entry.path)
    setContent(file.content)
  }

  const showDiff = async staged => {
    try {
      const result = staged ? await getStagedDiff(name) : await getDiff(name)
      setDiff(result.diff)
      setTab('changes')
    } catch (err) {
      setError(err.message)
    }
  }

  const loadCommits = async () => {
    try {
      setCommits(await getCommits(name))
      setTab('commits')
    } catch (err) {
      setError(err.message)
    }
  }

  const doCommit = () => run(async () => {
    await commit(name, message)
    setMessage('')
    setCommits(await getCommits(name))
    setTab('commits')
  })

  return <>
    <div className="repo-header">
      <div className="repo-title-line">
        <span className="repo-dot blue" />
        <h1>{name}</h1>
        <span className="visibility">{repository.clean ? 'Clean' : 'Changed'}</span>
      </div>
      <p>{repository.description || repository.path}</p>
      <div className="repo-stats">
        <Button onClick={onRefresh}><RefreshCw size={14} />Refresh</Button>
        <Button onClick={onDelete}>Delete</Button>
      </div>
    </div>

    <div className="tabs">
      <button className={tab === 'overview' ? 'selected' : ''} onClick={() => setTab('overview')}><LayoutDashboard size={16} />Overview</button>
      <button className={tab === 'files' ? 'selected' : ''} onClick={() => setTab('files')}><Code2 size={16} />Files</button>
      <button className={tab === 'changes' ? 'selected' : ''} onClick={() => showDiff(false)}><GitCommitHorizontal size={16} />Changes <span>{repository.stats.changes}</span></button>
      <button className={tab === 'commits' ? 'selected' : ''} onClick={loadCommits}><GitCommitHorizontal size={16} />Commits <span>{repository.stats.commits}</span></button>
    </div>

    {error && <div className="api-notice">{error}</div>}

    {tab === 'overview' && (
      <>
        <div className="repo-toolbar">
          <span className="select-button"><GitBranch size={15} />{repository.branch}</span>
          <div>
            <Button onClick={() => run(() => addFile(name, ['.']))}><Plus size={15} />Stage all</Button>
            <Button onClick={() => showDiff(false)}>Working diff</Button>
            <Button onClick={() => showDiff(true)}>Staged diff</Button>
          </div>
        </div>

        <section className="panel settings-content">
          <div className="setting-section">
            <h2>Working tree</h2>
            <p>
              Staged: {repository.status.staged.length} ·
              Modified: {repository.status.modified.length} ·
              Deleted: {repository.status.deleted.length} ·
              Untracked: {repository.status.untracked.length}
            </p>
          </div>

          <label>
            Commit message
            <input value={message} onChange={event => setMessage(event.target.value)} placeholder="feat: describe your changes" />
          </label>

          <Button primary disabled={!repository.status.staged.length || !message.trim()} onClick={doCommit}>
            <GitCommitHorizontal size={15} />Commit
          </Button>
        </section>
      </>
    )}

    {tab === 'files' && (
      <section className="panel file-explorer">
        <div className="file-breadcrumb">
          <Folder size={15} /> {path || 'root'}
          {path && <Button onClick={() => refreshFiles('')}>Root</Button>}
        </div>
        {content ? (
          <pre className="file-content">{content}</pre>
        ) : browser?.entries?.map(entry => {
          const Icon = entry.directory ? Folder : FileCode2
          return (
            <div className="file-row" key={entry.path} role="button" tabIndex="0" onClick={() => open(entry)}>
              <Icon size={16} className={entry.directory ? 'folder-icon' : 'file-icon'} />
              <strong>{entry.name}</strong>
              <span>{entry.directory ? 'folder' : 'file'}</span>
              {!entry.directory && <Button onClick={event => { event.stopPropagation(); run(() => addFile(name, [entry.path])) }}>Stage</Button>}
            </div>
          )
        })}
      </section>
    )}

    {tab === 'changes' && (
      <section className="panel settings-content">
        <div className="setting-section">
          <h2>Diff</h2>
          <p>Working-tree changes</p>
        </div>
        <div>
          <Button onClick={() => showDiff(false)}>Working</Button>{' '}
          <Button onClick={() => showDiff(true)}>Staged</Button>
        </div>
        <pre className="diff-viewer">{diff || 'No changes.'}</pre>
      </section>
    )}

    {tab === 'commits' && (
      <section className="panel rows-panel">
        {commits.length ? commits.map(item => (
          <button className="list-row" key={item.id} onClick={async () => {
            try {
              setSelectedCommit(await getCommit(name, item.id))
            } catch (err) {
              setError(err.message)
            }
          }}>
            <span className="status-dot green"><GitCommitHorizontal size={17} /></span>
            <div>
              <strong>{item.id.slice(0, 7)} · {item.message}</strong>
              <p>{formatTime(item.timestamp)} · {item.author}</p>
            </div>
          </button>
        )) : <p className="empty-state">No commits yet.</p>}

        {selectedCommit && (
  <div className="settings-content">
    <div className="setting-section">
      <h2>{selectedCommit.message}</h2>
      <p>{selectedCommit.id}</p>
    </div>
    <pre className="diff-viewer">{selectedCommit.diff || 'No diff.'}</pre>
  </div>
)}
      </section>
    )}
  </>
}

function App() {
  const [view, setView] = useState('overview')
  const [mobileOpen, setMobileOpen] = useState(false)
  const [user, setUser] = useState(null)
  const [repositories, setRepositories] = useState([])
  const [dashboard, setDashboard] = useState(null)
  const [selected, setSelected] = useState(null)
  const [modal, setModal] = useState(false)
  const [authMode, setAuthMode] = useState('login')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  const refresh = async (name = selected?.name) => {
    try {
      const [items, stats] = await Promise.all([getRepositories(), getDashboard()])
      setRepositories(items)
      setDashboard(stats)
      if (name) setSelected(await getRepository(name))
      else setSelected(null)
      setError('')
    } catch (err) {
      if (err.message.includes('Authentication required') || err.message.includes('Invalid')) {
        setUser(null)
      } else {
        setError(err.message)
      }
    }
  }

  useEffect(() => {
    getCurrentUser()
      .then(current => {
        setUser(current)
        return refresh()
      })
      .catch(err => {
        if (!err.message.includes('Authentication required') && !err.message.includes('Invalid')) setError(err.message)
      })
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <main className="auth-page"><p>Loading...</p></main>

  if (!user) {
    return <AuthScreen
      mode={authMode}
      setMode={setAuthMode}
      onAuthenticated={current => {
        setUser(current)
        setError('')
        refresh()
      }}
      initialError={error}
    />
  }

  const openRepository = async name => {
    try {
      setSelected(await getRepository(name))
      setView('repository')
      setMobileOpen(false)
    } catch (err) {
      setError(err.message)
    }
  }

  const removeRepository = async name => {
    if (!confirm(`Delete ${name}? This will remove the repository files and AIVCS data.`)) return
    try {
      await deleteRepository(name)
      setSelected(null)
      setView('overview')
      await refresh()
    } catch (err) {
      setError(err.message)
    }
  }

  const navItems = [
    ['overview', 'Overview', LayoutDashboard],
    ['repository', 'Repositories', Code2],
    ['ai-history', 'AI History', Sparkles],
    ['issues', 'Issues', CircleDot],
    ['pulls', 'Pull requests', GitPullRequest]
  ]

  return (
    <div className="app-shell">
      <header className="topbar">
        <button className="mobile-menu" onClick={() => setMobileOpen(!mobileOpen)}><Menu size={19} /></button>
        <button className="brand" onClick={() => { setSelected(null); setView('overview') }}>
          <span className="brand-mark"><span /><span /></span><span>AIVCS</span>
        </button>
        <div className="top-search"><Search size={16} /><span>Search repositories, users, commits...</span><kbd>⌘ K</kbd></div>
        <div className="top-actions">
          <button className="icon-button"><Bell size={17} /></button>
          <button className="avatar" onClick={() => setView('profile')}>{(user.name || user.username).slice(0, 2).toUpperCase()}</button>
          <button className="icon-button" title="Logout" onClick={async () => { await logout(); setUser(null); setSelected(null) }}><LogOut size={17} /></button>
        </div>
      </header>

      <div className="workspace">
        <aside className={`sidebar ${mobileOpen ? 'sidebar-open' : ''}`}>
          <div className="workspace-switcher">
            <div className="workspace-avatar">{(user.name || user.username).slice(0, 1).toUpperCase()}</div>
            <div><strong>{user.name || user.username}</strong><small>Personal workspace</small></div>
            <ChevronDown size={15} />
          </div>

          <div className="sidebar-label">Workspace</div>
          <nav>
            {navItems.map(([id, label, Icon]) => (
              <button key={id} className={view === id ? 'active' : ''} onClick={() => { setView(id); setMobileOpen(false) }}>
                <Icon size={17} /><span>{label}</span>
              </button>
            ))}
          </nav>

          <div className="sidebar-label repo-label">
            Your repositories
            <button onClick={() => setModal(true)}><Plus size={15} /></button>
          </div>

          <div className="mini-repos">
            {repositories.slice(0, 5).map(repo => (
              <button key={repo.name} onClick={() => openRepository(repo.name)}>
                <span className="repo-dot blue" />{repo.name}
              </button>
            ))}
            {!repositories.length && <small style={{ color: 'var(--faint)', padding: '9px' }}>No repositories</small>}
          </div>

          <div className="sidebar-bottom">
            <button onClick={() => setView('settings')}><Settings2 size={17} />Settings</button>
            <div className="ai-status">
              <span><Zap size={14} /></span>
              <div><strong>AI Copilot</strong><small>Ready to assist</small></div>
              <i />
            </div>
          </div>
        </aside>

        <main className="main-content">
          {error && <div className="api-notice">{error}</div>}

          {view === 'overview' && !selected && (
            <Dashboard
              user={user}
              dashboard={dashboard}
              repositories={repositories}
              onOpen={openRepository}
              onNew={() => setModal(true)}
              onDelete={removeRepository}
              onRefresh={() => refresh()}
            />
          )}

          {view === 'repository' && !selected && (
            <Dashboard
              user={user}
              dashboard={dashboard}
              repositories={repositories}
              onOpen={openRepository}
              onNew={() => setModal(true)}
              onDelete={removeRepository}
              onRefresh={() => refresh()}
            />
          )}

          {selected && (
            <RepositoryPage
              repository={selected}
              onRefresh={() => refresh(selected.name)}
              onDelete={() => removeRepository(selected.name)}
            />
          )}

          {view === 'ai-history' && !selected && (
            <section className="panel settings-content">
              <div className="setting-section">
                <h2>AI History</h2>
                <p>AI-native history features will connect to AIVCS intelligence in a later phase.</p>
              </div>
            </section>
          )}

          {(view === 'issues' || view === 'pulls') && !selected && (
            <section className="panel settings-content">
              <div className="setting-section">
                <h2>{view === 'issues' ? 'Issues' : 'Pull requests'}</h2>
                <p>This section is part of the AIVCSHub interface and can be connected to the platform APIs later.</p>
              </div>
            </section>
          )}

          {view === 'profile' && !selected && (
            <section className="panel settings-content">
              <div className="setting-section">
                <h2>{user.name || user.username}</h2>
                <p>@{user.username} · {user.email}</p>
              </div>
            </section>
          )}

          {view === 'settings' && !selected && (
            <section className="settings-layout">
              <nav className="settings-nav">
                {['Account', 'Profile', 'Security', 'Appearance', 'AI Settings', 'Repositories'].map((item, i) => (
                  <button className={i === 4 ? 'selected' : ''} key={item}>{item}</button>
                ))}
              </nav>
              <section className="settings-content panel">
                <div className="setting-section">
                  <h2>AI Settings</h2>
                  <p>Customize how AIVCS intelligence works for you.</p>
                </div>
                <div className="setting-section">
                  <h2>Workspace</h2>
                  <p>{dashboard?.repositories ?? 0} repositories · {dashboard?.tracked_files ?? 0} tracked files · {dashboard?.commits ?? 0} commits</p>
                </div>
              </section>
            </section>
          )}
        </main>
      </div>

      {modal && (
        <CreateRepository
          onClose={() => setModal(false)}
          onCreated={async repository => {
  setModal(false)
  setSelected(repository)
  setView('repository')
  await refresh()
}}
        />
      )}
    </div>
  )
}

export default App
