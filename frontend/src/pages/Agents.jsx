import { useState, useEffect } from 'react';
import { Plus, Trash2, Power, PowerOff, Activity, Clock, CheckCircle, XCircle, Code, Scale, DollarSign, Plane, Mail, Search, Play, X } from 'lucide-react';
import Layout from '../components/layout/Layout';
import Button from '../components/common/Button';
import Loading from '../components/common/Loading';
import Alert from '../components/common/Alert';
import api from '../services/api';

// Configuration des types d'agents avec leurs icônes et configs
const AGENT_TYPES = {
  branch_code_review: {
    name: 'Code Review Agent',
    description: 'Analyse automatique de code sur branches Git avec suggestions de corrections',
    icon: '🔍',
    IconComponent: Code,
    color: '#3b82f6',
    defaultConfig: (providers) => ({
      mcp_servers: ['github'],
      use_llm: true,
      llm_provider: providers[0]?.name || 'ollama',
      llm_model: 'codestral:22b',
      llm_temperature: 0.3,
      review_focus: 'security',
      auto_fix: true,
      auto_create_pr: true
    }),
    mcpConfig: {
      github: { token: '', repo: '' }
    },
    requiredFields: ['github.token', 'github.repo'],
    executeFields: [
      { name: 'branch', label: 'Branch Name', type: 'text', placeholder: 'feature/my-branch', required: true }
    ]
  },
  
  code_generator: {
    name: 'Code Generator Agent',
    description: 'Génération de code assistée par IA avec RAG, tests et linting automatiques',
    icon: '⚡',
    IconComponent: Code,
    color: '#8b5cf6',
    defaultConfig: (providers) => ({
      mcp_servers: ['github', 'linter'],
      llm_provider: providers[0]?.name || 'ollama',
      llm_model: 'codestral:22b',
      llm_temperature: 0.2,
      target_branch: 'ai-feature',
      base_branch: 'main',
      auto_test: true,
      auto_lint: true,
      auto_commit: true,
      auto_create_pr: false
    }),
    mcpConfig: {
      github: { token: '', repo: '' }
    },
    requiredFields: ['github.token', 'github.repo'],
    executeFields: [
      { name: 'prompt', label: 'Code Generation Prompt', type: 'textarea', placeholder: 'Add OAuth2 authentication...', required: true },
      { name: 'create_new_files', label: 'Create New Files', type: 'checkbox', defaultValue: true },
      { name: 'test_mode', label: 'Test Mode', type: 'checkbox', defaultValue: true }
    ]
  },
  
  legal_fiscal: {
    name: 'Legal & Fiscal Expert',
    description: 'Expert juridique et fiscal avec RAG sur documents légaux (contrats, factures, RGPD)',
    icon: '⚖️',
    IconComponent: Scale,
    color: '#059669',
    defaultConfig: (providers) => ({
      llm_provider: providers[0]?.name || 'ollama',
      llm_model: 'mistrallite:latest',
      llm_temperature: 0.3,
      legal_config: {
        domains: ['fiscal', 'social', 'commercial'],
        auto_summary: true,
        extract_entities: true
      }
    }),
    mcpConfig: {},
    requiredFields: [],
    executeFields: [
      { 
        name: 'mode', 
        label: 'Analysis Mode', 
        type: 'select', 
        required: true,
        options: [
          { value: 'analyze', label: 'Analyze Document' },
          { value: 'risk_assessment', label: 'Risk Assessment' },
          { value: 'compliance_check', label: 'Compliance Check' },
          { value: 'claim_processing', label: 'Claim Processing' },
          { value: 'document_drafting', label: 'Document Drafting' },
          { value: 'legal_research', label: 'Legal Research' },
          { value: 'training', label: 'Training Material' },
          { value: 'monitoring', label: 'Legislative Monitoring' }
        ]
      },
      { name: 'query', label: 'Query/Instructions', type: 'textarea', placeholder: 'Analyze contract clauses...', required: true },
      { name: 'documents', label: 'Document Paths (optional)', type: 'text', placeholder: '/app/data/contract.pdf (comma-separated)' }
    ]
  },
  
  accounting_finance: {
    name: 'Accounting Expert',
    description: 'Expert comptable et financier - analyse, conseil stratégique, écritures comptables',
    icon: '💰',
    IconComponent: DollarSign,
    color: '#dc2626',
    defaultConfig: (providers) => ({
      llm_provider: providers[0]?.name || 'ollama',
      llm_model: 'mistrallite:latest',
      llm_temperature: 0.3,
      accounting_config: {
        domains: ['comptabilite', 'social'],
        auto_summary: true,
        extract_entities: true
      }
    }),
    mcpConfig: {},
    requiredFields: [],
    executeFields: [
      { 
        name: 'mode', 
        label: 'Mode', 
        type: 'select', 
        required: true,
        options: [
          { value: 'accounting_entry', label: 'Accounting Entry' },
          { value: 'strategic_advice', label: 'Strategic Advice' }
        ]
      },
      { name: 'query', label: 'Query/Instructions', type: 'textarea', placeholder: 'Enter invoice details...', required: true }
    ]
  },
  
  travel_expert: {
    name: 'Travel Expert',
    description: 'Planification de voyages personnalisée avec recherche web intégrée',
    icon: '✈️',
    IconComponent: Plane,
    color: '#0ea5e9',
    defaultConfig: (providers) => ({
      llm_provider: providers[0]?.name || 'ollama',
      llm_model: 'mistrallite:latest',
      llm_temperature: 0.4,
      travel_config: {
        search_preferences: {
          budget_aware: true,
          eco_friendly: true,
          accessibility: false
        }
      }
    }),
    mcpConfig: {},
    requiredFields: [],
    executeFields: [
      { 
        name: 'mode', 
        label: 'Mode', 
        type: 'select', 
        required: true,
        options: [
          { value: 'itinerary_planning', label: 'Itinerary Planning' },
          { value: 'destination_search', label: 'Destination Search' },
          { value: 'budget_analysis', label: 'Budget Analysis' }
        ],
        defaultValue: 'itinerary_planning'
      },
      { name: 'query', label: 'Travel Request', type: 'textarea', placeholder: 'Trip to Japan for 2 weeks, couple, budget 4000€...', required: true }
    ]
  },
  
  email_expert: {
    name: 'Email Expert',
    description: 'Gestion intelligente des emails - analyse, rédaction, réponses automatiques',
    icon: '📧',
    IconComponent: Mail,
    color: '#f59e0b',
    defaultConfig: (providers) => ({
      llm_provider: providers[0]?.name || 'ollama',
      llm_model: 'mistrallite:latest',
      llm_temperature: 0.6,
      email_config: {
        email: '',
        password: '',
        imap_host: 'imap.gmail.com',
        imap_port: 993,
        smtp_host: 'smtp.gmail.com',
        smtp_port: 587,
        auto_categorize: true,
        auto_reply_enabled: false,
        signature: 'Cordialement,\\nVotre Assistant IA',
        default_tone: 'professional',
        language: 'fr'
      }
    }),
    mcpConfig: {},
    requiredFields: ['email_config.email', 'email_config.password'],
    executeFields: [
      { 
        name: 'mode', 
        label: 'Email Mode', 
        type: 'select', 
        required: true,
        options: [
          { value: 'send_email', label: 'Send Email' },
          { value: 'send_email_llm', label: 'Send Email (LLM-Generated)' },
          { value: 'analyze_inbox', label: 'Analyze Inbox' }
        ]
      },
      { name: 'to', label: 'To (for send modes)', type: 'text', placeholder: 'recipient@example.com' },
      { name: 'subject', label: 'Subject (for send modes)', type: 'text', placeholder: 'Email subject' },
      { name: 'body', label: 'Body (for send_email)', type: 'textarea', placeholder: 'Email content...' },
      { name: 'instructions', label: 'Instructions (for send_email_llm)', type: 'textarea', placeholder: 'Instructions for LLM...' },
      { name: 'context', label: 'Context (for send_email_llm)', type: 'text', placeholder: 'Additional context' },
      { name: 'limit', label: 'Limit (for analyze_inbox)', type: 'number', placeholder: '20' },
      { name: 'unread_only', label: 'Unread Only (for analyze_inbox)', type: 'checkbox', defaultValue: true },
      { name: 'auto_send', label: 'Auto Send (for send_email_llm)', type: 'checkbox', defaultValue: false }
    ]
  },
  
  websearch: {
    name: 'Web Search Agent',
    description: 'Recherche web avancée avec synthèse par LLM',
    icon: '🔎',
    IconComponent: Search,
    color: '#ec4899',
    defaultConfig: (providers) => ({
      llm_provider: providers[0]?.name || 'ollama',
      llm_model: 'mistrallite:latest',
      llm_temperature: 0.5,
      search_config: {
        max_results: 10,
        language: 'fr',
        safe_search: true,
        use_rag: false
      }
    }),
    mcpConfig: {},
    requiredFields: [],
    executeFields: [
      { name: 'query', label: 'Search Query', type: 'text', placeholder: 'What to search for...', required: true }
    ]
  }
};

