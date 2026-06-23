import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  MessageSquare, Plus, FolderKanban, Database, Layers,
  Settings, Bot
} from 'lucide-react';
import Layout from '../components/layout/Layout';
import Loading from '../components/common/Loading';
import api from '../services/api';

// ── Helpers ───────────────────────────────────────────────────────────────────
const fmtNum = (n) => {
  if (!n && n !== 0) return '—';
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(2) + 'M';
  if (n >= 1_000)     return (n / 1_000).toFixed(1) + 'k';
  return String(n);
};

const today = () =>
  new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' });

// ── Sub-components ────────────────────────────────────────────────────────────

const SectionLabel = ({ children, style = {} }) => (
  <div style={{
    fontSize: '11px', fontWeight: '500',
    color: 'var(--gray-400)',
    letterSpacing: '0.05em', textTransform: 'uppercase',
    marginBottom: '8px',
    ...style,
  }}>
    {children}
  </div>
);

const MetricCard = ({ value, label, delta }) => (
  <div style={{
    background: 'var(--gray-50, #f9fafb)',
    borderRadius: 'var(--radius)',
    padding: '12px 14px',
  }}>
    <div style={{ fontSize: '22px', fontWeight: '600', color: 'var(--gray-900)', lineHeight: 1 }}>
      {value}
    </div>
    <div style={{ fontSize: '12px', color: 'var(--gray-500)', marginTop: '3px' }}>
      {label}
    </div>
    {delta && (
      <div style={{ fontSize: '11px', color: '#27500A', marginTop: '2px' }}>
        {delta}
      </div>
    )}
  </div>
);

const ProviderRow = ({ provider }) => {
  const active = provider.is_active;
  const isLocal =
    (provider.base_url || '').includes('localhost') ||
    (provider.base_url || '').includes('127.0.0.1');

  const labelCfg = isLocal
    ? { label: 'Local', bg: '#E1F5EE', color: '#085041', border: '#5DCAA5' }
    : { label: 'Cloud', bg: '#EEEDFE', color: '#3C3489', border: '#AFA9EC' };

  const urlShort = (provider.base_url || '')
    .replace(/^https?:\/\//, '')
    .replace(/\/.*$/, '')
    .substring(0, 22);

  return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      padding: '6px 0',
      borderBottom: '1px solid var(--gray-100)',
      opacity: active ? 1 : 0.5,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '7px', minWidth: 0 }}>
        <span style={{
          width: '6px', height: '6px', borderRadius: '50%', flexShrink: 0,
          background: active ? '#639922' : '#B4B2A9',
        }} />
        <div style={{ minWidth: 0 }}>
          <div style={{
            fontSize: '12px', fontWeight: '500',
            color: active ? 'var(--gray-900)' : 'var(--gray-500)',
            overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
            maxWidth: '130px',
          }}>
            {provider.display_name || provider.name}
          </div>
          {urlShort && (
            <div style={{
              fontSize: '10px', color: 'var(--gray-400)',
              fontFamily: 'monospace', marginTop: '1px',
            }}>
              {urlShort}
            </div>
          )}
        </div>
      </div>
      <span style={{
        display: 'inline-flex', alignItems: 'center',
        padding: '2px 6px', borderRadius: '20px',
        fontSize: '10px', fontWeight: '500',
        background: labelCfg.bg, color: labelCfg.color,
        border: `0.5px solid ${labelCfg.border}`,
        flexShrink: 0,
      }}>
        {labelCfg.label}
      </span>
    </div>
  );
};

const QuickActionBtn = ({ icon: Icon, label, onClick, primary }) => (
  <button
    onClick={onClick}
    style={{
      width: '100%',
      display: 'inline-flex', alignItems: 'center', gap: '8px',
      height: '34px', padding: '0 12px',
      borderRadius: 'var(--radius)',
      border: primary ? '1px solid rgba(255,255,255,0.15)' : '1px solid var(--gray-200)',
      background: primary ? 'var(--primary)' : 'transparent',
      color: primary ? 'white' : 'var(--gray-600)',
      fontSize: '12px', fontWeight: '500',
      cursor: 'pointer', transition: 'opacity 0.12s',
      justifyContent: 'flex-start',
    }}
    onMouseEnter={e => { e.currentTarget.style.opacity = '0.85'; }}
    onMouseLeave={e => { e.currentTarget.style.opacity = '1'; }}
  >
    <Icon size={13} />
    {label}
  </button>
);

