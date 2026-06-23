import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Plus, ChevronDown, ChevronUp, Send, Loader2, Bot, User, Copy, Check, ExternalLink, History, MessageCircle } from 'lucide-react';
import Layout from '../components/layout/Layout';
import Button from '../components/common/Button';
import Loading from '../components/common/Loading';
import Alert from '../components/common/Alert';
import MarkdownMessage from '../components/common/MarkdownMessage';
import { StreamingService } from '../services/streaming';
import api from '../services/api';


// ─────────────────────────────────────────────────────────────────────────────
// AGENT TYPES REGISTRY
// ─────────────────────────────────────────────────────────────────────────────
const AGENT_TYPES = {
  branch_code_review: {
    name: 'Code Review',
    description: 'Automatic code review on Git branches with fix suggestions and PR creation',
    icon: '⎔', color: '#3b82f6', badge: 'fixed', mcp: ['github'],
    defaultConfig: (providers) => ({ mcp_servers: ['github'], use_llm: true, llm_provider: providers[0]?.name || 'ollama', llm_model: 'codestral:22b', llm_temperature: 0.3, review_focus: 'security', auto_fix: true, auto_create_pr: true }),
    mcpConfig: { github: { token: '', repo: '' } },
    requiredFields: ['github.token', 'github.repo'],
    executeFields: [
      { name: 'branch', label: 'Branch name', type: 'text', placeholder: 'feature/my-branch', required: true }
    ]
  },
  code_generator: {
    name: 'Code Generator',
    description: 'AI-assisted code generation with RAG, automatic tests and linting',
    icon: '⌬', color: '#8b5cf6', badge: 'fixed', mcp: ['github', 'linter'],
    defaultConfig: (providers) => ({ mcp_servers: ['github', 'linter'], llm_provider: providers[0]?.name || 'ollama', llm_model: 'codestral:22b', llm_temperature: 0.2, target_branch: 'ai-feature', base_branch: 'main', auto_test: true, auto_lint: true, auto_commit: true, auto_create_pr: false }),
    mcpConfig: { github: { token: '', repo: '' } },
    requiredFields: ['github.token', 'github.repo'],
    executeFields: [
      { name: 'prompt', label: 'Code generation prompt', type: 'textarea', placeholder: 'Add OAuth2 authentication...', required: true },
      { name: 'create_new_files', label: 'Create new files', type: 'checkbox', defaultValue: true },
      { name: 'test_mode', label: 'Test mode (dry-run)', type: 'checkbox', defaultValue: true }
    ]
  },
  legal_fiscal: {
    name: 'Legal & Fiscal Expert',
    description: 'Legal and fiscal expert with RAG on legal documents (contracts, invoices, GDPR)',
    icon: '⚖', color: '#059669', badge: 'fixed', mcp: [],
    defaultConfig: (providers) => ({ llm_provider: providers[0]?.name || 'ollama', llm_model: 'mistrallite:latest', llm_temperature: 0.3, legal_config: { domains: ['fiscal', 'social', 'commercial'], auto_summary: true, extract_entities: true } }),
    mcpConfig: {}, requiredFields: [],
    executeFields: [
      { name: 'mode', label: 'Analysis mode', type: 'select', required: true, options: [ { value: 'analyze', label: 'Analyze document' }, { value: 'risk_assessment', label: 'Risk assessment' }, { value: 'compliance_check', label: 'Compliance check' }, { value: 'claim_processing', label: 'Claim processing' }, { value: 'document_drafting', label: 'Document drafting' }, { value: 'legal_research', label: 'Legal research' }, { value: 'training', label: 'Training material' }, { value: 'monitoring', label: 'Legislative monitoring' } ] },
      { name: 'query', label: 'Query / instructions', type: 'textarea', placeholder: 'Analyze contract clauses...', required: true },
      { name: 'documents', label: 'Document paths (optional, comma-separated)', type: 'text', placeholder: '/app/data/contract.pdf' }
    ]
  },
  accounting_finance: {
    name: 'Accounting Expert',
    description: 'Accounting and financial expert — analysis, strategic advice, journal entries',
    icon: '∑', color: '#dc2626', badge: 'fixed', mcp: [],
    defaultConfig: (providers) => ({ llm_provider: providers[0]?.name || 'ollama', llm_model: 'mistrallite:latest', llm_temperature: 0.3, accounting_config: { domains: ['accounting', 'social'], auto_summary: true, extract_entities: true } }),
    mcpConfig: {}, requiredFields: [],
    executeFields: [
      { name: 'mode', label: 'Mode', type: 'select', required: true, options: [ { value: 'accounting_entry', label: 'Accounting entry' }, { value: 'strategic_advice', label: 'Strategic advice' } ] },
      { name: 'query', label: 'Query / instructions', type: 'textarea', placeholder: 'Enter invoice details...', required: true }
    ]
  },
  travel_expert: {
    name: 'Travel Expert',
    description: 'Personalized travel planning with integrated web search',
    icon: '⌘', color: '#0ea5e9', badge: 'fixed', mcp: [],
    defaultConfig: (providers) => ({ llm_provider: providers[0]?.name || 'ollama', llm_model: 'mistrallite:latest', llm_temperature: 0.4, travel_config: { search_preferences: { budget_aware: true, eco_friendly: true, accessibility: false } } }),
    mcpConfig: {}, requiredFields: [],
    executeFields: [
      { name: 'mode', label: 'Mode', type: 'select', required: true, options: [ { value: 'itinerary_planning', label: 'Itinerary planning' }, { value: 'destination_search', label: 'Destination search' }, { value: 'budget_analysis', label: 'Budget analysis' } ], defaultValue: 'itinerary_planning' },
      { name: 'query', label: 'Travel request', type: 'textarea', placeholder: 'Trip to Japan for 2 weeks, couple, budget 4000€...', required: true }
    ]
  },
  email_expert: {
    name: 'Email Expert',
    description: 'Smart email management — analysis, drafting, automatic replies',
    icon: '⊠', color: '#f59e0b', badge: 'fixed', mcp: [],
    defaultConfig: (providers) => ({ llm_provider: providers[0]?.name || 'ollama', llm_model: 'mistrallite:latest', llm_temperature: 0.6, email_config: { email: '', password: '', imap_host: 'imap.gmail.com', imap_port: 993, smtp_host: 'smtp.gmail.com', smtp_port: 587, auto_categorize: true, auto_reply_enabled: false, signature: 'Best regards,\nYour AI Assistant', default_tone: 'professional', language: 'en' } }),
    mcpConfig: {}, requiredFields: ['email_config.email', 'email_config.password'],
    executeFields: [
      { name: 'mode', label: 'Email mode', type: 'select', required: true, options: [ { value: 'send_email', label: 'Send email' }, { value: 'send_email_llm', label: 'Send email (LLM-generated)' }, { value: 'analyze_inbox', label: 'Analyze inbox' } ] },
      { name: 'to', label: 'To (send modes)', type: 'text', placeholder: 'recipient@example.com' },
      { name: 'subject', label: 'Subject (send modes)', type: 'text', placeholder: 'Email subject' },
      { name: 'body', label: 'Body (send_email)', type: 'textarea', placeholder: 'Email content...' },
      { name: 'instructions', label: 'Instructions (send_email_llm)', type: 'textarea', placeholder: 'Instructions for LLM...' },
      { name: 'context', label: 'Context (send_email_llm)', type: 'text', placeholder: 'Additional context' },
      { name: 'limit', label: 'Limit (analyze_inbox)', type: 'number', placeholder: '20' },
      { name: 'unread_only', label: 'Unread only (analyze_inbox)', type: 'checkbox', defaultValue: true },
      { name: 'auto_send', label: 'Auto send (send_email_llm)', type: 'checkbox', defaultValue: false }
    ]
  },
  websearch: {
    name: 'Web Search',
    description: 'Advanced web search with LLM synthesis',
    icon: '⊕', color: '#ec4899', badge: 'fixed', mcp: [],
    defaultConfig: (providers) => ({ llm_provider: providers[0]?.name || 'ollama', llm_model: 'mistrallite:latest', llm_temperature: 0.5, search_config: { max_results: 10, language: 'en', safe_search: true, use_rag: false } }),
    mcpConfig: {}, requiredFields: [],
    executeFields: [
      { name: 'query', label: 'Search query', type: 'text', placeholder: 'What to search for...', required: true }
    ]
  },
  skill: {
    name: 'Skill Agent',
    description: 'Executes a registered .md skill (ssh_admin, winrm_admin, k8s_ops, postgres_ops…) on a remote host via SSH or WinRM',
    icon: '⌥', color: '#6366f1', badge: 'skill', mcp: ['ssh', 'winrm'],
    defaultConfig: (providers) => ({ mcp_servers: ['ssh'], llm_provider: providers[0]?.name || 'lmstudio', llm_model: 'openai/gpt-oss-20b', llm_temperature: 0.2, memory_scope: 'session+global' }),
    mcpConfig: {}, requiredFields: [], executeFields: []
  },
  gitea_code_generator: {
    name: 'Gitea Code Generator',
    description: 'Generate code, lint, commit and create PRs on a self-hosted Gitea repo via MCP Gitea + Linter',
    icon: '⟐', color: '#f97316', badge: 'fixed', mcp: ['gitea', 'linter'],
    defaultConfig: (providers) => ({ mcp_servers: ['gitea', 'linter'], llm_provider: providers[0]?.name || 'lmstudio', llm_model: 'openai/gpt-oss-20b', llm_temperature: 0.2, target_branch: 'ai-feature', base_branch: 'main', auto_test: false, auto_lint: true, auto_commit: true, auto_create_pr: false }),
    mcpConfig: { gitea: { url: '', token: '', repo: '' } },
    requiredFields: ['gitea.url', 'gitea.token', 'gitea.repo'],
    executeFields: [
      { name: 'prompt', label: 'Code generation prompt', type: 'textarea', placeholder: 'Add a health check endpoint /healthz returning JSON status…', required: true },
      { name: 'create_new_files', label: 'Create new files', type: 'checkbox', defaultValue: true },
      { name: 'test_mode', label: 'Test mode (dry-run, no commit)', type: 'checkbox', defaultValue: false }
    ]
  },
  datagouv_explorer: {
    name: 'DataGouv Explorer',
    description: 'Explore the data.gouv.fr catalogue — datasets, resources, organizations, DINUM topics',
    icon: '⊗', color: '#003189', badge: 'fixed', mcp: ['datagouv'],
    defaultConfig: (providers) => ({ mcp_servers: ['datagouv'], mode: 'search', analyze: false, page_size: 10, llm_provider: providers[0]?.name || 'lmstudio', llm_model: 'openai/gpt-oss-20b', llm_temperature: 0.2 }),
    mcpConfig: {}, requiredFields: [],
    executeFields: [
      { name: 'mode', label: 'Mode', type: 'select', required: true, options: [ { value: 'search', label: 'search — find datasets' }, { value: 'dataset', label: 'dataset — detail + resources' }, { value: 'organization', label: 'organization — search an org' }, { value: 'topic', label: 'topic — DINUM API v2 themes' } ], defaultValue: 'search' },
      { name: 'query', label: 'Query (modes search / organization)', type: 'text', placeholder: 'population par commune | INSEE | Météo France' },
      { name: 'dataset_id', label: 'Dataset ID or slug (mode dataset)', type: 'text', placeholder: 'population-legale-2021' },
      { name: 'topic_id', label: 'Topic slug (mode topic)', type: 'text', placeholder: 'annuaire-des-entreprises' },
      { name: 'org_id', label: 'Org slug (mode organization)', type: 'text', placeholder: 'direction-interministerielle-du-numerique' },
      { name: 'page_size', label: 'Page size', type: 'number', placeholder: '10' },
      { name: 'sort', label: 'Sort (search: -created | -last_update | views…)', type: 'text', placeholder: '-last_update' }
    ]
  }
};

