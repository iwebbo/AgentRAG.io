import { useState, useEffect } from 'react';
import { User, Save, Search, CheckCircle, XCircle, Plus, RefreshCw, Loader2, Database } from 'lucide-react';
import Layout from '../components/layout/Layout';
import Button from '../components/common/Button';
import Alert from '../components/common/Alert';
import { useAuthStore } from '../store/authStore';
import api from '../services/api';

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
        </div>
      </div>
    </Layout>
  );
};

export default Settings;