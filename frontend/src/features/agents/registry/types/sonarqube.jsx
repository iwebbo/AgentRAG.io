// Agent type « sonarqube » — tout ce qui le concerne est ici (voir registry/README.md)

// Champs d'exécution visibles par mode
export const SONAR_FIELDS_BY_MODE = {
  projects:  ['query', 'with_quality_gate', 'page_size'],
  overview:  ['project_key', 'branch', 'in_new_code_period'],
  issues:    ['project_key', 'branch', 'types', 'severities', 'in_new_code_period', 'page_size'],
  hotspots:  ['project_key', 'branch', 'in_new_code_period', 'page_size'],
  remediate: ['project_key', 'issue_keys', 'branch', 'types', 'severities', 'max_remediations', 'snippet_context'],
};

// Rendu texte des résultats sonarqube — le panneau Output est monospace / pre-wrap
const formatSonarResult = (r) => {
  if (!r || typeof r !== 'object') return '';
  const payload = r.mode ? r : (r.data && r.data.mode ? r.data : r);
  if (!payload.mode) return '';
  const kv = (o) => Object.entries(o || {}).map(([k, v]) => `${k}=${v}`).join('  ') || '—';
  const file = (c) => (c || '').split(':').pop();
  const L = [];
  switch (payload.mode) {
    case 'projects':
      L.push(`Projects: ${payload.total ?? 0}  (source: ${payload.source || '?'})`, '');
      (payload.projects || []).forEach(p => L.push(
        `• ${p.key}  —  ${p.name}` +
        (p.quality_gate ? `  [QG ${p.quality_gate}]` : '') +
        (p.last_analysis_date ? `  · ${p.last_analysis_date}` : '')
      ));
      break;
    case 'overview':
      L.push(`Project: ${payload.project_key}${payload.branch ? ` (${payload.branch})` : ''}`,
             `Quality gate: ${payload.quality_gate?.status || 'N/A'}`);
      (payload.quality_gate?.failed_conditions || []).forEach(c =>
        L.push(`  ✗ ${c.metric}: ${c.actual} (${c.comparator} ${c.threshold})`));
      L.push('', 'Measures:');
      Object.entries(payload.measures || {}).forEach(([k, v]) => L.push(`  ${k.padEnd(26)} ${v}`));
      L.push('', `Issues: ${payload.issues_summary?.total ?? 0}`,
        `  Severity: ${kv(payload.issues_summary?.by_severity)}`,
        `  Type:     ${kv(payload.issues_summary?.by_type)}`,
        `Hotspots to review: ${payload.hotspots?.total ?? 0}`);
      if (payload.analysis) L.push('', '── LLM analysis ──', payload.analysis);
      break;
    case 'issues':
      L.push(`Project: ${payload.project_key} — ${payload.total ?? 0} issues`,
             `Severity: ${kv(payload.by_severity)}`,
             `Type:     ${kv(payload.by_type)}`, '');
      (payload.issues || []).forEach(i => L.push(
        `[${i.severity}][${i.type}] ${i.rule}  ${file(i.component)}:${i.line ?? '-'}`,
        `    ${i.message}  (${i.key})`
      ));
      if (payload.summary) L.push('', '── LLM analysis ──', payload.summary);
      break;
    case 'hotspots':
      L.push(`Project: ${payload.project_key} — ${payload.total ?? 0} hotspots (${payload.status})`, '');
      (payload.hotspots || []).forEach(h => L.push(
        `[${h.vulnerability_probability}] ${h.security_category}  ${file(h.component)}:${h.line ?? '-'}`,
        `    ${h.message}  (${h.key})`
      ));
      if (payload.summary) L.push('', '── LLM analysis ──', payload.summary);
      break;
    case 'remediate':
      L.push(`Remediations: ${payload.count ?? 0}${payload.project_key ? `  —  ${payload.project_key}` : ''}`, '');
      (payload.remediations || []).forEach((x, n) => L.push(
        `━━ [${n + 1}/${payload.count}] ${x.severity} ${x.rule} — ${x.rule_name || ''}`,
        `${x.component}:${x.line}  (${x.issue_key})`,
        x.message || '',
        '',
        x.remediation || '(no remediation generated)',
        ''
      ));
      break;
    default:
      return JSON.stringify(payload, null, 2);
  }
  return L.join('\n');
};

