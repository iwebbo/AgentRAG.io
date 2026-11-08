// Connexion GitHub (token / repo) — branch_code_review, code_generator, ansible_role_generator,
// github_changelog, github_branch_generator
const GithubConnectionFields = ({ formData, updateConfigField }) => (
  <div style={{ padding: 'var(--spacing-4)', backgroundColor: 'var(--gray-100)', borderRadius: 'var(--radius)', marginBottom: 'var(--spacing-4)' }}>
    <h3 style={{ fontWeight: '600', fontSize: 'var(--text-sm)', marginBottom: 'var(--spacing-3)' }}>GitHub configuration</h3>
    <div className="form-group"><label className="form-label">GitHub token * <span style={{ fontSize: 'var(--text-xs)', color: 'var(--gray-500)' }}>Required for code operations</span></label><input type="password" className="form-input" value={formData.mcp_config.github?.token || ''} onChange={e => updateConfigField('mcp_config.github.token', e.target.value)} placeholder="ghp_..." /></div>
    <div className="form-group"><label className="form-label">Repository * <span style={{ fontSize: 'var(--text-xs)', color: 'var(--gray-500)' }}>username/repo</span></label><input type="text" className="form-input" value={formData.mcp_config.github?.repo || ''} onChange={e => updateConfigField('mcp_config.github.repo', e.target.value)} placeholder="username/repository" /></div>
  </div>
);

export default GithubConnectionFields;
