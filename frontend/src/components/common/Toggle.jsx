const Toggle = ({ checked, onChange, disabled = false, label }) => (
  <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-2)' }}>
    <label className="toggle">
      <input
        type="checkbox"
        checked={!!checked}
        onChange={(e) => onChange(e.target.checked)}
        disabled={disabled}
      />
      <span className="toggle-slider" />
    </label>
    {label && <span style={{ fontSize: 'var(--text-sm)', color: 'var(--text-secondary)' }}>{label}</span>}
  </div>
);

export default Toggle;
