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
            <span className="job-tag source">{job.source}</span>
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
