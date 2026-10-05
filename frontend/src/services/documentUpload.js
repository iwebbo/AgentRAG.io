import api from './api';

export const ACCEPT = '.pdf,.docx,.doc,.pptx,.ppt,.txt,.md,.markdown,.html,.htm,.xlsx,.xls,.csv,.rtf,.odt,.ods,.odp,.tex,.epub,.xml,.py,.js,.jsx,.ts,.tsx,.css,.java,.cpp,.c,.cs,.go,.rs,.php,.rb,.swift,.kt,.scala,.r,.groovy,.sh,.bash,.sql,.json,.yaml,.yml,.toml,.ini,.env,.jenkinsfile,.zip,.tar,.gz';

export const MAX_FILE_SIZE = 100 * 1024 * 1024;
export const UPLOAD_CONCURRENCY = 3;

const EXTENSIONS = new Set(ACCEPT.split(','));
const POLL_INTERVAL_MS = 3000;
const MAX_POLL_FAILURES = 5;

export const validateFile = (file) => {
  const dot = file.name.lastIndexOf('.');
  const ext = dot >= 0 ? file.name.slice(dot).toLowerCase() : '';
  if (ext && !EXTENSIONS.has(ext)) return 'Unsupported format';
  if (file.size === 0) return 'Empty file';
  if (file.size > MAX_FILE_SIZE) return `File too large (max ${MAX_FILE_SIZE / 1024 / 1024} MB)`;
  return null;
};

export const uploadFile = (projectId, file, onProgress) => {
  const fd = new FormData();
  fd.append('file', file);
  return api.post(`/api/documents/${projectId}/upload`, fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (e) => {
      if (e.total) onProgress(Math.round((e.loaded / e.total) * 100));
    },
  });
};

/**
 * Polls the project document list once per tick for all tracked document ids.
 * onUpdate receives the batch of documents that reached a terminal status.
 */
export const createStatusWatcher = (projectId, onUpdate) => {
  const pending = new Set();
  let timer = null;
  let failures = 0;
  let stopped = false;

  const schedule = () => {
    if (!stopped && !timer && pending.size) timer = setTimeout(tick, POLL_INTERVAL_MS);
  };

  async function tick() {
    timer = null;
    const settled = [];
    try {
      const { data } = await api.get(`/api/documents/${projectId}/documents`);
      failures = 0;
      const byId = new Map(data.map((d) => [d.id, d]));
      for (const id of [...pending]) {
        const doc = byId.get(id);
        if (!doc) {
          pending.delete(id);
        } else if (doc.status === 'completed' || doc.status === 'failed') {
          pending.delete(id);
          settled.push(doc);
        }
      }
    } catch {
      if (++failures >= MAX_POLL_FAILURES) {
        pending.forEach((id) => settled.push({ id, status: 'failed', error_message: 'Status unavailable' }));
        pending.clear();
      }
    }
    if (settled.length && !stopped) onUpdate(settled);
    schedule();
  }

  return {
    add: (id) => {
      pending.add(id);
      schedule();
    },
    stop: () => {
      stopped = true;
      clearTimeout(timer);
    },
  };
};