// Composant modal d'exécution
const ExecuteAgentModal = ({ agent, agentType, onClose, onExecute }) => {
  const [executeData, setExecuteData] = useState({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    // Initialiser les valeurs par défaut
    const defaults = {};
    agentType.executeFields?.forEach(field => {
      if (field.defaultValue !== undefined) {
        defaults[field.name] = field.defaultValue;
      }
    });
    setExecuteData(defaults);
  }, [agentType]);

  const handleFieldChange = (fieldName, value) => {
    setExecuteData(prev => ({ ...prev, [fieldName]: value }));
  };

  const handleSubmit = async () => {
    setError(null);
    
    // Validation
    const requiredFields = agentType.executeFields?.filter(f => f.required) || [];
    for (const field of requiredFields) {
      if (!executeData[field.name]) {
        setError(`Field "${field.label}" is required`);
        return;
      }
    }

    // Construire input_data selon le type d'agent
    const input_data = {};
    
    // Pour code_generator, structure spéciale
    if (agent.agent_type === 'code_generator') {
      input_data.prompt = executeData.prompt;
      input_data.create_new_files = executeData.create_new_files ?? true;
      input_data.test_mode = executeData.test_mode ?? true;
    }
    // Pour branch_code_review
    else if (agent.agent_type === 'branch_code_review') {
      input_data.branch = executeData.branch;
    }
    // Pour legal_fiscal
    else if (agent.agent_type === 'legal_fiscal') {
      input_data.mode = executeData.mode;
      input_data.query = executeData.query;
      if (executeData.documents) {
        input_data.documents = executeData.documents.split(',').map(d => d.trim()).filter(Boolean);
      }
    }
    // Pour accounting_finance
    else if (agent.agent_type === 'accounting_finance') {
      input_data.mode = executeData.mode;
      input_data.query = executeData.query;
    }
    // Pour travel_expert
    else if (agent.agent_type === 'travel_expert') {
      input_data.mode = executeData.mode || 'itinerary_planning';
      input_data.query = executeData.query;
    }
    // Pour email_expert
    else if (agent.agent_type === 'email_expert') {
      input_data.mode = executeData.mode;
      if (executeData.mode === 'send_email') {
        input_data.to = executeData.to;
        input_data.subject = executeData.subject;
        input_data.body = executeData.body;
      } else if (executeData.mode === 'send_email_llm') {
        input_data.to = executeData.to;
        input_data.subject = executeData.subject;
        input_data.instructions = executeData.instructions;
        input_data.context = executeData.context;
        input_data.auto_send = executeData.auto_send ?? false;
      } else if (executeData.mode === 'analyze_inbox') {
        input_data.limit = parseInt(executeData.limit) || 20;
        input_data.unread_only = executeData.unread_only ?? true;
      }
    }
    // Pour websearch
    else if (agent.agent_type === 'websearch') {
      input_data.query = executeData.query;
    }

    const payload = {
      input_data,
      trigger: 'manual'
    };

    setLoading(true);
    try {
      await onExecute(agent.id, payload);
      onClose();
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Execution failed');
    } finally {
      setLoading(false);
    }
  };

  const renderField = (field) => {
    const value = executeData[field.name] ?? '';

    switch (field.type) {
      case 'textarea':
        return (
          <textarea
            className="form-input"
            value={value}
            onChange={(e) => handleFieldChange(field.name, e.target.value)}
            placeholder={field.placeholder}
            rows={4}
            required={field.required}
          />
        );
      
      case 'checkbox':
        return (
          <label style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-2)' }}>
            <input
              type="checkbox"
              checked={!!value}
              onChange={(e) => handleFieldChange(field.name, e.target.checked)}
            />
            <span>{field.label}</span>
          </label>
        );
      
      case 'select':
        return (
          <select
            className="form-input"
            value={value}
            onChange={(e) => handleFieldChange(field.name, e.target.value)}
            required={field.required}
          >
            <option value="">Select {field.label}</option>
            {field.options?.map(opt => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        );
      
      case 'number':
        return (
          <input
            type="number"
            className="form-input"
            value={value}
            onChange={(e) => handleFieldChange(field.name, e.target.value)}
            placeholder={field.placeholder}
            required={field.required}
          />
        );
      
      default: // text
        return (
          <input
            type="text"
            className="form-input"
            value={value}
            onChange={(e) => handleFieldChange(field.name, e.target.value)}
            placeholder={field.placeholder}
            required={field.required}
          />
        );
    }
  };

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      backgroundColor: 'rgba(0, 0, 0, 0.6)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 1000,
      padding: 'var(--spacing-4)'
    }}>
      <div className="card" style={{ 
        width: '100%', 
        maxWidth: '700px',
        maxHeight: '90vh',
        overflow: 'auto'
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--spacing-4)' }}>
          <h2 style={{ fontSize: 'var(--text-2xl)', fontWeight: '600' }}>
            Execute {agent.name}
          </h2>
          <button
            onClick={onClose}
            style={{
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              padding: 'var(--spacing-2)',
              color: 'var(--gray-600)'
            }}
          >
            <X size={20} />
          </button>
        </div>

        <p style={{ color: 'var(--gray-600)', marginBottom: 'var(--spacing-6)' }}>
          Configure the execution parameters below
        </p>

        {error && (
          <Alert type="error" style={{ marginBottom: 'var(--spacing-4)' }} onClose={() => setError(null)}>
            {error}
          </Alert>
        )}

        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-4)' }}>
          {agentType.executeFields?.map(field => {
            // Skip conditional fields
            if (field.name === 'to' || field.name === 'subject' || field.name === 'body' || 
                field.name === 'instructions' || field.name === 'context' || 
                field.name === 'limit' || field.name === 'unread_only' || field.name === 'auto_send') {
              const mode = executeData.mode;
              if (agent.agent_type === 'email_expert') {
                if (mode === 'send_email' && !['to', 'subject', 'body'].includes(field.name)) return null;
                if (mode === 'send_email_llm' && !['to', 'subject', 'instructions', 'context', 'auto_send'].includes(field.name)) return null;
                if (mode === 'analyze_inbox' && !['limit', 'unread_only'].includes(field.name)) return null;
              }
            }

            return (
              <div key={field.name} className="form-group">
                {field.type !== 'checkbox' && (
                  <label className="form-label">
                    {field.label} {field.required && '*'}
                  </label>
                )}
                {renderField(field)}
              </div>
            );
          })}
        </div>

        <div style={{
          display: 'flex',
          gap: 'var(--spacing-3)',
          justifyContent: 'flex-end',
          marginTop: 'var(--spacing-6)',
          paddingTop: 'var(--spacing-4)',
          borderTop: '1px solid var(--gray-200)'
        }}>
          <Button variant="ghost" onClick={onClose} disabled={loading}>
            Cancel
          </Button>
          <Button variant="primary" onClick={handleSubmit} disabled={loading} icon={Play}>
            {loading ? 'Executing...' : 'Execute Agent'}
          </Button>
        </div>
      </div>
    </div>
  );
};

