import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Plus, Upload, Trash2, FileText, MessageSquare,
  Loader2, GitBranch, Folder, RefreshCw, Database,
  Search, CheckCircle, XCircle, FolderKanban, Code2, BookOpen, Layers
} from 'lucide-react';
import Layout from '../components/layout/Layout';
import Loading from '../components/common/Loading';
import Alert from '../components/common/Alert';
import ConnectSourceModal from './ConnectSourceModal';
import api from '../services/api';

// ── Icon picker by project name heuristic ────────────────────────────────────
const ProjectIcon = ({ name }) => {
  const n = (name || '').toLowerCase();
  if (n.includes('code') || n.includes('eng') || n.includes('dev') || n.includes('git'))
    return <Code2 size={16} />;
  if (n.includes('legal') || n.includes('contract') || n.includes('law'))
    return <BookOpen size={16} />;
  if (n.includes('data') || n.includes('base') || n.includes('db'))
    return <Database size={16} />;
  if (n.includes('layer') || n.includes('stack') || n.includes('infra'))
    return <Layers size={16} />;
  return <FolderKanban size={16} />;
};

// ── Vector store badge ────────────────────────────────────────────────────────
const VsBadge = ({ type }) => {
  const cfg = {
    chroma:     { label: 'ChromaDB',    bg: '#EEEDFE', color: '#3C3489', border: '#AFA9EC' },
    opensearch: { label: 'OpenSearch',  bg: '#FAEEDA', color: '#633806', border: '#EF9F27' },
    both:       { label: 'Chroma + OS', bg: '#EAF3DE', color: '#27500A', border: '#97C459' },
  };
  const c = cfg[type] || cfg.chroma;
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: '4px',
      padding: '3px 8px', borderRadius: '20px',
      fontSize: '11px', fontWeight: '500',
      background: c.bg, color: c.color,
      border: `0.5px solid ${c.border}`,
    }}>
      <Database size={10} />
      {c.label}
    </span>
  );
};

// ── Integration badge ─────────────────────────────────────────────────────────
const IntBadge = ({ integration }) => {
  const isGit = integration.type === 'git';
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: '4px',
      padding: '3px 8px', borderRadius: '20px',
      fontSize: '11px', fontWeight: '500',
      background: isGit ? '#FAEEDA' : '#EAF3DE',
      color: isGit ? '#633806' : '#27500A',
      border: `0.5px solid ${isGit ? '#EF9F27' : '#97C459'}`,
    }}>
      {isGit ? <GitBranch size={10} /> : <Folder size={10} />}
      {integration.name}
    </span>
  );
};

// ── Stat cell ─────────────────────────────────────────────────────────────────
const Stat = ({ value, label }) => (
  <div style={{
    flex: 1,
    background: 'var(--gray-50, #f9fafb)',
    borderRadius: 'var(--radius)',
    padding: '8px 10px',
  }}>
    <div style={{ fontSize: '18px', fontWeight: '600', color: 'var(--gray-900)', lineHeight: 1 }}>
      {value >= 1000 ? `${(value / 1000).toFixed(1)}k` : value}
    </div>
    <div style={{ fontSize: '11px', color: 'var(--gray-500)', marginTop: '3px' }}>{label}</div>
  </div>
);

// ── Action button ─────────────────────────────────────────────────────────────
const ActBtn = ({ onClick, icon: Icon, label, primary, iconOnly, disabled, title }) => (
  <button
    onClick={onClick}
    disabled={disabled}
    title={title}
    style={{
      flex: iconOnly ? 'none' : 1,
      width: iconOnly ? '32px' : 'auto',
      display: 'inline-flex',
      alignItems: 'center',
      justifyContent: 'center',
      gap: '5px',
      padding: iconOnly ? '0' : '7px 10px',
      height: '32px',
      borderRadius: 'var(--radius)',
      border: primary ? 'none' : '1px solid var(--gray-200)',
      background: primary ? 'var(--primary)' : 'transparent',
      color: primary ? 'white' : 'var(--gray-600)',
      fontSize: '12px',
      fontWeight: '500',
      cursor: disabled ? 'not-allowed' : 'pointer',
      opacity: disabled ? 0.5 : 1,
      transition: 'all 0.12s',
    }}
    onMouseEnter={e => {
      if (disabled) return;
      if (!primary) {
        e.currentTarget.style.background = 'var(--gray-50)';
        e.currentTarget.style.color = 'var(--gray-900)';
      } else {
        e.currentTarget.style.opacity = '0.85';
      }
    }}
    onMouseLeave={e => {
      if (!primary) {
        e.currentTarget.style.background = 'transparent';
        e.currentTarget.style.color = 'var(--gray-600)';
      } else {
        e.currentTarget.style.opacity = '1';
      }
    }}
  >
    <Icon size={13} />
    {!iconOnly && label}
  </button>
);

