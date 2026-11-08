import { AGENT_TYPES } from '../registry';
import { RUN_STATUS_META } from '../utils/runUtils';
import AgentRunDrawer from './AgentRunDrawer';

// ─────────────────────────────────────────────────────────────────────────────
// RUN DOCK — drawer de l'exécution active, ou pastilles quand il est réduit
// ─────────────────────────────────────────────────────────────────────────────
const AgentRunDock = ({ runs, activeRunId, drawerOpen, onSelect, onMinimize, onDismiss, onRunAgain, onOpenExecution }) => {
  if (!runs.length) return null;
  const active = runs.find(r => r.id === activeRunId) || runs[runs.length - 1];

  if (drawerOpen && active) {
    return (
      <AgentRunDrawer
        key={active.id}
        run={active}
        runs={runs}
        onSelect={onSelect}
        onMinimize={onMinimize}
        onDismiss={onDismiss}
        onRunAgain={onRunAgain}
        onOpenExecution={onOpenExecution}
      />
    );
  }

  return (
    <div style={{ position: 'fixed', right: '20px', bottom: '20px', zIndex: 900, display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '8px', maxHeight: '60vh', overflowY: 'auto' }}>
      {runs.map(r => {
        const m = RUN_STATUS_META[r.status] || RUN_STATUS_META.running;
        const agentType = AGENT_TYPES[r.agent.agent_type];
        return (
          <div key={r.id} style={{ display: 'flex', alignItems: 'center', background: 'var(--bg-card)', border: `1px solid ${m.dot}`, borderRadius: '99px', boxShadow: '0 6px 20px rgba(0,0,0,0.25)', overflow: 'hidden' }}>
            <button onClick={() => onSelect(r.id)} title={r.label || r.agent.name} style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', padding: '8px 14px', background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-primary)', fontSize: '12px' }}>
              <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: m.dot, display: 'inline-block', animation: r.status === 'running' ? 'pulse 1s infinite' : 'none' }} />
              <span style={{ fontWeight: '600' }}>{agentType?.icon} {r.agent.name}</span>
              <span style={{ color: m.color }}>{r.status === 'running' ? 'running…' : r.status === 'done' ? 'done ✓' : 'failed ✗'}</span>
            </button>
            {r.status !== 'running' && (
              <button title="Dismiss" onClick={() => onDismiss(r.id)} style={{ background: 'none', border: 'none', borderLeft: '1px solid var(--gray-200)', cursor: 'pointer', color: 'var(--gray-500)', padding: '8px 10px', fontSize: '12px' }}>✕</button>
            )}
          </div>
        );
      })}
    </div>
  );
};

export default AgentRunDock;
