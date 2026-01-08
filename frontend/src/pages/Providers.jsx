import { useState, useEffect } from 'react';
import { Plus, Trash2, ExternalLink } from 'lucide-react';
import Layout from '../components/layout/Layout';
import Button from '../components/common/Button';
import Toggle from '../components/common/Toggle';
import StatusBadge from '../components/common/StatusBadge';
import Alert from '../components/common/Alert';
import api from '../services/api';

// CONFIGURATION DES PROVIDERS (facile à étendre)
const PROVIDER_CONFIG = [
  { value: 'openai',      label: 'OpenAI',                requiresKey: true,  defaultUrl: null,                                 keyHint: 'sk-...' },
  { value: 'claude',      label: 'Anthropic Claude',      requiresKey: true,  defaultUrl: null,                                 keyHint: 'sk-ant-...' },
  { value: 'gemini',      label: 'Google Gemini',         requiresKey: true,  defaultUrl: null,                                 keyHint: 'AIzaSy...', link: 'https://aistudio.google.com/app/apikey' },
  { value: 'huggingface', label: 'HuggingFace Inference', requiresKey: true,  defaultUrl: 'https://api-inference.huggingface.co', keyHint: 'hf_...', link: 'https://huggingface.co/settings/tokens' },

  { value: 'ollama',      label: 'Ollama (Local)',        requiresKey: false, defaultUrl: 'http://localhost:11434',              },
  { value: 'lmstudio',    label: 'LM Studio',             requiresKey: false, defaultUrl: 'http://localhost:1234/v1',            },
  { value: 'localai',     label: 'LocalAI',               requiresKey: false, defaultUrl: 'http://localhost:8080/v1',            },
  { value: 'oobabooga',   label: 'Text Generation WebUI', requiresKey: false, defaultUrl: 'http://localhost:5000/v1',            },
  { value: 'vllm',        label: 'vLLM',                  requiresKey: false, defaultUrl: 'http://localhost:8000/v1',            },
  { value: 'lmdeploy',    label: 'LMDeploy / OpenXLab',   requiresKey: false, defaultUrl: 'http://localhost:23333/v1',           },
  { value: 'grok',        label: 'xAI Grok (officiel)',     requiresKey: true,  defaultUrl: 'https://api.x.ai/v1',              keyHint: 'xai-...', link: 'https://console.x.ai', note: '25 $ gratuit • grok-3 = meilleur modèle 2025' },
  { value: 'openrouter',  label: 'OpenRouter (100+ modèles gratuits)', requiresKey: true, defaultUrl: 'https://openrouter.ai/api/v1',  keyHint: 'sk-or-...', link: 'https://openrouter.ai/keys' },
  { value: 'groq',        label: 'Groq (Llama 3.2 90B ultra-rapide)',  requiresKey: true, defaultUrl: 'https://api.groq.com/openai/v1', keyHint: 'gsk_...',   link: 'https://console.groq.com/keys' },
];

