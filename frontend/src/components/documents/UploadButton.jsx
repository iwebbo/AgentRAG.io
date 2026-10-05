import { useEffect } from 'react';
import { Upload, Loader2 } from 'lucide-react';
import { useUploadQueue } from '../../hooks/useUploadQueue';
import { ACCEPT } from '../../services/documentUpload';

const UploadButton = ({ projectId, onMessage, onSettled }) => {
  const { items, enqueue, clear, busy } = useUploadQueue(projectId, { onSettled });

  useEffect(() => {
    if (!items.length || busy) return;
    const failed = items.filter((i) => i.status === 'failed');
    const done = items.length - failed.length;
    if (failed.length) {
      onMessage('error', `${done}/${items.length} indexed — ${failed[0].name}: ${failed[0].error}`);
    } else {
      onMessage('success', `${done} document${done !== 1 ? 's' : ''} indexed`);
    }
    clear();
  }, [items, busy]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleChange = (e) => {
    const files = Array.from(e.target.files);
    e.target.value = '';
    enqueue(files);
  };

  const active = items.filter((i) => ['queued', 'uploading', 'processing'].includes(i.status)).length;

  return (
    <label
      style={{
        flex: 1,
        display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
        gap: '5px', height: '32px',
        borderRadius: 'var(--radius)',
        border: '1px solid var(--gray-200)',
        background: 'transparent',
        color: busy ? 'var(--primary)' : 'var(--gray-600)',
        fontSize: '12px', fontWeight: '500',
        cursor: 'pointer', transition: 'all 0.12s',
      }}
      onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--gray-50)'; }}
      onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; }}
    >
      {busy
        ? <><Loader2 size={13} className="animate-spin" /> {active} in progress</>
        : <><Upload size={13} /> Upload</>
      }
      <input type="file" multiple hidden accept={ACCEPT} onChange={handleChange} />
    </label>
  );
};

export default UploadButton;