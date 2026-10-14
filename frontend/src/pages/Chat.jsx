import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Send, Loader2, Plus, Trash2, MessageSquare, FileText, Mic, Settings, Copy, Check, RotateCcw, Download, Maximize2, Minimize2 } from 'lucide-react';
import { User, Bot } from 'lucide-react';
import Layout from '../components/layout/Layout';
import Loading from '../components/common/Loading';
import Button from '../components/common/Button';
import MessageItem from '../components/chat/MessageItem';
import { useChatStore } from '../store/chatStore';
import { StreamingService } from '../services/streaming';
import api from '../services/api';
import ExportButton from '../components/common/ExportButton';
import ExportHistory from '../components/common/ExportHistory';
/*add new featur for */

const SUGGESTIONS = [
  { title: 'Summarize', hint: 'Condense a text or document', prompt: 'Summarize the following text in 5 bullet points:\n\n' },
  { title: 'Explain', hint: 'Break a concept down step by step', prompt: 'Explain the following concept simply, with an example:\n\n' },
  { title: 'Write code', hint: 'Generate or fix a script', prompt: 'Write a script that does the following, with comments:\n\n' },
  { title: 'Plan', hint: 'Structure a project or a task', prompt: 'Create a step-by-step plan for the following goal:\n\n' },
];

