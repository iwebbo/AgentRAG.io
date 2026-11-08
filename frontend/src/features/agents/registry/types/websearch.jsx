// Agent type « websearch » — tout ce qui le concerne est ici (voir registry/README.md)

// [WEBSEARCH] Rendu texte des résultats websearch (synthèse + sources analysées)
// Accepte le payload direct, un event SSE { data: {...} } ou un output_data { output: {...} }
const formatWebSearchResult = (r) => {
  if (!r || typeof r !== 'object') return '';
  const p = r.results ? r : (r.data?.results ? r.data : (r.output?.results ? r.output : null));
  if (!p || !Array.isArray(p.results)) return '';
  const m = p.metadata || {};
  const L = [`Query: ${p.query}  —  ${p.results_count ?? p.results.length} results`];
  if (m.llm_analysis) L.push(`LLM: ${m.llm_provider}/${m.llm_model} · analyzed ${m.llm_analyzed_count}`);
  if (p.synthesis) L.push('', '── Synthesis ──', p.synthesis);
  L.push('', '── Sources ──');
  p.results.forEach((x, i) => {
    const a = x.llm_analysis;
    L.push(`[${i + 1}] ${x.title}`, `    ${x.url}`);
    if (a) {
      L.push(`    Relevance: ${a.relevance ?? '?'}/10${a.answers_query === true ? ' ✓' : ''}`, `    ${a.summary}`);
      (a.key_points || []).forEach(k => L.push(`      • ${k}`));
    } else if (x.snippet) {
      L.push(`    ${x.snippet}`);
    }
    L.push('');
  });
  return L.join('\n');
};

// [WEBSEARCH] Config de l'agent websearch (search_config)
const WebSearchConfigFields = ({ formData, updateConfigField }) => {
  const sc = formData.config.search_config || {};
  const num = (v, d) => (v === '' || isNaN(parseInt(v, 10)) ? d : parseInt(v, 10));
  const P = 'config.search_config.';
  return (
    <div style={{ padding: 'var(--spacing-4)', backgroundColor: 'var(--gray-100)', borderRadius: 'var(--radius)', marginBottom: 'var(--spacing-4)' }}>
      <h3 style={{ fontWeight: '600', fontSize: 'var(--text-sm)', marginBottom: 'var(--spacing-3)' }}>Web search configuration</h3>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr', gap: 'var(--spacing-3)' }}>
        <div className="form-group"><label className="form-label">Max results</label><input type="number" className="form-input" value={sc.max_results ?? 10} onChange={e => updateConfigField(P + 'max_results', num(e.target.value, 10))} /></div>
        <div className="form-group"><label className="form-label">Language</label>
          <select className="form-input" value={sc.language || 'en'} onChange={e => updateConfigField(P + 'language', e.target.value)}>
            {['fr', 'en', 'de', 'es', 'it', 'pt'].map(l => <option key={l} value={l}>{l}</option>)}
          </select></div>
        <div className="form-group"><label className="form-label">Analyze top N</label><input type="number" min="0" className="form-input" value={sc.analyze_top_n ?? 5} onChange={e => updateConfigField(P + 'analyze_top_n', num(e.target.value, 5))} /></div>
        <div className="form-group"><label className="form-label">Max chars / page</label><input type="number" className="form-input" value={sc.max_content_chars ?? 6000} onChange={e => updateConfigField(P + 'max_content_chars', num(e.target.value, 6000))} /></div>
      </div>
      <div style={{ display: 'flex', gap: 'var(--spacing-4)', flexWrap: 'wrap' }}>
        {[['safe_search', 'Safe search', true], ['extract_content', 'Extract content', true], ['llm_analysis', 'LLM analysis', true], ['synthesize', 'LLM synthesis', true]].map(([k, label, def]) => (
          <label key={k} style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-2)', cursor: 'pointer', fontSize: 'var(--text-sm)' }}>
            <input type="checkbox" checked={sc[k] ?? def} onChange={e => updateConfigField(P + k, e.target.checked)} />{label}
          </label>
        ))}
      </div>
    </div>
  );
};

export default {
  name: 'Web Search',
  description: 'Web search with page extraction and LLM analysis/synthesis',
  icon: '⊕', color: '#ec4899', badge: 'fixed', mcp: [],
  defaultConfig: (providers) => ({
    llm_provider: providers[0]?.name || 'ollama',
    llm_model: 'mistrallite:latest',
    llm_temperature: 0.3,
    search_config: {
      max_results: 10, language: 'en', safe_search: true, extract_content: true,
      llm_analysis: true, analyze_top_n: 5, synthesize: true, max_content_chars: 6000,
    },
  }),
  mcpConfig: {}, requiredFields: [],
  executeFields: [
    { name: 'query', label: 'Search query', type: 'text', placeholder: 'What to search for...', required: true },
    { name: 'max_results', label: 'Max results (optional)', type: 'number', placeholder: '10' },
    { name: 'extract_content', label: 'Extract page content', type: 'checkbox', defaultValue: true },
    { name: 'llm_analysis', label: 'LLM analysis per result', type: 'checkbox', defaultValue: true },
    { name: 'synthesize', label: 'LLM synthesis', type: 'checkbox', defaultValue: true },
  ],
  // les booléens envoyés surchargent la config de l'agent pour ce run
  buildInput: (d) => {
    const r = { query: String(d.query || '').trim() };
    if (d.max_results && !isNaN(parseInt(d.max_results, 10))) r.max_results = parseInt(d.max_results, 10);
    r.extract_content = d.extract_content ?? true;
    r.llm_analysis = d.llm_analysis ?? true;
    r.synthesize = d.synthesize ?? true;
    return r;
  },
  formatResult: formatWebSearchResult,
  // merge profond de search_config : un agent créé avant l'ajout de llm_analysis / synthesize /
  // analyze_top_n reçoit les nouveaux défauts au lieu que son ancien search_config remplace celui des defaults
  mergeConfig: (defaults, saved) => ({
    ...defaults,
    ...saved,
    search_config: { ...(defaults.search_config || {}), ...(saved.search_config || {}) },
  }),
  ConfigFields: WebSearchConfigFields,
};
