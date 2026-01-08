import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { MessageSquare, Server, FileText, TrendingUp, Plus, FolderKanban, Database, Layers } from 'lucide-react';
import Layout from '../components/layout/Layout';
import Button from '../components/common/Button';
import Loading from '../components/common/Loading';
import api from '../services/api';

const Dashboard = () => {
  const navigate = useNavigate();
  const [stats, setStats] = useState({
    totalConversations: 0,
    messagestoday: 0,
    activeProviders: 0,
    tokensUsed: 0,
    totalProjects: 0,
    totalDocuments: 0,
    totalChunks: 0,
    ragTokens: 0
  });
  const [loadingStats, setLoadingStats] = useState(true);

  useEffect(() => {
    loadStats();
  }, []);

  const loadStats = async () => {
    setLoadingStats(true);
    try {
      const [statsRes, providersRes] = await Promise.all([
        api.get('/api/conversations/stats'),
        api.get('/api/providers/')
      ]);

      const activeProviders = providersRes.data.filter(p => p.is_active).length;

      setStats({
        totalConversations: statsRes.data.total_conversations,
        messagestoday: statsRes.data.messages_today,
        activeProviders,
        tokensUsed: statsRes.data.tokens_used,
        totalProjects: statsRes.data.total_projects || 0,
        totalDocuments: statsRes.data.total_documents || 0,
        totalChunks: statsRes.data.total_chunks || 0,
        ragTokens: statsRes.data.rag_tokens || 0
      });
    } catch (error) {
      console.error('Failed to load stats:', error);
    } finally {
      setLoadingStats(false);
    }
  };

  const handleNewChat = () => {
    navigate('/chat');
  };

  const handleAddProvider = () => {
    navigate('/providers');
  };

  if (loadingStats) {
    return (
      <Layout>
        <Loading message="Loading dashboard..." />
      </Layout>
    );
  }

  return (
    <Layout>
      <div className="container" style={{ padding: 'var(--spacing-8) var(--spacing-4)' }}>
        <div className="flex justify-between items-center" style={{ marginBottom: 'var(--spacing-8)' }}>
          <div>
            <h1 style={{ fontSize: 'var(--text-3xl)', fontWeight: '700', marginBottom: 'var(--spacing-2)' }}>
              Dashboard
            </h1>
            <p style={{ color: 'var(--gray-600)' }}>
              Welcome back! Here's your overview.
            </p>
          </div>
          <div className="flex gap-4">
            <Button variant="ghost" icon={Plus} onClick={handleAddProvider}>
              Add Provider
            </Button>
            <Button variant="primary" icon={Plus} onClick={handleNewChat}>
              New Chat
            </Button>
          </div>
        </div>

        {/* Stats Sections */}
        <div style={{ marginBottom: 'var(--spacing-8)' }}>
          {/* Chat Stats */}
          <h2 style={{ 
            fontSize: 'var(--text-lg)', 
            fontWeight: '600', 
            marginBottom: 'var(--spacing-4)',
            color: 'var(--text-secondary)'
          }}>
            Chat Statistics
          </h2>
          <div className="grid grid-cols-4" style={{ marginBottom: 'var(--spacing-6)', gap: 'var(--spacing-4)' }}>
            <div className="card" style={{ textAlign: 'center' }}>
              <MessageSquare size={24} style={{ color: 'var(--primary)', margin: '0 auto var(--spacing-2)' }} />
              <div style={{ fontSize: 'var(--text-2xl)', fontWeight: '700', color: 'var(--text-primary)', marginBottom: 'var(--spacing-1)' }}>
                {stats.totalConversations}
              </div>
              <div style={{ fontSize: 'var(--text-sm)', color: 'var(--text-secondary)' }}>
                Conversations
              </div>
            </div>

            <div className="card" style={{ textAlign: 'center' }}>
              <TrendingUp size={24} style={{ color: 'var(--success)', margin: '0 auto var(--spacing-2)' }} />
              <div style={{ fontSize: 'var(--text-2xl)', fontWeight: '700', color: 'var(--text-primary)', marginBottom: 'var(--spacing-1)' }}>
                {stats.messagestoday}
              </div>
              <div style={{ fontSize: 'var(--text-sm)', color: 'var(--text-secondary)' }}>
                Messages Today
              </div>
            </div>

            <div className="card" style={{ textAlign: 'center' }}>
              <Server size={24} style={{ color: 'var(--warning)', margin: '0 auto var(--spacing-2)' }} />
              <div style={{ fontSize: 'var(--text-2xl)', fontWeight: '700', color: 'var(--text-primary)', marginBottom: 'var(--spacing-1)' }}>
                {stats.activeProviders}
              </div>
              <div style={{ fontSize: 'var(--text-sm)', color: 'var(--text-secondary)' }}>
                Active Providers
              </div>
            </div>

            <div className="card" style={{ textAlign: 'center' }}>
              <FileText size={24} style={{ color: 'var(--info)', margin: '0 auto var(--spacing-2)' }} />
              <div style={{ fontSize: 'var(--text-2xl)', fontWeight: '700', color: 'var(--text-primary)', marginBottom: 'var(--spacing-1)' }}>
                {stats.tokensUsed.toLocaleString()}
              </div>
              <div style={{ fontSize: 'var(--text-sm)', color: 'var(--text-secondary)' }}>
                Tokens Used
              </div>
            </div>
          </div>

          {/* RAG Stats */}
          <h2 style={{ 
            fontSize: 'var(--text-lg)', 
            fontWeight: '600', 
            marginBottom: 'var(--spacing-4)',
            color: 'var(--text-secondary)'
          }}>
            RAG Statistics
          </h2>
          <div className="grid grid-cols-4" style={{ marginBottom: 'var(--spacing-6)', gap: 'var(--spacing-4)' }}>
            <div className="card" style={{ textAlign: 'center' }}>
              <FolderKanban size={24} style={{ color: 'var(--primary)', margin: '0 auto var(--spacing-2)' }} />
              <div style={{ fontSize: 'var(--text-2xl)', fontWeight: '700', color: 'var(--text-primary)', marginBottom: 'var(--spacing-1)' }}>
                {stats.totalProjects}
              </div>
              <div style={{ fontSize: 'var(--text-sm)', color: 'var(--text-secondary)' }}>
                Projects
              </div>
            </div>

            <div className="card" style={{ textAlign: 'center' }}>
              <Database size={24} style={{ color: 'var(--success)', margin: '0 auto var(--spacing-2)' }} />
              <div style={{ fontSize: 'var(--text-2xl)', fontWeight: '700', color: 'var(--text-primary)', marginBottom: 'var(--spacing-1)' }}>
                {stats.totalDocuments}
              </div>
              <div style={{ fontSize: 'var(--text-sm)', color: 'var(--text-secondary)' }}>
                Documents
              </div>
            </div>

            <div className="card" style={{ textAlign: 'center' }}>
              <Layers size={24} style={{ color: 'var(--warning)', margin: '0 auto var(--spacing-2)' }} />
              <div style={{ fontSize: 'var(--text-2xl)', fontWeight: '700', color: 'var(--text-primary)', marginBottom: 'var(--spacing-1)' }}>
                {stats.totalChunks.toLocaleString()}
              </div>
              <div style={{ fontSize: 'var(--text-sm)', color: 'var(--text-secondary)' }}>
                Chunks
              </div>
            </div>

            <div className="card" style={{ textAlign: 'center' }}>
              <FileText size={24} style={{ color: 'var(--info)', margin: '0 auto var(--spacing-2)' }} />
              <div style={{ fontSize: 'var(--text-2xl)', fontWeight: '700', color: 'var(--text-primary)', marginBottom: 'var(--spacing-1)' }}>
                {stats.ragTokens.toLocaleString()}
              </div>
              <div style={{ fontSize: 'var(--text-sm)', color: 'var(--text-secondary)' }}>
                Tokens
              </div>
            </div>
          </div>
        </div>
      </div>
    </Layout>
  );
};

export default Dashboard;