// Config spécifique sonarqube
const SonarQubeConfigFields = ({ formData, updateConfigField }) => {
  const sq = formData.mcp_config.sonarqube || {};
  const cfg = formData.config || {};
  const num = (v, d) => (v === '' || isNaN(parseInt(v, 10)) ? d : parseInt(v, 10));
  const hint = { fontSize: 'var(--text-xs)', color: 'var(--gray-500)' };
  return (
    <div style={{ padding: 'var(--spacing-4)', backgroundColor: 'var(--gray-100)', borderRadius: 'var(--radius)', marginBottom: 'var(--spacing-4)' }}>
      <h3 style={{ fontWeight: '600', fontSize: 'var(--text-sm)', marginBottom: 'var(--spacing-3)' }}>SonarQube configuration</h3>

      <div className="form-group">
        <label className="form-label">SonarQube URL * <span style={hint}>base URL, without /api</span></label>
        <input type="text" className="form-input" value={sq.base_url || ''} onChange={e => updateConfigField('mcp_config.sonarqube.base_url', e.target.value)} placeholder="https://sonarqube.aecoding.local" />
      </div>
      <div className="form-group">
        <label className="form-label">API token * <span style={hint}>My Account → Security → Generate Token</span></label>
        <input type="password" className="form-input" value={sq.token || ''} onChange={e => updateConfigField('mcp_config.sonarqube.token', e.target.value)} placeholder="squ_..." />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 'var(--spacing-3)' }}>
        <div className="form-group">
          <label className="form-label">Auth mode <span style={hint}>auto-fallback on 401</span></label>
          <select className="form-input" value={sq.auth_mode || 'bearer'} onChange={e => updateConfigField('mcp_config.sonarqube.auth_mode', e.target.value)}>
            <option value="bearer">bearer (10.x+ / SonarCloud)</option>
            <option value="basic">basic (8.x / 9.x)</option>
          </select>
        </div>
        <div className="form-group">
          <label className="form-label">Verify SSL</label>
          <select className="form-input" value={sq.verify_ssl ? 'true' : 'false'} onChange={e => updateConfigField('mcp_config.sonarqube.verify_ssl', e.target.value === 'true')}>
            <option value="false">false (internal PKI)</option>
            <option value="true">true</option>
          </select>
        </div>
        <div className="form-group">
          <label className="form-label">Timeout (s)</label>
          <input type="number" className="form-input" value={sq.timeout ?? 30} onChange={e => updateConfigField('mcp_config.sonarqube.timeout', num(e.target.value, 30))} />
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 'var(--spacing-3)' }}>
        <div className="form-group">
          <label className="form-label">Default mode</label>
          <select className="form-input" value={cfg.mode || 'projects'} onChange={e => updateConfigField('config.mode', e.target.value)}>
            {Object.keys(SONAR_FIELDS_BY_MODE).map(m => <option key={m} value={m}>{m}</option>)}
          </select>
        </div>
        <div className="form-group">
          <label className="form-label">Page size</label>
          <input type="number" className="form-input" value={cfg.page_size ?? 50} onChange={e => updateConfigField('config.page_size', num(e.target.value, 50))} />
        </div>
        <div className="form-group">
          <label className="form-label">Analyze (LLM summary)</label>
          <select className="form-input" value={cfg.analyze ? 'true' : 'false'} onChange={e => updateConfigField('config.analyze', e.target.value === 'true')}>
            <option value="false">false — raw results</option>
            <option value="true">true — LLM analysis</option>
          </select>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--spacing-3)' }}>
        <div className="form-group">
          <label className="form-label">Max remediations / run</label>
          <input type="number" className="form-input" value={cfg.max_remediations ?? 3} onChange={e => updateConfigField('config.max_remediations', num(e.target.value, 3))} />
        </div>
        <div className="form-group">
          <label className="form-label">Snippet context (lines)</label>
          <input type="number" className="form-input" value={cfg.snippet_context ?? 15} onChange={e => updateConfigField('config.snippet_context', num(e.target.value, 15))} />
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: 'var(--spacing-3)' }}>
        <div className="form-group">
          <label className="form-label">Repository RAG</label>
          <select className="form-input" value={cfg.use_rag ? 'true' : 'false'} onChange={e => updateConfigField('config.use_rag', e.target.value === 'true')}>
            <option value="false">disabled</option>
            <option value="true">enabled</option>
          </select>
        </div>
        <div className="form-group">
          <label className="form-label">RAG project ID <span style={hint}>indexed repository — Projects page</span></label>
          <input type="text" className="form-input" value={cfg.project_id || ''} disabled={!cfg.use_rag} onChange={e => updateConfigField('config.project_id', e.target.value)} placeholder="uuid" />
        </div>
      </div>

      <div style={{ border: '1px solid var(--info)', borderLeft: '3px solid var(--info)', borderRadius: 'var(--radius)', padding: 'var(--spacing-2) var(--spacing-3)', backgroundColor: 'rgba(96,165,250,0.06)', fontSize: 'var(--text-xs)', color: 'var(--gray-700)', lineHeight: '1.6' }}>
        <strong style={{ color: 'var(--info)' }}>Token permissions.</strong> Browse on target projects is enough for projects / overview / issues / hotspots.
        Mode <code style={{ background: 'var(--gray-200)', padding: '0 3px', borderRadius: '3px' }}>remediate</code> also needs See Source Code, otherwise the LLM gets no code snippet.
      </div>
    </div>
  );
};

