// Agent type « wikijs » — tout ce qui le concerne est ici (voir registry/README.md)

// Config spécifique wikijs
const WikiJSConfigFields = ({ formData, updateConfigField }) => (
  <div style={{ padding: 'var(--spacing-4)', backgroundColor: 'var(--gray-100)', borderRadius: 'var(--radius)', marginBottom: 'var(--spacing-4)' }}>
    <h3 style={{ fontWeight: '600', fontSize: 'var(--text-sm)', marginBottom: 'var(--spacing-3)' }}>WikiJS configuration</h3>
    <div className="form-group">
      <label className="form-label">Wiki.js URL * <span style={{ fontSize: 'var(--text-xs)', color: 'var(--gray-500)' }}>base URL, without /graphql</span></label>
      <input type="text" className="form-input" value={formData.mcp_config.wikijs?.base_url || ''} onChange={e => updateConfigField('mcp_config.wikijs.base_url', e.target.value)} placeholder="http://wiki.aecoding.local:3000" />
    </div>
    <div className="form-group">
      <label className="form-label">API token * <span style={{ fontSize: 'var(--text-xs)', color: 'var(--gray-500)' }}>Administration → API Access → New API Key</span></label>
      <input type="password" className="form-input" value={formData.mcp_config.wikijs?.token || ''} onChange={e => updateConfigField('mcp_config.wikijs.token', e.target.value)} placeholder="eyJhbGciOiJSUzI1NiIs..." />
    </div>
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--spacing-3)' }}>
      <div className="form-group">
        <label className="form-label">Default locale</label>
        <input type="text" className="form-input" value={formData.config.default_locale || 'en'} onChange={e => updateConfigField('config.default_locale', e.target.value)} placeholder="en" />
        <p style={{ fontSize: 'var(--text-xs)', color: 'var(--gray-600)', marginTop: '4px' }}>Check it.</p>
      </div>
      <div className="form-group">
        <label className="form-label">Default mode</label>
        <select className="form-input" value={formData.config.mode || 'read'} onChange={e => updateConfigField('config.mode', e.target.value)}>
          <option value="search">search</option>
          <option value="read">read</option>
          <option value="create">create</option>
          <option value="update">update</option>
        </select>
      </div>
    </div>
  </div>
);

export default {
  name: 'WikiJS Assistant',
  description: 'Read, search, create and update Wiki.js documentation pages, powered by a local LLM',
  icon: '⌬', color: '#16a34a', badge: 'fixed', mcp: ['wikijs'],
  defaultConfig: (providers) => ({
    mcp_servers: ['wikijs'],
    mode: 'read',
    default_locale: 'en',
    default_tags: [],
    llm_provider: providers[0]?.name || 'lmstudio',
    llm_model: 'openai/gpt-oss-20b',
    llm_temperature: 0.3,
  }),
  mcpConfig: { wikijs: { base_url: '', token: '' } },
  requiredFields: ['wikijs.base_url', 'wikijs.token'],
  executeFields: [
    { name: 'mode', label: 'Mode', type: 'select', required: true, options: [
        { value: 'search', label: 'search — full-text search' },
        { value: 'read', label: 'read — load page + LLM analysis' },
        { value: 'create', label: 'create — generate new page via LLM' },
        { value: 'update', label: 'update — revise existing page via LLM' },
      ], defaultValue: 'read' },
    { name: 'query', label: 'Search query (mode: search)', type: 'text', placeholder: 'installation' },
    { name: 'path', label: 'Page path (modes: read / create / update)', type: 'text', placeholder: 'mqtt-install' },
    { name: 'title', label: 'Page title (mode: create)', type: 'text', placeholder: 'Installation MQTT Debian' },
    { name: 'prompt', label: 'Generation prompt (mode: create)', type: 'textarea', placeholder: 'Explain in 3 points how to install and configure X...' },
    { name: 'instruction', label: 'Update instruction (mode: update)', type: 'textarea', placeholder: 'Add a "Troubleshooting" section at the bottom...' },
    { name: 'question', label: 'Question (mode: read, optional)', type: 'text', placeholder: 'How is SSL configured here?' },
    { name: 'context', label: 'Context (modes: create / update, optional)', type: 'textarea', placeholder: 'Paste logs, config files, bash history...' },
    { name: 'tags', label: 'Tags, comma-separated (mode: create, optional)', type: 'text', placeholder: 'infra, installation' },
    { name: 'locale', label: 'Locale override (optional)', type: 'text', placeholder: 'en' },
  ],
  buildInput: (d) => {
    const r = { mode: d.mode || 'read' };
    if (d.query) r.query = d.query;
    if (d.path) r.path = d.path;
    if (d.locale) r.locale = d.locale;
    if (d.question) r.question = d.question;
    if (d.title) r.title = d.title;
    if (d.prompt) r.prompt = d.prompt;
    if (d.context) r.context = d.context;
    if (d.instruction) r.instruction = d.instruction;
    if (d.tags) r.tags = d.tags.split(',').map(t => t.trim()).filter(Boolean);
    return r;
  },
  ConfigFields: WikiJSConfigFields,
};
