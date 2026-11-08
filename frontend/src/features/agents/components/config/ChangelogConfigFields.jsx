// Config commune des agents changelog (github_changelog / gitea_changelog)
const ChangelogConfigFields = ({ formData, updateConfigField }) => {
  const cfg = formData.config || {};
  const hint = { fontSize: 'var(--text-xs)', color: 'var(--gray-500)' };
  const num = (v, d) => (v === '' || isNaN(parseInt(v, 10)) ? d : parseInt(v, 10));
  const inline = { background: 'var(--gray-200)', padding: '0 3px', borderRadius: '3px' };
  return (
    <div style={{ padding: 'var(--spacing-4)', backgroundColor: 'var(--gray-100)', borderRadius: 'var(--radius)', marginBottom: 'var(--spacing-4)' }}>
      <h3 style={{ fontWeight: '600', fontSize: 'var(--text-sm)', marginBottom: 'var(--spacing-3)' }}>Changelog configuration</h3>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 'var(--spacing-3)' }}>
        <div className="form-group">
          <label className="form-label">Base branch <span style={hint}>target of the PRs</span></label>
          <input type="text" className="form-input" value={cfg.base_branch || 'main'} onChange={e => updateConfigField('config.base_branch', e.target.value)} placeholder="main" />
        </div>
        <div className="form-group">
          <label className="form-label">PR state</label>
          <select className="form-input" value={cfg.pr_state || 'open'} onChange={e => updateConfigField('config.pr_state', e.target.value)}>
            <option value="open">open</option>
            <option value="closed">closed</option>
            <option value="all">all</option>
          </select>
        </div>
        <div className="form-group">
          <label className="form-label">PR scan limit <span style={hint}>1–100</span></label>
          <input type="number" min="1" max="100" className="form-input" value={cfg.pr_scan_limit ?? 30} onChange={e => updateConfigField('config.pr_scan_limit', num(e.target.value, 30))} />
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--spacing-3)' }}>
        <div className="form-group">
          <label className="form-label">Changelog path</label>
          <input type="text" className="form-input" value={cfg.changelog_path || 'CHANGELOG.md'} onChange={e => updateConfigField('config.changelog_path', e.target.value)} placeholder="CHANGELOG.md" />
        </div>
        <div className="form-group">
          <label className="form-label">Changelog title <span style={hint}>optional — default: &lt;repo&gt; Changelog</span></label>
          <input type="text" className="form-input" value={cfg.changelog_title || ''} onChange={e => updateConfigField('config.changelog_title', e.target.value)} placeholder="AgentRAG.io Changelog" />
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: 'var(--spacing-3)', alignItems: 'end' }}>
        <div className="form-group">
          <label className="form-label">Language</label>
          <select className="form-input" value={cfg.language || 'en'} onChange={e => updateConfigField('config.language', e.target.value)}>
            <option value="en">en</option>
            <option value="fr">fr</option>
            {cfg.language && !['en', 'fr'].includes(cfg.language) && <option value={cfg.language}>{cfg.language}</option>}
          </select>
        </div>
        <div style={{ display: 'flex', gap: 'var(--spacing-4)', flexWrap: 'wrap', paddingBottom: 'var(--spacing-3)' }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-2)', cursor: 'pointer', fontSize: 'var(--text-sm)' }}>
            <input type="checkbox" checked={cfg.use_llm !== false} onChange={e => updateConfigField('config.use_llm', e.target.checked)} />Use LLM
          </label>
          <label style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-2)', cursor: 'pointer', fontSize: 'var(--text-sm)' }}>
            <input type="checkbox" checked={!!cfg.skip_ci} onChange={e => updateConfigField('config.skip_ci', e.target.checked)} />Skip CI <span style={hint}>[skip ci]</span>
          </label>
        </div>
      </div>

      <div style={{ border: '1px solid var(--info)', borderLeft: '3px solid var(--info)', borderRadius: 'var(--radius)', padding: 'var(--spacing-2) var(--spacing-3)', backgroundColor: 'rgba(96,165,250,0.06)', fontSize: 'var(--text-xs)', color: 'var(--gray-700)', lineHeight: '1.6' }}>
        <strong style={{ color: 'var(--info)' }}>How it works.</strong> The version is set at execution. The agent finds the latest PR targeting the base branch (or the PR number you give),
        merges the new section into <code style={inline}>{cfg.changelog_path || 'CHANGELOG.md'}</code> and pushes it to the PR source branch. No tag and no release are created.
        With Use LLM disabled, or if the LLM output is invalid, a deterministic conventional-commits fallback is used.
      </div>
    </div>
  );
};

export default ChangelogConfigFields;
