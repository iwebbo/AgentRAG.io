import { useState } from 'react';
import { Plus } from 'lucide-react';
import Button from '../../../components/common/Button';
import Alert from '../../../components/common/Alert';
import api from '../../../services/api';
import { AGENT_TYPES, mergeMcpConfig } from '../registry';
import { applyConfigPath } from '../utils/formUtils';
import AgentConfigFields from './AgentConfigFields';

const EMPTY_FORM = { name: '', description: '', agent_type: '', config: {}, mcp_config: {} };

// Création d'un agent : choix du type, puis formulaire. Les blocs de config viennent du registre
// (AgentConfigFields → registry/types/<agent_type>.jsx), partagés avec AgentConfigModal.
const CreateAgentModal = ({ providers, skills, onClose, onCreated }) => {
  const [selectedAgentType, setSelectedAgentType] = useState(null);
  const [formData, setFormData] = useState(EMPTY_FORM);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  const selectAgentType = (type) => {
    setSelectedAgentType(type);
    const t = AGENT_TYPES[type];
    setFormData({ name: '', description: t.description, agent_type: type, config: t.defaultConfig(providers), mcp_config: mergeMcpConfig(t.mcpConfig, {}) });
  };

  const updateConfigField = (path, value) => setFormData(prev => applyConfigPath(prev, path, value));

  const validateForm = () => {
    if (!formData.name.trim()) { setError('Agent name is required'); return false; }
    const agentTypeDef = AGENT_TYPES[selectedAgentType];
    for (const field of agentTypeDef.requiredFields) {
      const rootKey = field.split('.')[0];
      const src = Object.prototype.hasOwnProperty.call(agentTypeDef.mcpConfig || {}, rootKey)
        ? formData.mcp_config
        : formData.config;
      const val = field.split('.').reduce((o, k) => o?.[k], src);
      if (!val || String(val).trim() === '') { setError(`Field ${field} is required`); return false; }
    }
    return true;
  };

  const handleSubmit = async () => {
    if (!validateForm()) return;
    try {
      await api.post('/api/agents/', formData);
      setSuccess('Agent created successfully!');
      setTimeout(() => onCreated?.(), 1500);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create agent');
    }
  };

  return (
    <div style={{ position: 'fixed', inset: 0, backgroundColor: 'var(--overlay)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, padding: 'var(--spacing-4)' }}>
      <div className="card" style={{ width: '100%', maxWidth: '900px', maxHeight: '90vh', overflow: 'auto' }}>
        <h2 style={{ fontSize: 'var(--text-xl)', fontWeight: '600', marginBottom: 'var(--spacing-2)' }}>
          {selectedAgentType ? `Configure — ${AGENT_TYPES[selectedAgentType].name}` : 'Select agent type'}
        </h2>
        {selectedAgentType && <p style={{ fontSize: 'var(--text-sm)', color: 'var(--gray-600)', marginBottom: 'var(--spacing-5)' }}>{AGENT_TYPES[selectedAgentType].description}</p>}

        {!selectedAgentType ? (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 'var(--spacing-3)' }}>
            {Object.entries(AGENT_TYPES).map(([type, info]) => (
              <div key={type} onClick={() => selectAgentType(type)} style={{ border: '1px solid var(--gray-300)', borderLeft: `3px solid ${info.color}`, borderRadius: 'var(--radius-md)', padding: 'var(--spacing-4)', cursor: 'pointer', transition: 'all .15s', background: 'var(--bg-card)' }}
                onMouseEnter={e => { e.currentTarget.style.borderColor = info.color; e.currentTarget.style.transform = 'translateY(-2px)'; }}
                onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--gray-300)'; e.currentTarget.style.transform = 'none'; }}>
                <div style={{ fontSize: '1.5rem', marginBottom: 'var(--spacing-2)' }}>{info.icon}</div>
                <div style={{ fontWeight: '600', fontSize: 'var(--text-sm)', marginBottom: 'var(--spacing-1)' }}>{info.name}</div>
                <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap', marginBottom: 'var(--spacing-2)' }}>
                  <span style={{ fontSize: '10px', fontWeight: '600', padding: '1px 6px', borderRadius: '99px', background: info.badge === 'skill' ? 'rgba(34,197,94,.15)' : 'rgba(96,165,250,.15)', color: info.badge === 'skill' ? 'var(--success-dark)' : 'var(--primary-dark)' }}>{info.badge}</span>
                  {info.mcp.map(m => <span key={m} style={{ fontSize: '10px', padding: '1px 5px', borderRadius: '99px', background: 'var(--gray-200)', color: 'var(--gray-700)' }}>{m}</span>)}
                </div>
                <p style={{ fontSize: 'var(--text-xs)', color: 'var(--gray-600)', lineHeight: '1.5' }}>{info.description}</p>
              </div>
            ))}
          </div>
        ) : (
          <div>
            {error && <Alert type="error" style={{ marginBottom: 'var(--spacing-4)' }} onClose={() => setError(null)}>{error}</Alert>}
            {success && <Alert type="success" style={{ marginBottom: 'var(--spacing-4)' }}>{success}</Alert>}

            <div className="form-group">
              <label className="form-label">Agent name *</label>
              <input type="text" className="form-input" value={formData.name} onChange={e => setFormData({ ...formData, name: e.target.value })} placeholder={`My ${AGENT_TYPES[selectedAgentType].name}`} />
            </div>
            <div className="form-group">
              <label className="form-label">Description</label>
              <textarea className="form-input" value={formData.description || ''} onChange={e => setFormData({ ...formData, description: e.target.value })} placeholder="Optional description" rows={2} />
            </div>

          <AgentConfigFields
            agentType={selectedAgentType}
            formData={formData}
            providers={providers}
            skills={skills}
            updateConfigField={updateConfigField}
          />

            <div style={{ display: 'flex', gap: 'var(--spacing-3)', justifyContent: 'space-between', marginTop: 'var(--spacing-6)', paddingTop: 'var(--spacing-4)', borderTop: '1px solid var(--gray-200)' }}>
              <Button variant="ghost" onClick={() => setSelectedAgentType(null)}>← Back</Button>
              <div style={{ display: 'flex', gap: 'var(--spacing-2)' }}>
                <Button variant="ghost" onClick={onClose}>Cancel</Button>
                <Button variant="primary" onClick={handleSubmit} disabled={!formData.name.trim()} icon={Plus}>Create agent</Button>
              </div>
            </div>
          </div>
        )}

        {!selectedAgentType && (
          <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 'var(--spacing-6)', paddingTop: 'var(--spacing-4)', borderTop: '1px solid var(--gray-200)' }}>
            <Button variant="ghost" onClick={onClose}>Cancel</Button>
          </div>
        )}
      </div>
    </div>
  );
};

export default CreateAgentModal;