// ─────────────────────────────────────────────────────────────────────────────
// DOC ENTRIES
// ─────────────────────────────────────────────────────────────────────────────
const DOC_ENTRIES = [
  {
    key: 'skill', icon: '⌥', title: 'Skill agents (SSH / WinRM / Ops)',
    desc: 'Register .md skills with a ## Mapping section. The "Command" field at execution must match a mapping entry. Skills: ssh_admin, winrm_admin, k8s_ops, postgres_ops, web_server_ops…',
    steps: [
      { n: 1, text: 'Register a .md skill via POST /api/skills/register with auto_create_agent=true. The skill_id in the frontmatter becomes the agent identifier.' },
      { n: 2, text: 'The "Command" field at execution = a phrase matching a line from ## Mapping in your .md. e.g. disk · restart nginx · pods · logs sshd · cleanup' },
      { n: 3, text: 'Host = select from the Hosts tab. Resolution uses GET /api/hosts/ — name or IP, protocol must match (ssh vs winrm).' },
      { n: 4, text: 'Skill ID is optional at execution — leave empty for auto semantic search, or set it explicitly to force e.g. k8s_ops vs ssh_admin on the same host.' }
    ]
  },
  {
    key: 'gitea_code_generator', icon: '⟐', title: 'Gitea Code Generator',
    desc: 'Fixed agent backed by MCP Gitea + Linter. Clones the repo, generates or modifies code, lints, commits to a feature branch, and optionally creates a PR.',
    steps: [
      { n: 1, text: 'Create the agent with mcp_config.gitea = { url, token, repo }. The token comes from Gitea → Settings → Applications.' },
      { n: 2, text: 'Set base_branch (default: main) and target_branch (default: ai-feature). The AI always works on target_branch, never on main.' },
      { n: 3, text: 'Execute with a prompt describing the change. Toggle auto_lint, auto_commit, auto_create_pr as needed.' },
      { n: 4, text: 'Use test_mode: true for a dry-run (generates code but does not commit).' }
    ]
  },
  {
    key: 'datagouv_explorer', icon: '⊗', title: 'DataGouv Explorer',
    desc: 'Fixed agent backed by MCP DataGouv. Supports 4 modes: search (datasets), dataset (detail + resources), organization (orgs), topic (DINUM API v2 themes).',
    steps: [
      { n: 1, text: 'mode=search + query → paginated dataset list. Supports sort (-created, -last_update, views…), tag and organization filters.' },
      { n: 2, text: 'mode=dataset + dataset_id (slug or ID) → full dataset info + download URLs for each resource.' },
      { n: 3, text: 'mode=organization + query (or org_id for direct fetch) → org info and dataset count.' },
      { n: 4, text: 'mode=topic (+ topic_id for a specific topic) → DINUM API v2 thematic groups. Leave topic_id empty to list all.' }
    ]
  },
  {
    key: 'reference', icon: '⌬', title: 'Agent types reference',
    desc: 'All agent_type keys, their badge (fixed / skill), MCP servers used and execute payload shape.',
    table: Object.entries(AGENT_TYPES).map(([key, t]) => ({ key, name: t.name, badge: t.badge, mcp: t.mcp.join(', ') || '—' }))
  }
];



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
    success: { bg: 'rgba(29,158,117,.15)', color: '#085041', dot: '#1D9E75' },
    failed:  { bg: 'rgba(226,75,74,.12)',  color: '#791F1F', dot: '#E24B4A' },
    running: { bg: 'rgba(96,165,250,.15)', color: '#185FA5', dot: '#60a5fa' },
    pending: { bg: 'rgba(136,135,128,.15)', color: '#5F5E5A', dot: '#888780' },
  }[s] || { bg: 'rgba(136,135,128,.15)', color: '#5F5E5A', dot: '#888780' });

  const getPromptLabel = (exec) => {
    const d = exec.input_data || {};
    return d.prompt || d.query || d.branch || d.mode || `#${exec.id?.slice(0, 8)}`;
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

// ─────────────────────────────────────────────────────────────────────────────
// SKILL EXECUTE FIELDS
// ─────────────────────────────────────────────────────────────────────────────
const SkillExecuteFields = ({ executeData, onChange, hosts }) => (
  <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-4)' }}>
    <div className="form-group">
      <label className="form-label">Command <span style={{ color: 'var(--danger)' }}>*</span></label>
      <input type="text" className="form-input" value={executeData.query || ''} onChange={e => onChange('query', e.target.value)} placeholder="disk | restart nginx | pods | logs sshd | cleanup" />
      <div style={{ marginTop: 'var(--spacing-2)', border: '1px solid var(--info)', borderLeft: '3px solid var(--info)', borderRadius: 'var(--radius)', padding: 'var(--spacing-2) var(--spacing-3)', backgroundColor: 'rgba(96,165,250,0.06)', fontSize: 'var(--text-xs)', color: 'var(--gray-700)', lineHeight: '1.6' }}>
        <strong style={{ color: 'var(--info)' }}>Command = a mapping entry from your .md skill file.</strong>{' '}
        This agent is already bound to its skill via <code style={{ background: 'var(--gray-200)', padding: '0 3px', borderRadius: '3px' }}>skill_id</code> set at creation.
        The backend resolves the command against the <code style={{ background: 'var(--gray-200)', padding: '0 3px', borderRadius: '3px' }}>## Mapping</code> section automatically.
      </div>
    </div>
    <div className="form-group">
      <label className="form-label">Target host <span style={{ color: 'var(--danger)' }}>*</span></label>
      <select className="form-input" value={executeData.host || ''} onChange={e => onChange('host', e.target.value)}>
        <option value="">— select a registered host —</option>
        {hosts.map(h => (
          <option key={h.id} value={h.name}>{h.name} — {h.host} ({h.protocol}){!h.is_active ? ' [inactive]' : ''}</option>
        ))}
      </select>
      <p style={{ fontSize: 'var(--text-xs)', color: 'var(--gray-600)', marginTop: '4px' }}>
        Loaded from <code style={{ fontSize: '11px', background: 'var(--gray-200)', padding: '0 3px', borderRadius: '3px' }}>GET /api/hosts/</code> — manage hosts in the Hosts tab
      </p>
    </div>
    <div className="form-group">
      <label className="form-label">Conversation ID <span style={{ color: 'var(--gray-500)', fontSize: 'var(--text-xs)' }}>(optional — cross-turn memory)</span></label>
      <input type="text" className="form-input" value={executeData.conversation_id || ''} onChange={e => onChange('conversation_id', e.target.value)} placeholder="uuid — leave empty for a new session" />
    </div>
  </div>
);

// ─────────────────────────────────────────────────────────────────────────────
// REGISTER SKILL MODAL
// ─────────────────────────────────────────────────────────────────────────────
const RegisterSkillModal = ({ onClose, onSuccess, providers }) => {
  const [mode, setMode] = useState('file');
  const [mdFile, setMdFile] = useState(null);
  const [mdContent, setMdContent] = useState('');
  const [autoCreate, setAutoCreate] = useState(true);
  const [llmProvider, setLlmProvider] = useState(providers[0]?.name || 'lmstudio');
  const [llmModel, setLlmModel] = useState('openai/gpt-oss-20b');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);

  const handleSubmit = async () => {
    setError(null);
    if (mode === 'file' && !mdFile) { setError('Select a .md file'); return; }
    if (mode === 'paste' && !mdContent.trim()) { setError('Paste your .md content'); return; }
    const formData = new FormData();
    if (mode === 'file') formData.append('file', mdFile);
    else formData.append('md_content', mdContent);
    formData.append('auto_create_agent', autoCreate ? 'true' : 'false');
    if (autoCreate) { formData.append('llm_provider', llmProvider); formData.append('llm_model', llmModel); }
    setLoading(true);
    try {
      const res = await api.post('/api/skills/register', formData, { headers: { 'Content-Type': 'multipart/form-data' } });
      setResult(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Registration failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.65)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, padding: 'var(--spacing-4)' }}>
      <div className="card" style={{ width: '100%', maxWidth: '620px', maxHeight: '90vh', overflow: 'auto' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--spacing-4)' }}>
          <div>
            <h2 style={{ fontSize: 'var(--text-xl)', fontWeight: '600' }}>Register skill</h2>
            <p style={{ fontSize: 'var(--text-sm)', color: 'var(--gray-600)', marginTop: '2px' }}>Upload a <code style={{ fontSize: '11px', background: 'var(--gray-200)', padding: '0 3px', borderRadius: '3px' }}>.md</code> skill file</p>
          </div>
          <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--gray-600)', fontSize: '1.25rem' }}>✕</button>
        </div>

        {!result ? (
          <>
            {error && <Alert type="error" style={{ marginBottom: 'var(--spacing-4)' }} onClose={() => setError(null)}>{error}</Alert>}
            <div style={{ display: 'flex', gap: 'var(--spacing-2)', marginBottom: 'var(--spacing-4)' }}>
              {[{ k: 'file', l: '📎 Upload file' }, { k: 'paste', l: 'Paste content' }].map(({ k, l }) => (
                <button key={k} onClick={() => setMode(k)} style={{ padding: 'var(--spacing-2) var(--spacing-4)', borderRadius: 'var(--radius)', border: mode === k ? '1px solid var(--primary)' : '1px solid var(--gray-300)', background: mode === k ? 'rgba(96,165,250,.1)' : 'var(--gray-100)', color: mode === k ? 'var(--primary)' : 'var(--gray-700)', fontWeight: mode === k ? '600' : '400', cursor: 'pointer', fontSize: 'var(--text-sm)' }}>{l}</button>
              ))}
            </div>
            {mode === 'file' && (
              <div className="form-group" style={{ marginBottom: 'var(--spacing-4)' }}>
                <label className="form-label">.md skill file *</label>
                <input type="file" accept=".md,text/markdown" className="form-input" onChange={e => setMdFile(e.target.files[0])} style={{ padding: 'var(--spacing-2)' }} />
                {mdFile && <p style={{ fontSize: 'var(--text-xs)', color: 'var(--gray-600)', marginTop: '4px' }}>Selected: <strong>{mdFile.name}</strong> ({(mdFile.size / 1024).toFixed(1)} KB)</p>}
              </div>
            )}
            {mode === 'paste' && (
              <div className="form-group" style={{ marginBottom: 'var(--spacing-4)' }}>
                <label className="form-label">.md content *</label>
                <textarea className="form-input" rows={12} value={mdContent} onChange={e => setMdContent(e.target.value)} placeholder={'---\nskill_id: my_skill\n...\n---\n## Mapping\n- disk  → df -h'} style={{ fontFamily: 'var(--font-mono)', fontSize: '12px' }} />
              </div>
            )}
            <div style={{ padding: 'var(--spacing-4)', backgroundColor: 'var(--gray-100)', borderRadius: 'var(--radius)', marginBottom: 'var(--spacing-4)' }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-2)', cursor: 'pointer', marginBottom: 'var(--spacing-3)' }}>
                <input type="checkbox" checked={autoCreate} onChange={e => setAutoCreate(e.target.checked)} />
                <span style={{ fontWeight: '600', fontSize: 'var(--text-sm)' }}>Auto-create agent</span>
                <span style={{ fontSize: 'var(--text-xs)', color: 'var(--gray-600)' }}>(creates skill + agent in one call)</span>
              </label>
              {autoCreate && (
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--spacing-3)' }}>
                  <div className="form-group"><label className="form-label">LLM provider</label><select className="form-input" value={llmProvider} onChange={e => setLlmProvider(e.target.value)}>{providers.map(p => <option key={p.name} value={p.name}>{p.name}</option>)}</select></div>
                  <div className="form-group"><label className="form-label">LLM model</label><input type="text" className="form-input" value={llmModel} onChange={e => setLlmModel(e.target.value)} /></div>
                </div>
              )}
            </div>
            <div style={{ display: 'flex', gap: 'var(--spacing-3)', justifyContent: 'flex-end', paddingTop: 'var(--spacing-4)', borderTop: '1px solid var(--gray-200)' }}>
              <Button variant="ghost" onClick={onClose} disabled={loading}>Cancel</Button>
              <Button variant="primary" onClick={handleSubmit} disabled={loading}>{loading ? 'Registering…' : '⬆ Register skill'}</Button>
            </div>
          </>
        ) : (
          <div>
            <div style={{ padding: 'var(--spacing-4)', border: '1px solid var(--success)', borderLeft: '3px solid var(--success)', borderRadius: 'var(--radius)', backgroundColor: 'rgba(52,211,153,.08)', marginBottom: 'var(--spacing-4)' }}>
              <p style={{ fontWeight: '600', color: 'var(--success-dark)', marginBottom: 'var(--spacing-2)' }}>✓ Skill registered successfully</p>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--spacing-2)', fontSize: 'var(--text-sm)' }}>
                <div><span style={{ color: 'var(--gray-600)' }}>skill_id</span><br /><code style={{ fontFamily: 'monospace', fontWeight: '600' }}>{result.skill_id}</code></div>
                {result.agent_id && <div><span style={{ color: 'var(--gray-600)' }}>agent_id</span><br /><code style={{ fontFamily: 'monospace', fontSize: '11px' }}>{result.agent_id}</code></div>}
              </div>
              {result.message && <p style={{ marginTop: 'var(--spacing-2)', fontSize: 'var(--text-sm)', color: 'var(--gray-700)' }}>{result.message}</p>}
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
              <Button variant="primary" onClick={() => { onSuccess?.(); onClose(); }}>Done</Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};


