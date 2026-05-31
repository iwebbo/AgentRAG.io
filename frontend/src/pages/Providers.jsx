import { useState, useEffect } from 'react';
import { Plus, Trash2, ExternalLink, Activity } from 'lucide-react';
import Layout from '../components/layout/Layout';
import Alert from '../components/common/Alert';
import Loading from '../components/common/Loading';
import api from '../services/api';

// ── Provider catalogue ────────────────────────────────────────────────────────
const PROVIDER_CONFIG = [
  { value: 'openai',      label: 'OpenAI',                        category: 'cloud', requiresKey: true,  defaultUrl: null,                                   keyHint: 'sk-...' },
  { value: 'claude',      label: 'Anthropic Claude',              category: 'cloud', requiresKey: true,  defaultUrl: null,                                   keyHint: 'sk-ant-...' },
  { value: 'gemini',      label: 'Google Gemini',                 category: 'cloud', requiresKey: true,  defaultUrl: null,                                   keyHint: 'AIzaSy...',  link: 'https://aistudio.google.com/app/apikey' },
  { value: 'huggingface', label: 'HuggingFace Inference',         category: 'cloud', requiresKey: true,  defaultUrl: 'https://api-inference.huggingface.co', keyHint: 'hf_...',     link: 'https://huggingface.co/settings/tokens' },
  { value: 'grok',        label: 'xAI Grok',                      category: 'cloud', requiresKey: true,  defaultUrl: 'https://api.x.ai/v1',                  keyHint: 'xai-...',    link: 'https://console.x.ai',            note: '$25 free credit · grok-3 recommended' },
  { value: 'openrouter',  label: 'OpenRouter',                    category: 'cloud', requiresKey: true,  defaultUrl: 'https://openrouter.ai/api/v1',          keyHint: 'sk-or-...',  link: 'https://openrouter.ai/keys',      note: '100+ free models' },
  { value: 'groq',        label: 'Groq',                          category: 'cloud', requiresKey: true,  defaultUrl: 'https://api.groq.com/openai/v1',        keyHint: 'gsk_...',    link: 'https://console.groq.com/keys',   note: 'Llama 3.2 90B — ultra fast' },
  { value: 'ollama',      label: 'Ollama',                        category: 'local', requiresKey: false, defaultUrl: 'http://localhost:11434' },
  { value: 'lmstudio',    label: 'LM Studio',                     category: 'local', requiresKey: false, defaultUrl: 'http://localhost:1234/v1' },
  { value: 'localai',     label: 'LocalAI',                       category: 'local', requiresKey: false, defaultUrl: 'http://localhost:8080/v1' },
  { value: 'oobabooga',   label: 'Text Generation WebUI',         category: 'local', requiresKey: false, defaultUrl: 'http://localhost:5000/v1' },
  { value: 'vllm',        label: 'vLLM',                          category: 'local', requiresKey: false, defaultUrl: 'http://localhost:8000/v1' },
  { value: 'lmdeploy',    label: 'LMDeploy / OpenXLab',           category: 'local', requiresKey: false, defaultUrl: 'http://localhost:23333/v1' },
];

// ── Helpers ───────────────────────────────────────────────────────────────────
const getConfig = (name) => PROVIDER_CONFIG.find(p => p.value === name) || null;
const getLabel  = (name) => getConfig(name)?.label || name.toUpperCase();
const getInitials = (name) => (getConfig(name)?.label || name).slice(0, 3).toUpperCase();
const stripProtocol = (url) => (url || '').replace(/^https?:\/\//, '');

const isLocal = (provider) =>
  getConfig(provider.name)?.category === 'local' ||
  (provider.base_url || '').includes('localhost') ||
  (provider.base_url || '').includes('127.0.0.1');

// ── Sub-components ────────────────────────────────────────────────────────────

const Badge = ({ children, variant = 'default' }) => {
  const styles = {
    active:   { background: '#EAF3DE', color: '#27500A', border: '0.5px solid #97C459' },
    inactive: { background: '#F1EFE8', color: '#5F5E5A', border: '0.5px solid #B4B2A9' },
    key:      { background: '#EEEDFE', color: '#3C3489', border: '0.5px solid #AFA9EC' },
    local:    { background: '#E1F5EE', color: '#085041', border: '0.5px solid #5DCAA5' },
    default:  { background: 'var(--gray-100)', color: 'var(--gray-600)', border: '0.5px solid var(--gray-200)' },
  };
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: '4px',
      padding: '3px 8px', borderRadius: '20px',
      fontSize: '11px', fontWeight: '500',
      ...styles[variant],
    }}>
      {children}
    </span>
  );
};