const Chat = () => {
  const textareaRef = useRef(null);
  const [showSettings, setShowSettings] = useState(false);
  const [showExportHistory, setShowExportHistory] = useState(false);
  const { id } = useParams();
  const navigate = useNavigate();
  const { 
    conversations,
    currentConversation, 
    messages, 
    loadConversations,
    loadConversation, 
    createConversation,
    deleteConversation,
    addMessage, 
    updateLastMessage, 
    setStreaming, 
    streaming 
  } = useChatStore();


  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [copiedIndex, setCopiedIndex] = useState(null);
  const [providers, setProviders] = useState([]);
  const [models, setModels] = useState([]);
  
  // NOUVEAUX Ãƒâ€°TATS TEMPLATES
  const [templates, setTemplates] = useState([]);
  const [selectedTemplate, setSelectedTemplate] = useState(null);
  const [showTemplateModal, setShowTemplateModal] = useState(false);
  const [templateVariables, setTemplateVariables] = useState({});
  
  const [chatSettings, setChatSettings] = useState({
    provider_name: 'ollama',
    model: 'llama2',
    temperature: 0.7,
    reasoning_mode: 'standard'
  });
  const [promptExpanded, setPromptExpanded] = useState(false);
  const stickRef = useRef(true);
  const messagesEndRef = useRef(null);
  const streamingService = useRef(new StreamingService());

// New for chat here
  const autoResizeTextarea = (textarea) => {
    textarea.style.height = 'auto';
    textarea.style.height = `${textarea.scrollHeight}px`;
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (input.trim() && !streaming) handleSend();
    }
  };

  useEffect(() => {
    if (textareaRef.current && input) autoResizeTextarea(textareaRef.current);
  }, [promptExpanded]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!input && textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  }, [input]);

  // new for chat.

  // Load conversations + templates on mount
  useEffect(() => {
    loadConversations();
    loadProviders();
    loadTemplates(); // NOUVEAU
  }, []);

  // NOUVELLE FONCTION - Charger templates
  const loadTemplates = async () => {
    try {
      const response = await api.get('/api/templates/');
      setTemplates(response.data);
    } catch (error) {
      console.error('Failed to load templates:', error);
    }
  };

  // NOUVELLE FONCTION - SÃƒÂ©lectionner template
  const handleSelectTemplate = (template) => {
    setSelectedTemplate(template);
    
    if (template.variables && template.variables.length > 0) {
      // Template avec variables Ã¢â€ â€™ ouvrir modal
      const initialVars = {};
      template.variables.forEach(v => initialVars[v] = '');
      setTemplateVariables(initialVars);
      setShowTemplateModal(true);
    } else {
      // Template sans variables Ã¢â€ â€™ insÃƒÂ©rer directement
      setInput(template.content);
    }
  };

  // NOUVELLE FONCTION - Appliquer template avec variables
  const handleApplyTemplate = async () => {
    try {
      const response = await api.post(`/api/templates/${selectedTemplate.id}/render`, {
        variables: templateVariables
      });
      setInput(response.data.rendered_content);
      setShowTemplateModal(false);
      setSelectedTemplate(null);
      setTemplateVariables({});
    } catch (error) {
      console.error('Failed to render template:', error);
      alert(error.response?.data?.detail || 'Failed to render template');
    }
  };

  // Load specific conversation if id is provided, OR redirect to latest conversation
  useEffect(() => {
    if (id) {
      console.log('Loading conversation:', id);
      loadConversation(id);
    } else if (conversations.length > 0 && !id) {
      const latestConv = conversations[0];
      if (latestConv && latestConv.id) {
        navigate(`/chat/${latestConv.id}`, { replace: true });
      }
    }
  }, [id, conversations]);

  // Update chat settings when conversation changes (only on initial load)
  const initialConversationId = useRef(null);
  
  useEffect(() => {
    if (currentConversation) {
      // Ne charge les settings QUE si c'est une nouvelle conversation
      if (initialConversationId.current !== currentConversation.id) {
        console.log('Current conversation loaded:', currentConversation);
        setChatSettings({
          provider_name: currentConversation.provider_name,
          model: currentConversation.model,
          temperature: currentConversation.temperature,
          reasoning_mode: currentConversation.reasoning_mode
        });
        initialConversationId.current = currentConversation.id;
      }
    }
  }, [currentConversation]);

  // Auto-scroll : instantané, et seulement si l'utilisateur n'a pas remonté la conversation
  useEffect(() => {
    if (stickRef.current) messagesEndRef.current?.scrollIntoView({ block: 'end' });
  }, [messages]);

  const handleMessagesScroll = (e) => {
    const el = e.currentTarget;
    stickRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 120;
  };

  // Load models when provider changes
  useEffect(() => {
    if (chatSettings.provider_name) {
      loadModels(chatSettings.provider_name);
    }
  }, [chatSettings.provider_name]);


  const loadProviders = async () => {
    try {
      const response = await api.get('/api/providers/');
      const activeProviders = response.data.filter(p => p.is_active);
      setProviders(activeProviders);
      
      if (activeProviders.length > 0 && !currentConversation) {
        const firstProvider = activeProviders[0];
        setChatSettings(prev => ({
          ...prev,
          provider_name: firstProvider.name
        }));
      }
    } catch (error) {
      console.error('Failed to load providers:', error);
    }
  };

  const loadModels = async (providerName) => {
    try {
      const response = await api.get(`/api/providers/${providerName}/models`);
      const availableModels = response.data.models || [];  // ← CHANGÉ ICI
      setModels(availableModels);
      
      // Change le modèle si: pas de modèle OU modèle invalide pour ce provider
      if (availableModels.length > 0) {
        const currentModelValid = availableModels.includes(chatSettings.model);
        if (!chatSettings.model || !currentModelValid) {
          setChatSettings(prev => ({
            ...prev,
            model: availableModels[0]
          }));
        }
      }
    } catch (error) {
      console.error('Failed to load models:', error);
    }
  };

  const handleNewChat = async () => {
    try {
      const newConv = await createConversation({
        title: 'New Conversation',
        provider_name: chatSettings.provider_name,
        model: chatSettings.model,
        temperature: chatSettings.temperature,
        reasoning_mode: chatSettings.reasoning_mode
      });
      navigate(`/chat/${newConv.id}`);
    } catch (error) {
      console.error('Failed to create conversation:', error);
    }
  };

  const handleSelectChat = (chatId) => {
    navigate(`/chat/${chatId}`);
  };

  const handleDeleteChat = async (chatId) => {
    if (!confirm('Delete this conversation?')) return;
    
    try {
      await deleteConversation(chatId);
      
      if (id === chatId) {
        navigate('/chat');
      }
    } catch (error) {
      console.error('Failed to delete conversation:', error);
    }
  };

  const handleSend = async () => {
    if (!input.trim() || streaming) return;
    const content = input.trim();
    setInput('');
    await handleSendWithContent(content);
  };

  const handleCopyMessage = async (content, index) => {
    try {
      await navigator.clipboard.writeText(content);
      setCopiedIndex(index);
      setTimeout(() => setCopiedIndex(null), 2000);
    } catch (err) {
      console.error('Copy failed:', err);
    }
  };

  const handleRetryMessage = (message, index) => {
    if (streaming) return;
    if (message.role === 'user') {
      // Re-send the user message
      setInput(message.content);
      setTimeout(() => handleSendWithContent(message.content), 0);
    } else {
      // Re-generate: find the previous user message
      const userMsg = [...messages].slice(0, index).reverse().find(m => m.role === 'user');
      if (userMsg) {
        handleSendWithContent(userMsg.content);
      }
    }
  };

  const handleSendWithContent = async (content) => {
    if (!content.trim() || streaming) return;
    setInput('');

    let conversationId = currentConversation?.id;

    if (!conversationId) {
      try {
        const newConv = await createConversation({
          title: content.substring(0, 50) + (content.length > 50 ? '...' : ''),
          provider_name: chatSettings.provider_name,
          model: chatSettings.model,
          temperature: chatSettings.temperature,
          reasoning_mode: chatSettings.reasoning_mode
        });
        conversationId = newConv.id;
        navigate(`/chat/${newConv.id}`);
      } catch (error) {
        console.error('Failed to create conversation:', error);
        return;
      }
    }

    addMessage({ role: 'user', content, created_at: new Date().toISOString() });
    addMessage({ role: 'assistant', content: '', created_at: new Date().toISOString() });
    setStreaming(true);

    const request = {
      message: content,
      conversation_id: conversationId,
      provider_name: chatSettings.provider_name,
      model: chatSettings.model,
      temperature: chatSettings.temperature,
      reasoning_mode: chatSettings.reasoning_mode
    };

    await streamingService.current.startSSEStream(
      request,
      (chunk) => updateLastMessage(chunk),
      (error) => {
        console.error('Streaming error:', error);
        setStreaming(false);
        streamingService.current.startWebSocketStream(request,
          (chunk) => updateLastMessage(chunk),
          () => setStreaming(false),
          () => setStreaming(false)
        );
      },
      () => { setStreaming(false); loadConversations(); }
    );
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const retryRef = useRef(null);
  retryRef.current = handleRetryMessage;
  const onRetry = useCallback((message, index) => retryRef.current(message, index), []);

  if (id && !currentConversation && loading) {
    return (
      <Layout>
        <Loading message="Loading conversation..." />
      </Layout>
    );
  }

  return (
    <Layout>
      <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - var(--topbar-h))' }}>
        <div style={{ 
          display: 'flex', 
          height: '100%',
          overflow: 'hidden'
        }}>
          {/* Liste des conversations : rail fixe + panneau en overlay (pas de reflow du chat) */}
          <div className="conv-rail">
            <aside className="conv-panel">
              <div className="conv-head">
                <button type="button" className="btn btn-primary conv-new" onClick={handleNewChat} title="New chat">
                  <Plus size={16} />
                  <span className="conv-newlabel">New Chat</span>
                </button>
              </div>

              <div className="conv-list">
                {conversations.map((conv) => (
                  <div
                    key={conv.id}
                    className={`conv-item ${id === conv.id ? 'active' : ''}`}
                    onClick={() => handleSelectChat(conv.id)}
                    title={conv.title}
                  >
                    <MessageSquare size={18} />
                    <div className="conv-meta">
                      <div className="conv-title">{conv.title}</div>
                      <div className="conv-sub">
                        <span>{conv.provider_name}</span>
                        <span>{conv.message_count || 0} msg</span>
                      </div>
                    </div>
                    <button
                      type="button"
                      className="conv-del"
                      title="Delete"
                      onClick={(e) => { e.stopPropagation(); handleDeleteChat(conv.id); }}
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                ))}
              </div>

              <div className="conv-foot">
                {conversations.length} conversation{conversations.length !== 1 ? 's' : ''}
              </div>
            </aside>
          </div>
          {/* Zone de chat principale */}
          <div className="chat-container">
            {/* Messages */}
            <div className="chat-messages" onScroll={handleMessagesScroll}>
              {messages.length === 0 ? (
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '100%', gap: 'var(--spacing-4)', padding: 'var(--spacing-4) 0' }}>
                  <h2 style={{ fontSize: 'var(--text-2xl)', fontWeight: 600, color: 'var(--text-heading)', letterSpacing: '-0.01em' }}>
                    Start a new conversation
                  </h2>
                  <p style={{ color: 'var(--text-muted)', fontSize: 'var(--text-sm)' }}>
                    Using: <span style={{ fontFamily: 'var(--font-mono)' }}>{chatSettings.provider_name} · {chatSettings.model}</span>
                  </p>
                  <div className="suggest-grid">
                    {SUGGESTIONS.map((sg) => (
                      <button
                        key={sg.title}
                        type="button"
                        className="suggest-card"
                        onClick={() => {
                          setInput(sg.prompt);
                          requestAnimationFrame(() => {
                            const t = textareaRef.current;
                            if (t) { t.focus(); autoResizeTextarea(t); t.setSelectionRange(t.value.length, t.value.length); }
                          });
                        }}
                      >
                        <strong>{sg.title}</strong>
                        <span>{sg.hint}</span>
                      </button>
                    ))}
                  </div>
                </div>
              ) : (
                <>
                  {messages.map((message, index) => (
                    <MessageItem
                      key={message.id || index}
                      message={message}
                      index={index}
                      grouped={index > 0 && messages[index - 1].role === message.role}
                      isStreaming={streaming && index === messages.length - 1}
                      busy={streaming}
                      onRetry={onRetry}
                    />
                  ))}
                  <div ref={messagesEndRef} />
                </>
              )}
            </div>
            {/* NEW STLE HERE */}
            {/* Input avec settings */}
            <div className="chat-input-container">
              {/* Conteneur centré */}
              <div style={{ padding: '0 var(--spacing-4)', display: 'flex', justifyContent: 'center' }}>
                <div
                  className={`input-chat-container ${input.trim() ? 'focused' : ''}`}
                  style={{
                    width: '100%',
                    maxWidth: '800px',
                    minWidth: '300px',
                    backgroundColor: 'var(--bg)',
                    borderRadius: 'var(--radius-lg)',
                    /*border: '1px solid var(--gray-200)',*/
                    boxShadow: '0 1px 3px rgba(0, 0, 0, 0.05)',
                    overflow: 'hidden',
                    transition: 'all 0.25s ease',
                  }}
                >
                  {/* === Barre d'actions : Settings + Templates + Delete === */}
                  <div
                    style={{
                      padding: 'var(--spacing-2) var(--spacing-3)',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      borderBottom: '1px solid var(--gray-100)',
                      backgroundColor: 'var(--bg-card)',
                      fontSize: 'var(--text-xs)',
                    }}
                  >
                    <button
                      onClick={() => setShowSettings(!showSettings)}
                      className={`btn-settings ${showSettings ? 'open' : ''}`}
                      style={{ padding: 'var(--spacing-1) var(--spacing-2)' }}
                    >
                      <Settings size={14} className="icon" />
                      {showSettings ? 'Hide' : 'Settings'}
                    </button>

                    <div style={{ display: 'flex', gap: 'var(--spacing-2)' }}>
                      {templates.length > 0 && (
                        <button
                          onClick={() => setShowTemplateModal(true)}
                          className="btn-settings-sm"
                        >
                          <FileText size={14} />
                          Templates
                        </button>
                      )}
                        <button
                          onClick={() => setShowExportHistory(true)}
                          className="btn-settings-sm"
                        >
                          <Download size={14} />
                          Exports
                        </button>
                      {currentConversation && (
                        <button
                          onClick={() => handleDeleteChat(currentConversation.id)}
                          className="btn-settings-sm delete"
                        >
                          <Trash2 size={14} className="icon" />
                          Delete
                        </button>
                      )}
                    </div>
                  </div>

                  {/* === Settings pliables === */}
                  {showSettings && (
                    <div
                      style={{
                        padding: 'var(--spacing-3)',
                        backgroundColor: 'var(--bg-card)',
                        borderBottom: '1px solid var(--gray-100)',
                        display: 'flex',
                        flexWrap: 'wrap',
                        gap: 'var(--spacing-3)',
                        fontSize: 'var(--text-xs)',
                        color: 'var(--gray-600)',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-2)' }}>
                        <span style={{ fontWeight: '500' }}>Provider:</span>
                        <select
                          className="form-select"
                          value={chatSettings.provider_name}
                          onChange={(e) => setChatSettings({ ...chatSettings, provider_name: e.target.value })}
                          style={{ fontSize: 'var(--text-xs)', padding: 'var(--spacing-1) var(--spacing-2)', minWidth: '100px' }}
                        >
                          {providers.map((p) => (
                            <option key={p.id} value={p.name}>{p.name.toUpperCase()}</option>
                          ))}
                        </select>
                      </div>

                      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-2)' }}>
                        <span style={{ fontWeight: '500' }}>Model:</span>
                        <select
                          className="form-select"
                          value={chatSettings.model}
                          onChange={(e) => setChatSettings({ ...chatSettings, model: e.target.value })}
                          style={{ fontSize: 'var(--text-xs)', padding: 'var(--spacing-1) var(--spacing-2)', minWidth: '150px' }}
                        >
                          {models.map((m) => (
                            <option key={m} value={m}>{m}</option>
                          ))}
                        </select>
                      </div>

                      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-2)' }}>
                        <span style={{ fontWeight: '500' }}>Temp: {chatSettings.temperature.toFixed(1)}</span>
                        <input
                          type="range"
                          min="0"
                          max="2"
                          step="0.1"
                          value={chatSettings.temperature}
                          onChange={(e) => setChatSettings({ ...chatSettings, temperature: parseFloat(e.target.value) })}
                          style={{ width: '80px' }}
                        />
                      </div>

                      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-2)' }}>
                        <span style={{ fontWeight: '500' }}>Reasoning:</span>
                        <select
                          className="form-select"
                          value={chatSettings.reasoning_mode}
                          onChange={(e) => setChatSettings({ ...chatSettings, reasoning_mode: e.target.value })}
                          style={{ fontSize: 'var(--text-xs)', padding: 'var(--spacing-1) var(--spacing-2)', minWidth: '120px' }}
                        >
                          <option value="standard">Standard</option>
                          <option value="cot">Chain of Thought</option>
                          <option value="deep">Deep Reasoning</option>
                        </select>
                      </div>
                    </div>
                  )}

                  {/* === Zone de texte === */}
                  <div style={{ position: 'relative', padding: 'var(--spacing-3) var(--spacing-4)' }}>
                    <button
                      type="button"
                      className="prompt-expand"
                      onClick={() => setPromptExpanded((v) => !v)}
                      title={promptExpanded ? 'Reduce' : 'Expand'}
                      aria-label={promptExpanded ? 'Reduce prompt box' : 'Expand prompt box'}
                    >
                      {promptExpanded ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
                    </button>
                    <textarea
                      ref={textareaRef}
                      placeholder="Ask anything..."
                      value={input}
                      onChange={(e) => {
                        setInput(e.target.value);
                        autoResizeTextarea(e.target);
                      }}
                      onKeyDown={handleKeyDown}
                      style={{
                        border: 'none',
                        outline: 'none',
                        background: 'transparent',
                        resize: 'none',
                        fontSize: 'var(--text-base)',
                        lineHeight: '1.5',
                        minHeight: promptExpanded ? '160px' : '52px',
                        maxHeight: promptExpanded ? '60vh' : '220px',
                        width: '100%',
                        padding: '0 28px 0 0',
                        margin: 0,
                      }}
                      rows={promptExpanded ? 6 : 2}
                    />

                    {/* Bouton Micro */}
                    <button className="btn-mic" disabled title="Voice input (soon)">
                      <Mic size={18} />
                    </button>

                    {/* Bouton Send */}
                    <button
                      className="btn-send"
                      onClick={handleSend}
                      disabled={!input.trim() || streaming}
                    >
                      {streaming ? <Loader2 size={18} className="animate-spin" /> : <Send size={18} />}
                    </button>
                  </div>

                  {/* === Indicateur === */}
                  <div
                    style={{
                      padding: '0 var(--spacing-4) var(--spacing-2)',
                      fontSize: 'var(--text-xs)',
                      color: 'var(--gray-500)',
                      textAlign: 'center',
                    }}
                  >
                    {streaming ? 'Generating… you can already type your next message' : 'Press Enter to send • Shift+Enter for new line'}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Modal Templates - INCHANGÉ */}
      {showTemplateModal && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: 'var(--overlay)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
            padding: 'var(--spacing-4)',
          }}
        >
          <div className="card" style={{ width: '100%', maxWidth: '600px', maxHeight: '80vh', overflow: 'auto' }}>
            <h2 style={{ fontSize: 'var(--text-2xl)', fontWeight: '600', marginBottom: 'var(--spacing-6)' }}>
              {selectedTemplate ? 'Fill Template Variables' : 'Select a Template'}
            </h2>

            {!selectedTemplate ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-3)' }}>
                {templates.map((template) => (
                  <div
                    key={template.id}
                    onClick={() => handleSelectTemplate(template)}
                    style={{
                      padding: 'var(--spacing-4)',
                      border: '1px solid var(--gray-200)',
                      borderRadius: 'var(--radius)',
                      cursor: 'pointer',
                      transition: 'var(--transition)',
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.borderColor = 'var(--primary)';
                      e.currentTarget.style.backgroundColor = 'var(--gray-50)';
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.borderColor = 'var(--gray-200)';
                      e.currentTarget.style.backgroundColor = 'var(--bg-card)';
                    }}
                  >
                    <h3 style={{ fontWeight: '600', marginBottom: 'var(--spacing-2)' }}>{template.name}</h3>
                    {template.description && (
                      <p style={{ fontSize: 'var(--text-sm)', color: 'var(--gray-600)', marginBottom: 'var(--spacing-2)' }}>
                        {template.description}
                      </p>
                    )}
                    {template.variables && template.variables.length > 0 && (
                      <div style={{ display: 'flex', gap: 'var(--spacing-1)', flexWrap: 'wrap' }}>
                        {template.variables.map((variable, index) => (
                          <span
                            key={index}
                            style={{
                              fontSize: 'var(--text-xs)',
                              padding: '2px 8px',
                              backgroundColor: 'var(--primary)',
                              color: 'white',
                              borderRadius: 'var(--radius-sm)',
                              fontFamily: 'monospace',
                            }}
                          >
                            {`{{${variable}}}`}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <div>
                <div
                  style={{
                    marginBottom: 'var(--spacing-4)',
                    padding: 'var(--spacing-3)',
                    backgroundColor: 'var(--gray-50)',
                    borderRadius: 'var(--radius)',
                  }}
                >
                  <p style={{ fontSize: 'var(--text-sm)', color: 'var(--gray-700)' }}>{selectedTemplate.content}</p>
                </div>

                {selectedTemplate.variables.map((variable) => (
                  <div key={variable} className="form-group">
                    <label className="form-label">{variable}</label>
                    <input
                      type="text"
                      className="form-input"
                      value={templateVariables[variable] || ''}
                      onChange={(e) =>
                        setTemplateVariables({
                          ...templateVariables,
                          [variable]: e.target.value,
                        })
                      }
                      placeholder={`Enter ${variable}`}
                    />
                  </div>
                ))}

                <div
                  style={{
                    display: 'flex',
                    gap: 'var(--spacing-3)',
                    justifyContent: 'flex-end',
                    marginTop: 'var(--spacing-6)',
                  }}
                >
                  <Button
                    variant="ghost"
                    onClick={() => {
                      setShowTemplateModal(false);
                      setSelectedTemplate(null);
                      setTemplateVariables({});
                    }}
                  >
                    Cancel
                  </Button>
                  <Button
                    variant="primary"
                    onClick={handleApplyTemplate}
                    disabled={Object.values(templateVariables).some((v) => !v.trim())}
                  >
                    Apply Template
                  </Button>
                </div>
              </div>
            )}

            {!selectedTemplate && (
              <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 'var(--spacing-6)' }}>
                <Button
                  variant="ghost"
                  onClick={() => {
                    setShowTemplateModal(false);
                    setSelectedTemplate(null);
                  }}
                >
                  Close
                </Button>
              </div>
            )}
          </div>
        </div>
      )}
      <ExportHistory open={showExportHistory} onClose={() => setShowExportHistory(false)} />
    </Layout>
  );
};

export default Chat;