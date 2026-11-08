import { useState } from 'react';
import { Plus } from 'lucide-react';
import Button from '../../../components/common/Button';
import Alert from '../../../components/common/Alert';
import api from '../../../services/api';

// ─────────────────────────────────────────────────────────────────────────────
// HOSTS TAB
// ─────────────────────────────────────────────────────────────────────────────
// Protocol registry — single source of truth for the Hosts tab (labels, defaults, credential types)
const HOST_PROTOCOLS = {
  ssh:   { label: 'SSH',      icon: '🐧', color: '#6366f1', defaultPort: 22,   defaultCred: 'key',      namePh: 'linux-01',   userPh: 'debian',
           credTypes: [['key', 'SSH key'], ['password', 'Password'], ['key+passphrase', 'SSH key + passphrase']] },
  winrm: { label: 'WinRM',    icon: '🪟', color: '#0ea5e9', defaultPort: 5985, defaultCred: 'ntlm',     namePh: 'win-01',     userPh: 'Administrator',
           credTypes: [['ntlm', 'NTLM'], ['kerberos', 'Kerberos'], ['password', 'Password']] },
  psrp:  { label: 'PSRP',     icon: '⚡', color: '#14b8a6', defaultPort: 5985, defaultCred: 'ntlm',     namePh: 'win-psrp-01', userPh: 'Administrator',
           credTypes: [['ntlm', 'NTLM'], ['negotiate', 'Negotiate'], ['kerberos', 'Kerberos'], ['credssp', 'CredSSP'], ['password', 'Password (basic)']] },
  db:    { label: 'Database', icon: '🗄️', color: '#f59e0b', defaultPort: null, defaultCred: 'password', namePh: 'mysql-prod', userPh: 'monitor',
           credTypes: [['password', 'Password']] },
};
const DB_TYPES = {
  mysql:      { label: 'MySQL',          port: 3306 },
  mariadb:    { label: 'MariaDB',        port: 3306 },
  postgresql: { label: 'PostgreSQL',     port: 5432 },
  mssql:      { label: 'SQL Server',     port: 1433 },
};
const PSRP_AUTH_METHODS = ['negotiate', 'ntlm', 'kerberos', 'basic', 'credssp'];
const PSRP_AUTH_CRED_TYPES = ['ntlm', 'negotiate', 'kerberos', 'credssp'];   // credential_type that maps 1:1 to a transport
const hostDefaultPort = (h) => h.port || (h.protocol === 'db' ? DB_TYPES[h.db_type]?.port : HOST_PROTOCOLS[h.protocol]?.defaultPort);

const EMPTY_HOST_FORM = {
  name: '', protocol: 'ssh', host: '', port: '', username: '', credential_type: 'key', password: '', key_content: '', key_passphrase: '',
  winrm_transport: 'ntlm', winrm_server_cert_validation: 'ignore', db_type: 'mysql', db_name: '', tags: '', notes: ''
};