const Toggle = ({ checked, onChange, disabled }) => (
  <button
    type="button"
    onClick={onChange}
    disabled={disabled}
    title={checked ? 'Disable provider' : 'Enable provider'}
    style={{
      width: '32px', height: '18px',
      borderRadius: '9px',
      background: checked ? '#639922' : 'var(--gray-300)',
      border: 'none',
      position: 'relative',
      cursor: disabled ? 'not-allowed' : 'pointer',
      transition: 'background 0.15s',
      flexShrink: 0,
      padding: 0,
    }}
  >
    <span style={{
      position: 'absolute',
      top: '3px',
      left: checked ? '17px' : '3px',
      width: '12px', height: '12px',
      borderRadius: '50%',
      background: 'white',
      transition: 'left 0.15s',
      display: 'block',
    }} />
  </button>
);

const SectionLabel = ({ children }) => (
  <div style={{
    fontSize: '11px', fontWeight: '500',
    color: 'var(--gray-400)',
    letterSpacing: '0.06em',
    textTransform: 'uppercase',
    marginBottom: '10px',
    marginTop: '1.75rem',
  }}>
    {children}
  </div>
);

// ── Provider Card ─────────────────────────────────────────────────────────────
const ProviderCard = ({ provider, onDelete, onTest, onToggle, testing }) => {
  const cfg     = getConfig(provider.name);
  const active  = provider.is_active;
  const local   = isLocal(provider);
  const url     = stripProtocol(provider.base_url);

  return (
    <div
      style={{
        background: 'var(--bg-card)',
        border: '1px solid var(--gray-200)',
        borderRadius: 'var(--radius-lg)',
        padding: '1rem 1.1rem',
        display: 'flex',
        flexDirection: 'column',
        gap: '12px',
        opacity: active ? 1 : 0.65,
        transition: 'border-color 0.15s, opacity 0.15s',
      }}
      onMouseEnter={e => { if (active) e.currentTarget.style.borderColor = 'var(--gray-300)'; }}
      onMouseLeave={e => e.currentTarget.style.borderColor = 'var(--gray-200)'}
    >
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', gap: '9px', alignItems: 'center', minWidth: 0 }}>
          {/* Avatar */}
          <div style={{
            width: '32px', height: '32px', flexShrink: 0,
            borderRadius: 'var(--radius)',
            background: 'var(--gray-100)',
            border: '1px solid var(--gray-200)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: '10px', fontWeight: '600',
            color: 'var(--gray-600)',
            letterSpacing: '0.02em',
          }}>
            {getInitials(provider.name)}
          </div>
          <div style={{ minWidth: 0 }}>
            <div style={{
              fontSize: '13px', fontWeight: '600',
              color: 'var(--gray-900)',
              overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
            }}>
              {getLabel(provider.name)}
            </div>
            {url && (
              <div style={{
                fontSize: '11px',
                color: 'var(--gray-400)',
                fontFamily: 'monospace',
                overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                maxWidth: '180px',
                marginTop: '1px',
              }}>
                {url}
              </div>
            )}
          </div>
        </div>
        {/* Delete */}
        <button
          onClick={() => onDelete(provider.id)}
          style={{
            padding: '4px', background: 'none', border: 'none',
            cursor: 'pointer', color: 'var(--gray-400)',
            borderRadius: '6px', flexShrink: 0,
            transition: 'all 0.12s',
          }}
          onMouseEnter={e => { e.currentTarget.style.color = 'var(--danger)'; e.currentTarget.style.background = 'rgba(239,68,68,0.08)'; }}
          onMouseLeave={e => { e.currentTarget.style.color = 'var(--gray-400)'; e.currentTarget.style.background = 'none'; }}
          title="Delete provider"
        >
          <Trash2 size={13} />
        </button>
      </div>

      {/* Badges */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '5px', alignItems: 'center' }}>
        <Badge variant={active ? 'active' : 'inactive'}>
          <span style={{
            width: '5px', height: '5px', borderRadius: '50%',
            background: active ? '#639922' : '#B4B2A9',
            flexShrink: 0,
          }} />
          {active ? 'Active' : 'Inactive'}
        </Badge>
        {cfg?.requiresKey
          ? <Badge variant="key">API key</Badge>
          : <Badge variant="local">Local</Badge>
        }
        <Badge>P {provider.priority}</Badge>
        {cfg?.note && (
          <span style={{ fontSize: '11px', color: 'var(--gray-400)', fontStyle: 'italic' }}>
            {cfg.note}
          </span>
        )}
      </div>

      {/* Actions */}
      <div style={{
        display: 'flex', gap: '6px',
        paddingTop: '8px',
        borderTop: '1px solid var(--gray-100)',
      }}>
        {/* Test button */}
        <button
          onClick={() => onTest(provider.id)}
          disabled={testing || !active}
          style={{
            flex: 1,
            display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
            gap: '5px',
            height: '28px',
            borderRadius: 'var(--radius)',
            border: '1px solid var(--gray-200)',
            background: 'transparent',
            fontSize: '12px', color: 'var(--gray-600)',
            cursor: (testing || !active) ? 'not-allowed' : 'pointer',
            opacity: (testing || !active) ? 0.45 : 1,
            transition: 'all 0.12s',
          }}
          onMouseEnter={e => { if (!testing && active) { e.currentTarget.style.background = 'var(--gray-50)'; e.currentTarget.style.color = 'var(--gray-900)'; } }}
          onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = 'var(--gray-600)'; }}
        >
          {testing
            ? <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ animation: 'spin 1s linear infinite' }}><path d="M21 12a9 9 0 11-6.219-8.56"/></svg>
            : <Activity size={11} />
          }
          {testing ? 'Testing…' : 'Test'}
        </button>

        {/* Toggle */}
        <Toggle
          checked={active}
          onChange={() => onToggle(provider)}
        />
      </div>
    </div>
  );
};

