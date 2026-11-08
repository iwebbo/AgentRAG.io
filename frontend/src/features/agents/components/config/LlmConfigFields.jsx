// Bloc LLM (provider / model / temperature) commun à tous les agents
const LlmConfigFields = ({ formData, providers, updateConfigField }) => (
  <div style={{ padding: 'var(--spacing-4)', backgroundColor: 'var(--gray-100)', borderRadius: 'var(--radius)', marginBottom: 'var(--spacing-4)' }}>
    <h3 style={{ fontWeight: '600', fontSize: 'var(--text-sm)', marginBottom: 'var(--spacing-3)' }}>LLM configuration</h3>
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 'var(--spacing-3)' }}>
      <div className="form-group">
        <label className="form-label">Provider</label>
        <select className="form-input" value={formData.config.llm_provider} onChange={e => updateConfigField('config.llm_provider', e.target.value)}>
          {providers.map(p => <option key={p.name} value={p.name}>{p.name}</option>)}
        </select>
      </div>
      <div className="form-group"><label className="form-label">Model</label><input type="text" className="form-input" value={formData.config.llm_model} onChange={e => updateConfigField('config.llm_model', e.target.value)} /></div>
      <div className="form-group"><label className="form-label">Temperature</label><input type="number" step="0.1" min="0" max="2" className="form-input" value={formData.config.llm_temperature} onChange={e => updateConfigField('config.llm_temperature', parseFloat(e.target.value))} /></div>
    </div>
  </div>
);

export default LlmConfigFields;
