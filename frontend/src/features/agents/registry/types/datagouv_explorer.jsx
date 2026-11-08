// Agent type « datagouv_explorer » — tout ce qui le concerne est ici (voir registry/README.md)

// Config spécifique datagouv_explorer
const DataGouvConfigFields = ({ formData, updateConfigField }) => (
  <div style={{ padding: 'var(--spacing-4)', backgroundColor: 'var(--gray-100)', borderRadius: 'var(--radius)', marginBottom: 'var(--spacing-4)' }}>
    <h3 style={{ fontWeight: '600', fontSize: 'var(--text-sm)', marginBottom: 'var(--spacing-3)' }}>DataGouv configuration</h3>
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--spacing-3)' }}>
      <div className="form-group"><label className="form-label">Page size</label><input type="number" className="form-input" value={formData.config.page_size || 10} onChange={e => updateConfigField('config.page_size', parseInt(e.target.value))} /></div>
      <div className="form-group"><label className="form-label">Analyze (LLM summary)</label><select className="form-input" value={formData.config.analyze ? 'true' : 'false'} onChange={e => updateConfigField('config.analyze', e.target.value === 'true')}><option value="false">false — raw results</option><option value="true">true — LLM summary</option></select></div>
    </div>
  </div>
);

export default {
  name: 'DataGouv Explorer',
  description: 'Explore the data.gouv.fr catalogue — datasets, resources, organizations, DINUM topics',
  icon: '⊗', color: '#003189', badge: 'fixed', mcp: ['datagouv'],
  defaultConfig: (providers) => ({ mcp_servers: ['datagouv'], mode: 'search', analyze: false, page_size: 10, llm_provider: providers[0]?.name || 'lmstudio', llm_model: 'openai/gpt-oss-20b', llm_temperature: 0.2 }),
  mcpConfig: {}, requiredFields: [],
  executeFields: [
    { name: 'mode', label: 'Mode', type: 'select', required: true, options: [ { value: 'search', label: 'search — find datasets' }, { value: 'dataset', label: 'dataset — detail + resources' }, { value: 'organization', label: 'organization — search an org' }, { value: 'topic', label: 'topic — DINUM API v2 themes' } ], defaultValue: 'search' },
    { name: 'query', label: 'Query (modes search / organization)', type: 'text', placeholder: 'population par commune | INSEE | Météo France' },
    { name: 'dataset_id', label: 'Dataset ID or slug (mode dataset)', type: 'text', placeholder: 'population-legale-2021' },
    { name: 'topic_id', label: 'Topic slug (mode topic)', type: 'text', placeholder: 'annuaire-des-entreprises' },
    { name: 'org_id', label: 'Org slug (mode organization)', type: 'text', placeholder: 'direction-interministerielle-du-numerique' },
    { name: 'page_size', label: 'Page size', type: 'number', placeholder: '10' },
    { name: 'sort', label: 'Sort (search: -created | -last_update | views…)', type: 'text', placeholder: '-last_update' }
  ],
  buildInput: (d) => {
    const r = { mode: d.mode || 'search' };
    if (d.query) r.query = d.query;
    if (d.dataset_id) r.dataset_id = d.dataset_id;
    if (d.topic_id) r.topic_id = d.topic_id;
    if (d.org_id) r.org_id = d.org_id;
    if (d.page_size) r.page_size = parseInt(d.page_size);
    if (d.sort) r.sort = d.sort;
    return r;
  },
  ConfigFields: DataGouvConfigFields,
};
