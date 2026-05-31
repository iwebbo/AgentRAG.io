import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Trash2, FileText, Upload, ArrowLeft,
  GitBranch, Folder, RefreshCw, ExternalLink,
  X, Check, AlertCircle, Loader2
} from 'lucide-react';
import Layout from '../components/layout/Layout';
import Alert from '../components/common/Alert';
import Loading from '../components/common/Loading';
import ConnectSourceModal from './ConnectSourceModal';
import api from '../services/api';

// ── File type config ──────────────────────────────────────────────────────────
const FILE_TYPE_CONFIG = {
  pdf:        { label: 'PDF',      bg: '#FCEBEB', color: '#791F1F' },
  txt:        { label: 'TXT',      bg: '#E6F1FB', color: '#0C447C' },
  md:         { label: 'MD',       bg: '#E6F1FB', color: '#0C447C' },
  markdown:   { label: 'MD',       bg: '#E6F1FB', color: '#0C447C' },
  docx:       { label: 'DOC',      bg: '#EEEDFE', color: '#3C3489' },
  doc:        { label: 'DOC',      bg: '#EEEDFE', color: '#3C3489' },
  xlsx:       { label: 'XLS',      bg: '#EAF3DE', color: '#27500A' },
  xls:        { label: 'XLS',      bg: '#EAF3DE', color: '#27500A' },
  csv:        { label: 'CSV',      bg: '#EAF3DE', color: '#27500A' },
  pptx:       { label: 'PPT',      bg: '#FAEEDA', color: '#633806' },
  ppt:        { label: 'PPT',      bg: '#FAEEDA', color: '#633806' },
  html:       { label: 'HTML',     bg: '#FAEEDA', color: '#633806' },
  py:         { label: 'PY',       bg: '#E1F5EE', color: '#085041' },
  js:         { label: 'JS',       bg: '#E1F5EE', color: '#085041' },
  jsx:        { label: 'JSX',      bg: '#E1F5EE', color: '#085041' },
  ts:         { label: 'TS',       bg: '#E1F5EE', color: '#085041' },
  tsx:        { label: 'TSX',      bg: '#E1F5EE', color: '#085041' },
  json:       { label: 'JSON',     bg: '#E1F5EE', color: '#085041' },
  yaml:       { label: 'YAML',     bg: '#E1F5EE', color: '#085041' },
  yml:        { label: 'YAML',     bg: '#E1F5EE', color: '#085041' },
};

const FILE_TYPE_LABELS = {
  pdf: 'PDF', txt: 'Text', md: 'Markdown', markdown: 'Markdown',
  docx: 'Word', doc: 'Word', xlsx: 'Excel', xls: 'Excel',
  csv: 'CSV', pptx: 'PowerPoint', ppt: 'PowerPoint',
  html: 'HTML', py: 'Python', js: 'JavaScript', jsx: 'React',
  ts: 'TypeScript', tsx: 'React TS', json: 'JSON', yaml: 'YAML', yml: 'YAML',
};

// ── Helpers ───────────────────────────────────────────────────────────────────
const formatFileSize = (bytes) => {
  if (!bytes) return '—';
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
};

const formatDate = (dateStr) => {
  if (!dateStr) return '—';
  return new Date(dateStr).toLocaleDateString('fr-FR');
};

const getFileExt = (filename, fileType) => {
  if (fileType) return fileType.toLowerCase();
  if (!filename) return 'file';
  return filename.split('.').pop()?.toLowerCase() || 'file';
};

// ── Sub-components ────────────────────────────────────────────────────────────

const FileTypeIcon = ({ filename, fileType }) => {
  const ext = getFileExt(filename, fileType);
  const cfg = FILE_TYPE_CONFIG[ext] || { label: 'FILE', bg: '#F1EFE8', color: '#5F5E5A' };
  return (
    <div style={{
      width: '28px', height: '28px', flexShrink: 0,
      borderRadius: '6px',
      background: cfg.bg,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontSize: '9px', fontWeight: '600',
      color: cfg.color, letterSpacing: '0.03em',
    }}>
      {cfg.label}
    </div>
  );
};

