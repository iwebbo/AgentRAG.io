import { NODE_STATUS_COLOR } from './nodes/AgentNode';

const STATUS_LABEL = { idle: 'Not run yet', running: 'Running…', done: 'Completed', failed: 'Failed', stopped: 'Stopped' };

// Panneau affiché quand aucun node n'est sélectionné : état du dernier run.
const RunSummary = ({ run, nodes, onSelectNode, children }) => (
  <div style={{ padding: 'var(--spacing-3)' }}>
    <div style={{ fontWeight: 600, fontSize: 'var(--text-sm)' }}>Run — {STATUS_LABEL[run.status] || run.status}</div>
    {run.error && (
      <div style={{ marginTop: 6, fontSize: 12, color: 'var(--error)', wordBreak: 'break-word' }}>{run.error}</div>
    )}

    <div style={{ display: 'flex', flexDirection: 'column', gap: 4, marginTop: 'var(--spacing-3)' }}>
      {nodes.length === 0 && <div style={{ fontSize: 'var(--text-xs)', color: 'var(--gray-500)' }}>Add agents from the palette, then connect them.</div>}
      {nodes.map(n => {
        const st = run.nodes[n.id]?.status || 'idle';
        return (
          <button
            key={n.id}
            onClick={() => onSelectNode(n.id)}
            style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '5px 8px', background: 'var(--gray-100)', border: '1px solid var(--gray-200)', borderRadius: 'var(--radius)', cursor: 'pointer', textAlign: 'left', color: 'var(--text-primary)', fontSize: 12 }}
          >
            <span style={{ width: 8, height: 8, borderRadius: '50%', background: NODE_STATUS_COLOR[st], flexShrink: 0 }} />
            <span style={{ fontWeight: 600 }}>{n.id}</span>
            <span style={{ color: 'var(--gray-600)', flex: 1, minWidth: 0, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{n.data.agentName || 'no agent'}</span>
            <span style={{ color: 'var(--gray-500)' }}>{st}</span>
          </button>
        );
      })}
    </div>

    {run.logs.length > 0 && (
      <div style={{ marginTop: 'var(--spacing-3)' }}>
        {run.logs.map((l, i) => (
          <div key={i} style={{ display: 'flex', gap: 8, fontSize: 12, padding: '1px 0' }}>
            <span style={{ color: 'var(--gray-400)', fontFamily: 'monospace', fontSize: 11, flexShrink: 0 }}>{l.ts}</span>
            <span style={{ wordBreak: 'break-word' }}>{l.message}</span>
          </div>
        ))}
      </div>
    )}

    {children}
  </div>
);

export default RunSummary;
