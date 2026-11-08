// Agent type « legal_fiscal » — tout ce qui le concerne est ici (voir registry/README.md)

export default {
  name: 'Legal & Fiscal Expert',
  description: 'Legal and fiscal expert with RAG on legal documents (contracts, invoices, GDPR)',
  icon: '⚖', color: '#059669', badge: 'fixed', mcp: [],
  defaultConfig: (providers) => ({ llm_provider: providers[0]?.name || 'ollama', llm_model: 'mistrallite:latest', llm_temperature: 0.3, legal_config: { domains: ['fiscal', 'social', 'commercial'], auto_summary: true, extract_entities: true } }),
  mcpConfig: {}, requiredFields: [],
  executeFields: [
    { name: 'mode', label: 'Analysis mode', type: 'select', required: true, options: [ { value: 'analyze', label: 'Analyze document' }, { value: 'risk_assessment', label: 'Risk assessment' }, { value: 'compliance_check', label: 'Compliance check' }, { value: 'claim_processing', label: 'Claim processing' }, { value: 'document_drafting', label: 'Document drafting' }, { value: 'legal_research', label: 'Legal research' }, { value: 'training', label: 'Training material' }, { value: 'monitoring', label: 'Legislative monitoring' } ] },
    { name: 'query', label: 'Query / instructions', type: 'textarea', placeholder: 'Analyze contract clauses...', required: true },
    { name: 'documents', label: 'Document paths (optional, comma-separated)', type: 'text', placeholder: '/app/data/contract.pdf' }
  ],
  buildInput: (d) => {
    const r = { mode: d.mode, query: d.query };
    if (d.documents) r.documents = d.documents.split(',').map(x => x.trim()).filter(Boolean);
    return r;
  },
};
