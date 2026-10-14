import { create } from 'zustand';
import api from '../services/api';

// Les chunks SSE arrivent bien plus vite que 60 fps : on les accumule et on ne
// publie qu'une fois par frame. Évite un re-render complet par token.
let pending = '';
let rafId = null;

export const useChatStore = create((set, get) => {
  const flush = () => {
    if (rafId !== null) {
      cancelAnimationFrame(rafId);
      rafId = null;
    }
    if (!pending) return;
    const chunk = pending;
    pending = '';
    const messages = get().messages;
    if (!messages.length) return;
    const last = messages[messages.length - 1];
    // Immutable : seul le dernier message change de référence (permet React.memo sur les autres).
    set({ messages: [...messages.slice(0, -1), { ...last, content: (last.content || '') + chunk }] });
  };

  const discardPending = () => {
    pending = '';
    if (rafId !== null) {
      cancelAnimationFrame(rafId);
      rafId = null;
    }
  };

  return {
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
        discardPending();
        set({
          currentConversation: response.data,
          messages: response.data.messages || [],
          loading: false,
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
        const conversations = get().conversations.filter((c) => c.id !== conversationId);
        set({ conversations });

        if (get().currentConversation?.id === conversationId) {
          discardPending();
          set({ currentConversation: null, messages: [] });
        }
      } catch (error) {
        set({ error: error.message });
        throw error;
      }
    },

    addMessage: (message) => {
      flush();
      set({ messages: [...get().messages, message] });
    },

    updateLastMessage: (content) => {
      if (!content) return;
      pending += content;
      if (rafId === null) rafId = requestAnimationFrame(() => { rafId = null; flush(); });
    },

    setStreaming: (streaming) => {
      flush(); // ne jamais perdre le dernier chunk à la fin du stream
      set({ streaming });
    },

    clearError: () => set({ error: null }),
  };
});
