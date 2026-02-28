import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Plus, Upload, Trash2, FileText, FolderKanban, MessageSquare,
  Loader2, GitBranch, Folder, RefreshCw, Database, Search, CheckCircle, XCircle
} from 'lucide-react';
import Layout from '../components/layout/Layout';
import Button from '../components/common/Button';
import Loading from '../components/common/Loading';
import Alert from '../components/common/Alert';
import ConnectSourceModal from './ConnectSourceModal';
import api from '../services/api';

// ── Vector store badge helper ─────────────────────────────────────────────────
const VectorStoreBadge = ({ type }) => {
  const config = {
    chroma: { label: 'ChromaDB', color: '#6366f1', bg: 'rgba(99,102,241,0.1)' },
    opensearch: { label: 'OpenSearch', color: '#f59e0b', bg: 'rgba(245,158,11,0.1)' },
    both: { label: 'Chroma + OS', color: '#10b981', bg: 'rgba(16,185,129,0.1)' },
  };
  const c = config[type] || config.chroma;
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: '4px',
      padding: '2px 8px', borderRadius: 'var(--radius-sm)',
      fontSize: 'var(--text-xs)', fontWeight: '600',
      color: c.color, background: c.bg,
      border: `1px solid ${c.color}44`
    }}>
      <Database size={10} />
      {c.label}
    </span>
  );
};

