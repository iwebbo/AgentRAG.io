import { create } from 'zustand';
import api from '../services/api';

export const useChatStore = create((set, get) => ({
  conversations: [],
  currentConversation: null,
  messages: [],
  loading: false,
  streaming: false,
  error: null,

  loadConversations: async () => {
    set({ loading: true });
    try {
      const response = await api.get('/api/conversations/');
      set({ conversations: response.data, loading: false });
    } catch (error) {
      set({ error: error.message, loading: false });
    }
  },

  loadConversation: async (conversationId) => {
    set({ loading: true });
    try {
      const response = await api.get(`/api/conversations/${conversationId}`);
      set({ 
        currentConversation: response.data,
        messages: response.data.messages || [],
        loading: false 
      });
    } catch (error) {
      set({ error: error.message, loading: false });
    }
  },

  createConversation: async (data) => {
    try {
      const response = await api.post('/api/conversations/', data);
      set({ currentConversation: response.data });
      return response.data;
    } catch (error) {
      set({ error: error.message });
      throw error;
    }
  },

  deleteConversation: async (conversationId) => {
    try {
      await api.delete(`/api/conversations/${conversationId}`);
      const conversations = get().conversations.filter(c => c.id !== conversationId);
      set({ conversations });
      
      if (get().currentConversation?.id === conversationId) {
        set({ currentConversation: null, messages: [] });
      }
    } catch (error) {
      set({ error: error.message });
      throw error;
    }
  },

  addMessage: (message) => {
    set({ messages: [...get().messages, message] });
  },

  updateLastMessage: (content) => {
    // In case debug return prompt LLM
    //console.log('Chunk reçu :', content);
    //console.log('updateLastMessage reçu:', content, 'Type:', typeof content);
    const messages = [...get().messages];
    if (messages.length > 0) {
      messages[messages.length - 1].content += content;
      set({ messages });
    }
  },

  setStreaming: (streaming) => {
    set({ streaming });
  },

  clearError: () => {
    set({ error: null });
  }
}));