const StatusBadge = ({ status }) => {
  const cfg = {
    completed: {
      bg: '#EAF3DE', color: '#27500A', border: '#97C459',
      icon: <Check size={8} strokeWidth={2.5} />, label: 'Indexed',
    },
    processing: {
      bg: '#FAEEDA', color: '#633806', border: '#EF9F27',
      icon: <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#EF9F27', display: 'inline-block', animation: 'pulse 1.2s ease-in-out infinite' }} />,
      label: 'Processing',
    },
    failed: {
      bg: '#FCEBEB', color: '#791F1F', border: '#F09595',
      icon: <X size={8} strokeWidth={2.5} />, label: 'Failed',
    },
    pending: {
      bg: '#FAEEDA', color: '#633806', border: '#EF9F27',
      icon: <Loader2 size={8} style={{ animation: 'spin 1s linear infinite' }} />,
      label: 'Pending',
    },
  };
  const s = cfg[status] || cfg.processing;
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: '4px',
      padding: '3px 8px', borderRadius: '20px',
      fontSize: '11px', fontWeight: '500',
      background: s.bg, color: s.color,
      border: `0.5px solid ${s.border}`,
    }}>
      {s.icon}
      {s.label}
    </span>
  );
};

const SourceBadge = ({ source }) => {
  if (!source || source === 'upload') return null;
  const cfg = {
    git:    { bg: '#FAEEDA', color: '#633806', border: '#EF9F27', icon: <GitBranch size={9} />, label: 'Git' },
    gdrive: { bg: '#EAF3DE', color: '#27500A', border: '#97C459', icon: <Folder size={9} />,    label: 'Drive' },
  };
  const c = cfg[source] || { bg: '#E6F1FB', color: '#0C447C', border: '#85B7EB', icon: <ExternalLink size={9} />, label: source };
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: '3px',
      padding: '2px 7px', borderRadius: '20px',
      fontSize: '11px', fontWeight: '500',
      background: c.bg, color: c.color,
      border: `0.5px solid ${c.border}`,
    }}>
      {c.icon}
      {c.label}
    </span>
  );
};

const SourceChip = ({ source, syncing, onSync, onDelete }) => {
  const isGit = source.type === 'git';
  return (
    <div style={{
      display: 'inline-flex', alignItems: 'center', gap: '6px',
      padding: '5px 10px',
      borderRadius: 'var(--radius)',
      background: 'var(--bg-card)',
      border: '1px solid var(--gray-200)',
      fontSize: '12px', color: 'var(--gray-600)',
    }}>
      <div style={{
        width: '18px', height: '18px', borderRadius: '4px',
        background: isGit ? '#FAEEDA' : '#EAF3DE',
        display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
      }}>
        {isGit
          ? <GitBranch size={10} color="#633806" />
          : <Folder size={10} color="#27500A" />
        }
      </div>
      <span style={{ fontWeight: '500', color: 'var(--gray-800)' }}>{source.name}</span>
      {source.last_sync && (
        <span style={{ fontSize: '11px', color: 'var(--gray-400)' }}>
          {new Date(source.last_sync).toLocaleDateString('fr-FR')}
        </span>
      )}
      <button
        onClick={() => onSync(source.name)}
        disabled={syncing}
        title="Sync"
        style={{
          padding: '3px', background: 'none', border: 'none',
          cursor: syncing ? 'not-allowed' : 'pointer',
          color: 'var(--gray-400)', borderRadius: '4px',
          display: 'flex', alignItems: 'center',
        }}
        onMouseEnter={e => { if (!syncing) { e.currentTarget.style.color = 'var(--gray-700)'; e.currentTarget.style.background = 'var(--gray-100)'; } }}
        onMouseLeave={e => { e.currentTarget.style.color = 'var(--gray-400)'; e.currentTarget.style.background = 'none'; }}
      >
        <RefreshCw size={11} style={syncing ? { animation: 'spin 1s linear infinite' } : {}} />
      </button>
      <button
        onClick={() => onDelete(source.id, source.name)}
        title="Remove"
        style={{
          padding: '3px', background: 'none', border: 'none',
          cursor: 'pointer', color: 'var(--gray-400)', borderRadius: '4px',
          display: 'flex', alignItems: 'center',
        }}
        onMouseEnter={e => { e.currentTarget.style.color = 'var(--danger)'; e.currentTarget.style.background = 'rgba(239,68,68,0.08)'; }}
        onMouseLeave={e => { e.currentTarget.style.color = 'var(--gray-400)'; e.currentTarget.style.background = 'none'; }}
      >
        <X size={11} />
      </button>
    </div>
  );
};