const Agents = () => {
  const [agents, setAgents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showExecuteModal, setShowExecuteModal] = useState(false);
  const [selectedAgentType, setSelectedAgentType] = useState(null);
  const [selectedAgent, setSelectedAgent] = useState(null);
  const [providers, setProviders] = useState([]);
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    agent_type: '',
    config: {},
    mcp_config: {}
  });

  useEffect(() => {
    loadAgents();
    loadProviders();
  }, []);

  const loadAgents = async () => {
    try {
      setLoading(true);
      const response = await api.get('/api/agents/');
      setAgents(response.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load agents');
    } finally {
      setLoading(false);
    }
  };

  const loadProviders = async () => {
    try {
      const response = await api.get('/api/providers/');
      setProviders(response.data.filter(p => p.is_active));
    } catch (err) {
      console.error('Failed to load providers:', err);
    }
  };

  const handleCreateAgent = () => {
    setShowCreateModal(true);
    setSelectedAgentType(null);
    setFormData({
      name: '',
      description: '',
      agent_type: '',
      config: {},
      mcp_config: {}
    });
    setError(null);
    setSuccess(null);
  };

  const selectAgentType = (type) => {
    setSelectedAgentType(type);
    const agentType = AGENT_TYPES[type];
    
    setFormData({
      name: '',
      description: agentType.description,
      agent_type: type,
      config: agentType.defaultConfig(providers),
      mcp_config: agentType.mcpConfig
    });
  };

  const validateForm = () => {
    if (!formData.name.trim()) {
      setError('Agent name is required');
      return false;
    }

    const agentType = AGENT_TYPES[selectedAgentType];
    for (const field of agentType.requiredFields) {
      const value = field.split('.').reduce((obj, key) => obj?.[key], 
        field.startsWith('github') ? formData.mcp_config : formData.config
      );
      
      if (!value || value.trim() === '') {
        setError(`Field ${field} is required`);
        return false;
      }
    }

    return true;
  };

  const handleSubmit = async () => {
    if (!validateForm()) return;

    try {
      await api.post('/api/agents/', formData);
      setSuccess('Agent created successfully!');
      setTimeout(() => {
        setShowCreateModal(false);
        loadAgents();
        setSuccess(null);
      }, 1500);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create agent');
    }
  };

  const toggleAgent = async (agentId) => {
    try {
      await api.patch(`/api/agents/${agentId}/toggle`);
      setSuccess('Agent status updated');
      setTimeout(() => setSuccess(null), 2000);
      loadAgents();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to toggle agent');
    }
  };

  const deleteAgent = async (agentId) => {
    if (!confirm('Are you sure you want to delete this agent?')) return;
    
    try {
      await api.delete(`/api/agents/${agentId}`);
      setSuccess('Agent deleted successfully');
      setTimeout(() => setSuccess(null), 2000);
      loadAgents();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to delete agent');
    }
  };

  const handleExecuteAgent = (agent) => {
    setSelectedAgent(agent);
    setShowExecuteModal(true);
  };

  const executeAgent = async (agentId, payload) => {
    try {
      const response = await api.post(`/api/agents/${agentId}/execute`, payload);
      
      setSuccess('Agent execution started successfully!');
      
      // L'utilisateur a mentionné que la sauvegarde dans Chat.jsx est déjà gérée
      // On peut optionnellement stocker localement l'execution_id pour référence
      const executionId = response.data.execution_id;
      console.log('Execution started:', executionId);
      
      // Recharger les agents pour mettre à jour le compteur d'exécutions
      setTimeout(() => {
        loadAgents();
        setSuccess(null);
      }, 2000);
      
    } catch (err) {
      throw err; // Sera géré par ExecuteAgentModal
    }
  };

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

  if (loading) return <Layout><Loading /></Layout>;

  return (
    <Layout>
      <div style={{ padding: 'var(--spacing-6)', maxWidth: '1400px', margin: '0 auto' }}>
        {/* Header */}
        <div style={{ 
          display: 'flex', 
          justifyContent: 'space-between', 
          alignItems: 'center',
          marginBottom: 'var(--spacing-6)'
        }}>
          <div>
            <h1 style={{ fontSize: 'var(--text-3xl)', fontWeight: '700', marginBottom: 'var(--spacing-2)' }}>
              🤖 AI Agents
            </h1>
            <p style={{ color: 'var(--gray-600)' }}>
              Create and manage specialized AI agents for different tasks
            </p>
          </div>
          <Button
            variant="primary"
            onClick={handleCreateAgent}
            icon={Plus}
          >
            New Agent
          </Button>
        </div>

        {/* Alerts */}
        {error && (
          <Alert type="error" style={{ marginBottom: 'var(--spacing-4)' }} onClose={() => setError(null)}>
            {error}
          </Alert>
        )}
        {success && (
          <Alert type="success" style={{ marginBottom: 'var(--spacing-4)' }} onClose={() => setSuccess(null)}>
            {success}
          </Alert>
        )}

        {/* Agents Grid */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(380px, 1fr))',
          gap: 'var(--spacing-4)'
        }}>
          {agents.map(agent => {
            const agentType = AGENT_TYPES[agent.agent_type];
            return (
              <div key={agent.id} className="card" style={{ position: 'relative', borderColor: agentType?.color }}>
                {/* Status Badge */}
                <div style={{
                  position: 'absolute',
                  top: 'var(--spacing-3)',
                  right: 'var(--spacing-3)'
                }}>
                  {agent.is_active ? (
                    <Power size={20} style={{ color: 'var(--success)' }} />
                  ) : (
                    <PowerOff size={20} style={{ color: 'var(--gray-400)' }} />
                  )}
                </div>

                {/* Agent Header */}
                <div style={{ marginBottom: 'var(--spacing-4)' }}>
                  <div style={{ 
                    display: 'flex',
                    alignItems: 'center',
                    gap: 'var(--spacing-3)',
                    marginBottom: 'var(--spacing-3)'
                  }}>
                    <div style={{ color: agentType?.color }}>
                      {agentType ? (
                        <agentType.IconComponent size={32} />
                      ) : (
                        <span style={{ fontSize: '2rem' }}>🤖</span>
                      )}
                    </div>
                    <div style={{ flex: 1 }}>
                      <h3 style={{ 
                        fontSize: 'var(--text-xl)', 
                        fontWeight: '600',
                        marginBottom: 'var(--spacing-1)'
                      }}>
                        {agent.name}
                      </h3>
                      <p style={{ 
                        fontSize: 'var(--text-sm)', 
                        color: 'var(--gray-600)'
                      }}>
                        {agentType?.name || agent.agent_type}
                      </p>
                    </div>
                  </div>
                </div>

                {/* Stats */}
                <div style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(3, 1fr)',
                  gap: 'var(--spacing-3)',
                  padding: 'var(--spacing-3)',
                  backgroundColor: 'var(--gray-50)',
                  borderRadius: 'var(--radius)',
                  marginBottom: 'var(--spacing-4)'
                }}>
                  <div style={{ textAlign: 'center' }}>
                    <Activity size={18} style={{ color: agentType?.color, marginBottom: 'var(--spacing-1)' }} />
                    <div style={{ fontSize: 'var(--text-lg)', fontWeight: '600' }}>
                      {agent.execution_count || 0}
                    </div>
                    <div style={{ fontSize: 'var(--text-xs)', color: 'var(--gray-600)' }}>
                      Executions
                    </div>
                  </div>
                  <div style={{ textAlign: 'center' }}>
                    <Clock size={18} style={{ color: agentType?.color, marginBottom: 'var(--spacing-1)' }} />
                    <div style={{ fontSize: 'var(--text-sm)', fontWeight: '600' }}>
                      {new Date(agent.updated_at).toLocaleDateString()}
                    </div>
                    <div style={{ fontSize: 'var(--text-xs)', color: 'var(--gray-600)' }}>
                      Last Update
                    </div>
                  </div>
                  <div style={{ textAlign: 'center' }}>
                    {agent.is_active ? (
                      <CheckCircle size={18} style={{ color: 'var(--success)', marginBottom: 'var(--spacing-1)' }} />
                    ) : (
                      <XCircle size={18} style={{ color: 'var(--gray-400)', marginBottom: 'var(--spacing-1)' }} />
                    )}
                    <div style={{ fontSize: 'var(--text-sm)', fontWeight: '600' }}>
                      {agent.is_active ? 'Active' : 'Disabled'}
                    </div>
                    <div style={{ fontSize: 'var(--text-xs)', color: 'var(--gray-600)' }}>
                      Status
                    </div>
                  </div>
                </div>

                {/* Actions */}
                <div style={{ 
                  display: 'flex', 
                  gap: 'var(--spacing-2)',
                  justifyContent: 'flex-end'
                }}>
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={() => handleExecuteAgent(agent)}
                    icon={Play}
                    disabled={!agent.is_active}
                  >
                    Execute
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => toggleAgent(agent.id)}
                  >
                    {agent.is_active ? 'Disable' : 'Enable'}
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => deleteAgent(agent.id)}
                    icon={Trash2}
                  >
                    Delete
                  </Button>
                </div>
              </div>
            );
          })}
        </div>

        {/* Empty State */}
        {agents.length === 0 && (
          <div style={{
            textAlign: 'center',
            padding: 'var(--spacing-12)',
            color: 'var(--gray-600)'
          }}>
            <div style={{ fontSize: '5rem', marginBottom: 'var(--spacing-4)' }}>🤖</div>
            <h3 style={{ fontSize: 'var(--text-2xl)', fontWeight: '600', marginBottom: 'var(--spacing-2)' }}>
              No agents yet
            </h3>
            <p style={{ marginBottom: 'var(--spacing-4)' }}>
              Create your first AI agent to automate tasks and enhance productivity
            </p>
            <Button variant="primary" onClick={handleCreateAgent} icon={Plus}>
              Create Your First Agent
            </Button>
          </div>
        )}

        {/* Execute Agent Modal */}
        {showExecuteModal && selectedAgent && (
          <ExecuteAgentModal
            agent={selectedAgent}
            agentType={AGENT_TYPES[selectedAgent.agent_type]}
            onClose={() => {
              setShowExecuteModal(false);
              setSelectedAgent(null);
            }}
            onExecute={executeAgent}
          />
        )}

        {/* Create Agent Modal */}
        {showCreateModal && (
          <div style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.6)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
            padding: 'var(--spacing-4)'
          }}>
            <div className="card" style={{ 
              width: '100%', 
              maxWidth: '900px',
              maxHeight: '90vh',
              overflow: 'auto'
            }}>
              <h2 style={{ 
                fontSize: 'var(--text-2xl)', 
                fontWeight: '600',
                marginBottom: 'var(--spacing-2)'
              }}>
                {selectedAgentType ? `Configure ${AGENT_TYPES[selectedAgentType].name}` : 'Select Agent Type'}
              </h2>
              
              {selectedAgentType && (
                <p style={{ color: 'var(--gray-600)', marginBottom: 'var(--spacing-6)' }}>
                  {AGENT_TYPES[selectedAgentType].description}
                </p>
              )}

              {!selectedAgentType ? (
                /* Agent Type Selection */
                <div style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))',
                  gap: 'var(--spacing-4)'
                }}>
                  {Object.entries(AGENT_TYPES).map(([type, info]) => (
                    <div
                      key={type}
                      onClick={() => selectAgentType(type)}
                      className="card"
                      style={{
                        cursor: 'pointer',
                        textAlign: 'center',
                        padding: 'var(--spacing-5)',
                        transition: 'all 0.2s',
                        borderColor: info.color
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.borderColor = info.color;
                        e.currentTarget.style.transform = 'translateY(-4px)';
                        e.currentTarget.style.boxShadow = `0 4px 12px ${info.color}20`;
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.borderColor = 'var(--gray-200)';
                        e.currentTarget.style.transform = 'translateY(0)';
                        e.currentTarget.style.boxShadow = 'none';
                      }}
                    >
                      <div style={{ color: info.color, marginBottom: 'var(--spacing-3)' }}>
                        <info.IconComponent size={32} />
                      </div>
                      <h3 style={{ fontWeight: '600', marginBottom: 'var(--spacing-2)', fontSize: 'var(--text-lg)' }}>
                        {info.name}
                      </h3>
                      <p style={{ fontSize: 'var(--text-sm)', color: 'var(--gray-600)', lineHeight: '1.5' }}>
                        {info.description}
                      </p>
                    </div>
                  ))}
                </div>
              ) : (
                /* Agent Configuration Form */
                <div>
                  {error && (
                    <Alert type="error" style={{ marginBottom: 'var(--spacing-4)' }} onClose={() => setError(null)}>
                      {error}
                    </Alert>
                  )}
                  {success && (
                    <Alert type="success" style={{ marginBottom: 'var(--spacing-4)' }}>
                      {success}
                    </Alert>
                  )}

                  <div className="form-group">
                    <label className="form-label">Agent Name *</label>
                    <input
                      type="text"
                      className="form-input"
                      value={formData.name}
                      onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                      placeholder={`My ${AGENT_TYPES[selectedAgentType].name}`}
                    />
                  </div>

                  <div className="form-group">
                    <label className="form-label">Description</label>
                    <textarea
                      className="form-input"
                      value={formData.description || ''}
                      onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                      placeholder="Optional description"
                      rows={2}
                    />
                  </div>

                  {/* LLM Configuration */}
                  <div style={{ 
                    padding: 'var(--spacing-4)', 
                    backgroundColor: 'var(--gray-50)', 
                    borderRadius: 'var(--radius)',
                    marginBottom: 'var(--spacing-4)'
                  }}>
                    <h3 style={{ fontWeight: '600', marginBottom: 'var(--spacing-3)' }}>LLM Configuration</h3>
                    
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 'var(--spacing-3)' }}>
                      <div className="form-group">
                        <label className="form-label">Provider</label>
                        <select
                          className="form-input"
                          value={formData.config.llm_provider}
                          onChange={(e) => updateConfigField('config.llm_provider', e.target.value)}
                        >
                          {providers.map(p => (
                            <option key={p.name} value={p.name}>{p.name}</option>
                          ))}
                        </select>
                      </div>

                      <div className="form-group">
                        <label className="form-label">Model</label>
                        <input
                          type="text"
                          className="form-input"
                          value={formData.config.llm_model}
                          onChange={(e) => updateConfigField('config.llm_model', e.target.value)}
                        />
                      </div>

                      <div className="form-group">
                        <label className="form-label">Temperature</label>
                        <input
                          type="number"
                          step="0.1"
                          min="0"
                          max="2"
                          className="form-input"
                          value={formData.config.llm_temperature}
                          onChange={(e) => updateConfigField('config.llm_temperature', parseFloat(e.target.value))}
                        />
                      </div>
                    </div>
                  </div>

                  {/* Agent-Specific Configuration */}
                  {(['branch_code_review', 'code_generator'].includes(selectedAgentType)) && (
                    <div style={{ 
                      padding: 'var(--spacing-4)', 
                      backgroundColor: 'var(--gray-50)', 
                      borderRadius: 'var(--radius)',
                      marginBottom: 'var(--spacing-4)'
                    }}>
                      <h3 style={{ fontWeight: '600', marginBottom: 'var(--spacing-3)' }}>GitHub Configuration</h3>
                      
                      <div className="form-group">
                        <label className="form-label">GitHub Token * <span style={{fontSize: 'var(--text-xs)', color: 'var(--gray-500)'}}>Required for code operations</span></label>
                        <input
                          type="password"
                          className="form-input"
                          value={formData.mcp_config.github?.token || ''}
                          onChange={(e) => updateConfigField('mcp_config.github.token', e.target.value)}
                          placeholder="ghp_..."
                        />
                      </div>
                      
                      <div className="form-group">
                        <label className="form-label">Repository * <span style={{fontSize: 'var(--text-xs)', color: 'var(--gray-500)'}}>Format: username/repo</span></label>
                        <input
                          type="text"
                          className="form-input"
                          value={formData.mcp_config.github?.repo || ''}
                          onChange={(e) => updateConfigField('mcp_config.github.repo', e.target.value)}
                          placeholder="username/repository"
                        />
                      </div>
                    </div>
                  )}

                  {selectedAgentType === 'email_expert' && (
                    <div style={{ 
                      padding: 'var(--spacing-4)', 
                      backgroundColor: 'var(--gray-50)', 
                      borderRadius: 'var(--radius)',
                      marginBottom: 'var(--spacing-4)'
                    }}>
                      <h3 style={{ fontWeight: '600', marginBottom: 'var(--spacing-3)' }}>Email Configuration</h3>
                      
                      <div className="form-group">
                        <label className="form-label">Email Address *</label>
                        <input
                          type="email"
                          className="form-input"
                          value={formData.config.email_config?.email || ''}
                          onChange={(e) => updateConfigField('config.email_config.email', e.target.value)}
                          placeholder="your.email@gmail.com"
                        />
                      </div>
                      
                      <div className="form-group">
                        <label className="form-label">App Password * <span style={{fontSize: 'var(--text-xs)', color: 'var(--gray-500)'}}>Use app-specific password, not your main password</span></label>
                        <input
                          type="password"
                          className="form-input"
                          value={formData.config.email_config?.password || ''}
                          onChange={(e) => updateConfigField('config.email_config.password', e.target.value)}
                          placeholder="App-specific password"
                        />
                      </div>
                    </div>
                  )}

                  {/* Actions */}
                  <div style={{
                    display: 'flex',
                    gap: 'var(--spacing-3)',
                    justifyContent: 'space-between',
                    marginTop: 'var(--spacing-6)',
                    paddingTop: 'var(--spacing-4)',
                    borderTop: '1px solid var(--gray-200)'
                  }}>
                    <Button
                      variant="ghost"
                      onClick={() => setSelectedAgentType(null)}
                    >
                      ← Back
                    </Button>
                    
                    <div style={{ display: 'flex', gap: 'var(--spacing-2)' }}>
                      <Button
                        variant="ghost"
                        onClick={() => {
                          setShowCreateModal(false);
                          setSelectedAgentType(null);
                        }}
                      >
                        Cancel
                      </Button>
                      <Button
                        variant="primary"
                        onClick={handleSubmit}
                        disabled={!formData.name.trim()}
                        icon={Plus}
                      >
                        Create Agent
                      </Button>
                    </div>
                  </div>
                </div>
              )}

              {!selectedAgentType && (
                <div style={{ 
                  display: 'flex', 
                  justifyContent: 'flex-end', 
                  marginTop: 'var(--spacing-6)',
                  paddingTop: 'var(--spacing-4)',
                  borderTop: '1px solid var(--gray-200)' 
                }}>
                  <Button
                    variant="ghost"
                    onClick={() => setShowCreateModal(false)}
                  >
                    Cancel
                  </Button>
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