// ── Main component ────────────────────────────────────────────────────────────
const Providers = () => {
  const [providers, setProviders]     = useState([]);
  const [loading, setLoading]         = useState(true);
  const [showModal, setShowModal]     = useState(false);
  const [testing, setTesting]         = useState({});
  const [alert, setAlert]             = useState(null);

  const [formData, setFormData] = useState({
    name: 'openai',
    api_key: '',
    base_url: '',
    priority: 50,
    is_active: true,
  });

  const selectedConfig = getConfig(formData.name) || PROVIDER_CONFIG[0];

  useEffect(() => {
    setFormData(prev => ({
      ...prev,
      base_url: selectedConfig.defaultUrl || '',
      api_key: '',
    }));
  }, [formData.name]);

  useEffect(() => { loadProviders(); }, []);

  const loadProviders = async () => {
    try {
      const res = await api.get('/api/providers/');
      setProviders(res.data);
    } catch {
      showAlert('error', 'Failed to load providers');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (selectedConfig.requiresKey && !formData.api_key.trim()) {
      showAlert('error', 'API key is required for this provider');
      return;
    }
    const payload = {
      name: formData.name,
      priority: formData.priority,
      is_active: formData.is_active,
    };
    if (selectedConfig.requiresKey) payload.api_key = formData.api_key.trim();
    if (formData.base_url.trim())   payload.base_url = formData.base_url.trim();

    try {
      await api.post('/api/providers/', payload);
      showAlert('success', 'Provider added');
      setShowModal(false);
      resetForm();
      loadProviders();
    } catch (err) {
      showAlert('error', err.response?.data?.detail || 'Failed to add provider');
    }
  };

  const handleDelete = async (id) => {
    if (!confirm('Delete this provider?')) return;
    try {
      await api.delete(`/api/providers/${id}`);
      showAlert('success', 'Provider deleted');
      loadProviders();
    } catch {
      showAlert('error', 'Failed to delete');
    }
  };

  const handleTest = async (id) => {
    setTesting(prev => ({ ...prev, [id]: true }));
    try {
      const res = await api.post(`/api/providers/${id}/test`);
      res.data.success
        ? showAlert('success', `Connected — ${res.data.latency_ms}ms`)
        : showAlert('error', res.data.message || 'Connection failed');
    } catch {
      showAlert('error', 'Connection test failed');
    } finally {
      setTesting(prev => ({ ...prev, [id]: false }));
    }
  };

  const handleToggle = async (provider) => {
    try {
      await api.put(`/api/providers/${provider.id}`, { is_active: !provider.is_active });
      loadProviders();
    } catch {
      showAlert('error', 'Failed to update provider');
    }
  };

  const showAlert = (type, message) => {
    setAlert({ type, message });
    setTimeout(() => setAlert(null), 5000);
  };

  const resetForm = () => {
    setFormData({ name: 'openai', api_key: '', base_url: '', priority: 50, is_active: true });
  };

  if (loading) return <Layout><Loading message="Loading providers..." /></Layout>;

  const cloudProviders = providers.filter(p => !isLocal(p));
  const localProviders = providers.filter(p =>  isLocal(p));
  const activeCount    = providers.filter(p => p.is_active).length;

  return (
    <Layout>
      <div style={{ padding: 'var(--spacing-8) var(--spacing-6)', maxWidth: '1100px', margin: '0 auto' }}>

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
              Providers
            </h1>
            <p style={{ fontSize: 'var(--text-sm)', color: 'var(--gray-500)' }}>
              {providers.length} configured · {activeCount} active
            </p>
          </div>
          <button
            onClick={() => setShowModal(true)}
            style={{
              display: 'inline-flex', alignItems: 'center', gap: '6px',
              padding: '9px 18px',
              background: 'transparent', color: 'white',
              border: 'none', borderRadius: 'var(--radius)',
              fontSize: 'var(--text-sm)', fontWeight: '500',
              cursor: 'pointer', transition: 'opacity 0.15s',
            }}
            onMouseEnter={e => e.currentTarget.style.opacity = '0.85'}
            onMouseLeave={e => e.currentTarget.style.opacity = '1'}
          >
            <Plus size={14} />
            Add provider
          </button>
        </div>

        {/* ── Empty ── */}
        {providers.length === 0 && (
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
              <Plus size={20} />
            </div>
            <div>
              <p style={{ fontWeight: '500', color: 'var(--gray-700)', marginBottom: '4px' }}>No providers configured</p>
              <p style={{ fontSize: 'var(--text-sm)', color: 'var(--gray-500)' }}>Add your first LLM provider to get started</p>
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
              Add provider
            </button>
          </div>
        )}

        {/* ── Cloud section ── */}
        {cloudProviders.length > 0 && (
          <>
            <div style={{
              fontSize: '11px', fontWeight: '500',
              color: 'var(--gray-400)',
              letterSpacing: '0.06em', textTransform: 'uppercase',
              marginBottom: '10px',
            }}>
              Cloud APIs
            </div>
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
              gap: '10px',
              marginBottom: '4px',
            }}>
              {cloudProviders.map(provider => (
                <ProviderCard
                  key={provider.id}
                  provider={provider}
                  onDelete={handleDelete}
                  onTest={handleTest}
                  onToggle={handleToggle}
                  testing={!!testing[provider.id]}
                />
              ))}
            </div>
          </>
        )}

        {/* ── Local section ── */}
        {localProviders.length > 0 && (
          <>
            <div style={{
              fontSize: '11px', fontWeight: '500',
              color: 'var(--gray-400)',
              letterSpacing: '0.06em', textTransform: 'uppercase',
              marginBottom: '10px',
              marginTop: cloudProviders.length > 0 ? '1.75rem' : '0',
            }}>
              Local models
            </div>
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
              gap: '10px',
            }}>
              {localProviders.map(provider => (
                <ProviderCard
                  key={provider.id}
                  provider={provider}
                  onDelete={handleDelete}
                  onTest={handleTest}
                  onToggle={handleToggle}
                  testing={!!testing[provider.id]}
                />
              ))}
            </div>
          </>
        )}

        {/* ══ Modal: Add Provider ══════════════════════════════════════════════ */}
        {showModal && (
          <div style={{
            position: 'fixed', inset: 0,
            backgroundColor: 'rgba(0,0,0,0.4)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            zIndex: 1000, padding: 'var(--spacing-4)',
          }}>
            <div className="card" style={{ width: '100%', maxWidth: '480px', padding: 'var(--spacing-8)' }}>

              <div style={{ marginBottom: 'var(--spacing-6)' }}>
                <h2 style={{ fontSize: 'var(--text-xl)', fontWeight: '600', color: 'var(--gray-900)' }}>
                  Add provider
                </h2>
                <p style={{ fontSize: 'var(--text-sm)', color: 'var(--gray-500)', marginTop: '4px' }}>
                  Configure a new LLM provider
                </p>
              </div>

              <form onSubmit={handleSubmit}>

                {/* Provider select */}
                <div className="form-group">
                  <label className="form-label">Provider</label>
                  <select
                    className="form-select"
                    value={formData.name}
                    onChange={e => setFormData({ ...formData, name: e.target.value })}
                  >
                    <optgroup label="Cloud APIs">
                      {PROVIDER_CONFIG.filter(p => p.category === 'cloud').map(p => (
                        <option key={p.value} value={p.value}>{p.label}</option>
                      ))}
                    </optgroup>
                    <optgroup label="Local models">
                      {PROVIDER_CONFIG.filter(p => p.category === 'local').map(p => (
                        <option key={p.value} value={p.value}>{p.label}</option>
                      ))}
                    </optgroup>
                  </select>
                  {selectedConfig.note && (
                    <p style={{ fontSize: 'var(--text-xs)', color: 'var(--gray-500)', marginTop: '4px' }}>
                      {selectedConfig.note}
                    </p>
                  )}
                </div>

                {/* API Key */}
                {selectedConfig.requiresKey && (
                  <div className="form-group">
                    <label className="form-label">API key</label>
                    <input
                      type="password"
                      className="form-input"
                      placeholder={selectedConfig.keyHint || 'Enter API key'}
                      value={formData.api_key}
                      onChange={e => setFormData({ ...formData, api_key: e.target.value })}
                      required
                    />
                    {selectedConfig.link && (
                      <p style={{ fontSize: 'var(--text-xs)', color: 'var(--gray-500)', marginTop: '4px' }}>
                        Get your key at{' '}
                        <a
                          href={selectedConfig.link}
                          target="_blank"
                          rel="noopener noreferrer"
                          style={{ color: 'var(--primary)', textDecoration: 'none' }}
                        >
                          {selectedConfig.link.replace('https://', '')}
                          <ExternalLink size={10} style={{ display: 'inline', marginLeft: '3px', verticalAlign: 'middle' }} />
                        </a>
                      </p>
                    )}
                  </div>
                )}

                {/* Base URL */}
                <div className="form-group">
                  <label className="form-label">
                    Base URL
                    <span style={{ fontWeight: '400', color: 'var(--gray-400)', marginLeft: '6px' }}>
                      {selectedConfig.defaultUrl ? 'pre-filled' : 'optional'}
                    </span>
                  </label>
                  <input
                    type="url"
                    className="form-input"
                    placeholder={selectedConfig.defaultUrl || 'https://api.example.com/v1'}
                    value={formData.base_url}
                    onChange={e => setFormData({ ...formData, base_url: e.target.value })}
                  />
                </div>

                {/* Priority */}
                <div className="form-group">
                  <label className="form-label" style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span>Priority</span>
                    <span style={{ fontWeight: '400', color: 'var(--gray-500)' }}>{formData.priority}</span>
                  </label>
                  <input
                    type="range"
                    min="0" max="100" step="1"
                    value={formData.priority}
                    onChange={e => setFormData({ ...formData, priority: parseInt(e.target.value) })}
                    style={{ width: '100%' }}
                  />
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: 'var(--gray-400)', marginTop: '2px' }}>
                    <span>0 — low</span>
                    <span>100 — high</span>
                  </div>
                </div>

                {/* Active toggle */}
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 'var(--spacing-4)' }}>
                  <span style={{ fontSize: 'var(--text-sm)', color: 'var(--gray-700)', fontWeight: '500' }}>Enable on creation</span>
                  <button
                    type="button"
                    onClick={() => setFormData(prev => ({ ...prev, is_active: !prev.is_active }))}
                    style={{
                      width: '36px', height: '20px',
                      borderRadius: '10px',
                      background: formData.is_active ? '#639922' : 'var(--gray-300)',
                      border: 'none', padding: 0,
                      position: 'relative', cursor: 'pointer',
                      transition: 'background 0.15s',
                    }}
                  >
                    <span style={{
                      position: 'absolute', top: '4px',
                      left: formData.is_active ? '20px' : '4px',
                      width: '12px', height: '12px',
                      borderRadius: '50%', background: 'white',
                      transition: 'left 0.15s', display: 'block',
                    }} />
                  </button>
                </div>

                {/* Footer */}
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
                      color: 'var(--gray-600)', cursor: 'pointer',
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
                      background: 'var(--primary)', color: 'white',
                      fontSize: 'var(--text-sm)', fontWeight: '500',
                      cursor: 'pointer',
                    }}
                  >
                    Add provider
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* Spin keyframe */}
        <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
      </div>
    </Layout>
  );
};

export default Providers;