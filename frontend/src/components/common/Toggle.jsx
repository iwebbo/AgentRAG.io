const Toggle = ({ checked, onChange, disabled = false, label }) => {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-2)' }}>
      <label className="toggle">
        <input
          type="checkbox"
          checked={checked}
          onChange={(e) => onChange(e.target.checked)}
          disabled={disabled}
        />
        <span className="toggle-slider"></span>
      </label>
      {label && <span style={{ fontSize: 'var(--text-sm)', color: 'var(--gray-700)' }}>{label}</span>}
    </div>
  );
};

export default Toggle;