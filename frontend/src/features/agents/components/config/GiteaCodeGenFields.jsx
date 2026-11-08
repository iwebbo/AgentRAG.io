// Connexion Gitea + branches + options auto — gitea_code_generator, gitea_ansible_role_generator
const GiteaCodeGenFields = ({ formData, updateConfigField }) => (
  <div style={{ padding: 'var(--spacing-4)', backgroundColor: 'var(--gray-100)', borderRadius: 'var(--radius)', marginBottom: 'var(--spacing-4)' }}>
    <h3 style={{ fontWeight: '600', fontSize: 'var(--text-sm)', marginBottom: 'var(--spacing-3)' }}>Gitea configuration</h3>
    <div className="form-group"><label className="form-label">Gitea URL *</label><input type="text" className="form-input" value={formData.mcp_config.gitea?.url || ''} onChange={e => updateConfigField('mcp_config.gitea.url', e.target.value)} placeholder="http://gitea.example.local:3000" /></div>
    <div className="form-group"><label className="form-label">Access token * <span style={{ fontSize: 'var(--text-xs)', color: 'var(--gray-500)' }}>Settings → Applications</span></label><input type="password" className="form-input" value={formData.mcp_config.gitea?.token || ''} onChange={e => updateConfigField('mcp_config.gitea.token', e.target.value)} placeholder="27d917559497ec0c…" /></div>
    <div className="form-group"><label className="form-label">Repository * <span style={{ fontSize: 'var(--text-xs)', color: 'var(--gray-500)' }}>owner/repo</span></label><input type="text" className="form-input" value={formData.mcp_config.gitea?.repo || ''} onChange={e => updateConfigField('mcp_config.gitea.repo', e.target.value)} placeholder="username/my-repo" /></div>
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--spacing-3)', marginBottom: 'var(--spacing-3)' }}>
      <div className="form-group"><label className="form-label">Base branch</label><input type="text" className="form-input" value={formData.config.base_branch || 'main'} onChange={e => updateConfigField('config.base_branch', e.target.value)} placeholder="main" /></div>
      <div className="form-group"><label className="form-label">Target branch (AI)</label><input type="text" className="form-input" value={formData.config.target_branch || 'ai-feature'} onChange={e => updateConfigField('config.target_branch', e.target.value)} placeholder="ai-feature" /></div>
    </div>
    <div style={{ display: 'flex', gap: 'var(--spacing-4)', flexWrap: 'wrap' }}>
      {[{ key: 'auto_lint', label: 'Auto lint' }, { key: 'auto_commit', label: 'Auto commit' }, { key: 'auto_create_pr', label: 'Auto create PR' }, { key: 'auto_test', label: 'Auto test' }].map(({ key, label }) => (
        <label key={key} style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-2)', cursor: 'pointer', fontSize: 'var(--text-sm)' }}>
          <input type="checkbox" checked={!!formData.config[key]} onChange={e => updateConfigField(`config.${key}`, e.target.checked)} />{label}
        </label>
      ))}
    </div>
  </div>
);

export default GiteaCodeGenFields;
