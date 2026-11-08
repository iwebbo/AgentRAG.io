import { AGENT_TYPES, buildExecuteInput, validateExecuteInput } from '../agents/registry';

// ─────────────────────────────────────────────────────────────────────────────
// État React Flow  <->  JSON backend (contrat versionné, voir README.md)
//
//   { version: 1,
//     nodes: [{ id, type: 'agent', agent_id, input, position, ui: { values } }],
//     edges: [{ source, target }] }
//
// `input`     : input_data de l'agent, produit par le registre (type.buildInput) — c'est ce que le backend exécute.
// `ui.values` : valeurs brutes du formulaire, pour ré-ouvrir le workflow sans perte (le backend les conserve tel quel).
// ─────────────────────────────────────────────────────────────────────────────

export const WORKFLOW_SCHEMA_VERSION = 1;

const TEMPLATE_RE = /\{\{[^}]*\}\}/;
const hasTemplate = (v) => typeof v === 'string' && TEMPLATE_RE.test(v);
export const nodeHasTemplate = (values) => Object.values(values || {}).some(hasTemplate);

// Valeurs initiales d'un node : mêmes règles que ExecuteAgentModal (defaultValue + initialExecuteValues du type)
export const defaultValuesFor = (agent) => {
  const type = AGENT_TYPES[agent?.agent_type];
  const d = {};
  type?.executeFields?.forEach(f => { if (f.defaultValue !== undefined) d[f.name] = f.defaultValue; });
  Object.assign(d, type?.initialExecuteValues?.(agent) || {});
  return d;
};

// input_data d'un node. buildInput() convertit les champs numériques (parseInt) : une référence {{...}} y serait
// perdue, on la rétablit pour les champs numériques visibles.
export const buildNodeInput = (agentType, values) => {
  const v = values || {};
  const input = buildExecuteInput(agentType, v);
  const type = AGENT_TYPES[agentType];
  type?.executeFields?.forEach(f => {
    if (f.type === 'number' && hasTemplate(v[f.name]) && (!type.isFieldVisible || type.isFieldVisible(f, v))) {
      input[f.name] = v[f.name];
    }
  });
  return input;
};

export const toWorkflowJson = (nodes, edges) => ({
  version: WORKFLOW_SCHEMA_VERSION,
  nodes: nodes.map(n => ({
    id: n.id,
    type: 'agent',
    agent_id: n.data.agentId || null,
    input: n.data.agentType ? buildNodeInput(n.data.agentType, n.data.values) : {},
    position: { x: Math.round(n.position.x), y: Math.round(n.position.y) },
    ui: { values: n.data.values || {} },
  })),
  edges: edges.map(e => ({ source: e.source, target: e.target })),
});

// agentsById : { [agent.id]: agent }
export const fromWorkflowJson = (def, agentsById) => {
  const nodes = (def?.nodes || [])
    .filter(n => !n.type || n.type === 'agent')
    .map(n => {
      const agent = agentsById[n.agent_id];
      return {
        id: n.id,
        type: 'agent',
        position: n.position || { x: 0, y: 0 },
        data: {
          agentId: n.agent_id || null,
          agentType: agent?.agent_type ?? null,
          agentName: agent?.name ?? null,
          values: n.ui?.values ?? n.input ?? {},
        },
      };
    });
  const ids = new Set(nodes.map(n => n.id));
  const edges = (def?.edges || [])
    .filter(e => ids.has(e.source) && ids.has(e.target))
    .map(e => ({ id: `e-${e.source}-${e.target}`, source: e.source, target: e.target }));
  return { nodes, edges };
};

export const nextNodeId = (nodes) => {
  const max = nodes.reduce((m, n) => {
    const k = /^n(\d+)$/.exec(n.id);
    return k ? Math.max(m, parseInt(k[1], 10)) : m;
  }, 0);
  return `n${max + 1}`;
};

// Nodes situés en amont (directement ou non) de nodeId
export const ancestorsOf = (nodeId, edges) => {
  const seen = new Set();
  const stack = [nodeId];
  while (stack.length) {
    const cur = stack.pop();
    edges.forEach(e => {
      if (e.target === cur && !seen.has(e.source)) { seen.add(e.source); stack.push(e.source); }
    });
  }
  return seen;
};

const hasCycle = (nodes, edges) => {
  const ids = new Set(nodes.map(n => n.id));
  const indeg = Object.fromEntries(nodes.map(n => [n.id, 0]));
  const valid = edges.filter(e => ids.has(e.source) && ids.has(e.target));
  valid.forEach(e => { indeg[e.target] += 1; });
  const queue = Object.keys(indeg).filter(k => indeg[k] === 0);
  let visited = 0;
  while (queue.length) {
    const cur = queue.shift();
    visited += 1;
    valid.forEach(e => { if (e.source === cur && --indeg[e.target] === 0) queue.push(e.target); });
  }
  return visited !== nodes.length;
};

// errors   : bloquent l'exécution
// warnings : non bloquants (un node qui contient des {{références}} ne peut pas être validé statiquement
//            par les règles du type — ex. regex de version — le backend revalide à l'exécution)
export const validateWorkflow = (nodes, edges, agentsById) => {
  const errors = [];
  const warnings = [];
  if (!nodes.length) errors.push('Add at least one agent node');
  const ids = new Set(nodes.map(n => n.id));

  nodes.forEach(n => {
    const label = `${n.id}${n.data.agentName ? ` (${n.data.agentName})` : ''}`;
    if (!n.data.agentId) { errors.push(`${label}: no agent selected`); return; }
    const agent = agentsById[n.data.agentId];
    if (!agent) { errors.push(`${label}: agent not found (deleted?)`); return; }
    if (!AGENT_TYPES[agent.agent_type]) { errors.push(`${label}: unknown agent type "${agent.agent_type}"`); return; }
    if (!agent.is_active) errors.push(`${label}: agent is disabled`);

    const values = n.data.values || {};
    const msg = validateExecuteInput(agent.agent_type, values);
    if (msg) (nodeHasTemplate(values) ? warnings : errors).push(`${label}: ${msg}`);

    const upstream = ancestorsOf(n.id, edges);
    const refs = new Set();
    for (const m of JSON.stringify(values).matchAll(/\{\{\s*nodes\.([A-Za-z0-9_-]+)/g)) refs.add(m[1]);
    refs.forEach(ref => {
      if (!ids.has(ref)) errors.push(`${label}: references unknown node "${ref}"`);
      else if (!upstream.has(ref)) errors.push(`${label}: references "${ref}" which is not upstream (connect it first)`);
    });
  });

  if (edges.some(e => e.source === e.target)) errors.push('A node cannot be connected to itself');
  else if (hasCycle(nodes, edges)) errors.push('The workflow contains a cycle (v1 supports DAGs only)');

  return { errors, warnings };
};
