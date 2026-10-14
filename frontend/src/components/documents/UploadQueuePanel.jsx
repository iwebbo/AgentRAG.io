import { Loader2, Check, X } from 'lucide-react';

const formatSize = (bytes) => {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
};

const ACTIVE = ['queued', 'uploading', 'processing'];

const statusView = (item) => {
  switch (item.status) {
    case 'queued':
      return { color: 'var(--text-muted)', icon: null, text: 'Queued' };
    case 'uploading':
      return { color: 'var(--text-secondary)', icon: <Loader2 size={12} className="animate-spin" />, text: `Uploading ${item.progress}%` };
    case 'processing':
      return { color: 'var(--warning-fg)', icon: <Loader2 size={12} className="animate-spin" />, text: 'Indexing…' };
    case 'completed':
      return { color: 'var(--success-fg)', icon: <Check size={12} />, text: `Indexed · ${item.chunks ?? 0} chunks` };
    default:
      return { color: 'var(--danger-fg)', icon: <X size={12} />, text: item.error || 'Failed' };
  }
};

const UploadQueuePanel = ({ items, onClear }) => {
  if (!items.length) return null;
  return (
    <div
      style={{
        marginBottom: 'var(--spacing-4)', background: 'var(--bg-surface)',
        border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-card)', overflow: 'hidden',
      }}
    >
      <div
        style={{
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          padding: '8px 14px', borderBottom: '1px solid var(--border-subtle)',
          fontSize: 12, color: 'var(--text-muted)',
        }}
      >
        <span>{items.length} file{items.length !== 1 ? 's' : ''}</span>
        <button
          type="button"
          onClick={onClear}
          disabled={items.every((i) => ACTIVE.includes(i.status))}
          className="btn btn-ghost btn-sm"
        >
          Clear finished
        </button>
      </div>
      <div style={{ maxHeight: 240, overflowY: 'auto' }}>
        {items.map((item) => {
          const view = statusView(item);
          return (
            <div
              key={item.id}
              style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '7px 14px', fontSize: 12, borderTop: '1px solid var(--border-subtle)' }}
            >
              <span style={{ flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: 'var(--text-primary)' }}>
                {item.name}
              </span>
              <span style={{ color: 'var(--text-muted)', flexShrink: 0 }}>{formatSize(item.size)}</span>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, color: view.color, flexShrink: 0, maxWidth: '45%', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {view.icon}{view.text}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default UploadQueuePanel;
