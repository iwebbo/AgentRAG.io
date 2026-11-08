import { useState, useEffect } from 'react';
import { Plus, History, Settings } from 'lucide-react';
import Layout from '../components/layout/Layout';
import Button from '../components/common/Button';
import Loading from '../components/common/Loading';
import Alert from '../components/common/Alert';
import api from '../services/api';
import { AGENT_TYPES } from '../features/agents/registry';
import { useAgentRuns } from '../features/agents/hooks/useAgentRuns';
import CreateAgentModal from '../features/agents/components/CreateAgentModal';
import ExecuteAgentModal from '../features/agents/components/ExecuteAgentModal';
import AgentConfigModal from '../features/agents/components/AgentConfigModal';
import RegisterSkillModal from '../features/agents/components/RegisterSkillModal';
import ExecutionHistoryPanel from '../features/agents/components/ExecutionHistoryPanel';
import AgentRunDock from '../features/agents/components/AgentRunDock';
import HostsTab from '../features/agents/components/HostsTab';
import DocumentationTab from '../features/agents/components/DocumentationTab';

// ─────────────────────────────────────────────────────────────────────────────
// PAGE AGENTS — orchestration uniquement (liste, onglets, ouverture des modals).
// Logique par type d'agent : src/features/agents/registry/types/<agent_type>.jsx
// ─────────────────────────────────────────────────────────────────────────────
const Agents = () => {
  const [agents, setAgents] = useState([]);
  const [hosts, setHosts] = useState([]);
  const [skills, setSkills] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [activeTab, setActiveTab] = useState('all');
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showExecuteModal, setShowExecuteModal] = useState(false);
  const [showRegisterSkill, setShowRegisterSkill] = useState(false);
  const [historyAgent, setHistoryAgent] = useState(null); // agent dont on affiche l'historique
  const [selectedAgent, setSelectedAgent] = useState(null);
  const [configAgent, setConfigAgent] = useState(null);
  const [providers, setProviders] = useState([]);

  useEffect(() => { loadAll(); }, []);

  const loadAll = async () => {
    setLoading(true);
    try {
      const [agRes, provRes] = await Promise.all([
        api.get('/api/agents/'),
        api.get('/api/providers/')
      ]);
      setAgents(agRes.data);
      setProviders(provRes.data.filter(p => p.is_active));
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load agents');
    } finally {
      setLoading(false);
    }
    try {
      const [hRes, sRes] = await Promise.all([
        api.get('/api/hosts/'),
        api.get('/api/skills/')
      ]);
      setHosts(hRes.data);
      setSkills(sRes.data);
    } catch (_) {}
  };

  const loadHosts = async () => {
    try { const res = await api.get('/api/hosts/'); setHosts(res.data); } catch (_) {}
  };
  const handleCreateAgent = () => {
    setShowCreateModal(true);
    setError(null); setSuccess(null);
  };

  const toggleAgent = async (agentId) => {
    try { await api.patch(`/api/agents/${agentId}/toggle`); loadAll(); }
    catch (err) { setError(err.response?.data?.detail || 'Failed to toggle agent'); }
  };

  const deleteAgent = async (agentId) => {
    if (!confirm('Delete this agent?')) return;
    try {
      await api.delete(`/api/agents/${agentId}`);
      setSuccess('Agent deleted');
      setTimeout(() => setSuccess(null), 2000);
      loadAll();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to delete agent');
    }
  };

  // Refresh silencieux sans spinner — ne démonte pas le modal ouvert
  const refreshAgentsSilent = async () => {
    try {
      const res = await api.get('/api/agents/');
      setAgents(res.data);
    } catch (_) {}
  };

  // Callback post-exécution : refresh silencieux, le modal reste ouvert
  const handleAgentExecuted = () => { setTimeout(refreshAgentsSilent, 1000); };

  const agentRuns = useAgentRuns({ onExecuted: handleAgentExecuted });
  const totalActive = agents.filter(a => a.is_active).length;
  const totalRuns = agents.reduce((s, a) => s + (a.execution_count || 0), 0);

  const filteredAgents = agents.filter(a => {
    if (activeTab === 'fixed') return AGENT_TYPES[a.agent_type]?.badge === 'fixed';
    if (activeTab === 'skill') return AGENT_TYPES[a.agent_type]?.badge === 'skill';
    return true;
  });
  if (loading) return <Layout><Loading /></Layout>;

  const TABS = [
    { key: 'all', label: 'All agents' },
    { key: 'fixed', label: 'Fixed agents' },
    { key: 'skill', label: 'Skill agents' },
    { key: 'hosts', label: 'Hosts' },
    { key: 'docs', label: 'Docs' }
  ];

  return (
    <Layout>
      <div className="page">

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 'var(--spacing-5)' }}>
          <div>
            <h1 style={{ fontSize: 'var(--text-3xl)', fontWeight: '700', marginBottom: 'var(--spacing-1)' }}>AI Agents</h1>
            <p style={{ color: 'var(--gray-600)', fontSize: 'var(--text-sm)' }}>Create and manage specialized AI agents for different tasks</p>
          </div>
          <div style={{ display: 'flex', gap: 'var(--spacing-2)' }}>
            <Button variant="primary" onClick={() => setShowRegisterSkill(true)} icon={Plus}>New skill</Button>
            <Button variant="primary" onClick={handleCreateAgent} icon={Plus}>New agent</Button>
          </div>
        </div>

        {error && <Alert type="error" style={{ marginBottom: 'var(--spacing-4)' }} onClose={() => setError(null)}>{error}</Alert>}
        {success && <Alert type="success" style={{ marginBottom: 'var(--spacing-4)' }} onClose={() => setSuccess(null)}>{success}</Alert>}

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 'var(--spacing-3)', marginBottom: 'var(--spacing-5)' }}>
          {[
            { label: 'Total agents', value: agents.length, color: 'var(--gray-800)' },
            { label: 'Active', value: totalActive, color: 'var(--success)' },
            { label: 'Disabled', value: agents.length - totalActive, color: 'var(--warning)' },
            { label: 'Total runs', value: totalRuns, color: 'var(--primary)' }
          ].map(s => (
            <div key={s.label} style={{ background: 'var(--gray-100)', border: '1px solid var(--gray-200)', borderRadius: 'var(--radius)', padding: 'var(--spacing-3)', textAlign: 'center' }}>
              <div style={{ fontSize: 'var(--text-2xl)', fontWeight: '700', color: s.color }}>{s.value}</div>
              <div style={{ fontSize: 'var(--text-xs)', color: 'var(--gray-600)', marginTop: '2px' }}>{s.label}</div>
            </div>
          ))}
        </div>

        <div style={{ display: 'flex', borderBottom: '1px solid var(--gray-200)', marginBottom: 'var(--spacing-5)', gap: 'var(--spacing-1)' }}>
          {TABS.map(tab => (
            <button key={tab.key} onClick={() => setActiveTab(tab.key)} style={{
              padding: 'var(--spacing-2) var(--spacing-4)', background: 'none', border: 'none', cursor: 'pointer',
              fontSize: 'var(--text-sm)', fontWeight: activeTab === tab.key ? '600' : '400',
              color: activeTab === tab.key ? 'var(--primary)' : 'var(--gray-600)',
              borderBottom: activeTab === tab.key ? '2px solid var(--primary)' : '2px solid transparent',
              marginBottom: '-1px', transition: 'color .15s'
            }}>{tab.label}</button>
          ))}
        </div>

        {activeTab === 'hosts' && <HostsTab hosts={hosts} onRefresh={loadHosts} />}
        {activeTab === 'docs' && <DocumentationTab />}

        {!["hosts", "docs"].includes(activeTab) && (
          filteredAgents.length === 0 ? (
            <div style={{ textAlign: 'center', padding: 'var(--spacing-12)', color: 'var(--gray-600)' }}>
              <div style={{ fontSize: '3rem', marginBottom: 'var(--spacing-3)' }}>🤖</div>
              <h3 style={{ fontSize: 'var(--text-xl)', fontWeight: '600', marginBottom: 'var(--spacing-2)' }}>No agents yet</h3>
              <p style={{ marginBottom: 'var(--spacing-4)', fontSize: 'var(--text-sm)' }}>Create your first AI agent to automate tasks</p>
              <Button variant="primary" onClick={handleCreateAgent} icon={Plus}>Create your first agent</Button>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-2)' }}>
              {filteredAgents.map(agent => {
                const t = AGENT_TYPES[agent.agent_type];
                const accentColor = t?.color || 'var(--gray-400)';
                return (
                  <div key={agent.id} style={{
                    display: 'grid', gridTemplateColumns: '36px 1fr auto auto',
                    alignItems: 'center', gap: 'var(--spacing-3)',
                    padding: 'var(--spacing-3) var(--spacing-4)',
                    background: 'var(--bg-card)', border: '1px solid var(--gray-200)',
                    borderLeft: `3px solid ${accentColor}`, borderRadius: 'var(--radius-md)',
                    opacity: agent.is_active ? 1 : 0.6, transition: 'border-color .15s'
                  }}>
                    <div style={{ width: '36px', height: '36px', borderRadius: 'var(--radius)', background: 'var(--gray-100)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '18px' }}>
                      {t?.icon || '🤖'}
                    </div>
                    <div style={{ minWidth: 0 }}>
                      <div style={{ fontWeight: '600', fontSize: 'var(--text-base)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{agent.name}</div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-2)', flexWrap: 'wrap', marginTop: '3px' }}>
                        <span style={{ fontSize: '10px', fontWeight: '600', padding: '1px 7px', borderRadius: '99px', background: t?.badge === 'skill' ? 'rgba(34,197,94,.15)' : 'rgba(96,165,250,.15)', color: t?.badge === 'skill' ? 'var(--success-dark)' : 'var(--primary-dark)' }}>{t?.badge === 'skill' ? 'Skill' : 'Fixed'}</span>
                        {t?.mcp?.map(m => <span key={m} style={{ fontSize: '10px', padding: '1px 6px', borderRadius: '99px', background: 'var(--gray-200)', color: 'var(--gray-700)' }}>{m}</span>)}
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', fontSize: '11px', color: agent.is_active ? 'var(--success)' : 'var(--gray-500)' }}>
                          <span style={{ width: '7px', height: '7px', borderRadius: '50%', background: agent.is_active ? 'var(--success)' : 'var(--gray-400)', display: 'inline-block' }} />
                          {agent.is_active ? 'active' : 'disabled'}
                        </span>
                        <span style={{ fontSize: '11px', color: 'var(--gray-600)' }}>updated {new Date(agent.updated_at).toLocaleDateString()}</span>
                      </div>
                    </div>
                    <div style={{ textAlign: 'right', minWidth: '48px' }}>
                      <div style={{ fontSize: 'var(--text-lg)', fontWeight: '700' }}>{agent.execution_count || 0}</div>
                      <div style={{ fontSize: '10px', color: 'var(--gray-600)' }}>runs</div>
                    </div>
                    <div style={{ display: 'flex', gap: '4px', alignItems: 'center' }}>
                      <button title="Execute" disabled={!agent.is_active} onClick={() => { setSelectedAgent(agent); setShowExecuteModal(true); }} style={{ width: '30px', height: '30px', borderRadius: 'var(--radius)', border: agent.is_active ? '1px solid var(--success)' : '1px solid var(--gray-300)', background: agent.is_active ? 'rgba(52,211,153,.12)' : 'var(--gray-100)', color: agent.is_active ? 'var(--success)' : 'var(--gray-400)', cursor: agent.is_active ? 'pointer' : 'not-allowed', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '14px' }}>▶</button>
                      <button title="Execution history" onClick={() => setHistoryAgent(agent)} style={{ width: '30px', height: '30px', borderRadius: 'var(--radius)', border: '1px solid var(--gray-300)', background: 'var(--gray-100)', color: 'var(--gray-600)', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                        <History size={14} />
                      </button>
                      <button title="Configuration" onClick={() => setConfigAgent(agent)} style={{ width: '30px', height: '30px', borderRadius: 'var(--radius)', border: '1px solid var(--gray-300)', background: 'var(--gray-100)', color: 'var(--gray-600)', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                        <Settings size={14} />
                      </button>
                      <button title={agent.is_active ? 'Disable' : 'Enable'} onClick={() => toggleAgent(agent.id)} style={{ width: '30px', height: '30px', borderRadius: 'var(--radius)', border: '1px solid var(--gray-300)', background: 'var(--gray-100)', color: 'var(--gray-600)', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '14px' }}>{agent.is_active ? '⏸' : '▷'}</button>
                      <button title="Delete" onClick={() => deleteAgent(agent.id)} style={{ width: '30px', height: '30px', borderRadius: 'var(--radius)', border: '1px solid var(--gray-300)', background: 'var(--gray-100)', color: 'var(--danger)', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '14px' }}>✕</button>
                    </div>
                  </div>
                );
              })}
            </div>
          )
        )}

        {historyAgent && (
          <ExecutionHistoryPanel
            agent={historyAgent}
            agentType={AGENT_TYPES[historyAgent.agent_type]}
            onClose={() => setHistoryAgent(null)}
            onReopenExec={(exec) => {
              agentRuns.openFromExecution(historyAgent, exec);
              setHistoryAgent(null);
            }}
          />
        )}

        {showRegisterSkill && (
          <RegisterSkillModal providers={providers} onClose={() => setShowRegisterSkill(false)} onSuccess={loadAll} />
        )}

        {showExecuteModal && selectedAgent && (
          <ExecuteAgentModal
            agent={selectedAgent}
            agentType={AGENT_TYPES[selectedAgent.agent_type]}
            hosts={hosts}
            initialValues={agentRuns.rerun?.agentId === selectedAgent.id ? agentRuns.rerun.values : undefined}
            onClose={() => { setShowExecuteModal(false); setSelectedAgent(null); agentRuns.setRerun(null); }}
            onStart={(inputData, formValues) => {
              agentRuns.startRun(selectedAgent, inputData, formValues);
              setShowExecuteModal(false);
              setSelectedAgent(null);
              agentRuns.setRerun(null);
            }}
          />
        )}

        <AgentRunDock
          runs={agentRuns.runs}
          activeRunId={agentRuns.activeRunId}
          drawerOpen={agentRuns.drawerOpen}
          onSelect={agentRuns.selectRun}
          onMinimize={() => agentRuns.setDrawerOpen(false)}
          onDismiss={agentRuns.dismissRun}
          onOpenExecution={agentRuns.openFromExecution}
          onRunAgain={(run) => {
            agentRuns.setRerun({ agentId: run.agent.id, values: run.formValues });
            setSelectedAgent(run.agent);
            setShowExecuteModal(true);
          }}
        />
        {showCreateModal && (
          <CreateAgentModal
            providers={providers}
            skills={skills}
            onClose={() => setShowCreateModal(false)}
            onCreated={() => { setShowCreateModal(false); loadAll(); }}
          />
        )}

        {configAgent && (
          <AgentConfigModal
            agent={configAgent}
            providers={providers}
            skills={skills}
            onClose={() => setConfigAgent(null)}
            onSaved={loadAll}
          />
        )}

      </div>
    </Layout>
  );
};

export default Agents;
