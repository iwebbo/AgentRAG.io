// Agent type « skill » — tout ce qui le concerne est ici (voir registry/README.md)

// Champs d'exécution spécifiques (hôte résolu depuis l'onglet Hosts)
const SkillExecuteFields = ({ executeData, onChange, hosts }) => (
  <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-4)' }}>
    <div className="form-group">
      <label className="form-label">Command <span style={{ color: 'var(--danger)' }}>*</span></label>
      <input type="text" className="form-input" value={executeData.query || ''} onChange={e => onChange('query', e.target.value)} placeholder="disk | restart nginx | pods | logs sshd | cleanup" />
      <div style={{ marginTop: 'var(--spacing-2)', border: '1px solid var(--info)', borderLeft: '3px solid var(--info)', borderRadius: 'var(--radius)', padding: 'var(--spacing-2) var(--spacing-3)', backgroundColor: 'rgba(96,165,250,0.06)', fontSize: 'var(--text-xs)', color: 'var(--gray-700)', lineHeight: '1.6' }}>
        <strong style={{ color: 'var(--info)' }}>Command = a mapping entry from your .md skill file.</strong>{' '}
        This agent is already bound to its skill via <code style={{ background: 'var(--gray-200)', padding: '0 3px', borderRadius: '3px' }}>skill_id</code> set at creation.
        The backend resolves the command against the <code style={{ background: 'var(--gray-200)', padding: '0 3px', borderRadius: '3px' }}>## Mapping</code> section automatically.
      </div>
    </div>
    <div className="form-group">
      <label className="form-label">Target host <span style={{ color: 'var(--danger)' }}>*</span></label>
      <select className="form-input" value={executeData.host || ''} onChange={e => onChange('host', e.target.value)}>
        <option value="">— select a registered host —</option>
        {hosts.map(h => (
          <option key={h.id} value={h.name}>{h.name} — {h.host} ({h.protocol}){!h.is_active ? ' [inactive]' : ''}</option>
        ))}
      </select>
      <p style={{ fontSize: 'var(--text-xs)', color: 'var(--gray-600)', marginTop: '4px' }}>
        Loaded from <code style={{ fontSize: '11px', background: 'var(--gray-200)', padding: '0 3px', borderRadius: '3px' }}>GET /api/hosts/</code> — manage hosts in the Hosts tab
      </p>
    </div>
    <div className="form-group">
      <label className="form-label">Conversation ID <span style={{ color: 'var(--gray-500)', fontSize: 'var(--text-xs)' }}>(optional — cross-turn memory)</span></label>
      <input type="text" className="form-input" value={executeData.conversation_id || ''} onChange={e => onChange('conversation_id', e.target.value)} placeholder="uuid — leave empty for a new session" />
    </div>
  </div>
);

// Config spécifique skill
const SkillConfigFields = ({ formData, skills, updateConfigField }) => (
  <div style={{ padding: 'var(--spacing-4)', backgroundColor: 'var(--gray-100)', borderRadius: 'var(--radius)', marginBottom: 'var(--spacing-4)' }}>
    <h3 style={{ fontWeight: '600', fontSize: 'var(--text-sm)', marginBottom: 'var(--spacing-3)' }}>Skill configuration</h3>
    <div className="form-group">
      <label className="form-label">Default skill <span style={{ color: 'var(--gray-500)', fontSize: 'var(--text-xs)' }}>(optional — auto-resolved at execution by semantic search)</span></label>
      <select className="form-input" value={formData.config.skill_id || ''} onChange={e => updateConfigField('config.skill_id', e.target.value)}>
        <option value="">— auto-detect —</option>
        {skills.map(s => <option key={s.skill_id} value={s.skill_id}>{s.skill_id} — {s.description}</option>)}
      </select>
      <p style={{ fontSize: 'var(--text-xs)', color: 'var(--gray-600)', marginTop: '4px' }}>Skills loaded from <code style={{ fontSize: '11px' }}>GET /api/skills/</code> — Register via <code style={{ fontSize: '11px' }}>POST /api/skills/register</code>.</p>
    </div>
    <div className="form-group">
      <label className="form-label">Memory scope</label>
      <select className="form-input" value={formData.config.memory_scope || 'session+global'} onChange={e => updateConfigField('config.memory_scope', e.target.value)}>
        <option value="session+global">session+global (recommended)</option>
        <option value="session">session only</option>
        <option value="global">global only</option>
        <option value="none">none</option>
      </select>
    </div>
  </div>
);

export default {
  name: 'Skill Agent',
  description: 'Executes a registered .md skill (ssh_admin, winrm_admin, k8s_ops, postgres_ops…) on a remote host via SSH, WinRM, PSRP or a database connection (DB)',
  icon: '⌥', color: '#6366f1', badge: 'skill', mcp: ['ssh', 'winrm', 'psrp', 'db'],
  defaultConfig: (providers) => ({ mcp_servers: ['ssh'], llm_provider: providers[0]?.name || 'lmstudio', llm_model: 'openai/gpt-oss-20b', llm_temperature: 0.2, memory_scope: 'session+global' }),
  mcpConfig: {}, requiredFields: [], executeFields: [],
  buildInput: (d) => {
    const r = { query: d.query, host: d.host };
    if (d.skill_id) r.skill_id = d.skill_id;
    if (d.conversation_id) r.conversation_id = d.conversation_id;
    return r;
  },
  validate: (d) => {
    if (!d.query?.trim()) return 'Command is required';
    if (!d.host) return 'Target host is required';
    return null;
  },
  ExecuteFields: SkillExecuteFields,
  ConfigFields: SkillConfigFields,
};
