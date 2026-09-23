import { useState, useEffect } from 'react';
import {
  User, Save, Search, CheckCircle, XCircle, Plus, RefreshCw, Loader2, Database,
  KeyRound, Copy, Eye, EyeOff, Clock, ShieldAlert, Terminal
} from 'lucide-react';
import Layout from '../components/layout/Layout';
import Button from '../components/common/Button';
import Alert from '../components/common/Alert';
import { useAuthStore } from '../store/authStore';
import { authService } from '../services/auth';
import api from '../services/api';

/**
 * Décode le payload d'un JWT (base64url) sans dépendance externe.
 * Ne vérifie PAS la signature : usage purement informatif côté UI
 * (affichage de la date d'expiration réelle configurée côté backend
 * via ACCESS_TOKEN_EXPIRE_MINUTES / REFRESH_TOKEN_EXPIRE_DAYS).
 */
const decodeJwtPayload = (token) => {
  try {
    const base64Url = token.split('.')[1];
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
    const json = decodeURIComponent(
      atob(base64)
        .split('')
        .map(c => '%' + c.charCodeAt(0).toString(16).padStart(2, '0'))
        .join('')
    );
    return JSON.parse(json);
  } catch {
    return null;
  }
};

const Settings = () => {
  const { user, loadUser } = useAuthStore();
  const [activeTab, setActiveTab] = useState('profile');
  const [formData, setFormData] = useState({
    username: '',
    email: '',
    password: '',
    confirmPassword: ''
  });
  const [loading, setLoading] = useState(false);
  const [alert, setAlert] = useState(null);

  // OpenSearch state
  const [osSettings, setOsSettings] = useState(null);
  const [osHealth, setOsHealth] = useState(null);         // null | {status, ...}
  const [osIndices, setOsIndices] = useState([]);
  const [osLoading, setOsLoading] = useState(false);
  const [osIndexInput, setOsIndexInput] = useState('');
  const [creatingIndex, setCreatingIndex] = useState(false);

  // API Token state (usage externe : intégrations tierces via l'API)
  const [tokenPassword, setTokenPassword] = useState('');
  const [tokenLoading, setTokenLoading] = useState(false);
  const [apiToken, setApiToken] = useState(null); // { access_token, refresh_token, accessExp, refreshExp }
  const [showAccessToken, setShowAccessToken] = useState(false);
  const [showRefreshToken, setShowRefreshToken] = useState(false);
  const [copiedField, setCopiedField] = useState(null);

  useEffect(() => {
    if (user) {
      setFormData({ username: user.username, email: user.email, password: '', confirmPassword: '' });
    }
  }, [user]);

  useEffect(() => {
    if (activeTab === 'opensearch') {
      loadOsSettings();
    }
  }, [activeTab]);

  const loadOsSettings = async () => {
    setOsLoading(true);
    try {
      const res = await api.get('/api/opensearch/settings');
      setOsSettings(res.data);
    } catch (e) {
      console.error('Failed to load OpenSearch settings:', e);
    } finally {
      setOsLoading(false);
    }
  };

  const testOsConnection = async () => {
    setOsLoading(true);
    try {
      const res = await api.get('/api/opensearch/health');
      setOsHealth(res.data);
      if (res.data.status === 'ok') {
        const idxRes = await api.get('/api/opensearch/indices');
        setOsIndices(idxRes.data || []);
      }
    } catch (e) {
      setOsHealth({ status: 'error', detail: e.response?.data?.detail || e.message });
    } finally {
      setOsLoading(false);
    }
  };

  const refreshIndices = async () => {
    try {
      const res = await api.get('/api/opensearch/indices');
      setOsIndices(res.data || []);
    } catch (e) {
      console.error(e);
    }
  };

  const createIndex = async () => {
    if (!osIndexInput.trim()) return;
    setCreatingIndex(true);
    try {
      const res = await api.post('/api/opensearch/indices', { index_name: osIndexInput.trim() });
      showAlert('success', res.data.created
        ? `Index '${osIndexInput}' created successfully`
        : `Index '${osIndexInput}' already exists`);
      setOsIndexInput('');
      await refreshIndices();
    } catch (e) {
      showAlert('error', e.response?.data?.detail || 'Failed to create index');
    } finally {
      setCreatingIndex(false);
    }
  };

  const generateApiToken = async (e) => {
    e.preventDefault();
    if (!tokenPassword) {
      showAlert('error', 'Enter your password to confirm token generation');
      return;
    }
    setTokenLoading(true);
    try {
      // Réutilise le flux d'authentification existant (/api/auth/login).
      // Pas de credentials stockés côté client : le mot de passe n'est
      // utilisé qu'en mémoire pour cet appel puis immédiatement effacé.
      const data = await authService.login(user.username, tokenPassword);
      const accessPayload = decodeJwtPayload(data.access_token);
      const refreshPayload = decodeJwtPayload(data.refresh_token);
      setApiToken({
        access_token: data.access_token,
        refresh_token: data.refresh_token,
        accessExp: accessPayload?.exp ? new Date(accessPayload.exp * 1000) : null,
        refreshExp: refreshPayload?.exp ? new Date(refreshPayload.exp * 1000) : null,
      });
      setShowAccessToken(false);
      setShowRefreshToken(false);
      showAlert('success', 'Token generated successfully');
    } catch (error) {
      showAlert('error', error.response?.data?.detail || 'Failed to generate token — check your password');
    } finally {
      setTokenPassword('');
      setTokenLoading(false);
    }
  };

  const copyToClipboard = async (text, field) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedField(field);
      setTimeout(() => setCopiedField(null), 2000);
    } catch {
      showAlert('error', 'Copy failed — select and copy manually');
    }
  };

  const revokeApiToken = () => {
    setApiToken(null);
    setShowAccessToken(false);
    setShowRefreshToken(false);
  };

  const apiBase = typeof window !== 'undefined' ? window.location.origin : '';

  const curlLoginExample = `export BASE="${apiBase}"

TOKEN=$(curl -sk -X POST "$BASE/api/auth/login" \\
  -H "Content-Type: application/x-www-form-urlencoded" \\
  -d "username=${user?.username || 'username'}&password=YOUR_PASSWORD" \\
  | jq -r '.access_token')

echo "TOKEN=$TOKEN"`;

  const curlUseExample = apiToken
    ? `curl -sk "${apiBase}/api/auth/me" \\
  -H "Authorization: Bearer ${apiToken.access_token}"`
    : '';

  const handleChange = (e) => setFormData({ ...formData, [e.target.name]: e.target.value });

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (formData.password && formData.password !== formData.confirmPassword) {
      showAlert('error', 'Passwords do not match'); return;
    }
    if (formData.password && formData.password.length < 8) {
      showAlert('error', 'Password must be at least 8 characters'); return;
    }
    setLoading(true);
    try {
      const updateData = { username: formData.username, email: formData.email };
      if (formData.password) updateData.password = formData.password;
      await api.put('/api/auth/me', updateData);
      await loadUser();
      showAlert('success', 'Profile updated successfully');
      setFormData(f => ({ ...f, password: '', confirmPassword: '' }));
    } catch (error) {
      showAlert('error', error.response?.data?.detail || 'Failed to update profile');
    } finally {
      setLoading(false);
    }
  };

  const showAlert = (type, message) => {
    setAlert({ type, message });
    setTimeout(() => setAlert(null), 5000);
  };

  const tabs = [
    { id: 'profile', label: 'Profile', icon: User },
    { id: 'opensearch', label: 'OpenSearch', icon: Search },
    { id: 'api-token', label: 'API Token', icon: KeyRound },
  ];

  return (
    <Layout>
      <div className="container" style={{ padding: 'var(--spacing-8) var(--spacing-4)' }}>
        {alert && (
          <div style={{ marginBottom: 'var(--spacing-4)' }}>
            <Alert type={alert.type} message={alert.message} onClose={() => setAlert(null)} />
          </div>
        )}

        <div style={{ maxWidth: '800px', margin: '0 auto' }}>
          <div style={{ marginBottom: 'var(--spacing-6)' }}>
            <h1 style={{ fontSize: 'var(--text-3xl)', fontWeight: '700', marginBottom: 'var(--spacing-2)' }}>Settings</h1>
            <p style={{ color: 'var(--gray-600)' }}>Manage your account and infrastructure settings</p>
          </div>

          {/* Tab bar */}
          <div style={{ display: 'flex', gap: 'var(--spacing-1)', marginBottom: 'var(--spacing-6)', borderBottom: '1px solid var(--border)', paddingBottom: 'var(--spacing-1)' }}>
            {tabs.map(tab => {
              const Icon = tab.icon;
              return (
                <button key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  style={{
                    display: 'flex', alignItems: 'center', gap: '6px',
                    padding: 'var(--spacing-2) var(--spacing-4)',
                    borderRadius: 'var(--radius) var(--radius) 0 0',
                    border: 'none', cursor: 'pointer',
                    fontWeight: activeTab === tab.id ? '600' : '400',
                    color: activeTab === tab.id ? 'var(--primary)' : 'var(--gray-600)',
                    background: activeTab === tab.id ? 'rgba(99,102,241,0.08)' : 'transparent',
                    borderBottom: activeTab === tab.id ? '2px solid var(--primary)' : '2px solid transparent',
                    transition: 'all 0.15s',
                    fontSize: 'var(--text-sm)'
                  }}>
                  <Icon size={16} />{tab.label}
                </button>
              );
            })}
          </div>

          {/* ── Profile Tab ─────────────────────────────────────────────────── */}
          {activeTab === 'profile' && (
            <>
              <div className="card">
                <div className="card-header">
                  <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-3)' }}>
                    <User size={24} style={{ color: 'var(--primary)' }} />
                    <div>
                      <h2 className="card-title">Profile Information</h2>
                      <p className="card-description">Update your account details</p>
                    </div>
                  </div>
                </div>
                <form onSubmit={handleSubmit}>
                  <div className="form-group">
                    <label className="form-label">Username</label>
                    <input type="text" name="username" className="form-input" value={formData.username} onChange={handleChange} required minLength={3} maxLength={50} />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Email</label>
                    <input type="email" name="email" className="form-input" value={formData.email} onChange={handleChange} required />
                  </div>
                  <div style={{ borderTop: '1px solid var(--gray-200)', margin: 'var(--spacing-6) 0', paddingTop: 'var(--spacing-6)' }}>
                    <h3 style={{ fontSize: 'var(--text-lg)', fontWeight: '600', marginBottom: 'var(--spacing-2)' }}>Change Password</h3>
                    <p style={{ fontSize: 'var(--text-sm)', color: 'var(--gray-600)', marginBottom: 'var(--spacing-4)' }}>Leave blank to keep current password</p>
                    <div className="form-group">
                      <label className="form-label">New Password</label>
                      <input type="password" name="password" className="form-input" value={formData.password} onChange={handleChange} minLength={8} placeholder="Enter new password" />
                    </div>
                    <div className="form-group">
                      <label className="form-label">Confirm New Password</label>
                      <input type="password" name="confirmPassword" className="form-input" value={formData.confirmPassword} onChange={handleChange} placeholder="Confirm new password" />
                    </div>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 'var(--spacing-3)' }}>
                    <Button type="button" variant="ghost" onClick={() => setFormData({ username: user.username, email: user.email, password: '', confirmPassword: '' })}>Cancel</Button>
                    <Button type="submit" variant="primary" icon={Save} loading={loading}>Save Changes</Button>
                  </div>
                </form>
              </div>

              <div className="card" style={{ marginTop: 'var(--spacing-6)' }}>
                <div className="card-header">
                  <h2 className="card-title">Account Information</h2>
                  <p className="card-description">View your account details</p>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-3)' }}>
                  {[
                    { label: 'Account Status', value: 'Active', color: 'var(--success)' },
                    { label: 'Member Since', value: user && new Date(user.created_at).toLocaleDateString() },
                    { label: 'Last Updated', value: user && new Date(user.updated_at).toLocaleDateString() },
                  ].map(item => (
                    <div key={item.label} style={{ display: 'flex', justifyContent: 'space-between', padding: 'var(--spacing-3)', backgroundColor: 'var(--gray-50)', borderRadius: 'var(--radius)' }}>
                      <span style={{ fontWeight: '500', color: 'var(--gray-700)' }}>{item.label}</span>
                      <span style={{ color: item.color || 'var(--gray-600)' }}>{item.value}</span>
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}

          {/* ── OpenSearch Tab ─────────────────────────────────────────────── */}
          {activeTab === 'opensearch' && (
            <>
              {/* Connection info card */}
              <div className="card" style={{ marginBottom: 'var(--spacing-6)' }}>
                <div className="card-header">
                  <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-3)' }}>
                    <Search size={24} style={{ color: 'var(--primary)' }} />
                    <div>
                      <h2 className="card-title">OpenSearch Connection</h2>
                      <p className="card-description">
                        Connection settings are read-only here — configure via env vars, docker <code>-e</code>, or Helm <code>values.yaml</code>.
                      </p>
                    </div>
                  </div>
                </div>

                {osLoading && !osSettings ? (
                  <div style={{ textAlign: 'center', padding: 'var(--spacing-6)' }}>
                    <Loader2 className="animate-spin" size={24} style={{ color: 'var(--gray-400)', margin: '0 auto' }} />
                  </div>
                ) : osSettings ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-2)', marginBottom: 'var(--spacing-4)' }}>
                    {[
                      { label: 'Host', value: osSettings.host },
                      { label: 'Port', value: osSettings.port },
                      { label: 'User', value: osSettings.user || '—' },
                      { label: 'SSL', value: osSettings.use_ssl ? 'Enabled' : 'Disabled' },
                      { label: 'Verify Certs', value: osSettings.verify_certs ? 'Yes' : 'No' },
                      { label: 'Embedding Dim', value: osSettings.embedding_dim },
                    ].map(row => (
                      <div key={row.label} style={{ display: 'flex', justifyContent: 'space-between', padding: 'var(--spacing-2) var(--spacing-3)', background: 'var(--gray-50)', borderRadius: 'var(--radius)' }}>
                        <span style={{ fontWeight: '500', color: 'var(--gray-700)', fontSize: 'var(--text-sm)' }}>{row.label}</span>
                        <code style={{ fontSize: 'var(--text-sm)', color: 'var(--gray-800)' }}>{String(row.value)}</code>
                      </div>
                    ))}
                  </div>
                ) : null}

                {/* Health status */}
                {osHealth && (
                  <div style={{
                    display: 'flex', alignItems: 'center', gap: 'var(--spacing-2)',
                    padding: 'var(--spacing-3)', borderRadius: 'var(--radius)', marginBottom: 'var(--spacing-4)',
                    background: osHealth.status === 'ok' ? 'rgba(16,185,129,0.08)' : 'rgba(239,68,68,0.08)',
                    border: `1px solid ${osHealth.status === 'ok' ? 'rgba(16,185,129,0.3)' : 'rgba(239,68,68,0.3)'}`
                  }}>
                    {osHealth.status === 'ok'
                      ? <CheckCircle size={18} style={{ color: 'var(--success)', flexShrink: 0 }} />
                      : <XCircle size={18} style={{ color: 'var(--error)', flexShrink: 0 }} />}
                    <div>
                      {osHealth.status === 'ok' ? (
                        <span style={{ fontSize: 'var(--text-sm)', fontWeight: '600', color: 'var(--success)' }}>
                          Connected — cluster <strong>{osHealth.cluster_name}</strong>, OpenSearch {osHealth.version}, status: <strong>{osHealth.cluster_status}</strong>
                        </span>
                      ) : (
                        <span style={{ fontSize: 'var(--text-sm)', fontWeight: '600', color: 'var(--error)' }}>
                          Connection failed: {osHealth.detail}
                        </span>
                      )}
                    </div>
                  </div>
                )}

                <div style={{ display: 'flex', gap: 'var(--spacing-3)' }}>
                  <Button variant="primary" onClick={testOsConnection} loading={osLoading}>
                    <Search size={16} />
                    Test Connection
                  </Button>
                  {osHealth?.status === 'ok' && (
                    <Button variant="ghost" onClick={refreshIndices}>
                      <RefreshCw size={16} />
                      Refresh Indices
                    </Button>
                  )}
                </div>

                <div style={{ marginTop: 'var(--spacing-4)', padding: 'var(--spacing-3)', background: 'var(--gray-50)', borderRadius: 'var(--radius)', fontSize: 'var(--text-xs)', color: 'var(--gray-500)' }}>
                  <strong>To update connection settings:</strong> set these env vars then restart the backend container:<br />
                  <code>OPENSEARCH_HOST · OPENSEARCH_PORT · OPENSEARCH_USER · OPENSEARCH_PASSWORD · OPENSEARCH_USE_SSL · OPENSEARCH_VERIFY_CERTS · OPENSEARCH_EMBEDDING_DIM</code>
                </div>
              </div>

              {/* Index management card */}
              <div className="card">
                <div className="card-header">
                  <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-3)' }}>
                    <Database size={24} style={{ color: 'var(--primary)' }} />
                    <div>
                      <h2 className="card-title">Index Management</h2>
                      <p className="card-description">View and create OpenSearch project indices</p>
                    </div>
                  </div>
                </div>

                {/* Create index */}
                <div style={{ display: 'flex', gap: 'var(--spacing-2)', marginBottom: 'var(--spacing-4)' }}>
                  <input type="text" className="form-input" style={{ flex: 1 }}
                    placeholder="my-new-index"
                    value={osIndexInput}
                    onChange={e => setOsIndexInput(e.target.value.toLowerCase().replace(/[^a-z0-9_\-]/g, ''))} />
                  <Button variant="primary" onClick={createIndex} disabled={creatingIndex || !osIndexInput.trim() || osHealth?.status !== 'ok'}>
                    {creatingIndex ? <Loader2 size={16} className="animate-spin" /> : <Plus size={16} />}
                    Create Index
                  </Button>
                </div>
                <p style={{ fontSize: 'var(--text-xs)', color: 'var(--gray-400)', marginBottom: 'var(--spacing-4)' }}>
                  Creates an index with knn_vector mapping matching the configured embedding dimension ({osSettings?.embedding_dim || 384} dims).
                  You can then reference this index when creating a project.
                </p>

                {/* Index list */}
                {osIndices.length === 0 ? (
                  <div style={{ textAlign: 'center', padding: 'var(--spacing-6)', color: 'var(--gray-400)', fontSize: 'var(--text-sm)' }}>
                    {osHealth?.status === 'ok' ? 'No project indices found — create one above or via a project.' : 'Connect to OpenSearch to view indices.'}
                  </div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-2)' }}>
                    {osIndices.map(idx => (
                      <div key={idx.index} style={{
                        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                        padding: 'var(--spacing-3)', background: 'var(--gray-50)', borderRadius: 'var(--radius)',
                        border: '1px solid var(--border)'
                      }}>
                        <code style={{ fontSize: 'var(--text-sm)', color: 'var(--gray-800)' }}>{idx.index}</code>
                        <div style={{ display: 'flex', gap: 'var(--spacing-4)', fontSize: 'var(--text-xs)', color: 'var(--gray-500)' }}>
                          {idx.docs_count != null && <span>{idx.docs_count} docs</span>}
                          {idx.store_size && <span>{idx.store_size}</span>}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </>
          )}

          {/* ── API Token Tab ──────────────────────────────────────────────── */}
          {activeTab === 'api-token' && (
            <>
              <div className="card" style={{ marginBottom: 'var(--spacing-6)' }}>
                <div className="card-header">
                  <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-3)' }}>
                    <KeyRound size={24} style={{ color: 'var(--primary)' }} />
                    <div>
                      <h2 className="card-title">API Token</h2>
                      <p className="card-description">
                        Generate a token to call this API from an external app (e.g. agentragio.io integrations).
                      </p>
                    </div>
                  </div>
                </div>

                <div style={{
                  display: 'flex', alignItems: 'flex-start', gap: 'var(--spacing-2)',
                  padding: 'var(--spacing-3)', borderRadius: 'var(--radius)', marginBottom: 'var(--spacing-4)',
                  background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.3)'
                }}>
                  <ShieldAlert size={18} style={{ color: '#b45309', flexShrink: 0, marginTop: '2px' }} />
                  <span style={{ fontSize: 'var(--text-sm)', color: '#92400e' }}>
                    Treat this token like a password. It grants full API access as <strong>{user?.username}</strong>.
                    Expiry is set by the backend (<code>ACCESS_TOKEN_EXPIRE_MINUTES</code> / <code>REFRESH_TOKEN_EXPIRE_DAYS</code>) —
                    the exact dates below are read directly from the generated token once you create one. Never commit it to a repo or CI logs.
                  </span>
                </div>

                {/* Password confirmation → generate */}
                <form onSubmit={generateApiToken} style={{ display: 'flex', gap: 'var(--spacing-2)', marginBottom: 'var(--spacing-2)' }}>
                  <input
                    type="password"
                    className="form-input"
                    style={{ flex: 1 }}
                    placeholder="Confirm your password to generate a token"
                    value={tokenPassword}
                    onChange={e => setTokenPassword(e.target.value)}
                    autoComplete="current-password"
                  />
                  <Button type="submit" variant="primary" icon={KeyRound} loading={tokenLoading} disabled={!tokenPassword}>
                    Generate Token
                  </Button>
                </form>
                <p style={{ fontSize: 'var(--text-xs)', color: 'var(--gray-400)' }}>
                  Re-entering your password confirms the request. It is sent once over HTTPS to <code>/api/auth/login</code> and never stored.
                </p>
              </div>

              {apiToken && (
                <div className="card" style={{ marginBottom: 'var(--spacing-6)' }}>
                  <div className="card-header">
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <div>
                        <h2 className="card-title">Generated Credentials</h2>
                        <p className="card-description">Copy and store these securely — the access token will not be shown again after you leave this page.</p>
                      </div>
                      <Button variant="ghost" onClick={revokeApiToken}>Clear</Button>
                    </div>
                  </div>

                  {/* Access token */}
                  <div style={{ marginBottom: 'var(--spacing-4)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                      <label className="form-label" style={{ margin: 0 }}>Access Token</label>
                      {apiToken.accessExp && (
                        <span style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: 'var(--text-xs)', color: 'var(--gray-500)' }}>
                          <Clock size={12} /> expires {apiToken.accessExp.toLocaleString()}
                        </span>
                      )}
                    </div>
                    <div style={{ display: 'flex', gap: 'var(--spacing-2)' }}>
                      <input
                        readOnly
                        type={showAccessToken ? 'text' : 'password'}
                        className="form-input"
                        style={{ flex: 1, fontFamily: 'monospace', fontSize: 'var(--text-xs)' }}
                        value={apiToken.access_token}
                        onFocus={e => e.target.select()}
                      />
                      <Button variant="ghost" onClick={() => setShowAccessToken(s => !s)}>
                        {showAccessToken ? <EyeOff size={16} /> : <Eye size={16} />}
                      </Button>
                      <Button variant="ghost" onClick={() => copyToClipboard(apiToken.access_token, 'access')}>
                        {copiedField === 'access' ? <CheckCircle size={16} style={{ color: 'var(--success)' }} /> : <Copy size={16} />}
                      </Button>
                    </div>
                  </div>

                  {/* Refresh token */}
                  <div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                      <label className="form-label" style={{ margin: 0 }}>Refresh Token</label>
                      {apiToken.refreshExp && (
                        <span style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: 'var(--text-xs)', color: 'var(--gray-500)' }}>
                          <Clock size={12} /> expires {apiToken.refreshExp.toLocaleString()}
                        </span>
                      )}
                    </div>
                    <div style={{ display: 'flex', gap: 'var(--spacing-2)' }}>
                      <input
                        readOnly
                        type={showRefreshToken ? 'text' : 'password'}
                        className="form-input"
                        style={{ flex: 1, fontFamily: 'monospace', fontSize: 'var(--text-xs)' }}
                        value={apiToken.refresh_token}
                        onFocus={e => e.target.select()}
                      />
                      <Button variant="ghost" onClick={() => setShowRefreshToken(s => !s)}>
                        {showRefreshToken ? <EyeOff size={16} /> : <Eye size={16} />}
                      </Button>
                      <Button variant="ghost" onClick={() => copyToClipboard(apiToken.refresh_token, 'refresh')}>
                        {copiedField === 'refresh' ? <CheckCircle size={16} style={{ color: 'var(--success)' }} /> : <Copy size={16} />}
                      </Button>
                    </div>
                    <p style={{ fontSize: 'var(--text-xs)', color: 'var(--gray-400)', marginTop: '4px' }}>
                      Use it against <code>POST /api/auth/refresh</code> to obtain a new access token without re-entering your password.
                    </p>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </Layout>
  );
};

export default Settings;