// ── Provider display name map ─────────────────────────────────────────────────
const PROVIDER_NAMES = {
  openai:      'OpenAI',
  claude:      'Anthropic Claude',
  gemini:      'Google Gemini',
  huggingface: 'HuggingFace',
  ollama:      'Ollama',
  lmstudio:    'LM Studio',
  localai:     'LocalAI',
  groq:        'Groq',
  grok:        'xAI Grok',
  openrouter:  'OpenRouter',
  vllm:        'vLLM',
  lmdeploy:    'LMDeploy',
  oobabooga:   'Text Gen WebUI',
};

// ── Main component ────────────────────────────────────────────────────────────
const Dashboard = () => {
  const navigate = useNavigate();

  const [stats, setStats] = useState({
    totalConversations: 0,
    messagestoday:      0,
    activeProviders:    0,
    tokensUsed:         0,
    totalProjects:      0,
    totalDocuments:     0,
    totalChunks:        0,
    ragTokens:          0,
  });
  const [providers, setProviders] = useState([]);
  const [loading, setLoading]     = useState(true);

  useEffect(() => { loadAll(); }, []);

  const loadAll = async () => {
    setLoading(true);
    try {
      const [statsRes, providersRes] = await Promise.all([
        api.get('/api/conversations/stats'),
        api.get('/api/providers/'),
      ]);

      const activeProviders = providersRes.data.filter(p => p.is_active).length;

      setStats({
        totalConversations: statsRes.data.total_conversations    || 0,
        messagestoday:      statsRes.data.messages_today         || 0,
        activeProviders,
        tokensUsed:         statsRes.data.tokens_used            || 0,
        totalProjects:      statsRes.data.total_projects         || 0,
        totalDocuments:     statsRes.data.total_documents        || 0,
        totalChunks:        statsRes.data.total_chunks           || 0,
        ragTokens:          statsRes.data.rag_tokens             || 0,
      });

      // Enrich providers with display names
      const enriched = providersRes.data.map(p => ({
        ...p,
        display_name: PROVIDER_NAMES[p.name] || p.name.toUpperCase(),
      }));
      setProviders(enriched);
    } catch (err) {
      console.error('Failed to load dashboard:', err);
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <Layout><Loading message="Loading dashboard..." /></Layout>;

  const sortedProviders = [...providers].sort((a, b) => {
    if (a.is_active && !b.is_active) return -1;
    if (!a.is_active && b.is_active) return 1;
    return (b.priority || 0) - (a.priority || 0);
  });

  return (
    <Layout>
      <div style={{ padding: 'var(--spacing-8) var(--spacing-6)', maxWidth: '1100px', margin: '0 auto' }}>

        {/* ── Header ── */}
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: '2rem' }}>
          <div>
            <h1 style={{ fontSize: 'var(--text-2xl)', fontWeight: '600', color: 'var(--gray-900)', marginBottom: '4px' }}>
              Dashboard
            </h1>
            <p style={{ fontSize: 'var(--text-sm)', color: 'var(--gray-500)' }}>
              {today()} · {stats.activeProviders} provider{stats.activeProviders !== 1 ? 's' : ''} active
            </p>
          </div>
          <div style={{ display: 'flex', gap: '6px' }}>
            <button
              onClick={() => navigate('/providers')}
              style={{
                display: 'inline-flex', alignItems: 'center', gap: '5px',
                height: '32px', padding: '0 14px',
                borderRadius: 'var(--radius)',
                border: '1px solid var(--gray-200)',
                background: 'transparent',
                fontSize: '12px', fontWeight: '500', color: 'var(--gray-600)',
                cursor: 'pointer', transition: 'all 0.12s',
              }}
              onMouseEnter={e => { e.currentTarget.style.background = 'var(--gray-50)'; e.currentTarget.style.color = 'var(--gray-900)'; }}
              onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = 'var(--gray-600)'; }}
            >
              <Settings size={13} />
              Providers
            </button>
            <button
              onClick={() => navigate('/chat')}
              style={{
                display: 'inline-flex', alignItems: 'center', gap: '5px',
                height: '32px', padding: '0 14px',
                borderRadius: 'var(--radius)',
                background: 'var(--primary)', color: 'white',
                border: 'none',
                fontSize: '12px', fontWeight: '500',
                cursor: 'pointer', transition: 'opacity 0.12s',
              }}
              onMouseEnter={e => e.currentTarget.style.opacity = '0.85'}
              onMouseLeave={e => e.currentTarget.style.opacity = '1'}
            >
              <Plus size={13} />
              New chat
            </button>
          </div>
        </div>

        {/* ── Main layout: 2/3 + 1/3 ── */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 280px', gap: '12px' }}>

          {/* ── Left column ── */}
          <div>
            {/* Chat metrics */}
            <SectionLabel>Chat</SectionLabel>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, minmax(0, 1fr))', gap: '8px', marginBottom: '4px' }}>
              <MetricCard value={fmtNum(stats.totalConversations)} label="Conversations" />
              <MetricCard
                value={fmtNum(stats.messagestoday)}
                label="Messages today"
                delta={stats.messagestoday > 0 ? undefined : undefined}
              />
              <MetricCard value={stats.activeProviders} label="Active providers" />
              <MetricCard value={fmtNum(stats.tokensUsed)} label="Tokens used" />
            </div>

            {/* RAG metrics */}
            <SectionLabel style={{ marginTop: '1.5rem' }}>RAG</SectionLabel>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, minmax(0, 1fr))', gap: '8px', marginBottom: '4px' }}>
              <MetricCard value={fmtNum(stats.totalProjects)}  label="Projects" />
              <MetricCard value={fmtNum(stats.totalDocuments)} label="Documents" />
              <MetricCard value={fmtNum(stats.totalChunks)}    label="Chunks indexed" />
              <MetricCard value={fmtNum(stats.ragTokens)}      label="RAG tokens" />
            </div>

          </div>

          {/* ── Right column ── */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>

            {/* Providers list */}
            <div>
              <SectionLabel>Providers</SectionLabel>
              <div style={{
                background: 'var(--bg-card)',
                border: '1px solid var(--gray-200)',
                borderRadius: 'var(--radius-lg)',
                padding: '10px 12px',
              }}>
                {sortedProviders.length === 0 ? (
                  <div style={{ fontSize: '12px', color: 'var(--gray-400)', padding: '8px 0', textAlign: 'center' }}>
                    No providers configured
                  </div>
                ) : (
                  sortedProviders.map((p, i) => (
                    <div
                      key={p.id}
                      style={{ borderBottom: i === sortedProviders.length - 1 ? 'none' : undefined }}
                    >
                      <ProviderRow provider={p} />
                    </div>
                  ))
                )}
                <button
                  onClick={() => navigate('/providers')}
                  style={{
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    gap: '4px',
                    width: '100%', marginTop: '8px',
                    padding: '6px 0',
                    border: '1px dashed var(--gray-200)',
                    borderRadius: 'var(--radius)',
                    background: 'transparent',
                    fontSize: '11px', color: 'var(--gray-400)',
                    cursor: 'pointer', transition: 'all 0.12s',
                  }}
                  onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--gray-400)'; e.currentTarget.style.color = 'var(--gray-600)'; }}
                  onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--gray-200)'; e.currentTarget.style.color = 'var(--gray-400)'; }}
                >
                  <Plus size={11} />
                  Add provider
                </button>
              </div>
            </div>

            {/* Quick actions */}
            <div>
              <SectionLabel style={{ marginTop: '1.25rem' }}>Quick actions</SectionLabel>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                <QuickActionBtn
                  primary
                  icon={MessageSquare}
                  label="Chat"
                  onClick={() => navigate('/chat')}
                />
                <QuickActionBtn
                  icon={FolderKanban}
                  label="RAG chat"
                  onClick={() => navigate('/projects')}
                />
                <QuickActionBtn
                  icon={Bot}
                  label="Agents"
                  onClick={() => navigate('/agents')}
                />
              </div>
            </div>
          </div>
        </div>
      </div>
    </Layout>
  );
};

export default Dashboard;