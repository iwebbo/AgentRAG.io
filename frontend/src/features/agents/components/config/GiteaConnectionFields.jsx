// Connexion Gitea (url / token / repo) — gitea_changelog, gitea_branch_generator
const GiteaConnectionFields = ({ formData, updateConfigField }) => (
  <div style={{ padding: 'var(--spacing-4)', backgroundColor: 'var(--gray-100)', borderRadius: 'var(--radius)', marginBottom: 'var(--spacing-4)' }}>
    <h3 style={{ fontWeight: '600', fontSize: 'var(--text-sm)', marginBottom: 'var(--spacing-3)' }}>Gitea configuration</h3>
    <div className="form-group"><label className="form-label">Gitea URL * <span style={{ fontSize: 'var(--text-xs)', color: 'var(--gray-500)' }}>base URL, without /api/v1</span></label><input type="text" className="form-input" value={formData.mcp_config.gitea?.url || ''} onChange={e => updateConfigField('mcp_config.gitea.url', e.target.value)} placeholder="http://gitea.example.local:3000" /></div>
    <div className="form-group"><label className="form-label">Access token * <span style={{ fontSize: 'var(--text-xs)', color: 'var(--gray-500)' }}>Settings → Applications</span></label><input type="password" className="form-input" value={formData.mcp_config.gitea?.token || ''} onChange={e => updateConfigField('mcp_config.gitea.token', e.target.value)} placeholder="Gitea access token" /></div>
    <div className="form-group"><label className="form-label">Repository * <span style={{ fontSize: 'var(--text-xs)', color: 'var(--gray-500)' }}>owner/repo</span></label><input type="text" className="form-input" value={formData.mcp_config.gitea?.repo || ''} onChange={e => updateConfigField('mcp_config.gitea.repo', e.target.value)} placeholder="username/my-repo" /></div>
  </div>
);

export default GiteaConnectionFields;
