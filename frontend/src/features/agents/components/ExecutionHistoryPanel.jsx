import { useState, useEffect } from 'react';
import { Loader2, History, ExternalLink } from 'lucide-react';
import Alert from '../../../components/common/Alert';
import api from '../../../services/api';

// ─────────────────────────────────────────────────────────────────────────────
// EXECUTION HISTORY PANEL — slide-in depuis la liste agents
// ─────────────────────────────────────────────────────────────────────────────
const ExecutionHistoryPanel = ({ agent, agentType, onClose, onReopenExec }) => {
  const [executions, setExecutions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!agent) return;
    (async () => {
      try {
        setLoading(true);
        const res = await api.get(`/api/agents/${agent.id}/executions?limit=50`);
        setExecutions(res.data);
      } catch (e) {
        setError(e.response?.data?.detail || 'Failed to load executions');
      } finally {
        setLoading(false);
      }
    })();
  }, [agent?.id]);

  const fmtDuration = (ms) => {
    if (!ms) return '—';
    if (ms < 1000) return `${ms}ms`;
    const s = Math.round(ms / 1000);
    return s >= 60 ? `${Math.floor(s / 60)}m ${s % 60}s` : `${s}s`;
  };

  const fmtDate = (iso) => {
    if (!iso) return '—';
    const d = new Date(iso);
    const now = new Date();
    const diff = now - d;
    if (diff < 86400000) return `Today ${d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
    if (diff < 172800000) return `Yesterday ${d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
    return d.toLocaleDateString();
  };

  const statusStyle = (s) => ({
    success: { bg: 'rgba(29,158,117,.15)', color: 'var(--success-fg)', dot: 'var(--status-success)' },
    failed:  { bg: 'rgba(226,75,74,.12)',  color: 'var(--danger-fg)', dot: 'var(--status-error)' },
    running: { bg: 'rgba(96,165,250,.15)', color: 'var(--info-fg)', dot: 'var(--status-info)' },
    pending: { bg: 'rgba(136,135,128,.15)', color: 'var(--neutral-fg)', dot: 'var(--text-muted)' },
  }[s] || { bg: 'rgba(136,135,128,.15)', color: 'var(--neutral-fg)', dot: 'var(--text-muted)' });

  const getPromptLabel = (exec) => {
    const d = exec.input_data || {};
    return d.prompt || d.query || d.branch || d.project_key || d.version || d.url || d.instruction || d.mode || `#${exec.id?.slice(0, 8)}`;
  };

  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 1050, display: 'flex' }} onClick={onClose}>
      {/* Backdrop */}
      <div style={{ flex: 1 }} />
      {/* Panel */}
      <div
        onClick={e => e.stopPropagation()}
        style={{ width: '420px', background: 'var(--bg-card)', borderLeft: '1px solid var(--gray-200)', display: 'flex', flexDirection: 'column', height: '100%', boxShadow: '-4px 0 24px rgba(0,0,0,0.12)' }}
      >
        {/* Header */}
        <div style={{ padding: 'var(--spacing-4)', borderBottom: '1px solid var(--gray-200)', flexShrink: 0 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <div>
              <div style={{ fontWeight: '600', fontSize: 'var(--text-base)', display: 'flex', alignItems: 'center', gap: 'var(--spacing-2)' }}>
                <History size={16} style={{ color: 'var(--gray-500)' }} />
                Execution history
              </div>
              <div style={{ fontSize: 'var(--text-xs)', color: 'var(--gray-600)', marginTop: '2px' }}>
                {agentType?.icon} {agent?.name} · {executions.length} run{executions.length !== 1 ? 's' : ''}
              </div>
            </div>
            <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--gray-500)', fontSize: '1.1rem', lineHeight: 1 }}>✕</button>
          </div>
        </div>

        {/* Body */}
        <div style={{ flex: 1, overflowY: 'auto' }}>
          {loading && (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 'var(--spacing-10)', gap: 'var(--spacing-2)', color: 'var(--gray-500)' }}>
              <Loader2 size={16} className="animate-spin" /> Loading…
            </div>
          )}
          {error && (
            <div style={{ padding: 'var(--spacing-4)' }}>
              <Alert type="error">{error}</Alert>
            </div>
          )}
          {!loading && !error && executions.length === 0 && (
            <div style={{ textAlign: 'center', padding: 'var(--spacing-10)', color: 'var(--gray-500)', fontSize: 'var(--text-sm)' }}>
              No executions yet
            </div>
          )}
          {!loading && executions.map((exec, i) => {
            const st = statusStyle(exec.status);
            const out = exec.output_data;
            const convId = exec.input_data?.conversation_id
              || (typeof out === 'object' && out !== null && (out.conversation_id || out.data?.conversation_id))
              || null;
            return (
              <div key={exec.id} style={{ padding: '10px 16px', borderBottom: '1px solid var(--gray-200)', display: 'grid', gridTemplateColumns: '8px 1fr auto auto', gap: '10px', alignItems: 'center' }}>
                <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: st.dot, display: 'inline-block', flexShrink: 0 }} />
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontSize: 'var(--text-sm)', fontWeight: '500', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {getPromptLabel(exec)}
                  </div>
                  <div style={{ fontSize: '11px', color: 'var(--gray-600)', marginTop: '2px' }}>
                    {fmtDate(exec.started_at)}
                    {exec.execution_time_ms ? ` · ${fmtDuration(exec.execution_time_ms)}` : ''}
                    {exec.tokens_used ? ` · ${exec.tokens_used.toLocaleString()} tokens` : ''}
                  </div>
                </div>
                <span style={{ fontSize: '10px', fontWeight: '600', padding: '2px 8px', borderRadius: '99px', background: st.bg, color: st.color, flexShrink: 0 }}>
                  {exec.status}
                </span>
                <button
                  title={convId ? 'Open in execution panel' : 'No conversation linked'}
                  disabled={!convId}
                  onClick={() => convId && onReopenExec(exec)}
                  style={{ background: 'none', border: 'none', cursor: convId ? 'pointer' : 'not-allowed', color: 'var(--gray-500)', opacity: convId ? 1 : 0.3, display: 'flex', alignItems: 'center', padding: '4px' }}
                >
                  <ExternalLink size={14} />
                </button>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

export default ExecutionHistoryPanel;
