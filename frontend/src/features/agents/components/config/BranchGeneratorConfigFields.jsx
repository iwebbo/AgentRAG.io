// Config des agents branch generator (github_branch_generator / gitea_branch_generator)
const BranchGeneratorConfigFields = ({ formData, updateConfigField }) => {
  const cfg = formData.config || {};
  const hint = { fontSize: 'var(--text-xs)', color: 'var(--gray-500)' };
  const num = (v, d) => (v === '' || isNaN(parseInt(v, 10)) ? d : parseInt(v, 10));
  return (
    <div style={{ padding: 'var(--spacing-4)', backgroundColor: 'var(--gray-100)', borderRadius: 'var(--radius)', marginBottom: 'var(--spacing-4)' }}>
      <h3 style={{ fontWeight: '600', fontSize: 'var(--text-sm)', marginBottom: 'var(--spacing-3)' }}>Branch generator configuration</h3>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--spacing-3)' }}>
        <div className="form-group">
          <label className="form-label">Base branch <span style={hint}>new branch is created from it</span></label>
          <input type="text" className="form-input" value={cfg.base_branch || 'main'} onChange={e => updateConfigField('config.base_branch', e.target.value)} placeholder="main" />
        </div>
        <div className="form-group">
          <label className="form-label">Max files <span style={hint}>1–200</span></label>
          <input type="number" min="1" max="200" className="form-input" value={cfg.max_files ?? 40} onChange={e => updateConfigField('config.max_files', num(e.target.value, 40))} />
        </div>
      </div>
      <label style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-2)', cursor: 'pointer', fontSize: 'var(--text-sm)' }}>
        <input type="checkbox" checked={!!cfg.auto_create_pr} onChange={e => updateConfigField('config.auto_create_pr', e.target.checked)} />
        Auto create PR <span style={hint}>open a Pull Request to the base branch after the push</span>
      </label>
    </div>
  );
};

export default BranchGeneratorConfigFields;