// ── Shared accept string ──────────────────────────────────────────────────────
const ACCEPT = '.pdf,.docx,.doc,.pptx,.ppt,.txt,.md,.markdown,.html,.htm,.xlsx,.xls,.csv,.rtf,.odt,.ods,.odp,.tex,.epub,.xml,.py,.js,.jsx,.ts,.tsx,.css,.java,.cpp,.c,.cs,.go,.rs,.php,.rb,.swift,.kt,.scala,.r,.groovy,.sh,.bash,.sql,.json,.yaml,.yml,.toml,.ini,.env,.jenkinsfile,.zip,.tar,.gz';

// ── Table header cell ─────────────────────────────────────────────────────────
const TH = ({ children, align = 'left' }) => (
  <th style={{
    padding: '9px 14px',
    textAlign: align,
    fontSize: '11px', fontWeight: '500',
    color: 'var(--gray-400)',
    letterSpacing: '0.04em', textTransform: 'uppercase',
    whiteSpace: 'nowrap',
    borderBottom: '1px solid var(--gray-100)',
  }}>
    {children}
  </th>
);

// ── Main component ────────────────────────────────────────────────────────────
const Documents = () => {
  const { projectId } = useParams();
  const navigate = useNavigate();

  const [documents, setDocuments]             = useState([]);
  const [project, setProject]                 = useState(null);
  const [loading, setLoading]                 = useState(true);
  const [uploading, setUploading]             = useState(false);
  const [syncing, setSyncing]                 = useState(false);
  const [connectedSources, setConnectedSources] = useState([]);
  const [showSourceModal, setShowSourceModal] = useState(false);
  const [alert, setAlert]                     = useState(null);

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
      const [projectRes, docsRes] = await Promise.all([
        api.get(`/api/projects/${projectId}`),
        api.get(`/api/documents/${projectId}/documents`),
      ]);
      setProject(projectRes.data);
      setDocuments(Array.isArray(docsRes.data) ? docsRes.data : []);
    } catch (err) {
      showAlert('error', 'Failed to load documents');
      setDocuments([]);
    } finally {
      setLoading(false);
    }
  };

  const fetchDocuments = async () => {
    setLoading(true);
    try {
      const res = await api.get('/documents');
      setDocuments(Array.isArray(res.data) ? res.data : []);
    } catch {
      showAlert('error', 'Failed to load documents');
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
    } catch {
      setConnectedSources([]);
    }
  };

  const syncExternalSources = async () => {
    if (!projectId) return;
    setSyncing(true);
    try {
      const res = await api.post('/api/integrations/sync', { domain: projectId.toString() });
      showAlert('success', `Synced ${res.data.total_documents} documents from external sources`);
      await fetchProjectAndDocuments();
    } catch (err) {
      showAlert('error', 'Sync failed: ' + (err.response?.data?.detail || err.message));
    } finally {
      setSyncing(false);
    }
  };

  const resyncIntegration = async (name) => {
    setSyncing(true);
    try {
      const res = await api.post('/api/integrations/sync', {
        domain: projectId.toString(),
        sources: [name],
      });
      showAlert('success', `Synced ${res.data.total_documents} documents from "${name}"`);
      await fetchProjectAndDocuments();
    } catch (err) {
      showAlert('error', 'Sync failed: ' + (err.response?.data?.detail || err.message));
    } finally {
      setSyncing(false);
    }
  };

  const deleteIntegration = async (id, name) => {
    if (!window.confirm(`Delete integration "${name}"? Documents already synced will remain.`)) return;
    try {
      await api.delete(`/api/integrations/integrations/${id}`);
      showAlert('success', `Integration "${name}" removed`);
      loadConnectedSources();
    } catch (err) {
      showAlert('error', 'Failed to remove integration: ' + (err.response?.data?.detail || err.message));
    }
  };

  const handleUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const fd = new FormData();
    fd.append('file', file);
    setUploading(true);
    try {
      const endpoint = projectId
        ? `/api/documents/${projectId}/upload`
        : '/api/documents/upload';
      const res = await api.post(endpoint, fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      showAlert('success', `"${file.name}" uploaded — processing…`);
      pollDocumentStatus(res.data.document_id);
    } catch (err) {
      showAlert('error', err.response?.data?.detail || 'Upload failed');
    } finally {
      setUploading(false);
      e.target.value = '';
    }
  };

  const pollDocumentStatus = (documentId) => {
    const interval = setInterval(async () => {
      try {
        const res = await api.get(`/api/documents/${documentId}/status`);
        if (res.data.status === 'completed') {
          showAlert('success', `Processing complete — ${res.data.chunk_count} chunks`);
          clearInterval(interval);
          projectId ? fetchProjectAndDocuments() : fetchDocuments();
        } else if (res.data.status === 'failed') {
          showAlert('error', `Processing failed: ${res.data.error_message}`);
          clearInterval(interval);
        }
      } catch {
        clearInterval(interval);
      }
    }, 2000);
  };

  const handleDelete = async (docId) => {
    if (!window.confirm('Delete this document?')) return;
    try {
      await api.delete(`/api/documents/${docId}`);
      setDocuments(prev => prev.filter(d => d.id !== docId));
      showAlert('success', 'Document deleted');
    } catch (err) {
      showAlert('error', 'Delete failed: ' + (err.response?.data?.detail || err.message));
    }
  };

  const showAlert = (type, message) => {
    setAlert({ type, message });
    setTimeout(() => setAlert(null), 5000);
  };

  const totalChunks = documents.reduce((s, d) => s + (d.chunk_count || 0), 0);

  if (loading) return <Layout><Loading message="Loading documents..." /></Layout>;

  return (
    <Layout>
      <style>{`
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
        @keyframes pulse { 0%,100% { opacity:1 } 50% { opacity:.3 } }
      `}</style>

      <div style={{ padding: 'var(--spacing-8) var(--spacing-6)', maxWidth: '1100px', margin: '0 auto' }}>

        {/* Alert */}
        {alert && (
          <div style={{ marginBottom: 'var(--spacing-4)' }}>
            <Alert type={alert.type} message={alert.message} onClose={() => setAlert(null)} />
          </div>
        )}

        {/* ── Header ── */}
        <div style={{ marginBottom: '1.5rem' }}>
          {projectId && (
            <button
              onClick={() => navigate('/projects')}
              style={{
                display: 'inline-flex', alignItems: 'center', gap: '5px',
                fontSize: '12px', color: 'var(--gray-500)',
                background: 'none', border: 'none', cursor: 'pointer',
                padding: '0', marginBottom: '8px',
              }}
            >
              <ArrowLeft size={12} />
              Back to projects
            </button>
          )}

          <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '12px' }}>
            <div>
              <h1 style={{ fontSize: 'var(--text-2xl)', fontWeight: '600', color: 'var(--gray-900)', marginBottom: '4px' }}>
                {projectId && project ? project.name : 'Documents'}
              </h1>
              <p style={{ fontSize: 'var(--text-sm)', color: 'var(--gray-500)' }}>
                {documents.length} document{documents.length !== 1 ? 's' : ''}
                {totalChunks > 0 && ` · ${totalChunks.toLocaleString()} chunks indexed`}
              </p>
            </div>

            {/* Actions */}
            <div style={{ display: 'flex', gap: '6px', alignItems: 'center', flexShrink: 0, marginTop: '2px' }}>
              {projectId && (
                <>
                  <button
                    onClick={() => setShowSourceModal(true)}
                    style={{
                      display: 'inline-flex', alignItems: 'center', gap: '5px',
                      height: '32px', padding: '0 12px',
                      borderRadius: 'var(--radius)',
                      border: '1px solid var(--gray-200)',
                      background: 'transparent',
                      fontSize: '12px', color: 'var(--gray-600)',
                      cursor: 'pointer', whiteSpace: 'nowrap',
                    }}
                    onMouseEnter={e => { e.currentTarget.style.background = 'var(--gray-50)'; e.currentTarget.style.color = 'var(--gray-900)'; }}
                    onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = 'var(--gray-600)'; }}
                  >
                    <GitBranch size={13} />
                    Connect source
                  </button>

                  <button
                    onClick={syncExternalSources}
                    disabled={syncing}
                    style={{
                      display: 'inline-flex', alignItems: 'center', gap: '5px',
                      height: '32px', padding: '0 12px',
                      borderRadius: 'var(--radius)',
                      border: '1px solid var(--gray-200)',
                      background: 'transparent',
                      fontSize: '12px', color: 'var(--gray-600)',
                      cursor: syncing ? 'not-allowed' : 'pointer',
                      opacity: syncing ? 0.6 : 1,
                      whiteSpace: 'nowrap',
                    }}
                    onMouseEnter={e => { if (!syncing) { e.currentTarget.style.background = 'var(--gray-50)'; e.currentTarget.style.color = 'var(--gray-900)'; } }}
                    onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = 'var(--gray-600)'; }}
                  >
                    <RefreshCw size={13} style={syncing ? { animation: 'spin 1s linear infinite' } : {}} />
                    {syncing ? 'Syncing…' : 'Sync all'}
                  </button>
                </>
              )}

              {/* Upload */}
              <label
                style={{
                  display: 'inline-flex', alignItems: 'center', gap: '5px',
                  height: '32px', padding: '0 14px',
                  borderRadius: 'var(--radius)',
                  background: 'var(--gray-900)', color: 'white',
                  border: 'none',
                  fontSize: '12px', fontWeight: '500',
                  cursor: uploading ? 'not-allowed' : 'pointer',
                  opacity: uploading ? 0.7 : 1,
                  transition: 'opacity 0.15s',
                  whiteSpace: 'nowrap',
                }}
                onMouseEnter={e => { if (!uploading) e.currentTarget.style.opacity = '0.85'; }}
                onMouseLeave={e => { e.currentTarget.style.opacity = uploading ? '0.7' : '1'; }}
              >
                {uploading
                  ? <><Loader2 size={13} style={{ animation: 'spin 1s linear infinite' }} /> Uploading…</>
                  : <><Upload size={13} /> Upload</>
                }
                <input type="file" hidden accept={ACCEPT} onChange={handleUpload} disabled={uploading} />
              </label>
            </div>
          </div>

          {/* ── Connected sources chips ── */}
          {connectedSources.length > 0 && (
            <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '6px', marginTop: '14px' }}>
              <span style={{
                fontSize: '11px', fontWeight: '500',
                color: 'var(--gray-400)',
                letterSpacing: '0.05em', textTransform: 'uppercase',
                marginRight: '2px',
              }}>
                Sources
              </span>
              {connectedSources.map(source => (
                <SourceChip
                  key={source.id}
                  source={source}
                  syncing={syncing}
                  onSync={resyncIntegration}
                  onDelete={deleteIntegration}
                />
              ))}
            </div>
          )}
        </div>

        {/* ── Empty state ── */}
        {documents.length === 0 ? (
          <div style={{
            display: 'flex', flexDirection: 'column',
            alignItems: 'center', justifyContent: 'center',
            padding: 'var(--spacing-16)',
            border: '1px dashed var(--gray-300)',
            borderRadius: 'var(--radius-lg)',
            textAlign: 'center', gap: 'var(--spacing-4)',
          }}>
            <div style={{
              width: '48px', height: '48px', borderRadius: '50%',
              border: '1px solid var(--gray-200)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              color: 'var(--gray-400)',
            }}>
              <FileText size={20} />
            </div>
            <div>
              <p style={{ fontWeight: '500', color: 'var(--gray-700)', marginBottom: '4px' }}>No documents yet</p>
              <p style={{ fontSize: 'var(--text-sm)', color: 'var(--gray-500)' }}>
                Upload a file or connect an external source
              </p>
            </div>
            <label style={{
              display: 'inline-flex', alignItems: 'center', gap: '6px',
              padding: '8px 20px',
              background: 'var(--gray-900)', color: 'white',
              border: 'none', borderRadius: 'var(--radius)',
              fontSize: 'var(--text-sm)', fontWeight: '500', cursor: 'pointer',
            }}>
              <Upload size={14} />
              Upload document
              <input type="file" hidden accept={ACCEPT} onChange={handleUpload} disabled={uploading} />
            </label>
          </div>
        ) : (
          /* ── Documents table ── */
          <div style={{
            background: 'var(--bg-card)',
            border: '1px solid var(--gray-200)',
            borderRadius: 'var(--radius-lg)',
            overflow: 'hidden',
          }}>
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr>
                    <TH>Document</TH>
                    <TH>Type</TH>
                    <TH>Source</TH>
                    <TH>Size</TH>
                    <TH>Chunks</TH>
                    <TH>Status</TH>
                    <TH>Date</TH>
                    <TH align="right" />
                  </tr>
                </thead>
                <tbody>
                  {documents.map((doc, idx) => {
                    const ext = getFileExt(doc.filename, doc.file_type);
                    return (
                      <tr
                        key={doc.id}
                        style={{
                          borderTop: idx === 0 ? 'none' : '1px solid var(--gray-100)',
                          transition: 'background 0.1s',
                        }}
                        onMouseEnter={e => e.currentTarget.style.background = 'var(--gray-50)'}
                        onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                      >
                        {/* Filename */}
                        <td style={{ padding: '10px 14px', maxWidth: '280px' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                            <FileTypeIcon filename={doc.filename} fileType={doc.file_type} />
                            <span style={{
                              fontSize: '13px', fontWeight: '500',
                              color: 'var(--gray-900)',
                              overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                            }}>
                              {doc.filename || 'Unnamed'}
                            </span>
                          </div>
                        </td>

                        {/* Type label */}
                        <td style={{ padding: '10px 14px' }}>
                          <span style={{ fontSize: '12px', color: 'var(--gray-500)' }}>
                            {FILE_TYPE_LABELS[ext] || ext.toUpperCase()}
                          </span>
                        </td>

                        {/* Source badge */}
                        <td style={{ padding: '10px 14px' }}>
                          <SourceBadge source={doc.source} />
                        </td>

                        {/* Size */}
                        <td style={{ padding: '10px 14px', fontSize: '12px', color: 'var(--gray-500)', whiteSpace: 'nowrap' }}>
                          {formatFileSize(doc.file_size)}
                        </td>

                        {/* Chunks */}
                        <td style={{ padding: '10px 14px', fontSize: '13px', fontWeight: '500', color: 'var(--gray-800)' }}>
                          {doc.chunk_count > 0 ? doc.chunk_count : '—'}
                        </td>

                        {/* Status */}
                        <td style={{ padding: '10px 14px' }}>
                          <StatusBadge status={doc.status || 'completed'} />
                        </td>

                        {/* Date */}
                        <td style={{ padding: '10px 14px', fontSize: '12px', color: 'var(--gray-500)', whiteSpace: 'nowrap' }}>
                          {formatDate(doc.created_at)}
                        </td>

                        {/* Delete */}
                        <td style={{ padding: '10px 14px', textAlign: 'right' }}>
                          <button
                            onClick={() => handleDelete(doc.id)}
                            title="Delete document"
                            style={{
                              padding: '4px', background: 'none', border: 'none',
                              cursor: 'pointer', color: 'var(--gray-400)',
                              borderRadius: '5px', display: 'inline-flex',
                              alignItems: 'center',
                            }}
                            onMouseEnter={e => { e.currentTarget.style.color = 'var(--danger)'; e.currentTarget.style.background = 'rgba(239,68,68,0.08)'; }}
                            onMouseLeave={e => { e.currentTarget.style.color = 'var(--gray-400)'; e.currentTarget.style.background = 'none'; }}
                          >
                            <Trash2 size={13} />
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* ── Connect Source Modal ── */}
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