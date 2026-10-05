import { Loader2, Check, X } from 'lucide-react';

const formatSize = (bytes) => {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
};

const ACTIVE = ['queued', 'uploading', 'processing'];

const statusView = (item) => {
  switch (item.status) {
    case 'queued':     return { color: 'var(--gray-500)', icon: null, text: 'Queued' };
    case 'uploading':  return { color: 'var(--gray-600)', icon: <Loader2 size={12} style={{ animation: 'spin 1s linear infinite' }} />, text: `Uploading ${item.progress}%` };
    case 'processing': return { color: '#633806', icon: <Loader2 size={12} style={{ animation: 'spin 1s linear infinite' }} />, text: 'Indexing…' };
    case 'completed':  return { color: '#27500A', icon: <Check size={12} />, text: `Indexed · ${item.chunks ?? 0} chunks` };
    default:           return { color: '#791F1F', icon: <X size={12} />, text: item.error || 'Failed' };
  }
};

const UploadQueuePanel = ({ items, onClear }) => {
  if (!items.length) return null;
  return (
    <div style={{
      marginBottom: 'var(--spacing-4)',
      background: 'var(--bg-card)',
      border: '1px solid var(--gray-200)',
      borderRadius: 'var(--radius-lg)',
      overflow: 'hidden',
    }}>
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        padding: '8px 14px', borderBottom: '1px solid var(--gray-100)',
        fontSize: '12px', color: 'var(--gray-500)',
      }}>
        <span>{items.length} file{items.length !== 1 ? 's' : ''}</span>
        <button
          onClick={onClear}
          disabled={items.every((i) => ACTIVE.includes(i.status))}
          style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '12px', color: 'var(--gray-600)' }}
        >
          Clear finished
        </button>
      </div>
      <div style={{ maxHeight: '240px', overflowY: 'auto' }}>
        {items.map((item) => {
          const view = statusView(item);
          return (
            <div key={item.id} style={{
              display: 'flex', alignItems: 'center', gap: '10px',
              padding: '7px 14px', fontSize: '12px',
              borderTop: '1px solid var(--gray-100)',
            }}>
              <span style={{ flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: 'var(--gray-800)' }}>
                {item.name}
              </span>
              <span style={{ color: 'var(--gray-400)', flexShrink: 0 }}>{formatSize(item.size)}</span>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', color: view.color, flexShrink: 0, maxWidth: '45%', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
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