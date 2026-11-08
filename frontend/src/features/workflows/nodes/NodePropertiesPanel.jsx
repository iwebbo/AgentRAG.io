import { AGENT_TYPES } from '../../agents/registry';
import { ExecuteFieldsForm } from '../../agents/components/FieldRenderer';

const pre = {
  margin: 0, padding: 'var(--spacing-2)', background: 'var(--bg-main)', color: 'var(--text-primary)',
  borderRadius: 'var(--radius)', fontFamily: 'monospace', fontSize: 12, lineHeight: 1.6,
  whiteSpace: 'pre-wrap', wordBreak: 'break-word', maxHeight: 260, overflowY: 'auto',
};
const code = { background: 'var(--gray-200)', padding: '0 3px', borderRadius: 3, fontSize: 11 };

// Panneau de propriétés d'un node : sélection de l'agent + formulaire généré depuis le registre
// (executeFields / ExecuteFields / isFieldVisible du type) — aucun formulaire propre au workflow.
const NodePropertiesPanel = ({ node, agents, hosts, upstreamIds, nodeRun, onChangeAgent, onChangeValue, onDelete, onBack }) => {
  const { data } = node;
  const type = AGENT_TYPES[data.agentType];
  const CustomFields = type?.ExecuteFields;
  const values = data.values || {};
  const knownAgent = agents.some(a => a.id === data.agentId);

  return (
    <div style={{ padding: 'var(--spacing-3)', display: 'flex', flexDirection: 'column', gap: 'var(--spacing-3)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
        <button
          title="Back to run summary and history"
          onClick={onBack}
          style={{ height: 28, padding: '0 8px', borderRadius: 'var(--radius)', border: '1px solid var(--gray-300)', background: 'var(--gray-100)', color: 'var(--text-primary)', cursor: 'pointer', fontSize: 12, flexShrink: 0 }}
        >← Back</button>
        <div style={{ fontWeight: 600, fontSize: 'var(--text-sm)', flex: 1, minWidth: 0 }}>Node <code style={code}>{node.id}</code></div>
        <button
          title="Delete node"
          onClick={() => onDelete(node.id)}
          style={{ width: 28, height: 28, borderRadius: 'var(--radius)', border: '1px solid var(--gray-300)', background: 'var(--gray-100)', color: 'var(--danger)', cursor: 'pointer' }}
        >✕</button>
      </div>

      <div className="form-group">
        <label className="form-label">Agent *</label>
        <select className="form-input" value={data.agentId || ''} onChange={e => onChangeAgent(node.id, e.target.value)}>
          <option value="">— select an agent —</option>
          {data.agentId && !knownAgent && <option value={data.agentId}>(missing agent) {data.agentId}</option>}
          {agents.map(a => <option key={a.id} value={a.id}>{a.name} — {AGENT_TYPES[a.agent_type]?.name}</option>)}
        </select>
      </div>

      {type && (
        <>
          {CustomFields ? (
            <CustomFields executeData={values} onChange={onChangeValue} hosts={hosts} />
          ) : (
            <ExecuteFieldsForm fields={type.executeFields} values={values} onChange={onChangeValue} isFieldVisible={type.isFieldVisible} />
          )}

          <div style={{ border: '1px solid var(--info)', borderLeft: '3px solid var(--info)', borderRadius: 'var(--radius)', padding: 'var(--spacing-2) var(--spacing-3)', backgroundColor: 'rgba(96,165,250,0.06)', fontSize: 'var(--text-xs)', color: 'var(--gray-700)', lineHeight: 1.6 }}>
            <strong style={{ color: 'var(--info)' }}>References.</strong>{' '}
            Any text field accepts <code style={code}>{'{{trigger.key}}'}</code> (run inputs)
            {upstreamIds.length > 0
              ? <> or the output of an upstream node: {upstreamIds.map(u => <code key={u} style={{ ...code, marginRight: 4 }}>{`{{nodes.${u}.output}}`}</code>)}</>
              : <>. Connect an upstream node to reference its output.</>}
          </div>
        </>
      )}

      {nodeRun && (nodeRun.output || nodeRun.error || nodeRun.logs?.length > 0) && (
        <div>
          <div style={{ fontWeight: 600, fontSize: 'var(--text-sm)', marginBottom: 6 }}>Last run — {nodeRun.status}</div>
          {nodeRun.error && <pre style={{ ...pre, color: 'var(--error)', marginBottom: 6 }}>{nodeRun.error}</pre>}
          {nodeRun.output && <pre style={pre}>{nodeRun.output}</pre>}
          {nodeRun.logs?.length > 0 && (
            <div style={{ marginTop: 6 }}>
              {nodeRun.logs.map((l, i) => (
                <div key={i} style={{ display: 'flex', gap: 8, fontSize: 12, padding: '1px 0' }}>
                  <span style={{ color: 'var(--gray-400)', fontFamily: 'monospace', fontSize: 11, flexShrink: 0 }}>{l.ts}</span>
                  <span style={{ wordBreak: 'break-word' }}>{l.message}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default NodePropertiesPanel;
