import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Plus, Upload, Trash2, FileText, FolderKanban, MessageSquare, Loader2, GitBranch, Folder, RefreshCw } from 'lucide-react';
import Layout from '../components/layout/Layout';
import Button from '../components/common/Button';
import Loading from '../components/common/Loading';
import Alert from '../components/common/Alert';
import ConnectSourceModal from './ConnectSourceModal';
import api from '../services/api';

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

  const [formData, setFormData] = useState({
    name: '',
    description: '',
    chunk_size: 2000,
    chunk_overlap: 200
  });

  useEffect(() => {
    loadProjects();
  }, []);

  const loadProjects = async () => {
    try {
      const res = await api.get('/api/projects/');
      setProjects(res.data);
      
      // ✅ Charger les intégrations pour chaque projet
      const integrationsData = {};
      for (const project of res.data) {
        try {
          const intRes = await api.get(`/api/integrations/projects/${project.id}/sources`);
          integrationsData[project.id] = intRes.data || [];
        } catch (err) {
          console.error(`Failed to load integrations for project ${project.id}:`, err);
          integrationsData[project.id] = [];
        }
      }
      setIntegrations(integrationsData);
      
    } catch (error) {
      showAlert('error', 'Failed to load projects');
    } finally {
      setLoading(false);
    }
  };

  const createProject = async (e) => {
    e.preventDefault();
    try {
      await api.post('/api/projects/', formData);
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
    } catch (error) {
      showAlert('error', 'Failed to delete project');
    }
  };

  const uploadDocument = async (projectId, file) => {
    setUploading(prev => ({ ...prev, [projectId]: true }));

    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await api.post(`/api/documents/${projectId}/upload`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      
      showAlert('success', `Document uploaded: ${res.data.filename}`);
      
      // Poll status
      pollDocumentStatus(res.data.document_id);
    } catch (error) {
      showAlert('error', error.response?.data?.detail || 'Upload failed');
    } finally {
      setUploading(prev => ({ ...prev, [projectId]: false }));
    }
  };

  const pollDocumentStatus = async (documentId) => {
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
      } catch (error) {
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
      const res = await api.post('/api/integrations/sync', {
        domain: projectId.toString()
      });

      showAlert('success', `✅ Synced ${res.data.total_documents} documents from external sources`);
      loadProjects();
    } catch (error) {
      showAlert('error', 'Sync failed: ' + (error.response?.data?.detail || error.message));
    } finally {
      setSyncing(prev => ({ ...prev, [projectId]: false }));
    }
  };

  const viewDocuments = (project) => {
    navigate(`/projects/${project.id}/documents`);
  };

  const startChat = (project) => {
    navigate(`/projects/${project.id}/chat`);
  };

  const resetForm = () => {
    setFormData({
      name: '',
      description: '',
      chunk_size: 2000,
      chunk_overlap: 200
    });
  };

  const showAlert = (type, message) => {
    setAlert({ type, message });
    setTimeout(() => setAlert(null), 5000);
  };

  if (loading) {
    return (
      <Layout>
        <Loading message="Loading projects..." />
      </Layout>
    );
  }

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
            <p style={{ color: 'var(--gray-600)' }}>
              Manage your document collections and chat with them
            </p>
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
            <Button variant="primary" icon={Plus} onClick={() => setShowModal(true)}>
              Create First Project
            </Button>
          </div>
        ) : (
          <div className="grid grid-cols-3">
            {projects.map((project) => (
              <div key={project.id} className="card">
                <div className="flex justify-between items-start" style={{ marginBottom: 'var(--spacing-3)' }}>
                  <div>
                    <h3 style={{ fontWeight: '600', marginBottom: 'var(--spacing-1)' }}>
                      {project.name}
                    </h3>
                    {project.description && (
                      <p style={{ fontSize: 'var(--text-sm)', color: 'var(--gray-600)' }}>
                        {project.description}
                      </p>
                    )}
                  </div>
                  <button
                    className="btn btn-ghost btn-sm"
                    onClick={() => deleteProject(project.id)}
                  >
                    <Trash2 size={16} />
                  </button>
                </div>

                <div style={{ 
                  padding: 'var(--spacing-3)', 
                  backgroundColor: 'var(--gray-50)', 
                  borderRadius: 'var(--radius)',
                  marginBottom: 'var(--spacing-3)'
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 'var(--spacing-2)' }}>
                    <span style={{ fontSize: 'var(--text-sm)', color: 'var(--gray-600)' }}>Documents:</span>
                    <span style={{ fontSize: 'var(--text-sm)', fontWeight: '600' }}>{project.document_count}</span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ fontSize: 'var(--text-sm)', color: 'var(--gray-600)' }}>Chunks:</span>
                    <span style={{ fontSize: 'var(--text-sm)', fontWeight: '600' }}>{project.total_chunks}</span>
                  </div>
                </div>

                {/* ✅ Afficher les intégrations Git/Drive */}
                {integrations[project.id] && integrations[project.id].length > 0 && (
                  <div style={{ marginBottom: 'var(--spacing-3)' }}>
                    <div style={{ fontSize: 'var(--text-xs)', color: 'var(--gray-600)', marginBottom: 'var(--spacing-2)' }}>
                      Connected Sources:
                    </div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--spacing-1)' }}>
                      {integrations[project.id].map((integration) => (
                        <span
                          key={integration.id}
                          style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: 'var(--spacing-1)',
                            padding: 'var(--spacing-1) var(--spacing-2)',
                            fontSize: 'var(--text-xs)',
                            backgroundColor: integration.type === 'git' ? 'rgba(251, 146, 60, 0.1)' : 'rgba(34, 197, 94, 0.1)',
                            color: integration.type === 'git' ? 'var(--warning)' : 'var(--success)',
                            borderRadius: 'var(--radius-sm)',
                            border: `1px solid ${integration.type === 'git' ? 'rgba(251, 146, 60, 0.3)' : 'rgba(34, 197, 94, 0.3)'}`
                          }}
                        >
                          {integration.type === 'git' ? <GitBranch size={12} /> : <Folder size={12} />}
                          {integration.name}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Actions Row 1: Upload + View + Chat */}
                <div style={{ display: 'flex', gap: 'var(--spacing-2)', marginBottom: 'var(--spacing-2)' }}>
                  <label className="btn btn-primary btn-sm" style={{ flex: 1 }}>
                    {uploading[project.id] ? (
                      <>
                        <Loader2 className="animate-spin" size={16} />
                        Uploading...
                      </>
                    ) : (
                      <>
                        <Upload size={16} />
                        Upload
                      </>
                    )}
                    <input
                      type="file"
                      hidden
                      accept=".pdf,.docx,.doc,.pptx,.ppt,.txt,.md,.markdown,.html,.htm,.xlsx,.xls,.csv,.rtf,.odt,.ods,.odp,.tex,.epub,.xml,.py,.js,.jsx,.ts,.tsx,.css,.java,.cpp,.c,.cs,.go,.rs,.php,.rb,.swift,.kt,.scala,.r,.groovy,.sh,.bash,.sql,.json,.yaml,.yml,.toml,.ini,.env,.jenkinsfile,.zip,.tar,.gz"
                      onChange={(e) => uploadDocument(project.id, e.target.files[0])}
                      disabled={uploading[project.id]}
                    />
                  </label>
                  
                  <Button 
                    variant="ghost" 
                    size="sm" 
                    onClick={() => viewDocuments(project)}
                  >
                    <FileText size={16} />
                  </Button>
                  
                  <Button 
                    variant="success" 
                    size="sm" 
                    onClick={() => startChat(project)}
                  >
                    <MessageSquare size={16} />
                  </Button>
                </div>

                {/* Actions Row 2: External Sources */}
                <div style={{ display: 'flex', gap: 'var(--spacing-2)' }}>
                  <button
                    className="btn btn-ghost btn-sm"
                    style={{ flex: 1, fontSize: 'var(--text-xs)' }}
                    onClick={() => openConnectSource(project)}
                  >
                    <GitBranch size={14} />
                    <span>Git / Drive</span>
                  </button>
                  
                  <button
                    className="btn btn-ghost btn-sm"
                    onClick={() => syncExternalSources(project.id)}
                    disabled={syncing[project.id]}
                  >
                    {syncing[project.id] ? (
                      <Loader2 className="animate-spin" size={14} />
                    ) : (
                      <RefreshCw size={14} />
                    )}
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Modal Create Project */}
        {showModal && (
          <div style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.5)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
            padding: 'var(--spacing-4)'
          }}>
            <div className="card" style={{ width: '100%', maxWidth: '600px' }}>
              <h2 style={{ fontSize: 'var(--text-2xl)', fontWeight: '600', marginBottom: 'var(--spacing-6)' }}>
                New RAG Project
              </h2>

              <form onSubmit={createProject}>
                <div className="form-group">
                  <label className="form-label">Project Name</label>
                  <input
                    type="text"
                    className="form-input"
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    required
                    placeholder="e.g., Company Knowledge Base"
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">Description (optional)</label>
                  <textarea
                    className="form-textarea"
                    value={formData.description}
                    onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                    placeholder="What is this project about?"
                    rows={3}
                  />
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--spacing-4)' }}>
                  <div className="form-group">
                    <label className="form-label">Chunk Size (tokens)</label>
                    <input
                      type="number"
                      className="form-input"
                      value={formData.chunk_size}
                      onChange={(e) => setFormData({ ...formData, chunk_size: parseInt(e.target.value) })}
                      min="500"
                      max="8000"
                    />
                  </div>

                  <div className="form-group">
                    <label className="form-label">Chunk Overlap</label>
                    <input
                      type="number"
                      className="form-input"
                      value={formData.chunk_overlap}
                      onChange={(e) => setFormData({ ...formData, chunk_overlap: parseInt(e.target.value) })}
                      min="0"
                      max="1000"
                    />
                  </div>
                </div>

                <div style={{ display: 'flex', gap: 'var(--spacing-3)', justifyContent: 'flex-end', marginTop: 'var(--spacing-6)' }}>
                  <Button 
                    variant="ghost" 
                    onClick={() => {
                      setShowModal(false);
                      resetForm();
                    }}
                  >
                    Cancel
                  </Button>
                  <Button type="submit" variant="primary">
                    Create Project
                  </Button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* Modal Connect Source */}
        {showSourceModal && selectedProject && (
          <ConnectSourceModal
            projectId={selectedProject.id}
            onClose={() => {
              setShowSourceModal(false);
              setSelectedProject(null);
            }}
            onSuccess={loadProjects}
          />
        )}
      </div>
    </Layout>
  );
};

export default Projects;