import { NODE_STATUS_COLOR } from './nodes/AgentNode';

const STATUS_META = {
  success: { label: 'Completed', color: NODE_STATUS_COLOR.done },
  failed: { label: 'Failed', color: NODE_STATUS_COLOR.failed },
  cancelled: { label: 'Stopped', color: NODE_STATUS_COLOR.idle },
  running: { label: 'Running', color: NODE_STATUS_COLOR.running },
};

// Le backend renvoie des datetimes UTC naïfs (sans suffixe) : on force l'UTC pour l'affichage.
const parseUtc = (s) => (s ? new Date(/(Z|[+-]\d\d:\d\d)$/.test(s) ? s : `${s}Z`) : null);

const inputPreview = (input) => {
  if (!input || Object.keys(input).length === 0) return '';
  const t = JSON.stringify(input);
  return t.length > 60 ? `${t.slice(0, 60)}…` : t;
};

const formatDuration = (start, end) => {
  if (!start || !end) return '';
  const sec = Math.max(0, Math.round((end - start) / 1000));
  if (sec < 60) return `${sec}s`;
  return `${Math.floor(sec / 60)}m ${sec % 60}s`;
};

// Historique des exécutions (persisté côté backend). Un clic charge le run dans l'éditeur.
const RunHistory = ({ runs, loading, activeId, disabled, onSelect }) => (
  <div style={{ marginTop: 'var(--spacing-4)', paddingTop: 'var(--spacing-3)', borderTop: '1px solid var(--gray-200)' }}>
    <div style={{ fontWeight: 600, fontSize: 'var(--text-sm)', marginBottom: 6 }}>
      History{loading ? ' …' : ''}
    </div>
    {!loading && runs.length === 0 && (
      <div style={{ fontSize: 'var(--text-xs)', color: 'var(--gray-500)' }}>No run yet.</div>
    )}
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      {runs.map(r => {
        const meta = STATUS_META[r.status] || STATUS_META.cancelled;
        const start = parseUtc(r.started_at);
        const end = parseUtc(r.completed_at);
        const active = r.id === activeId;
        return (
          <button
            key={r.id}
            onClick={() => onSelect(r.id)}
            disabled={disabled}
            style={{
              display: 'flex', alignItems: 'center', gap: 8, padding: '5px 8px', textAlign: 'left',
              background: active ? 'var(--gray-200)' : 'var(--gray-100)',
              border: `1px solid ${active ? 'var(--primary)' : 'var(--gray-200)'}`,
              borderRadius: 'var(--radius)', cursor: disabled ? 'not-allowed' : 'pointer',
              color: 'var(--text-primary)', fontSize: 12, opacity: disabled ? 0.6 : 1,
            }}
          >
            <span style={{ width: 8, height: 8, borderRadius: '50%', background: meta.color, flexShrink: 0 }} />
            <span style={{ flex: 1, minWidth: 0 }}>
              <span style={{ display: 'block' }}>{start ? start.toLocaleString() : '—'}</span>
              <span style={{ display: 'block', color: 'var(--gray-600)' }}>{meta.label}</span>
              {inputPreview(r.input_data) && (
                <span style={{ display: 'block', color: 'var(--gray-500)', fontFamily: 'var(--font-mono)', fontSize: 11, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {inputPreview(r.input_data)}
                </span>
              )}
            </span>
            <span style={{ color: 'var(--gray-500)', flexShrink: 0 }}>{formatDuration(start, end)}</span>
          </button>
        );
      })}
    </div>
  </div>
);

export default RunHistory;
