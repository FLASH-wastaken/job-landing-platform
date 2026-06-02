import React, { useState, useEffect } from 'react'

const API = '/api'

const STATUS_LABELS = {
  saved: 'Saved',
  tailoring: 'Tailoring',
  applied: 'Applied',
  awaiting_response: 'Awaiting Response',
  follow_up_sent: 'Follow-up Sent',
  interview_scheduled: 'Interview',
  interview_completed: 'Interviewed',
  offer_received: 'Offer!',
  rejected: 'Rejected',
  withdrawn: 'Withdrawn',
}

const PIPELINE_COLUMNS = ['saved', 'applied', 'awaiting_response', 'follow_up_sent', 'interview_scheduled', 'offer_received']

function App() {
  const [dashboard, setDashboard] = useState(null)
  const [candidates, setCandidates] = useState([])
  const [selectedCandidate, setSelectedCandidate] = useState(null)
  const [applications, setApplications] = useState([])
  const [showAddCandidate, setShowAddCandidate] = useState(false)
  const [showAddApplication, setShowAddApplication] = useState(false)
  const [selectedApp, setSelectedApp] = useState(null)
  const [activeTab, setActiveTab] = useState('pipeline')
  const [jobSearchResults, setJobSearchResults] = useState([])
  const [jobSearching, setJobSearching] = useState(false)
  const [jobQuery, setJobQuery] = useState('')
  const [jobLocation, setJobLocation] = useState('')
  const [careerUrl, setCareerUrl] = useState('')
  const [scrapeResults, setScrapeResults] = useState([])
  const [scraping, setScraping] = useState(false)
  const [saveMessage, setSaveMessage] = useState('')
  // Agent state
  const [agentRunning, setAgentRunning] = useState(false)
  const [agentResult, setAgentResult] = useState(null)
  const [agentQueue, setAgentQueue] = useState([])
  const [agentConfig, setAgentConfig] = useState({
    min_match_score: 40,
    max_jobs_per_candidate: 10,
    search_limit: 20,
    auto_tailor: true,
    auto_cover_letter: true,
  })
  // Discovery quiz state
  const [quizStep, setQuizStep] = useState(0) // 0=intro, 1-4=questions, 5=results
  const [quizAnswers, setQuizAnswers] = useState({ interests: [], skills: [], workstyle: {}, values: [] })
  const [quizResults, setQuizResults] = useState(null)
  const [quizLoading, setQuizLoading] = useState(false)
  const [discoveryJobs, setDiscoveryJobs] = useState({})
  const [discoveryJobsLoading, setDiscoveryJobsLoading] = useState({})
  const [selectedRolesForApply, setSelectedRolesForApply] = useState([])
  const [autoApplyRunning, setAutoApplyRunning] = useState(false)
  const [autoApplyResult, setAutoApplyResult] = useState(null)

  useEffect(() => {
    fetchDashboard()
    fetchCandidates()
  }, [])

  useEffect(() => {
    if (selectedCandidate) {
      fetchApplications(selectedCandidate.id)
    } else {
      fetchApplications()
    }
  }, [selectedCandidate])

  async function fetchDashboard() {
    try {
      const res = await fetch(`${API}/dashboard`)
      if (res.ok) setDashboard(await res.json())
    } catch (e) { console.error(e) }
  }

  async function fetchCandidates() {
    try {
      const res = await fetch(`${API}/candidates`)
      if (res.ok) setCandidates(await res.json())
    } catch (e) { console.error(e) }
  }

  async function fetchApplications(candidateId) {
    try {
      const url = candidateId ? `${API}/applications?candidate_id=${candidateId}` : `${API}/applications`
      const res = await fetch(url)
      if (res.ok) setApplications(await res.json())
    } catch (e) { console.error(e) }
  }

  async function refreshSuggestions() {
    await fetch(`${API}/dashboard/refresh-suggestions`, { method: 'POST' })
    fetchDashboard()
  }

  async function addCandidate(data) {
    const res = await fetch(`${API}/candidates`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    })
    if (res.ok) {
      fetchCandidates()
      fetchDashboard()
      setShowAddCandidate(false)
    }
  }

  async function addApplication(data) {
    const res = await fetch(`${API}/applications`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    })
    if (res.ok) {
      fetchApplications(selectedCandidate?.id)
      fetchDashboard()
      setShowAddApplication(false)
    }
  }

  async function updateStatus(appId, status) {
    await fetch(`${API}/applications/${appId}/status`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status }),
    })
    fetchApplications(selectedCandidate?.id)
    fetchDashboard()
  }

  async function searchJobs(e) {
    e?.preventDefault()
    if (!jobQuery.trim()) return
    setJobSearching(true)
    setJobSearchResults([])
    try {
      const params = new URLSearchParams({ q: jobQuery.trim(), limit: '20' })
      if (jobLocation.trim()) params.set('location', jobLocation.trim())
      const res = await fetch(`${API}/jobs/search?${params}`)
      if (res.ok) {
        const data = await res.json()
        setJobSearchResults(data.jobs || [])
      }
    } catch (e) { console.error(e) }
    setJobSearching(false)
  }

  async function scrapeCareerPage(e) {
    e?.preventDefault()
    if (!careerUrl.trim()) return
    setScraping(true)
    setScrapeResults([])
    try {
      const res = await fetch(`${API}/jobs/scrape-careers`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: careerUrl.trim() }),
      })
      if (res.ok) {
        const data = await res.json()
        setScrapeResults(data.jobs || [])
      }
    } catch (e) { console.error(e) }
    setScraping(false)
  }

  async function saveJobToPipeline(job, candidateId) {
    try {
      const res = await fetch(`${API}/jobs/save`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          candidate_id: candidateId,
          title: job.title,
          company: job.company,
          url: job.url,
          description: job.description,
          location: typeof job.location === 'object' ? job.location.join(', ') : (job.location || ''),
          salary: job.salary || '',
        }),
      })
      const data = await res.json()
      if (res.ok) {
        setSaveMessage(`Saved! Match: ${data.match_score ? data.match_score + '%' : 'N/A'}`)
        fetchApplications(selectedCandidate?.id)
        fetchDashboard()
        setTimeout(() => setSaveMessage(''), 3000)
      } else {
        setSaveMessage(data.detail || 'Error saving')
        setTimeout(() => setSaveMessage(''), 3000)
      }
    } catch (e) {
      setSaveMessage('Error saving job')
      setTimeout(() => setSaveMessage(''), 3000)
    }
  }

  async function dismissSuggestion(id) {
    await fetch(`${API}/applications/suggestions/${id}/dismiss`, { method: 'PUT' })
    fetchDashboard()
  }

  async function completeSuggestion(id) {
    await fetch(`${API}/applications/suggestions/${id}/complete`, { method: 'PUT' })
    fetchDashboard()
  }

  // Agent functions
  async function runAgent() {
    setAgentRunning(true)
    setAgentResult(null)
    try {
      const body = { ...agentConfig }
      if (selectedCandidate) {
        body.candidate_ids = [selectedCandidate.id]
      }
      const res = await fetch(`${API}/agent/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      const data = await res.json()
      setAgentResult(data)
      fetchAgentQueue()
      fetchApplications(selectedCandidate?.id)
      fetchDashboard()
    } catch (e) {
      setAgentResult({ status: 'error', error: e.message })
    }
    setAgentRunning(false)
  }

  async function fetchAgentQueue() {
    try {
      const res = await fetch(`${API}/agent/queue`)
      if (res.ok) {
        const data = await res.json()
        setAgentQueue(data.applications || [])
      }
    } catch (e) { console.error(e) }
  }

  async function approveJob(appId) {
    await fetch(`${API}/agent/approve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ application_id: appId, action: 'approve' }),
    })
    fetchAgentQueue()
    fetchApplications(selectedCandidate?.id)
    fetchDashboard()
  }

  async function rejectJob(appId) {
    await fetch(`${API}/agent/approve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ application_id: appId, action: 'reject' }),
    })
    fetchAgentQueue()
    fetchApplications(selectedCandidate?.id)
    fetchDashboard()
  }

  // Discovery quiz functions
  async function submitQuiz() {
    setQuizLoading(true)
    try {
      const res = await fetch(`${API}/discovery/results`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(quizAnswers),
      })
      if (res.ok) {
        const data = await res.json()
        setQuizResults(data)
        setQuizStep(5)
        setSelectedRolesForApply([])
        setAutoApplyResult(null)
      }
    } catch (e) { console.error(e) }
    setQuizLoading(false)
  }

  async function searchRoleJobs(role) {
    setDiscoveryJobsLoading(prev => ({ ...prev, [role.role]: true }))
    try {
      const res = await fetch(`${API}/discovery/search-roles`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ search_terms: role.search_terms, location: '', limit: 5 }),
      })
      if (res.ok) {
        const data = await res.json()
        setDiscoveryJobs(prev => ({ ...prev, [role.role]: data.jobs }))
      }
    } catch (e) { console.error(e) }
    setDiscoveryJobsLoading(prev => ({ ...prev, [role.role]: false }))
  }

  function toggleRoleForApply(roleName) {
    setSelectedRolesForApply(prev =>
      prev.includes(roleName) ? prev.filter(r => r !== roleName) : [...prev, roleName]
    )
  }

  async function runDiscoveryAutoApply() {
    if (!selectedCandidate || selectedRolesForApply.length === 0) return
    setAutoApplyRunning(true)
    setAutoApplyResult(null)
    try {
      const res = await fetch(`${API}/discovery/auto-apply`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          candidate_id: selectedCandidate.id,
          roles: selectedRolesForApply,
          max_per_role: 5,
        }),
      })
      if (res.ok) {
        const data = await res.json()
        setAutoApplyResult(data)
        fetchApplications(selectedCandidate?.id)
        fetchDashboard()
      }
    } catch (e) {
      setAutoApplyResult({ status: 'error', error: e.message })
    }
    setAutoApplyRunning(false)
  }

  function resetQuiz() {
    setQuizStep(0)
    setQuizAnswers({ interests: [], skills: [], workstyle: {}, values: [] })
    setQuizResults(null)
    setDiscoveryJobs({})
    setSelectedRolesForApply([])
    setAutoApplyResult(null)
  }

  const pipelineApps = PIPELINE_COLUMNS.reduce((acc, status) => {
    acc[status] = applications.filter(a => a.status === status)
    return acc
  }, {})

  return (
    <div className="app">
      <header className="header">
        <h1>Job Landing Platform</h1>
        <div className="header-actions">
          <button className="btn btn-secondary" onClick={refreshSuggestions}>
            Refresh Suggestions
          </button>
          <button className="btn btn-primary" onClick={() => setShowAddCandidate(true)}>
            + Add Candidate
          </button>
        </div>
      </header>

      <div className="main-content">
        <aside className="sidebar">
          <h3>Candidates</h3>
          <div
            className={`candidate-item ${!selectedCandidate ? 'active' : ''}`}
            onClick={() => setSelectedCandidate(null)}
          >
            <div className="name">All Candidates</div>
            <div className="role">Overview</div>
          </div>
          <ul className="candidate-list">
            {candidates.map(c => (
              <li
                key={c.id}
                className={`candidate-item ${selectedCandidate?.id === c.id ? 'active' : ''}`}
                onClick={() => setSelectedCandidate(c)}
              >
                <div className="name">{c.name}</div>
                <div className="role">{c.target_role}</div>
                <div className="stats">
                  <span className="stat-badge active">{c.active_applications} active</span>
                  <span className="stat-badge">{c.total_applications} total</span>
                </div>
              </li>
            ))}
          </ul>
        </aside>

        <main className="content-area">
          {/* Metrics */}
          <div className="dashboard-grid">
            <div className="metric-card">
              <div className="label">Total Applications</div>
              <div className="value purple">{dashboard?.total_applications || 0}</div>
            </div>
            <div className="metric-card">
              <div className="label">Awaiting Response</div>
              <div className="value yellow">{dashboard?.pipeline?.awaiting_response || 0}</div>
            </div>
            <div className="metric-card">
              <div className="label">Interviews</div>
              <div className="value blue">{dashboard?.pipeline?.interview_scheduled || 0}</div>
            </div>
            <div className="metric-card">
              <div className="label">Actions Needed</div>
              <div className="value green">{dashboard?.top_suggestions?.length || 0}</div>
            </div>
          </div>

          {/* Tabs */}
          <div className="tab-nav">
            <button className={activeTab === 'pipeline' ? 'active' : ''} onClick={() => setActiveTab('pipeline')}>
              Pipeline
            </button>
            <button className={activeTab === 'jobsearch' ? 'active' : ''} onClick={() => setActiveTab('jobsearch')}>
              🔍 Job Search
            </button>
            <button className={activeTab === 'agent' ? 'active' : ''} onClick={() => { setActiveTab('agent'); fetchAgentQueue() }}>
              Auto-Apply Agent
            </button>
            <button className={activeTab === 'suggestions' ? 'active' : ''} onClick={() => setActiveTab('suggestions')}>
              Suggestions ({dashboard?.top_suggestions?.length || 0})
            </button>
            <button className={`discover-tab ${activeTab === 'discover' ? 'active' : ''}`} onClick={() => setActiveTab('discover')}>
              Discover Yourself
            </button>
          </div>

          {activeTab === 'pipeline' && (
            <div className="pipeline-section">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                <h2>{selectedCandidate ? `${selectedCandidate.name}'s Pipeline` : 'All Applications'}</h2>
                {selectedCandidate && (
                  <button className="btn btn-primary" onClick={() => setShowAddApplication(true)}>
                    + New Application
                  </button>
                )}
              </div>
              <div className="pipeline-board">
                {PIPELINE_COLUMNS.map(status => (
                  <div key={status} className="pipeline-column">
                    <div className="column-header">
                      <span className="column-title">{STATUS_LABELS[status]}</span>
                      <span className="column-count">{pipelineApps[status]?.length || 0}</span>
                    </div>
                    {pipelineApps[status]?.map(app => (
                      <div key={app.id} className="app-card" onClick={() => setSelectedApp(app)}>
                        <div className="company">{app.company_name}</div>
                        <div className="title">{app.job_title}</div>
                        {app.match_score && (
                          <div className="score">
                            Match: {app.match_score}%
                            <div className="score-bar">
                              <div
                                className={`score-fill ${app.match_score >= 70 ? 'high' : app.match_score >= 40 ? 'medium' : 'low'}`}
                                style={{ width: `${app.match_score}%` }}
                              />
                            </div>
                          </div>
                        )}
                        {app.suggestion_count > 0 && (
                          <div style={{ marginTop: '0.5rem', fontSize: '0.7rem', color: '#f59e0b' }}>
                            {app.suggestion_count} action{app.suggestion_count > 1 ? 's' : ''} needed
                          </div>
                        )}
                      </div>
                    ))}
                    {(!pipelineApps[status] || pipelineApps[status].length === 0) && (
                      <div style={{ fontSize: '0.75rem', color: '#52525b', textAlign: 'center', padding: '1rem' }}>
                        No applications
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {activeTab === 'jobsearch' && (
            <div className="job-search-section">
              <h2>Find Jobs</h2>

              {saveMessage && (
                <div className="save-toast">{saveMessage}</div>
              )}

              {/* Search Form */}
              <form onSubmit={searchJobs} className="search-form">
                <div className="search-row">
                  <input
                    className="search-input"
                    placeholder="Job title, skills, or keywords..."
                    value={jobQuery}
                    onChange={e => setJobQuery(e.target.value)}
                  />
                  <input
                    className="search-input location-input"
                    placeholder="Location (optional)"
                    value={jobLocation}
                    onChange={e => setJobLocation(e.target.value)}
                  />
                  <button type="submit" className="btn btn-primary" disabled={jobSearching}>
                    {jobSearching ? 'Searching...' : 'Search Jobs'}
                  </button>
                </div>
              </form>

              {/* Career Page Scraper */}
              <form onSubmit={scrapeCareerPage} className="search-form" style={{ marginTop: '0.75rem' }}>
                <div className="search-row">
                  <input
                    className="search-input"
                    placeholder="Paste company careers page URL to scrape..."
                    value={careerUrl}
                    onChange={e => setCareerUrl(e.target.value)}
                    style={{ flex: 2 }}
                  />
                  <button type="submit" className="btn btn-secondary" disabled={scraping}>
                    {scraping ? 'Scraping...' : 'Scrape Careers Page'}
                  </button>
                </div>
              </form>

              {/* Search Results */}
              {jobSearchResults.length > 0 && (
                <div className="search-results">
                  <h3 style={{ marginTop: '1.5rem', marginBottom: '1rem', color: '#e4e4e7' }}>
                    Found {jobSearchResults.length} jobs
                  </h3>
                  {jobSearchResults.map((job, i) => (
                    <JobCard key={`search-${i}`} job={job} candidates={candidates} onSave={saveJobToPipeline} />
                  ))}
                </div>
              )}

              {/* Scrape Results */}
              {scrapeResults.length > 0 && (
                <div className="search-results">
                  <h3 style={{ marginTop: '1.5rem', marginBottom: '1rem', color: '#e4e4e7' }}>
                    Found {scrapeResults.length} openings on career page
                  </h3>
                  {scrapeResults.map((job, i) => (
                    <JobCard key={`scrape-${i}`} job={job} candidates={candidates} onSave={saveJobToPipeline} />
                  ))}
                </div>
              )}

              {jobSearching && (
                <div className="empty-state">
                  <div className="spinner"></div>
                  <p>Searching across multiple job boards...</p>
                </div>
              )}

              {scraping && (
                <div className="empty-state">
                  <div className="spinner"></div>
                  <p>Scraping career page for openings...</p>
                </div>
              )}

              {!jobSearching && !scraping && jobSearchResults.length === 0 && scrapeResults.length === 0 && (
                <div className="empty-state" style={{ marginTop: '2rem' }}>
                  <p style={{ fontSize: '1.1rem', marginBottom: '0.5rem' }}>Search for jobs or paste a company careers URL</p>
                  <p style={{ color: '#71717a', fontSize: '0.85rem' }}>Results come from Remotive, Arbeitnow, Himalayas, and career page scraping</p>
                </div>
              )}
            </div>
          )}

          {activeTab === 'agent' && (
            <div className="agent-section">
              <div className="agent-header">
                <div>
                  <h2>Auto-Apply Agent</h2>
                  <p className="agent-subtitle">Discovers, scores, and queues jobs automatically for your candidates</p>
                </div>
                <button
                  className={`btn ${agentRunning ? 'btn-warning' : 'btn-primary'}`}
                  onClick={runAgent}
                  disabled={agentRunning}
                >
                  {agentRunning ? 'Agent Running...' : 'Run Agent Now'}
                </button>
              </div>

              {/* Agent Config */}
              <div className="agent-config">
                <h3>Configuration</h3>
                <div className="config-grid">
                  <div className="config-item">
                    <label>Min Match Score</label>
                    <input
                      type="number"
                      min="0"
                      max="100"
                      value={agentConfig.min_match_score}
                      onChange={e => setAgentConfig({ ...agentConfig, min_match_score: parseInt(e.target.value) || 0 })}
                    />
                  </div>
                  <div className="config-item">
                    <label>Max Jobs Per Candidate</label>
                    <input
                      type="number"
                      min="1"
                      max="50"
                      value={agentConfig.max_jobs_per_candidate}
                      onChange={e => setAgentConfig({ ...agentConfig, max_jobs_per_candidate: parseInt(e.target.value) || 5 })}
                    />
                  </div>
                  <div className="config-item">
                    <label>Search Limit</label>
                    <input
                      type="number"
                      min="5"
                      max="50"
                      value={agentConfig.search_limit}
                      onChange={e => setAgentConfig({ ...agentConfig, search_limit: parseInt(e.target.value) || 20 })}
                    />
                  </div>
                  <div className="config-item checkbox-item">
                    <label>
                      <input
                        type="checkbox"
                        checked={agentConfig.auto_tailor}
                        onChange={e => setAgentConfig({ ...agentConfig, auto_tailor: e.target.checked })}
                      />
                      Auto-tailor resumes
                    </label>
                  </div>
                  <div className="config-item checkbox-item">
                    <label>
                      <input
                        type="checkbox"
                        checked={agentConfig.auto_cover_letter}
                        onChange={e => setAgentConfig({ ...agentConfig, auto_cover_letter: e.target.checked })}
                      />
                      Auto-generate cover letters
                    </label>
                  </div>
                </div>
                {selectedCandidate && (
                  <p className="config-note">Running for: <strong>{selectedCandidate.name}</strong> (select "All Candidates" in sidebar to run for everyone)</p>
                )}
              </div>

              {/* Agent Running Indicator */}
              {agentRunning && (
                <div className="agent-running">
                  <div className="spinner"></div>
                  <p>Agent is searching job boards, scoring matches, and tailoring resumes...</p>
                </div>
              )}

              {/* Agent Results */}
              {agentResult && !agentRunning && (
                <div className={`agent-result ${agentResult.status === 'error' ? 'error' : ''}`}>
                  <h3>Last Run Results</h3>
                  {agentResult.status === 'error' ? (
                    <p className="error-text">Error: {agentResult.error}</p>
                  ) : (
                    <div className="result-stats">
                      <div className="result-stat">
                        <span className="result-number">{agentResult.total_discovered || 0}</span>
                        <span className="result-label">Jobs Discovered</span>
                      </div>
                      <div className="result-stat">
                        <span className="result-number">{agentResult.total_qualified || 0}</span>
                        <span className="result-label">Passed Score Filter</span>
                      </div>
                      <div className="result-stat">
                        <span className="result-number">{agentResult.total_queued || 0}</span>
                        <span className="result-label">Queued for Review</span>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Approval Queue */}
              <div className="agent-queue">
                <h3>Approval Queue ({agentQueue.length})</h3>
                {agentQueue.length === 0 ? (
                  <div className="empty-state">
                    <p>No jobs in queue. Run the agent to discover matching jobs.</p>
                  </div>
                ) : (
                  <div className="queue-list">
                    {agentQueue.map(item => (
                      <div key={item.id} className="queue-card">
                        <div className="queue-card-main">
                          <div className="queue-card-info">
                            <div className="queue-card-title">{item.title}</div>
                            <div className="queue-card-company">{item.company}</div>
                            <div className="queue-card-meta">
                              {item.candidate_name && <span className="job-tag">{item.candidate_name}</span>}
                              {item.location && <span className="job-tag">{item.location}</span>}
                              {item.salary && <span className="job-tag salary">{item.salary}</span>}
                            </div>
                          </div>
                          <div className="queue-card-score">
                            <div className="score-circle">
                              <span>{item.match_score || '?'}%</span>
                            </div>
                            <div className="queue-badges">
                              {item.has_tailored_resume && <span className="badge-ready">Resume</span>}
                              {item.has_cover_letter && <span className="badge-ready">Cover Letter</span>}
                            </div>
                          </div>
                        </div>
                        <div className="queue-card-actions">
                          <button className="btn btn-success btn-sm" onClick={() => approveJob(item.id)}>
                            Approve & Apply
                          </button>
                          <button className="btn btn-secondary btn-sm" onClick={() => rejectJob(item.id)}>
                            Reject
                          </button>
                          {item.url && (
                            <a href={item.url} target="_blank" rel="noopener noreferrer" className="btn btn-secondary btn-sm">
                              View Listing
                            </a>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Agent Log */}
              {agentResult?.log && agentResult.log.length > 0 && (
                <div className="agent-log">
                  <h3>Agent Log</h3>
                  <div className="log-entries">
                    {agentResult.log.map((entry, i) => (
                      <div key={i} className={`log-entry ${entry.level}`}>
                        <span className="log-time">{new Date(entry.time).toLocaleTimeString()}</span>
                        <span className="log-msg">{entry.message}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {activeTab === 'suggestions' && (
            <div className="suggestions-section">
              <h2>Action Items</h2>
              {dashboard?.top_suggestions?.length === 0 && (
                <div className="empty-state">
                  <p>No suggestions right now. Keep applying!</p>
                </div>
              )}
              {dashboard?.top_suggestions?.map(s => (
                <div key={s.id} className="suggestion-card">
                  <div className={`priority-dot ${s.priority >= 8 ? 'high' : s.priority >= 6 ? 'medium' : 'low'}`} />
                  <div className="suggestion-content">
                    <div className="suggestion-title">{s.title}</div>
                    <div className="suggestion-context">{s.candidate_name} &middot; {s.job_title} at {s.company}</div>
                    <div className="suggestion-desc">{s.description}</div>
                    {s.draft_message && (
                      <div className="draft-preview">{s.draft_message}</div>
                    )}
                    <div className="suggestion-actions">
                      <button className="btn btn-success" onClick={() => completeSuggestion(s.id)}>
                        Mark Done
                      </button>
                      <button className="btn btn-secondary" onClick={() => dismissSuggestion(s.id)}>
                        Dismiss
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {activeTab === 'discover' && (
            <div className="discover-section">
              {/* Step 0: Intro */}
              {quizStep === 0 && (
                <div className="quiz-intro">
                  <div className="quiz-intro-glow" />
                  <h2 className="quiz-intro-title">Discover Your Ideal Career</h2>
                  <p className="quiz-intro-sub">
                    Not sure what role fits you best? Take this 2-minute quiz to uncover your
                    strengths, passions, and ideal job roles — then auto-apply with tailored
                    resumes for each one.
                  </p>
                  <div className="quiz-intro-steps">
                    <div className="intro-step">
                      <div className="intro-step-num">1</div>
                      <div className="intro-step-text">Tell us what excites you</div>
                    </div>
                    <div className="intro-step">
                      <div className="intro-step-num">2</div>
                      <div className="intro-step-text">Share your natural strengths</div>
                    </div>
                    <div className="intro-step">
                      <div className="intro-step-num">3</div>
                      <div className="intro-step-text">Describe your ideal work style</div>
                    </div>
                    <div className="intro-step">
                      <div className="intro-step-num">4</div>
                      <div className="intro-step-text">Pick what matters most</div>
                    </div>
                  </div>
                  <button className="btn btn-primary btn-lg" onClick={() => setQuizStep(1)}>
                    Start Discovery Quiz
                  </button>
                </div>
              )}

              {/* Step 1: Interests */}
              {quizStep === 1 && (
                <div className="quiz-step">
                  <div className="quiz-progress">
                    <div className="quiz-progress-bar" style={{ width: '25%' }} />
                  </div>
                  <div className="quiz-step-header">
                    <span className="quiz-step-tag">Step 1 of 4</span>
                    <h2>What excites you?</h2>
                    <p>Pick everything that sparks your curiosity</p>
                  </div>
                  <div className="quiz-options-grid">
                    {[
                      { id: 'build', label: 'Building things from scratch', icon: '\u{1F528}' },
                      { id: 'analyze', label: 'Analyzing data & finding patterns', icon: '\u{1F4CA}' },
                      { id: 'design', label: 'Designing beautiful experiences', icon: '\u{1F3A8}' },
                      { id: 'lead', label: 'Leading teams & shaping strategy', icon: '\u{1F9ED}' },
                      { id: 'persuade', label: 'Persuading & communicating ideas', icon: '\u{1F4E3}' },
                      { id: 'solve', label: 'Solving technical puzzles', icon: '\u{1F9E9}' },
                      { id: 'write', label: 'Writing & storytelling', icon: '\u{270F}\u{FE0F}' },
                      { id: 'optimize', label: 'Organizing & optimizing processes', icon: '\u{2699}\u{FE0F}' },
                      { id: 'numbers', label: 'Working with numbers & finance', icon: '\u{1F4B0}' },
                      { id: 'help', label: 'Helping people learn & grow', icon: '\u{2764}\u{FE0F}' },
                    ].map(opt => (
                      <button
                        key={opt.id}
                        className={`quiz-option ${quizAnswers.interests.includes(opt.id) ? 'selected' : ''}`}
                        onClick={() => {
                          setQuizAnswers(prev => ({
                            ...prev,
                            interests: prev.interests.includes(opt.id)
                              ? prev.interests.filter(i => i !== opt.id)
                              : [...prev.interests, opt.id]
                          }))
                        }}
                      >
                        <span className="quiz-option-icon">{opt.icon}</span>
                        <span className="quiz-option-label">{opt.label}</span>
                      </button>
                    ))}
                  </div>
                  <div className="quiz-nav">
                    <button className="btn btn-secondary" onClick={() => setQuizStep(0)}>Back</button>
                    <button
                      className="btn btn-primary"
                      disabled={quizAnswers.interests.length === 0}
                      onClick={() => setQuizStep(2)}
                    >
                      Next
                    </button>
                  </div>
                </div>
              )}

              {/* Step 2: Skills */}
              {quizStep === 2 && (
                <div className="quiz-step">
                  <div className="quiz-progress">
                    <div className="quiz-progress-bar" style={{ width: '50%' }} />
                  </div>
                  <div className="quiz-step-header">
                    <span className="quiz-step-tag">Step 2 of 4</span>
                    <h2>What are you naturally good at?</h2>
                    <p>Pick your top strengths</p>
                  </div>
                  <div className="quiz-options-grid">
                    {[
                      { id: 'coding', label: 'Programming & coding', icon: '\u{1F4BB}' },
                      { id: 'visual', label: 'Visual design & aesthetics', icon: '\u{1F441}\u{FE0F}' },
                      { id: 'data', label: 'Data analysis & statistics', icon: '\u{1F4C8}' },
                      { id: 'communication', label: 'Communication & presenting', icon: '\u{1F399}\u{FE0F}' },
                      { id: 'debugging', label: 'Problem solving & debugging', icon: '\u{1F41B}' },
                      { id: 'pm', label: 'Project management & planning', icon: '\u{1F4C5}' },
                      { id: 'content', label: 'Writing & content creation', icon: '\u{270D}\u{FE0F}' },
                      { id: 'sales', label: 'Sales & negotiation', icon: '\u{1F91D}' },
                      { id: 'leadership', label: 'Leadership & mentoring', icon: '\u{1F465}' },
                      { id: 'research', label: 'Research & learning quickly', icon: '\u{1F50D}' },
                    ].map(opt => (
                      <button
                        key={opt.id}
                        className={`quiz-option ${quizAnswers.skills.includes(opt.id) ? 'selected' : ''}`}
                        onClick={() => {
                          setQuizAnswers(prev => ({
                            ...prev,
                            skills: prev.skills.includes(opt.id)
                              ? prev.skills.filter(i => i !== opt.id)
                              : [...prev.skills, opt.id]
                          }))
                        }}
                      >
                        <span className="quiz-option-icon">{opt.icon}</span>
                        <span className="quiz-option-label">{opt.label}</span>
                      </button>
                    ))}
                  </div>
                  <div className="quiz-nav">
                    <button className="btn btn-secondary" onClick={() => setQuizStep(1)}>Back</button>
                    <button
                      className="btn btn-primary"
                      disabled={quizAnswers.skills.length === 0}
                      onClick={() => setQuizStep(3)}
                    >
                      Next
                    </button>
                  </div>
                </div>
              )}

              {/* Step 3: Work Style */}
              {quizStep === 3 && (
                <div className="quiz-step">
                  <div className="quiz-progress">
                    <div className="quiz-progress-bar" style={{ width: '75%' }} />
                  </div>
                  <div className="quiz-step-header">
                    <span className="quiz-step-tag">Step 3 of 4</span>
                    <h2>How do you like to work?</h2>
                    <p>Pick the option that fits you best</p>
                  </div>

                  <div className="workstyle-group">
                    <h4>Team dynamic</h4>
                    <div className="workstyle-options">
                      {[
                        { id: 'solo', label: 'Mostly solo / deep focus' },
                        { id: 'small_team', label: 'Small collaborative team' },
                        { id: 'large_team', label: 'Large cross-functional team' },
                      ].map(opt => (
                        <button
                          key={opt.id}
                          className={`workstyle-btn ${quizAnswers.workstyle.team === opt.id ? 'selected' : ''}`}
                          onClick={() => setQuizAnswers(prev => ({
                            ...prev, workstyle: { ...prev.workstyle, team: opt.id }
                          }))}
                        >
                          {opt.label}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div className="workstyle-group">
                    <h4>Work style</h4>
                    <div className="workstyle-options">
                      {[
                        { id: 'creative', label: 'Creative & open-ended' },
                        { id: 'balanced', label: 'Mix of creative and structured' },
                        { id: 'structured', label: 'Structured & process-driven' },
                      ].map(opt => (
                        <button
                          key={opt.id}
                          className={`workstyle-btn ${quizAnswers.workstyle.structure === opt.id ? 'selected' : ''}`}
                          onClick={() => setQuizAnswers(prev => ({
                            ...prev, workstyle: { ...prev.workstyle, structure: opt.id }
                          }))}
                        >
                          {opt.label}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div className="workstyle-group">
                    <h4>Pace</h4>
                    <div className="workstyle-options">
                      {[
                        { id: 'fast', label: 'Fast-paced & high energy' },
                        { id: 'moderate', label: 'Steady & sustainable' },
                        { id: 'flexible', label: 'Self-paced & flexible' },
                      ].map(opt => (
                        <button
                          key={opt.id}
                          className={`workstyle-btn ${quizAnswers.workstyle.pace === opt.id ? 'selected' : ''}`}
                          onClick={() => setQuizAnswers(prev => ({
                            ...prev, workstyle: { ...prev.workstyle, pace: opt.id }
                          }))}
                        >
                          {opt.label}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div className="quiz-nav">
                    <button className="btn btn-secondary" onClick={() => setQuizStep(2)}>Back</button>
                    <button
                      className="btn btn-primary"
                      disabled={!quizAnswers.workstyle.team || !quizAnswers.workstyle.structure || !quizAnswers.workstyle.pace}
                      onClick={() => setQuizStep(4)}
                    >
                      Next
                    </button>
                  </div>
                </div>
              )}

              {/* Step 4: Values */}
              {quizStep === 4 && (
                <div className="quiz-step">
                  <div className="quiz-progress">
                    <div className="quiz-progress-bar" style={{ width: '100%' }} />
                  </div>
                  <div className="quiz-step-header">
                    <span className="quiz-step-tag">Step 4 of 4</span>
                    <h2>What matters most in your career?</h2>
                    <p>Pick your top 3 values</p>
                  </div>
                  <div className="quiz-options-grid">
                    {[
                      { id: 'salary', label: 'High compensation', icon: '\u{1F4B5}' },
                      { id: 'balance', label: 'Work-life balance', icon: '\u{2696}\u{FE0F}' },
                      { id: 'innovation', label: 'Innovation & creativity', icon: '\u{1F4A1}' },
                      { id: 'impact', label: 'Helping others / social impact', icon: '\u{1F30D}' },
                      { id: 'growth', label: 'Career growth & advancement', icon: '\u{1F4C8}' },
                      { id: 'security', label: 'Job security & stability', icon: '\u{1F6E1}\u{FE0F}' },
                      { id: 'autonomy', label: 'Autonomy & independence', icon: '\u{1F3F4}' },
                      { id: 'collaboration', label: 'Team & collaboration', icon: '\u{1F91D}' },
                      { id: 'scale', label: 'Impact at massive scale', icon: '\u{1F680}' },
                      { id: 'learning', label: 'Continuous learning', icon: '\u{1F4DA}' },
                    ].map(opt => (
                      <button
                        key={opt.id}
                        className={`quiz-option ${quizAnswers.values.includes(opt.id) ? 'selected' : ''} ${quizAnswers.values.length >= 3 && !quizAnswers.values.includes(opt.id) ? 'disabled' : ''}`}
                        onClick={() => {
                          if (quizAnswers.values.length >= 3 && !quizAnswers.values.includes(opt.id)) return
                          setQuizAnswers(prev => ({
                            ...prev,
                            values: prev.values.includes(opt.id)
                              ? prev.values.filter(i => i !== opt.id)
                              : [...prev.values, opt.id]
                          }))
                        }}
                      >
                        <span className="quiz-option-icon">{opt.icon}</span>
                        <span className="quiz-option-label">{opt.label}</span>
                      </button>
                    ))}
                  </div>
                  <div className="quiz-nav">
                    <button className="btn btn-secondary" onClick={() => setQuizStep(3)}>Back</button>
                    <button
                      className="btn btn-primary btn-lg"
                      disabled={quizAnswers.values.length === 0 || quizLoading}
                      onClick={submitQuiz}
                    >
                      {quizLoading ? 'Analyzing...' : 'See My Results'}
                    </button>
                  </div>
                </div>
              )}

              {/* Step 5: Results */}
              {quizStep === 5 && quizResults && (
                <div className="quiz-results">
                  <div className="quiz-results-header">
                    <div>
                      <h2>Your Ideal Roles</h2>
                      <p className="quiz-results-sub">Based on your interests, skills, work style, and values</p>
                    </div>
                    <button className="btn btn-secondary" onClick={resetQuiz}>Retake Quiz</button>
                  </div>

                  <div className="role-cards">
                    {quizResults.roles.map((role, i) => (
                      <div key={role.role} className={`role-card ${i < 3 ? 'top-match' : ''}`}>
                        <div className="role-card-header">
                          <div className="role-card-rank">#{i + 1}</div>
                          <div className="role-card-info">
                            <div className="role-card-title">{role.role}</div>
                            <div className="role-card-field">{role.field}</div>
                          </div>
                          <div className={`role-match-badge ${role.match_percent >= 70 ? 'high' : role.match_percent >= 40 ? 'medium' : 'low'}`}>
                            {role.match_percent}% match
                          </div>
                        </div>
                        <div className="role-card-skills">
                          <span className="role-skills-label">Skills needed:</span> {role.skills_needed}
                        </div>
                        <div className="role-card-bar">
                          <div
                            className={`role-card-fill ${role.match_percent >= 70 ? 'high' : role.match_percent >= 40 ? 'medium' : 'low'}`}
                            style={{ width: `${role.match_percent}%` }}
                          />
                        </div>
                        <div className="role-card-actions">
                          <button
                            className={`btn btn-sm ${selectedRolesForApply.includes(role.role) ? 'btn-success' : 'btn-secondary'}`}
                            onClick={() => toggleRoleForApply(role.role)}
                          >
                            {selectedRolesForApply.includes(role.role) ? 'Selected for Auto-Apply' : 'Select for Auto-Apply'}
                          </button>
                          <button
                            className="btn btn-secondary btn-sm"
                            disabled={discoveryJobsLoading[role.role]}
                            onClick={() => searchRoleJobs(role)}
                          >
                            {discoveryJobsLoading[role.role] ? 'Searching...' : discoveryJobs[role.role] ? `${discoveryJobs[role.role].length} jobs found` : 'See Open Jobs'}
                          </button>
                        </div>
                        {discoveryJobs[role.role] && discoveryJobs[role.role].length > 0 && (
                          <div className="role-jobs-preview">
                            {discoveryJobs[role.role].slice(0, 3).map((job, j) => (
                              <div key={j} className="role-job-item">
                                <div className="role-job-title">{job.title}</div>
                                <div className="role-job-company">{job.company}</div>
                                {job.url && <a href={job.url} target="_blank" rel="noopener noreferrer" className="role-job-link">View Listing</a>}
                              </div>
                            ))}
                          </div>
                        )}
                        {discoveryJobs[role.role] && discoveryJobs[role.role].length === 0 && (
                          <div className="role-jobs-empty">No open positions found right now</div>
                        )}
                      </div>
                    ))}
                  </div>

                  {/* Auto-Apply Panel */}
                  {selectedRolesForApply.length > 0 && (
                    <div className="discovery-auto-apply">
                      <div className="discovery-auto-apply-header">
                        <div>
                          <h3>Auto-Apply to {selectedRolesForApply.length} Role{selectedRolesForApply.length > 1 ? 's' : ''}</h3>
                          <p>
                            {selectedCandidate
                              ? `Applying as ${selectedCandidate.name} — CV and cover letter will be customized for each job`
                              : 'Select a candidate from the sidebar first'}
                          </p>
                        </div>
                        <button
                          className={`btn ${autoApplyRunning ? 'btn-warning' : 'btn-primary'} btn-lg`}
                          disabled={autoApplyRunning || !selectedCandidate}
                          onClick={runDiscoveryAutoApply}
                        >
                          {autoApplyRunning ? 'Applying...' : 'Auto-Apply Now'}
                        </button>
                      </div>
                      <div className="selected-roles-chips">
                        {selectedRolesForApply.map(r => (
                          <span key={r} className="role-chip">
                            {r}
                            <button onClick={() => toggleRoleForApply(r)}>&times;</button>
                          </span>
                        ))}
                      </div>

                      {autoApplyRunning && (
                        <div className="agent-running" style={{ marginTop: '1rem' }}>
                          <div className="spinner"></div>
                          <p>Searching job boards, tailoring resumes & cover letters for each application...</p>
                        </div>
                      )}

                      {autoApplyResult && !autoApplyRunning && (
                        <div className={`agent-result ${autoApplyResult.status === 'error' ? 'error' : ''}`} style={{ marginTop: '1rem' }}>
                          {autoApplyResult.status === 'error' ? (
                            <p className="error-text">Error: {autoApplyResult.error}</p>
                          ) : (
                            <>
                              <div className="result-stats">
                                <div className="result-stat">
                                  <span className="result-number">{autoApplyResult.total_discovered || 0}</span>
                                  <span className="result-label">Jobs Found</span>
                                </div>
                                <div className="result-stat">
                                  <span className="result-number">{autoApplyResult.total_applied || 0}</span>
                                  <span className="result-label">Applications Created</span>
                                </div>
                                <div className="result-stat">
                                  <span className="result-number">{autoApplyResult.jobs?.filter(j => j.has_tailored_resume).length || 0}</span>
                                  <span className="result-label">Resumes Tailored</span>
                                </div>
                              </div>
                              {autoApplyResult.jobs && autoApplyResult.jobs.length > 0 && (
                                <div className="auto-apply-jobs-list">
                                  <h4>Applications Created</h4>
                                  {autoApplyResult.jobs.map((job, i) => (
                                    <div key={i} className="auto-apply-job-item">
                                      <div className="auto-apply-job-info">
                                        <div className="auto-apply-job-title">{job.title}</div>
                                        <div className="auto-apply-job-company">{job.company}</div>
                                      </div>
                                      <div className="auto-apply-job-badges">
                                        <span className={`score-badge ${job.score >= 70 ? 'high' : job.score >= 40 ? 'medium' : 'low'}`}>
                                          {job.score}%
                                        </span>
                                        {job.has_tailored_resume && <span className="badge-ready">CV</span>}
                                        {job.has_cover_letter && <span className="badge-ready">Cover Letter</span>}
                                      </div>
                                    </div>
                                  ))}
                                </div>
                              )}
                            </>
                          )}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </main>
      </div>

      {/* Add Candidate Modal */}
      {showAddCandidate && (
        <AddCandidateModal onSave={addCandidate} onClose={() => setShowAddCandidate(false)} />
      )}

      {/* Add Application Modal */}
      {showAddApplication && selectedCandidate && (
        <AddApplicationModal
          candidateId={selectedCandidate.id}
          onSave={addApplication}
          onClose={() => setShowAddApplication(false)}
        />
      )}

      {/* Application Detail Modal */}
      {selectedApp && (
        <AppDetailModal
          app={selectedApp}
          onClose={() => setSelectedApp(null)}
          onStatusChange={(status) => { updateStatus(selectedApp.id, status); setSelectedApp(null) }}
        />
      )}
    </div>
  )
}

function AddCandidateModal({ onSave, onClose }) {
  const [form, setForm] = useState({
    name: '', email: '', field: '', target_role: '',
    linkedin_url: '', skills: '', years_experience: '',
    location_preference: '', base_resume_text: '',
  })

  const handleSubmit = (e) => {
    e.preventDefault()
    onSave({
      ...form,
      years_experience: form.years_experience ? parseInt(form.years_experience) : null,
    })
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <h2>Add Candidate</h2>
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>Name *</label>
            <input required value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} />
          </div>
          <div className="form-group">
            <label>Email</label>
            <input type="email" value={form.email} onChange={e => setForm({ ...form, email: e.target.value })} />
          </div>
          <div className="form-group">
            <label>Field *</label>
            <input required placeholder="e.g., Software Engineering, Marketing, Data Science" value={form.field} onChange={e => setForm({ ...form, field: e.target.value })} />
          </div>
          <div className="form-group">
            <label>Target Role *</label>
            <input required placeholder="e.g., Senior Frontend Engineer" value={form.target_role} onChange={e => setForm({ ...form, target_role: e.target.value })} />
          </div>
          <div className="form-group">
            <label>LinkedIn URL</label>
            <input value={form.linkedin_url} onChange={e => setForm({ ...form, linkedin_url: e.target.value })} />
          </div>
          <div className="form-group">
            <label>Skills (comma-separated)</label>
            <input placeholder="React, Python, AWS, ..." value={form.skills} onChange={e => setForm({ ...form, skills: e.target.value })} />
          </div>
          <div className="form-group">
            <label>Years of Experience</label>
            <input type="number" value={form.years_experience} onChange={e => setForm({ ...form, years_experience: e.target.value })} />
          </div>
          <div className="form-group">
            <label>Location Preference</label>
            <input placeholder="Remote, NYC, SF Bay Area..." value={form.location_preference} onChange={e => setForm({ ...form, location_preference: e.target.value })} />
          </div>
          <div className="form-group">
            <label>Resume Text (paste full resume)</label>
            <textarea rows="8" placeholder="Paste the full text of the base resume here..." value={form.base_resume_text} onChange={e => setForm({ ...form, base_resume_text: e.target.value })} />
          </div>
          <div className="form-actions">
            <button type="button" className="btn btn-secondary" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn btn-primary">Add Candidate</button>
          </div>
        </form>
      </div>
    </div>
  )
}

function AddApplicationModal({ candidateId, onSave, onClose }) {
  const [form, setForm] = useState({
    candidate_id: candidateId,
    company_name: '', job_title: '', job_url: '',
    job_description: '', salary_range: '', location: '',
  })

  const handleSubmit = (e) => {
    e.preventDefault()
    onSave(form)
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <h2>Add Job Application</h2>
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>Company Name *</label>
            <input required value={form.company_name} onChange={e => setForm({ ...form, company_name: e.target.value })} />
          </div>
          <div className="form-group">
            <label>Job Title *</label>
            <input required value={form.job_title} onChange={e => setForm({ ...form, job_title: e.target.value })} />
          </div>
          <div className="form-group">
            <label>Job URL</label>
            <input value={form.job_url} onChange={e => setForm({ ...form, job_url: e.target.value })} />
          </div>
          <div className="form-group">
            <label>Salary Range</label>
            <input placeholder="$120k-$160k" value={form.salary_range} onChange={e => setForm({ ...form, salary_range: e.target.value })} />
          </div>
          <div className="form-group">
            <label>Location</label>
            <input placeholder="Remote, Hybrid - NYC, etc." value={form.location} onChange={e => setForm({ ...form, location: e.target.value })} />
          </div>
          <div className="form-group">
            <label>Job Description (paste full JD for resume tailoring)</label>
            <textarea rows="10" placeholder="Paste the full job description here. This is used to tailor the resume and calculate match score." value={form.job_description} onChange={e => setForm({ ...form, job_description: e.target.value })} />
          </div>
          <div className="form-actions">
            <button type="button" className="btn btn-secondary" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn btn-primary">Create & Tailor Resume</button>
          </div>
        </form>
      </div>
    </div>
  )
}

function JobCard({ job, candidates, onSave }) {
  const [selectedCandidate, setSelectedCandidate] = useState('')
  const [expanded, setExpanded] = useState(false)
  const locationStr = typeof job.location === 'object' ? job.location.join(', ') : (job.location || '')

  return (
    <div className="job-card">
      <div className="job-card-header" onClick={() => setExpanded(!expanded)}>
        <div className="job-card-info">
          <div className="job-card-title">{job.title}</div>
          <div className="job-card-company">{job.company}</div>
          <div className="job-card-meta">
            {locationStr && <span className="job-tag">{locationStr}</span>}
            {job.job_type && <span className="job-tag">{job.job_type}</span>}
            {job.salary && <span className="job-tag salary">{job.salary}</span>}
            <span className={`job-tag source ${job.source?.startsWith('Gov:') ? 'gov-source' : ''}`}>{job.source}</span>
          </div>
        </div>
        <div className="job-card-actions" onClick={e => e.stopPropagation()}>
          <select
            value={selectedCandidate}
            onChange={e => setSelectedCandidate(e.target.value)}
            className="candidate-select"
          >
            <option value="">Select person...</option>
            {candidates.map(c => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
          <button
            className="btn btn-primary btn-sm"
            disabled={!selectedCandidate}
            onClick={() => onSave(job, parseInt(selectedCandidate))}
          >
            Save to Pipeline
          </button>
        </div>
      </div>
      {expanded && job.description && (
        <div className="job-card-desc">
          {job.description.substring(0, 500)}{job.description.length > 500 ? '...' : ''}
        </div>
      )}
      {job.url && (
        <a href={job.url} target="_blank" rel="noopener noreferrer" className="job-link" onClick={e => e.stopPropagation()}>
          View Full Listing →
        </a>
      )}
    </div>
  )
}

function AppDetailModal({ app, onClose, onStatusChange }) {
  const nextStatuses = {
    saved: ['applied'],
    applied: ['awaiting_response', 'withdrawn'],
    awaiting_response: ['follow_up_sent', 'interview_scheduled', 'rejected', 'withdrawn'],
    follow_up_sent: ['interview_scheduled', 'rejected', 'withdrawn'],
    interview_scheduled: ['interview_completed', 'withdrawn'],
    interview_completed: ['offer_received', 'rejected'],
    offer_received: ['withdrawn'],
  }

  const available = nextStatuses[app.status] || []

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <h2>{app.job_title}</h2>
        <p style={{ color: '#a1a1aa', marginBottom: '1rem' }}>{app.company_name}</p>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1.5rem' }}>
          <div>
            <div style={{ fontSize: '0.75rem', color: '#71717a' }}>Status</div>
            <div style={{ fontWeight: 600 }}>{STATUS_LABELS[app.status]}</div>
          </div>
          <div>
            <div style={{ fontSize: '0.75rem', color: '#71717a' }}>Match Score</div>
            <div style={{ fontWeight: 600 }}>{app.match_score ? `${app.match_score}%` : 'N/A'}</div>
          </div>
          <div>
            <div style={{ fontSize: '0.75rem', color: '#71717a' }}>Applied</div>
            <div>{app.applied_at ? new Date(app.applied_at).toLocaleDateString() : 'Not yet'}</div>
          </div>
          <div>
            <div style={{ fontSize: '0.75rem', color: '#71717a' }}>Location</div>
            <div>{app.location || 'N/A'}</div>
          </div>
        </div>

        {available.length > 0 && (
          <div style={{ marginBottom: '1.5rem' }}>
            <div style={{ fontSize: '0.8rem', color: '#71717a', marginBottom: '0.5rem' }}>Move to:</div>
            <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
              {available.map(s => (
                <button key={s} className="btn btn-secondary" onClick={() => onStatusChange(s)}>
                  {STATUS_LABELS[s]}
                </button>
              ))}
            </div>
          </div>
        )}

        <div className="form-actions">
          <button className="btn btn-secondary" onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  )
}

export default App