export default {
  name: 'SonarQube Security',
  description: 'SonarQube audit — projects, vulnerabilities, security hotspots, quality gate and LLM-assisted remediation',
  icon: '◈', color: '#4E9BCD', badge: 'fixed', mcp: ['sonarqube'],
  defaultConfig: (providers) => ({
    mcp_servers: ['sonarqube'],
    mode: 'projects',
    analyze: false,
    page_size: 50,
    max_remediations: 3,
    snippet_context: 15,
    use_rag: false,
    project_id: '',
    llm_provider: providers[0]?.name || 'lmstudio',
    llm_model: 'openai/gpt-oss-20b',
    llm_temperature: 0.2,
  }),
  mcpConfig: { sonarqube: { base_url: '', token: '', verify_ssl: false, auth_mode: 'bearer', timeout: 30 } },
  requiredFields: ['sonarqube.base_url', 'sonarqube.token'],
  executeFields: [
    { name: 'mode', label: 'Mode', type: 'select', required: true, options: [
        { value: 'projects',  label: 'projects — inventory' },
        { value: 'overview',  label: 'overview — quality gate + metrics + posture' },
        { value: 'issues',    label: 'issues — vulnerabilities / bugs' },
        { value: 'hotspots',  label: 'hotspots — security hotspots' },
        { value: 'remediate', label: 'remediate — LLM fixes' },
      ], defaultValue: 'projects' },
    { name: 'query', label: 'Project filter (mode: projects)', type: 'text', placeholder: 'backend' },
    { name: 'project_key', label: 'Project key', type: 'text', placeholder: 'MON_PROJET' },
    { name: 'branch', label: 'Branch (optional)', type: 'text', placeholder: 'main' },
    { name: 'types', label: 'Types, comma-separated', type: 'text', placeholder: 'VULNERABILITY,BUG' },
    { name: 'severities', label: 'Severities, comma-separated', type: 'text', placeholder: 'BLOCKER,CRITICAL' },
    { name: 'issue_keys', label: 'Issue keys, comma-separated (overrides project selection)', type: 'text', placeholder: 'AY7xK...,AY8zL...' },
    { name: 'max_remediations', label: 'Max remediations', type: 'number', placeholder: '3' },
    { name: 'snippet_context', label: 'Snippet context (lines around issue)', type: 'number', placeholder: '15' },
    { name: 'page_size', label: 'Page size', type: 'number', placeholder: '50' },
    { name: 'with_quality_gate', label: 'Include quality gate per project', type: 'checkbox', defaultValue: false },
    { name: 'in_new_code_period', label: 'New code only', type: 'checkbox', defaultValue: false },
  ],
  buildInput: (d) => {
    const mode = d.mode || 'projects';
    const allowed = SONAR_FIELDS_BY_MODE[mode] || [];
    const csv = (v) => String(v).split(',').map(s => s.trim()).filter(Boolean);
    const has = (k) => allowed.includes(k) && d[k] !== undefined && d[k] !== '' && d[k] !== false;
    const r = { mode };
    if (has('query')) r.query = String(d.query).trim();
    if (has('project_key')) r.project_key = String(d.project_key).trim();
    if (has('branch')) r.branch = String(d.branch).trim();
    if (has('types')) r.types = csv(d.types).map(s => s.toUpperCase());
    if (has('severities')) r.severities = csv(d.severities).map(s => s.toUpperCase());
    if (has('issue_keys')) r.issue_keys = csv(d.issue_keys);
    if (has('with_quality_gate')) r.with_quality_gate = true;
    if (has('in_new_code_period')) r.in_new_code_period = true;
    ['page_size', 'max_remediations', 'snippet_context'].forEach(k => {
      if (has(k) && !isNaN(parseInt(d[k], 10))) r[k] = parseInt(d[k], 10);
    });
    return r;
  },
  validate: (d) => {
    const m = d.mode || 'projects';
    const hasKeys = m === 'remediate' && d.issue_keys?.trim();
    if (m !== 'projects' && !d.project_key?.trim() && !hasKeys) {
      return m === 'remediate' ? 'Project key or issue keys required' : 'Project key is required';
    }
    return null;
  },
  isFieldVisible: (field, d) => {
    if (field.name === 'mode') return true;
    return (SONAR_FIELDS_BY_MODE[d.mode || 'projects'] || []).includes(field.name);
  },
  // l'agent démarre sur le mode par défaut de sa configuration
  initialExecuteValues: (agent) => (agent.config?.mode ? { mode: agent.config.mode } : {}),
  formatResult: formatSonarResult,
  ConfigFields: SonarQubeConfigFields,
};
