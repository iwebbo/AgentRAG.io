import { useState, useEffect, useRef, useCallback } from 'react';
import {
  validateFile, uploadFile, createStatusWatcher, UPLOAD_CONCURRENCY,
} from '../services/documentUpload';

const ACTIVE = ['queued', 'uploading', 'processing'];
let seq = 0;

/**
 * Multi-file upload queue: UPLOAD_CONCURRENCY parallel uploads to the existing
 * single-file endpoint, then one shared status poll for indexing progress.
 * item.status: queued | uploading | processing | completed | failed
 */
export const useUploadQueue = (projectId, { onSettled } = {}) => {
  const [items, setItems] = useState([]);
  const queue = useRef([]);
  const running = useRef(0);
  const watcher = useRef(null);
  const onSettledRef = useRef(onSettled);
  onSettledRef.current = onSettled;

  const patch = useCallback((match, changes) => {
    setItems((prev) => prev.map((i) => (match(i) ? { ...i, ...changes } : i)));
  }, []);

  useEffect(() => {
    watcher.current = createStatusWatcher(projectId, (docs) => {
      const byId = new Map(docs.map((d) => [d.id, d]));
      setItems((prev) => prev.map((i) => {
        const doc = byId.get(i.documentId);
        return doc
          ? { ...i, status: doc.status, chunks: doc.chunk_count, error: doc.error_message }
          : i;
      }));
      onSettledRef.current?.();
    });
    return () => {
      queue.current = [];
      watcher.current.stop();
    };
  }, [projectId]);

  const pump = useCallback(() => {
    while (running.current < UPLOAD_CONCURRENCY && queue.current.length) {
      const entry = queue.current.shift();
      running.current += 1;
      patch((i) => i.id === entry.id, { status: 'uploading' });
      uploadFile(projectId, entry.file, (progress) => patch((i) => i.id === entry.id, { progress }))
        .then((res) => {
          patch((i) => i.id === entry.id, {
            status: 'processing', progress: 100, documentId: res.data.document_id,
          });
          watcher.current.add(res.data.document_id);
        })
        .catch((err) => {
          patch((i) => i.id === entry.id, {
            status: 'failed', error: err.response?.data?.detail || 'Upload failed',
          });
        })
        .finally(() => {
          running.current -= 1;
          pump();
        });
    }
  }, [projectId, patch]);

  const enqueue = useCallback((files) => {
    if (!projectId) return;
    const entries = Array.from(files).map((file) => {
      const error = validateFile(file);
      return {
        id: `${Date.now()}-${seq++}`, file, name: file.name, size: file.size,
        progress: 0, status: error ? 'failed' : 'queued', error,
      };
    });
    if (!entries.length) return;
    setItems((prev) => [...prev, ...entries]);
    queue.current.push(...entries.filter((e) => e.status === 'queued'));
    pump();
  }, [projectId, pump]);

  const clear = useCallback(() => {
    setItems((prev) => prev.filter((i) => ACTIVE.includes(i.status)));
  }, []);

  return { items, enqueue, clear, busy: items.some((i) => ACTIVE.includes(i.status)) };
};