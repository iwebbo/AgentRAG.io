// Rendu générique des executeFields d'un type d'agent.
// Utilisé par ExecuteAgentModal ; réutilisable tel quel (panneau de propriétés d'un node workflow, etc.).

export const FieldInput = ({ field, value, onChange }) => {
  switch (field.type) {
    case 'textarea':
      return <textarea className="form-input" value={value} onChange={e => onChange(field.name, e.target.value)} placeholder={field.placeholder} rows={4} />;
    case 'checkbox':
      return (
        <label style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-2)', cursor: 'pointer' }}>
          <input type="checkbox" checked={!!value} onChange={e => onChange(field.name, e.target.checked)} />
          <span style={{ fontSize: 'var(--text-sm)' }}>{field.label}</span>
        </label>
      );
    case 'select':
      return (
        <select className="form-input" value={value} onChange={e => onChange(field.name, e.target.value)}>
          <option value="">Select {field.label}</option>
          {field.options?.map(opt => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
        </select>
      );
    case 'number':
      return <input type="number" className="form-input" value={value} onChange={e => onChange(field.name, e.target.value)} placeholder={field.placeholder} />;
    default:
      return <input type="text" className="form-input" value={value} onChange={e => onChange(field.name, e.target.value)} placeholder={field.placeholder} />;
  }
};

export const FieldRenderer = ({ field, value, onChange }) => (
  <div className="form-group">
    {field.type !== 'checkbox' && <label className="form-label">{field.label}{field.required && ' *'}</label>}
    <FieldInput field={field} value={value} onChange={onChange} />
  </div>
);

// isFieldVisible(field, values) : prédicat optionnel fourni par le type (champs conditionnels par mode)
export const ExecuteFieldsForm = ({ fields, values, onChange, isFieldVisible }) => (
  <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-4)' }}>
    {fields?.map(field => {
      if (isFieldVisible && !isFieldVisible(field, values)) return null;
      return <FieldRenderer key={field.name} field={field} value={values[field.name] ?? ''} onChange={onChange} />;
    })}
  </div>
);

export default FieldRenderer;