const Projects = () => {
  const navigate = useNavigate();
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [showSourceModal, setShowSourceModal] = useState(false);
  const [selectedProject, setSelectedProject] = useState(null);
  const [uploading, setUploading] = useState({});
  const [syncing, setSyncing] = useState({});
  const [integrations, setIntegrations] = useState({});
  const [alert, setAlert] = useState(null);

  // OpenSearch index state for modal
  const [osIndices, setOsIndices] = useState([]);
  const [osHealthOk, setOsHealthOk] = useState(null); // null=unchecked, true/false
  const [osIndexInput, setOsIndexInput] = useState('');
  const [creatingIndex, setCreatingIndex] = useState(false);

  const [formData, setFormData] = useState({
    name: '',
    description: '',
    chunk_size: 2000,
    chunk_overlap: 200,
    vector_store_type: 'chroma',
    opensearch_index: '',
  });

  useEffect(() => {
    loadProjects();
  }, []);

  // When vector store type changes to opensearch/both, probe health + load indices
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
      await checkOpenSearchHealth(); // refresh list
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

    // Validate: if OS selected but no index specified, auto-generate (backend handles it)
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
        headers: { 'Content-Type': 'multipart/form-data' }
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
          showAlert('success', `✅ Processing complete: ${res.data.chunk_count} chunks`);
          clearInterval(interval);
          loadProjects();
        } else if (res.data.status === 'failed') {
          showAlert('error', `❌ Processing failed: ${res.data.error_message}`);
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
      showAlert('success', `✅ Synced ${res.data.total_documents} documents from external sources`);
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

  return (
    <Layout>
      <div className="container" style={{ padding: 'var(--spacing-8) var(--spacing-4)' }}>
        {alert && (
          <div style={{ marginBottom: 'var(--spacing-4)' }}>
            <Alert type={alert.type} message={alert.message} onClose={() => setAlert(null)} />
          </div>
        )}

        <div className="flex justify-between items-center" style={{ marginBottom: 'var(--spacing-8)' }}>
          <div>
            <h1 style={{ fontSize: 'var(--text-3xl)', fontWeight: '700', marginBottom: 'var(--spacing-2)' }}>
              RAG Projects
            </h1>
            <p style={{ color: 'var(--gray-600)' }}>Manage your document collections and chat with them</p>
          </div>
          <Button variant="primary" icon={Plus} onClick={() => setShowModal(true)}>
            New Project
          </Button>
        </div>

        {projects.length === 0 ? (
          <div className="card" style={{ textAlign: 'center', padding: 'var(--spacing-8)' }}>
            <FolderKanban size={48} style={{ color: 'var(--gray-400)', margin: '0 auto var(--spacing-4)' }} />
            <p style={{ color: 'var(--gray-600)', marginBottom: 'var(--spacing-4)' }}>
              No projects yet. Create your first RAG project!
            </p>
            <Button variant="primary" icon={Plus} onClick={() => setShowModal(true)}>Create First Project</Button>
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 'var(--spacing-4)' }}>
            {projects.map(project => (
              <div key={project.id} className="card" style={{ padding: 'var(--spacing-4)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 'var(--spacing-3)' }}>
                  <div style={{ flex: 1 }}>
                    <h3 style={{ fontWeight: '600', marginBottom: 'var(--spacing-1)' }}>{project.name}</h3>
                    {project.description && (
                      <p style={{ fontSize: 'var(--text-sm)', color: 'var(--gray-600)', marginBottom: 'var(--spacing-2)' }}>
                        {project.description}
                      </p>
                    )}
                    <VectorStoreBadge type={project.vector_store_type || 'chroma'} />
                    {(project.vector_store_type === 'opensearch' || project.vector_store_type === 'both') && project.opensearch_index && (
                      <div style={{ fontSize: 'var(--text-xs)', color: 'var(--gray-500)', marginTop: '4px' }}>
                        Index: <code>{project.opensearch_index}</code>
                      </div>
                    )}
                  </div>
                  <button
                    onClick={() => deleteProject(project.id)}
                    style={{ color: 'var(--error)', background: 'none', border: 'none', cursor: 'pointer', padding: '4px' }}
                  >
                    <Trash2 size={16} />
                  </button>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--spacing-2)', marginBottom: 'var(--spacing-3)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ fontSize: 'var(--text-sm)', color: 'var(--gray-600)' }}>Docs:</span>
                    <span style={{ fontSize: 'var(--text-sm)', fontWeight: '600' }}>{project.document_count}</span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ fontSize: 'var(--text-sm)', color: 'var(--gray-600)' }}>Chunks:</span>
                    <span style={{ fontSize: 'var(--text-sm)', fontWeight: '600' }}>{project.total_chunks}</span>
                  </div>
                </div>

                {/* Connected sources */}
                {integrations[project.id]?.length > 0 && (
                  <div style={{ marginBottom: 'var(--spacing-3)' }}>
                    <div style={{ fontSize: 'var(--text-xs)', color: 'var(--gray-600)', marginBottom: 'var(--spacing-2)' }}>Connected Sources:</div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--spacing-1)' }}>
                      {integrations[project.id].map(integration => (
                        <span key={integration.id} style={{
                          display: 'inline-flex', alignItems: 'center', gap: 'var(--spacing-1)',
                          padding: 'var(--spacing-1) var(--spacing-2)', fontSize: 'var(--text-xs)',
                          backgroundColor: integration.type === 'git' ? 'rgba(251,146,60,0.1)' : 'rgba(34,197,94,0.1)',
                          color: integration.type === 'git' ? 'var(--warning)' : 'var(--success)',
                          borderRadius: 'var(--radius-sm)',
                          border: `1px solid ${integration.type === 'git' ? 'rgba(251,146,60,0.3)' : 'rgba(34,197,94,0.3)'}`
                        }}>
                          {integration.type === 'git' ? <GitBranch size={12} /> : <Folder size={12} />}
                          {integration.name}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Actions Row 1 */}
                <div style={{ display: 'flex', gap: 'var(--spacing-2)', marginBottom: 'var(--spacing-2)' }}>
                  <label className="btn btn-primary btn-sm" style={{ flex: 1 }}>
                    {uploading[project.id] ? (
                      <><Loader2 className="animate-spin" size={16} /> Uploading...</>
                    ) : (
                      <><Upload size={16} /> Upload</>
                    )}
                    <input
                      type="file" hidden
                      accept=".pdf,.docx,.doc,.pptx,.ppt,.txt,.md,.markdown,.html,.htm,.xlsx,.xls,.csv,.rtf,.odt,.ods,.odp,.tex,.epub,.xml,.py,.js,.jsx,.ts,.tsx,.css,.java,.cpp,.c,.cs,.go,.rs,.php,.rb,.swift,.kt,.scala,.r,.groovy,.sh,.bash,.sql,.json,.yaml,.yml,.toml,.ini,.env,.jenkinsfile,.zip,.tar,.gz"
                      onChange={(e) => uploadDocument(project.id, e.target.files[0])}
                      disabled={uploading[project.id]}
                    />
                  </label>
                  <Button variant="ghost" size="sm" onClick={() => navigate(`/projects/${project.id}/documents`)}>
                    <FileText size={16} />
                  </Button>
                  <Button variant="success" size="sm" onClick={() => navigate(`/projects/${project.id}/chat`)}>
                    <MessageSquare size={16} />
                  </Button>
                </div>

                {/* Actions Row 2 */}
                <div style={{ display: 'flex', gap: 'var(--spacing-2)' }}>
                  <button className="btn btn-ghost btn-sm" style={{ flex: 1, fontSize: 'var(--text-xs)' }} onClick={() => openConnectSource(project)}>
                    <GitBranch size={14} /><span>Git / Drive</span>
                  </button>
                  <button className="btn btn-ghost btn-sm" onClick={() => syncExternalSources(project.id)} disabled={syncing[project.id]}>
                    {syncing[project.id] ? <Loader2 className="animate-spin" size={14} /> : <RefreshCw size={14} />}
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* ── Modal: Create Project ──────────────────────────────────────────── */}
        {showModal && (
          <div style={{
            position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.5)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            zIndex: 1000, padding: 'var(--spacing-4)', overflowY: 'auto'
          }}>
            <div className="card" style={{ width: '100%', maxWidth: '640px' }}>
              <h2 style={{ fontSize: 'var(--text-2xl)', fontWeight: '600', marginBottom: 'var(--spacing-6)' }}>
                New RAG Project
              </h2>

              <form onSubmit={createProject}>
                {/* Name */}
                <div className="form-group">
                  <label className="form-label">Project Name</label>
                  <input type="text" className="form-input" value={formData.name}
                    onChange={e => setFormData({ ...formData, name: e.target.value })}
                    required placeholder="e.g., Company Knowledge Base" />
                </div>

                {/* Description */}
                <div className="form-group">
                  <label className="form-label">Description (optional)</label>
                  <textarea className="form-textarea" value={formData.description}
                    onChange={e => setFormData({ ...formData, description: e.target.value })}
                    placeholder="What is this project about?" rows={2} />
                </div>

                {/* Chunk settings */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--spacing-4)' }}>
                  <div className="form-group">
                    <label className="form-label">Chunk Size (tokens)</label>
                    <input type="number" className="form-input" value={formData.chunk_size}
                      onChange={e => setFormData({ ...formData, chunk_size: parseInt(e.target.value) })}
                      min="500" max="8000" />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Chunk Overlap</label>
                    <input type="number" className="form-input" value={formData.chunk_overlap}
                      onChange={e => setFormData({ ...formData, chunk_overlap: parseInt(e.target.value) })}
                      min="0" max="1000" />
                  </div>
                </div>

                {/* ── Vector Store ─────────────────────────────────────────── */}
                <div className="form-group">
                  <label className="form-label">Vector Store</label>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 'var(--spacing-2)', marginTop: 'var(--spacing-2)' }}>
                    {[
                      { value: 'chroma', label: 'ChromaDB', desc: 'Default — local, no extra infra' },
                      { value: 'opensearch', label: 'OpenSearch', desc: 'Scalable, existing cluster' },
                      { value: 'both', label: 'Both', desc: 'Index in both, query ChromaDB' },
                    ].map(opt => (
                      <label key={opt.value} style={{
                        display: 'block', padding: 'var(--spacing-3)',
                        borderRadius: 'var(--radius)', cursor: 'pointer',
                        border: `2px solid ${formData.vector_store_type === opt.value ? 'var(--primary)' : 'var(--border)'}`,
                        background: formData.vector_store_type === opt.value ? 'rgba(99,102,241,0.06)' : 'transparent',
                        transition: 'all 0.15s'
                      }}>
                        <input type="radio" name="vector_store_type" value={opt.value} hidden
                          checked={formData.vector_store_type === opt.value}
                          onChange={e => setFormData({ ...formData, vector_store_type: e.target.value, opensearch_index: '' })} />
                        <div style={{ fontWeight: '600', fontSize: 'var(--text-sm)', marginBottom: '2px' }}>{opt.label}</div>
                        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--gray-500)' }}>{opt.desc}</div>
                      </label>
                    ))}
                  </div>
                </div>

                {/* ── OpenSearch section (conditional) ─────────────────────── */}
                {needsOpenSearch && (
                  <div style={{
                    background: 'var(--gray-50, #f9fafb)', border: '1px solid var(--border)',
                    borderRadius: 'var(--radius)', padding: 'var(--spacing-4)', marginBottom: 'var(--spacing-4)'
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-2)', marginBottom: 'var(--spacing-3)' }}>
                      <Search size={16} style={{ color: 'var(--gray-600)' }} />
                      <span style={{ fontWeight: '600', fontSize: 'var(--text-sm)' }}>OpenSearch Index</span>
                      {/* Connection status indicator */}
                      {osHealthOk === null && (
                        <span style={{ fontSize: 'var(--text-xs)', color: 'var(--gray-400)' }}>Checking...</span>
                      )}
                      {osHealthOk === true && (
                        <span style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: 'var(--text-xs)', color: 'var(--success)' }}>
                          <CheckCircle size={12} /> Connected
                        </span>
                      )}
                      {osHealthOk === false && (
                        <span style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: 'var(--text-xs)', color: 'var(--error)' }}>
                          <XCircle size={12} /> Unreachable — check Settings
                        </span>
                      )}
                    </div>

                    {/* Index selector — pick existing or type a new one */}
                    <div className="form-group" style={{ marginBottom: 'var(--spacing-2)' }}>
                      <label className="form-label" style={{ fontSize: 'var(--text-xs)' }}>
                        Index name
                        <span style={{ color: 'var(--gray-400)', fontWeight: '400', marginLeft: '4px' }}>
                          (leave empty to auto-generate as <code>project-&lt;id&gt;</code>)
                        </span>
                      </label>

                      {/* Existing indices dropdown */}
                      {osIndices.length > 0 && (
                        <select className="form-input" style={{ marginBottom: 'var(--spacing-2)' }}
                          value={formData.opensearch_index}
                          onChange={e => setFormData({ ...formData, opensearch_index: e.target.value })}>
                          <option value="">— Select existing index —</option>
                          {osIndices.map(idx => (
                            <option key={idx.index} value={idx.index}>
                              {idx.index} ({idx.docs_count || 0} docs)
                            </option>
                          ))}
                        </select>
                      )}

                      <input type="text" className="form-input" placeholder="my-custom-index"
                        value={formData.opensearch_index}
                        onChange={e => setFormData({ ...formData, opensearch_index: e.target.value.toLowerCase().replace(/[^a-z0-9_\-]/g, '') })} />
                    </div>

                    {/* Create index button */}
                    <div style={{ display: 'flex', gap: 'var(--spacing-2)', alignItems: 'center' }}>
                      <input type="text" className="form-input" style={{ flex: 1 }}
                        placeholder="new-index-name"
                        value={osIndexInput}
                        onChange={e => setOsIndexInput(e.target.value.toLowerCase().replace(/[^a-z0-9_\-]/g, ''))} />
                      <Button
                        type="button" variant="ghost" size="sm"
                        onClick={createOsIndex}
                        disabled={creatingIndex || !osIndexInput.trim() || !osHealthOk}>
                        {creatingIndex ? <Loader2 size={14} className="animate-spin" /> : <Plus size={14} />}
                        Create Index
                      </Button>
                    </div>
                    <p style={{ fontSize: 'var(--text-xs)', color: 'var(--gray-400)', marginTop: 'var(--spacing-1)' }}>
                      Creates the index with knn_vector mapping. Skip if the index already exists or you want auto-naming.
                    </p>
                  </div>
                )}

                <div style={{ display: 'flex', gap: 'var(--spacing-3)', justifyContent: 'flex-end', marginTop: 'var(--spacing-6)' }}>
                  <Button variant="ghost" type="button" onClick={() => { setShowModal(false); resetForm(); }}>Cancel</Button>
                  <Button type="submit" variant="primary">Create Project</Button>
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