// ─────────────────────────────────────────────────────────────────────────────
// EMBEDDED CHAT — panneau droit post-exécution
// ─────────────────────────────────────────────────────────────────────────────
const EmbeddedChat = ({ conversationId, agentName }) => {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [streaming, setStreaming] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(true);
  const [copiedIndex, setCopiedIndex] = useState(null);
  const [chatSettings, setChatSettings] = useState({ provider_name: 'ollama', model: 'llama2', temperature: 0.7, reasoning_mode: 'standard' });
  const messagesEndRef = useRef(null);
  const streamingServiceRef = useRef(new StreamingService());

  useEffect(() => {
    if (!conversationId) return;
    (async () => {
      try {
        setLoadingHistory(true);
        const res = await api.get(`/api/conversations/${conversationId}`);
        const conv = res.data;
        setMessages(conv.messages || []);
        setChatSettings(prev => ({
          ...prev,
          provider_name: conv.provider_name || prev.provider_name,
          model: conv.model || prev.model,
          temperature: conv.temperature || prev.temperature,
        }));
      } catch (e) {
        console.error('Failed to load agent conversation:', e);
      } finally {
        setLoadingHistory(false);
      }
    })();
  }, [conversationId]);

  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);

  const appendChunk = (chunk) => {
    setMessages(prev => {
      const updated = [...prev];
      updated[updated.length - 1] = {
        ...updated[updated.length - 1],
        content: updated[updated.length - 1].content + chunk
      };
      return updated;
    });
  };

  const handleSend = async () => {
    if (!input.trim() || streaming || !conversationId) return;
    const content = input.trim();
    setInput('');
    setMessages(prev => [
      ...prev,
      { role: 'user', content, created_at: new Date().toISOString() },
      { role: 'assistant', content: '', created_at: new Date().toISOString() }
    ]);
    setStreaming(true);
    const request = { message: content, conversation_id: conversationId, ...chatSettings };
    await streamingServiceRef.current.startSSEStream(
      request,
      appendChunk,
      (err) => {
        console.error('Chat stream error:', err);
        setStreaming(false);
        streamingServiceRef.current.startWebSocketStream(request, appendChunk, () => setStreaming(false), () => setStreaming(false));
      },
      () => setStreaming(false)
    );
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); }
  };

  const handleCopy = async (content, idx) => {
    await navigator.clipboard.writeText(content).catch(() => {});
    setCopiedIndex(idx);
    setTimeout(() => setCopiedIndex(null), 2000);
  };

  if (loadingHistory) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--gray-500)', gap: 'var(--spacing-2)' }}>
        <Loader2 size={18} className="animate-spin" />
        <span style={{ fontSize: 'var(--text-sm)' }}>Loading conversation…</span>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Header */}
      <div style={{ padding: 'var(--spacing-3) var(--spacing-4)', borderBottom: '1px solid var(--gray-200)', backgroundColor: 'var(--gray-50)', flexShrink: 0 }}>
        <div style={{ fontSize: 'var(--text-sm)', fontWeight: '600', color: 'var(--gray-800)' }}>
          💬 Continue with {agentName}
        </div>
        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--gray-500)', marginTop: '2px' }}>
          {chatSettings.provider_name} · {chatSettings.model}
        </div>
      </div>

      {/* Messages */}
      <div style={{ flex: 1, overflowY: 'auto', padding: 'var(--spacing-3)', display: 'flex', flexDirection: 'column', gap: 'var(--spacing-3)' }}>
        {messages.length === 0 && (
          <div style={{ textAlign: 'center', color: 'var(--gray-400)', fontSize: 'var(--text-sm)', marginTop: 'var(--spacing-8)' }}>
            No messages yet — ask a follow-up question
          </div>
        )}
        {messages.map((msg, idx) => (
          <div
            key={idx}
            style={{ display: 'flex', gap: 'var(--spacing-2)', alignItems: 'flex-start', flexDirection: msg.role === 'user' ? 'row-reverse' : 'row' }}
          >
            <div style={{
              width: '28px', height: '28px', borderRadius: '50%', flexShrink: 0,
              background: msg.role === 'user' ? 'var(--primary)' : 'var(--gray-200)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              color: msg.role === 'user' ? 'white' : 'var(--gray-600)'
            }}>
              {msg.role === 'user' ? <User size={14} /> : <Bot size={14} />}
            </div>
            <div
              style={{ maxWidth: '80%' }}
              onMouseEnter={e => { const a = e.currentTarget.querySelector('.msg-actions'); if (a) a.style.opacity = '1'; }}
              onMouseLeave={e => { const a = e.currentTarget.querySelector('.msg-actions'); if (a) a.style.opacity = '0'; }}
            >
              <div style={{
                padding: 'var(--spacing-2) var(--spacing-3)',
                borderRadius: 'var(--radius)',
                background: msg.role === 'user' ? 'var(--primary)' : 'var(--gray-100)',
                color: msg.role === 'user' ? 'white' : 'var(--gray-900)',
                fontSize: 'var(--text-sm)', lineHeight: '1.6'
              }}>
                {msg.content
                  ? <MarkdownMessage content={msg.content} isStreaming={streaming && idx === messages.length - 1} />
                  : <Loader2 size={14} className="animate-spin" style={{ color: 'var(--gray-400)' }} />
                }
              </div>
              {msg.content && !(streaming && idx === messages.length - 1) && (
                <div className="msg-actions" style={{
                  opacity: 0, transition: 'opacity 0.15s', marginTop: '4px',
                  display: 'flex', justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start'
                }}>
                  <button
                    onClick={() => handleCopy(msg.content, idx)}
                    style={{ display: 'flex', alignItems: 'center', gap: '3px', padding: '2px 6px', fontSize: '11px', color: copiedIndex === idx ? 'var(--success)' : 'var(--gray-500)', background: 'var(--gray-100)', border: '1px solid var(--gray-200)', borderRadius: 'var(--radius-sm)', cursor: 'pointer' }}
                  >
                    {copiedIndex === idx ? <Check size={11} /> : <Copy size={11} />}
                    {copiedIndex === idx ? 'Copied' : 'Copy'}
                  </button>
                </div>
              )}
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div style={{ padding: 'var(--spacing-3)', borderTop: '1px solid var(--gray-200)', flexShrink: 0 }}>
        <div style={{ display: 'flex', gap: 'var(--spacing-2)', alignItems: 'flex-end', border: '1px solid var(--gray-300)', borderRadius: 'var(--radius)', padding: 'var(--spacing-2) var(--spacing-3)', background: 'var(--bg)' }}>
          <textarea
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={streaming}
            placeholder="Ask a follow-up question…"
            rows={1}
            style={{ flex: 1, border: 'none', outline: 'none', background: 'transparent', resize: 'none', fontSize: 'var(--text-sm)', lineHeight: '1.5', maxHeight: '120px', padding: 0 }}
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || streaming}
            style={{ background: 'var(--primary)', border: 'none', borderRadius: 'var(--radius-sm)', padding: '6px 10px', color: 'white', cursor: input.trim() && !streaming ? 'pointer' : 'not-allowed', opacity: input.trim() && !streaming ? 1 : 0.4, display: 'flex', alignItems: 'center' }}
          >
            {streaming ? <Loader2 size={15} className="animate-spin" /> : <Send size={15} />}
          </button>
        </div>
        <div style={{ fontSize: '11px', color: 'var(--gray-400)', marginTop: '4px', textAlign: 'center' }}>
          {streaming ? 'Thinking…' : 'Enter to send · Shift+Enter for new line'}
        </div>
      </div>
    </div>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// EXECUTE MODAL — SSE stream + split panel post-exécution
// ─────────────────────────────────────────────────────────────────────────────
const ExecuteAgentModal = ({ agent, agentType, onClose, onExecuted, hosts, skills, preloadExec }) => {
  const navigate = useNavigate();
  const [executeData, setExecuteData] = useState({});
  const [error, setError] = useState(null);
  const [phase, setPhase] = useState('idle'); // idle | running | done | failed
  const [steps, setSteps] = useState([]);
  const [outputText, setOutputText] = useState('');
  const [conversationId, setConversationId] = useState(null);
  const [logsExpanded, setLogsExpanded] = useState(false);
  const [activeLeftTab, setActiveLeftTab] = useState('output'); // 'output' | 'history'
  const [panelExecutions, setPanelExecutions] = useState([]);
  const [panelExecLoading, setPanelExecLoading] = useState(false);
  const outputRef = useRef(null);
  const readerRef = useRef(null);

  useEffect(() => {
    const defaults = {};
    agentType?.executeFields?.forEach(f => {
      if (f.defaultValue !== undefined) defaults[f.name] = f.defaultValue;
    });
    setExecuteData(defaults);
  }, [agentType]);

  useEffect(() => {
    if (outputRef.current) outputRef.current.scrollTop = outputRef.current.scrollHeight;
  }, [outputText]);

  useEffect(() => () => { readerRef.current?.cancel().catch(() => {}); }, []);

  // Préchargement depuis l'historique (cas slide-in → popup)
  useEffect(() => {
    if (!preloadExec) return;
    const convId = preloadExec.input_data?.conversation_id || preloadExec.output_data?.conversation_id;
    const out = preloadExec.output_data;
    const text = (out && typeof out === 'object')
      ? (out.content || out.result || out.output || out.summary || out.text || JSON.stringify(out, null, 2))
      : (typeof out === 'string' ? out : '');
    setConversationId(convId || null);
    setOutputText(text);
    setPhase('done');
    setActiveLeftTab('output');
    setSteps([]);
  }, [preloadExec]);

  useEffect(() => {
    if (activeLeftTab !== 'history') return;
    (async () => {
      setPanelExecLoading(true);
      try {
        const res = await api.get(`/api/agents/${agent.id}/executions?limit=30`);
        setPanelExecutions(res.data);
      } catch (_) {}
      finally { setPanelExecLoading(false); }
    })();
  }, [activeLeftTab, agent.id]);

  const handleChange = (name, value) => setExecuteData(prev => ({ ...prev, [name]: value }));

  const buildInputData = () => {
    const d = executeData;
    if (agent.agent_type === 'skill') {
      const r = { query: d.query, host: d.host };
      if (d.skill_id) r.skill_id = d.skill_id;
      if (d.conversation_id) r.conversation_id = d.conversation_id;
      return r;
    }
    if (agent.agent_type === 'code_generator') {
      return { prompt: d.prompt, create_new_files: d.create_new_files ?? true, test_mode: d.test_mode ?? true };
    }
    if (agent.agent_type === 'branch_code_review') return { branch: d.branch };
    if (agent.agent_type === 'legal_fiscal') {
      const r = { mode: d.mode, query: d.query };
      if (d.documents) r.documents = d.documents.split(',').map(x => x.trim()).filter(Boolean);
      return r;
    }
    if (agent.agent_type === 'accounting_finance') return { mode: d.mode, query: d.query };
    if (agent.agent_type === 'travel_expert') return { mode: d.mode || 'itinerary_planning', query: d.query };
    if (agent.agent_type === 'email_expert') {
      const r = { mode: d.mode };
      if (d.mode === 'send_email') { r.to = d.to; r.subject = d.subject; r.body = d.body; }
      else if (d.mode === 'send_email_llm') { r.to = d.to; r.subject = d.subject; r.instructions = d.instructions; r.context = d.context; r.auto_send = d.auto_send ?? false; }
      else if (d.mode === 'analyze_inbox') { r.limit = parseInt(d.limit) || 20; r.unread_only = d.unread_only ?? true; }
      return r;
    }
    if (agent.agent_type === 'websearch') return { query: d.query };
    if (agent.agent_type === 'gitea_code_generator') {
      return { prompt: d.prompt, create_new_files: d.create_new_files ?? true, test_mode: d.test_mode ?? false };
    }
    if (agent.agent_type === 'datagouv_explorer') {
      const r = { mode: d.mode || 'search' };
      if (d.query) r.query = d.query;
      if (d.dataset_id) r.dataset_id = d.dataset_id;
      if (d.topic_id) r.topic_id = d.topic_id;
      if (d.org_id) r.org_id = d.org_id;
      if (d.page_size) r.page_size = parseInt(d.page_size);
      if (d.sort) r.sort = d.sort;
      return r;
    }
    return {};
  };

  const validate = () => {
    if (agent.agent_type === 'skill') {
      if (!executeData.query?.trim()) { setError('Command is required'); return false; }
      if (!executeData.host) { setError('Target host is required'); return false; }
      return true;
    }
    const required = agentType?.executeFields?.filter(f => f.required) || [];
    for (const f of required) {
      if (!executeData[f.name]) { setError(`"${f.label}" is required`); return false; }
    }
    return true;
  };

  const extractContent = (data) => {
    if (!data) return '';
    if (typeof data === 'string') return data;
    return data.content || data.result || data.output || data.summary || data.text
      || (data.data && extractContent(data.data)) || '';
  };

  const addStep = (type, message) => setSteps(prev => [...prev, { type, message, ts: new Date().toLocaleTimeString() }]);

  const handleSubmit = async () => {
    if (!validate()) return;
    setError(null);
    setPhase('running');
    setSteps([]);
    setOutputText('');
    setConversationId(null);

    const token = localStorage.getItem('access_token');
    try {
      const response = await fetch(`/api/agents/${agent.id}/execute/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {})
        },
        body: JSON.stringify({ input_data: buildInputData(), trigger: 'manual' })
      });

      if (!response.ok) {
        const e = await response.json().catch(() => ({}));
        throw new Error(e.detail || `HTTP ${response.status}`);
      }

      const reader = response.body.getReader();
      readerRef.current = reader;
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
              setConversationId(data.conversation_id);
              addStep('init', '🚀 Execution started');
            } else if (eventType === 'log' || eventType === 'progress') {
              const msg = data.data?.message || data.message || data.data?.step || '';
              if (msg) addStep(eventType, msg);
            } else if (eventType === 'result') {
              const c = extractContent(data);
              if (c) setOutputText(prev => prev + (prev ? '\n\n' : '') + c);
              addStep('result', '✅ Result received');
            } else if (eventType === 'done') {
              setConversationId(prev => prev || data.conversation_id);
              const c = extractContent(data.output);
              if (c) setOutputText(prev => prev || c);
              setPhase('done');
              if (onExecuted) onExecuted();
            } else if (eventType === 'error') {
              throw new Error(data.error || 'Agent execution failed');
            }
          } catch (pe) {
            if (!pe.message?.includes('JSON')) throw pe;
          }
        }
      }
      setPhase(prev => prev === 'running' ? 'done' : prev);

    } catch (err) {
      setError(err.message || 'Execution failed');
      setPhase('failed');
    }
  };

  const renderField = (field) => {
    const value = executeData[field.name] ?? '';
    switch (field.type) {
      case 'textarea':
        return <textarea className="form-input" value={value} onChange={e => handleChange(field.name, e.target.value)} placeholder={field.placeholder} rows={4} />;
      case 'checkbox':
        return (
          <label style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-2)', cursor: 'pointer' }}>
            <input type="checkbox" checked={!!value} onChange={e => handleChange(field.name, e.target.checked)} />
            <span style={{ fontSize: 'var(--text-sm)' }}>{field.label}</span>
          </label>
        );
      case 'select':
        return (
          <select className="form-input" value={value} onChange={e => handleChange(field.name, e.target.value)}>
            <option value="">Select {field.label}</option>
            {field.options?.map(opt => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
          </select>
        );
      case 'number':
        return <input type="number" className="form-input" value={value} onChange={e => handleChange(field.name, e.target.value)} placeholder={field.placeholder} />;
      default:
        return <input type="text" className="form-input" value={value} onChange={e => handleChange(field.name, e.target.value)} placeholder={field.placeholder} />;
    }
  };

  const isSkill = agent.agent_type === 'skill';
  const emailMode = executeData.mode;
  const emailConditional = ['to', 'subject', 'body', 'instructions', 'context', 'limit', 'unread_only', 'auto_send'];
  const stepColor = { init: 'var(--info)', log: 'var(--gray-500)', progress: 'var(--primary)', result: 'var(--success)', error: 'var(--error)' };

  // ── IDLE : modal compacte identique à l'original ──────────────────────────
  if (phase === 'idle') {
    return (
      <div style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.65)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, padding: 'var(--spacing-4)' }}>
        <div className="card" style={{ width: '100%', maxWidth: '680px', maxHeight: '90vh', overflow: 'auto' }}>

          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 'var(--spacing-4)' }}>
            <div>
              <h2 style={{ fontSize: 'var(--text-xl)', fontWeight: '600', marginBottom: 'var(--spacing-1)' }}>
                Execute — {agent.name}
              </h2>
              <p style={{ fontSize: 'var(--text-sm)', color: 'var(--gray-600)' }}>
                {agentType?.name} · {agentType?.mcp?.join(', ') || 'no MCP'}
              </p>
            </div>
            <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--gray-600)', fontSize: '1.25rem', lineHeight: 1 }}>✕</button>
          </div>

          {error && <Alert type="error" style={{ marginBottom: 'var(--spacing-4)' }} onClose={() => setError(null)}>{error}</Alert>}

          {isSkill ? (
            <SkillExecuteFields executeData={executeData} onChange={handleChange} hosts={hosts} />
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-4)' }}>
              {agentType?.executeFields?.map(field => {
                if (emailConditional.includes(field.name) && agent.agent_type === 'email_expert') {
                  if (!emailMode) return null;
                  if (emailMode === 'send_email' && !['to', 'subject', 'body'].includes(field.name)) return null;
                  if (emailMode === 'send_email_llm' && !['to', 'subject', 'instructions', 'context', 'auto_send'].includes(field.name)) return null;
                  if (emailMode === 'analyze_inbox' && !['limit', 'unread_only'].includes(field.name)) return null;
                }
                return (
                  <div key={field.name} className="form-group">
                    {field.type !== 'checkbox' && <label className="form-label">{field.label}{field.required && ' *'}</label>}
                    {renderField(field)}
                  </div>
                );
              })}
            </div>
          )}

          <div style={{ display: 'flex', gap: 'var(--spacing-3)', justifyContent: 'flex-end', marginTop: 'var(--spacing-6)', paddingTop: 'var(--spacing-4)', borderTop: '1px solid var(--gray-300)' }}>
            <Button variant="ghost" onClick={onClose}>Cancel</Button>
            <Button variant="primary" onClick={handleSubmit}>▶ Execute agent</Button>
          </div>
        </div>
      </div>
    );
  }

  // ── RUNNING / DONE / FAILED : fullscreen split 50/50 ─────────────────────
  return (
    <div style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.78)', display: 'flex', alignItems: 'stretch', justifyContent: 'center', zIndex: 1000, padding: 'var(--spacing-5)' }}>
      <div style={{ width: '100%', maxWidth: '1280px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--spacing-4)', height: '100%' }}>

        {/* ── Panneau gauche : output terminal ── */}
        <div className="card" style={{ display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--spacing-3)', flexShrink: 0 }}>
            <div>
              <h2 style={{ fontSize: 'var(--text-lg)', fontWeight: '600', marginBottom: '2px' }}>
                {agentType?.icon} {agent.name}
              </h2>
              <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-2)', fontSize: 'var(--text-xs)' }}>
                {phase === 'running' && (
                  <><span style={{ width: '7px', height: '7px', borderRadius: '50%', background: '#f59e0b', display: 'inline-block', animation: 'pulse 1s infinite' }} />Running…</>
                )}
                {phase === 'done' && (
                  <><span style={{ width: '7px', height: '7px', borderRadius: '50%', background: 'var(--success)', display: 'inline-block' }} /><span style={{ color: 'var(--success)', fontWeight: '600' }}>Completed</span></>
                )}
                {phase === 'failed' && (
                  <><span style={{ width: '7px', height: '7px', borderRadius: '50%', background: 'var(--error)', display: 'inline-block' }} /><span style={{ color: 'var(--error)', fontWeight: '600' }}>Failed</span></>
                )}
              </div>
            </div>
            <button
              onClick={onClose}
              disabled={phase === 'running'}
              style={{ background: 'none', border: 'none', cursor: phase === 'running' ? 'not-allowed' : 'pointer', color: 'var(--gray-400)', fontSize: '1.1rem', opacity: phase === 'running' ? 0.3 : 1 }}
            >✕</button>
          </div>

          {error && <Alert type="error" style={{ marginBottom: 'var(--spacing-3)', flexShrink: 0 }}>{error}</Alert>}

          {/* Onglets Output / History */}
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', border: '1px solid #1e293b', borderRadius: 'var(--radius)', overflow: 'hidden', marginBottom: 'var(--spacing-3)' }}>
            {/* Tab bar */}
            <div style={{ display: 'flex', background: '#1e293b', borderBottom: '1px solid #334155', flexShrink: 0 }}>
              {[
                { key: 'output', label: 'Output', icon: <span style={{ width: '10px', height: '10px', borderRadius: '50%', background: phase === 'running' ? '#f59e0b' : phase === 'done' ? '#22c55e' : '#ef4444', display: 'inline-block', marginRight: '6px' }} /> },
                { key: 'history', label: 'History', icon: <History size={12} style={{ marginRight: '5px', verticalAlign: '-1px' }} /> }
              ].map(tab => (
                <button key={tab.key} onClick={() => setActiveLeftTab(tab.key)} style={{
                  padding: '6px 14px', background: 'none', border: 'none',
                  borderBottom: activeLeftTab === tab.key ? '2px solid #60a5fa' : '2px solid transparent',
                  color: activeLeftTab === tab.key ? '#e2e8f0' : '#64748b',
                  fontSize: '12px', cursor: 'pointer', display: 'flex', alignItems: 'center',
                  fontWeight: activeLeftTab === tab.key ? '600' : '400'
                }}>
                  {tab.icon}{tab.label}
                  {tab.key === 'history' && panelExecutions.length > 0 && (
                    <span style={{ marginLeft: '5px', fontSize: '10px', background: '#334155', color: '#94a3b8', borderRadius: '99px', padding: '1px 5px' }}>
                      {panelExecutions.length}
                    </span>
                  )}
                </button>
              ))}
            </div>

            {/* Output tab */}
            {activeLeftTab === 'output' && (
              <div ref={outputRef} style={{ flex: 1, overflowY: 'auto', padding: 'var(--spacing-3)', fontFamily: 'monospace', fontSize: '13px', lineHeight: '1.7', whiteSpace: 'pre-wrap', wordBreak: 'break-word', background: '#0f172a', color: '#e2e8f0' }}>
                {outputText || <span style={{ color: '#475569' }}>{phase === 'running' ? 'Waiting for output…' : 'No output captured.'}</span>}
                {phase === 'running' && <span style={{ color: '#60a5fa', animation: 'pulse 1s infinite' }}>▋</span>}
              </div>
            )}

            {/* History tab */}
            {activeLeftTab === 'history' && (
              <div style={{ flex: 1, overflowY: 'auto', background: 'var(--bg-card)' }}>
                {panelExecLoading && (
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 'var(--spacing-8)', gap: 'var(--spacing-2)', color: 'var(--gray-500)' }}>
                    <Loader2 size={15} className="animate-spin" /> Loading…
                  </div>
                )}
                {!panelExecLoading && panelExecutions.length === 0 && (
                  <div style={{ textAlign: 'center', padding: 'var(--spacing-8)', color: 'var(--gray-500)', fontSize: 'var(--text-sm)' }}>No executions yet</div>
                )}
                {!panelExecLoading && panelExecutions.map((exec) => {
                  const stMap = { success: { bg: 'rgba(29,158,117,.15)', color: '#085041', dot: '#1D9E75' }, failed: { bg: 'rgba(226,75,74,.12)', color: '#791F1F', dot: '#E24B4A' }, running: { bg: 'rgba(96,165,250,.15)', color: '#185FA5', dot: '#60a5fa' } };
                  const st = stMap[exec.status] || { bg: 'rgba(136,135,128,.15)', color: '#5F5E5A', dot: '#888780' };
                  const eOut = exec.output_data;
                  const convId = exec.input_data?.conversation_id
                    || (typeof eOut === 'object' && eOut !== null && (eOut.conversation_id || eOut.data?.conversation_id))
                    || null;
                  const label = (exec.input_data?.prompt || exec.input_data?.query || exec.input_data?.branch || exec.input_data?.mode || `#${exec.id?.slice(0, 8)}`);
                  const dur = exec.execution_time_ms ? (exec.execution_time_ms < 60000 ? `${Math.round(exec.execution_time_ms / 1000)}s` : `${Math.floor(exec.execution_time_ms / 60000)}m ${Math.round((exec.execution_time_ms % 60000) / 1000)}s`) : '';
                  const dt = exec.started_at ? new Date(exec.started_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '';
                  return (
                    <div key={exec.id} style={{ padding: '9px 14px', borderBottom: '1px solid var(--gray-200)', display: 'grid', gridTemplateColumns: '8px 1fr auto auto', gap: '9px', alignItems: 'center' }}>
                      <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: st.dot, display: 'inline-block', flexShrink: 0 }} />
                      <div style={{ minWidth: 0 }}>
                        <div style={{ fontSize: '12px', fontWeight: '500', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', color: 'var(--gray-900)' }}>{label}</div>
                        <div style={{ fontSize: '11px', color: 'var(--gray-500)', marginTop: '1px' }}>{dt}{dur ? ` · ${dur}` : ''}{exec.tokens_used ? ` · ${exec.tokens_used.toLocaleString()} tok` : ''}</div>
                      </div>
                      <span style={{ fontSize: '10px', fontWeight: '600', padding: '1px 7px', borderRadius: '99px', background: st.bg, color: st.color, flexShrink: 0 }}>{exec.status}</span>
                      <button
                        title={convId ? 'Load this run' : 'No conversation'}
                        disabled={!convId}
                        onClick={() => {
                          if (!convId) return;
                          const text = (eOut && typeof eOut === 'object')
                            ? (eOut.content || eOut.result || eOut.output || eOut.summary || eOut.text || JSON.stringify(eOut, null, 2))
                            : (typeof eOut === 'string' ? eOut : '');
                          setConversationId(convId);
                          setOutputText(text);
                          setPhase('done');
                          setActiveLeftTab('output');
                          setSteps([]);
                        }}
                        style={{ background: 'none', border: 'none', cursor: convId ? 'pointer' : 'not-allowed', color: 'var(--gray-500)', opacity: convId ? 1 : 0.3, padding: '3px', display: 'flex', alignItems: 'center' }}
                      >
                        <ExternalLink size={14} />
                      </button>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Logs accordion */}
          {steps.length > 0 && (
            <div style={{ border: '1px solid var(--gray-200)', borderRadius: 'var(--radius)', overflow: 'hidden', flexShrink: 0, marginBottom: 'var(--spacing-3)' }}>
              <button
                onClick={() => setLogsExpanded(p => !p)}
                style={{ width: '100%', display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 12px', background: 'var(--gray-50)', border: 'none', borderBottom: logsExpanded ? '1px solid var(--gray-200)' : 'none', cursor: 'pointer', fontSize: '12px', color: 'var(--gray-600)', fontWeight: '600' }}
              >
                <span>Execution logs ({steps.length})</span>
                {logsExpanded ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
              </button>
              {logsExpanded && (
                <div style={{ maxHeight: '140px', overflowY: 'auto', padding: '8px 12px', display: 'flex', flexDirection: 'column', gap: '3px' }}>
                  {steps.map((s, i) => (
                    <div key={i} style={{ display: 'flex', gap: '8px', fontSize: '11px' }}>
                      <span style={{ color: 'var(--gray-400)', flexShrink: 0, fontFamily: 'monospace' }}>{s.ts}</span>
                      <span style={{ color: stepColor[s.type] || 'var(--gray-600)', wordBreak: 'break-word' }}>{s.message}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Footer actions */}
          <div style={{ display: 'flex', gap: 'var(--spacing-2)', justifyContent: 'flex-end', flexShrink: 0 }}>
            {(phase === 'done' || phase === 'failed') && (
              <Button variant="ghost" size="sm" onClick={() => { setPhase('idle'); setError(null); setSteps([]); setOutputText(''); setConversationId(null); }}>
                Run Again
              </Button>
            )}
            {phase === 'done' && conversationId && (
              <Button variant="ghost" size="sm" icon={ExternalLink} onClick={() => navigate(`/chat/${conversationId}`)}>
                Full Chat
              </Button>
            )}
            <Button variant="ghost" size="sm" onClick={onClose} disabled={phase === 'running'}>
              {phase === 'running' ? 'Running…' : 'Close'}
            </Button>
          </div>
        </div>

        {/* ── Panneau droit : chat embarqué ── */}
        <div className="card" style={{ display: 'flex', flexDirection: 'column', overflow: 'hidden', padding: 0 }}>
          {phase === 'running' ? (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', gap: 'var(--spacing-3)', padding: 'var(--spacing-6)' }}>
              <Loader2 size={32} className="animate-spin" style={{ color: 'var(--primary)' }} />
              <p style={{ fontSize: 'var(--text-sm)', color: 'var(--gray-500)', textAlign: 'center' }}>
                Chat will be available once the agent completes
              </p>
            </div>
          ) : conversationId ? (
            <EmbeddedChat conversationId={conversationId} agentName={agent.name} />
          ) : (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--gray-400)', fontSize: 'var(--text-sm)' }}>
              No conversation linked to this execution
            </div>
          )}
        </div>

      </div>
    </div>
  );
};



// ─────────────────────────────────────────────────────────────────────────────
// HOSTS TAB
// ─────────────────────────────────────────────────────────────────────────────
const HostsTab = ({ hosts, onRefresh }) => {
  const [showAddModal, setShowAddModal] = useState(false);
  const [editHost, setEditHost] = useState(null);
  const [testResults, setTestResults] = useState({});
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [form, setForm] = useState({ name: '', protocol: 'ssh', host: '', port: '', username: '', credential_type: 'key', password: '', key_content: '', key_passphrase: '', winrm_transport: 'ntlm', winrm_server_cert_validation: 'ignore', tags: '', notes: '' });

  const resetForm = () => setForm({ name: '', protocol: 'ssh', host: '', port: '', username: '', credential_type: 'key', password: '', key_content: '', key_passphrase: '', winrm_transport: 'ntlm', winrm_server_cert_validation: 'ignore', tags: '', notes: '' });
  const openAdd = () => { resetForm(); setEditHost(null); setShowAddModal(true); };
  const openEdit = (h) => {
    setForm({ name: h.name, protocol: h.protocol, host: h.host, port: h.port || '', username: h.username, credential_type: h.credential_type, password: '', key_content: '', key_passphrase: '', winrm_transport: h.winrm_transport || 'ntlm', winrm_server_cert_validation: h.winrm_server_cert_validation || 'ignore', tags: (h.tags || []).join(', '), notes: h.notes || '' });
    setEditHost(h); setShowAddModal(true);
  };

  const handleSave = async () => {
    try {
      const payload = { name: form.name, protocol: form.protocol, host: form.host, port: form.port ? parseInt(form.port) : undefined, username: form.username, credential_type: form.credential_type, tags: form.tags ? form.tags.split(',').map(t => t.trim()).filter(Boolean) : [], notes: form.notes || undefined };
      if (form.password) payload.password = form.password;
      if (form.key_content) payload.key_content = form.key_content;
      if (form.key_passphrase) payload.key_passphrase = form.key_passphrase;
      if (form.protocol === 'winrm') { payload.winrm_transport = form.winrm_transport; payload.winrm_server_cert_validation = form.winrm_server_cert_validation; }
      if (editHost) { await api.put(`/api/hosts/${editHost.id}`, payload); setSuccess('Host updated successfully'); }
      else { await api.post('/api/hosts/', payload); setSuccess('Host added successfully'); }
      setShowAddModal(false); resetForm(); onRefresh(); setTimeout(() => setSuccess(null), 3000);
    } catch (err) { setError(err.response?.data?.detail || 'Failed to save host'); }
  };

  const handleTest = async (hostId) => {
    setTestResults(prev => ({ ...prev, [hostId]: 'testing' }));
    try { const res = await api.post(`/api/hosts/${hostId}/test`); setTestResults(prev => ({ ...prev, [hostId]: res.data })); }
    catch (err) { setTestResults(prev => ({ ...prev, [hostId]: { success: false, error: err.response?.data?.detail || 'Test failed' } })); }
  };

  const handleDelete = async (hostId, name) => {
    if (!confirm(`Delete host "${name}"?`)) return;
    try { await api.delete(`/api/hosts/${hostId}`); setSuccess('Host deleted'); onRefresh(); setTimeout(() => setSuccess(null), 2000); }
    catch (err) { setError(err.response?.data?.detail || 'Failed to delete host'); }
  };

  const protocolIcon = (p) => p === 'ssh' ? '🐧' : '🪟';

  return (
    <div>
      {error && <Alert type="error" style={{ marginBottom: 'var(--spacing-4)' }} onClose={() => setError(null)}>{error}</Alert>}
      {success && <Alert type="success" style={{ marginBottom: 'var(--spacing-4)' }} onClose={() => setSuccess(null)}>{success}</Alert>}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--spacing-4)' }}>
        <p style={{ fontSize: 'var(--text-sm)', color: 'var(--gray-600)' }}>{hosts.length} host{hosts.length !== 1 ? 's' : ''} registered · credentials stored encrypted</p>
        <Button variant="primary" onClick={openAdd} icon={Plus}>Add host</Button>
      </div>
      {hosts.length === 0 ? (
        <div style={{ textAlign: 'center', padding: 'var(--spacing-10)', color: 'var(--gray-600)' }}>
          <div style={{ fontSize: '2.5rem', marginBottom: 'var(--spacing-3)' }}>🖥️</div>
          <p style={{ marginBottom: 'var(--spacing-3)' }}>No hosts registered yet</p>
          <Button variant="primary" onClick={openAdd} icon={Plus}>Add your first host</Button>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-2)' }}>
          {hosts.map(h => {
            const tr = testResults[h.id];
            return (
              <div key={h.id} style={{ display: 'grid', gridTemplateColumns: '28px 1fr auto auto', alignItems: 'center', gap: 'var(--spacing-3)', padding: 'var(--spacing-3) var(--spacing-4)', background: 'var(--bg-card)', border: '1px solid var(--gray-200)', borderLeft: `3px solid ${h.protocol === 'ssh' ? '#6366f1' : '#0ea5e9'}`, borderRadius: 'var(--radius-md)', opacity: h.is_active ? 1 : 0.6 }}>
                <div style={{ fontSize: '18px', textAlign: 'center' }}>{protocolIcon(h.protocol)}</div>
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontWeight: '600', fontSize: 'var(--text-sm)' }}>{h.name}</div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-2)', flexWrap: 'wrap', marginTop: '3px' }}>
                    <span style={{ fontSize: 'var(--text-xs)', color: 'var(--gray-600)' }}>{h.host}:{h.port || (h.protocol === 'ssh' ? 22 : 5985)}</span>
                    <span style={{ fontSize: '10px', padding: '1px 6px', borderRadius: '99px', background: 'var(--gray-200)', color: 'var(--gray-700)' }}>{h.protocol}</span>
                    <span style={{ fontSize: '10px', padding: '1px 6px', borderRadius: '99px', background: 'var(--gray-200)', color: 'var(--gray-700)' }}>{h.credential_type}</span>
                    {(h.tags || []).map(tag => <span key={tag} style={{ fontSize: '10px', padding: '1px 6px', borderRadius: '99px', background: 'var(--gray-200)', color: 'var(--gray-700)' }}>{tag}</span>)}
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', fontSize: '11px', color: h.is_active ? 'var(--success)' : 'var(--gray-500)' }}>
                      <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: h.is_active ? 'var(--success)' : 'var(--gray-400)', display: 'inline-block' }} />
                      {h.is_active ? 'active' : 'inactive'}
                    </span>
                    {h.last_connected && <span style={{ fontSize: '11px', color: 'var(--gray-600)' }}>last: {new Date(h.last_connected).toLocaleString()}</span>}
                  </div>
                  {tr && tr !== 'testing' && (
                    <div style={{ marginTop: '4px', fontSize: '11px', padding: '2px 8px', borderRadius: '3px', display: 'inline-block', background: tr.success ? 'rgba(52,211,153,.15)' : 'rgba(248,113,113,.15)', color: tr.success ? 'var(--success-dark)' : 'var(--danger-dark)' }}>
                      {tr.success ? `✓ OK ${tr.latency_ms}ms` : `✗ ${tr.error}`}
                    </div>
                  )}
                  {tr === 'testing' && <div style={{ marginTop: '4px', fontSize: '11px', color: 'var(--gray-600)' }}>Testing connection…</div>}
                </div>
                <div style={{ fontSize: '11px', color: 'var(--gray-600)' }}>{h.username}@{h.host}</div>
                <div style={{ display: 'flex', gap: '4px' }}>
                  {[{ label: 'Test', action: () => handleTest(h.id), color: 'var(--info)' }, { label: '✎', action: () => openEdit(h), color: 'var(--gray-600)' }, { label: '✕', action: () => handleDelete(h.id, h.name), color: 'var(--danger)' }].map(btn => (
                    <button key={btn.label} onClick={btn.action} style={{ width: '28px', height: '28px', borderRadius: 'var(--radius)', border: '1px solid var(--gray-300)', background: 'var(--gray-100)', color: btn.color, cursor: 'pointer', fontSize: '12px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>{btn.label}</button>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {showAddModal && (
        <div style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.65)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1100, padding: 'var(--spacing-4)' }}>
          <div className="card" style={{ width: '100%', maxWidth: '640px', maxHeight: '90vh', overflow: 'auto' }}>
            <h2 style={{ fontSize: 'var(--text-xl)', fontWeight: '600', marginBottom: 'var(--spacing-4)' }}>{editHost ? `Edit host — ${editHost.name}` : 'Add remote host'}</h2>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--spacing-3)', marginBottom: 'var(--spacing-3)' }}>
              <div className="form-group"><label className="form-label">Host name *</label><input type="text" className="form-input" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} placeholder="linux-01" disabled={!!editHost} /></div>
              <div className="form-group"><label className="form-label">Protocol *</label><select className="form-input" value={form.protocol} onChange={e => setForm({ ...form, protocol: e.target.value, credential_type: e.target.value === 'winrm' ? 'ntlm' : 'key' })}><option value="ssh">SSH</option><option value="winrm">WinRM</option></select></div>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: 'var(--spacing-3)', marginBottom: 'var(--spacing-3)' }}>
              <div className="form-group"><label className="form-label">IP / Hostname *</label><input type="text" className="form-input" value={form.host} onChange={e => setForm({ ...form, host: e.target.value })} placeholder="192.168.1.85" /></div>
              <div className="form-group" style={{ width: '100px' }}><label className="form-label">Port</label><input type="number" className="form-input" value={form.port} onChange={e => setForm({ ...form, port: e.target.value })} placeholder={form.protocol === 'ssh' ? '22' : '5985'} /></div>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--spacing-3)', marginBottom: 'var(--spacing-3)' }}>
              <div className="form-group"><label className="form-label">Username *</label><input type="text" className="form-input" value={form.username} onChange={e => setForm({ ...form, username: e.target.value })} placeholder={form.protocol === 'ssh' ? 'debian' : 'Administrator'} /></div>
              <div className="form-group">
                <label className="form-label">Credential type *</label>
                <select className="form-input" value={form.credential_type} onChange={e => setForm({ ...form, credential_type: e.target.value })}>
                  {form.protocol === 'ssh' ? (<><option value="key">SSH key</option><option value="password">Password</option><option value="key+passphrase">SSH key + passphrase</option></>) : (<><option value="ntlm">NTLM</option><option value="kerberos">Kerberos</option><option value="password">Password</option></>)}
                </select>
              </div>
            </div>
            {form.protocol === 'ssh' && (form.credential_type === 'key' || form.credential_type === 'key+passphrase') && (
              <div className="form-group" style={{ marginBottom: 'var(--spacing-3)' }}>
                <label className="form-label">SSH private key (PEM) {editHost ? '— leave empty to keep current' : '*'}</label>
                <textarea className="form-input" rows={4} value={form.key_content} onChange={e => setForm({ ...form, key_content: e.target.value })} placeholder="-----BEGIN OPENSSH PRIVATE KEY-----&#10;...&#10;-----END OPENSSH PRIVATE KEY-----" />
              </div>
            )}
            {form.credential_type === 'key+passphrase' && (
              <div className="form-group" style={{ marginBottom: 'var(--spacing-3)' }}>
                <label className="form-label">Key passphrase</label>
                <input type="password" className="form-input" value={form.key_passphrase} onChange={e => setForm({ ...form, key_passphrase: e.target.value })} placeholder="Passphrase for private key" />
              </div>
            )}
            {(form.credential_type === 'password' || form.credential_type === 'ntlm') && (
              <div className="form-group" style={{ marginBottom: 'var(--spacing-3)' }}>
                <label className="form-label">Password {editHost ? '— leave empty to keep current' : '*'}</label>
                <input type="password" className="form-input" value={form.password} onChange={e => setForm({ ...form, password: e.target.value })} placeholder="Password" />
              </div>
            )}
            {form.protocol === 'winrm' && (
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--spacing-3)', marginBottom: 'var(--spacing-3)' }}>
                <div className="form-group"><label className="form-label">WinRM transport</label><select className="form-input" value={form.winrm_transport} onChange={e => setForm({ ...form, winrm_transport: e.target.value })}><option value="ntlm">ntlm</option><option value="basic">basic</option><option value="kerberos">kerberos</option></select></div>
                <div className="form-group"><label className="form-label">Certificate validation</label><select className="form-input" value={form.winrm_server_cert_validation} onChange={e => setForm({ ...form, winrm_server_cert_validation: e.target.value })}><option value="ignore">ignore</option><option value="validate">validate</option></select></div>
              </div>
            )}
            <div className="form-group" style={{ marginBottom: 'var(--spacing-3)' }}>
              <label className="form-label">Tags <span style={{ color: 'var(--gray-500)', fontSize: 'var(--text-xs)' }}>(comma-separated)</span></label>
              <input type="text" className="form-input" value={form.tags} onChange={e => setForm({ ...form, tags: e.target.value })} placeholder="linux, prod, web" />
            </div>
            <div className="form-group" style={{ marginBottom: 'var(--spacing-4)' }}>
              <label className="form-label">Notes</label>
              <textarea className="form-input" rows={2} value={form.notes} onChange={e => setForm({ ...form, notes: e.target.value })} placeholder="Optional notes about this host" />
            </div>
            <div style={{ padding: 'var(--spacing-3)', border: '1px solid var(--warning)', borderLeft: '3px solid var(--warning)', borderRadius: 'var(--radius)', backgroundColor: 'rgba(251,191,36,0.06)', marginBottom: 'var(--spacing-4)', fontSize: 'var(--text-xs)', color: 'var(--gray-700)', lineHeight: '1.6' }}>
              <strong style={{ color: 'var(--warning-dark)' }}>🔒 Credentials are encrypted immediately</strong> and never returned in API responses. After saving, use the <strong>Test</strong> button to verify connectivity.
            </div>
            <div style={{ display: 'flex', gap: 'var(--spacing-3)', justifyContent: 'flex-end', paddingTop: 'var(--spacing-4)', borderTop: '1px solid var(--gray-200)' }}>
              <Button variant="ghost" onClick={() => { setShowAddModal(false); resetForm(); }}>Cancel</Button>
              <Button variant="primary" onClick={handleSave} disabled={!form.name || !form.host || !form.username}>{editHost ? 'Update host' : 'Save host'}</Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// DOCUMENTATION TAB
// ─────────────────────────────────────────────────────────────────────────────
const DocumentationTab = () => (
  <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-5)' }}>
    {DOC_ENTRIES.map(entry => (
      <div key={entry.key} style={{ border: '1px solid var(--gray-300)', borderRadius: 'var(--radius-md)', overflow: 'hidden' }}>
        <div style={{ padding: 'var(--spacing-4)', backgroundColor: 'var(--gray-100)', borderBottom: '1px solid var(--gray-300)' }}>
          <h3 style={{ fontWeight: '600', fontSize: 'var(--text-base)', display: 'flex', alignItems: 'center', gap: 'var(--spacing-2)' }}><span>{entry.icon}</span> {entry.title}</h3>
          <p style={{ fontSize: 'var(--text-sm)', color: 'var(--gray-700)', marginTop: 'var(--spacing-1)', lineHeight: '1.6' }}>{entry.desc}</p>
        </div>
        {entry.steps && (
          <div style={{ padding: 'var(--spacing-4)', display: 'flex', flexDirection: 'column', gap: 'var(--spacing-3)' }}>
            {entry.steps.map(step => (
              <div key={step.n} style={{ display: 'flex', gap: 'var(--spacing-3)', alignItems: 'flex-start' }}>
                <span style={{ minWidth: '22px', height: '22px', borderRadius: '50%', background: 'var(--gray-200)', border: '1px solid var(--gray-400)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 'var(--text-xs)', fontWeight: '600', color: 'var(--gray-800)', flexShrink: 0 }}>{step.n}</span>
                <p style={{ fontSize: 'var(--text-sm)', color: 'var(--gray-800)', lineHeight: '1.6' }}>{step.text}</p>
              </div>
            ))}
          </div>
        )}
        {entry.table && (
          <div style={{ padding: 'var(--spacing-4)', overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 'var(--text-sm)' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--gray-300)' }}>
                  {['agent_type', 'name', 'badge', 'MCP servers'].map(h => (
                    <th key={h} style={{ textAlign: 'left', padding: 'var(--spacing-2) var(--spacing-3)', color: 'var(--gray-600)', fontWeight: '600', fontSize: 'var(--text-xs)', textTransform: 'uppercase', letterSpacing: '.05em' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {entry.table.map((row, i) => (
                  <tr key={row.key} style={{ borderBottom: i < entry.table.length - 1 ? '1px solid var(--gray-200)' : 'none' }}>
                    <td style={{ padding: 'var(--spacing-2) var(--spacing-3)', fontFamily: 'monospace', fontSize: 'var(--text-xs)', color: 'var(--gray-800)' }}>{row.key}</td>
                    <td style={{ padding: 'var(--spacing-2) var(--spacing-3)', fontWeight: '500' }}>{row.name}</td>
                    <td style={{ padding: 'var(--spacing-2) var(--spacing-3)' }}>
                      <span style={{ fontSize: '10px', fontWeight: '600', padding: '2px 8px', borderRadius: '99px', background: row.badge === 'skill' ? 'rgba(34,197,94,.15)' : 'rgba(96,165,250,.15)', color: row.badge === 'skill' ? 'var(--success-dark)' : 'var(--primary-dark)' }}>{row.badge}</span>
                    </td>
                    <td style={{ padding: 'var(--spacing-2) var(--spacing-3)', color: 'var(--gray-700)', fontSize: 'var(--text-xs)' }}>{row.mcp}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    ))}
  </div>
);


// ─────────────────────────────────────────────────────────────────────────────
// MAIN COMPONENT
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
  const [preloadExec, setPreloadExec] = useState(null);  // exec à précharger dans le popup
  const [selectedAgentType, setSelectedAgentType] = useState(null);
  const [selectedAgent, setSelectedAgent] = useState(null);
  const [providers, setProviders] = useState([]);
  const [formData, setFormData] = useState({ name: '', description: '', agent_type: '', config: {}, mcp_config: {} });

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
    setSelectedAgentType(null);
    setFormData({ name: '', description: '', agent_type: '', config: {}, mcp_config: {} });
    setError(null); setSuccess(null);
  };

  const selectAgentType = (type) => {
    setSelectedAgentType(type);
    const t = AGENT_TYPES[type];
    setFormData({ name: '', description: t.description, agent_type: type, config: t.defaultConfig(providers), mcp_config: { ...t.mcpConfig } });
  };

  const validateForm = () => {
    if (!formData.name.trim()) { setError('Agent name is required'); return false; }
    const t = AGENT_TYPES[selectedAgentType];
    for (const field of t.requiredFields) {
      const src = (field.startsWith('github') || field.startsWith('gitea')) ? formData.mcp_config : formData.config;
      const val = field.split('.').reduce((o, k) => o?.[k], src);
      if (!val || val.trim() === '') { setError(`Field ${field} is required`); return false; }
    }
    return true;
  };

  const handleSubmit = async () => {
    if (!validateForm()) return;
    try {
      await api.post('/api/agents/', formData);
      setSuccess('Agent created successfully!');
      setTimeout(() => { setShowCreateModal(false); loadAll(); setSuccess(null); }, 1500);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create agent');
    }
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

  const updateConfigField = (path, value) => {
    const keys = path.split('.');
    const newFormData = { ...formData };
    let current = keys[0] === 'mcp_config' ? newFormData.mcp_config : newFormData.config;
    for (let i = (keys[0] === 'mcp_config' || keys[0] === 'config') ? 1 : 0; i < keys.length - 1; i++) {
      if (!current[keys[i]]) current[keys[i]] = {};
      current = current[keys[i]];
    }
    current[keys[keys.length - 1]] = value;
    setFormData(newFormData);
  };

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
      <div style={{ padding: 'var(--spacing-6)', maxWidth: '1200px', margin: '0 auto' }}>

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
              setSelectedAgent(historyAgent);
              setPreloadExec(exec);
              setShowExecuteModal(true);
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
            onClose={() => { setShowExecuteModal(false); setSelectedAgent(null); setPreloadExec(null); }}
            onExecuted={handleAgentExecuted}
            hosts={hosts}
            skills={skills}
            preloadExec={preloadExec}
          />
        )}

        {showCreateModal && (
          <div style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.65)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, padding: 'var(--spacing-4)' }}>
            <div className="card" style={{ width: '100%', maxWidth: '900px', maxHeight: '90vh', overflow: 'auto' }}>
              <h2 style={{ fontSize: 'var(--text-xl)', fontWeight: '600', marginBottom: 'var(--spacing-2)' }}>
                {selectedAgentType ? `Configure — ${AGENT_TYPES[selectedAgentType].name}` : 'Select agent type'}
              </h2>
              {selectedAgentType && <p style={{ fontSize: 'var(--text-sm)', color: 'var(--gray-600)', marginBottom: 'var(--spacing-5)' }}>{AGENT_TYPES[selectedAgentType].description}</p>}

              {!selectedAgentType ? (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 'var(--spacing-3)' }}>
                  {Object.entries(AGENT_TYPES).map(([type, info]) => (
                    <div key={type} onClick={() => selectAgentType(type)} style={{ border: '1px solid var(--gray-300)', borderLeft: `3px solid ${info.color}`, borderRadius: 'var(--radius-md)', padding: 'var(--spacing-4)', cursor: 'pointer', transition: 'all .15s', background: 'var(--bg-card)' }}
                      onMouseEnter={e => { e.currentTarget.style.borderColor = info.color; e.currentTarget.style.transform = 'translateY(-2px)'; }}
                      onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--gray-300)'; e.currentTarget.style.transform = 'none'; }}>
                      <div style={{ fontSize: '1.5rem', marginBottom: 'var(--spacing-2)' }}>{info.icon}</div>
                      <div style={{ fontWeight: '600', fontSize: 'var(--text-sm)', marginBottom: 'var(--spacing-1)' }}>{info.name}</div>
                      <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap', marginBottom: 'var(--spacing-2)' }}>
                        <span style={{ fontSize: '10px', fontWeight: '600', padding: '1px 6px', borderRadius: '99px', background: info.badge === 'skill' ? 'rgba(34,197,94,.15)' : 'rgba(96,165,250,.15)', color: info.badge === 'skill' ? 'var(--success-dark)' : 'var(--primary-dark)' }}>{info.badge}</span>
                        {info.mcp.map(m => <span key={m} style={{ fontSize: '10px', padding: '1px 5px', borderRadius: '99px', background: 'var(--gray-200)', color: 'var(--gray-700)' }}>{m}</span>)}
                      </div>
                      <p style={{ fontSize: 'var(--text-xs)', color: 'var(--gray-600)', lineHeight: '1.5' }}>{info.description}</p>
                    </div>
                  ))}
                </div>
              ) : (
                <div>
                  {error && <Alert type="error" style={{ marginBottom: 'var(--spacing-4)' }} onClose={() => setError(null)}>{error}</Alert>}
                  {success && <Alert type="success" style={{ marginBottom: 'var(--spacing-4)' }}>{success}</Alert>}

                  <div className="form-group">
                    <label className="form-label">Agent name *</label>
                    <input type="text" className="form-input" value={formData.name} onChange={e => setFormData({ ...formData, name: e.target.value })} placeholder={`My ${AGENT_TYPES[selectedAgentType].name}`} />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Description</label>
                    <textarea className="form-input" value={formData.description || ''} onChange={e => setFormData({ ...formData, description: e.target.value })} placeholder="Optional description" rows={2} />
                  </div>

                  <div style={{ padding: 'var(--spacing-4)', backgroundColor: 'var(--gray-100)', borderRadius: 'var(--radius)', marginBottom: 'var(--spacing-4)' }}>
                    <h3 style={{ fontWeight: '600', fontSize: 'var(--text-sm)', marginBottom: 'var(--spacing-3)' }}>LLM configuration</h3>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 'var(--spacing-3)' }}>
                      <div className="form-group"><label className="form-label">Provider</label><select className="form-input" value={formData.config.llm_provider} onChange={e => updateConfigField('config.llm_provider', e.target.value)}>{providers.map(p => <option key={p.name} value={p.name}>{p.name}</option>)}</select></div>
                      <div className="form-group"><label className="form-label">Model</label><input type="text" className="form-input" value={formData.config.llm_model} onChange={e => updateConfigField('config.llm_model', e.target.value)} /></div>
                      <div className="form-group"><label className="form-label">Temperature</label><input type="number" step="0.1" min="0" max="2" className="form-input" value={formData.config.llm_temperature} onChange={e => updateConfigField('config.llm_temperature', parseFloat(e.target.value))} /></div>
                    </div>
                  </div>

                  {selectedAgentType === 'skill' && (
                    <div style={{ padding: 'var(--spacing-4)', backgroundColor: 'var(--gray-100)', borderRadius: 'var(--radius)', marginBottom: 'var(--spacing-4)' }}>
                      <h3 style={{ fontWeight: '600', fontSize: 'var(--text-sm)', marginBottom: 'var(--spacing-3)' }}>Skill configuration</h3>
                      <div className="form-group">
                        <label className="form-label">Default skill <span style={{ color: 'var(--gray-500)', fontSize: 'var(--text-xs)' }}>(optional — auto-resolved at execution by semantic search)</span></label>
                        <select className="form-input" value={formData.config.skill_id || ''} onChange={e => updateConfigField('config.skill_id', e.target.value)}>
                          <option value="">— auto-detect —</option>
                          {skills.map(s => <option key={s.skill_id} value={s.skill_id}>{s.skill_id} — {s.description}</option>)}
                        </select>
                        <p style={{ fontSize: 'var(--text-xs)', color: 'var(--gray-600)', marginTop: '4px' }}>Skills loaded from <code style={{ fontSize: '11px' }}>GET /api/skills/</code> — Register via <code style={{ fontSize: '11px' }}>POST /api/skills/register</code>.</p>
                      </div>
                      <div className="form-group">
                        <label className="form-label">Memory scope</label>
                        <select className="form-input" value={formData.config.memory_scope || 'session+global'} onChange={e => updateConfigField('config.memory_scope', e.target.value)}>
                          <option value="session+global">session+global (recommended)</option>
                          <option value="session">session only</option>
                          <option value="global">global only</option>
                          <option value="none">none</option>
                        </select>
                      </div>
                    </div>
                  )}

                  {['branch_code_review', 'code_generator'].includes(selectedAgentType) && (
                    <div style={{ padding: 'var(--spacing-4)', backgroundColor: 'var(--gray-100)', borderRadius: 'var(--radius)', marginBottom: 'var(--spacing-4)' }}>
                      <h3 style={{ fontWeight: '600', fontSize: 'var(--text-sm)', marginBottom: 'var(--spacing-3)' }}>GitHub configuration</h3>
                      <div className="form-group"><label className="form-label">GitHub token * <span style={{ fontSize: 'var(--text-xs)', color: 'var(--gray-500)' }}>Required for code operations</span></label><input type="password" className="form-input" value={formData.mcp_config.github?.token || ''} onChange={e => updateConfigField('mcp_config.github.token', e.target.value)} placeholder="ghp_..." /></div>
                      <div className="form-group"><label className="form-label">Repository * <span style={{ fontSize: 'var(--text-xs)', color: 'var(--gray-500)' }}>username/repo</span></label><input type="text" className="form-input" value={formData.mcp_config.github?.repo || ''} onChange={e => updateConfigField('mcp_config.github.repo', e.target.value)} placeholder="username/repository" /></div>
                    </div>
                  )}

                  {selectedAgentType === 'gitea_code_generator' && (
                    <div style={{ padding: 'var(--spacing-4)', backgroundColor: 'var(--gray-100)', borderRadius: 'var(--radius)', marginBottom: 'var(--spacing-4)' }}>
                      <h3 style={{ fontWeight: '600', fontSize: 'var(--text-sm)', marginBottom: 'var(--spacing-3)' }}>Gitea configuration</h3>
                      <div className="form-group"><label className="form-label">Gitea URL *</label><input type="text" className="form-input" value={formData.mcp_config.gitea?.url || ''} onChange={e => updateConfigField('mcp_config.gitea.url', e.target.value)} placeholder="http://gitea.example.local:3000" /></div>
                      <div className="form-group"><label className="form-label">Access token * <span style={{ fontSize: 'var(--text-xs)', color: 'var(--gray-500)' }}>Settings → Applications</span></label><input type="password" className="form-input" value={formData.mcp_config.gitea?.token || ''} onChange={e => updateConfigField('mcp_config.gitea.token', e.target.value)} placeholder="27d917559497ec0c…" /></div>
                      <div className="form-group"><label className="form-label">Repository * <span style={{ fontSize: 'var(--text-xs)', color: 'var(--gray-500)' }}>owner/repo</span></label><input type="text" className="form-input" value={formData.mcp_config.gitea?.repo || ''} onChange={e => updateConfigField('mcp_config.gitea.repo', e.target.value)} placeholder="username/my-repo" /></div>
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--spacing-3)', marginBottom: 'var(--spacing-3)' }}>
                        <div className="form-group"><label className="form-label">Base branch</label><input type="text" className="form-input" value={formData.config.base_branch || 'main'} onChange={e => updateConfigField('config.base_branch', e.target.value)} placeholder="main" /></div>
                        <div className="form-group"><label className="form-label">Target branch (AI)</label><input type="text" className="form-input" value={formData.config.target_branch || 'ai-feature'} onChange={e => updateConfigField('config.target_branch', e.target.value)} placeholder="ai-feature" /></div>
                      </div>
                      <div style={{ display: 'flex', gap: 'var(--spacing-4)', flexWrap: 'wrap' }}>
                        {[{ key: 'auto_lint', label: 'Auto lint' }, { key: 'auto_commit', label: 'Auto commit' }, { key: 'auto_create_pr', label: 'Auto create PR' }, { key: 'auto_test', label: 'Auto test' }].map(({ key, label }) => (
                          <label key={key} style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-2)', cursor: 'pointer', fontSize: 'var(--text-sm)' }}>
                            <input type="checkbox" checked={!!formData.config[key]} onChange={e => updateConfigField(`config.${key}`, e.target.checked)} />{label}
                          </label>
                        ))}
                      </div>
                    </div>
                  )}

                  {selectedAgentType === 'datagouv_explorer' && (
                    <div style={{ padding: 'var(--spacing-4)', backgroundColor: 'var(--gray-100)', borderRadius: 'var(--radius)', marginBottom: 'var(--spacing-4)' }}>
                      <h3 style={{ fontWeight: '600', fontSize: 'var(--text-sm)', marginBottom: 'var(--spacing-3)' }}>DataGouv configuration</h3>
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--spacing-3)' }}>
                        <div className="form-group"><label className="form-label">Page size</label><input type="number" className="form-input" value={formData.config.page_size || 10} onChange={e => updateConfigField('config.page_size', parseInt(e.target.value))} /></div>
                        <div className="form-group"><label className="form-label">Analyze (LLM summary)</label><select className="form-input" value={formData.config.analyze ? 'true' : 'false'} onChange={e => updateConfigField('config.analyze', e.target.value === 'true')}><option value="false">false — raw results</option><option value="true">true — LLM summary</option></select></div>
                      </div>
                    </div>
                  )}

                  {selectedAgentType === 'email_expert' && (
                    <div style={{ padding: 'var(--spacing-4)', backgroundColor: 'var(--gray-100)', borderRadius: 'var(--radius)', marginBottom: 'var(--spacing-4)' }}>
                      <h3 style={{ fontWeight: '600', fontSize: 'var(--text-sm)', marginBottom: 'var(--spacing-3)' }}>Email configuration</h3>
                      <div className="form-group"><label className="form-label">Email address *</label><input type="email" className="form-input" value={formData.config.email_config?.email || ''} onChange={e => updateConfigField('config.email_config.email', e.target.value)} placeholder="your.email@gmail.com" /></div>
                      <div className="form-group"><label className="form-label">App password * <span style={{ fontSize: 'var(--text-xs)', color: 'var(--gray-500)' }}>Use app-specific password</span></label><input type="password" className="form-input" value={formData.config.email_config?.password || ''} onChange={e => updateConfigField('config.email_config.password', e.target.value)} placeholder="App-specific password" /></div>
                    </div>
                  )}

                  <div style={{ display: 'flex', gap: 'var(--spacing-3)', justifyContent: 'space-between', marginTop: 'var(--spacing-6)', paddingTop: 'var(--spacing-4)', borderTop: '1px solid var(--gray-200)' }}>
                    <Button variant="ghost" onClick={() => setSelectedAgentType(null)}>← Back</Button>
                    <div style={{ display: 'flex', gap: 'var(--spacing-2)' }}>
                      <Button variant="ghost" onClick={() => { setShowCreateModal(false); setSelectedAgentType(null); }}>Cancel</Button>
                      <Button variant="primary" onClick={handleSubmit} disabled={!formData.name.trim()} icon={Plus}>Create agent</Button>
                    </div>
                  </div>
                </div>
              )}

              {!selectedAgentType && (
                <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 'var(--spacing-6)', paddingTop: 'var(--spacing-4)', borderTop: '1px solid var(--gray-200)' }}>
                  <Button variant="ghost" onClick={() => setShowCreateModal(false)}>Cancel</Button>
                </div>
              )}
            </div>
          </div>
        )}

      </div>
    </Layout>
  );
};

export default Agents;