import { useState, useEffect, useRef } from 'react';
import { renderAgentOutput } from '../registry';
import { getExecConversationId, getRunLabel } from '../utils/runUtils';

// ─────────────────────────────────────────────────────────────────────────────
// AGENT RUNS — exécutions en arrière-plan : état + flux SSE de N exécutions simultanées.
// Affichage : components/AgentRunDock (drawer + pastilles) / AgentRunDrawer.
// ─────────────────────────────────────────────────────────────────────────────
let runSeq = 0;
const nextRunId = () => `run-${Date.now()}-${++runSeq}`;

export const useAgentRuns = ({ onExecuted } = {}) => {
  const [runs, setRuns] = useState([]);
  const [activeRunId, setActiveRunId] = useState(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [rerun, setRerun] = useState(null); // { agentId, values } — préremplissage de "Run again"
  const readersRef = useRef({});
  const onExecutedRef = useRef(onExecuted);

  useEffect(() => { onExecutedRef.current = onExecuted; });

  // Démontage de la page : on coupe les flux ouverts (comportement identique à l'ancienne modal)
  useEffect(() => () => {
    Object.values(readersRef.current).forEach(r => { r.cancel().catch(() => {}); });
    readersRef.current = {};
  }, []);

  const patchRun = (id, patch) => setRuns(prev => prev.map(r => (
    r.id === id ? { ...r, ...(typeof patch === 'function' ? patch(r) : patch) } : r
  )));

  const addStep = (id, type, message) => patchRun(id, r => ({
    steps: [...r.steps, { type, message, ts: new Date().toLocaleTimeString() }],
  }));

  const streamRun = async (id, agent, inputData) => {
    const token = localStorage.getItem('access_token');
    try {
      const response = await fetch(`/api/agents/${agent.id}/execute/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {})
        },
        body: JSON.stringify({ input_data: inputData, trigger: 'manual' })
      });

      if (!response.ok) {
        const e = await response.json().catch(() => ({}));
        throw new Error(e.detail || `HTTP ${response.status}`);
      }

      const reader = response.body.getReader();
      readersRef.current[id] = reader;
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const blocks = buffer.split('\n\n');
        buffer = blocks.pop() ?? '';

        for (const block of blocks) {
          if (!block.trim()) continue;
          let eventType = '', dataStr = '';
          for (const line of block.split('\n')) {
            if (line.startsWith('event: ')) eventType = line.slice(7).trim();
            else if (line.startsWith('data: ')) dataStr = line.slice(6).trim();
          }
          if (!dataStr) continue;
          try {
            const data = JSON.parse(dataStr);
            if (eventType === 'init') {
              patchRun(id, { conversationId: data.conversation_id || null });
              addStep(id, 'init', '🚀 Execution started');
            } else if (eventType === 'log' || eventType === 'progress') {
              const msg = data.data?.message || data.message || data.data?.step || '';
              if (msg) addStep(id, eventType, msg);
            } else if (eventType === 'result') {
              const c = renderAgentOutput(agent.agent_type, data);
              if (c) patchRun(id, r => ({ outputText: r.outputText + (r.outputText ? '\n\n' : '') + c }));
              addStep(id, 'result', '✅ Result received');
            } else if (eventType === 'done') {
              const c = renderAgentOutput(agent.agent_type, data.output);
              patchRun(id, r => ({
                conversationId: r.conversationId || data.conversation_id || null,
                outputText: r.outputText || c || '',
                status: 'done',
                finishedAt: Date.now(),
              }));
              if (onExecutedRef.current) onExecutedRef.current();
            } else if (eventType === 'error') {
              throw new Error(data.error || 'Agent execution failed');
            }
          } catch (pe) {
            if (!pe.message?.includes('JSON')) throw pe;
          }
        }
      }
      patchRun(id, r => (r.status === 'running' ? { status: 'done', finishedAt: Date.now() } : {}));
    } catch (err) {
      patchRun(id, r => (r.status === 'done' ? {} : {
        error: err.message || 'Execution failed',
        status: 'failed',
        finishedAt: Date.now(),
      }));
    } finally {
      delete readersRef.current[id];
    }
  };

  const selectRun = (id) => { setActiveRunId(id); setDrawerOpen(true); };

  const startRun = (agent, inputData, formValues) => {
    const id = nextRunId();
    const run = {
      id, execId: null, agent, agentId: agent.id, status: 'running',
      outputText: '', steps: [], conversationId: null, error: null,
      startedAt: Date.now(), finishedAt: null, durationMs: null,
      formValues, label: getRunLabel(inputData),
    };
    setRuns(prev => [...prev, run]);
    selectRun(id);
    streamRun(id, agent, inputData);
  };

  // Ouvre une exécution passée (historique) dans le drawer, sans écraser un run en cours
  const openFromExecution = (agent, exec) => {
    const existing = runs.find(r => r.execId && r.execId === exec.id);
    if (existing) { selectRun(existing.id); return; }
    const out = exec.output_data;
    const text = (out && typeof out === 'object')
      ? renderAgentOutput(agent.agent_type, out)
      : (typeof out === 'string' ? out : '');
    const startedAt = exec.started_at ? new Date(exec.started_at).getTime() : Date.now();
    const errMsg = exec.error_message || exec.error;
    const id = nextRunId();
    const run = {
      id, execId: exec.id, agent, agentId: agent.id,
      status: exec.status === 'failed' ? 'failed' : 'done',
      outputText: text, steps: [], conversationId: getExecConversationId(exec),
      error: exec.status === 'failed' && typeof errMsg === 'string' ? errMsg : null,
      startedAt, finishedAt: startedAt, durationMs: exec.execution_time_ms || null,
      formValues: undefined, label: getRunLabel(exec.input_data),
    };
    setRuns(prev => [...prev, run]);
    selectRun(id);
  };

  const dismissRun = (id) => {
    const target = runs.find(r => r.id === id);
    if (!target || target.status === 'running') return;
    const remaining = runs.filter(r => r.id !== id);
    setRuns(remaining);
    if (activeRunId === id) {
      if (remaining.length) setActiveRunId(remaining[remaining.length - 1].id);
      else { setActiveRunId(null); setDrawerOpen(false); }
    }
  };

  return { runs, activeRunId, drawerOpen, setDrawerOpen, startRun, openFromExecution, selectRun, dismissRun, rerun, setRerun };
};
