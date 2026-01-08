import { useState, useEffect } from 'react';
import { GitBranch, Folder, X, Loader, CheckCircle } from 'lucide-react';
import api from '../services/api';

const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID;
const GOOGLE_API_KEY = import.meta.env.VITE_GOOGLE_API_KEY;
const GOOGLE_APP_ID = import.meta.env.VITE_GOOGLE_APP_ID;

const ConnectSourceModal = ({ projectId, onClose, onSuccess }) => {
  const [activeTab, setActiveTab] = useState('git');
  const [loading, setLoading] = useState(false);
  const [googleReady, setGoogleReady] = useState(false);
  const [gdriveConnected, setGdriveConnected] = useState(false);
  const [gdriveEmail, setGdriveEmail] = useState(null);
  
  const [gitConfig, setGitConfig] = useState({
    name: '',
    url: '',
    branch: 'main',
    token: '',
    patterns: '*.md, *.txt, *.pdf, *.docx'
  });

  // Load Google APIs
  useEffect(() => {
    loadGoogleAPIs();
    checkGDriveStatus();
  }, []);

  const loadGoogleAPIs = () => {
    // Load GAPI
    const gapiScript = document.createElement('script');
    gapiScript.src = 'https://apis.google.com/js/api.js';
    gapiScript.async = true;
    gapiScript.defer = true;
    gapiScript.onload = () => {
      window.gapi.load('client:picker', () => {
        setGoogleReady(true);
      });
    };
    document.body.appendChild(gapiScript);

    // Load GSI
    const gsiScript = document.createElement('script');
    gsiScript.src = 'https://accounts.google.com/gsi/client';
    gsiScript.async = true;
    gsiScript.defer = true;
    document.body.appendChild(gsiScript);
  };

  const checkGDriveStatus = async () => {
    try {
      const res = await api.get(`/api/integrations/gdrive/status/${projectId}`);
      setGdriveConnected(res.data.connected);
      setGdriveEmail(res.data.user_email);
    } catch (err) {
      console.error('Failed to check GDrive status:', err);
    }
  };

  // ========== GIT ==========
  const connectGit = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      const testRes = await api.post('/api/integrations/git/test', {
        url: gitConfig.url,
        token: gitConfig.token || undefined,
        branch: gitConfig.branch
      });

      if (!testRes.data.connected) {
        alert('Cannot connect to repository');
        setLoading(false);
        return;
      }

      await api.post('/api/integrations/git/repos', {
        project_id: projectId.toString(),
        name: gitConfig.name,
        url: gitConfig.url,
        branch: gitConfig.branch,
        token: gitConfig.token || undefined,
        patterns: gitConfig.patterns.split(',').map(p => p.trim()),
      });

      await api.post('/api/integrations/sync', {
        domain: projectId.toString(),
        sources: [gitConfig.name]
      });

      alert(`✅ Repository "${gitConfig.name}" connected!`);
      onSuccess();
      onClose();
    } catch (error) {
      alert('Error: ' + (error.response?.data?.detail || error.message));
    } finally {
      setLoading(false);
    }
  };

  // ========== GOOGLE DRIVE ==========
  const openGooglePicker = () => {
    if (!googleReady) {
      alert('⏳ Loading Google API...');
      return;
    }

    const tokenClient = window.google.accounts.oauth2.initTokenClient({
      client_id: GOOGLE_CLIENT_ID,
      scope: 'https://www.googleapis.com/auth/drive.readonly',
      callback: async (response) => {
        if (response.error) {
          alert('❌ Auth failed: ' + response.error);
          return;
        }

        const accessToken = response.access_token;

        // Init GAPI client
        await window.gapi.client.init({
          apiKey: GOOGLE_API_KEY,
          discoveryDocs: ['https://www.googleapis.com/discovery/v1/apis/drive/v3/rest']
        });

        // Open Picker
        const picker = new window.google.picker.PickerBuilder()
          .addView(window.google.picker.ViewId.DOCS)
          .addView(new window.google.picker.DocsView().setIncludeFolders(true))
          .setOAuthToken(accessToken)
          .setDeveloperKey(GOOGLE_API_KEY)
          .setAppId(GOOGLE_APP_ID)
          .setCallback((data) => handlePickerResult(data, accessToken))
          .build();

        picker.setVisible(true);
      }
    });

    tokenClient.requestAccessToken();
  };

  const handlePickerResult = async (data, accessToken) => {
    if (data.action !== window.google.picker.Action.PICKED) return;

    const files = data.docs.map(doc => ({
      id: doc.id,
      name: doc.name,
      mimeType: doc.mimeType
    }));

    setLoading(true);

    try {
      // Connect Google Drive
      await api.post('/api/integrations/gdrive/connect', {
        project_id: projectId.toString(),
        access_token: accessToken
      });

      // Import files
      const res = await api.post('/api/integrations/gdrive/import-files', {
        project_id: projectId.toString(),
        access_token: accessToken,
        files: files
      });

      alert(`✅ Imported ${res.data.files_downloaded} files!`);
      setGdriveConnected(true);
      onSuccess();
      onClose();
    } catch (error) {
      alert('❌ Error: ' + (error.response?.data?.detail || error.message));
    } finally {
      setLoading(false);
    }
  };

  const disconnectGDrive = async () => {
    if (!confirm('Disconnect Google Drive?')) return;

    try {
      await api.delete(`/api/integrations/gdrive/${projectId}`);
      setGdriveConnected(false);
      setGdriveEmail(null);
      alert('✅ Disconnected');
    } catch (error) {
      alert('Error: ' + (error.response?.data?.detail || error.message));
    }
  };

  return (
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
      <div className="card" style={{ 
        width: '100%', 
        maxWidth: '700px',
        maxHeight: '90vh',
        overflow: 'auto'
      }}>
        {/* Header */}
        <div style={{ 
          display: 'flex', 
          justifyContent: 'space-between', 
          alignItems: 'center',
          marginBottom: 'var(--spacing-6)'
        }}>
          <h2 style={{ fontSize: 'var(--text-2xl)', fontWeight: '600' }}>
            Connect External Source
          </h2>
          <button 
            onClick={onClose} 
            className="btn-ghost btn-sm"
            style={{ border: 'none', background: 'none', cursor: 'pointer', padding: 'var(--spacing-2)' }}
          >
            <X size={20} />
          </button>
        </div>

        {/* Tabs */}
        <div style={{ 
          display: 'flex', 
          gap: 'var(--spacing-2)',
          borderBottom: '1px solid var(--border-color)',
          marginBottom: 'var(--spacing-6)'
        }}>
          <button
            onClick={() => setActiveTab('git')}
            style={{
              padding: 'var(--spacing-3) var(--spacing-4)',
              border: 'none',
              background: 'none',
              borderBottom: activeTab === 'git' ? '2px solid var(--primary)' : 'none',
              color: activeTab === 'git' ? 'var(--primary)' : 'var(--text-secondary)',
              fontWeight: activeTab === 'git' ? '600' : '400',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 'var(--spacing-2)'
            }}
          >
            <GitBranch size={16} />
            Git Repository
          </button>
          <button
            onClick={() => setActiveTab('gdrive')}
            style={{
              padding: 'var(--spacing-3) var(--spacing-4)',
              border: 'none',
              background: 'none',
              borderBottom: activeTab === 'gdrive' ? '2px solid var(--primary)' : 'none',
              color: activeTab === 'gdrive' ? 'var(--primary)' : 'var(--text-secondary)',
              fontWeight: activeTab === 'gdrive' ? '600' : '400',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 'var(--spacing-2)'
            }}
          >
            <Folder size={16} />
            Google Drive
          </button>
        </div>

        {/* GIT FORM */}
        {activeTab === 'git' && (
          <form onSubmit={connectGit}>
            <div className="form-group">
              <label className="form-label">Repository Name</label>
              <input
                type="text"
                className="form-input"
                placeholder="my-docs"
                value={gitConfig.name}
                onChange={(e) => setGitConfig({ ...gitConfig, name: e.target.value })}
                required
              />
            </div>

            <div className="form-group">
              <label className="form-label">Repository URL</label>
              <input
                type="url"
                className="form-input"
                placeholder="https://github.com/user/repo.git"
                value={gitConfig.url}
                onChange={(e) => setGitConfig({ ...gitConfig, url: e.target.value })}
                required
              />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--spacing-4)' }}>
              <div className="form-group">
                <label className="form-label">Branch</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="main"
                  value={gitConfig.branch}
                  onChange={(e) => setGitConfig({ ...gitConfig, branch: e.target.value })}
                />
              </div>

              <div className="form-group">
                <label className="form-label">Token (optional)</label>
                <input
                  type="password"
                  className="form-input"
                  placeholder="ghp_xxx"
                  value={gitConfig.token}
                  onChange={(e) => setGitConfig({ ...gitConfig, token: e.target.value })}
                />
              </div>
            </div>

            <div className="form-group">
              <label className="form-label">File Patterns</label>
              <input
                type="text"
                className="form-input"
                placeholder="*.md, *.txt, *.pdf"
                value={gitConfig.patterns}
                onChange={(e) => setGitConfig({ ...gitConfig, patterns: e.target.value })}
              />
            </div>

            <div style={{ display: 'flex', gap: 'var(--spacing-3)', justifyContent: 'flex-end', marginTop: 'var(--spacing-6)' }}>
              <button type="button" className="btn btn-ghost" onClick={onClose} disabled={loading}>
                Cancel
              </button>
              <button type="submit" className="btn btn-primary" disabled={loading}>
                {loading ? 'Connecting...' : 'Connect & Sync'}
              </button>
            </div>
          </form>
        )}

        {/* GOOGLE DRIVE */}
        {activeTab === 'gdrive' && (
          <div>
            {gdriveConnected ? (
              <div style={{
                padding: 'var(--spacing-4)',
                background: 'rgba(34, 197, 94, 0.05)',
                border: '1px solid rgba(34, 197, 94, 0.3)',
                borderRadius: 'var(--radius)',
                marginBottom: 'var(--spacing-6)'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-2)', marginBottom: 'var(--spacing-2)' }}>
                  <CheckCircle size={20} style={{ color: 'var(--success)' }} />
                  <strong>✅ Google Drive Connected</strong>
                </div>
                <p style={{ fontSize: 'var(--text-sm)', color: 'var(--text-secondary)', marginBottom: 'var(--spacing-3)' }}>
                  {gdriveEmail && `Connected as: ${gdriveEmail}`}
                </p>
                <button onClick={disconnectGDrive} className="btn btn-ghost" style={{ fontSize: 'var(--text-sm)' }}>
                  Disconnect
                </button>
              </div>
            ) : (
              <>
                <div style={{
                  padding: 'var(--spacing-4)',
                  background: 'rgba(96, 165, 250, 0.05)',
                  border: '1px solid rgba(96, 165, 250, 0.2)',
                  borderRadius: 'var(--radius)',
                  marginBottom: 'var(--spacing-6)'
                }}>
                  <h3 style={{ fontSize: 'var(--text-lg)', fontWeight: '600', marginBottom: 'var(--spacing-2)' }}>
                    📁 Import from Google Drive
                  </h3>
                  <p style={{ fontSize: 'var(--text-sm)', color: 'var(--text-secondary)' }}>
                    Click below to authenticate and select files
                  </p>
                </div>

                <button
                  onClick={openGooglePicker}
                  className="btn btn-primary"
                  disabled={loading || !googleReady}
                  style={{ 
                    width: '100%',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: 'var(--spacing-2)',
                    padding: 'var(--spacing-4)'
                  }}
                >
                  {loading ? (
                    <>
                      <Loader size={20} style={{ animation: 'spin 1s linear infinite' }} />
                      Importing...
                    </>
                  ) : !googleReady ? (
                    <>
                      <Loader size={20} style={{ animation: 'spin 1s linear infinite' }} />
                      Loading...
                    </>
                  ) : (
                    <>
                      <Folder size={20} />
                      Connect Google Drive
                    </>
                  )}
                </button>
              </>
            )}

            <div style={{ marginTop: 'var(--spacing-6)', display: 'flex', justifyContent: 'flex-end' }}>
              <button type="button" className="btn btn-ghost" onClick={onClose}>
                Close
              </button>
            </div>
          </div>
        )}
      </div>

      <style>{`
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
};

export default ConnectSourceModal;