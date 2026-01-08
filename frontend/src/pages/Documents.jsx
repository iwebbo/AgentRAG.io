import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Trash2, FileText, Upload, AlertCircle, ArrowLeft, GitBranch, Folder, RefreshCw, ExternalLink } from 'lucide-react';
import Layout from '../components/layout/Layout';
import Alert from '../components/common/Alert';
import ConnectSourceModal from './ConnectSourceModal';
import api from '../services/api';

const Documents = () => {
  const { projectId } = useParams();
  const navigate = useNavigate();
  const [documents, setDocuments] = useState([]);
  const [project, setProject] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [uploading, setUploading] = useState(false);
  const [uploadSuccess, setUploadSuccess] = useState('');
  const [showSourceModal, setShowSourceModal] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [connectedSources, setConnectedSources] = useState([]);

  useEffect(() => {
    if (projectId) {
      fetchProjectAndDocuments();
      loadConnectedSources();
    } else {
      fetchDocuments();
    }
  }, [projectId]);

  const fetchProjectAndDocuments = async () => {
    setLoading(true);
    try {
      const projectRes = await api.get(`/api/projects/${projectId}`);
      setProject(projectRes.data);

      const docsRes = await api.get(`/api/documents/projects/${projectId}/documents`);
      setDocuments(Array.isArray(docsRes.data) ? docsRes.data : []);
      setError('');
    } catch (err) {
      console.error('Error loading documents:', err);
      setError('Erreur lors du chargement des documents');
      setDocuments([]);
    } finally {
      setLoading(false);
    }
  };

  const fetchDocuments = async () => {
    setLoading(true);
    try {
      const response = await api.get('/documents');
      setDocuments(Array.isArray(response.data) ? response.data : []);
      setError('');
    } catch (err) {
      console.error('Error loading documents:', err);
      setError('Erreur lors du chargement des documents');
      setDocuments([]);
    } finally {
      setLoading(false);
    }
  };

  const loadConnectedSources = async () => {
    if (!projectId) return;
    
    try {
      const res = await api.get(`/api/integrations/projects/${projectId}/sources`);
      setConnectedSources(res.data || []);
    } catch (err) {
      console.error('Failed to load sources:', err);
      setConnectedSources([]);
    }
  };

  const syncExternalSources = async () => {
    if (!projectId) return;
    
    setSyncing(true);
    setError('');
    setUploadSuccess('');

    try {
      const res = await api.post('/api/integrations/sync', {
        domain: projectId.toString()
      });

      setUploadSuccess(`✅ Synced ${res.data.total_documents} documents from external sources`);
      await fetchProjectAndDocuments();
    } catch (err) {
      setError('Sync failed: ' + (err.response?.data?.detail || err.message));
    } finally {
      setSyncing(false);
    }
  };

  const handleUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    setUploading(true);
    setError('');
    setUploadSuccess('');

    try {
      const endpoint = projectId 
        ? `/api/documents/${projectId}/upload`
        : '/api/documents/upload';
      
      const res = await api.post(endpoint, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      
      setUploadSuccess(`Document "${file.name}" téléchargé - traitement en cours...`);
      
      // Poll status comme dans Projects.jsx
      pollDocumentStatus(res.data.document_id);
    } catch (err) {
      console.error('Upload error:', err);
      setError(err.response?.data?.detail || 'Erreur lors de l\'upload');
    } finally {
      setUploading(false);
      e.target.value = '';
    }
  };

  const pollDocumentStatus = async (documentId) => {
    const interval = setInterval(async () => {
      try {
        const res = await api.get(`/api/documents/${documentId}/status`);
        
        if (res.data.status === 'completed') {
          setUploadSuccess(`✅ Processing complete: ${res.data.chunk_count} chunks`);
          clearInterval(interval);
          
          // Recharger les documents
          if (projectId) {
            fetchProjectAndDocuments();
          } else {
            fetchDocuments();
          }
        } else if (res.data.status === 'failed') {
          setError(`❌ Processing failed: ${res.data.error_message}`);
          clearInterval(interval);
        }
      } catch (error) {
        clearInterval(interval);
      }
    }, 2000);
  };

  const handleDelete = async (docId) => {
    if (!window.confirm('Supprimer ce document ?')) return;

    try {
      const endpoint = projectId
        ? `/api/documents/projects/${projectId}/documents/${docId}`
        : `/api/documents/${docId}`;
      
      await api.delete(endpoint);
      setDocuments(documents.filter(d => d.id !== docId));
      setUploadSuccess('Document supprimé');
    } catch (err) {
      console.error('Delete error:', err);
      setError('Erreur lors de la suppression: ' + (err.response?.data?.detail || err.message));
    }
  };

  const deleteIntegration = async (integrationId, integrationName) => {
    if (!window.confirm(`Delete integration "${integrationName}"? This will not delete the documents already synced.`)) return;

    try {
      await api.delete(`/api/integrations/integrations/${integrationId}`);
      setUploadSuccess(`Integration "${integrationName}" deleted`);
      loadConnectedSources();
    } catch (err) {
      console.error('Delete integration error:', err);
      setError('Failed to delete integration: ' + (err.response?.data?.detail || err.message));
    }
  };

  const resyncIntegration = async (integrationName) => {
    setSyncing(true);
    setError('');
    setUploadSuccess('');

    try {
      const res = await api.post('/api/integrations/sync', {
        domain: projectId.toString(),
        sources: [integrationName]
      });

      setUploadSuccess(`✅ Synced ${res.data.total_documents} documents from "${integrationName}"`);
      await fetchProjectAndDocuments();
    } catch (err) {
      setError('Sync failed: ' + (err.response?.data?.detail || err.message));
    } finally {
      setSyncing(false);
    }
  };

  const formatFileSize = (bytes) => {
    if (!bytes) return '0 B';
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  };

  const getFileTypeBadge = (type) => {
    const badges = {
      pdf: { bg: 'var(--danger)', text: 'PDF' },
      txt: { bg: 'var(--info)', text: 'TXT' },
      md: { bg: 'var(--warning)', text: 'MD' },
      doc: { bg: 'var(--success)', text: 'DOC' },
      docx: { bg: 'var(--success)', text: 'DOCX' }
    };
    const badge = badges[type?.toLowerCase()] || { bg: 'var(--gray-400)', text: 'FILE' };
    return (
      <span 
        className="badge" 
        style={{ 
          background: badge.bg,
          color: 'white',
          padding: 'var(--spacing-1) var(--spacing-2)',
          borderRadius: 'var(--radius)',
          fontSize: 'var(--text-xs)',
          fontWeight: '600'
        }}
      >
        {badge.text}
      </span>
    );
  };

  const getSourceBadge = (source) => {
    if (!source || source === 'upload') return null;
    
    const badges = {
      git: { icon: <GitBranch size={12} />, bg: 'var(--warning)', text: 'Git' },
      gdrive: { icon: <Folder size={12} />, bg: 'var(--success)', text: 'Drive' }
    };

    const badge = badges[source] || { icon: <ExternalLink size={12} />, bg: 'var(--info)', text: source };
    
    return (
      <span 
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 'var(--spacing-1)',
          background: badge.bg,
          color: 'white',
          padding: 'var(--spacing-1) var(--spacing-2)',
          borderRadius: 'var(--radius)',
          fontSize: 'var(--text-xs)',
          fontWeight: '600'
        }}
      >
        {badge.icon}
        {badge.text}
      </span>
    );
  };

  return (
    <Layout>
      <div className="container" style={{ paddingTop: 'var(--spacing-6)', paddingBottom: 'var(--spacing-6)' }}>
        {/* Header */}
        <div style={{ marginBottom: 'var(--spacing-6)' }}>
          {projectId && (
            <button
              onClick={() => navigate('/projects')}
              className="btn btn-ghost"
            >
              <ArrowLeft size={16} />
              Retour aux projets
            </button>
          )}

          <div className="flex justify-between items-center">
            <div>
              <h1 style={{ 
                fontSize: 'var(--text-3xl)', 
                fontWeight: '700',
                color: 'var(--text-primary)',
                marginBottom: 'var(--spacing-2)'
              }}>
                {projectId && project 
                  ? `Documents - ${project.name}`
                  : 'Documents'
                }
              </h1>
              <p style={{ 
                fontSize: 'var(--text-sm)', 
                color: 'var(--text-secondary)'
              }}>
                {documents.length} document{documents.length > 1 ? 's' : ''} indexé{documents.length > 1 ? 's' : ''}
              </p>
            </div>

            <div style={{ display: 'flex', gap: 'var(--spacing-2)' }}>
              {projectId && (
                <>
                  <button 
                    className="btn btn-ghost"
                    onClick={() => setShowSourceModal(true)}
                  >
                    <GitBranch size={16} />
                    Connect Source
                  </button>
                  
                  <button
                    className="btn btn-ghost"
                    onClick={syncExternalSources}
                    disabled={syncing}
                  >
                    <RefreshCw size={16} className={syncing ? 'animate-spin' : ''} />
                    {syncing ? 'Syncing...' : 'Sync'}
                  </button>
                </>
              )}

              <label className="btn btn-primary" style={{ cursor: 'pointer' }}>
                {uploading ? (
                  <>
                    <Upload size={16} />
                    Uploading...
                  </>
                ) : (
                  <>
                    <Upload size={16} />
                    Upload Document
                  </>
                )}
                <input
                  type="file"
                  hidden
                  accept=".pdf,.docx,.doc,.pptx,.ppt,.txt,.md,.markdown,.html,.htm,.xlsx,.xls,.csv,.rtf,.odt,.ods,.odp,.tex,.epub,.xml,.py,.js,.jsx,.ts,.tsx,.css,.java,.cpp,.c,.cs,.go,.rs,.php,.rb,.swift,.kt,.scala,.r,.groovy,.sh,.bash,.sql,.json,.yaml,.yml,.toml,.ini,.env,.jenkinsfile,.zip,.tar,.gz"
                  onChange={handleUpload}
                  disabled={uploading}
                />
              </label>
            </div>
          </div>

          {/* Connected Sources */}
          {projectId && connectedSources.length > 0 && (
            <div style={{ marginTop: 'var(--spacing-4)' }}>
              <h3 style={{ 
                fontSize: 'var(--text-sm)', 
                fontWeight: '600', 
                marginBottom: 'var(--spacing-3)',
                color: 'var(--text-secondary)'
              }}>
                Connected Sources ({connectedSources.length})
              </h3>
              
              <div className="grid grid-cols-3" style={{ gap: 'var(--spacing-3)' }}>
                {connectedSources.map((source) => (
                  <div key={source.id} className="card">
                    <div style={{ 
                      display: 'flex', 
                      alignItems: 'center', 
                      justifyContent: 'space-between',
                      marginBottom: 'var(--spacing-2)'
                    }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-2)' }}>
                        {source.type === 'git' ? (
                          <GitBranch size={16} style={{ color: 'var(--warning)' }} />
                        ) : (
                          <Folder size={16} style={{ color: 'var(--success)' }} />
                        )}
                        <span style={{ fontWeight: '600' }}>{source.name}</span>
                      </div>
                      
                      <span 
                        className="badge"
                        style={{
                          fontSize: 'var(--text-xs)',
                          padding: 'var(--spacing-1) var(--spacing-2)',
                          background: source.type === 'git' ? 'var(--warning)' : 'var(--success)',
                          color: 'white',
                          borderRadius: 'var(--radius-sm)'
                        }}
                      >
                        {source.type}
                      </span>
                    </div>

                    {source.last_sync && (
                      <p style={{ 
                        fontSize: 'var(--text-xs)', 
                        color: 'var(--text-secondary)',
                        marginBottom: 'var(--spacing-3)'
                      }}>
                        Last sync: {new Date(source.last_sync).toLocaleString()}
                      </p>
                    )}

                    <div style={{ display: 'flex', gap: 'var(--spacing-2)' }}>
                      <button
                        className="btn btn-ghost btn-sm"
                        onClick={() => resyncIntegration(source.name)}
                        disabled={syncing}
                        style={{ flex: 1 }}
                      >
                        <RefreshCw size={14} className={syncing ? 'animate-spin' : ''} />
                        Sync
                      </button>
                      <button
                        className="btn btn-ghost btn-sm"
                        onClick={() => deleteIntegration(source.id, source.name)}
                        style={{ color: 'var(--danger)' }}
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Alerts */}
        {error && (
          <Alert type="error" style={{ marginBottom: 'var(--spacing-4)' }} onClose={() => setError('')}>
            {error}
          </Alert>
        )}
        {uploadSuccess && (
          <Alert type="success" style={{ marginBottom: 'var(--spacing-4)' }} onClose={() => setUploadSuccess('')}>
            {uploadSuccess}
          </Alert>
        )}

        {/* Documents List */}
        {loading ? (
          <div className="card" style={{ textAlign: 'center', padding: 'var(--spacing-8)' }}>
            <p style={{ color: 'var(--text-secondary)' }}>Chargement...</p>
          </div>
        ) : documents.length === 0 ? (
          <div className="card" style={{ textAlign: 'center', padding: 'var(--spacing-8)' }}>
            <FileText size={48} style={{ color: 'var(--gray-400)', margin: '0 auto var(--spacing-4)' }} />
            <p style={{ color: 'var(--text-secondary)', marginBottom: 'var(--spacing-4)' }}>
              Aucun document dans ce projet
            </p>
            <label className="btn btn-primary" style={{ cursor: 'pointer' }}>
              {uploading ? (
                <>
                  <Upload size={16} />
                  Uploading...
                </>
              ) : (
                <>
                  <Upload size={16} />
                  Upload un document
                </>
              )}
              <input
                type="file"
                hidden
                accept=".pdf,.docx,.doc,.pptx,.ppt,.txt,.md,.markdown,.html,.htm,.xlsx,.xls,.csv,.rtf,.odt,.ods,.odp,.tex,.epub,.xml,.py,.js,.jsx,.ts,.tsx,.css,.java,.cpp,.c,.cs,.go,.rs,.php,.rb,.swift,.kt,.scala,.r,.groovy,.sh,.bash,.sql,.json,.yaml,.yml,.toml,.ini,.env,.jenkinsfile,.zip,.tar,.gz"
                onChange={handleUpload}
                disabled={uploading}
              />
            </label>
          </div>
        ) : (
          <div className="card" style={{ padding: '0', overflow: 'hidden' }}>
            <div style={{ overflowX: 'auto' }}>
              <table className="table">
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--border-color)' }}>
                    <th style={{ 
                      padding: 'var(--spacing-3) var(--spacing-4)',
                      textAlign: 'left',
                      fontSize: 'var(--text-xs)',
                      fontWeight: '600',
                      color: 'var(--text-secondary)',
                      textTransform: 'uppercase',
                      letterSpacing: '0.05em'
                    }}>
                      Document
                    </th>
                    <th style={{ 
                      padding: 'var(--spacing-3) var(--spacing-4)',
                      textAlign: 'left',
                      fontSize: 'var(--text-xs)',
                      fontWeight: '600',
                      color: 'var(--text-secondary)',
                      textTransform: 'uppercase',
                      letterSpacing: '0.05em'
                    }}>
                      Type
                    </th>
                    <th style={{ 
                      padding: 'var(--spacing-3) var(--spacing-4)',
                      textAlign: 'left',
                      fontSize: 'var(--text-xs)',
                      fontWeight: '600',
                      color: 'var(--text-secondary)',
                      textTransform: 'uppercase',
                      letterSpacing: '0.05em'
                    }}>
                      Source
                    </th>
                    <th style={{ 
                      padding: 'var(--spacing-3) var(--spacing-4)',
                      textAlign: 'left',
                      fontSize: 'var(--text-xs)',
                      fontWeight: '600',
                      color: 'var(--text-secondary)',
                      textTransform: 'uppercase',
                      letterSpacing: '0.05em'
                    }}>
                      Taille
                    </th>
                    <th style={{ 
                      padding: 'var(--spacing-3) var(--spacing-4)',
                      textAlign: 'left',
                      fontSize: 'var(--text-xs)',
                      fontWeight: '600',
                      color: 'var(--text-secondary)',
                      textTransform: 'uppercase',
                      letterSpacing: '0.05em'
                    }}>
                      Chunks
                    </th>
                    <th style={{ 
                      padding: 'var(--spacing-3) var(--spacing-4)',
                      textAlign: 'left',
                      fontSize: 'var(--text-xs)',
                      fontWeight: '600',
                      color: 'var(--text-secondary)',
                      textTransform: 'uppercase',
                      letterSpacing: '0.05em'
                    }}>
                      Date
                    </th>
                    <th style={{ 
                      padding: 'var(--spacing-3) var(--spacing-4)',
                      textAlign: 'right',
                      fontSize: 'var(--text-xs)',
                      fontWeight: '600',
                      color: 'var(--text-secondary)',
                      textTransform: 'uppercase',
                      letterSpacing: '0.05em'
                    }}>
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {documents.map((doc) => (
                    <tr 
                      key={doc.id}
                      style={{ 
                        borderBottom: '1px solid var(--border-color)',
                        transition: 'background-color 0.2s'
                      }}
                      onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--gray-100)'}
                      onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
                    >
                      <td style={{ padding: 'var(--spacing-4)' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-2)' }}>
                          <FileText size={16} style={{ color: 'var(--text-secondary)' }} />
                          <span style={{ 
                            fontSize: 'var(--text-sm)',
                            fontWeight: '500',
                            color: 'var(--text-primary)'
                          }}>
                            {doc.filename || 'Sans nom'}
                          </span>
                        </div>
                      </td>
                      <td style={{ padding: 'var(--spacing-4)' }}>
                        {getFileTypeBadge(doc.file_type)}
                      </td>
                      <td style={{ padding: 'var(--spacing-4)' }}>
                        {getSourceBadge(doc.source)}
                      </td>
                      <td style={{ 
                        padding: 'var(--spacing-4)',
                        fontSize: 'var(--text-sm)',
                        color: 'var(--text-secondary)'
                      }}>
                        {formatFileSize(doc.file_size)}
                      </td>
                      <td style={{ padding: 'var(--spacing-4)' }}>
                        <span className="badge" style={{
                          background: 'var(--gray-200)',
                          color: 'var(--text-primary)',
                          padding: 'var(--spacing-1) var(--spacing-2)',
                          borderRadius: 'var(--radius)',
                          fontSize: 'var(--text-xs)',
                          fontWeight: '600'
                        }}>
                          {doc.chunk_count || 0}
                        </span>
                      </td>
                      <td style={{ 
                        padding: 'var(--spacing-4)',
                        fontSize: 'var(--text-sm)',
                        color: 'var(--text-secondary)'
                      }}>
                        {doc.created_at ? new Date(doc.created_at).toLocaleDateString('fr-FR') : '-'}
                      </td>
                      <td style={{ padding: 'var(--spacing-4)', textAlign: 'right' }}>
                        <button
                          onClick={() => handleDelete(doc.id)}
                          className="btn-ghost btn-sm"
                          style={{ color: 'var(--danger)' }}
                          title="Supprimer"
                        >
                          <Trash2 size={16} />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Info Box */}
        <div className="card" style={{ 
          marginTop: 'var(--spacing-6)',
          background: 'rgba(96, 165, 250, 0.05)',
          border: '1px solid rgba(96, 165, 250, 0.2)'
        }}>
          <div className="flex gap-4">
            <div style={{
              width: '32px',
              height: '32px',
              borderRadius: 'var(--radius-lg)',
              background: 'rgba(96, 165, 250, 0.1)',
              border: '1px solid rgba(96, 165, 250, 0.2)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: '0'
            }}>
              <AlertCircle size={16} style={{ color: 'var(--primary)' }} />
            </div>
            <div style={{ fontSize: 'var(--text-sm)' }}>
              <p style={{ 
                fontWeight: '600',
                color: 'var(--text-primary)',
                marginBottom: 'var(--spacing-1)'
              }}>
                Sources de documents
              </p>
              <p style={{ color: 'var(--text-secondary)' }}>
                <strong>Upload manuel:</strong> PDF, TXT, Markdown, Word
              </p>
              <p style={{ 
                color: 'var(--text-secondary)',
                marginTop: 'var(--spacing-2)'
              }}>
                <strong>Sources externes:</strong> Connectez Git ou Google Drive pour synchroniser automatiquement vos documents
              </p>
            </div>
          </div>
        </div>

        {/* Modal Connect Source */}
        {showSourceModal && projectId && (
          <ConnectSourceModal
            projectId={projectId}
            onClose={() => setShowSourceModal(false)}
            onSuccess={() => {
              fetchProjectAndDocuments();
              loadConnectedSources();
            }}
          />
        )}
      </div>
    </Layout>
  );
};

export default Documents;