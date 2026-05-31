import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Send, Loader2, Plus, Trash2, ArrowLeft, Settings as SettingsIcon, Zap, Copy, Check, RotateCcw, Download } from 'lucide-react';
import { User, Bot } from 'lucide-react';
import Layout from '../components/layout/Layout';
import Loading from '../components/common/Loading';
import Button from '../components/common/Button';
import MarkdownMessage from '../components/common/MarkdownMessage';
import api from '../services/api';
import ExportButton from '../components/common/ExportButton';
import ExportHistory from '../components/common/ExportHistory';

const RAGChat = () => {
  const { projectId } = useParams();
  const navigate = useNavigate();
  const textareaRef = useRef(null);
  const messagesEndRef = useRef(null);

  // FIX: Use a ref to always hold the latest conversationId — avoids stale closure in async stream handler
  const currentConversationIdRef = useRef(null);

  const [project, setProject] = useState(null);
  const [conversations, setConversations] = useState([]);
  const [currentConversation, setCurrentConversation] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [streaming, setStreaming] = useState(false);
  const [loading, setLoading] = useState(true);
  const [copiedIndex, setCopiedIndex] = useState(null);
  const [retrievedChunks, setRetrievedChunks] = useState([]);
  const [showSources, setShowSources] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [showExportHistory, setShowExportHistory] = useState(false);

  const [providers, setProviders] = useState([]);
  const [models, setModels] = useState([]);

  const [chatSettings, setChatSettings] = useState({
    provider_name: 'ollama',
    model: 'llama2',
    temperature: 0.7,
    reasoning_mode: 'standard',
    top_k: 5
  });

  // Detect big model 256K
  const is256KModel = (model) => {
    const largeModels = ['qwen3-coder:30b','mistral-large','phi3:latest','qwen2.5:72b','phi3:14b','gpt-oss:20b','gpt-4-turbo', 'claude-3', 'gemini-1.5', 'llama3.1', 'gemma4:e2b', 'gemma4:e4b', 'deepseek-r1:14b', 'gemma3:27b-it-qat', 'gemma3:27b','gemma4:26b'];
    return largeModels.some(m => model.toLowerCase().includes(m));
  };

  useEffect(() => {
    loadProject();
    loadConversations();
    loadProviders();
  }, [projectId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    if (chatSettings.provider_name) {
      loadModels(chatSettings.provider_name);
    }
  }, [chatSettings.provider_name]);

  // Auto-adjust top_k for large context models
  useEffect(() => {
    if (is256KModel(chatSettings.model) && chatSettings.top_k < 10) {
      setChatSettings(prev => ({ ...prev, top_k: 15 }));
    }
  }, [chatSettings.model]);

  // FIX: Keep ref in sync with state
  useEffect(() => {
    currentConversationIdRef.current = currentConversation?.id ?? null;
  }, [currentConversation]);

  const loadProject = async () => {
    try {
      const res = await api.get(`/api/projects/${projectId}`);
      setProject(res.data);
    } catch (error) {
      console.error('Failed to load project:', error);
      navigate('/projects');
    } finally {
      setLoading(false);
    }
  };

  const loadConversations = async () => {
    try {
      const res = await api.get(`/api/rag/conversations/${projectId}`);
      setConversations(res.data);
    } catch (error) {
      console.error('Failed to load conversations:', error);
    }
  };

  const loadProviders = async () => {
    try {
      const res = await api.get('/api/providers/');
      const activeProviders = res.data.filter(p => p.is_active);
      setProviders(activeProviders);

      if (activeProviders.length > 0) {
        const firstProvider = activeProviders[0];
        setChatSettings(prev => ({ ...prev, provider_name: firstProvider.name }));
      }
    } catch (error) {
      console.error('Failed to load providers:', error);
    }
  };

  const loadModels = async (providerName) => {
    try {
      const res = await api.get(`/api/providers/${providerName}/models`);
      const availableModels = res.data.models || [];
      setModels(availableModels);

      if (availableModels.length > 0) {
        const currentModelValid = availableModels.includes(chatSettings.model);
        if (!chatSettings.model || !currentModelValid) {
          setChatSettings(prev => ({ ...prev, model: availableModels[0] }));
        }
      }
    } catch (error) {
      console.error('Failed to load models:', error);
    }
  };

  // FIX: Full reset — clear both state AND ref
  const handleNewChat = useCallback(() => {
    currentConversationIdRef.current = null;
    setCurrentConversation(null);
    setMessages([]);
    setInput('');
    setRetrievedChunks([]);
    setShowSources(false);
  }, []);

  const handleSelectConversation = async (convId) => {
    try {
      const res = await api.get(`/api/rag/conversation/${convId}`);

      currentConversationIdRef.current = res.data.id;
      setCurrentConversation(res.data);
      setMessages(res.data.messages || []);
      setRetrievedChunks([]);

      setChatSettings({
        provider_name: res.data.provider_name,
        model: res.data.model,
        temperature: res.data.temperature,
        reasoning_mode: res.data.reasoning_mode,
        top_k: res.data.top_k
      });
    } catch (error) {
      console.error('Failed to load conversation:', error);
      alert('Erreur lors du chargement de la conversation');
    }
  };

  const handleDeleteConversation = async (convId) => {
    if (!confirm('Delete this conversation?')) return;

    try {
      await api.delete(`/api/rag/conversations/${convId}`);
      loadConversations();
      if (currentConversation?.id === convId) {
        handleNewChat();
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
      handleSendWithContent(message.content);
    } else {
      const userMsg = [...messages].slice(0, index).reverse().find(m => m.role === 'user');
      if (userMsg) handleSendWithContent(userMsg.content);
    }
  };

  const handleSendWithContent = async (userMessage) => {
    if (!userMessage.trim() || streaming) return;
    setInput('');

    const newUserMsg = { role: 'user', content: userMessage, created_at: new Date().toISOString() };
    setMessages(prev => [...prev, newUserMsg]);
    const placeholderMsg = { role: 'assistant', content: '', created_at: new Date().toISOString() };
    setMessages(prev => [...prev, placeholderMsg]);

    setStreaming(true);
    setRetrievedChunks([]);

    try {
      const response = await fetch(`/api/rag/chat/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        },
        body: JSON.stringify({
          project_id: projectId,
          // FIX: Read from ref — always current, never stale even inside async closure
          conversation_id: currentConversationIdRef.current ?? null,
          message: userMessage,
          provider_name: chatSettings.provider_name,
          model: chatSettings.model,
          temperature: chatSettings.temperature,
          reasoning_mode: chatSettings.reasoning_mode,
          top_k: chatSettings.top_k
        })
      });

      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err.detail || `HTTP ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let fullResponse = '';
      let buffer = '';

      // Parse a single SSE block (lines between two \n\n)
      const parseSSEBlock = async (block) => {
        const lines = block.split('\n');
        let eventType = '';
        let dataStr = '';

        for (const line of lines) {
          if (line.startsWith('event: ')) {
            eventType = line.substring(7).trim();
          } else if (line.startsWith('data: ')) {
            dataStr = line.substring(6).trim();
          }
        }

        if (!eventType || !dataStr) return;

        try {
          const data = JSON.parse(dataStr);

          if (eventType === 'retrieval') {
            setRetrievedChunks(data.chunks || []);

          } else if (eventType === 'message') {
            fullResponse += data.content;
            setMessages(prev => {
              const updated = [...prev];
              updated[updated.length - 1] = {
                ...updated[updated.length - 1],
                content: fullResponse
              };
              return updated;
            });

          } else if (eventType === 'done') {
            if (data.conversation_id && currentConversationIdRef.current === null) {
              currentConversationIdRef.current = data.conversation_id;
              const res = await api.get(`/api/rag/conversation/${data.conversation_id}`);
              setCurrentConversation(res.data);
              loadConversations();
            }

          } else if (eventType === 'error') {
            throw new Error(data.error || 'Stream error');
          }
        } catch (e) {
          if (e.message && !e.message.startsWith('Stream error')) {
            console.error(`Error parsing SSE block [${eventType}]:`, e);
          } else {
            throw e;
          }
        }
      };

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // Split on double-newline (SSE block separator)
        const blocks = buffer.split('\n\n');
        // Last element may be incomplete — keep in buffer
        buffer = blocks.pop() ?? '';

        for (const block of blocks) {
          const trimmed = block.trim();
          if (trimmed) await parseSSEBlock(trimmed);
        }
      }

      // Flush any remaining complete block
      if (buffer.trim()) await parseSSEBlock(buffer.trim());
    } catch (error) {
      console.error('Streaming error:', error);
      // Remove empty placeholder on error
      setMessages(prev => {
        const updated = [...prev];
        if (updated[updated.length - 1]?.content === '') updated.pop();
        return updated;
      });
      alert('Failed to send message: ' + error.message);
    } finally {
      setStreaming(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (input.trim() && !streaming) handleSend();
    }
  };

  const autoResizeTextarea = (textarea) => {
    textarea.style.height = 'auto';
    textarea.style.height = `${textarea.scrollHeight}px`;
  };

  useEffect(() => {
    if (!input && textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  }, [input]);

  if (loading) {
    return (
      <Layout>
        <Loading message="Loading project..." />
      </Layout>
    );
  }

  return (
    <Layout>
      <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 73px)' }}>
        <div style={{ display: 'flex', height: '100%', overflow: 'hidden' }}>
          <aside style={{
            width: '280px',
            borderRight: '1px solid var(--gray-200)',
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden'
          }}>
            <div style={{
              padding: 'var(--spacing-4)',
              borderBottom: '1px solid var(--gray-200)',
            }}>
              <Button
                variant="ghost"
                icon={ArrowLeft}
                onClick={() => navigate('/projects')}
                style={{ width: '100%', marginBottom: 'var(--spacing-2)' }}
              >
                Back to Projects
              </Button>
              <Button
                variant="primary"
                icon={Plus}
                onClick={handleNewChat}
                style={{ width: '100%' }}
              >
                New Chat
              </Button>
            </div>

            <div style={{
              padding: 'var(--spacing-3)',
              borderBottom: '1px solid var(--gray-200)',
              backgroundColor: 'var(--gray-50)'
            }}>
              <h3 style={{ fontSize: 'var(--text-sm)', fontWeight: '600', marginBottom: 'var(--spacing-1)' }}>
                {project?.name}
              </h3>
              <p style={{ fontSize: 'var(--text-xs)', color: 'var(--gray-600)' }}>
                RAG Chat with Documents
              </p>
            </div>

            <div className="chat-messages" style={{
              flex: 1,
              overflowY: 'auto',
              padding: 'var(--spacing-2)',
              backgroundColor: 'transparent'
            }}>
              {conversations.map((conv) => (
                <div
                  key={conv.id}
                  onClick={() => handleSelectConversation(conv.id)}
                  style={{
                    padding: 'var(--spacing-3)',
                    marginBottom: 'var(--spacing-2)',
                    borderRadius: 'var(--radius)',
                    cursor: 'pointer',
                    backgroundColor: currentConversation?.id === conv.id ? 'var(--gray-100)' : 'transparent',
                    border: currentConversation?.id === conv.id ? '1px solid var(--primary)' : '1px solid transparent',
                    transition: 'var(--transition)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    gap: 'var(--spacing-2)'
                  }}
                >
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{
                      fontWeight: '500',
                      fontSize: 'var(--text-sm)',
                      color: 'var(--gray-900)',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                      marginBottom: 'var(--spacing-1)'
                    }}>
                      {conv.title}
                    </div>
                    <div style={{ fontSize: 'var(--text-xs)', color: 'var(--gray-500)' }}>
                      {conv.provider_name} - {conv.model}
                    </div>
                  </div>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDeleteConversation(conv.id);
                    }}
                    className="btn btn-ghost btn-sm"
                    style={{ padding: 'var(--spacing-1)', minWidth: 'auto' }}
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              ))}
            </div>
          </aside>

          <div className="chat-container">
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
                    Chat with your documents
                  </h2>
                  <p style={{ color: 'var(--gray-600)', textAlign: 'center', maxWidth: '500px' }}>
                    Ask questions about the documents in <strong>{project?.name}</strong>.
                    I'll search through your documents and provide accurate answers with sources.
                  </p>
                  {is256KModel(chatSettings.model) && (
                    <div style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 'var(--spacing-2)',
                      padding: 'var(--spacing-2) var(--spacing-3)',
                      backgroundColor: 'var(--primary)',
                      color: 'white',
                      borderRadius: 'var(--radius-full)',
                      fontSize: 'var(--text-xs)',
                      fontWeight: '600'
                    }}>
                      <Zap size={14} />
                      128K Context Active
                    </div>
                  )}
                </div>
              ) : (
                <>
                  {messages.map((message, index) => (
                    <div
                      key={index}
                      className={`chat-message ${message.role === 'user' ? 'chat-message-user' : ''}`}
                      style={{ marginBottom: 'var(--spacing-4)' }}
                    >
                      <div className="chat-message-avatar">
                        {message.role === 'user' ? <User size={20} /> : <Bot size={20} />}
                      </div>
                      <div
                        className="chat-message-content"
                        style={{ position: 'relative' }}
                        onMouseEnter={(e) => {
                          const actions = e.currentTarget.querySelector('.message-actions');
                          if (actions) actions.style.opacity = '1';
                        }}
                        onMouseLeave={(e) => {
                          const actions = e.currentTarget.querySelector('.message-actions');
                          if (actions) actions.style.opacity = '0';
                        }}
                      >
                        {message.content ? (
                          <MarkdownMessage
                            content={message.content}
                            isStreaming={streaming && index === messages.length - 1}
                          />
                        ) : (
                          <Loader2 className="animate-spin" size={20} style={{ color: 'var(--gray-500)' }} />
                        )}
                        {message.content && !(streaming && index === messages.length - 1) && (
                          <div
                            className="message-actions"
                            style={{
                              display: 'flex',
                              gap: '4px',
                              marginTop: '6px',
                              opacity: 0,
                              transition: 'opacity 0.15s ease',
                            }}
                          >
                            <button
                              onClick={() => handleCopyMessage(message.content, index)}
                              title="Copy"
                              style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: '4px',
                                padding: '3px 8px',
                                fontSize: 'var(--text-xs)',
                                color: copiedIndex === index ? '#22c55e' : 'var(--gray-500)',
                                background: 'var(--gray-100)',
                                border: '1px solid var(--gray-200)',
                                borderRadius: 'var(--radius-sm)',
                                cursor: 'pointer',
                                transition: 'color 0.15s ease',
                              }}
                            >
                              {copiedIndex === index ? <Check size={12} /> : <Copy size={12} />}
                              {copiedIndex === index ? 'Copied' : 'Copy'}
                            </button>
                            <button
                              onClick={() => handleRetryMessage(message, index)}
                              disabled={streaming}
                              title={message.role === 'user' ? 'Retry this message' : 'Regenerate response'}
                              style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: '4px',
                                padding: '3px 8px',
                                fontSize: 'var(--text-xs)',
                                color: 'var(--gray-500)',
                                background: 'var(--gray-100)',
                                border: '1px solid var(--gray-200)',
                                borderRadius: 'var(--radius-sm)',
                                cursor: streaming ? 'not-allowed' : 'pointer',
                                opacity: streaming ? 0.4 : 1,
                                transition: 'opacity 0.15s ease',
                              }}
                            >
                              <RotateCcw size={12} />
                              {message.role === 'user' ? 'Retry' : 'Regenerate'}
                            </button>
                              {message.role === 'assistant' && message.content && (
                                <ExportButton
                                  content={message.content}
                                  title={message.content.trim().split(/\s+/).slice(0, 6).join(' ')}
                                  compact={false}
                                />
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                  <div ref={messagesEndRef} />
                </>
              )}
            </div>

            <div className="chat-input-container">
              <div style={{ padding: '0 var(--spacing-4)', display: 'flex', justifyContent: 'center' }}>
                <div className="input-chat-container" style={{ width: '100%', maxWidth: '800px' }}>

                  <div style={{
                    padding: 'var(--spacing-2) var(--spacing-3)',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    borderBottom: '1px solid var(--gray-100)',
                    backgroundColor: 'var(--bg-card)',
                    fontSize: 'var(--text-xs)',
                  }}>
                    <button
                      onClick={() => setShowSettings(!showSettings)}
                      className="btn-settings"
                    >
                      <SettingsIcon size={14} />
                      {showSettings ? 'Hide' : 'Settings'}
                    </button>

                    <div style={{ display: 'flex', gap: 'var(--spacing-2)', alignItems: 'center' }}>
                       <button
                        onClick={() => setShowExportHistory(true)}
                        className="btn-settings-sm"
                      >
                        <Download size={14} />
                        Exports
                      </button>
                      {is256KModel(chatSettings.model) && (
                        <span style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '4px',
                          color: 'var(--primary)',
                          fontWeight: '600'
                        }}>
                          <Zap size={12} />
                          128K
                        </span>
                      )}

                      {retrievedChunks.length > 0 && (
                        <button
                          onClick={() => setShowSources(!showSources)}
                          className="btn-settings-sm"
                        >
                          {retrievedChunks.length} sources
                        </button>
                      )}
                    </div>
                  </div>

                  {showSettings && (
                    <div style={{
                      padding: 'var(--spacing-3)',
                      backgroundColor: 'var(--bg-card)',
                      borderBottom: '1px solid var(--gray-100)',
                      display: 'flex',
                      flexWrap: 'wrap',
                      gap: 'var(--spacing-3)',
                      fontSize: 'var(--text-xs)',
                    }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-2)' }}>
                        <span style={{ fontWeight: '500' }}>Provider:</span>
                        <select
                          className="form-select"
                          value={chatSettings.provider_name}
                          onChange={(e) => setChatSettings({ ...chatSettings, provider_name: e.target.value })}
                          style={{ fontSize: 'var(--text-xs)', padding: 'var(--spacing-1) var(--spacing-2)' }}
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
                          style={{ fontSize: 'var(--text-xs)', padding: 'var(--spacing-1) var(--spacing-2)' }}
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
                          <option value="auto">Auto</option>
                          <option value="cot">Chain of Thought</option>
                          <option value="deep">Deep Reasoning</option>
                        </select>
                      </div>

                      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-2)' }}>
                        <span style={{ fontWeight: '500' }}>Top-K:</span>
                        <input
                          type="number"
                          min="1"
                          max={is256KModel(chatSettings.model) ? "20" : "10"}
                          value={chatSettings.top_k}
                          onChange={(e) => setChatSettings({ ...chatSettings, top_k: parseInt(e.target.value) })}
                          style={{ width: '60px', fontSize: 'var(--text-xs)', padding: 'var(--spacing-1)' }}
                        />
                        <span style={{ fontSize: '10px', color: 'var(--gray-500)' }}>
                          (max {is256KModel(chatSettings.model) ? "20" : "10"})
                        </span>
                      </div>
                    </div>
                  )}

                  {showSources && retrievedChunks.length > 0 && (
                    <div style={{
                      padding: 'var(--spacing-3)',
                      backgroundColor: 'var(--gray-50)',
                      borderBottom: '1px solid var(--gray-100)',
                      maxHeight: '200px',
                      overflowY: 'auto'
                    }}>
                      <h4 style={{ fontSize: 'var(--text-sm)', fontWeight: '600', marginBottom: 'var(--spacing-2)' }}>
                        Retrieved Sources:
                      </h4>
                      {retrievedChunks.map((chunk, idx) => (
                        <div key={idx} style={{
                          padding: 'var(--spacing-2)',
                          marginBottom: 'var(--spacing-2)',
                          backgroundColor: 'white',
                          borderRadius: 'var(--radius)',
                          border: '1px solid var(--gray-200)'
                        }}>
                          <div style={{ fontSize: 'var(--text-xs)', color: 'var(--gray-600)', marginBottom: 'var(--spacing-1)' }}>
                            {chunk.metadata?.filename} Score: {(chunk.score * 100).toFixed(1)}%
                          </div>
                          <div style={{ fontSize: 'var(--text-xs)', color: 'var(--gray-700)' }}>
                            {chunk.text.substring(0, 150)}...
                          </div>
                        </div>
                      ))}
                    </div>
                  )}

                  <div style={{ position: 'relative', padding: 'var(--spacing-3) var(--spacing-4)' }}>
                    <textarea
                      ref={textareaRef}
                      placeholder="Ask a question about your documents..."
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

                    <button
                      className="btn-send"
                      onClick={handleSend}
                      disabled={!input.trim() || streaming}
                    >
                      {streaming ? <Loader2 size={18} className="animate-spin" /> : <Send size={18} />}
                    </button>
                  </div>

                  <div style={{
                    padding: '0 var(--spacing-4) var(--spacing-2)',
                    fontSize: 'var(--text-xs)',
                    color: 'var(--gray-500)',
                    textAlign: 'center',
                  }}>
                    {streaming ? 'AgentRAG is thinking...' : 'Press Enter to send - Shift+Enter for new line'}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
      <ExportHistory open={showExportHistory} onClose={() => setShowExportHistory(false)} />
    </Layout>
  );
};

export default RAGChat;