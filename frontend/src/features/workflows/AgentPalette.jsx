import { AGENT_TYPES } from '../agents/registry';

export const DRAG_MIME = 'application/x-workflow-agent-id';

// Palette : tous les agents actifs dont le type est connu du registre.
// Un nouvel agent (ou un nouveau type enregistré) apparaît ici sans modification.
const AgentPalette = ({ agents, onAdd }) => (
  <aside style={{ width: 220, flexShrink: 0, borderRight: '1px solid var(--gray-200)', overflowY: 'auto', padding: 'var(--spacing-3)', background: 'var(--bg-card)' }}>
    <div style={{ fontWeight: 600, fontSize: 'var(--text-sm)' }}>Agents</div>
    <div style={{ fontSize: 'var(--text-xs)', color: 'var(--gray-600)', margin: '2px 0 var(--spacing-3)' }}>Click or drag onto the canvas</div>
    {agents.length === 0 && <div style={{ fontSize: 'var(--text-xs)', color: 'var(--gray-500)' }}>No active agent available</div>}
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      {agents.map(a => {
        const t = AGENT_TYPES[a.agent_type];
        return (
          <div
            key={a.id}
            draggable
            onDragStart={e => { e.dataTransfer.setData(DRAG_MIME, a.id); e.dataTransfer.effectAllowed = 'move'; }}
            onClick={() => onAdd(a)}
            title={t?.description}
            style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '6px 8px', cursor: 'grab', background: 'var(--gray-100)', border: '1px solid var(--gray-200)', borderLeft: `3px solid ${t?.color || 'var(--gray-400)'}`, borderRadius: 'var(--radius)' }}
          >
            <span style={{ fontSize: 16 }}>{t?.icon}</span>
            <div style={{ minWidth: 0 }}>
              <div style={{ fontSize: 'var(--text-sm)', fontWeight: 500, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{a.name}</div>
              <div style={{ fontSize: 10, color: 'var(--gray-600)' }}>{t?.name}</div>
            </div>
          </div>
        );
      })}
    </div>
  </aside>
);

export default AgentPalette;
