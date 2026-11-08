// Constantes et helpers partagés par useAgentRuns, AgentRunDrawer et AgentRunDock

export const RUN_STEP_COLOR = { init: 'var(--info)', log: 'var(--gray-500)', progress: 'var(--primary)', result: 'var(--success)', error: 'var(--error)' };

export const RUN_STATUS_META = {
  running: { dot: '#f59e0b', label: 'Running…', color: 'var(--text-primary)' },
  done:    { dot: 'var(--success)', label: 'Completed', color: 'var(--success)' },
  failed:  { dot: 'var(--error)', label: 'Failed', color: 'var(--error)' },
};

// Lien direct vers la conversation (logs) de l'agent — ouvert dans un nouvel onglet
export const buildChatUrl = (conversationId) => (conversationId ? `${window.location.origin}/chat/${conversationId}` : null);

export const getExecConversationId = (exec) => {
  const out = exec?.output_data;
  return exec?.input_data?.conversation_id
    || (typeof out === 'object' && out !== null && (out.conversation_id || out.data?.conversation_id))
    || null;
};

export const getRunLabel = (inputData) => {
  const d = inputData || {};
  return String(d.prompt || d.query || d.branch || d.project_key || d.version || d.url || d.instruction || d.mode || '');
};

export const fmtElapsed = (ms) => {
  const s = Math.max(0, Math.round((ms || 0) / 1000));
  return s >= 60 ? `${Math.floor(s / 60)}m ${s % 60}s` : `${s}s`;
};

export const runIconBtn = (disabled) => ({
  width: '28px', height: '28px', borderRadius: 'var(--radius)', border: '1px solid var(--gray-300)',
  background: 'var(--gray-100)', color: 'var(--gray-600)', cursor: disabled ? 'not-allowed' : 'pointer',
  opacity: disabled ? 0.4 : 1, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '13px', padding: 0,
});