// ─────────────────────────────────────────────────────────────────────────────

const Projects = () => {
  const navigate = useNavigate();
  const [projects, setProjects]           = useState([]);
  const [loading, setLoading]             = useState(true);
  const [showModal, setShowModal]         = useState(false);
  const [showSourceModal, setShowSourceModal] = useState(false);
  const [selectedProject, setSelectedProject] = useState(null);
  const [uploading, setUploading]         = useState({});
  const [syncing, setSyncing]             = useState({});
  const [integrations, setIntegrations]   = useState({});
  const [alert, setAlert]                 = useState(null);

  const [osIndices, setOsIndices]         = useState([]);
  const [osHealthOk, setOsHealthOk]       = useState(null);
  const [osIndexInput, setOsIndexInput]   = useState('');
  const [creatingIndex, setCreatingIndex] = useState(false);

  const [formData, setFormData] = useState({
    name: '',
    description: '',
    chunk_size: 2000,
    chunk_overlap: 200,
    vector_store_type: 'chroma',
    opensearch_index: '',
  });

  useEffect(() => { loadProjects(); }, []);

  useEffect(() => {
    if (formData.vector_store_type === 'chroma') {
      setOsHealthOk(null);
      setOsIndices([]);
      return;
    }
    checkOpenSearchHealth();
  }, [formData.vector_store_type]);

  const checkOpenSearchHealth = async () => {
    try {
      const res = await api.get('/api/opensearch/health');
      const ok = res.data.status === 'ok';
      setOsHealthOk(ok);
      if (ok) {
        const idxRes = await api.get('/api/opensearch/indices');
        setOsIndices(idxRes.data || []);
      }
    } catch {
      setOsHealthOk(false);
      setOsIndices([]);
    }
  };

  const createOsIndex = async () => {
    if (!osIndexInput.trim()) return;
    setCreatingIndex(true);
    try {
      const res = await api.post('/api/opensearch/indices', { index_name: osIndexInput.trim() });
      showAlert('success', res.data.created
        ? `Index '${osIndexInput}' created`
        : `Index '${osIndexInput}' already exists`);
      setFormData(f => ({ ...f, opensearch_index: osIndexInput.trim() }));
      await checkOpenSearchHealth();
    } catch (err) {
      showAlert('error', err.response?.data?.detail || 'Failed to create index');
    } finally {
      setCreatingIndex(false);
    }
  };

  const loadProjects = async () => {
    try {
      const res = await api.get('/api/projects/');
      setProjects(res.data);
      const integrationsData = {};
      for (const project of res.data) {
        try {
          const intRes = await api.get(`/api/integrations/projects/${project.id}/sources`);
          integrationsData[project.id] = intRes.data || [];
        } catch {
          integrationsData[project.id] = [];
        }
      }
      setIntegrations(integrationsData);
    } catch {
      showAlert('error', 'Failed to load projects');
    } finally {
      setLoading(false);
    }
  };

  const createProject = async (e) => {
    e.preventDefault();
    const payload = {
      ...formData,
      opensearch_index: formData.opensearch_index?.trim() || null,
    };
    try {
      await api.post('/api/projects/', payload);
      showAlert('success', 'Project created successfully');
      setShowModal(false);
      resetForm();
      loadProjects();
    } catch (error) {
      showAlert('error', error.response?.data?.detail || 'Failed to create project');
    }
  };

  const deleteProject = async (projectId) => {
    if (!confirm('Delete this project and all its documents?')) return;
    try {
      await api.delete(`/api/projects/${projectId}`);
      showAlert('success', 'Project deleted');
      loadProjects();
    } catch {
      showAlert('error', 'Failed to delete project');
    }
  };

  const uploadDocument = async (projectId, file) => {
    setUploading(prev => ({ ...prev, [projectId]: true }));
    const fd = new FormData();
    fd.append('file', file);
    try {
      const res = await api.post(`/api/documents/${projectId}/upload`, fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      showAlert('success', `Document uploaded: ${res.data.filename}`);
      pollDocumentStatus(res.data.document_id);
    } catch (error) {
      showAlert('error', error.response?.data?.detail || 'Upload failed');
    } finally {
      setUploading(prev => ({ ...prev, [projectId]: false }));
    }
  };

  const pollDocumentStatus = (documentId) => {
    const interval = setInterval(async () => {
      try {
        const res = await api.get(`/api/documents/${documentId}/status`);
        if (res.data.status === 'completed') {
          showAlert('success', `Processing complete: ${res.data.chunk_count} chunks`);
          clearInterval(interval);
          loadProjects();
        } else if (res.data.status === 'failed') {
          showAlert('error', `Processing failed: ${res.data.error_message}`);
          clearInterval(interval);
        }
      } catch {
        clearInterval(interval);
      }
    }, 2000);
  };

  const openConnectSource = (project) => {
    setSelectedProject(project);
    setShowSourceModal(true);
  };

  const syncExternalSources = async (projectId) => {
    setSyncing(prev => ({ ...prev, [projectId]: true }));
    try {
      const res = await api.post('/api/integrations/sync', { domain: projectId.toString() });
      showAlert('success', `Synced ${res.data.total_documents} documents from external sources`);
      loadProjects();
    } catch (error) {
      showAlert('error', 'Sync failed: ' + (error.response?.data?.detail || error.message));
    } finally {
      setSyncing(prev => ({ ...prev, [projectId]: false }));
    }
  };

  const resetForm = () => {
    setFormData({ name: '', description: '', chunk_size: 2000, chunk_overlap: 200, vector_store_type: 'chroma', opensearch_index: '' });
    setOsHealthOk(null);
    setOsIndices([]);
    setOsIndexInput('');
  };

  const showAlert = (type, message) => {
    setAlert({ type, message });
    setTimeout(() => setAlert(null), 5000);
  };

  if (loading) return <Layout><Loading message="Loading projects..." /></Layout>;

  const needsOpenSearch = formData.vector_store_type === 'opensearch' || formData.vector_store_type === 'both';

  const totalDocs = projects.reduce((s, p) => s + (p.document_count || 0), 0);

  return (
    <Layout>
      <div style={{ padding: 'var(--spacing-8) var(--spacing-6)', maxWidth: '1200px', margin: '0 auto' }}>

        {/* Alert */}
        {alert && (
          <div style={{ marginBottom: 'var(--spacing-4)' }}>
            <Alert type={alert.type} message={alert.message} onClose={() => setAlert(null)} />
          </div>
        )}

        {/* ── Header ── */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 'var(--spacing-8)' }}>
          <div>
            <h1 style={{ fontSize: 'var(--text-2xl)', fontWeight: '600', color: 'var(--gray-900)', marginBottom: '4px' }}>
              RAG Projects
            </h1>
            <p style={{ fontSize: 'var(--text-sm)', color: 'var(--gray-500)' }}>
              {projects.length} project{projects.length !== 1 ? 's' : ''} · {totalDocs.toLocaleString()} documents indexed
            </p>
          </div>
          <button
            onClick={() => setShowModal(true)}
            style={{
              display: 'inline-flex', alignItems: 'center', gap: '6px',
              padding: '9px 18px',
              background: 'transparent',
              color: 'white',
              border: 'none',
              borderRadius: 'var(--radius)',
              fontSize: 'var(--text-sm)',
              fontWeight: '500',
              cursor: 'pointer',
              transition: 'opacity 0.15s',
            }}
            onMouseEnter={e => e.currentTarget.style.opacity = '0.85'}
            onMouseLeave={e => e.currentTarget.style.opacity = '1'}
          >
            <Plus size={14} />
            New project
          </button>
        </div>

        {/* ── Empty state ── */}
        {projects.length === 0 ? (
          <div style={{
            display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
            padding: 'var(--spacing-16)',
            border: '1px dashed var(--gray-300)',
            borderRadius: 'var(--radius-lg)',
            textAlign: 'center',
            gap: 'var(--spacing-4)',
          }}>
            <div style={{
              width: '48px', height: '48px', borderRadius: '50%',
              border: '1px solid var(--gray-200)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              color: 'var(--gray-400)',
            }}>
              <Plus size={20} />
            </div>
            <div>
              <p style={{ fontWeight: '500', color: 'var(--gray-700)', marginBottom: '4px' }}>No projects yet</p>
              <p style={{ fontSize: 'var(--text-sm)', color: 'var(--gray-500)' }}>Create your first RAG project to get started</p>
            </div>
            <button
              onClick={() => setShowModal(true)}
              style={{
                padding: '8px 20px',
                background: 'var(--gray-900)', color: 'white',
                border: 'none', borderRadius: 'var(--radius)',
                fontSize: 'var(--text-sm)', fontWeight: '500', cursor: 'pointer',
              }}
            >
              Create project
            </button>
          </div>
        ) : (
          /* ── Grid ── */
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))',
            gap: 'var(--spacing-4)',
          }}>
            {projects.map(project => (
              <div
                key={project.id}
                className="card"
                style={{
                  padding: 'var(--spacing-5)',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '14px',
                  transition: 'border-color 0.15s',
                }}
                onMouseEnter={e => e.currentTarget.style.borderColor = 'var(--gray-300)'}
                onMouseLeave={e => e.currentTarget.style.borderColor = ''}
              >
                {/* Card header */}
                <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '8px' }}>
                  <div style={{ display: 'flex', gap: '10px', alignItems: 'flex-start', flex: 1, minWidth: 0 }}>
                    {/* Icon */}
                    <div style={{
                      width: '36px', height: '36px', flexShrink: 0,
                      borderRadius: 'var(--radius)',
                      background: 'var(--gray-100)',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      color: 'var(--gray-600)',
                    }}>
                      <ProjectIcon name={project.name} />
                    </div>
                    {/* Title + desc */}
                    <div style={{ minWidth: 0 }}>
                      <div style={{
                        fontSize: 'var(--text-sm)', fontWeight: '600',
                        color: 'var(--gray-900)',
                        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                      }}>
                        {project.name}
                      </div>
                      {project.description && (
                        <div style={{
                          fontSize: 'var(--text-xs)', color: 'var(--gray-500)',
                          marginTop: '2px', lineHeight: '1.4',
                          overflow: 'hidden', textOverflow: 'ellipsis',
                          display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical',
                        }}>
                          {project.description}
                        </div>
                      )}
                    </div>
                  </div>
                  {/* Delete */}
                  <button
                    onClick={() => deleteProject(project.id)}
                    style={{
                      flexShrink: 0, padding: '4px',
                      background: 'none', border: 'none', cursor: 'pointer',
                      color: 'var(--gray-400)', borderRadius: '6px',
                      transition: 'all 0.12s',
                    }}
                    onMouseEnter={e => { e.currentTarget.style.color = 'var(--danger)'; e.currentTarget.style.background = 'rgba(239,68,68,0.08)'; }}
                    onMouseLeave={e => { e.currentTarget.style.color = 'var(--gray-400)'; e.currentTarget.style.background = 'none'; }}
                    title="Delete project"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>

                {/* Stats row */}
                <div style={{ display: 'flex', gap: '6px' }}>
                  <Stat value={project.document_count || 0} label="docs" />
                  <Stat value={project.total_chunks || 0} label="chunks" />
                </div>

                {/* Badges row */}
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', alignItems: 'center' }}>
                  <VsBadge type={project.vector_store_type || 'chroma'} />
                  {(project.vector_store_type === 'opensearch' || project.vector_store_type === 'both') && project.opensearch_index && (
                    <span style={{
                      fontSize: '11px', color: 'var(--gray-500)',
                      fontFamily: 'monospace',
                    }}>
                      {project.opensearch_index}
                    </span>
                  )}
                  {integrations[project.id]?.map(integration => (
                    <IntBadge key={integration.id} integration={integration} />
                  ))}
                </div>

                {/* Divider */}
                <div style={{ height: '1px', background: 'var(--gray-100)' }} />

                {/* Actions */}
                <div style={{ display: 'flex', gap: '6px' }}>
                  {/* Chat — primary */}
                  <ActBtn
                    primary
                    icon={MessageSquare}
                    label="Chat"
                    onClick={() => navigate(`/projects/${project.id}/chat`)}
                  />
                  {/* Docs */}
                  <ActBtn
                    icon={FileText}
                    label="Docs"
                    onClick={() => navigate(`/projects/${project.id}/documents`)}
                  />
                  {/* Upload */}
                  <label
                    style={{
                      flex: 1,
                      display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                      gap: '5px',
                      height: '32px',
                      borderRadius: 'var(--radius)',
                      border: '1px solid var(--gray-200)',
                      background: 'transparent',
                      color: uploading[project.id] ? 'var(--primary)' : 'var(--gray-600)',
                      fontSize: '12px', fontWeight: '500',
                      cursor: uploading[project.id] ? 'not-allowed' : 'pointer',
                      transition: 'all 0.12s',
                    }}
                    onMouseEnter={e => { if (!uploading[project.id]) { e.currentTarget.style.background = 'var(--gray-50)'; e.currentTarget.style.color = 'var(--gray-900)'; } }}
                    onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = uploading[project.id] ? 'var(--primary)' : 'var(--gray-600)'; }}
                  >
                    {uploading[project.id]
                      ? <><Loader2 size={13} className="animate-spin" /> Uploading</>
                      : <><Upload size={13} /> Upload</>
                    }
                    <input
                      type="file" hidden
                      accept=".pdf,.docx,.doc,.pptx,.ppt,.txt,.md,.markdown,.html,.htm,.xlsx,.xls,.csv,.rtf,.odt,.ods,.odp,.tex,.epub,.xml,.py,.js,.jsx,.ts,.tsx,.css,.java,.cpp,.c,.cs,.go,.rs,.php,.rb,.swift,.kt,.scala,.r,.groovy,.sh,.bash,.sql,.json,.yaml,.yml,.toml,.ini,.env,.jenkinsfile,.zip,.tar,.gz"
                      onChange={e => uploadDocument(project.id, e.target.files[0])}
                      disabled={uploading[project.id]}
                    />
                  </label>
                  {/* Connect source */}
                  <ActBtn
                    iconOnly
                    icon={GitBranch}
                    title="Connect Git / Drive"
                    onClick={() => openConnectSource(project)}
                  />
                  {/* Sync */}
                  <ActBtn
                    iconOnly
                    icon={syncing[project.id] ? Loader2 : RefreshCw}
                    title="Sync external sources"
                    onClick={() => syncExternalSources(project.id)}
                    disabled={syncing[project.id]}
                  />
                </div>
              </div>
            ))}

            {/* ── Add card ── */}
            <div
              onClick={() => setShowModal(true)}
              style={{
                display: 'flex', flexDirection: 'column',
                alignItems: 'center', justifyContent: 'center',
                gap: '8px', minHeight: '200px',
                border: '1px dashed var(--gray-200)',
                borderRadius: 'var(--radius-lg)',
                cursor: 'pointer',
                transition: 'all 0.15s',
                color: 'var(--gray-400)',
              }}
              onMouseEnter={e => { e.currentTarget.style.background = 'var(--gray-50)'; e.currentTarget.style.borderColor = 'var(--gray-300)'; e.currentTarget.style.color = 'var(--gray-600)'; }}
              onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.borderColor = 'var(--gray-200)'; e.currentTarget.style.color = 'var(--gray-400)'; }}
            >
              <div style={{
                width: '36px', height: '36px', borderRadius: '50%',
                border: '1px solid var(--gray-200)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                <Plus size={16} />
              </div>
              <span style={{ fontSize: 'var(--text-sm)' }}>New project</span>
            </div>
          </div>
        )}

        {/* ══ Modal: Create Project ══════════════════════════════════════════════ */}
        {showModal && (
          <div style={{
            position: 'fixed', inset: 0,
            backgroundColor: 'rgba(0,0,0,0.4)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            zIndex: 1000, padding: 'var(--spacing-4)', overflowY: 'auto',
          }}>
            <div className="card" style={{ width: '100%', maxWidth: '600px', padding: 'var(--spacing-8)' }}>

              {/* Modal header */}
              <div style={{ marginBottom: 'var(--spacing-6)' }}>
                <h2 style={{ fontSize: 'var(--text-xl)', fontWeight: '600', color: 'var(--gray-900)' }}>
                  New RAG Project
                </h2>
                <p style={{ fontSize: 'var(--text-sm)', color: 'var(--gray-500)', marginTop: '4px' }}>
                  Configure your document collection and vector store
                </p>
              </div>

              <form onSubmit={createProject}>
                {/* Name */}
                <div className="form-group">
                  <label className="form-label">Project name</label>
                  <input
                    type="text" className="form-input"
                    value={formData.name}
                    onChange={e => setFormData({ ...formData, name: e.target.value })}
                    required placeholder="e.g., Company Knowledge Base"
                  />
                </div>

                {/* Description */}
                <div className="form-group">
                  <label className="form-label">
                    Description
                    <span style={{ fontWeight: '400', color: 'var(--gray-400)', marginLeft: '6px' }}>optional</span>
                  </label>
                  <textarea
                    className="form-textarea"
                    value={formData.description}
                    onChange={e => setFormData({ ...formData, description: e.target.value })}
                    placeholder="What is this project about?"
                    rows={2}
                  />
                </div>

                {/* Chunk settings */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--spacing-4)' }}>
                  <div className="form-group">
                    <label className="form-label">Chunk size <span style={{ color: 'var(--gray-400)', fontWeight: '400' }}>tokens</span></label>
                    <input
                      type="number" className="form-input"
                      value={formData.chunk_size}
                      onChange={e => setFormData({ ...formData, chunk_size: parseInt(e.target.value) })}
                      min="500" max="8000"
                    />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Chunk overlap</label>
                    <input
                      type="number" className="form-input"
                      value={formData.chunk_overlap}
                      onChange={e => setFormData({ ...formData, chunk_overlap: parseInt(e.target.value) })}
                      min="0" max="1000"
                    />
                  </div>
                </div>

                {/* Vector store selector */}
                <div className="form-group">
                  <label className="form-label">Vector store</label>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 'var(--spacing-2)', marginTop: 'var(--spacing-2)' }}>
                    {[
                      { value: 'chroma',     label: 'ChromaDB',   desc: 'Local · no extra infra' },
                      { value: 'opensearch', label: 'OpenSearch', desc: 'Scalable cluster' },
                      { value: 'both',       label: 'Both',       desc: 'Index in both' },
                    ].map(opt => (
                      <label
                        key={opt.value}
                        style={{
                          display: 'block', padding: 'var(--spacing-3)',
                          borderRadius: 'var(--radius)', cursor: 'pointer',
                          border: `2px solid ${formData.vector_store_type === opt.value ? 'var(--primary)' : 'var(--border)'}`,
                          background: formData.vector_store_type === opt.value ? 'rgba(99,102,241,0.05)' : 'transparent',
                          transition: 'all 0.12s',
                        }}
                      >
                        <input
                          type="radio" name="vector_store_type" value={opt.value} hidden
                          checked={formData.vector_store_type === opt.value}
                          onChange={e => setFormData({ ...formData, vector_store_type: e.target.value, opensearch_index: '' })}
                        />
                        <div style={{ fontWeight: '600', fontSize: 'var(--text-sm)', marginBottom: '2px' }}>{opt.label}</div>
                        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--gray-500)' }}>{opt.desc}</div>
                      </label>
                    ))}
                  </div>
                </div>

                {/* OpenSearch config (conditional) */}
                {needsOpenSearch && (
                  <div style={{
                    background: 'var(--gray-50)',
                    border: '1px solid var(--border)',
                    borderRadius: 'var(--radius)',
                    padding: 'var(--spacing-4)',
                    marginBottom: 'var(--spacing-4)',
                  }}>
                    {/* OS header */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-2)', marginBottom: 'var(--spacing-3)' }}>
                      <Search size={14} style={{ color: 'var(--gray-500)' }} />
                      <span style={{ fontWeight: '600', fontSize: 'var(--text-sm)' }}>OpenSearch index</span>
                      {osHealthOk === null && (
                        <span style={{ fontSize: 'var(--text-xs)', color: 'var(--gray-400)' }}>Checking connection...</span>
                      )}
                      {osHealthOk === true && (
                        <span style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: 'var(--text-xs)', color: 'var(--success)' }}>
                          <CheckCircle size={12} /> Connected
                        </span>
                      )}
                      {osHealthOk === false && (
                        <span style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: 'var(--text-xs)', color: 'var(--danger)' }}>
                          <XCircle size={12} /> Unreachable — check Settings
                        </span>
                      )}
                    </div>

                    {/* Index selector */}
                    <div className="form-group" style={{ marginBottom: 'var(--spacing-2)' }}>
                      <label className="form-label" style={{ fontSize: 'var(--text-xs)' }}>
                        Index name
                        <span style={{ color: 'var(--gray-400)', fontWeight: '400', marginLeft: '4px' }}>
                          — leave empty to auto-generate as <code>project-&lt;id&gt;</code>
                        </span>
                      </label>
                      {osIndices.length > 0 && (
                        <select
                          className="form-input"
                          style={{ marginBottom: 'var(--spacing-2)' }}
                          value={formData.opensearch_index}
                          onChange={e => setFormData({ ...formData, opensearch_index: e.target.value })}
                        >
                          <option value="">— Select existing index —</option>
                          {osIndices.map(idx => (
                            <option key={idx.index} value={idx.index}>
                              {idx.index} ({idx.docs_count || 0} docs)
                            </option>
                          ))}
                        </select>
                      )}
                      <input
                        type="text" className="form-input"
                        placeholder="my-custom-index"
                        value={formData.opensearch_index}
                        onChange={e => setFormData({ ...formData, opensearch_index: e.target.value.toLowerCase().replace(/[^a-z0-9_-]/g, '') })}
                      />
                    </div>

                    {/* Create new index */}
                    <div style={{ display: 'flex', gap: 'var(--spacing-2)', alignItems: 'center' }}>
                      <input
                        type="text" className="form-input" style={{ flex: 1 }}
                        placeholder="new-index-name"
                        value={osIndexInput}
                        onChange={e => setOsIndexInput(e.target.value.toLowerCase().replace(/[^a-z0-9_-]/g, ''))}
                      />
                      <button
                        type="button"
                        onClick={createOsIndex}
                        disabled={creatingIndex || !osIndexInput.trim() || !osHealthOk}
                        style={{
                          display: 'inline-flex', alignItems: 'center', gap: '4px',
                          padding: '7px 12px',
                          border: '1px solid var(--border)',
                          borderRadius: 'var(--radius)',
                          background: 'transparent',
                          fontSize: 'var(--text-xs)', fontWeight: '500',
                          cursor: (creatingIndex || !osIndexInput.trim() || !osHealthOk) ? 'not-allowed' : 'pointer',
                          opacity: (creatingIndex || !osIndexInput.trim() || !osHealthOk) ? 0.5 : 1,
                        }}
                      >
                        {creatingIndex ? <Loader2 size={12} className="animate-spin" /> : <Plus size={12} />}
                        Create index
                      </button>
                    </div>
                    <p style={{ fontSize: 'var(--text-xs)', color: 'var(--gray-400)', marginTop: 'var(--spacing-1)' }}>
                      Creates the index with knn_vector mapping. Skip if it already exists or you want auto-naming.
                    </p>
                  </div>
                )}

                {/* Footer buttons */}
                <div style={{ display: 'flex', gap: 'var(--spacing-3)', justifyContent: 'flex-end', marginTop: 'var(--spacing-6)' }}>
                  <button
                    type="button"
                    onClick={() => { setShowModal(false); resetForm(); }}
                    style={{
                      padding: '8px 18px',
                      border: '1px solid var(--border)',
                      borderRadius: 'var(--radius)',
                      background: 'transparent',
                      fontSize: 'var(--text-sm)', fontWeight: '500',
                      color: 'var(--gray-600)',
                      cursor: 'pointer',
                    }}
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    style={{
                      padding: '8px 20px',
                      border: 'none',
                      borderRadius: 'var(--radius)',
                      background: 'var(--primary)',
                      color: 'white',
                      fontSize: 'var(--text-sm)', fontWeight: '500',
                      cursor: 'pointer',
                    }}
                  >
                    Create project
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* Modal Connect Source */}
        {showSourceModal && selectedProject && (
          <ConnectSourceModal
            projectId={selectedProject.id}
            onClose={() => { setShowSourceModal(false); setSelectedProject(null); }}
            onSuccess={loadProjects}
          />
        )}
      </div>
    </Layout>
  );
};

export default Projects;