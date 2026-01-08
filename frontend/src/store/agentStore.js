import { create } from 'zustand';
import api from '../services/api';

export const useAgentStore = create((set, get) => ({
  agents: [],
  currentAgent: null,
  executions: [],
  currentExecution: null,
  loading: false,
  executing: false,
  error: null,

  // Load all user's agents
  loadAgents: async () => {
    set({ loading: true, error: null });
    try {
      const response = await api.get('/api/agents/');
      set({ agents: response.data, loading: false });
    } catch (error) {
      set({ error: error.message, loading: false });
    }
  },

  // Load single agent with details
  loadAgent: async (agentId) => {
    set({ loading: true, error: null });
    try {
      const response = await api.get(`/api/agents/${agentId}`);
      set({ 
        currentAgent: response.data,
        loading: false 
      });
      return response.data;
    } catch (error) {
      set({ error: error.message, loading: false });
      throw error;
    }
  },

  // Create new agent
  createAgent: async (data) => {
    set({ loading: true, error: null });
    try {
      const response = await api.post('/api/agents/', data);
      const agents = [...get().agents, response.data];
      set({ agents, loading: false });
      return response.data;
    } catch (error) {
      set({ error: error.message, loading: false });
      throw error;
    }
  },

  // Update agent configuration
  updateAgent: async (agentId, data) => {
    set({ loading: true, error: null });
    try {
      const response = await api.put(`/api/agents/${agentId}`, data);
      const agents = get().agents.map(a => 
        a.id === agentId ? response.data : a
      );
      set({ agents, currentAgent: response.data, loading: false });
      return response.data;
    } catch (error) {
      set({ error: error.message, loading: false });
      throw error;
    }
  },

  // Delete agent
  deleteAgent: async (agentId) => {
    set({ loading: true, error: null });
    try {
      await api.delete(`/api/agents/${agentId}`);
      const agents = get().agents.filter(a => a.id !== agentId);
      set({ agents, loading: false });
      
      if (get().currentAgent?.id === agentId) {
        set({ currentAgent: null });
      }
    } catch (error) {
      set({ error: error.message, loading: false });
      throw error;
    }
  },

  // Execute agent task
  executeAgent: async (agentId, inputData) => {
    set({ executing: true, error: null });
    try {
      const response = await api.post(`/api/agents/${agentId}/execute`, inputData);
      set({ 
        currentExecution: response.data,
        executing: false 
      });
      return response.data;
    } catch (error) {
      set({ error: error.message, executing: false });
      throw error;
    }
  },

  // Load execution history for agent
  loadExecutions: async (agentId) => {
    set({ loading: true, error: null });
    try {
      const response = await api.get(`/api/agents/${agentId}/executions`);
      set({ executions: response.data, loading: false });
    } catch (error) {
      set({ error: error.message, loading: false });
    }
  },

  // Get specific execution details
  loadExecution: async (executionId) => {
    set({ loading: true, error: null });
    try {
      const response = await api.get(`/api/agents/executions/${executionId}`);
      set({ 
        currentExecution: response.data,
        loading: false 
      });
      return response.data;
    } catch (error) {
      set({ error: error.message, loading: false });
      throw error;
    }
  },

  // Toggle agent active status
  toggleAgentStatus: async (agentId) => {
    const agent = get().agents.find(a => a.id === agentId);
    if (!agent) return;

    try {
      const response = await api.patch(`/api/agents/${agentId}/toggle`);
      const agents = get().agents.map(a => 
        a.id === agentId ? response.data : a
      );
      set({ agents });
    } catch (error) {
      set({ error: error.message });
      throw error;
    }
  },

  clearError: () => {
    set({ error: null });
  }
}));