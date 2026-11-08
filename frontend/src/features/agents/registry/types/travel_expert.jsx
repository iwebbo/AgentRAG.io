// Agent type « travel_expert » — tout ce qui le concerne est ici (voir registry/README.md)

export default {
  name: 'Travel Expert',
  description: 'Personalized travel planning with integrated web search',
  icon: '⌘', color: '#0ea5e9', badge: 'fixed', mcp: [],
  defaultConfig: (providers) => ({ llm_provider: providers[0]?.name || 'ollama', llm_model: 'mistrallite:latest', llm_temperature: 0.4, travel_config: { search_preferences: { budget_aware: true, eco_friendly: true, accessibility: false } } }),
  mcpConfig: {}, requiredFields: [],
  executeFields: [
    { name: 'mode', label: 'Mode', type: 'select', required: true, options: [ { value: 'itinerary_planning', label: 'Itinerary planning' }, { value: 'destination_search', label: 'Destination search' }, { value: 'budget_analysis', label: 'Budget analysis' } ], defaultValue: 'itinerary_planning' },
    { name: 'query', label: 'Travel request', type: 'textarea', placeholder: 'Trip to Japan for 2 weeks, couple, budget 4000€...', required: true }
  ],
  buildInput: (d) => ({ mode: d.mode || 'itinerary_planning', query: d.query }),
};
