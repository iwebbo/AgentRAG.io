import { useState, useEffect } from 'react';
import Button from '../../../components/common/Button';
import Loading from '../../../components/common/Loading';
import Alert from '../../../components/common/Alert';
import api from '../../../services/api';
import { AGENT_TYPES, mergeMcpConfig, mergeAgentConfig } from '../registry';
import { applyConfigPath } from '../utils/formUtils';
import AgentConfigFields from './AgentConfigFields';

const AgentConfigModal = ({ agent, providers, skills, onClose, onSaved }) => {
  const t = AGENT_TYPES[agent.agent_type];
  const [formData, setFormData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  useEffect(() => {
    (async () => {
      try {
        const res = await api.get(`/api/agents/${agent.id}`);
        const d = res.data;
        const defaults = t.defaultConfig(providers);
        setFormData({
          name: d.name,
          description: d.description || '',
          // merge avec les defaults du type pour combler les clés manquantes
          // (utile pour les agents créés avant l'ajout d'un champ)
          config: mergeAgentConfig(agent.agent_type, defaults, d.config),
          mcp_config: mergeMcpConfig(t.mcpConfig, d.mcp_config),
        });
      } catch (e) {
        setError(e.response?.data?.detail || 'Failed to load agent config');
      } finally {
        setLoading(false);
      }
    })();
  }, [agent.id]);

  const updateConfigField = (path, value) => setFormData(prev => applyConfigPath(prev, path, value));

  const handleSave = async () => {
    if (!formData.name.trim()) { setError('Agent name is required'); return; }
    setSaving(true);
    setError(null);
    try {
      await api.put(`/api/agents/${agent.id}`, {
        name: formData.name,
        description: formData.description,
        config: formData.config,
        mcp_config: formData.mcp_config,
      });
      setSuccess('Configuration updated');
      setTimeout(() => { onSaved?.(); onClose(); }, 900);
    } catch (e) {
      setError(e.response?.data?.detail || 'Failed to update agent');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{ position: 'fixed', inset: 0, backgroundColor: 'var(--overlay)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, padding: 'var(--spacing-4)' }}>
      <div className="card" style={{ width: '100%', maxWidth: '720px', maxHeight: '90vh', overflow: 'auto' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 'var(--spacing-4)' }}>
          <div>
            <h2 style={{ fontSize: 'var(--text-xl)', fontWeight: '600' }}>{t?.icon} Configure — {agent.name}</h2>
            <p style={{ fontSize: 'var(--text-sm)', color: 'var(--gray-600)' }}>{t?.name} · type non modifiable</p>
          </div>
          <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--gray-600)', fontSize: '1.25rem' }}>✕</button>
        </div>

        {loading && <Loading />}
        {!loading && error && <Alert type="error" style={{ marginBottom: 'var(--spacing-4)' }} onClose={() => setError(null)}>{error}</Alert>}
        {success && <Alert type="success" style={{ marginBottom: 'var(--spacing-4)' }}>{success}</Alert>}

        {!loading && formData && (
          <>
            <div className="form-group">
              <label className="form-label">Agent name *</label>
              <input type="text" className="form-input" value={formData.name} onChange={e => setFormData(p => ({ ...p, name: e.target.value }))} />
            </div>
            <div className="form-group">
              <label className="form-label">Description</label>
              <textarea className="form-input" rows={2} value={formData.description} onChange={e => setFormData(p => ({ ...p, description: e.target.value }))} />
            </div>

            <AgentConfigFields agentType={agent.agent_type} formData={formData} providers={providers} skills={skills} updateConfigField={updateConfigField} />

            <div style={{ display: 'flex', gap: 'var(--spacing-3)', justifyContent: 'flex-end', marginTop: 'var(--spacing-6)', paddingTop: 'var(--spacing-4)', borderTop: '1px solid var(--gray-200)' }}>
              <Button variant="ghost" onClick={onClose} disabled={saving}>Cancel</Button>
              <Button variant="primary" onClick={handleSave} disabled={saving}>{saving ? 'Saving…' : 'Save changes'}</Button>
            </div>
          </>
        )}
      </div>
    </div>
  );
};

export default AgentConfigModal;
