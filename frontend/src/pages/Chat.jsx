import { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Send, Loader2, Plus, Trash2, MessageSquare, FileText, Mic, Settings } from 'lucide-react';
import { User, Bot } from 'lucide-react';
import Layout from '../components/layout/Layout';
import Loading from '../components/common/Loading';
import Button from '../components/common/Button';
import MarkdownMessage from '../components/common/MarkdownMessage';
import { useChatStore } from '../store/chatStore';
import { StreamingService } from '../services/streaming';
import api from '../services/api';

/*add new featur for */

const Chat = () => {
  const textareaRef = useRef(null);
  const [showSettings, setShowSettings] = useState(false);
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
  const [sidebarExpanded, setSidebarExpanded] = useState(false);
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

  // Auto-scroll to bottom
  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Load models when provider changes
  useEffect(() => {
    if (chatSettings.provider_name) {
      loadModels(chatSettings.provider_name);
    }
  }, [chatSettings.provider_name]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

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

    const userMessage = input.trim();
    setInput('');

    let conversationId = currentConversation?.id;
    
    if (!conversationId) {
      try {
        const newConv = await createConversation({
          title: userMessage.substring(0, 50) + (userMessage.length > 50 ? '...' : ''),
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

    addMessage({
      role: 'user',
      content: userMessage,
      created_at: new Date().toISOString()
    });

    addMessage({
      role: 'assistant',
      content: '',
      created_at: new Date().toISOString()
    });

    setStreaming(true);

    const request = {
      message: userMessage,
      conversation_id: conversationId,
      provider_name: chatSettings.provider_name,
      model: chatSettings.model,
      temperature: chatSettings.temperature,
      reasoning_mode: chatSettings.reasoning_mode
    };

    await streamingService.current.startSSEStream(
      request,
      (chunk) => {
        updateLastMessage(chunk);
      },
      (error) => {
        console.error('Streaming error:', error);
        setStreaming(false);
        streamingService.current.startWebSocketStream(request, 
          (chunk) => updateLastMessage(chunk),
          (error) => {
            console.error('WebSocket error:', error);
            setStreaming(false);
          },
          () => setStreaming(false)
        );
      },
      () => {
        setStreaming(false);
        // Recharge juste la liste pour mettre Ã  jour updated_at
        loadConversations();
      }
    );
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  if (id && !currentConversation && loading) {
    return (
      <Layout>
        <Loading message="Loading conversation..." />
      </Layout>
    );
  }

  return (
    <Layout>
      <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 73px)' }}>
        <div style={{ 
          display: 'flex', 
          height: '100%',
          overflow: 'hidden'
        }}>
          {/* Liste des conversations */}
          <aside 
            style={{ 
              width: sidebarExpanded ? '280px' : '60px',
              borderRight: '1px solid var(--gray-200)',
              display: 'flex',
              flexDirection: 'column',
              /*backgroundColor: 'var(--bg-card)',*/
              transition: 'width 0.3s ease',
              overflow: 'hidden'
            }}
            onMouseEnter={() => setSidebarExpanded(true)}
            onMouseLeave={() => setSidebarExpanded(false)}
          >
            <div style={{ 
              padding: 'var(--spacing-4)', 
              borderBottom: '1px solid var(--gray-200)',
            }}>
              <Button 
                variant="primary" 
                icon={Plus} 
                onClick={handleNewChat}
                style={{ 
                  width: '100%',
                  justifyContent: sidebarExpanded ? 'center' : 'center',
                  padding: sidebarExpanded ? undefined : 'var(--spacing-2)'
                }}
              >
                {sidebarExpanded && 'New Chat'}
              </Button>
            </div>

            <div 
              className="chat-messages"
              style={{ 
                flex: 1, 
                overflowY: 'auto', 
                padding: 'var(--spacing-2)',
                backgroundColor: 'transparent'
            }}>
              {conversations.length === 0 ? (
                sidebarExpanded && (
                  <div style={{ 
                    padding: 'var(--spacing-8)', 
                    textAlign: 'center',
                    color: 'var(--gray-500)' 
                  }}>
                    <p style={{ fontSize: 'var(--text-sm)' }}>No conversations yet</p>
                  </div>
                )
              ) : (
                conversations.map((conv) => (
                  <div
                    key={conv.id}
                    onClick={() => handleSelectChat(conv.id)}
                    style={{
                      padding: sidebarExpanded ? 'var(--spacing-3)' : 'var(--spacing-2)',
                      marginBottom: 'var(--spacing-2)',
                      borderRadius: 'var(--radius)',
                      cursor: 'pointer',
                      backgroundColor: id === conv.id ? 'var(--gray-100)' : 'transparent',
                      border: id === conv.id ? '1px solid var(--primary)' : '1px solid transparent',
                      transition: 'var(--transition)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: sidebarExpanded ? 'space-between' : 'center',
                      gap: 'var(--spacing-2)',
                      minHeight: '40px'
                    }}
                    onMouseEnter={(e) => {
                      if (id !== conv.id) {
                        e.currentTarget.style.backgroundColor = 'var(--gray-50)';
                      }
                    }}
                    onMouseLeave={(e) => {
                      if (id !== conv.id) {
                        e.currentTarget.style.backgroundColor = 'transparent';
                      }
                    }}
                  >
                    {!sidebarExpanded ? (
                      <MessageSquare size={20} style={{ color: id === conv.id ? 'var(--primary)' : 'var(--gray-600)' }} />
                    ) : (
                      <>
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={{ 
                            fontWeight: id === conv.id ? '600' : '500',
                            fontSize: 'var(--text-sm)',
                            color: 'var(--gray-900)',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap',
                            marginBottom: 'var(--spacing-1)'
                          }}>
                            {conv.title}
                          </div>
                          <div style={{ 
                            fontSize: 'var(--text-xs)', 
                            color: 'var(--gray-500)',
                            display: 'flex',
                            gap: 'var(--spacing-2)'
                          }}>
                            <span>{conv.provider_name}</span>
                            <span>{conv.message_count || 0} msg</span>
                          </div>
                        </div>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDeleteChat(conv.id);
                          }}
                          className="btn btn-ghost btn-sm"
                          style={{ 
                            padding: 'var(--spacing-1)',
                            minWidth: 'auto',
                            opacity: 0.6
                          }}
                          onMouseEnter={(e) => {
                            e.currentTarget.style.opacity = 1;
                            e.currentTarget.style.color = 'var(--danger)';
                          }}
                          onMouseLeave={(e) => {
                            e.currentTarget.style.opacity = 0.6;
                            e.currentTarget.style.color = '';
                          }}
                        >
                          <Trash2 size={14} />
                        </button>
                      </>
                    )}
                  </div>
                ))
              )}
            </div>

            {sidebarExpanded && (
              <div style={{ 
                padding: 'var(--spacing-3)', 
                borderTop: '1px solid var(--gray-200)',
                fontSize: 'var(--text-xs)',
                color: 'var(--gray-500)',
                textAlign: 'center',
                backgroundColor: 'var(--bg-card)'
              }}>
                {conversations.length} conversation{conversations.length !== 1 ? 's' : ''}
              </div>
            )}
          </aside>
          {/* Zone de chat principale */}
          <div className="chat-container">
            {/* Messages */}
            <div className="chat-messages">
              {messages.length === 0 ? (
                <div style={{ 
                  display: 'flex', 
                  flexDirection: 'column', 
                  alignItems: 'center', 
                  justifyContent: 'center',
                  height: '100%',
                  gap: 'var(--spacing-4)'
                }}>
                  <h2 style={{ fontSize: 'var(--text-2xl)', fontWeight: '600', color: 'var(--gray-700)' }}>
                    Start a new conversation
                  </h2>
                  <p style={{ color: 'var(--gray-600)', textAlign: 'center', maxWidth: '500px' }}>
                    Ask me anything! I'm here to help with your questions, ideas, and tasks.
                  </p>
                  <p style={{ fontSize: 'var(--text-sm)', color: 'var(--gray-500)' }}>
                    Using: {chatSettings.provider_name} - {chatSettings.model}
                  </p>
                </div>
              ) : (
                <>
                  {messages.map((message, index) => (
                    <div
                      key={message.id || index}
                      className={`
                        chat-message 
                        ${message.role === 'user' ? 'chat-message-user' : ''} 
                        ${index > 0 && messages[index - 1].role === message.role ? 'chat-message-same' : ''}
                      `}
                      style={{ 
                        marginBottom: index > 0 && messages[index - 1].role === message.role 
                          ? '0.5rem' 
                          : 'var(--spacing-4)' 
                      }}
                    >
                      <div className="chat-message-avatar">
                        {message.role === 'user' ? (
                          <User size={20} />
                        ) : (
                          <Bot size={20} />
                        )}
                      </div>
                      <div className="chat-message-content">
                        {message.content ? (
                        <MarkdownMessage 
                            content={message.content} 
                            isStreaming={streaming && index === messages.length - 1}
                          />
                        ) : (
                          <Loader2 className="animate-spin" size={20} style={{ color: 'var(--gray-500)' }} />
                        )}
                      </div>
                    </div>
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
                    <textarea
                      ref={textareaRef}
                      placeholder="Ask anything..."
                      value={input}
                      onChange={(e) => {
                        setInput(e.target.value);
                        autoResizeTextarea(e.target);
                      }}
                      onKeyDown={handleKeyDown}
                      disabled={streaming}
                      style={{
                        border: 'none',
                        outline: 'none',
                        background: 'transparent',
                        resize: 'none',
                        fontSize: 'var(--text-base)',
                        lineHeight: '1.5',
                        minHeight: '24px',
                        maxHeight: '200px',
                        width: '100%',
                        padding: 0,
                        margin: 0,
                      }}
                      rows={1}
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
                    {streaming ? 'LLM.io is thinking...' : 'Press Enter to send • Shift+Enter for new line'}
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
            backgroundColor: 'rgba(0, 0, 0, 0.5)',
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
    </Layout>
  );
};

export default Chat;