import { useState } from 'react';
import Button from '../../../components/common/Button';
import Alert from '../../../components/common/Alert';
import { buildExecuteInput, validateExecuteInput } from '../registry';
import { ExecuteFieldsForm } from './FieldRenderer';

// ─────────────────────────────────────────────────────────────────────────────
// EXECUTE MODAL — formulaire de lancement uniquement. Toute la logique propre à un type
// (payload, validation, champs conditionnels, valeurs initiales) vient du registre :
// registry/types/<agent_type>.jsx. L'exécution et le flux SSE sont pris en charge par useAgentRuns.
// ─────────────────────────────────────────────────────────────────────────────
const ExecuteAgentModal = ({ agent, agentType, onClose, onStart, hosts, initialValues }) => {
  const [executeData, setExecuteData] = useState(() => {
    const defaults = {};
    agentType?.executeFields?.forEach(f => {
      if (f.defaultValue !== undefined) defaults[f.name] = f.defaultValue;
    });
    Object.assign(defaults, agentType?.initialExecuteValues?.(agent) || {});
    return { ...defaults, ...(initialValues || {}) };
  });
  const [error, setError] = useState(null);

  const handleChange = (name, value) => setExecuteData(prev => ({ ...prev, [name]: value }));

  const handleSubmit = () => {
    const message = validateExecuteInput(agent.agent_type, executeData);
    if (message) { setError(message); return; }
    setError(null);
    onStart(buildExecuteInput(agent.agent_type, executeData), executeData);
  };

  // composant de champs propre au type (ex. skill : sélecteur d'hôte), sinon formulaire générique
  const CustomFields = agentType?.ExecuteFields;

  return (
    <div style={{ position: 'fixed', inset: 0, backgroundColor: 'var(--overlay)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, padding: 'var(--spacing-4)' }}>
      <div className="card" style={{ width: '100%', maxWidth: '680px', maxHeight: '90vh', overflow: 'auto' }}>

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 'var(--spacing-4)' }}>
          <div>
            <h2 style={{ fontSize: 'var(--text-xl)', fontWeight: '600', marginBottom: 'var(--spacing-1)' }}>
              Execute — {agent.name}
            </h2>
            <p style={{ fontSize: 'var(--text-sm)', color: 'var(--gray-600)' }}>
              {agentType?.name} · {agentType?.mcp?.join(', ') || 'no MCP'}
            </p>
          </div>
          <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--gray-600)', fontSize: '1.25rem', lineHeight: 1 }}>✕</button>
        </div>

        {error && <Alert type="error" style={{ marginBottom: 'var(--spacing-4)' }} onClose={() => setError(null)}>{error}</Alert>}

        {CustomFields ? (
          <CustomFields executeData={executeData} onChange={handleChange} hosts={hosts} />
        ) : (
          <ExecuteFieldsForm
            fields={agentType?.executeFields}
            values={executeData}
            onChange={handleChange}
            isFieldVisible={agentType?.isFieldVisible}
          />
        )}

        <div style={{ display: 'flex', gap: 'var(--spacing-3)', justifyContent: 'flex-end', marginTop: 'var(--spacing-6)', paddingTop: 'var(--spacing-4)', borderTop: '1px solid var(--gray-300)' }}>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button variant="primary" onClick={handleSubmit}>▶ Execute agent</Button>
        </div>
      </div>
    </div>
  );
};
export default ExecuteAgentModal;
