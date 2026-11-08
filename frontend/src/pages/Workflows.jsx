import { useState, useEffect } from 'react';
import { Plus } from 'lucide-react';
import Layout from '../components/layout/Layout';
import Button from '../components/common/Button';
import Loading from '../components/common/Loading';
import Alert from '../components/common/Alert';
import api from '../services/api';
import WorkflowEditor from '../features/workflows/WorkflowEditor';
import { listWorkflows, getWorkflow, deleteWorkflow, errMsg } from '../features/workflows/workflowApi';

// ─────────────────────────────────────────────────────────────────────────────
// PAGE WORKFLOWS — liste + éditeur (feature : src/features/workflows).
// Dépend des agents uniquement via src/features/agents/registry.
// Route à déclarer : /workflows  (voir src/features/workflows/README.md)
// ─────────────────────────────────────────────────────────────────────────────
const Workflows = () => {
  const [workflows, setWorkflows] = useState([]);
  const [agents, setAgents] = useState([]);
  const [hosts, setHosts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [editing, setEditing] = useState(null); // null | 'new' | workflow (avec definition)

  const refreshList = async () => {
    try { setWorkflows(await listWorkflows()); } catch (e) { setError(errMsg(e, 'Failed to load workflows')); }
  };

  useEffect(() => {
    (async () => {
      try {
        const [wf, ag] = await Promise.all([listWorkflows(), api.get('/api/agents/')]);
        setWorkflows(wf);
        setAgents(ag.data);
      } catch (e) {
        setError(errMsg(e, 'Failed to load workflows'));
      } finally {
        setLoading(false);
      }
      try { setHosts((await api.get('/api/hosts/')).data); } catch (_) { /* hosts : uniquement pour les agents skill */ }
    })();
  }, []);

  const openWorkflow = async (w) => {
    try { setEditing(await getWorkflow(w.id)); } catch (e) { setError(errMsg(e, 'Failed to open workflow')); }
  };

  const removeWorkflow = async (w) => {
    if (!confirm(`Delete workflow "${w.name}"?`)) return;
    try { await deleteWorkflow(w.id); refreshList(); } catch (e) { setError(errMsg(e, 'Failed to delete workflow')); }
  };

  if (loading) return <Layout><Loading /></Layout>;

  return (
    <Layout>
      <div className="page">
        {error && <Alert type="error" style={{ marginBottom: 'var(--spacing-4)' }} onClose={() => setError(null)}>{error}</Alert>}

        {editing ? (
          <WorkflowEditor
            key={editing === 'new' ? 'new' : editing.id}
            workflow={editing === 'new' ? null : editing}
            agents={agents}
            hosts={hosts}
            onBack={() => { setEditing(null); refreshList(); }}
            onSaved={refreshList}
          />
        ) : (
          <>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 'var(--spacing-5)' }}>
              <div>
                <h1 style={{ fontSize: 'var(--text-3xl)', fontWeight: '700', marginBottom: 'var(--spacing-1)' }}>Workflows</h1>
                <p style={{ color: 'var(--gray-600)', fontSize: 'var(--text-sm)' }}>Chain agents into a graph executed by the backend</p>
              </div>
              <Button variant="primary" onClick={() => setEditing('new')} icon={Plus}>New workflow</Button>
            </div>

            {workflows.length === 0 ? (
              <div style={{ textAlign: 'center', padding: 'var(--spacing-12)', color: 'var(--gray-600)' }}>
                <h3 style={{ fontSize: 'var(--text-xl)', fontWeight: '600', marginBottom: 'var(--spacing-2)' }}>No workflows yet</h3>
                <Button variant="primary" onClick={() => setEditing('new')} icon={Plus}>Create your first workflow</Button>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-2)' }}>
                {workflows.map(w => (
                  <div key={w.id} style={{ display: 'grid', gridTemplateColumns: '1fr auto auto', alignItems: 'center', gap: 'var(--spacing-3)', padding: 'var(--spacing-3) var(--spacing-4)', background: 'var(--bg-card)', border: '1px solid var(--gray-200)', borderRadius: 'var(--radius-md)' }}>
                    <div style={{ minWidth: 0 }}>
                      <div style={{ fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{w.name}</div>
                      {w.description && <div style={{ fontSize: 'var(--text-xs)', color: 'var(--gray-600)', marginTop: 2 }}>{w.description}</div>}
                    </div>
                    <span style={{ fontSize: 11, color: 'var(--gray-600)' }}>{w.updated_at ? `updated ${new Date(w.updated_at).toLocaleDateString()}` : ''}</span>
                    <div style={{ display: 'flex', gap: 4 }}>
                      <Button variant="ghost" size="sm" onClick={() => openWorkflow(w)}>Open</Button>
                      <button title="Delete" onClick={() => removeWorkflow(w)} style={{ width: 30, height: 30, borderRadius: 'var(--radius)', border: '1px solid var(--gray-300)', background: 'var(--gray-100)', color: 'var(--danger)', cursor: 'pointer' }}>✕</button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </Layout>
  );
};

export default Workflows;