const HostsTab = ({ hosts, onRefresh }) => {
  const [showAddModal, setShowAddModal] = useState(false);
  const [editHost, setEditHost] = useState(null);
  const [testResults, setTestResults] = useState({});
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [form, setForm] = useState(EMPTY_HOST_FORM);

  const resetForm = () => setForm(EMPTY_HOST_FORM);
  const openAdd = () => { resetForm(); setEditHost(null); setShowAddModal(true); };
  const openEdit = (h) => {
    setForm({ name: h.name, protocol: h.protocol, host: h.host, port: h.port || '', username: h.username, credential_type: h.credential_type, password: '', key_content: '', key_passphrase: '', winrm_transport: h.winrm_transport || 'ntlm', winrm_server_cert_validation: h.winrm_server_cert_validation || 'ignore', db_type: h.db_type || 'mysql', db_name: h.db_name || '', tags: (h.tags || []).join(', '), notes: h.notes || '' });
    setEditHost(h); setShowAddModal(true);
  };

  const changeProtocol = (p) => setForm({ ...form, protocol: p, credential_type: HOST_PROTOCOLS[p].defaultCred, winrm_transport: 'ntlm', port: '' });
  const changeCredentialType = (v) => setForm({ ...form, credential_type: v, ...(form.protocol === 'psrp' && PSRP_AUTH_CRED_TYPES.includes(v) ? { winrm_transport: v } : {}) });

  const isWindowsProto = form.protocol === 'winrm' || form.protocol === 'psrp';
  // Password input: db always; psrp unless Kerberos; ssh/winrm keep the historical rule
  const showPassword = form.protocol === 'db'
    || (form.protocol === 'psrp' ? form.winrm_transport !== 'kerberos' : (form.credential_type === 'password' || form.credential_type === 'ntlm'));
  // Backend requires a password when creating psrp (non-Kerberos) and db hosts
  const passwordRequired = !editHost && showPassword && (form.protocol === 'db' || form.protocol === 'psrp');
  const portPlaceholder = String((form.protocol === 'db' ? DB_TYPES[form.db_type]?.port : HOST_PROTOCOLS[form.protocol]?.defaultPort) || '');

  const handleSave = async () => {
    try {
      const payload = { name: form.name, protocol: form.protocol, host: form.host, port: form.port ? parseInt(form.port) : undefined, username: form.username, credential_type: form.credential_type, tags: form.tags ? form.tags.split(',').map(t => t.trim()).filter(Boolean) : [], notes: form.notes || undefined };
      if (form.password) payload.password = form.password;
      if (form.key_content) payload.key_content = form.key_content;
      if (form.key_passphrase) payload.key_passphrase = form.key_passphrase;
      if (isWindowsProto) { payload.winrm_transport = form.winrm_transport; payload.winrm_server_cert_validation = form.winrm_server_cert_validation; }
      if (form.protocol === 'db') { payload.db_type = form.db_type; if (form.db_name) payload.db_name = form.db_name; }
      if (editHost) { await api.put(`/api/hosts/${editHost.id}`, payload); setSuccess('Host updated successfully'); }
      else { await api.post('/api/hosts/', payload); setSuccess('Host added successfully'); }
      setShowAddModal(false); resetForm(); onRefresh(); setTimeout(() => setSuccess(null), 3000);
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(Array.isArray(detail) ? detail.map(d => d.msg).join(' · ') : (detail || 'Failed to save host'));
    }
  };

  const handleTest = async (hostId) => {
    setTestResults(prev => ({ ...prev, [hostId]: 'testing' }));
    try { const res = await api.post(`/api/hosts/${hostId}/test`); setTestResults(prev => ({ ...prev, [hostId]: res.data })); }
    catch (err) { setTestResults(prev => ({ ...prev, [hostId]: { success: false, error: err.response?.data?.detail || 'Test failed' } })); }
  };

  const handleDelete = async (hostId, name) => {
    if (!confirm(`Delete host "${name}"?`)) return;
    try { await api.delete(`/api/hosts/${hostId}`); setSuccess('Host deleted'); onRefresh(); setTimeout(() => setSuccess(null), 2000); }
    catch (err) { setError(err.response?.data?.detail || 'Failed to delete host'); }
  };

  const protocolIcon = (p) => HOST_PROTOCOLS[p]?.icon || '🖥️';

  return (
    <div>
      {error && <Alert type="error" style={{ marginBottom: 'var(--spacing-4)' }} onClose={() => setError(null)}>{error}</Alert>}
      {success && <Alert type="success" style={{ marginBottom: 'var(--spacing-4)' }} onClose={() => setSuccess(null)}>{success}</Alert>}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--spacing-4)' }}>
        <p style={{ fontSize: 'var(--text-sm)', color: 'var(--gray-600)' }}>{hosts.length} host{hosts.length !== 1 ? 's' : ''} registered · credentials stored encrypted</p>
        <Button variant="primary" onClick={openAdd} icon={Plus}>Add host</Button>
      </div>
      {hosts.length === 0 ? (
        <div style={{ textAlign: 'center', padding: 'var(--spacing-10)', color: 'var(--gray-600)' }}>
          <div style={{ fontSize: '2.5rem', marginBottom: 'var(--spacing-3)' }}>🖥️</div>
          <p style={{ marginBottom: 'var(--spacing-3)' }}>No hosts registered yet</p>
          <Button variant="primary" onClick={openAdd} icon={Plus}>Add your first host</Button>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-2)' }}>
          {hosts.map(h => {
            const tr = testResults[h.id];
            return (
              <div key={h.id} style={{ display: 'grid', gridTemplateColumns: '28px 1fr auto auto', alignItems: 'center', gap: 'var(--spacing-3)', padding: 'var(--spacing-3) var(--spacing-4)', background: 'var(--bg-card)', border: '1px solid var(--gray-200)', borderLeft: `3px solid ${HOST_PROTOCOLS[h.protocol]?.color || '#6366f1'}`, borderRadius: 'var(--radius-md)', opacity: h.is_active ? 1 : 0.6 }}>
                <div style={{ fontSize: '18px', textAlign: 'center' }}>{protocolIcon(h.protocol)}</div>
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontWeight: '600', fontSize: 'var(--text-sm)' }}>{h.name}</div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-2)', flexWrap: 'wrap', marginTop: '3px' }}>
                    <span style={{ fontSize: 'var(--text-xs)', color: 'var(--gray-600)' }}>{h.host}:{hostDefaultPort(h) || '—'}</span>
                    <span style={{ fontSize: '10px', padding: '1px 6px', borderRadius: '99px', background: 'var(--gray-200)', color: 'var(--gray-700)' }}>{h.protocol}</span>
                    {h.protocol === 'db' && h.db_type && <span style={{ fontSize: '10px', padding: '1px 6px', borderRadius: '99px', background: 'var(--gray-200)', color: 'var(--gray-700)' }}>{h.db_type}{h.db_name ? `/${h.db_name}` : ''}</span>}
                    <span style={{ fontSize: '10px', padding: '1px 6px', borderRadius: '99px', background: 'var(--gray-200)', color: 'var(--gray-700)' }}>{h.credential_type}</span>
                    {(h.tags || []).map(tag => <span key={tag} style={{ fontSize: '10px', padding: '1px 6px', borderRadius: '99px', background: 'var(--gray-200)', color: 'var(--gray-700)' }}>{tag}</span>)}
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', fontSize: '11px', color: h.is_active ? 'var(--success)' : 'var(--gray-500)' }}>
                      <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: h.is_active ? 'var(--success)' : 'var(--gray-400)', display: 'inline-block' }} />
                      {h.is_active ? 'active' : 'inactive'}
                    </span>
                    {h.last_connected && <span style={{ fontSize: '11px', color: 'var(--gray-600)' }}>last: {new Date(h.last_connected).toLocaleString()}</span>}
                  </div>
                  {tr && tr !== 'testing' && (
                    <div style={{ marginTop: '4px', fontSize: '11px', padding: '2px 8px', borderRadius: '3px', display: 'inline-block', background: tr.success ? 'rgba(52,211,153,.15)' : 'rgba(248,113,113,.15)', color: tr.success ? 'var(--success-dark)' : 'var(--danger-dark)' }}>
                      {tr.success ? `✓ OK ${tr.latency_ms}ms` : `✗ ${tr.error}`}
                    </div>
                  )}
                  {tr === 'testing' && <div style={{ marginTop: '4px', fontSize: '11px', color: 'var(--gray-600)' }}>Testing connection…</div>}
                </div>
                <div style={{ fontSize: '11px', color: 'var(--gray-600)' }}>{h.username}@{h.host}</div>
                <div style={{ display: 'flex', gap: '4px' }}>
                  {[{ label: 'Test', action: () => handleTest(h.id), color: 'var(--info)' }, { label: '✎', action: () => openEdit(h), color: 'var(--gray-600)' }, { label: '✕', action: () => handleDelete(h.id, h.name), color: 'var(--danger)' }].map(btn => (
                    <button key={btn.label} onClick={btn.action} style={{ width: '28px', height: '28px', borderRadius: 'var(--radius)', border: '1px solid var(--gray-300)', background: 'var(--gray-100)', color: btn.color, cursor: 'pointer', fontSize: '12px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>{btn.label}</button>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {showAddModal && (
        <div style={{ position: 'fixed', inset: 0, backgroundColor: 'var(--overlay)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1100, padding: 'var(--spacing-4)' }}>
          <div className="card" style={{ width: '100%', maxWidth: '640px', maxHeight: '90vh', overflow: 'auto' }}>
            <h2 style={{ fontSize: 'var(--text-xl)', fontWeight: '600', marginBottom: 'var(--spacing-4)' }}>{editHost ? `Edit host — ${editHost.name}` : 'Add remote host'}</h2>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--spacing-3)', marginBottom: 'var(--spacing-3)' }}>
              <div className="form-group"><label className="form-label">Host name *</label><input type="text" className="form-input" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} placeholder={HOST_PROTOCOLS[form.protocol].namePh} disabled={!!editHost} /></div>
              <div className="form-group">
                <label className="form-label">Protocol *</label>
                <select className="form-input" value={form.protocol} onChange={e => changeProtocol(e.target.value)} disabled={!!editHost}>
                  {Object.entries(HOST_PROTOCOLS).map(([key, p]) => <option key={key} value={key}>{p.label}</option>)}
                </select>
              </div>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: 'var(--spacing-3)', marginBottom: 'var(--spacing-3)' }}>
              <div className="form-group"><label className="form-label">IP / Hostname *</label><input type="text" className="form-input" value={form.host} onChange={e => setForm({ ...form, host: e.target.value })} placeholder="192.168.1.85" /></div>
              <div className="form-group" style={{ width: '100px' }}><label className="form-label">Port</label><input type="number" className="form-input" value={form.port} onChange={e => setForm({ ...form, port: e.target.value })} placeholder={portPlaceholder} /></div>
            </div>
            {form.protocol === 'db' && (
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--spacing-3)', marginBottom: 'var(--spacing-3)' }}>
                <div className="form-group">
                  <label className="form-label">Database engine *</label>
                  <select className="form-input" value={form.db_type} onChange={e => setForm({ ...form, db_type: e.target.value })}>
                    {Object.entries(DB_TYPES).map(([key, t]) => <option key={key} value={key}>{t.label}</option>)}
                  </select>
                </div>
                <div className="form-group"><label className="form-label">Default database <span style={{ color: 'var(--gray-500)', fontSize: 'var(--text-xs)' }}>(optional)</span></label><input type="text" className="form-input" value={form.db_name} onChange={e => setForm({ ...form, db_name: e.target.value })} placeholder="appdb" /></div>
              </div>
            )}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--spacing-3)', marginBottom: 'var(--spacing-3)' }}>
              <div className="form-group"><label className="form-label">Username *</label><input type="text" className="form-input" value={form.username} onChange={e => setForm({ ...form, username: e.target.value })} placeholder={HOST_PROTOCOLS[form.protocol].userPh} /></div>
              <div className="form-group">
                <label className="form-label">Credential type *</label>
                <select className="form-input" value={form.credential_type} onChange={e => changeCredentialType(e.target.value)}>
                  {HOST_PROTOCOLS[form.protocol].credTypes.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                </select>
              </div>
            </div>
            {form.protocol === 'ssh' && (form.credential_type === 'key' || form.credential_type === 'key+passphrase') && (
              <div className="form-group" style={{ marginBottom: 'var(--spacing-3)' }}>
                <label className="form-label">SSH private key (PEM) {editHost ? '— leave empty to keep current' : '*'}</label>
                <textarea className="form-input" rows={4} value={form.key_content} onChange={e => setForm({ ...form, key_content: e.target.value })} placeholder="-----BEGIN OPENSSH PRIVATE KEY-----&#10;...&#10;-----END OPENSSH PRIVATE KEY-----" />
              </div>
            )}
            {form.credential_type === 'key+passphrase' && (
              <div className="form-group" style={{ marginBottom: 'var(--spacing-3)' }}>
                <label className="form-label">Key passphrase</label>
                <input type="password" className="form-input" value={form.key_passphrase} onChange={e => setForm({ ...form, key_passphrase: e.target.value })} placeholder="Passphrase for private key" />
              </div>
            )}
            {showPassword && (
              <div className="form-group" style={{ marginBottom: 'var(--spacing-3)' }}>
                <label className="form-label">Password {editHost ? '— leave empty to keep current' : (passwordRequired ? '*' : '')}</label>
                <input type="password" className="form-input" value={form.password} onChange={e => setForm({ ...form, password: e.target.value })} placeholder="Password" autoComplete="new-password" />
              </div>
            )}
            {isWindowsProto && (
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--spacing-3)', marginBottom: 'var(--spacing-3)' }}>
                <div className="form-group">
                  <label className="form-label">{form.protocol === 'psrp' ? 'PSRP auth method' : 'WinRM transport'}</label>
                  <select className="form-input" value={form.winrm_transport} onChange={e => setForm({ ...form, winrm_transport: e.target.value })}>
                    {(form.protocol === 'psrp' ? PSRP_AUTH_METHODS : ['ntlm', 'basic', 'kerberos']).map(t => <option key={t} value={t}>{t}</option>)}
                  </select>
                </div>
                <div className="form-group"><label className="form-label">Certificate validation</label><select className="form-input" value={form.winrm_server_cert_validation} onChange={e => setForm({ ...form, winrm_server_cert_validation: e.target.value })}><option value="ignore">ignore</option><option value="validate">validate</option></select></div>
              </div>
            )}
            <div className="form-group" style={{ marginBottom: 'var(--spacing-3)' }}>
              <label className="form-label">Tags <span style={{ color: 'var(--gray-500)', fontSize: 'var(--text-xs)' }}>(comma-separated)</span></label>
              <input type="text" className="form-input" value={form.tags} onChange={e => setForm({ ...form, tags: e.target.value })} placeholder={form.protocol === 'db' ? 'db, mysql, prod' : 'linux, prod, web'} />
            </div>
            <div className="form-group" style={{ marginBottom: 'var(--spacing-4)' }}>
              <label className="form-label">Notes</label>
              <textarea className="form-input" rows={2} value={form.notes} onChange={e => setForm({ ...form, notes: e.target.value })} placeholder="Optional notes about this host" />
            </div>
            <div style={{ padding: 'var(--spacing-3)', border: '1px solid var(--warning)', borderLeft: '3px solid var(--warning)', borderRadius: 'var(--radius)', backgroundColor: 'rgba(251,191,36,0.06)', marginBottom: 'var(--spacing-4)', fontSize: 'var(--text-xs)', color: 'var(--gray-700)', lineHeight: '1.6' }}>
              <strong style={{ color: 'var(--warning-dark)' }}>🔒 Credentials are encrypted immediately</strong> and never returned in API responses. After saving, use the <strong>Test</strong> button to verify connectivity.
              {form.protocol === 'db' && <> Use a dedicated least-privilege database account: read-only statements are enforced by the MCP, but the account grants are the real safeguard.</>}
            </div>
            <div style={{ display: 'flex', gap: 'var(--spacing-3)', justifyContent: 'flex-end', paddingTop: 'var(--spacing-4)', borderTop: '1px solid var(--gray-200)' }}>
              <Button variant="ghost" onClick={() => { setShowAddModal(false); resetForm(); }}>Cancel</Button>
              <Button variant="primary" onClick={handleSave} disabled={!form.name || !form.host || !form.username || (passwordRequired && !form.password)}>{editHost ? 'Update host' : 'Save host'}</Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default HostsTab;
