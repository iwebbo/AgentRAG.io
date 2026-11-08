import { memo, useContext } from 'react';
import { Handle, Position } from '@xyflow/react';
import { AGENT_TYPES } from '../../agents/registry';
import { RunStateContext } from './RunStateContext';

export const NODE_STATUS_COLOR = {
  idle: 'var(--gray-400)',
  running: '#f59e0b',
  done: 'var(--success)',
  failed: 'var(--error)',
};

// Node « agent » : l'icône, la couleur et le nom viennent du registre, rien n'est codé par type ici.
const AgentNode = ({ id, data, selected }) => {
  const run = useContext(RunStateContext);
  const status = run.nodes?.[id]?.status || 'idle';
  const type = AGENT_TYPES[data.agentType];
  const missing = !data.agentId || !type;

  return (
    <div style={{
      width: 210, background: 'var(--bg-card)', borderRadius: 'var(--radius-md)', padding: '8px 10px',
      border: `1px solid ${selected ? 'var(--primary)' : 'var(--gray-300)'}`,
      borderLeft: `3px solid ${type?.color || 'var(--gray-400)'}`,
      boxShadow: selected ? '0 0 0 2px rgba(96,165,250,.35)' : 'none',
    }}>
      <Handle type="target" position={Position.Left} />
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ fontSize: 18 }}>{type?.icon || '?'}</span>
        <div style={{ minWidth: 0, flex: 1 }}>
          <div style={{ fontWeight: 600, fontSize: 'var(--text-sm)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {data.agentName || (missing ? 'Select an agent' : data.agentId)}
          </div>
          <div style={{ fontSize: 11, color: 'var(--gray-600)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {type?.name || (data.agentId ? 'agent not found' : '—')} · {id}
          </div>
        </div>
        <span
          title={status}
          style={{
            width: 9, height: 9, borderRadius: '50%', flexShrink: 0, background: NODE_STATUS_COLOR[status],
            animation: status === 'running' ? 'pulse 1s infinite' : 'none',
          }}
        />
      </div>
      <Handle type="source" position={Position.Right} />
    </div>
  );
};

export default memo(AgentNode);
