import { useState } from 'react';
import Button from '../../components/common/Button';
import Alert from '../../components/common/Alert';

// Saisie des entrées du run : objet JSON envoyé comme input_data, référencé par {{trigger.<clé>}}
const RunDialog = ({ onRun, onClose }) => {
  const [text, setText] = useState('{\n  \n}');
  const [error, setError] = useState(null);

  const submit = () => {
    let parsed;
    try {
      parsed = text.trim() ? JSON.parse(text) : {};
    } catch (e) {
      setError(`Invalid JSON: ${e.message}`);
      return;
    }
    if (parsed === null || typeof parsed !== 'object' || Array.isArray(parsed)) {
      setError('Trigger inputs must be a JSON object');
      return;
    }
    onRun(parsed);
  };

  return (
    <div style={{ position: 'fixed', inset: 0, backgroundColor: 'var(--overlay)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, padding: 'var(--spacing-4)' }}>
      <div className="card" style={{ width: '100%', maxWidth: 520 }}>
        <h2 style={{ fontSize: 'var(--text-xl)', fontWeight: 600, marginBottom: 'var(--spacing-1)' }}>Run workflow</h2>
        <p style={{ fontSize: 'var(--text-sm)', color: 'var(--gray-600)', marginBottom: 'var(--spacing-3)' }}>
          Trigger inputs (JSON object), available as <code>{'{{trigger.<key>}}'}</code> in the nodes. Leave empty if none.
        </p>
        {error && <Alert type="error" style={{ marginBottom: 'var(--spacing-3)' }} onClose={() => setError(null)}>{error}</Alert>}
        <textarea
          className="form-input"
          rows={8}
          value={text}
          onChange={e => setText(e.target.value)}
          style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}
          placeholder={'{ "query": "..." }'}
        />
        <div style={{ display: 'flex', gap: 'var(--spacing-3)', justifyContent: 'flex-end', marginTop: 'var(--spacing-4)', paddingTop: 'var(--spacing-4)', borderTop: '1px solid var(--gray-200)' }}>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button variant="primary" onClick={submit}>▶ Run</Button>
        </div>
      </div>
    </div>
  );
};

export default RunDialog;
