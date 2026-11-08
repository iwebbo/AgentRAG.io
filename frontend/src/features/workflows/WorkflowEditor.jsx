import { useState, useRef, useMemo, useCallback, useEffect } from 'react';
import {
  ReactFlow, ReactFlowProvider, Background, Controls, MiniMap, MarkerType,
  addEdge, useNodesState, useEdgesState, useReactFlow,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import Button from '../../components/common/Button';
import Alert from '../../components/common/Alert';
import { AGENT_TYPES } from '../agents/registry';
import AgentNode from './nodes/AgentNode';
import NodePropertiesPanel from './nodes/NodePropertiesPanel';
import { RunStateContext, EMPTY_RUN } from './nodes/RunStateContext';
import AgentPalette, { DRAG_MIME } from './AgentPalette';
import RunDialog from './RunDialog';
import RunSummary from './RunSummary';
import RunHistory from './RunHistory';
import { reduceRunEvent, finalizeRun, hydrateRun } from './runReducer';
import {
  toWorkflowJson, fromWorkflowJson, validateWorkflow, defaultValuesFor, nextNodeId, ancestorsOf,
} from './serialize';
import {
  createWorkflow, updateWorkflow, streamWorkflowRun, listWorkflowRuns, getWorkflowRun, errMsg,
} from './workflowApi';

// Défini hors du composant : React Flow exige des références stables.
const nodeTypes = { agent: AgentNode };
const defaultEdgeOptions = { markerEnd: { type: MarkerType.ArrowClosed } };
const isValidConnection = (c) => c.source !== c.target;

const colorModeFor = () => {
  const t = document.documentElement.getAttribute('data-theme');
  return t === 'light' || t === 'dark' ? t : 'system';
};

const snapshotOf = (name, description, nodes, edges) =>
  JSON.stringify({ name, description, definition: toWorkflowJson(nodes, edges) });

const STATUS_LABEL = { idle: '', running: 'Running…', done: 'Completed', failed: 'Failed', stopped: 'Stopped' };

const WorkflowEditorInner = ({ workflow, agents, hosts, onBack, onSaved }) => {
  const agentsById = useMemo(() => Object.fromEntries(agents.map(a => [a.id, a])), [agents]);
  const paletteAgents = useMemo(() => agents.filter(a => a.is_active && AGENT_TYPES[a.agent_type]), [agents]);
  const initial = useMemo(() => fromWorkflowJson(workflow?.definition, agentsById), []); // eslint-disable-line

  const [nodes, setNodes, onNodesChange] = useNodesState(initial.nodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initial.edges);
  const [wfId, setWfId] = useState(workflow?.id || null);
  const [name, setName] = useState(workflow?.name || '');
  const [description, setDescription] = useState(workflow?.description || '');
  const [savedSnapshot, setSavedSnapshot] = useState(
    () => snapshotOf(workflow?.name || '', workflow?.description || '', initial.nodes, initial.edges),
  );
  const [saving, setSaving] = useState(false);
  const [problems, setProblems] = useState({ errors: [], warnings: [] });
  const [showRunDialog, setShowRunDialog] = useState(false);
  const [run, setRun] = useState(EMPTY_RUN);
  const [history, setHistory] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);

  const abortRef = useRef(null);
  const wrapperRef = useRef(null);
  const nodesRef = useRef(nodes);
  nodesRef.current = nodes;
  const { screenToFlowPosition } = useReactFlow();

  // fermeture de la page : on coupe le flux SSE ouvert
  useEffect(() => () => abortRef.current?.abort(), []);

  const refreshHistory = useCallback(async (id) => {
    if (!id) { setHistory([]); return; }
    setHistoryLoading(true);
    try { setHistory(await listWorkflowRuns(id)); } catch { /* l'historique est secondaire */ } finally { setHistoryLoading(false); }
  }, []);

  useEffect(() => { refreshHistory(wfId); }, [wfId, refreshHistory]);

  const snapshot = useMemo(() => snapshotOf(name, description, nodes, edges), [name, description, nodes, edges]);
  const dirty = snapshot !== savedSnapshot;
  const isRunning = run.status === 'running';

  const selected = nodes.filter(n => n.selected);
  const selectedNode = selected.length === 1 ? selected[0] : null;
  const upstreamIds = selectedNode ? [...ancestorsOf(selectedNode.id, edges)].sort() : [];

  // ── édition du graphe ──────────────────────────────────────────────────────
  const onConnect = useCallback(
    (params) => setEdges(es => addEdge({ ...params, id: `e-${params.source}-${params.target}` }, es)),
    [setEdges],
  );

  const addAgentNode = useCallback((agent, position) => {
    setNodes(ns => [
      ...ns.map(n => (n.selected ? { ...n, selected: false } : n)),
      {
        id: nextNodeId(ns), type: 'agent', position, selected: true,
        data: { agentId: agent.id, agentType: agent.agent_type, agentName: agent.name, values: defaultValuesFor(agent) },
      },
    ]);
  }, [setNodes]);

  const handleAddClick = (agent) => {
    const rect = wrapperRef.current.getBoundingClientRect();
    const jitter = (nodesRef.current.length % 5) * 24;
    addAgentNode(agent, screenToFlowPosition({
      x: rect.left + rect.width / 2 - 105 + jitter,
      y: rect.top + rect.height / 2 - 30 + jitter,
    }));
  };

  const onDragOver = (e) => { e.preventDefault(); e.dataTransfer.dropEffect = 'move'; };
  const onDrop = (e) => {
    e.preventDefault();
    const agent = agentsById[e.dataTransfer.getData(DRAG_MIME)];
    if (agent) addAgentNode(agent, screenToFlowPosition({ x: e.clientX, y: e.clientY }));
  };

  const changeNodeAgent = (nodeId, agentId) => {
    const agent = agentsById[agentId];
    setNodes(ns => ns.map(n => (n.id !== nodeId ? n : {
      ...n,
      data: agent
        ? { agentId: agent.id, agentType: agent.agent_type, agentName: agent.name, values: defaultValuesFor(agent) }
        : { agentId: null, agentType: null, agentName: null, values: {} },
    })));
  };

  const setNodeValue = (nodeId, field, value) => {
    setNodes(ns => ns.map(n => (n.id !== nodeId ? n : {
      ...n, data: { ...n.data, values: { ...n.data.values, [field]: value } },
    })));
  };

  const deleteNode = (nodeId) => {
    setNodes(ns => ns.filter(n => n.id !== nodeId));
    setEdges(es => es.filter(e => e.source !== nodeId && e.target !== nodeId));
  };

  const clearSelection = () => setNodes(ns => ns.map(n => (n.selected ? { ...n, selected: false } : n)));

  const selectNode = (nodeId) => setNodes(ns => ns.map(n => ({ ...n, selected: n.id === nodeId })));

  // ── sauvegarde ─────────────────────────────────────────────────────────────
  const save = async () => {
    if (!name.trim()) { setProblems({ errors: ['Workflow name is required'], warnings: [] }); return null; }
    setSaving(true);
    try {
      const payload = { name: name.trim(), description, definition: toWorkflowJson(nodes, edges) };
      const saved = wfId ? await updateWorkflow(wfId, payload) : await createWorkflow(payload);
      const id = saved?.id ?? wfId;
      setWfId(id);
      setSavedSnapshot(snapshot);
      setProblems({ errors: [], warnings: [] });
      onSaved?.({ ...saved, id });
      return id;
    } catch (e) {
      setProblems({ errors: [errMsg(e, 'Failed to save workflow')], warnings: [] });
      return null;
    } finally {
      setSaving(false);
    }
  };

  // ── exécution ──────────────────────────────────────────────────────────────
  const agentTypeOf = (nodeId) => nodesRef.current.find(n => n.id === nodeId)?.data.agentType;

  const startRun = async (inputData) => {
    setShowRunDialog(false);
    const { errors, warnings } = validateWorkflow(nodes, edges, agentsById);
    setProblems({ errors, warnings });
    if (errors.length) return;

    const id = wfId && !dirty ? wfId : await save();
    if (!id) return;
    setProblems({ errors: [], warnings });

    const ctrl = new AbortController();
    abortRef.current = ctrl;
    setRun({ status: 'running', error: null, logs: [], nodes: {} });
    try {
      await streamWorkflowRun(
        id, inputData,
        (type, data) => setRun(prev => reduceRunEvent(prev, type, data, agentTypeOf)),
        ctrl.signal,
      );
      setRun(prev => finalizeRun(prev));
    } catch (e) {
      if (e.name === 'AbortError') setRun(prev => ({ ...prev, status: 'stopped' }));
      else setRun(prev => ({ ...prev, status: 'failed', error: e.message || 'Execution failed' }));
    } finally {
      refreshHistory(id);
    }
  };

  const stopRun = () => abortRef.current?.abort();

  // charge un run passé dans l'état d'affichage (canvas + panneau de droite)
  const loadHistoryRun = async (runId) => {
    if (isRunning) return;
    try {
      const persisted = await getWorkflowRun(runId);
      setNodes(ns => ns.map(n => (n.selected ? { ...n, selected: false } : n)));
      setRun(hydrateRun(persisted, agentTypeOf));
    } catch (e) {
      setProblems({ errors: [errMsg(e, 'Failed to load run')], warnings: [] });
    }
  };

  return (
    <RunStateContext.Provider value={run}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-3)' }}>

        {/* Toolbar */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-3)', flexWrap: 'wrap' }}>
          <Button variant="ghost" onClick={onBack} disabled={isRunning}>← Workflows</Button>
          <input className="form-input" style={{ maxWidth: 260 }} value={name} onChange={e => setName(e.target.value)} placeholder="Workflow name *" />
          <input className="form-input" style={{ flex: 1, minWidth: 180 }} value={description} onChange={e => setDescription(e.target.value)} placeholder="Description (optional)" />
          {dirty && <span style={{ fontSize: 'var(--text-xs)', color: 'var(--warning)' }}>● unsaved</span>}
          {STATUS_LABEL[run.status] && <span style={{ fontSize: 'var(--text-xs)', color: 'var(--gray-600)' }}>{STATUS_LABEL[run.status]}</span>}
          <Button variant="ghost" onClick={save} disabled={saving || isRunning || !dirty}>{saving ? 'Saving…' : 'Save'}</Button>
          {isRunning
            ? <Button variant="ghost" onClick={stopRun}>■ Stop</Button>
            : <Button variant="primary" onClick={() => setShowRunDialog(true)} disabled={saving}>▶ Run</Button>}
        </div>

        {problems.errors.length > 0 && (
          <Alert type="error" onClose={() => setProblems(p => ({ ...p, errors: [] }))}>
            {problems.errors.map((m, i) => <div key={i}>{m}</div>)}
          </Alert>
        )}
        {problems.warnings.length > 0 && (
          <div style={{ padding: 'var(--spacing-2) var(--spacing-3)', border: '1px solid var(--warning)', borderLeft: '3px solid var(--warning)', borderRadius: 'var(--radius)', backgroundColor: 'rgba(251,191,36,0.06)', fontSize: 'var(--text-xs)', color: 'var(--gray-700)', lineHeight: 1.6 }}>
            <strong style={{ color: 'var(--warning-dark)' }}>Not statically checkable (node uses references) — validated by the backend at run time:</strong>
            {problems.warnings.map((m, i) => <div key={i}>{m}</div>)}
          </div>
        )}

        {/* Palette | canvas | propriétés */}
        <div style={{ display: 'flex', height: 'calc(100vh - 280px)', minHeight: 520, border: '1px solid var(--gray-200)', borderRadius: 'var(--radius-md)', overflow: 'hidden' }}>
          <AgentPalette agents={paletteAgents} onAdd={handleAddClick} />

          <div ref={wrapperRef} style={{ flex: 1, minWidth: 0 }}>
            <ReactFlow
              nodes={nodes}
              edges={edges}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              onConnect={onConnect}
              nodeTypes={nodeTypes}
              defaultEdgeOptions={defaultEdgeOptions}
              isValidConnection={isValidConnection}
              onDrop={onDrop}
              onDragOver={onDragOver}
              colorMode={colorModeFor()}
              fitView
            >
              <Background />
              <Controls />
              <MiniMap pannable zoomable />
            </ReactFlow>
          </div>

          <aside style={{ width: 340, flexShrink: 0, borderLeft: '1px solid var(--gray-200)', overflowY: 'auto', background: 'var(--bg-card)' }}>
            {selectedNode ? (
              <NodePropertiesPanel
                key={selectedNode.id}
                node={selectedNode}
                agents={paletteAgents}
                hosts={hosts}
                upstreamIds={upstreamIds}
                nodeRun={run.nodes[selectedNode.id]}
                onChangeAgent={changeNodeAgent}
                onChangeValue={(field, value) => setNodeValue(selectedNode.id, field, value)}
                onDelete={deleteNode}
                onBack={clearSelection}
              />
            ) : (
              <RunSummary run={run} nodes={nodes} onSelectNode={selectNode}>
                {wfId && (
                  <RunHistory
                    runs={history}
                    loading={historyLoading}
                    activeId={run.runId}
                    disabled={isRunning}
                    onSelect={loadHistoryRun}
                  />
                )}
              </RunSummary>
            )}
          </aside>
        </div>
      </div>

      {showRunDialog && <RunDialog onRun={startRun} onClose={() => setShowRunDialog(false)} />}
    </RunStateContext.Provider>
  );
};

// Le Provider est requis pour useReactFlow (screenToFlowPosition)
const WorkflowEditor = (props) => (
  <ReactFlowProvider>
    <WorkflowEditorInner {...props} />
  </ReactFlowProvider>
);

export default WorkflowEditor;
