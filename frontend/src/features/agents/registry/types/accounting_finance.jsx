// Agent type « accounting_finance » — tout ce qui le concerne est ici (voir registry/README.md)

export default {
  name: 'Accounting Expert',
  description: 'Accounting and financial expert — analysis, strategic advice, journal entries',
  icon: '∑', color: '#dc2626', badge: 'fixed', mcp: [],
  defaultConfig: (providers) => ({ llm_provider: providers[0]?.name || 'ollama', llm_model: 'mistrallite:latest', llm_temperature: 0.3, accounting_config: { domains: ['accounting', 'social'], auto_summary: true, extract_entities: true } }),
  mcpConfig: {}, requiredFields: [],
  executeFields: [
    { name: 'mode', label: 'Mode', type: 'select', required: true, options: [ { value: 'accounting_entry', label: 'Accounting entry' }, { value: 'strategic_advice', label: 'Strategic advice' } ] },
    { name: 'query', label: 'Query / instructions', type: 'textarea', placeholder: 'Enter invoice details...', required: true }
  ],
  buildInput: (d) => ({ mode: d.mode, query: d.query }),
};
