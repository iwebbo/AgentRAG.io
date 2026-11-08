import { renderAgentOutput } from '../agents/registry';

// Réducteur des événements SSE d'un run de workflow (même vocabulaire que useAgentRuns, enrichi de node_id).
//
//   init                       -> log global
//   log | progress  (+node_id) -> node en cours + ligne de log du node ; sans node_id : log global
//   node_status     (+node_id, data.status)  -> statut explicite (optionnel côté backend)
//   result          (+node_id) -> node terminé, sortie rendue par le registre (type.formatResult)
//   error           (+node_id) -> node en échec ; sans node_id : le workflow échoue
//   done                       -> fin du workflow (failed si un node a échoué)
const stamp = () => new Date().toLocaleTimeString();

export const finalizeRun = (run) => {
  if (run.status !== 'running') return run;
  const anyFailed = Object.values(run.nodes).some(n => n.status === 'failed');
  return { ...run, status: anyFailed ? 'failed' : 'done' };
};

export const reduceRunEvent = (prev, type, data, agentTypeOf) => {
  const nodeId = data?.node_id || null;
  const msg = data?.data?.message || data?.message || data?.data?.step || '';
  const nodes = { ...prev.nodes };
  const patch = (id, fn) => {
    const cur = nodes[id] || { status: 'idle', logs: [], output: '', error: null };
    nodes[id] = { ...cur, ...fn(cur) };
  };
  let next = { ...prev, nodes };

  switch (type) {
    case 'init':
      next.logs = [...prev.logs, { ts: stamp(), message: '🚀 Workflow started' }];
      next.runId = data?.run_id || null;
      break;
    case 'log':
    case 'progress':
      if (nodeId) {
        patch(nodeId, c => ({
          status: c.status === 'idle' ? 'running' : c.status,
          logs: msg ? [...c.logs, { ts: stamp(), message: msg }] : c.logs,
        }));
      } else if (msg) {
        next.logs = [...prev.logs, { ts: stamp(), message: msg }];
      }
      break;
    case 'node_status':
      if (nodeId && data.status) patch(nodeId, () => ({ status: data.status }));
      break;
    case 'result':
      if (nodeId) patch(nodeId, () => ({ status: 'done', output: renderAgentOutput(agentTypeOf(nodeId), data) }));
      break;
    case 'error':
      if (nodeId) {
        patch(nodeId, () => ({ status: 'failed', error: data.error || 'Node execution failed' }));
      } else {
        next = { ...next, status: 'failed', error: data.error || 'Workflow execution failed' };
      }
      break;
    case 'done':
      next = finalizeRun(next);
      break;
    default:
      break;
  }
  return next;
};

// Run persisté (GET /api/workflows/runs/{id}) -> même forme que l'état construit par reduceRunEvent.
// Le backend ne stocke ni les logs ni la définition : logs vides, affichage sur le graphe courant.
const RUN_STATUS = { success: 'done', failed: 'failed', cancelled: 'stopped', running: 'stopped' };

export const hydrateRun = (persisted, agentTypeOf) => {
  const nodes = {};
  Object.entries(persisted.node_results || {}).forEach(([nodeId, r]) => {
    const status = r.status === 'done' || r.status === 'failed' ? r.status : 'idle';
    let output = '';
    if (r.output && r.output.truncated) output = 'Output too large to store';
    else if (r.output !== null && r.output !== undefined) {
      output = renderAgentOutput(agentTypeOf(nodeId), { type: 'result', data: r.output });
    }
    nodes[nodeId] = { status, logs: [], output, error: r.error || null };
  });
  return {
    status: RUN_STATUS[persisted.status] || 'stopped',
    error: persisted.error || null,
    logs: [],
    nodes,
    runId: persisted.id,
  };
};
