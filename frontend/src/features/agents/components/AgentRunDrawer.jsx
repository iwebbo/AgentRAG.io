import { useState, useEffect, useRef } from 'react';
import { Loader2, Copy, Check, ExternalLink, History } from 'lucide-react';
import Button from '../../../components/common/Button';
import Alert from '../../../components/common/Alert';
import api from '../../../services/api';
import { AGENT_TYPES } from '../registry';
import {
  RUN_STEP_COLOR, RUN_STATUS_META, buildChatUrl, getExecConversationId, fmtElapsed, runIconBtn,
} from '../utils/runUtils';

// ─────────────────────────────────────────────────────────────────────────────
// RUN DRAWER — panneau latéral droit, non bloquant (la liste d'agents reste utilisable)
// ─────────────────────────────────────────────────────────────────────────────
const AgentRunDrawer = ({ run, runs, onSelect, onMinimize, onDismiss, onRunAgain, onOpenExecution }) => {
  const [tab, setTab] = useState('output'); // output | logs | history
  const [executions, setExecutions] = useState([]);
  const [execLoading, setExecLoading] = useState(false);
  const [copied, setCopied] = useState(false);
  const [, setTick] = useState(0);
  const outputRef = useRef(null);

  const agentType = AGENT_TYPES[run.agent.agent_type];
  const meta = RUN_STATUS_META[run.status] || RUN_STATUS_META.running;
  const isRunning = run.status === 'running';
  const chatUrl = buildChatUrl(run.conversationId);
  const elapsed = run.durationMs ?? ((run.finishedAt || Date.now()) - run.startedAt);

  // chrono live tant que l'exécution tourne
  useEffect(() => {
    if (!isRunning) return undefined;
    const i = setInterval(() => setTick(n => n + 1), 1000);
    return () => clearInterval(i);
  }, [isRunning]);

  useEffect(() => {
    if (tab === 'output' && outputRef.current) outputRef.current.scrollTop = outputRef.current.scrollHeight;
  }, [run.outputText, tab]);

  useEffect(() => {
    if (tab !== 'history') return undefined;
    let cancelled = false;
    (async () => {
      setExecLoading(true);
      try {
        const res = await api.get(`/api/agents/${run.agentId}/executions?limit=30`);
        if (!cancelled) setExecutions(res.data);
      } catch (_) { /* silencieux comme l'ancien onglet History */ }
      finally { if (!cancelled) setExecLoading(false); }
    })();
    return () => { cancelled = true; };
  }, [tab, run.agentId, run.status]);

  const handleCopy = async () => {
    if (!chatUrl) return;
    await navigator.clipboard.writeText(chatUrl).catch(() => {});
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const TABS = [
    { key: 'output', label: 'Output' },
    { key: 'logs', label: `Logs${run.steps.length ? ` (${run.steps.length})` : ''}` },
    { key: 'history', label: 'History' },
  ];

  const stMap = {
    success: { bg: 'rgba(29,158,117,.15)', color: 'var(--success-fg)', dot: 'var(--status-success)' },
    failed: { bg: 'rgba(226,75,74,.12)', color: 'var(--danger-fg)', dot: 'var(--status-error)' },
    running: { bg: 'rgba(96,165,250,.15)', color: 'var(--info-fg)', dot: 'var(--status-info)' },
  };

  return (
    <div style={{ position: 'fixed', top: 0, right: 0, bottom: 0, width: 'min(560px, 100vw)', zIndex: 900, background: 'var(--bg-card)', borderLeft: '1px solid var(--gray-200)', boxShadow: '-4px 0 24px rgba(0,0,0,0.25)', display: 'flex', flexDirection: 'column' }}>

      {/* Header */}
      <div style={{ padding: 'var(--spacing-3) var(--spacing-4)', borderBottom: '1px solid var(--gray-200)', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 'var(--spacing-3)', flexShrink: 0 }}>
        <div style={{ minWidth: 0 }}>
          <div style={{ fontWeight: '600', fontSize: 'var(--text-base)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {agentType?.icon} {run.agent.name}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: 'var(--text-xs)', marginTop: '3px', minWidth: 0 }}>
            <span style={{ width: '7px', height: '7px', borderRadius: '50%', background: meta.dot, display: 'inline-block', flexShrink: 0, animation: isRunning ? 'pulse 1s infinite' : 'none' }} />
            <span style={{ color: meta.color, fontWeight: isRunning ? '400' : '600' }}>{meta.label}</span>
            <span style={{ color: 'var(--gray-500)' }}>· {fmtElapsed(elapsed)}</span>
            {run.label && (
              <span style={{ color: 'var(--gray-500)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>· {run.label}</span>
            )}
          </div>
        </div>
        <div style={{ display: 'flex', gap: '6px', flexShrink: 0 }}>
          <button title="Minimize (the run keeps going)" onClick={onMinimize} style={runIconBtn(false)}>—</button>
          <button title={isRunning ? 'Cannot close while running — minimize instead' : 'Close and remove from the list'} disabled={isRunning} onClick={() => onDismiss(run.id)} style={runIconBtn(isRunning)}>✕</button>
        </div>
      </div>

      {/* Sélecteur d'exécutions (si plusieurs runs) */}
      {runs.length > 1 && (
        <div style={{ display: 'flex', gap: '6px', padding: '8px var(--spacing-3)', borderBottom: '1px solid var(--gray-200)', overflowX: 'auto', flexShrink: 0 }}>
          {runs.map(r => {
            const m = RUN_STATUS_META[r.status] || RUN_STATUS_META.running;
            const active = r.id === run.id;
            return (
              <button key={r.id} onClick={() => onSelect(r.id)} title={r.label || r.agent.name} style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', padding: '4px 10px', borderRadius: '99px', border: active ? '1px solid var(--primary)' : '1px solid var(--gray-300)', background: active ? 'rgba(96,165,250,.12)' : 'var(--gray-100)', color: active ? 'var(--text-primary)' : 'var(--gray-600)', fontSize: '11px', cursor: 'pointer', whiteSpace: 'nowrap', flexShrink: 0 }}>
                <span style={{ width: '7px', height: '7px', borderRadius: '50%', background: m.dot, display: 'inline-block', animation: r.status === 'running' ? 'pulse 1s infinite' : 'none' }} />
                {r.agent.name}
              </button>
            );
          })}
        </div>
      )}

      {run.error && (
        <div style={{ padding: 'var(--spacing-3) var(--spacing-4) 0', flexShrink: 0 }}>
          <Alert type="error">{run.error}</Alert>
        </div>
      )}

      {/* Onglets */}
      <div style={{ display: 'flex', background: 'var(--bg-surface-hover)', borderBottom: '1px solid var(--border-subtle)', flexShrink: 0, marginTop: run.error ? 'var(--spacing-3)' : 0 }}>
        {TABS.map(tb => (
          <button key={tb.key} onClick={() => setTab(tb.key)} style={{
            padding: '8px 16px', background: 'none', border: 'none',
            borderBottom: tab === tb.key ? '2px solid var(--info)' : '2px solid transparent',
            color: tab === tb.key ? 'var(--text-primary)' : 'var(--text-muted)',
            fontSize: '12px', cursor: 'pointer', fontWeight: tab === tb.key ? '600' : '400',
            display: 'flex', alignItems: 'center'
          }}>
            {tb.key === 'history' && <History size={12} style={{ marginRight: '5px' }} />}
            {tb.label}
          </button>
        ))}
      </div>

      {/* Contenu */}
      {tab === 'output' && (
        <div ref={outputRef} style={{ flex: 1, overflowY: 'auto', padding: 'var(--spacing-3)', fontFamily: 'monospace', fontSize: '13px', lineHeight: '1.7', whiteSpace: 'pre-wrap', wordBreak: 'break-word', background: 'var(--bg-main)', color: 'var(--text-primary)' }}>
          {run.outputText || <span style={{ color: 'var(--text-muted)' }}>{isRunning ? 'Waiting for output…' : 'No output captured.'}</span>}
          {isRunning && <span style={{ color: 'var(--info)', animation: 'pulse 1s infinite' }}>▋</span>}
        </div>
      )}

      {tab === 'logs' && (
        <div style={{ flex: 1, overflowY: 'auto', padding: 'var(--spacing-3)', background: 'var(--bg-main)' }}>
          {run.steps.length === 0 && (
            <div style={{ color: 'var(--text-muted)', fontSize: 'var(--text-sm)' }}>
              {isRunning ? 'Waiting for logs…' : 'No logs captured for this run.'}
            </div>
          )}
          {run.steps.map((s, i) => (
            <div key={i} style={{ display: 'flex', gap: '8px', fontSize: '12px', padding: '2px 0' }}>
              <span style={{ color: 'var(--gray-400)', flexShrink: 0, fontFamily: 'monospace', fontSize: '11px' }}>{s.ts}</span>
              <span style={{ color: RUN_STEP_COLOR[s.type] || 'var(--gray-600)', wordBreak: 'break-word' }}>{s.message}</span>
            </div>
          ))}
        </div>
      )}

      {tab === 'history' && (
        <div style={{ flex: 1, overflowY: 'auto', background: 'var(--bg-card)' }}>
          {execLoading && (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 'var(--spacing-8)', gap: 'var(--spacing-2)', color: 'var(--gray-500)' }}>
              <Loader2 size={15} className="animate-spin" /> Loading…
            </div>
          )}
          {!execLoading && executions.length === 0 && (
            <div style={{ textAlign: 'center', padding: 'var(--spacing-8)', color: 'var(--gray-500)', fontSize: 'var(--text-sm)' }}>No executions yet</div>
          )}
          {!execLoading && executions.map((exec) => {
            const st = stMap[exec.status] || { bg: 'rgba(136,135,128,.15)', color: 'var(--neutral-fg)', dot: 'var(--text-muted)' };
            const convId = getExecConversationId(exec);
            const label = exec.input_data?.prompt || exec.input_data?.query || exec.input_data?.branch || exec.input_data?.project_key || exec.input_data?.version || exec.input_data?.mode || `#${exec.id?.slice(0, 8)}`;
            const dur = exec.execution_time_ms ? (exec.execution_time_ms < 60000 ? `${Math.round(exec.execution_time_ms / 1000)}s` : `${Math.floor(exec.execution_time_ms / 60000)}m ${Math.round((exec.execution_time_ms % 60000) / 1000)}s`) : '';
            const dt = exec.started_at ? new Date(exec.started_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '';
            return (
              <div key={exec.id} style={{ padding: '9px 14px', borderBottom: '1px solid var(--gray-200)', display: 'grid', gridTemplateColumns: '8px 1fr auto auto', gap: '9px', alignItems: 'center', background: exec.id === run.execId ? 'rgba(96,165,250,.08)' : 'transparent' }}>
                <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: st.dot, display: 'inline-block', flexShrink: 0 }} />
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontSize: '12px', fontWeight: '500', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', color: 'var(--gray-900)' }}>{label}</div>
                  <div style={{ fontSize: '11px', color: 'var(--gray-500)', marginTop: '1px' }}>{dt}{dur ? ` · ${dur}` : ''}{exec.tokens_used ? ` · ${exec.tokens_used.toLocaleString()} tok` : ''}</div>
                </div>
                <span style={{ fontSize: '10px', fontWeight: '600', padding: '1px 7px', borderRadius: '99px', background: st.bg, color: st.color, flexShrink: 0 }}>{exec.status}</span>
                <button
                  title={convId ? 'Load this run' : 'No conversation'}
                  disabled={!convId}
                  onClick={() => convId && onOpenExecution(run.agent, exec)}
                  style={{ background: 'none', border: 'none', cursor: convId ? 'pointer' : 'not-allowed', color: 'var(--gray-500)', opacity: convId ? 1 : 0.3, padding: '3px', display: 'flex', alignItems: 'center' }}
                >
                  <ExternalLink size={14} />
                </button>
              </div>
            );
          })}
        </div>
      )}

      {/* Footer : lien chat (nouvel onglet) + actions */}
      <div style={{ padding: 'var(--spacing-3) var(--spacing-4)', borderTop: '1px solid var(--gray-200)', flexShrink: 0, display: 'flex', flexDirection: 'column', gap: 'var(--spacing-2)' }}>
        {chatUrl ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '6px 10px', border: '1px solid var(--gray-200)', borderRadius: 'var(--radius)', background: 'var(--gray-100)', minWidth: 0 }}>
            <span style={{ flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontFamily: 'monospace', fontSize: '11px', color: 'var(--gray-600)', userSelect: 'all' }}>{chatUrl}</span>
            <button title="Copy link" onClick={handleCopy} style={{ ...runIconBtn(false), width: '24px', height: '24px', color: copied ? 'var(--success)' : 'var(--gray-600)' }}>
              {copied ? <Check size={12} /> : <Copy size={12} />}
            </button>
          </div>
        ) : (
          <div style={{ fontSize: '11px', color: 'var(--gray-500)' }}>Chat link available once the run is initialised.</div>
        )}
        <div style={{ display: 'flex', gap: 'var(--spacing-2)', alignItems: 'center', justifyContent: 'flex-end' }}>
          <Button variant="ghost" size="sm" onClick={() => onRunAgain(run)} disabled={isRunning}>Run Again</Button>
          {chatUrl ? (
            <a href={chatUrl} target="_blank" rel="noopener noreferrer" title="Open the agent conversation (logs) in a new tab" style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', padding: '6px 12px', borderRadius: 'var(--radius)', background: 'var(--primary)', color: 'white', fontSize: 'var(--text-sm)', fontWeight: '600', textDecoration: 'none' }}>
              <ExternalLink size={13} /> Open chat
            </a>
          ) : (
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', padding: '6px 12px', borderRadius: 'var(--radius)', background: 'var(--gray-200)', color: 'var(--gray-500)', fontSize: 'var(--text-sm)', fontWeight: '600', opacity: 0.6, cursor: 'not-allowed' }}>
              <ExternalLink size={13} /> Open chat
            </span>
          )}
        </div>
      </div>
    </div>
  );
};

export default AgentRunDrawer;
