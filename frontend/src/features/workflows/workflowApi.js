import api from '../../services/api';

// ─────────────────────────────────────────────────────────────────────────────
// Accès backend workflows — SEUL fichier à adapter si les endpoints diffèrent.
//
//   GET    /api/workflows/                     -> [{ id, name, description, updated_at, ... }]
//   GET    /api/workflows/{id}                 -> { id, name, description, definition, ... }
//   POST   /api/workflows/                     { name, description, definition } -> { id, ... }
//   PUT    /api/workflows/{id}                 { name, description, definition } -> { id, ... }
//   DELETE /api/workflows/{id}
//   POST   /api/workflows/{id}/execute/stream  { input_data, trigger: 'manual' }  (SSE)
//   GET    /api/workflows/{id}/runs            -> [{ id, status, trigger, started_at, completed_at }]
//   GET    /api/workflows/runs/{run_id}        -> { ..., input_data, node_results, error }
//
// `definition` = JSON versionné produit par serialize.toWorkflowJson.
// ─────────────────────────────────────────────────────────────────────────────

const BASE = '/api/workflows';

export const errMsg = (e, fallback) => {
  const detail = e?.response?.data?.detail;
  if (Array.isArray(detail)) return detail.map(d => d.msg).join(' · ');
  return detail || e?.message || fallback;
};

export const listWorkflows = () => api.get(`${BASE}/`).then(r => r.data);
export const getWorkflow = (id) => api.get(`${BASE}/${id}`).then(r => r.data);
export const createWorkflow = (payload) => api.post(`${BASE}/`, payload).then(r => r.data);
export const updateWorkflow = (id, payload) => api.put(`${BASE}/${id}`, payload).then(r => r.data);
export const deleteWorkflow = (id) => api.delete(`${BASE}/${id}`).then(r => r.data);

// Historique des exécutions (persisté côté backend)
export const listWorkflowRuns = (id, limit = 50) => api.get(`${BASE}/${id}/runs`, { params: { limit } }).then(r => r.data);
export const getWorkflowRun = (runId) => api.get(`${BASE}/runs/${runId}`).then(r => r.data);

// Exécution + flux SSE. Même format d'événements que /api/agents/{id}/execute/stream
// (init | log | progress | result | done | error), enrichis de `node_id` pour les événements propres à un node.
// onEvent(eventType, data). Rejette en cas d'erreur HTTP ; AbortError si `signal` est annulé.
export const streamWorkflowRun = async (id, inputData, onEvent, signal) => {
  const token = localStorage.getItem('access_token');
  const response = await fetch(`${BASE}/${id}/execute/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ input_data: inputData, trigger: 'manual' }),
    signal,
  });

  if (!response.ok) {
    const e = await response.json().catch(() => ({}));
    throw new Error(typeof e.detail === 'string' ? e.detail : `HTTP ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const blocks = buffer.split('\n\n');
      buffer = blocks.pop() ?? '';
      for (const block of blocks) {
        if (!block.trim()) continue;
        let eventType = '';
        let dataStr = '';
        for (const line of block.split('\n')) {
          if (line.startsWith('event: ')) eventType = line.slice(7).trim();
          else if (line.startsWith('data: ')) dataStr = line.slice(6).trim();
        }
        if (!dataStr) continue;
        let data;
        try { data = JSON.parse(dataStr); } catch { continue; }
        onEvent(eventType, data);
      }
    }
  } finally {
    reader.cancel().catch(() => {});
  }
};