const Providers = () => {
  const [providers, setProviders] = useState([]);
  const [showAddModal, setShowAddModal] = useState(false);
  const [testing, setTesting] = useState({});
  const [alert, setAlert] = useState(null);

  const [formData, setFormData] = useState({
    name: 'openai',
    api_key: '',
    base_url: '',
    priority: 50,
    is_active: true,
  });

  const selectedConfig = PROVIDER_CONFIG.find(p => p.value === formData.name) || PROVIDER_CONFIG[0];

  // Auto-remplir base_url
  useEffect(() => {
    setFormData(prev => ({
      ...prev,
      base_url: selectedConfig.defaultUrl || '',
      api_key: '' // reset key quand on change
    }));
  }, [formData.name]);

  useEffect(() => {
    loadProviders();
  }, []);

  const loadProviders = async () => {
    try {
      const res = await api.get('/api/providers/');
      setProviders(res.data);
    } catch {
      showAlert('error', 'Failed to load providers');
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    const payload = {
      name: formData.name,
      priority: formData.priority,
      is_active: formData.is_active,
    };

    if (selectedConfig.requiresKey && !formData.api_key.trim()) {
      showAlert('error', 'API Key is required');
      return;
    }
    if (selectedConfig.requiresKey) payload.api_key = formData.api_key.trim();
    if (formData.base_url.trim()) payload.base_url = formData.base_url.trim();

    try {
      await api.post('/api/providers/', payload);
      showAlert('success', 'Provider added successfully');
      setShowAddModal(false);
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
        ? showAlert('success', `Connected! ${res.data.latency_ms}ms`)
        : showAlert('error', res.data.message || 'Failed');
    } catch {
      showAlert('error', 'Connection test failed');
    } finally {
      setTesting(prev => ({ ...prev, [id]: false }));
    }
  };

  const handleToggleActive = async (provider) => {
    try {
      await api.put(`/api/providers/${provider.id}`, { is_active: !provider.is_active });
      loadProviders();
    } catch {
      showAlert('error', 'Failed to update');
    }
  };

  const showAlert = (type, message) => {
    setAlert({ type, message });
    setTimeout(() => setAlert(null), 5000);
  };

  const resetForm = () => {
    setFormData({ name: 'openai', api_key: '', base_url: '', priority: 50, is_active: true });
  };

  const getLabel = (name) => PROVIDER_CONFIG.find(p => p.value === name)?.label || name.toUpperCase();

  return (
    <Layout>
      <div className="container" style={{ padding: 'var(--spacing-8) var(--spacing-4)' }}>
        {alert && (
          <div style={{ marginBottom: 'var(--spacing-4)' }}>
            <Alert type={alert.type} message={alert.message} onClose={() => setAlert(null)} />
          </div>
        )}

        {/* Header */}
        <div className="flex justify-between items-center" style={{ marginBottom: 'var(--spacing-8)' }}>
          <div>
            <h1 style={{ fontSize: 'var(--text-3xl)', fontWeight: '700', marginBottom: 'var(--spacing-2)' }}>
              Providers
            </h1>
            <p style={{ color: 'var(--gray-600)' }}>Manage your LLM provider configurations</p>
          </div>
          <Button variant="primary" icon={Plus} onClick={() => setShowAddModal(true)}>
            Add Provider
          </Button>
        </div>

        {/* Grid des cartes */}
        <div className="grid grid-cols-3 gap-6">
          {providers.map((provider) => (
            <div key={provider.id} className="card">

              {/* En-tête carte */}
              <div className="flex justify-between items-start" style={{ marginBottom: 'var(--spacing-4)' }}>
                <div>
                  <h3 style={{ fontWeight: '600', marginBottom: 'var(--spacing-2)' }}>
                    {getLabel(provider.name)}
                  </h3>
                  <StatusBadge status={provider.is_active ? 'online' : 'offline'} />
                </div>
                <button className="btn btn-ghost btn-sm" onClick={() => handleDelete(provider.id)}>
                  <Trash2 size={16} />
                </button>
              </div>

              {/* Infos */}
              <div style={{ marginBottom: 'var(--spacing-4)' }}>
                <p style={{ fontSize: 'var(--text-sm)', color: 'var(--gray-600)', marginBottom: 'var(--spacing-2)' }}>
                  Priority: {provider.priority}
                </p>
                {provider.base_url && (
                  <p style={{ fontSize: 'var(--text-xs)', color: 'var(--gray-500)', wordBreak: 'break-all' }}>
                    {provider.base_url}
                  </p>
                )}
              </div>

              {/* Actions */}
              <div style={{ display: 'flex', gap: 'var(--spacing-2)', alignItems: 'center' }}>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => handleTest(provider.id)}
                  loading={testing[provider.id]}
                >
                  Test Connection
                </Button>
                <Toggle
                  checked={provider.is_active}
                  onChange={() => handleToggleActive(provider)}
                  label="Active"
                />
              </div>
            </div>
          ))}
        </div>

        {/* Modal Ajout */}
        {showAddModal && (
          <div style={{
            position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
            backgroundColor: 'rgba(0,0,0,0.5)', display: 'flex',
            alignItems: 'center', justifyContent: 'center', zIndex: 1000
          }}>
            <div className="card" style={{ width: '100%', maxWidth: '500px' }}>
              <h2 style={{ fontSize: 'var(--text-2xl)', fontWeight: '600', marginBottom: 'var(--spacing-6)' }}>
                Add Provider
              </h2>

              <form onSubmit={handleSubmit}>
                {/* Provider Select */}
                <div className="form-group">
                  <label className="form-label">Provider</label>
                  <select
                    className="form-select"
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  >
                    {PROVIDER_CONFIG.map(p => (
                      <option key={p.value} value={p.value}>{p.label}</option>
                    ))}
                  </select>
                </div>

                {/* API Key */}
                {selectedConfig.requiresKey && (
                  <div className="form-group">
                    <label className="form-label">API Key</label>
                    <input
                      type="password"
                      className="form-input"
                      placeholder={selectedConfig.keyHint || 'Enter API key'}
                      value={formData.api_key}
                      onChange={(e) => setFormData({ ...formData, api_key: e.target.value })}
                      required
                    />
                    {selectedConfig.link && (
                      <p style={{ fontSize: 'var(--text-xs)', color: 'var(--gray-600)', marginTop: 'var(--spacing-1)' }}>
                        Get your key → <a href={selectedConfig.link} target="_blank" rel="noopener noreferrer" className="underline">here <ExternalLink size={12} style={{ display: 'inline' }} /></a>
                      </p>
                    )}
                  </div>
                )}

                {/* Base URL */}
                <div className="form-group">
                  <label className="form-label">
                    Base URL {selectedConfig.defaultUrl ? '(default)' : '(optional)'}
                  </label>
                  <input
                    type="url"
                    className="form-input"
                    placeholder={selectedConfig.defaultUrl || 'https://api.openai.com/v1'}
                    value={formData.base_url}
                    onChange={(e) => setFormData({ ...formData, base_url: e.target.value })}
                  />
                  {selectedConfig.defaultUrl && (
                    <p style={{ fontSize: 'var(--text-xs)', color: 'var(--gray-600)', marginTop: 'var(--spacing-1)' }}>
                      Default: <code style={{ background: 'var(--gray-200)', padding: '2px 6px', borderRadius: '4px' }}>
                        {selectedConfig.defaultUrl}
                      </code>
                    </p>
                  )}
                </div>

                {/* Priority */}
                <div className="form-group">
                  <label className="form-label">Priority (0-100)</label>
                  <input
                    type="number"
                    className="form-input"
                    min="0"
                    max="100"
                    value={formData.priority}
                    onChange={(e) => setFormData({ ...formData, priority: parseInt(e.target.value) || 0 })}
                  />
                </div>

                {/* Active Toggle */}
                <div className="form-group">
                  <Toggle
                    checked={formData.is_active}
                    onChange={(c) => setFormData({ ...formData, is_active: c })}
                    label="Active"
                  />
                </div>

                {/* Boutons */}
                <div style={{ display: 'flex', gap: 'var(--spacing-3)', justifyContent: 'flex-end', marginTop: 'var(--spacing-6)' }}>
                  <Button variant="ghost" onClick={() => { setShowAddModal(false); resetForm(); }}>
                    Cancel
                  </Button>
                  <Button type="submit" variant="primary">
                    Add Provider
                  </Button>
                </div>
              </form>
            </div>
          </div>
        )}
      </div>
    </Layout>
  );
};

export default Providers;